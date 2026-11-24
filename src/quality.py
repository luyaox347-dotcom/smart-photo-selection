"""Traditional technical quality scoring for original images and A's records."""

from __future__ import annotations

import csv
import hashlib
from io import BytesIO
from math import isfinite, log1p
from pathlib import Path
from time import perf_counter
from typing import Iterable, Mapping

import cv2
import numpy as np
from PIL import Image, ImageOps

from config.quality import DEFAULT_QUALITY_CONFIG, QualityConfig
from config.settings import SUPPORTED_EXTENSIONS
from src.preprocessing import _derive_group_id, _safe_id


IDENTITY_FIELDS = ("group_id", "image_id", "source_id", "original_path", "processed_path")
RAW_FIELDS = ("sharpness_raw", "exposure_raw", "contrast_raw")
SCORE_FIELDS = ("sharpness_score", "exposure_score", "contrast_score", "quality_score")
METRIC_FIELDS = RAW_FIELDS + SCORE_FIELDS + (
    "mean_luminance", "underexposed_ratio", "overexposed_ratio", "width", "height",
    "sharpness_width", "sharpness_height", "read_time_ms", "compute_time_ms",
)
QUALITY_CSV_FIELDS = IDENTITY_FIELDS + (
    "record_kind", "crop_id", "image_path", "source_image_path",
) + METRIC_FIELDS + ("status", "error")
_LEVELS = np.arange(256, dtype=np.float64)


class _ImageInputError(ValueError):
    """Expected invalid image input."""


def _read_image(path: Path, *, original: bool) -> tuple[Image.Image, str | None]:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise _ImageInputError(f"Unsupported image extension: {path.suffix or '[none]'}")
    # Hash exactly the bytes decoded for a standalone call. A already supplies
    # the original identity for processed and crop records.
    with path.open("rb") as stream:
        data = stream.read() if original else None
        with Image.open(BytesIO(data) if data is not None else stream) as image:
            if image.format not in {"JPEG", "PNG"}:
                raise _ImageInputError(f"Unsupported image format: {image.format}")
            decoded = ImageOps.exif_transpose(image) if original else image.copy()
    return decoded, hashlib.sha256(data).hexdigest() if data is not None else None


def _luminance(image: Image.Image, config: QualityConfig) -> np.ndarray:
    if image.mode == "I" or image.mode.startswith("I;16"):
        pixels = np.asarray(image, dtype=np.float32)
        return np.rint(np.clip(pixels, 0, 65535) / 257).astype(np.uint8)
    if "A" in image.getbands() or "transparency" in image.info:
        rgb = image.convert("RGBA")
        gray = config.alpha_background
        background = Image.new("RGBA", image.size, (gray, gray, gray, 255))
        image = Image.alpha_composite(background, rgb)
    if image.mode in ("1", "L"):
        return np.asarray(image.convert("L"))
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)


