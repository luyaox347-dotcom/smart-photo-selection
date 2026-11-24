"""Score a batch of original paths or precomputed A records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import SCORE_OUTPUT_DIR
from src.preprocessing import preprocess_images
from src.quality import evaluate_crop_quality, evaluate_quality_batch, export_quality_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="*", type=Path)
    parser.add_argument("--preprocessing-records", type=Path)
    parser.add_argument("--group-id")
    parser.add_argument("--processed-dir", type=Path)
    parser.add_argument("--output", type=Path, default=SCORE_OUTPUT_DIR / "quality.csv")
    parser.add_argument("--crop-records", type=Path, help="JSON array of crop lists in parent order")
    parser.add_argument("--crop-output", type=Path, default=SCORE_OUTPUT_DIR / "crop_quality.csv")
    args = parser.parse_args()
    if bool(args.images) == bool(args.preprocessing_records):
        parser.error("Provide image paths or --preprocessing-records")
    if args.preprocessing_records and (args.group_id or args.processed_dir):
        parser.error("--group-id and --processed-dir require original image paths")
    if args.crop_records and not args.preprocessing_records:
        parser.error("--crop-records requires --preprocessing-records")
    if args.crop_records and args.output.resolve() == args.crop_output.resolve():
        parser.error("Whole-image and crop outputs need distinct filenames")

    if args.preprocessing_records:
        records = json.loads(args.preprocessing_records.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            parser.error("Preprocessing JSON must contain a list of A records")
    else:
        records = preprocess_images(args.images, group_id=args.group_id, output_dir=args.processed_dir)
    crops = None
    if args.crop_records:
        candidates = json.loads(args.crop_records.read_text(encoding="utf-8-sig"))
        if (not isinstance(candidates, list) or len(candidates) != len(records)
                or any(not isinstance(group, list) or any(not isinstance(row, dict) for row in group)
                       for group in candidates)):
            parser.error("Crop JSON must contain one list of crop records per preprocessing record")
        crops = [
            row for record, group in zip(records, candidates)
            for row in evaluate_crop_quality(record, group)
        ]
    images = evaluate_quality_batch(records)
    exports = {str(export_quality_csv(images, args.output)): images}
    if crops is not None:
        exports[str(export_quality_csv(crops, args.crop_output))] = crops
    print(json.dumps({
        path: {"rows": len(rows), "success": sum(row["status"] == "success" for row in rows)}
        for path, rows in exports.items()
    }, indent=2))


if __name__ == "__main__":
    main()
