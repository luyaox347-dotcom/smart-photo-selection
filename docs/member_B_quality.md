# 成员 B 传统机器视觉与画质评价

## 算法与默认配置

Pillow 读取 JPEG、PNG。RGB 经 OpenCV 转为 8 位灰度，近似 `Y = 0.299R + 0.587G + 0.114B`，结果取整。灰度图直接使用灰度，16 位灰度按 0–65535 映射至 0–255。透明图先按 alpha 合成到灰度 127 的中性底色，全透明 RGB 内容因此不会影响评分。指标在解码后的像素上计算，采用全局亮度和边缘统计，未做 ICC 色彩空间变换。

| 原始指标 | 公式和单位 | 分数方向及默认参数 |
| --- | --- | --- |
| `sharpness_raw` | 评估图上 `Var(Laplacian(Y))`，总体方差。默认 `ksize=1` 使用四邻域离散拉普拉斯，OpenCV 输出 `CV_64F`，默认反射边界。 | 越大分越高。最长边上限 512 像素，保持比例、面积插值缩小，短边至少 1 像素。默认使用对数映射，参考值 1000。 |
| `exposure_raw` | 原尺寸 256 桶亮度直方图中 `Y ≤ 12` 与 `Y ≥ 243` 的像素比例之和，范围 0–1。 | 越小分越高，分数为 `10 × (1 − exposure_raw)`。两端各约 5% 的码值范围用于检测接近剪切；同时输出两端各自比例和平均亮度。 |
| `contrast_raw` | 原尺寸亮度总体标准差 `sqrt(Σ p(y) × (y − μ)²)`，其中 `μ = Σ y × p(y)`。 | 越大分越高，使用固定线性映射，参考值 64，约为 8 位码值范围的四分之一。 |

设 `x = clip(raw, 0, ref)`。线性映射为 `10 × x / ref`，清晰度默认用 `10 × log1p(x) / log1p(ref)`，给低段拉普拉斯能量更多分辨空间。三项分数分别记为 `sharpness_score`、`exposure_score`、`contrast_score`，均在 0–10。B 内部画质分为 `0.45 × 清晰度分 + 0.35 × 曝光分 + 0.20 × 对比度分`。将细节损失和亮暗信息损失置于全局对比度之前是初始工程判断。默认阈值、参考值和权重均为固定设定，尚未用真实标注优化，也无数据拟合参数。

配置集中在 `config/quality.py` 的 `QualityConfig`，可用 `dataclasses.replace` 生成替代配置。清晰度的可选核为 1 或 3，变更核或评估尺寸时应一并验证清晰度参考值。权重按清晰度、曝光、对比度排列，必须非负且总和在绝对误差 `1e-9` 内等于 1。所有映射依赖固定参数，同一张图的分数与批次组成无关。

常量图可正常评分，拉普拉斯方差和亮度标准差均为 0。极小图按实际尺寸评价，通常缺少足够细节。非有限指标导致该图片评分失败；显式调用 `score_quality_metrics` 传入 NaN 或 Inf 时会抛出 `ValueError`。纹理、噪声和过度锐化都可能抬高清晰度分；512 像素尺度可能掩盖细小模糊，小图保留原尺寸后仍可能与大图存在尺度偏差。夜景、低调、高调、纯色或透明背景图可能被误判；亮度直方图可能漏掉单色通道剪切。全局标准差可能被背景、强反差和过度处理抬高，也无法指出主体局部的反差。画质分仅衡量定义中的技术指标。

## A 接入与 D 调用

```python
from pathlib import Path

from src.quality import evaluate_crop_quality, evaluate_quality, evaluate_quality_batch, export_quality_csv

standalone = evaluate_quality(Path("data/raw/example/照片 01.jpg"))
quality_rows = evaluate_quality_batch(preprocessing_records)
export_quality_csv(quality_rows, Path("outputs/scores/quality.csv"))

# preprocessing_records 来自 A 的 preprocess_images。
# existing_crop_records 来自 A 对该条记录的 image_path 已生成的候选。
crop_rows = evaluate_crop_quality(preprocessing_records[0], existing_crop_records)
export_quality_csv(crop_rows, Path("outputs/scores/crop_quality.csv"))

for row in quality_rows:
    if row["status"] == "success":
        image_id, quality_score = row["image_id"], row["quality_score"]
        # D 在同一 image_id 上合并 C 提供的 aesthetic_score。
```

单路径入口面向原始 JPEG/PNG，读取时应用一次 EXIF 方向，按照 A 的同父目录组名、安全化原始文件名及文件 SHA-256 前八位构建 ID。A 显式指定组名、从多目录推导组名或已经生成处理副本时，用批量入口继承 A 的 ID。批量入口只按 A 的 `image_path` 读取成功记录中的标准化副本，保留 `original_path`、`processed_path` 和失败记录的原始原因。输出顺序与输入一致，重复 ID 的行全部保留。

