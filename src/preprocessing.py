"""Image validation, EXIF normalization, and metadata extraction.

OpenCV is deliberately used only for low-level decode validation. Pillow is the
single authority for EXIF orientation so that an image cannot be rotated twice.
Original files are never modified.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from time import perf_counter
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from config.settings import PROCESSED_DATA_DIR, SUPPORTED_EXTENSIONS


EXIF_ORIENTATION_TAG = 274
EXIF_DATETIME_ORIGINAL_TAG = 36867
EXIF_MAKE_TAG = 271
EXIF_MODEL_TAG = 272


def _safe_id(value: str, fallback: str) -> str:
    """Return a filesystem-friendly but still human-readable identifier."""
    normalized = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    normalized = normalized.strip("._-")
    return normalized or fallback


def _derive_group_id(paths: list[Path]) -> str:
    if not paths:
        return "empty_group"
    parents = {str(path.parent.resolve()) for path in paths}
    if len(parents) == 1:
        return _safe_id(paths[0].parent.name, "group")
    digest = hashlib.sha256(
        "\n".join(sorted(str(path.resolve()) for path in paths)).encode("utf-8")
    ).hexdigest()[:10]
    return f"batch_{digest}"


def _decode_with_opencv(path: Path) -> np.ndarray:
    """Decode without applying EXIF orientation; supports Unicode Windows paths."""
    encoded = np.fromfile(path, dtype=np.uint8)
    if encoded.size == 0:
        raise ValueError("文件为空")
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("OpenCV 无法解码图片像素")
    return image


def _content_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _png_compatible(image: Image.Image) -> Image.Image:
    """Convert uncommon Pillow modes to a PNG-safe representation."""
    if image.mode == "P":
        return image.convert("RGBA" if "transparency" in image.info else "RGB")
    if image.mode in {"1", "L", "LA", "RGB", "RGBA", "I", "I;16"}:
        return image.copy()
    return image.convert("RGB")


def preprocess_images(
    image_paths: Iterable[str | Path],
    group_id: str | None = None,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """Validate and normalize a batch of JPG/JPEG/PNG images.

    The original public call ``preprocess_images(image_paths)`` remains valid.
    ``group_id`` and ``output_dir`` are optional extensions used by the pipeline
    and tests. Successful images are saved as lossless PNG files.
    """
    paths = [Path(value) for value in image_paths]
    resolved_group_id = _safe_id(group_id, "group") if group_id else _derive_group_id(paths)
    processed_root = Path(output_dir) if output_dir is not None else PROCESSED_DATA_DIR
    group_output_dir = processed_root / resolved_group_id

    results: list[dict] = []
    for path in paths:
        started = perf_counter()
        source_id = _safe_id(path.stem, "image")
        item = {
            "image_id": None,
            "source_id": source_id,
            "group_id": resolved_group_id,
            "image_path": str(path),
            "original_path": str(path),
            "processed_path": None,
            "width": None,
            "height": None,
            "original_width": None,
            "original_height": None,
            "original_format": None,
            "original_mode": None,
            "processed_format": None,
            "processed_mode": None,
            "file_size_bytes": None,
            "sha256": None,
            "exif_orientation": None,
            "orientation_corrected": False,
            "datetime_original": None,
            "camera_make": None,
            "camera_model": None,
            "status": "error",
            "error": None,
            "processing_time_ms": None,
        }

        try:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError(f"不支持的图片格式：{path.suffix or '[无扩展名]'}")
            if not path.is_file():
                raise FileNotFoundError(f"图片不存在：{path}")

            item["file_size_bytes"] = path.stat().st_size
            _decode_with_opencv(path)
            digest = _content_digest(path)
            item["sha256"] = digest
            item["image_id"] = f"{resolved_group_id}__{source_id}__{digest[:8]}"

            try:
                with Image.open(path) as original:
                    original.load()
                    if original.format not in {"JPEG", "PNG"}:
                        raise ValueError(f"文件真实格式不受支持：{original.format}")
                    item["original_width"], item["original_height"] = original.size
                    item["original_format"] = original.format
                    item["original_mode"] = original.mode

                    exif = original.getexif()
                    orientation = exif.get(EXIF_ORIENTATION_TAG, 1)
                    item["exif_orientation"] = int(orientation) if orientation else 1
                    item["datetime_original"] = exif.get(EXIF_DATETIME_ORIGINAL_TAG)
                    item["camera_make"] = exif.get(EXIF_MAKE_TAG)
                    item["camera_model"] = exif.get(EXIF_MODEL_TAG)

                    corrected = ImageOps.exif_transpose(original)
                    normalized = _png_compatible(corrected)
                    item["orientation_corrected"] = item["exif_orientation"] not in (None, 1)
                    item["width"], item["height"] = normalized.size
                    item["processed_mode"] = normalized.mode
                    item["processed_format"] = "PNG"

                    group_output_dir.mkdir(parents=True, exist_ok=True)
                    processed_path = group_output_dir / f"{item['image_id']}.png"
                    save_kwargs = {}
                    icc_profile = original.info.get("icc_profile")
                    if icc_profile:
                        save_kwargs["icc_profile"] = icc_profile
                    normalized.save(processed_path, format="PNG", **save_kwargs)

                item["processed_path"] = str(processed_path)
                item["image_path"] = str(processed_path)
                item["status"] = "success"
            except (UnidentifiedImageError, OSError, ValueError) as exc:
                raise ValueError(f"Pillow 无法完整读取图片：{exc}") from exc
        except Exception as exc:  # one bad file must not abort the batch
            item["error"] = str(exc)
        finally:
            item["processing_time_ms"] = round((perf_counter() - started) * 1000, 3)

        results.append(item)
    return results
