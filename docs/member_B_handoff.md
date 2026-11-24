# 成员 B 交接总结

B 已完成传统画质评价、批量评分、A 数据对接及实验交付。在 Python 3.10.11 下，A 回归 15 项和 B 测试 18 项通过，全量共 33 项通过。**下一棒建议交给成员 C**，先完成美学评分，再把 A、B、C 的结果交给成员 D 联调。真实人工选片对照需要补充同场景标注。

## 本次完成的工作


| 文件                                                                                | 内容                                                                            |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| [src/quality.py](../src/quality.py)                                                 | 单图、批量整图、已有裁剪候选的评分，固定归一化、可解释指标、失败状态及 CSV 导出 |
| [config/quality.py](../config/quality.py)                                           | 尺度、核、曝光阈值、透明底色、归一化和内部权重                                  |
| [tests/test_quality.py](../tests/test_quality.py)                                   | 合成退化、边界输入、异常、批次独立性、A 的 EXIF 和裁剪记录、人工对照            |
| [scripts/score_quality.py](../scripts/score_quality.py)                             | 从原图路径或 A 的 JSON 记录执行批量评分，整图和裁剪分开输出                     |
| [scripts/run_quality_experiment.py](../scripts/run_quality_experiment.py)           | 固定种子生成样例，比较归一化和权重，分段计时，另跑公开样本                      |
| [scripts/compare_quality_annotations.py](../scripts/compare_quality_annotations.py) | 按 A 的标注格式对比 B 的组内最高分与人工选择，支持多评价员和并列                |
| [member_B_quality.md](member_B_quality.md)                                          | 指标公式、配置依据、输入输出、复杂度与接入示例                                  |
| [实验报告与运行记录](../outputs/experiments/quality/README.md)                      | 本次实测数值、环境、局限和全部交付数据的索引                                    |

清晰度使用灰度图的拉普拉斯方差，默认最长边最多 512 像素，保持比例缩小，小图保留原尺寸。曝光使用原尺寸亮度直方图中 `Y ≤ 12` 和 `Y ≥ 243` 的像素比例之和，原始值越大表示接近剪切的像素越多。对比度使用原尺寸亮度总体标准差。三项子分统一为 0–10、越高越好，默认权重是 **清晰度 0.45、曝光 0.35、对比度 0.20**。清晰度默认用固定对数映射，参考值 1000，对比度用固定线性映射，参考值 64。默认值来自工程设定，尚无真实标注校准依据。指标对纹理、噪声、夜景、高低调和局部主体反差有局限。

## 验证结果与复现

- **环境与测试**　项目内的 Python 3.10.11 独立虚拟环境按 `requirements.txt` 安装，`pip check` 通过。A 15 项、B 18 项、全量 33 项通过，无失败或跳过。首次 pytest 遇到 Windows 临时目录权限错误，通过获准的项目内临时目录完成复跑。原图路径和 A JSON 两个 CLI 入口均通过冒烟验证，覆盖中文空格路径、失败空分数和裁剪 ID。
- **合成样例**　15 张、3 个场景、12 对未退化和退化对比。固定对数和线性两种映射下，三组完整权重都取得 12 胜，无法用这批样例选出最优权重。默认权重下，两种映射对模糊的平均分差分别为 2.920 和 0.857；曝光单项为 6 胜、6 平。 [逐张结果](../outputs/experiments/quality/synthetic_quality.csv) · [配置汇总](../outputs/experiments/quality/configuration_summary.csv)
- **分段耗时**　15 张标准化 PNG 预热两批、重复六批，共 90 次测量。Intel Core i7-14650HX、Windows、OpenCV 单线程条件下，3840 × 2160 样例的平均读图与解码时间是 13.773 ms，平均计算时间是 23.094 ms。结果包含暖缓存影响。 [实验摘要](../outputs/experiments/quality/summary.json) · [逐次计时](../outputs/experiments/quality/timing_samples.csv) · [分数图](../outputs/experiments/quality/synthetic_scores.png)
- **公开样本**　B 对 A 的 13 条样本重新评分，11 张整图和 73 个裁剪候选评分成功，损坏 JPEG 与不支持的 BMP 保留 A 的错误。实验生成的 PNG 副本与裁剪文件由脚本临时创建，CSV 中相应路径用于追溯，可通过实验命令重新生成。 [整图结果](../outputs/experiments/quality/real_quality.csv) · [裁剪结果](../outputs/experiments/quality/real_crop_quality.csv)
- **真实人工对照**　标注模板只有表头，实际运行参与组和有效评价均为 0，一致率为空。取得同场景标注后，以完整 `image_id` 对应整图分数，按 `group_id + evaluator_id` 记录选择与理由，再分析构图、表情、内容偏好等可能的分歧因素。正式测试 A/B 的人工答案用于独立评估；如需调参，应另用校准组。 [人工对照记录](../outputs/experiments/quality/human_comparison.json)

