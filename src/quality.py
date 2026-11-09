from pathlib import Path
import cv2


def evaluate_quality(image_path: str | Path) -> dict:
    """
    返回单张图片的画质指标。
    TODO(B): 实现清晰度、曝光、对比度指标及归一化综合分。
    quality_score 范围统一为 0-10。
    """
    path = Path(image_path)
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"无法读取图片：{path}")
    raise NotImplementedError("成员B：待实现画质评价算法")