裁剪入口接受一条 A 预处理记录及其候选列表，检查父 `image_id` 和 `source_image_path`，继承父图的 `group_id`、`source_id`、`original_path`、`processed_path`。候选 `image_path` 为实际打分文件，`crop_id` 为其标识，`source_image_path` 指向标准化父图。整图和裁剪 CSV 按 `record_kind` 分开，A 的原图候选若在裁剪列表内，仍作为裁剪结果记录。

CSV 使用 UTF-8 BOM。结果还包含原始指标、各子分、总分、亮度与暗亮比例、原尺寸和清晰度评估尺寸、分段耗时、`status`、`error`。失败时 `status="error"`，指标在 Python 中为 `None`，在 CSV 中为空白。成功的 0 分保留数值。D 只取整图成功记录并按 `image_id` 关联，负责处理失败或重复行。D 最初的综合公式 `0.4 × quality_score + 0.6 × aesthetic_score` 使用另一层权重。

可直接将一组原始路径交给 A 和 B 串联，也可传入 A 字典列表的 JSON。相对路径以命令当前目录解析。`--crop-records` 的 JSON 外层为数组，每个元素是同位置父记录的 A 裁剪字典数组。无候选的父图使用 `[]`。

```powershell
python scripts/score_quality.py "data/raw/example/照片 01.jpg" "data/raw/example/照片 02.jpg" --group-id example --output outputs/scores/quality.csv
python scripts/score_quality.py --preprocessing-records preprocessing.json --crop-records crops.json --output outputs/scores/quality.csv --crop-output outputs/scores/crop_quality.csv
```

## 复杂度与实验复现

令 `E` 为编码文件字节数，`N = W × H` 为解码像素数，`M = W′ × H′` 为清晰度评估像素数，默认 `M ≤ 512²`。在常规 JPEG/PNG 解码模型下，读图、解码、可能的方向校正总计 `O(E + N)` 时间；单路径调用还需 `O(E)` 时间计算文件摘要，并在内存保留编码字节。灰度和透明度处理、直方图扫描各为 `O(N)`。面积缩小和固定核拉普拉斯共 `O(N + M)` 时间，256 桶统计和三项合成相对于图像尺寸为常数。计算阶段主要空间为 `O(N + M)`，另有 256 桶直方图；单路径的编码缓冲使整体峰值上界为 `O(E + N + M)`。批量按图顺序读取并只保留结果行。这里列出的设置是传统算法配置，无可训练模型参数。

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_quality.py tests/test_preprocessing.py tests/test_cropping.py -q
python scripts/run_quality_experiment.py --real-dir data/sample/real_cases --output-dir outputs/experiments/quality --warmup 2 --repeats 6
python scripts/compare_quality_annotations.py outputs/experiments/quality/real_quality.csv data/annotations/human_selection_template.csv --output outputs/experiments/quality/human_comparison.json
```

计时使用 `perf_counter`。读取阶段包括文件读取和解码到内存，原始路径入口还计入方向校正及摘要。计算阶段包括灰度处理、缩放、指标和合成分。受控性能实验使用 A 的 PNG 处理副本，单线程 OpenCV，顺序重复读同一批，包含系统文件缓存影响。预处理、生成裁剪、写 CSV 和绘图均在测量范围之外。

## 人工选片对照

输入为整图评分 CSV，以及按 A 的 `group_id,evaluator_id,selected_image_id,is_tie,tied_image_ids,reason` 填写的真实标注 CSV。选择使用完整 `image_id`，并列由分号分隔；比较脚本要求每个 `group_id + evaluator_id` 唯一。每组至少有两张不同且评分成功的照片，人工选择的照片必须均有成功分数。完全相同的重复评分归为同一张，冲突分数报错。B 将距最高分不超过 `1e-9` 的图片都记录为并列候选，用候选集合与当次人工选择是否相交作为一致判定。对多评价员分别计数，同时报告所有有效评价的平均与各组平均值的平均。

明细保留预测 ID、人工 ID 及对应分数、人工理由和是否一致，可用来核对高画质未被选中的构图、表情、内容偏好等因素。当前模板只有表头，脚本记录 0 条标注和 0 个参与组，一致率缺失。真实分歧案例待获得同场景人工标注后分析。A 的公开样本集合涵盖多种场景，本次只用于接口和指标补充验证。若后续用真实标注拟合阈值或权重，应把校准组与正式测试组隔离，并保存校准范围和最终固定配置。
