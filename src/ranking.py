def calculate_ranking(
    quality_results: list[dict],
    aesthetics_results: list[dict],
    quality_weight: float = 0.4,
    aesthetic_weight: float = 0.6,
) -> list[dict]:
    """按 image_id 合并评分并排序；两个分数均为 0-10。"""
    if not 0 <= quality_weight <= 1 or not 0 <= aesthetic_weight <= 1:
        raise ValueError("权重必须在0到1之间")
    if abs(quality_weight + aesthetic_weight - 1.0) > 1e-8:
        raise ValueError("quality_weight 与 aesthetic_weight 之和必须为1")

    quality_by_id = {x["image_id"]: x for x in quality_results}
    aesthetic_by_id = {x["image_id"]: x for x in aesthetics_results}
    common_ids = set(quality_by_id) & set(aesthetic_by_id)

    ranked = []
    for image_id in common_ids:
        q = float(quality_by_id[image_id]["quality_score"])
        a = float(aesthetic_by_id[image_id]["aesthetic_score"])
        if not (0 <= q <= 10 and 0 <= a <= 10):
            raise ValueError(f"{image_id} 的评分必须在0到10之间")
        ranked.append({
            "image_id": image_id,
            "quality_score": q,
            "aesthetic_score": a,
            "final_score": round(quality_weight * q + aesthetic_weight * a, 4),
        })

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked
