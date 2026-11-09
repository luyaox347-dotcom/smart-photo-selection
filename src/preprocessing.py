from pathlib import Path
from PIL import Image, ImageOps
from typing import Iterable


def preprocess_images(image_paths: Iterable[str | Path]) -> list[dict]:
    """读取图片并返回统一元数据；不覆盖原图。"""
    results = []
    for path_value in image_paths:
        path = Path(path_value)
        item = {
            "image_id": path.stem,
            "image_path": str(path),
            "width": None,
            "height": None,
            "status": "error",
            "error": None,
        }
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                item["width"], item["height"] = image.size
                item["status"] = "success"
        except Exception as exc:
            item["error"] = str(exc)
        results.append(item)
    return results
