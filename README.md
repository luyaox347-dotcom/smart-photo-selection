# SmartPhotoSelection

基于机器视觉与多模态模型的智能选片系统。

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
.venv\\Scripts\\Activate.ps1
```

### 2. 安装依赖
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
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
原始照片、模型权重、`.env` 和虚拟环境不提交到Git。
