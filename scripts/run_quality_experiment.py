"""Run controlled quality comparisons and time the two scoring stages."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from statistics import mean, median, stdev
from tempfile import TemporaryDirectory

import cv2
import matplotlib
import numpy as np
from PIL import Image, ImageDraw, __version__ as pillow_version

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.quality import DEFAULT_QUALITY_CONFIG
from src.cropping import generate_crops
from src.preprocessing import preprocess_images
from src.quality import (
    RAW_FIELDS, evaluate_crop_quality, evaluate_quality_batch, export_quality_csv,
    score_quality_metrics,
)

DEGRADATIONS = ("blurred", "overexposed", "underexposed", "low_contrast")
SIZES = ((640, 480), (1920, 1080), (3840, 2160))
SEED = 20261124
WEIGHTS = {
    "default": DEFAULT_QUALITY_CONFIG.weights,
    "equal": (1 / 3,) * 3,
    "exposure_first": (0.25, 0.60, 0.15),
    "sharpness_only": (1, 0, 0),
    "exposure_only": (0, 1, 0),
    "contrast_only": (0, 0, 1),
}
ALTERNATIVE_NORMALIZATIONS = ("log_sharpness", "linear")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_samples(directory: Path) -> dict[str, list[Path]]:
    directory.mkdir()
    samples = {}
    for index, (width, height) in enumerate(SIZES):
        rng = np.random.default_rng(SEED + index)
        group = f"synthetic_{width}x{height}"
        scene = Image.new("L", (640, 480), 105 + 10 * index)
        draw = ImageDraw.Draw(scene)
        draw.ellipse((35, 45, 420, 420), fill=166 - 10 * index, outline=58, width=3)
        for _ in range(84):
            x, y = rng.integers((24, 24), (597, 420)).tolist()
            level = int(rng.integers(39, 218))
            draw.rectangle((x, y, x + 15, y + 25), fill=level)
        array = np.asarray(scene.resize((width, height), Image.Resampling.BILINEAR))
        values = array.astype(np.float32)
        sigma = 3 * max(width, height) / 512
        variants = {
            "clean": array,
            "blurred": cv2.GaussianBlur(array, (0, 0), sigmaX=sigma),
            "overexposed": np.clip(values + 132, 0, 255).astype(np.uint8),
            "underexposed": np.clip(values - 110, 0, 255).astype(np.uint8),
            "low_contrast": np.rint(127 + 0.25 * (values - 127)).astype(np.uint8),
        }
        paths = []
        for name, pixels in variants.items():
            path = directory / f"{group}_{name}.png"
            Image.fromarray(pixels).save(path)
            paths.append(path)
        samples[group] = paths
    return samples


def relative_scratch_paths(rows: list[dict], scratch: Path) -> list[dict]:
    fields = ("original_path", "processed_path", "image_path", "source_image_path")
    for row in rows:
        for key in fields:
            if row[key] and Path(row[key]).is_relative_to(scratch):
                row[key] = Path(row[key]).relative_to(scratch).as_posix()
    return rows


def analyze_configurations(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    details, summaries = [], []
    for normalization, (name, weights) in product(ALTERNATIVE_NORMALIZATIONS, WEIGHTS.items()):
        config = replace(DEFAULT_QUALITY_CONFIG, normalization=normalization, weights=weights)
        scored = {}
        for row in rows:
            scores = score_quality_metrics(*(row[field] for field in RAW_FIELDS), config=config)
            details.append({
                "normalization": normalization, "weights": name,
                "group_id": row["group_id"], "image_id": row["image_id"], "variant": row["variant"],
                **{field: row[field] for field in RAW_FIELDS}, **scores,
            })
            scored[row["group_id"], row["variant"]] = scores["quality_score"]
        groups = sorted({row["group_id"] for row in rows})
        margins = {
            variant: [scored[group, "clean"] - scored[group, variant] for group in groups]
            for variant in DEGRADATIONS
        }
        differences = [margin for variant_margins in margins.values() for margin in variant_margins]
        summaries.append({
            "normalization": normalization, "weights": name,
            "sharpness_weight": weights[0], "exposure_weight": weights[1],
            "contrast_weight": weights[2], "pairs": len(differences),
            "clean_wins": sum(diff > 1e-9 for diff in differences),
            "ties": sum(abs(diff) <= 1e-9 for diff in differences),
            "clean_losses": sum(diff < -1e-9 for diff in differences),
            **{f"mean_margin_{variant}": mean(values) for variant, values in margins.items()},
        })
    return details, summaries


def measure_times(records: list[dict], warmup: int, repeats: int) -> tuple[list[dict], list[dict]]:
    for _ in range(warmup):
        evaluate_quality_batch(records)
    samples = []
    for repeat in range(1, repeats + 1):
        for row in evaluate_quality_batch(records):
            samples.append({
                "repeat": repeat,
                **{key: row[key] for key in (
                    "group_id", "image_id", "width", "height", "sharpness_width", "sharpness_height",
                    "read_time_ms", "compute_time_ms",
                )},
            })
    statistics = []
    for width, height in SIZES:
        group = [row for row in samples if (row["width"], row["height"]) == (width, height)]
        for stage in ("read", "compute"):
            values = [row[f"{stage}_time_ms"] for row in group]
            statistics.append({
                "width": width, "height": height, "stage": stage, "measurements": len(values),
                "mean_ms": mean(values), "median_ms": median(values), "std_ms": stdev(values),
                "min_ms": min(values), "max_ms": max(values),
            })
    return samples, statistics


def plot_scores(rows: list[dict], path: Path) -> None:
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    variants = ("clean", *DEGRADATIONS)
    figure, axes = plt.subplots(1, 3, figsize=(11, 3.6), layout="constrained", sharey=True)
    for axis, (width, height) in zip(axes, SIZES):
        subset = {row["variant"]: row for row in rows if row["width"] == width}
        axis.bar(("Clean", "Blur", "Bright", "Dark", "Low contrast"),
                 [subset[variant]["quality_score"] for variant in variants], color="#245e99")
        axis.set(title=f"{width} × {height}", ylim=(0, 10))
        axis.tick_params(axis="x", rotation=32)
        axis.grid(axis="y", alpha=0.24)
    axes[0].set_ylabel("Quality score (0–10)")
    figure.savefig(path, dpi=150)
    plt.close(figure)


def score_real_cases(input_dir: Path, scratch: Path, output: Path) -> dict:
    with (input_dir / "cases_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
        paths = [input_dir / row["file_name"] for row in csv.DictReader(stream)]
    records = preprocess_images(paths, group_id=input_dir.name, output_dir=scratch / "real_processed")
    images = evaluate_quality_batch(records)
    crops = [
        result
        for record in records if record["status"] == "success"
        for result in evaluate_crop_quality(
            record, generate_crops(record["image_path"], output_dir=scratch / "real_crops"),
        )
    ]
    export_quality_csv(relative_scratch_paths(images, scratch), output / "real_quality.csv")
    export_quality_csv(relative_scratch_paths(crops, scratch), output / "real_crop_quality.csv")
    return {
        "input_directory": input_dir.as_posix(), "images": len(images), "crops": len(crops),
        "scored_images": sum(row["status"] == "success" for row in images),
        "scored_crops": sum(row["status"] == "success" for row in crops),
        "failed_images": [
            {"source_id": row["source_id"], "error": row["error"]}
            for row in images if row["status"] != "success"
        ],
        "image_score_range": score_range(images), "crop_score_range": score_range(crops),
    }


def score_range(rows: list[dict]) -> list[float] | None:
    values = [row["quality_score"] for row in rows if row["status"] == "success"]
    return [min(values), max(values)] if values else None


def cpu_name() -> str:
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def run(output: Path, real_dir: Path | None, warmup: int, repeats: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    with TemporaryDirectory(prefix="quality-inputs-", dir=output) as root:
        scratch = Path(root)
        samples = make_samples(scratch / "synthetic")
        records = [
            record
            for group, paths in samples.items()
            for record in preprocess_images(paths, group_id=group, output_dir=scratch / "processed")
        ]
        rows = relative_scratch_paths(evaluate_quality_batch(records), scratch)
        for row in rows:
            if row["status"] != "success":
                raise RuntimeError(f"Synthetic input failed: {row['error']}")
            row["variant"] = row["source_id"].removeprefix(row["group_id"] + "_")
        details, configurations = analyze_configurations(rows)
        times, timings = measure_times(records, warmup, repeats)
        real = score_real_cases(real_dir, scratch, output) if real_dir is not None else None

    write_csv(output / "synthetic_quality.csv", rows)
    write_csv(output / "configuration_scores.csv", details)
    write_csv(output / "configuration_summary.csv", configurations)
    write_csv(output / "timing_samples.csv", times)
    plot_scores(rows, output / "synthetic_scores.png")
    summary = {
        "environment": {
            "system": platform.platform(), "cpu": cpu_name(), "logical_cpus": os.cpu_count(),
            "python": platform.python_version(), "opencv": cv2.__version__, "opencv_threads": 1,
            "numpy": np.__version__, "pillow": pillow_version, "matplotlib": matplotlib.__version__,
        },
        "default_config": asdict(DEFAULT_QUALITY_CONFIG),
        "synthetic": {"seed": SEED, "groups": len(samples), "images": len(rows), "sizes": SIZES},
        "timing": {"warmup_batches": warmup, "measured_batches": repeats, "statistics": timings},
        "configurations": configurations,
        "real_cases": real,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/experiments/quality"))
    parser.add_argument("--real-dir", type=Path)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=6)
    args = parser.parse_args()
    if args.warmup < 1 or args.repeats < 2:
        parser.error("Use at least one warmup and two measured repetitions")
    run(args.output_dir, args.real_dir, args.warmup, args.repeats)
    print(f"Quality experiment results: {args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
