"""Generate diverse, bounded crop candidates for one image."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PIL import Image, ImageOps

from config.settings import CROP_OUTPUT_DIR, MAX_CROPS


MIN_CROP_SIZE = 64
DUPLICATE_IOU_THRESHOLD = 0.98
FACE_EXPANSION = 2.0
FACE_DETECTION_MAX_DIMENSION = 1600
YUNET_SCORE_THRESHOLD = 0.90
YUNET_NMS_THRESHOLD = 0.30
YUNET_TOP_K = 5000
CASCADE_MIN_CONFIDENCE = 3.0
SALIENCY_MAX_DIMENSION = 1200
YUNET_MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "face"
    / "face_detection_yunet_2023mar.onnx"
)


@dataclass(frozen=True)
class _Candidate:
    box: tuple[int, int, int, int]
    ratio: str
    source: str
    reason: str
    priority: int


def _target_ratios(width: int, height: int) -> list[tuple[str, float]]:
    if width >= height:
        return [("1:1", 1.0), ("4:3", 4 / 3), ("16:9", 16 / 9)]
    return [("1:1", 1.0), ("3:4", 3 / 4), ("9:16", 9 / 16)]


def _max_crop_size(width: int, height: int, ratio: float) -> tuple[int, int]:
    if width / height > ratio:
        crop_height = height
        crop_width = int(round(height * ratio))
    else:
        crop_width = width
        crop_height = int(round(width / ratio))
    return max(1, min(width, crop_width)), max(1, min(height, crop_height))


def _box_around(
    center_x: float,
    center_y: float,
    crop_width: int,
    crop_height: int,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    x1 = int(round(center_x - crop_width / 2))
    y1 = int(round(center_y - crop_height / 2))
    x1 = min(max(0, x1), image_width - crop_width)
    y1 = min(max(0, y1), image_height - crop_height)
    return x1, y1, x1 + crop_width, y1 + crop_height


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if intersection == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / float(area_a + area_b - intersection)


def _cv_image(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片：{path}")
    return image


def _saliency_center(image_bgr: np.ndarray) -> tuple[float, float, str]:
    """Return a subject center; edge energy is a portable fallback."""
    height, width = image_bgr.shape[:2]
    scale = min(1.0, SALIENCY_MAX_DIMENSION / max(width, height))
    working_image = image_bgr
    if scale < 1.0:
        working_image = cv2.resize(
            image_bgr,
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    saliency_map = None
    method = "edge_energy"
    saliency_namespace = getattr(cv2, "saliency", None)
    if saliency_namespace is not None:
        try:
            detector = saliency_namespace.StaticSaliencySpectralResidual_create()
            ok, saliency_map = detector.computeSaliency(working_image)
            if not ok:
                saliency_map = None
            else:
                method = "spectral_residual"
        except cv2.error:
            saliency_map = None

    if saliency_map is None:
        gray = cv2.cvtColor(working_image, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        saliency_map = cv2.magnitude(gx, gy)

    weights = np.asarray(saliency_map, dtype=np.float64)
    weights[~np.isfinite(weights)] = 0
    total = float(weights.sum())
    if total <= 1e-12:
        return width / 2, height / 2, "center_fallback"
    ys, xs = np.indices(weights.shape)
    center_x = float((xs * weights).sum() / total)
    center_y = float((ys * weights).sum() / total)
    return center_x / scale, center_y / scale, method


def _detect_faces_yunet(image_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detect human faces with the bundled OpenCV Zoo YuNet model."""
    if not YUNET_MODEL_PATH.is_file() or not hasattr(cv2, "FaceDetectorYN"):
        raise RuntimeError("YuNet model or OpenCV FaceDetectorYN is unavailable")
    height, width = image_bgr.shape[:2]
    detector = cv2.FaceDetectorYN.create(
        str(YUNET_MODEL_PATH),
        "",
        (width, height),
        YUNET_SCORE_THRESHOLD,
        YUNET_NMS_THRESHOLD,
        YUNET_TOP_K,
    )
    _, detected = detector.detect(image_bgr)
    if detected is None:
        return []
    return [tuple(int(round(value)) for value in face[:4]) for face in detected]


