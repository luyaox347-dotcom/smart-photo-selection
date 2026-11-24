from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from src.pipeline import run_selection


st.set_page_config(page_title="SmartPhotoSelection", layout="wide")
st.title("智能选片系统")
st.info("画质分来自图像分析，美学分为模拟值，综合排名仅用于流程验证。")

uploaded_files = st.file_uploader(
    "上传同一场景的照片（JPG / PNG）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.write(f"已上传 {len(uploaded_files)} 张照片。")

if st.button("开始分析", disabled=not uploaded_files):
    with TemporaryDirectory() as temp_dir:
        paths = []
        names_by_path = {}
        for index, file in enumerate(uploaded_files, start=1):
            source_id = f"photo_{index:04d}"
            path = Path(temp_dir) / f"{source_id}{Path(file.name).suffix.lower()}"
            path.write_bytes(file.getbuffer())
            paths.append(path)
            names_by_path[str(path)] = file.name

        result = run_selection(paths, output_dir=Path(temp_dir) / "processed")
        for error in result["errors"]:
            name = names_by_path.get(error.get("original_path"))
            st.warning(f"{name}：{error['message']}" if name else error["message"])

        recommendation = result["recommendation"]
        if recommendation:
            st.subheader("推荐照片")
            image_id = recommendation["image_id"]
            images = {item["image_id"]: item for item in result["images"]}
            names = {key: names_by_path[item["original_path"]] for key, item in images.items()}
            st.image(Path(images[image_id]["image_path"]).read_bytes(), caption=names[image_id])
            st.write(f"演示综合分 {recommendation['final_score']:.2f}，排名第 1。")

            st.subheader("评分排名")
            st.dataframe(
                [
                    {
                        "排名": row["rank"],
                        "照片": names[row["image_id"]],
                        "画质分": row["quality_score"],
                        "模拟美学分": row["aesthetic_score"],
                        "综合分": row["final_score"],
                    }
                    for row in result["ranking"]
                ],
                hide_index=True,
            )

            st.subheader("照片预览")
            columns = st.columns(min(4, len(result["ranking"])))
            for index, row in enumerate(result["ranking"]):
                image_id = row["image_id"]
                image_bytes = Path(images[image_id]["image_path"]).read_bytes()
                columns[index % len(columns)].image(image_bytes, caption=names[image_id])
