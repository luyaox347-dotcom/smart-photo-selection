from pathlib import Path

from src.preprocessing import preprocess_images
from src.ranking import calculate_ranking


def run_selection(image_paths: list[str | Path]) -> dict:
    """用模拟评分验证从预处理到推荐的流程。"""
    images = preprocess_images(image_paths)
    quality_results = []
    aesthetics_results = []
    errors = []

    for index, item in enumerate(images):
        image_id = item["image_id"]
        if item["status"] != "success":
            errors.append({"image_id": image_id, "message": item["error"]})
            continue

        # 固定分数仅用于验证联调，后续由真实评分模块提供。
        quality_results.append({"image_id": image_id, "quality_score": 6 + index % 4})
        aesthetics_results.append({"image_id": image_id, "aesthetic_score": 9 - index % 4})

    ranking = calculate_ranking(quality_results, aesthetics_results)
    if not ranking:
        errors.append({"image_id": None, "message": "没有可用于排名的照片。"})
    return {
        "images": images,
        "ranking": ranking,
        "recommendation": ranking[0] if ranking else None,
        "status": "success" if ranking else "error",
        "errors": errors,
    }
