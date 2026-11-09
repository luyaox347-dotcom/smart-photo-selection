from pathlib import Path
from src.preprocessing import preprocess_images


def run_selection(image_paths: list[str | Path]) -> dict:
    """
    流程总入口。
    TODO(D): 接入 quality、aesthetics、ranking 和 multimodal。
    当前只执行预处理检查。
    """
    metadata = preprocess_images(image_paths)
    return {
        "images": metadata,
        "status": "preprocessing_only",
        "ranking": [],
        "recommendation": None,
    }
