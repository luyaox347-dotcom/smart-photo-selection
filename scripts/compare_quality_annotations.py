"""Compare B's existing whole-image scores with A's human annotation format."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from math import isclose, isfinite
from pathlib import Path

TIE_TOLERANCE = 1e-9
ANNOTATION_FIELDS = {
    "group_id", "evaluator_id", "selected_image_id", "is_tie", "tied_image_ids", "reason",
}
SCORE_FIELDS = {"group_id", "image_id", "record_kind", "quality_score", "status"}


def read_rows(path: Path, required: set[str]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"Missing required columns in {path}")
        return list(reader)


def compare_annotations(scores: list[dict], annotations: list[dict]) -> dict:
    groups: dict[str, dict[str, float]] = defaultdict(dict)
    for row in scores:
        if row["record_kind"] != "image":
            raise ValueError("Human comparison requires whole-image scores")
        if row["status"] != "success":
            continue
        group, image_id = row["group_id"], row["image_id"]
        score = float(row["quality_score"])
        if not group or not image_id or not isfinite(score) or not 0 <= score <= 10:
            raise ValueError(f"Invalid scored image: {group!r}, {image_id!r}")
        if image_id in groups[group] and groups[group][image_id] != score:
            raise ValueError(f"Conflicting scores for {group}, {image_id}")
        groups[group][image_id] = score

    def key(row: dict) -> tuple[str, str]:
        return row["group_id"].strip(), row["evaluator_id"].strip()

    counts = Counter(map(key, annotations))
    comparisons, excluded = [], []
    for row in annotations:
        group, evaluator = key(row)
        detail = {"group_id": group, "evaluator_id": evaluator, "reason": row["reason"]}
        is_tie = row["is_tie"].strip().lower()
        selected = row["selected_image_id"].strip()
        tied = {value.strip() for value in row["tied_image_ids"].split(";") if value.strip()}
        human = tied if is_tie == "true" else {selected}
        scored = groups.get(group, {})
        if not group or not evaluator or counts[group, evaluator] != 1:
            error = "Missing or duplicate annotation key"
        elif not ((is_tie == "true" and not selected and len(tied) >= 2)
                  or (is_tie == "false" and selected and not tied)):
            error = "Invalid single or tied annotation"
        elif len(scored) < 2:
            error = "Fewer than two distinct successfully scored images"
        elif not human.issubset(scored):
            error = "At least one human choice is missing a successful score"
        else:
            top_score = max(scored.values())
            predicted = sorted(
                image for image, score in scored.items()
                if isclose(top_score, score, rel_tol=0, abs_tol=TIE_TOLERANCE)
            )
            comparisons.append({
                **detail, "predicted_image_ids": predicted, "predicted_score": top_score,
                "human_choices": {image: scored[image] for image in sorted(human)},
                "agreement": bool(human.intersection(predicted)),
            })
            continue
        excluded.append({**detail, "error": error})

    by_group: dict[str, list[bool]] = defaultdict(list)
    for row in comparisons:
        by_group[row["group_id"]].append(row["agreement"])
    group_agreement = {group: sum(votes) / len(votes) for group, votes in sorted(by_group.items())}
    return {
        "status": "complete" if comparisons else "pending",
        "annotation_rows": len(annotations),
        "participating_groups": len(by_group),
        "compared_annotations": len(comparisons),
        "agreed_annotations": sum(row["agreement"] for row in comparisons),
        "annotation_agreement_rate": (
            sum(row["agreement"] for row in comparisons) / len(comparisons) if comparisons else None
        ),
        "mean_group_agreement_rate": (
            sum(group_agreement.values()) / len(group_agreement) if group_agreement else None
        ),
        "tie_tolerance": TIE_TOLERANCE,
        "group_agreement": group_agreement,
        "comparisons": comparisons,
        "excluded_annotations": excluded,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scores", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {args.scores.resolve(), args.annotations.resolve()}:
        parser.error("Output must be distinct from both inputs")
    result = compare_annotations(
        read_rows(args.scores, SCORE_FIELDS), read_rows(args.annotations, ANNOTATION_FIELDS),
    )
    result.update(scores=args.scores.as_posix(), annotations=args.annotations.as_posix())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{result['status']}: {result['participating_groups']} groups, "
          f"{result['compared_annotations']} compared annotations")


if __name__ == "__main__":
    main()
