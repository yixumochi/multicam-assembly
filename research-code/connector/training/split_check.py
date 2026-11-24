#!/usr/bin/env python3
"""Check image/label matching and YOLO row validity for every dataset split."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "YOLO_Baseline_Data"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VALID_CLASS_IDS = {0, 1, 2, 3}


def inspect_label(path: Path) -> list[str]:
    """Return validation problems found inside one YOLO label file."""
    problems: list[str] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 5:
            problems.append(f"line {line_number}: expected 5 fields")
            continue
        try:
            class_id = int(fields[0])
            values = [float(value) for value in fields[1:]]
        except ValueError:
            problems.append(f"line {line_number}: non-numeric value")
            continue
        if class_id not in VALID_CLASS_IDS:
            problems.append(f"line {line_number}: invalid class ID {class_id}")
        if any(value < 0.0 or value > 1.0 for value in values):
            problems.append(f"line {line_number}: coordinate outside [0, 1]")
        if values[2] <= 0.0 or values[3] <= 0.0:
            problems.append(f"line {line_number}: non-positive box size")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="Check YOLO image/label pairs.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=PROJECT_ROOT / "split_check_log.csv",
    )
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    has_error = False
    for split in ("train", "val", "test"):
        image_directory = args.dataset_root / "images" / split
        label_directory = args.dataset_root / "labels" / split
        images = {
            path.stem: path
            for path in image_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        }
        labels = {
            path.stem: path
            for path in label_directory.glob("*.txt")
            if path.is_file()
        }

        for stem in sorted(images.keys() - labels.keys()):
            has_error = True
            rows.append(
                {
                    "split": split,
                    "status": "missing_label",
                    "stem": stem,
                    "path": str(images[stem]),
                    "detail": "Image has no matching TXT label.",
                }
            )
        for stem in sorted(labels.keys() - images.keys()):
            has_error = True
            rows.append(
                {
                    "split": split,
                    "status": "missing_image",
                    "stem": stem,
                    "path": str(labels[stem]),
                    "detail": "TXT label has no matching image.",
                }
            )
        for stem in sorted(images.keys() & labels.keys()):
            problems = inspect_label(labels[stem])
            if problems:
                has_error = True
                for problem in problems:
                    rows.append(
                        {
                            "split": split,
                            "status": "invalid_label",
                            "stem": stem,
                            "path": str(labels[stem]),
                            "detail": problem,
                        }
                    )

        print(
            f"{split:>5}: images={len(images)}, labels={len(labels)}, "
            f"paired={len(images.keys() & labels.keys())}"
        )

    if not rows:
        rows.append(
            {
                "split": "all",
                "status": "ok",
                "stem": "",
                "path": str(args.dataset_root.resolve()),
                "detail": "All image/label pairs and YOLO rows passed validation.",
            }
        )

    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("split", "status", "stem", "path", "detail"),
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Check log: {args.log.resolve()}")
    if has_error:
        raise SystemExit("Dataset check failed. Review split_check_log.csv.")
    print("Dataset check passed.")


if __name__ == "__main__":
    main()