def _detect_faces_cascade(image_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Compatibility fallback used only when YuNet cannot be loaded."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    cascade_paths = [
        Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml",
        Path(__file__).resolve().parents[1]
        / "models"
        / "face"
        / "lbpcascade_frontalface_opencv.xml",
    ]
    detector = None
    for cascade_path in cascade_paths:
        if not cascade_path.is_file():
            continue
        candidate_detector = cv2.CascadeClassifier(str(cascade_path))
        if not candidate_detector.empty():
            detector = candidate_detector
            break
    if detector is None:
        return []
    try:
        detected, _, confidence = detector.detectMultiScale3(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(32, 32),
            outputRejectLevels=True,
        )
        return [
            tuple(int(value) for value in face)
            for face, weight in zip(detected, confidence)
            if float(weight) >= CASCADE_MIN_CONFIDENCE
        ]
    except (AttributeError, cv2.error):
        detected = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(32, 32),
        )
        return [tuple(int(value) for value in face) for face in detected]


def _face_candidates(
    image_bgr: np.ndarray,
    ratios: list[tuple[str, float]],
) -> tuple[list[_Candidate], dict]:
    image_height, image_width = image_bgr.shape[:2]
    detection_scale = min(1.0, FACE_DETECTION_MAX_DIMENSION / max(image_width, image_height))
    detection_image = image_bgr
    if detection_scale < 1.0:
        detection_image = cv2.resize(
            image_bgr,
            (
                max(1, int(round(image_width * detection_scale))),
                max(1, int(round(image_height * detection_scale))),
            ),
            interpolation=cv2.INTER_AREA,
        )
    detector_name = "yunet_2023mar"
    try:
        faces = _detect_faces_yunet(detection_image)
    except (RuntimeError, cv2.error):
        detector_name = "haar_or_lbp_fallback"
        faces = _detect_faces_cascade(detection_image)
    diagnostics = {
        "face_detector": detector_name,
        "face_detection_count": len(faces),
        "face_detection_scale": round(detection_scale, 6),
        "face_score_threshold": (
            YUNET_SCORE_THRESHOLD if detector_name == "yunet_2023mar" else CASCADE_MIN_CONFIDENCE
        ),
        "face_nms_threshold": (
            YUNET_NMS_THRESHOLD if detector_name == "yunet_2023mar" else None
        ),
    }
    if len(faces) == 0:
        return [], diagnostics

    scaled_faces = [
        tuple(int(round(value / detection_scale)) for value in face) for face in faces
    ]
    x1 = min(x for x, _, _, _ in scaled_faces)
    y1 = min(y for _, y, _, _ in scaled_faces)
    x2 = max(x + w for x, _, w, _ in scaled_faces)
    y2 = max(y + h for _, y, _, h in scaled_faces)
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    subject_width, subject_height = x2 - x1, y2 - y1

    candidates: list[_Candidate] = []
    for ratio_name, ratio in ratios[:2]:
        crop_width = max(subject_width * FACE_EXPANSION, subject_height * FACE_EXPANSION * ratio)
        crop_height = crop_width / ratio
        if crop_height < subject_height * FACE_EXPANSION:
            crop_height = subject_height * FACE_EXPANSION
            crop_width = crop_height * ratio
        scale = min(1.0, image_width / crop_width, image_height / crop_height)
        crop_width = max(MIN_CROP_SIZE, int(round(crop_width * scale)))
        crop_height = max(MIN_CROP_SIZE, int(round(crop_height * scale)))
        crop_width = min(image_width, crop_width)
        crop_height = min(image_height, crop_height)
        box = _box_around(center_x, center_y, crop_width, crop_height, image_width, image_height)
        candidates.append(
            _Candidate(
                box,
                ratio_name,
                "face",
                f"{detector_name}_"
                + ("multi_face_union" if len(scaled_faces) > 1 else "single_face_expanded"),
                1,
            )
        )
    return candidates, diagnostics


def _valid(candidate: _Candidate, width: int, height: int) -> bool:
    x1, y1, x2, y2 = candidate.box
    return (
        0 <= x1 < x2 <= width
        and 0 <= y1 < y2 <= height
        and x2 - x1 >= min(MIN_CROP_SIZE, width)
        and y2 - y1 >= min(MIN_CROP_SIZE, height)
    )