在项目根目录用 Python 3.10 虚拟环境运行。Windows 默认临时目录若不可访问，可用 `--basetemp` 指向项目内专用的测试临时目录。

```powershell
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
python scripts/score_quality.py --help
python scripts/run_quality_experiment.py --real-dir data/sample/real_cases --output-dir outputs/experiments/quality --warmup 2 --repeats 6
python scripts/compare_quality_annotations.py outputs/experiments/quality/real_quality.csv data/annotations/human_selection_template.csv --output outputs/experiments/quality/human_comparison.json
```

给 C 和 D 的对齐事项

**成员 C 先交付美学评分。** 保留 `evaluate_aesthetics(image_path)`，输出 `image_id`、`aesthetic_score`、`model`、`status`，建议补充与 A、B 一致的 `error` 字段。给 D 的批量结果应沿用 A 的 ID。先用 A 成功记录和固定模型跑通整图美学分，再接候选多模态复核。D 可同步接入 B，等 C 确认评分字段与尺度后联调完整排序。 [任务书](../tasks.docx)


| 要对齐的内容       | C、D 接续时采用的约定                                                                                                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 输入范围和方向     | 整图评分从 A 的同一条成功记录取`image_path`，指向已校正方向的标准化副本。C 可按模型输入规范缩放、转换色彩，先确认模型是否默认中心裁剪并记录实际策略，这会影响构图判断。B 的单路径入口用于原始图片；A 副本通过批量接口保留身份。                  |
| ID 与来源          | 模块间按完整`image_id` 关联，组内选片按 `group_id` 划分，最终映射原始文件时按任务约定使用 `source_id`。同名文件和重复行都可能出现，D 应显式确定重复处理方式并记录冲突。                                                                          |
| 分数及权重         | `quality_score` 与 `aesthetic_score` 均为有限的 0–10 分、越高越好。C 应记录模型名、版本、输入处理、原始输出到 0–10 的固定映射。D 按 `0.4 × quality_score + 0.6 × aesthetic_score` 做初始综合排序。B 内部三项权重只用于计算 `quality_score`。 |
| 状态及缺失分       | 采用成功/失败状态和可读错误信息。真实 0 分仍可排序。失败分使用`None`，CSV 留空。模型不可用、图片失败和无有效候选时，由 D 决定跳过、重试或执行明确的降级策略，并将状态传给 GUI。                                                                  |
| 整图、裁剪和复核   | 整图候选按原始照片的`image_id` 参评；裁剪候选同时携带 `crop_id` 和父 `image_id`。A 的 `source_image_path` 指向标准化父图，候选 `image_path` 指向实际评分像素。D 先完成原始整图推荐，再展示其可选裁剪；多模态复核以对应候选 ID 记录结果。         |
| 可复现性与排序稳定 | C 准备可重复运行的本地测试，记录模型权重来源与版本。D 做一组真实端到端试跑，校验乱序返回仍能正确关联 ID、同分时排序稳定、失败记录可追溯、裁剪结果归属正确。                                                                                      |

D 可直接用以下入口获得 B 结果，再与 C 的成功评分按 `image_id` 关联。

```python
from src.quality import evaluate_quality_batch

quality_rows = evaluate_quality_batch(preprocessing_records)
for row in quality_rows:
    if row["status"] == "success":
        image_id, quality_score = row["image_id"], row["quality_score"]
```

建议 D 的首个联调样例包含同组两张有效原图、一张坏图、一个 C 评分缺失的结果，以及由一张原图产生的裁剪候选。验证每张图的来源、分数、失败原因和候选归属后，再接推荐理由、GUI 与正式测试 A/B。

## Git 交付

本地交付目录无 Git 元数据，未能使用 `feature/quality`。导入组内正式仓库时，按 B 文件清单与实验产物提交。Python 虚拟环境、临时图片、模型权重、密钥和私人原图留在本地。

建议提交信息为 `feat(quality): add technical photo scoring and reproducible experiments`。
