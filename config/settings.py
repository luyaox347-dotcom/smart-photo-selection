from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ANNOTATIONS_DIR = DATA_DIR / "annotations"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CROP_OUTPUT_DIR = OUTPUT_DIR / "crops"
SCORE_OUTPUT_DIR = OUTPUT_DIR / "scores"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_CROPS = 7
QUALITY_WEIGHT = 0.4
AESTHETIC_WEIGHT = 0.6
