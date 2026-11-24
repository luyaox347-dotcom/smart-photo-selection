from pathlib import Path

from PIL import Image

from src.preprocessing import preprocess_images


def test_preprocess_reads_image(tmp_path):
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (120, 80), "white").save(image_path)
    original_bytes = image_path.read_bytes()

    result = preprocess_images(
        [image_path], group_id="group_001", output_dir=tmp_path / "processed"
    )[0]

    assert result["status"] == "success"
    assert result["group_id"] == "group_001"
    assert result["source_id"] == "sample"
    assert result["image_id"].startswith("group_001__sample__")
    assert result["width"] == 120
    assert result["height"] == 80
    assert result["original_width"] == 120
    assert result["original_height"] == 80
    assert result["processed_format"] == "PNG"
    assert Path(result["processed_path"]).is_file()
    assert result["image_path"] == result["processed_path"]
    assert image_path.read_bytes() == original_bytes


def test_preprocess_applies_exif_orientation_once(tmp_path):
    image_path = tmp_path / "portrait.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (80, 120), "blue").save(image_path, exif=exif)

    result = preprocess_images(
        [image_path], group_id="g", output_dir=tmp_path / "processed"
    )[0]

    assert result["status"] == "success"
    assert result["original_width"] == 80
    assert result["original_height"] == 120
    assert result["width"] == 120
    assert result["height"] == 80
    assert result["exif_orientation"] == 6
    assert result["orientation_corrected"] is True
    with Image.open(result["processed_path"]) as normalized:
        assert normalized.size == (120, 80)
        assert normalized.getexif().get(274, 1) == 1


def test_preprocess_continues_after_corrupt_image(tmp_path):
    corrupt = tmp_path / "broken.jpg"
    corrupt.write_bytes(b"not an image")
    valid = tmp_path / "valid.png"
    Image.new("RGB", (32, 24), "green").save(valid)

    results = preprocess_images(
        [corrupt, valid], group_id="g", output_dir=tmp_path / "processed"
    )

    assert results[0]["status"] == "error"
    assert results[0]["error"]
    assert results[1]["status"] == "success"


def test_preprocess_rejects_unsupported_extension(tmp_path):
    image_path = tmp_path / "sample.bmp"
    Image.new("RGB", (20, 20), "white").save(image_path)

    result = preprocess_images(
        [image_path], group_id="g", output_dir=tmp_path / "processed"
    )[0]

    assert result["status"] == "error"
    assert "不支持" in result["error"]


def test_preprocess_supports_unicode_path_and_alpha(tmp_path):
    image_path = tmp_path / "中文透明图.png"
    Image.new("RGBA", (40, 30), (255, 0, 0, 80)).save(image_path)

    result = preprocess_images(
        [image_path], group_id="中文场景", output_dir=tmp_path / "处理结果"
    )[0]

    assert result["status"] == "success"
    assert result["processed_mode"] == "RGBA"
    with Image.open(result["processed_path"]) as normalized:
        assert normalized.mode == "RGBA"
        assert normalized.getpixel((0, 0))[3] == 80


def test_preprocess_checks_real_format_not_only_extension(tmp_path):
    disguised = tmp_path / "disguised.jpg"
    bmp = tmp_path / "source.bmp"
    Image.new("RGB", (24, 18), "purple").save(bmp)
    disguised.write_bytes(bmp.read_bytes())

    result = preprocess_images(
        [disguised], group_id="g", output_dir=tmp_path / "processed"
    )[0]

    assert result["status"] == "error"
    assert "真实格式" in result["error"]
