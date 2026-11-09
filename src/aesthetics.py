from pathlib import Path


def evaluate_aesthetics(image_path: str | Path) -> dict:
    """
    返回 NIMA 美学评价结果。
    TODO(C): 加载并调用经过验证的预训练权重。
    aesthetic_score 范围统一为 0-10。
    """
    raise NotImplementedError("成员C：待接入NIMA模型")
