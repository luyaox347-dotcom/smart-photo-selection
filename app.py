import streamlit as st

st.set_page_config(page_title="SmartPhotoSelection", layout="wide")
st.title("智能选片系统")
st.write("上传同一场景的多张照片，系统将逐步提供画质评价、美学评分与推荐结果。")

uploaded_files = st.file_uploader(
    "上传同一场景的照片（JPG / PNG）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.info(f"已上传 {len(uploaded_files)} 张照片。当前为项目骨架，算法模块接入后将显示分析结果。")
    cols = st.columns(min(4, len(uploaded_files)))
    for i, file in enumerate(uploaded_files):
        with cols[i % len(cols)]:
            st.image(file, caption=file.name, use_container_width=True)
