# SmartPhotoSelection 数据与标识规范

## 目录结构

```text
data/
├── raw/<group_id>/
├── processed/<group_id>/
├── annotations/
└── sample/
```

原始图片只读，不得覆盖。EXIF 方向校正后的标准化副本保存为无损 PNG，裁剪结果保存到 `outputs/crops/`。

## 标识规则

- `group_id`：同一实际场景或同一次连拍共享的组 ID。正式数据推荐 `G<日期8位>_<三位序号>`，例如 `G20261116_001`。优先由 pipeline 显式传入；未传入时使用共同父目录名，不同父目录的混合批次使用路径列表 SHA-256 前 10 位生成 `batch_<摘要>`。
- `source_id`：原始文件名去掉扩展名并安全化，供老师测试集结果映射。例如 `IMG 0001.jpg` 变为 `IMG_0001`。
- `image_id`：`<group_id>__<source_id>__<原文件SHA-256前8位>`，例如 `G20261116_001__IMG_0001__a1b2c3d4`，用于系统内部唯一关联。相同文件重复导入得到相同 ID；内容变化后摘要也会变化。
- `crop_id`：`<image_id>__<候选来源>_<两位序号>`，例如 `G20261116_001__IMG_0001__a1b2c3d4__face_02`。它只表示裁剪候选，不能作为整图选片提交 ID。
- 安全化规则：保留 Unicode 字母/数字、下划线、点和连字符；其他连续字符替换为 `_`，首尾的点、下划线和连字符移除。

最终输出给老师或回映原图时使用 `source_id`；模块间关联使用 `image_id`；展示某个裁剪时使用 `crop_id`。

## 人工评价表

每行表示一名评价者对一组图片的一次独立评价。`evaluator_id` 采用 `E` + 三位匿名序号，例如 `E001`，不得填写姓名、学号或手机号。一个评价者在同一轮标注中保持同一编号，不得跨人复用。

- 单选：`selected_image_id` 填被选原图的完整 `image_id`，`is_tie=false`，`tied_image_ids` 留空。
- 并列：`selected_image_id` 留空，`is_tie=true`，多个完整 `image_id` 按字典序用分号连接写入 `tied_image_ids`。
- `reason`：填写可复核的简短原因，例如“主体清晰、表情自然”，不能只写“好看”。
- 唯一性：`group_id + evaluator_id` 构成一次评价的唯一键；同一组合不能出现两行。

字段：`group_id,evaluator_id,selected_image_id,is_tie,tied_image_ids,reason`。

示例：

```csv
group_id,evaluator_id,selected_image_id,is_tie,tied_image_ids,reason
G20261116_001,E001,G20261116_001__IMG_0001__a1b2c3d4,false,,主体清晰且构图完整
```

## 预处理清单

预处理清单至少保留 `group_id`、`source_id`、`image_id`、原始路径、处理路径、尺寸、状态、错误和耗时，确保评分、标注和最终提交结果可以追溯到原始图片。

模板位置：

- `data/annotations/dataset_manifest_template.csv`
- `data/annotations/human_selection_template.csv`
