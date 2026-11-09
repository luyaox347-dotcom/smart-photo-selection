from pathlib import Path


def generate_crops(image_path: str | Path, max_crops: int = 7) -> list[dict]:
    """
    生成候选裁剪区域。
    TODO(A): 实现原图、中心裁剪及常用比例裁剪，并保存裁剪图。
    box 顺序固定为 [x1, y1, x2, y2]，坐标为原图像素。
    """
    raise NotImplementedError("成员A：待实现候选裁剪区域生成")
