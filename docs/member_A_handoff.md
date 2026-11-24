# 成员 A 交付说明

交付日期：2026-11-16

## 一、交付范围

成员 A 已完成以下六项任务：

1. 批量读取 JPEG/PNG，处理 EXIF 方向并提取原始与处理后元信息；
2. 保留原始文件，生成无损 PNG 标准化副本；
3. 为每张正常图片生成最多 7 个原图、人脸、中心比例及显著性候选；
4. 测试横图、竖图、超长图、EXIF 图片、损坏图片和不支持格式；
5. 制定数据目录、`group_id`、`source_id`、`image_id`、`crop_id`、评价者编号及标注规则；
6. 输出预处理成功率、候选有效率、候选数量和平均耗时等实验数据。

## 二、组员集成时需要的核心文件

| 文件 | 用途 |
|---|---|
| `src/preprocessing.py` | 批量预处理、EXIF 校正、元数据提取、ID 生成 |
| `src/cropping.py` | YuNet 人脸检测、中心/显著性裁剪、去重、最多 7 个候选 |
| `config/settings.py` | 数据路径、支持格式、候选上限等公共配置 |
| `models/face/face_detection_yunet_2023mar.onnx` | 当前人脸主检测模型 |
| `models/face/lbpcascade_frontalface_opencv.xml` | YuNet 无法加载时的兼容后备 |
| `requirements.txt` | Python 依赖 |
| `docs/data_spec.md` | 文件夹、ID、评价者和标注规则 |
| `docs/methods_and_parameters.md` | 六项任务的方法、模型、参数和指标公式 |

## 三、接口

### 1. 预处理

```python
from src.preprocessing import preprocess_images

items = preprocess_images(
    image_paths,
    group_id="G20261116_001",
    output_dir="data/processed",
)
```

每个结果包含 `group_id`、`source_id`、`image_id`、原始与处理后路径、宽高、格式、模式、SHA-256、EXIF、状态、错误和耗时。组员后续模块只处理 `status == "success"` 的项目，并优先读取 `image_path` 指向的方向校正副本。

### 2. 候选裁剪

```python
from src.cropping import generate_crops

candidates = generate_crops(
    item["image_path"],
    max_crops=7,
    output_dir="outputs/crops",
)
```

每个候选包含 `crop_id`、`image_id`、候选路径、原图路径、`box`、比例、来源、原因、宽高、生成耗时和统计信息。`box` 格式是 `[left, top, right, bottom]`，右、下边界不包含在裁剪内。

## 四、模块间约定

- 系统内部合并结果使用完整 `image_id`，不要只用文件名。
- 老师要求回映原始测试图片时使用 `source_id`。
- `crop_id` 只标识裁剪候选，不能替代最终原图选择 ID。
- 人脸池只表示真人脸；狗、猫、建筑和静物主要由显著性候选覆盖。
- YuNet 正常运行但检测为 0 时不会启用 Haar/LBP；只有模型或接口无法加载时才降级。
- 原图永远不覆盖，后续模块不得把结果保存回 `original_path`。

## 五、验证方式

运行成员 A 自动化测试：

```powershell
python -m pytest tests/test_preprocessing.py tests/test_cropping.py -q
```

当前结果：`15 passed`。

复现真实样本实验：

```powershell
python scripts/run_a_experiment.py data/sample/real_cases `
  --processed-dir tmp/member_a_check/processed `
  --crop-dir tmp/member_a_check/crops `
  --output-dir outputs/experiments/real_cases
```

完整实验过程见 `outputs/experiments/real_cases/README.md`。CSV/JSON 保存最终 YuNet 实验数据，报告同时保留 Haar/LBP 基线及前后对比。

## 六、交付包目录

```text
member_A_delivery_2026-11-16/
├── README.md
├── requirements.txt
├── src/
├── config/
├── models/face/
├── docs/
├── data/annotations/
├── data/sample/real_cases/
├── tests/
├── scripts/
└── outputs/experiments/real_cases/
```

其中真实样本仅用于复现实验，不属于系统运行时必需文件。集成到小组主项目时，至少合并第二节列出的核心文件。
