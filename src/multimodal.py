def review_candidates(image_paths: list[str]) -> dict:
    """
    输入候选图片路径列表。
    返回 selected_image_id、reason；confidence 可为 None。
    TODO(C): 接入视觉大模型；失败时由 pipeline 回退基础排序。
    """
    raise NotImplementedError("成员C：待接入多模态视觉模型")