def _select_diverse(candidates: list[_Candidate], limit: int) -> list[_Candidate]:
    selected: list[_Candidate] = []
    for candidate in sorted(candidates, key=lambda item: item.priority):
        if any(
            candidate.box == old.box
            or _iou(candidate.box, old.box) >= DUPLICATE_IOU_THRESHOLD
            for old in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def generate_crops(
    image_path: str | Path,
    max_crops: int = MAX_CROPS,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """Generate and save at most ``max_crops`` valid crop candidates.

    Coordinates use Pillow's left/top-inclusive, right/bottom-exclusive
    convention and always refer to the EXIF-corrected image.
    """
    if not 1 <= max_crops <= MAX_CROPS:
        raise ValueError(f"max_crops 必须在 1 到 {MAX_CROPS} 之间")

    started = perf_counter()
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"图片不存在：{path}")

    with Image.open(path) as opened:
        opened.load()
        corrected = ImageOps.exif_transpose(opened)
        image = corrected.copy()
    width, height = image.size
    if width < 2 or height < 2:
        raise ValueError("图片尺寸过小，无法生成裁剪候选")

    image_bgr = _cv_image(path)
    if (image_bgr.shape[1], image_bgr.shape[0]) != (width, height):
        rgb = np.asarray(image.convert("RGB"))
        image_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    ratios = _target_ratios(width, height)
    candidates = [
        _Candidate((0, 0, width, height), "original", "original", "uncropped_original", 0)
    ]
    face_candidates, face_diagnostics = _face_candidates(image_bgr, ratios)
    candidates.extend(face_candidates)

    for ratio_index, (ratio_name, ratio) in enumerate(ratios):
        crop_width, crop_height = _max_crop_size(width, height, ratio)
        candidates.append(
            _Candidate(
                _box_around(width / 2, height / 2, crop_width, crop_height, width, height),
                ratio_name,
                "center",
                "center_common_ratio",
                2 if ratio_index < 2 else 4,
            )
        )

    salient_x, salient_y, saliency_method = _saliency_center(image_bgr)
    for ratio_name, ratio in ratios:
        crop_width, crop_height = _max_crop_size(width, height, ratio)
        candidates.append(
            _Candidate(
                _box_around(salient_x, salient_y, crop_width, crop_height, width, height),
                ratio_name,
                "saliency",
                f"{saliency_method}_weighted_center",
                3,
            )
        )

    raw_candidate_count = len(candidates)
    valid_candidates = [candidate for candidate in candidates if _valid(candidate, width, height)]
    unique_candidates = _select_diverse(valid_candidates, len(valid_candidates))
    selected = unique_candidates[:max_crops]

    image_id = path.stem
    crop_root = Path(output_dir) if output_dir is not None else CROP_OUTPUT_DIR
    image_crop_dir = crop_root / image_id
    image_crop_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for index, candidate in enumerate(selected, 1):
        crop_id = f"{image_id}__{candidate.source}_{index:02d}"
        if candidate.source == "original":
            candidate_path = path
        else:
            candidate_path = image_crop_dir / f"{crop_id}.png"
            image.crop(candidate.box).save(candidate_path, format="PNG")
        x1, y1, x2, y2 = candidate.box
        results.append(
            {
                "crop_id": crop_id,
                "image_id": image_id,
                "image_path": str(candidate_path),
                "source_image_path": str(path),
                "box": [x1, y1, x2, y2],
                "ratio": candidate.ratio,
                "source": candidate.source,
                "reason": candidate.reason,
                "width": x2 - x1,
                "height": y2 - y1,
            }
        )

    elapsed_ms = round((perf_counter() - started) * 1000, 3)
    statistics = {
        "raw_candidate_count": raw_candidate_count,
        "valid_candidate_count": len(valid_candidates),
        "unique_candidate_count": len(unique_candidates),
        "returned_candidate_count": len(selected),
        "invalid_candidate_count": raw_candidate_count - len(valid_candidates),
        "duplicate_candidate_count": len(valid_candidates) - len(unique_candidates),
        "limited_candidate_count": max(0, len(unique_candidates) - len(selected)),
        "candidate_validity_rate": round(
            len(unique_candidates) / raw_candidate_count * 100, 3
        ),
        **face_diagnostics,
    }
    for result in results:
        result["generation_time_ms"] = elapsed_ms
        result["generation_stats"] = statistics.copy()
    return results
