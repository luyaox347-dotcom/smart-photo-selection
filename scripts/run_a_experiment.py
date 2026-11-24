"""Run member A preprocessing/cropping experiments and export CSV/JSON."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cropping import generate_crops  # noqa: E402
from src.preprocessing import preprocess_images  # noqa: E402


def _average(values: list[float]) -> float:
    return round(mean(values), 3) if values else 0.0


def run_experiment(
    input_dir: Path,
    processed_dir: Path,
    crop_dir: Path,
    output_dir: Path,
) -> dict:
    test_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff"}
    image_paths = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in test_extensions
    )
    expected_status: dict[str, str] = {}
    manifest_path = input_dir / "cases_manifest.csv"
    if manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            expected_status = {
                row["file_name"]: row["expected_status"]
                for row in csv.DictReader(stream)
            }
    preprocessing = preprocess_images(
        image_paths,
        group_id=input_dir.name,
        output_dir=processed_dir,
    )

    rows: list[dict] = []
    crop_raw_total = 0
    crop_unique_total = 0
    for item in preprocessing:
        row = {
            "source_id": item["source_id"],
            "image_id": item["image_id"],
            "status": item["status"],
            "error": item["error"],
            "expected_status": expected_status.get(Path(item["original_path"]).name),
            "expectation_met": None,
            "original_width": item["original_width"],
            "original_height": item["original_height"],
            "processed_width": item["width"],
            "processed_height": item["height"],
            "orientation_corrected": item["orientation_corrected"],
            "preprocessing_time_ms": item["processing_time_ms"],
            "crop_status": "skipped",
            "crop_error": None,
            "crop_count": 0,
            "crop_sources": "",
            "crop_generation_time_ms": None,
            "raw_candidate_count": 0,
            "unique_candidate_count": 0,
            "candidate_validity_rate": None,
            "face_detector": None,
            "face_detection_count": None,
            "face_score_threshold": None,
            "face_nms_threshold": None,
        }
        if row["expected_status"]:
            row["expectation_met"] = item["status"] == row["expected_status"]
        if item["status"] == "success":
            try:
                crops = generate_crops(item["image_path"], output_dir=crop_dir)
                stats = crops[0]["generation_stats"] if crops else {}
                row.update(
                    {
                        "crop_status": "success",
                        "crop_count": len(crops),
                        "crop_sources": ";".join(
                            sorted({crop["source"] for crop in crops})
                        ),
                        "crop_generation_time_ms": crops[0]["generation_time_ms"]
                        if crops
                        else 0,
                        "raw_candidate_count": stats.get("raw_candidate_count", 0),
                        "unique_candidate_count": stats.get(
                            "unique_candidate_count", 0
                        ),
                        "candidate_validity_rate": stats.get(
                            "candidate_validity_rate"
                        ),
                        "face_detector": stats.get("face_detector"),
                        "face_detection_count": stats.get("face_detection_count"),
                        "face_score_threshold": stats.get("face_score_threshold"),
                        "face_nms_threshold": stats.get("face_nms_threshold"),
                    }
                )
                crop_raw_total += stats.get("raw_candidate_count", 0)
                crop_unique_total += stats.get("unique_candidate_count", 0)
            except Exception as exc:
                row["crop_status"] = "error"
                row["crop_error"] = str(exc)
        rows.append(row)

    success_rows = [row for row in rows if row["status"] == "success"]
    crop_success_rows = [row for row in rows if row["crop_status"] == "success"]
    expectation_rows = [row for row in rows if row["expected_status"]]
    summary = {
        "input_directory": str(input_dir),
        "total_files": len(rows),
        "preprocessing_success_count": len(success_rows),
        "preprocessing_failure_count": len(rows) - len(success_rows),
        "preprocessing_success_rate": round(
            len(success_rows) / len(rows) * 100, 3
        )
        if rows
        else 0.0,
        "expected_outcome_accuracy": round(
            sum(bool(row["expectation_met"]) for row in expectation_rows)
            / len(expectation_rows)
            * 100,
            3,
        )
        if expectation_rows
        else None,
        "orientation_corrected_count": sum(
            bool(row["orientation_corrected"]) for row in success_rows
        ),
        "average_preprocessing_time_ms": _average(
            [float(row["preprocessing_time_ms"]) for row in rows]
        ),
        "crop_success_count": len(crop_success_rows),
        "crop_failure_count": len(success_rows) - len(crop_success_rows),
        "average_crop_generation_time_ms": _average(
            [float(row["crop_generation_time_ms"]) for row in crop_success_rows]
        ),
        "average_returned_crop_count": _average(
            [float(row["crop_count"]) for row in crop_success_rows]
        ),
        "overall_candidate_validity_rate": round(
            crop_unique_total / crop_raw_total * 100, 3
        )
        if crop_raw_total
        else 0.0,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "a_experiment_details.csv"
    json_path = output_dir / "a_experiment_summary.json"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    return {"summary": summary, "csv_path": str(csv_path), "json_path": str(json_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--crop-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        args.input_dir, args.processed_dir, args.crop_dir, args.output_dir
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
