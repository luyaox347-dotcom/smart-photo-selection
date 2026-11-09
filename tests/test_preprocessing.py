from PIL import Image
from src.preprocessing import preprocess_images


def test_preprocess_reads_image(tmp_path):
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (120, 80), "white").save(image_path)
    result = preprocess_images([image_path])
    assert result[0]["status"] == "success"
    assert result[0]["width"] == 120
    assert result[0]["height"] == 80