def score_quality_metrics(
    sharpness_raw: float,
    exposure_raw: float,
    contrast_raw: float,
    *,
    config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> dict[str, float]:
    """Apply fixed normalization and weights to reusable, finite measurements."""
    raw = (sharpness_raw, exposure_raw, contrast_raw)
    if any(not isfinite(value) for value in raw):
        raise ValueError("Quality measurements must be finite")
    sharpness = min(config.sharpness_reference, max(0, sharpness_raw))
    if config.normalization == "log_sharpness":
        sharpness = log1p(sharpness) / log1p(config.sharpness_reference)
    else:
        sharpness /= config.sharpness_reference
    exposure = 1 - min(1, max(0, exposure_raw))
    contrast = min(config.contrast_reference, max(0, contrast_raw)) / config.contrast_reference
    scores = (10 * sharpness, 10 * exposure, 10 * contrast)
    quality = sum(weight * score for weight, score in zip(config.weights, scores))
    return dict(zip(SCORE_FIELDS, (*scores, min(10.0, quality))))


def _measure_image(image: Image.Image, config: QualityConfig) -> dict:
    gray = _luminance(image, config)
    height, width = gray.shape
    scale = min(1, config.max_sharpness_edge / max(width, height))
    sharp_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    sharp_gray = gray
    if sharp_size != (width, height):
        sharp_gray = cv2.resize(gray, sharp_size, interpolation=cv2.INTER_AREA)
    laplacian = cv2.Laplacian(sharp_gray, cv2.CV_64F, ksize=config.laplacian_kernel)
    sharpness = float(laplacian.var())

    # Exposure and contrast use native pixels so shrinking cannot hide clipping.
    histogram = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel().astype(np.float64)
    fractions = histogram / histogram.sum()
    mean = float(_LEVELS @ fractions)
    dark = float(fractions[:config.dark_threshold + 1].sum())
    bright = float(fractions[config.bright_threshold:].sum())
    exposure = min(1.0, dark + bright)
    contrast = float(np.sqrt((_LEVELS - mean) ** 2 @ fractions))
    return {
        "sharpness_raw": sharpness, "exposure_raw": exposure, "contrast_raw": contrast,
        "mean_luminance": mean, "underexposed_ratio": dark, "overexposed_ratio": bright,
        "width": width, "height": height,
        "sharpness_width": sharp_size[0], "sharpness_height": sharp_size[1],
    }


def _result(record: Mapping, crop: Mapping | None = None) -> dict:
    scored = record if crop is None else crop
    return {
        **{key: record.get(key) for key in IDENTITY_FIELDS},
        "record_kind": "image" if crop is None else "crop",
        "crop_id": scored.get("crop_id") if crop is not None else None,
        "image_path": scored.get("image_path"),
        "source_image_path": scored.get("source_image_path") if crop is not None else None,
        **dict.fromkeys(METRIC_FIELDS),
        "status": "error",
        "error": None,
    }


def _evaluate(result: dict, config: QualityConfig, *, original: bool = False) -> dict:
    if not result["image_path"]:
        result["error"] = "Missing image_path"
        return result
    path = Path(result["image_path"])
    result["image_path"] = str(path)
    started = perf_counter()
    try:
        image, digest = _read_image(path, original=original)
    except (OSError, SyntaxError, Image.DecompressionBombError, _ImageInputError) as exc:
        result["error"] = str(exc)
        return result
    if digest is not None:
        result["image_id"] = f"{result['group_id']}__{result['source_id']}__{digest[:8]}"
    compute_started = perf_counter()
    try:
        raw = _measure_image(image, config)
    except cv2.error as exc:
        result["error"] = f"OpenCV metric calculation failed: {exc}"
        return result
    if any(not isfinite(value) for value in raw.values()):
        result["error"] = "Quality measurements must be finite"
        return result
    scores = score_quality_metrics(*(raw[key] for key in RAW_FIELDS), config=config)
    result.update(
        raw, **scores, status="success",
        read_time_ms=(compute_started - started) * 1000,
        compute_time_ms=(perf_counter() - compute_started) * 1000,
    )
    return result


def evaluate_quality(
    image_path: str | Path, *, config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> dict:
    """Read a standalone original, honoring its EXIF orientation once."""
    path = Path(image_path)
    record = {
        "group_id": _derive_group_id([path]),
        "source_id": _safe_id(path.stem, "image"),
        "original_path": str(path),
        "image_path": str(path),
    }
    return _evaluate(_result(record), config, original=True)


def evaluate_quality_batch(
    records: Iterable[Mapping], *, config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> list[dict]:
    """Score A's preprocessed whole-image records in input order."""
    results = []
    for record in records:
        if record.get("crop_id") is not None:
            raise ValueError("Use evaluate_crop_quality for A's crop records")
        result = _result(record)
        if record.get("status") == "success":
            _evaluate(result, config)
        else:
            result["error"] = record.get("error") or "Upstream preprocessing failed"
        results.append(result)
    return results


def evaluate_crop_quality(
    record: Mapping, crops: Iterable[Mapping], *, config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> list[dict]:
    """Score A's candidates for one parent record without regenerating them."""
    results = []
    for crop in crops:
        result = _result(record, crop)
        if record.get("status") != "success":
            result["error"] = record.get("error") or "Upstream preprocessing failed"
        elif (not crop.get("crop_id") or crop.get("image_id") != record.get("image_id")
              or not crop.get("source_image_path") or not record.get("image_path")
              or Path(crop["source_image_path"]).resolve() != Path(record["image_path"]).resolve()):
            result["error"] = "Crop ID or source does not match the preprocessing record"
        else:
            _evaluate(result, config)
        results.append(result)
    return results


def export_quality_csv(results: Iterable[Mapping], output_path: str | Path) -> Path:
    """Write one kind of result per UTF-8 CSV, with missing values as empty cells."""
    rows = list(results)
    if len({row["record_kind"] for row in rows}) > 1:
        raise ValueError("Export whole-image and crop quality results separately")
    path = Path(output_path)
    if path.suffix.lower() != ".csv":
        raise ValueError("Quality CSV output requires a .csv filename")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=QUALITY_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path
