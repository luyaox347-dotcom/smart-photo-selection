import csv
from dataclasses import replace
from math import isfinite

import cv2
import numpy as np
import pytest
from PIL import Image

from config.quality import DEFAULT_QUALITY_CONFIG
from scripts.compare_quality_annotations import compare_annotations
from src.cropping import generate_crops
from src.preprocessing import preprocess_images
from src.quality import (
    QUALITY_CSV_FIELDS,
    evaluate_crop_quality,
    evaluate_quality,
    evaluate_quality_batch,
    export_quality_csv,
    score_quality_metrics,
)


@pytest.fixture
def target():
    y, x = np.indices((228, 336))
    return np.where((x // 19 + y // 19) % 2, 180, 74).astype(np.uint8)


def _save(directory, name, array):
    path = directory / name
    Image.fromarray(array).save(path)
    return path


def test_blur_reduces_sharpness_at_controlled_scale(tmp_path, target):
    path = _save(tmp_path, "清晰 图.png", target)
    blurred = _save(tmp_path, "blurred.png", cv2.GaussianBlur(target, (0, 0), 3))
    sharp = evaluate_quality(path)
    soft = evaluate_quality(blurred)
    assert sharp["status"] == soft["status"] == "success"
    assert sharp["sharpness_raw"] > soft["sharpness_raw"]
    assert sharp["sharpness_score"] > soft["sharpness_score"]
    larger = _save(tmp_path, "large.png", np.repeat(np.repeat(target, 4, axis=0), 4, axis=1))
    sized = evaluate_quality(larger, config=replace(DEFAULT_QUALITY_CONFIG, max_sharpness_edge=336))
    assert (sized["sharpness_width"], sized["sharpness_height"]) == (336, 228)
    assert sized["sharpness_raw"] == pytest.approx(sharp["sharpness_raw"])


def test_exposure_counts_both_tails_instead_of_a_good_mean(tmp_path, target):
    clean = evaluate_quality(_save(tmp_path, "normal.png", target))
    for shift, tail in [(150, "overexposed"), (-150, "underexposed")]:
        clipped = np.clip(target.astype(np.int16) + shift, 0, 255).astype(np.uint8)
        result = evaluate_quality(_save(tmp_path, f"{tail}.png", clipped))
        assert result[f"{tail}_ratio"] > 0.45
        assert clean["exposure_raw"] < result["exposure_raw"]
        assert clean["exposure_score"] > result["exposure_score"]
    two_tails = np.where(target > 127, 255, 0).astype(np.uint8)
    result = evaluate_quality(_save(tmp_path, "two_tails.png", two_tails))
    assert result["mean_luminance"] == pytest.approx(127.5)
    assert result["exposure_raw"] == 1
    assert result["exposure_score"] == 0


def test_flattening_reduces_luminance_contrast(tmp_path, target):
    clean = evaluate_quality(_save(tmp_path, "normal.png", target))
    flat = np.rint(127 + 0.25 * (target.astype(float) - 127)).astype(np.uint8)
    result = evaluate_quality(_save(tmp_path, "flat.png", flat))
    assert result["contrast_raw"] < clean["contrast_raw"]
    assert result["contrast_score"] < clean["contrast_score"]


@pytest.mark.parametrize(
    ("mode", "size", "color", "gray"),
    [
        ("L", (12, 18), 0, 0),
        ("L", (1, 1), 127, 127),
        ("RGB", (1, 5), (127, 127, 127), 127),
        ("RGBA", (12, 18), (255, 0, 0, 0), 127),
        ("RGBA", (12, 18), (0, 255, 255, 0), 127),
        ("I;16", (12, 18), 65535, 255),
    ],
)
def test_constant_grayscale_transparency_and_tiny_inputs(tmp_path, mode, size, color, gray):
    path = tmp_path / "boundary.png"
    Image.new(mode, size, color).save(path)
    result = evaluate_quality(path)
    assert result["status"] == "success"
    assert result["mean_luminance"] == gray
    assert result["sharpness_raw"] == result["contrast_raw"] == 0
    assert all(isfinite(result[key]) and 0 <= result[key] <= 10 for key in
               ("quality_score", "sharpness_score", "exposure_score", "contrast_score"))
    if gray == 0:
        assert result["quality_score"] == 0


@pytest.mark.parametrize("failure", ["missing", "corrupt", "unsupported", "disguised"])
def test_invalid_inputs_leave_scores_missing(tmp_path, failure):
    path = tmp_path / ("invalid.bmp" if failure == "unsupported" else "invalid.png")
    if failure == "corrupt":
        path.write_bytes(b"not a photo")
    elif failure in {"unsupported", "disguised"}:
        Image.new("RGB", (10, 10)).save(path, format="BMP")
    result = evaluate_quality(path)
    assert result["status"] == "error"
    assert result["error"]
    assert result["quality_score"] is None
    assert result["sharpness_raw"] is None


def test_fixed_normalization_is_deterministic_and_batch_independent(tmp_path, target):
    normal = _save(tmp_path, "normal.png", target)
    extreme = _save(tmp_path, "extreme.png", np.zeros_like(target))
    config = replace(DEFAULT_QUALITY_CONFIG, normalization="linear")
    records = preprocess_images([normal, extreme], output_dir=tmp_path / "processed")
    alone = evaluate_quality_batch(records[:1], config=config)[0]
    in_batch = evaluate_quality_batch(reversed(records), config=config)[1]
    metrics = [field for field in QUALITY_CSV_FIELDS if not field.endswith("_time_ms")]
    assert [alone[key] for key in metrics] == [in_batch[key] for key in metrics]
    standalone = evaluate_quality(normal, config=config)
    assert standalone["image_id"] == alone["image_id"]
    assert standalone["quality_score"] == alone["quality_score"]


def test_validation_and_bounds():
    with pytest.raises(ValueError):
        replace(DEFAULT_QUALITY_CONFIG, weights=(0.5, 0.3, 0.3))
    with pytest.raises(ValueError):
        replace(DEFAULT_QUALITY_CONFIG, weights=(-0.1, 0.5, 0.6))
    with pytest.raises(ValueError):
        replace(DEFAULT_QUALITY_CONFIG, sharpness_reference=float("nan"))
    for value in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            score_quality_metrics(value, 0, 0)
    assert score_quality_metrics(1e300, -1e300, 1e300)["quality_score"] == 10


def test_batch_inherits_a_ids_paths_and_failure_preserves_order_in_csv(tmp_path, target):
    folder = tmp_path / "中文 路径"
    folder.mkdir()
    normal = _save(folder, "清晰 图.png", target)
    black = _save(folder, "黑图.png", np.zeros_like(target))
    broken = folder / "损坏.jpg"
    broken.write_bytes(b"invalid")
    records = preprocess_images([normal, broken, black, normal], group_id="G 示例",
                                output_dir=folder / "A 副本")
    results = evaluate_quality_batch(records)
    assert [row["status"] for row in results] == ["success", "error", "success", "success"]
    for row, record in zip(results, records):
        for field in ("image_id", "source_id", "group_id", "original_path", "image_path", "processed_path"):
            assert row[field] == record[field]
    assert results[0]["image_id"] == results[3]["image_id"]
    assert results[1]["error"] == records[1]["error"]
    output = export_quality_csv(results, folder / "B 分数.csv")
    with output.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        assert reader.fieldnames == list(QUALITY_CSV_FIELDS)
    assert [row["source_id"] for row in rows] == [record["source_id"] for record in records]
    assert rows[1]["quality_score"] == rows[1]["exposure_raw"] == ""
    assert float(rows[2]["quality_score"]) == 0


def test_a_exif_and_crop_records_use_correct_paths_and_parent(tmp_path, target):
    image = Image.fromarray(target)
    path = tmp_path / "portrait.jpg"
    exif = Image.Exif()
    exif[274] = 6
    image.save(path, exif=exif)
    original = path.read_bytes()
    parent = preprocess_images([path], group_id="G_scene", output_dir=tmp_path / "copies")[0]
    row = evaluate_quality_batch([parent])[0]
    direct = evaluate_quality(path)
    assert (row["width"], row["height"]) == (target.shape[0], target.shape[1])
    assert (direct["width"], direct["height"]) == (row["width"], row["height"])
    assert direct["quality_score"] == pytest.approx(row["quality_score"])
    candidates = generate_crops(parent["image_path"], output_dir=tmp_path / "crops")
    results = evaluate_crop_quality(parent, candidates)
    assert len(results) > 1
    for score, crop in zip(results, candidates):
        assert score["status"] == "success"
        assert score["record_kind"] == "crop"
        assert score["crop_id"] == crop["crop_id"]
        assert score["image_id"] == parent["image_id"]
        assert score["original_path"] == parent["original_path"]
        assert score["source_image_path"] == parent["processed_path"]
        assert score["image_path"] == crop["image_path"]
        assert (score["width"], score["height"]) == (crop["width"], crop["height"])
    assert results[0]["quality_score"] == row["quality_score"]  # A's original candidate
    assert path.read_bytes() == original
    mismatched = evaluate_crop_quality(parent, [{**candidates[0], "source_image_path": str(path)}])
    assert mismatched[0]["status"] == "error"
    assert mismatched[0]["quality_score"] is None
    with pytest.raises(ValueError):
        export_quality_csv([row, results[0]], tmp_path / "mixed.csv")


def test_annotation_comparison_tracks_evaluators_and_ties():
    scores = [
        {"record_kind": "image", "status": "success", "group_id": "G",
         "image_id": name, "quality_score": score}
        for name, score in (("a", 8), ("b", 8), ("c", 5))
    ]
    votes = [
        {"group_id": "G", "evaluator_id": evaluator, "selected_image_id": selected,
         "is_tie": tie, "tied_image_ids": tied, "reason": reason}
        for evaluator, selected, tie, tied, reason in (
            ("E001", "", "true", "b;c", "fixture tie"),
            ("E002", "c", "false", "", "fixture preference"),
            ("E003", "missing-id", "false", "", "fixture missing"),
        )
    ]
    result = compare_annotations(scores, votes)
    assert result["participating_groups"] == 1
    assert result["compared_annotations"] == 2
    assert result["annotation_agreement_rate"] == 0.5
    assert result["comparisons"][0]["predicted_image_ids"] == ["a", "b"]
    assert result["comparisons"][1]["human_choices"] == {"c": 5}
    assert result["comparisons"][1]["reason"] == "fixture preference"
    pending = compare_annotations(scores, [])
    assert pending["status"] == "pending"
    assert pending["annotation_agreement_rate"] is None
