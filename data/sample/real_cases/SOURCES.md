# 真实图片测试样本来源

获取日期：2026-11-16。

## scikit-image 0.26.0 官方发行包

以下图片取自 PyPI 发布的 `scikit-image 0.26.0` wheel 中的 `skimage/data`。项目官方文档将这些文件作为通用计算机视觉测试图片，并在对应数据函数中记录来源与许可。

- `01_landscape_rocket.jpg`：SpaceX DSCOVR 发射照片，公共领域。
- `02_portrait_astronaut.png`：由 `astronaut.png` 中央裁剪得到的竖图；原图为 NASA 宇航员 Eileen Collins，公共领域。
- `03_ultrawide_hubble.jpg`：由 `hubble_deep_field.jpg` 中央裁剪得到的 5:1 超宽图；NASA 图片，公共领域。
- `04_ultratall_rocket.jpg`：由 `rocket.jpg` 中央裁剪得到的超长竖图；公共领域。
- `05_face_astronaut.png`：NASA 宇航员照片，公共领域。
- `06_animal_cat.png`：Chelsea 猫照片，摄影者 Stefan van der Walt，CC0。
- `07_still_life_coffee.png`：咖啡杯照片，摄影者 Rachel Michetti，CC0。
- `08_exif_orientation_6.jpg`：由公共领域 `rocket.jpg` 旋转并写入 EXIF Orientation=6 得到，用于方向校正测试。
- `09_corrupt_truncated.jpg`：由公共领域 `rocket.jpg` 截断得到，用于损坏文件测试。
- `10_unsupported_rocket.bmp`：由公共领域 `rocket.jpg` 转换为 BMP，用于不支持格式测试。
- `11_grayscale_camera.png`：灰度摄影样本，摄影者 Lav Varshney，CC0。

官方数据文档：https://scikit-image.org/docs/stable/api/skimage.data.html

PyPI 发行页：https://pypi.org/project/scikit-image/0.26.0/

## Wikimedia Commons 原始文件

- `04_tall_eiffel.jpg`：`Eiffel Tower High Res.jpg`，作者 Andyxox，公共领域。https://commons.wikimedia.org/wiki/File:Eiffel_Tower_High_Res.jpg
- `07_dog_cc0.jpg`：`Dog (41625601132).jpg`，作者 Jusotil_1943，CC0。https://commons.wikimedia.org/wiki/File:Dog_(41625601132).jpg

这些文件仅用于课程项目的算法测试与结果展示。派生图片的名称明确标注了测试用途；原始来源和许可保留在本文件中。

## 人脸检测模型

主模型 `models/face/face_detection_yunet_2023mar.onnx` 来自 OpenCV Zoo 的 YuNet，获取日期为 2026-11-16，模型地址、SHA-256 和许可证见 `models/face/README.md`。

`models/face/lbpcascade_frontalface_opencv.xml` 取自同一 scikit-image 发行包，原始文件来自 OpenCV。Haar/LBP 级联用于第一轮基线实验；最终代码仅在 YuNet 模型或 `FaceDetectorYN` 接口无法加载时将其作为兼容后备。
