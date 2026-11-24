from pathlib import Path

from src.preprocessing import preprocess_images
from src.quality import evaluate_quality_batch
from src.ranking import calculate_ranking


def run_selection(
    image_paths: list[str | Path], *, output_dir: str | Path | None = None
) -> dict:
    """使用真实画质分和模拟美学分生成推荐。"""
    images = preprocess_images(image_paths, output_dir=output_dir)
    quality_results = []
    aesthetics_results = []
    errors = []

    for index, item in enumerate(evaluate_quality_batch(images)):
        image_id = item["image_id"]
        if item["status"] != "success":
            errors.append({
                "image_id": image_id,
                "original_path": item["original_path"],
                "message": item["error"],
            })
            continue

        quality_results.append(item)
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
