from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from src.cropping import generate_crops


def _make_subject_image(path: Path, size=(480, 320)) -> None:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 80, 150, 250), fill="black")
    image.save(path)


@pytest.mark.parametrize("size", [(480, 320), (320, 480), (800, 120)])
def test_generate_crops_are_bounded_and_saved(tmp_path, size):
    image_path = tmp_path / f"sample_{size[0]}x{size[1]}.png"
    _make_subject_image(image_path, size)

    results = generate_crops(image_path, output_dir=tmp_path / "crops")

    assert 1 <= len(results) <= 7
    assert results[0]["source"] == "original"
    boxes = []
    for result in results:
        x1, y1, x2, y2 = result["box"]
        assert 0 <= x1 < x2 <= size[0]
        assert 0 <= y1 < y2 <= size[1]
        assert Path(result["image_path"]).is_file()
        boxes.append(tuple(result["box"]))
    assert len(boxes) == len(set(boxes))


def test_square_image_does_not_duplicate_original(tmp_path):
    image_path = tmp_path / "square.png"
    _make_subject_image(image_path, (300, 300))

    results = generate_crops(image_path, output_dir=tmp_path / "crops")

    original_box = (0, 0, 300, 300)
    assert sum(tuple(item["box"]) == original_box for item in results) == 1


def test_generate_crops_respects_limit(tmp_path):
    image_path = tmp_path / "sample.png"
    _make_subject_image(image_path)

    results = generate_crops(image_path, max_crops=3, output_dir=tmp_path / "crops")

    assert len(results) <= 3
    assert results[0]["generation_stats"]["returned_candidate_count"] == len(results)
    assert 0 < results[0]["generation_stats"]["candidate_validity_rate"] <= 100


def test_generate_crops_rejects_invalid_limit(tmp_path):
    image_path = tmp_path / "sample.png"
    _make_subject_image(image_path)

    with pytest.raises(ValueError):
        generate_crops(image_path, max_crops=8, output_dir=tmp_path / "crops")


@pytest.mark.parametrize(
    ("filename", "expects_face"),
    [
        ("05_face_astronaut.png", True),
        ("04_tall_eiffel.jpg", False),
        ("07_dog_cc0.jpg", False),
    ],
)
def test_yunet_face_pool_real_cases(tmp_path, filename, expects_face):
    sample = Path("data/sample/real_cases") / filename
    if not sample.is_file():
        pytest.skip(f"real sample unavailable: {sample}")

    results = generate_crops(sample, output_dir=tmp_path / "crops")

    stats = results[0]["generation_stats"]
    assert stats["face_detector"] == "yunet_2023mar"
    assert (stats["face_detection_count"] > 0) is expects_face
    assert any(item["source"] == "face" for item in results) is expects_face
