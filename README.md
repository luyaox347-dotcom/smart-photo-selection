# SmartPhotoSelection

基于机器视觉与多模态模型的智能选片系统。当前版本已合并 A 的预处理和裁剪，以及 B 的传统画质评分。网页使用真实画质分和模拟美学分生成演示排名。

## 环境
- Python 3.10.x
- Git
- Windows / macOS

## 快速开始

### 1. 创建虚拟环境

macOS:
```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:
```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. 安装依赖
```bash
python -m pip install --upgrade pip
python -m pip install --prefer-binary -r requirements.txt
```

### 3. 运行测试
```bash
python -m pytest
```

### 4. 启动网页
```bash
streamlit run app.py
```

## 目录说明
- `src/preprocessing.py`: 图片读取与预处理（成员A）
- `src/cropping.py`: 候选裁剪框生成（成员A）
- `src/quality.py`: 传统画质评价（成员B）
- `src/aesthetics.py`: NIMA美学评价（成员C）
- `src/multimodal.py`: 多模态模型复核（成员C）
- `src/ranking.py`: 综合评分与排序（成员D）
- `src/pipeline.py`: 流程整合（成员D）
- `app.py`: Streamlit网页（成员D）

## 协作约定
先在各自分支开发；不要直接向 `main` 推送。接口变更先沟通，并同步更新测试。
私人原图、额外模型权重、`.env` 和虚拟环境不提交到Git。

## A、B 交付与复现

- [A 的数据接口、裁剪和实验说明](docs/member_A_handoff.md)
- [B 的画质评分接口与参数](docs/member_B_quality.md)
- [B 的交接说明](docs/member_B_handoff.md)
- [A 的样本实验](outputs/experiments/real_cases/README.md)和 [B 的画质实验](outputs/experiments/quality/README.md)

从原图路径批量生成画质 CSV：

```bash
python scripts/score_quality.py --help
```

该脚本也支持 A 的预处理 JSON，可分别导出整图和裁剪候选的画质分。网页演示对整图排序，裁剪候选通过模块或实验脚本使用。仓库随附 A 的 YuNet 模型及其许可证，供裁剪功能使用。
