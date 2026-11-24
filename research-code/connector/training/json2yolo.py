#!/usr/bin/env python3
"""Convert cleaned LabelMe annotations into a YOLO detection dataset."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "YOLO_Baseline_Data"

IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
POINT_BOX_WIDTH_RATIO = 0.04
POINT_BOX_HEIGHT_RATIO = 0.04

CLASS_MAP = {
    "female_interface": 0,
    "male_connector": 1,
    "movable_part": 2,
    "assembled_structure": 3,
}

EXPECTED_SHAPE_TYPES = {
    "female_interface": "point",
    "male_connector": "point",
    "movable_part": "polygon",
    "assembled_structure": "polygon",
}

SPLIT_SOURCES = {
    "train": (
        Path("train/labeled_human/assembly"),
        Path("train/labeled_human/disassembly"),
    ),
    "val": (
        Path("val/labeled_human/assembly"),
        Path("val/labeled_human/disassembly"),
    ),
    "test": (
        Path("test/labeled_human/assembly"),
        Path("test/labeled_human/disassembly"),
    ),
}

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")


@dataclass
class ConversionStats:
    images: int = 0
    labels: int = 0
    shapes_written: int = 0
    invalid_labels: int = 0
    invalid_shapes: int = 0
    empty_labels: int = 0


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a numeric value to an inclusive range."""
    return max(lower, min(value, upper))


def find_matching_image(json_path: Path) -> Path | None:
    """Find an image with the same stem next to a LabelMe JSON file."""
    for suffix in IMAGE_SUFFIXES:
        candidate = json_path.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def point_to_yolo(
    points: list[list[float]],
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float] | None:
    """Convert one LabelMe point into a fixed 4%-by-4% detection box.

    The point remains the center of the generated box. During the later custom
    point evaluation, the predicted box center is compared with this ground
    truth center. A prediction is accepted when the Euclidean center distance
    is less than 3% of the image diagonal. The fixed box is only a practical
    representation that allows a standard YOLO detector to learn point-like
    interfaces; it is not treated as a pixel-perfect object boundary.
    """
    if not points or len(points[0]) < 2:
        return None
    center_x = clamp(float(points[0][0]), 0.0, float(image_width))
    center_y = clamp(float(points[0][1]), 0.0, float(image_height))
    return (
        center_x / image_width,
        center_y / image_height,
        POINT_BOX_WIDTH_RATIO,
        POINT_BOX_HEIGHT_RATIO,
    )


def polygon_to_yolo(
    points: list[list[float]],
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float] | None:
    """Convert a polygon to its minimum outer axis-aligned bounding box."""
    valid_points = [
        (float(point[0]), float(point[1]))
        for point in points
        if isinstance(point, list) and len(point) >= 2
    ]
    if len(valid_points) < 3:
        return None

    x_values = [point[0] for point in valid_points]
    y_values = [point[1] for point in valid_points]
    x_min = clamp(min(x_values), 0.0, float(image_width))
    x_max = clamp(max(x_values), 0.0, float(image_width))
    y_min = clamp(min(y_values), 0.0, float(image_height))
    y_max = clamp(max(y_values), 0.0, float(image_height))
    if x_max <= x_min or y_max <= y_min:
        return None

    return (
        ((x_min + x_max) / 2.0) / image_width,
        ((y_min + y_max) / 2.0) / image_height,
        (x_max - x_min) / image_width,
        (y_max - y_min) / image_height,
    )


def convert_shape(
    shape: dict[str, Any],
    image_width: int,
    image_height: int,
) -> tuple[int, float, float, float, float] | None:
    """Convert one valid LabelMe shape to a YOLO detection row."""
    label = shape.get("label")
    if label not in CLASS_MAP:
        return None

    shape_type = shape.get("shape_type")
    if shape_type != EXPECTED_SHAPE_TYPES[label]:
        return None

    points = shape.get("points", [])
    if label in {"female_interface", "male_connector"}:
        box = point_to_yolo(points, image_width, image_height)
    else:
        box = polygon_to_yolo(points, image_width, image_height)
    if box is None:
        return None
    return (CLASS_MAP[label], *box)


def prepare_output(output_root: Path, clean_output: bool) -> None:
    """Create the standard YOLO images/labels split directories."""
    if clean_output and output_root.exists():
        shutil.rmtree(output_root)
    for split in SPLIT_SOURCES:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)


def convert_dataset(
    source_root: Path,
    output_root: Path,
) -> tuple[dict[str, ConversionStats], list[dict[str, str]]]:
    """Convert every cleaned human-labeled sample and copy its source image."""
    all_stats: dict[str, ConversionStats] = {}
    issue_rows: list[dict[str, str]] = []
    used_names: dict[str, Path] = {}

    for split, source_directories in SPLIT_SOURCES.items():
        stats = ConversionStats()
        all_stats[split] = stats
        image_output = output_root / "images" / split
        label_output = output_root / "labels" / split

        json_files: list[Path] = []
        for relative_directory in source_directories:
            directory = source_root / relative_directory
            if not directory.is_dir():
                raise FileNotFoundError(f"Required source directory not found: {directory}")
            json_files.extend(directory.rglob("*.json"))

        for json_path in sorted(json_files):
            image_path = find_matching_image(json_path)
            if image_path is None:
                raise FileNotFoundError(f"No matching image for: {json_path}")

            output_name_key = f"{split}/{image_path.name.lower()}"
            previous = used_names.get(output_name_key)
            if previous is not None and previous != image_path:
                raise RuntimeError(
                    "Duplicate image filename would overwrite another sample: "
                    f"{previous} and {image_path}"
                )
            used_names[output_name_key] = image_path

            with json_path.open("r", encoding="utf-8-sig") as handle:
                annotation = json.load(handle)

            image_width = int(annotation.get("imageWidth") or IMAGE_WIDTH)
            image_height = int(annotation.get("imageHeight") or IMAGE_HEIGHT)
            if (image_width, image_height) != (IMAGE_WIDTH, IMAGE_HEIGHT):
                raise ValueError(
                    f"Unexpected image size in {json_path}: "
                    f"{image_width}x{image_height}, expected 1280x720"
                )

            yolo_rows: list[tuple[int, float, float, float, float]] = []
            for shape_index, shape in enumerate(annotation.get("shapes", [])):
                if not isinstance(shape, dict):
                    stats.invalid_shapes += 1
                    issue_rows.append(
                        {
                            "split": split,
                            "json_path": str(json_path),
                            "shape_index": str(shape_index),
                            "label": "",
                            "shape_type": "",
                            "reason": "Shape entry is not a JSON object.",
                        }
                    )
                    continue
                label = shape.get("label")
                if label not in CLASS_MAP:
                    stats.invalid_labels += 1
                    issue_rows.append(
                        {
                            "split": split,
                            "json_path": str(json_path),
                            "shape_index": str(shape_index),
                            "label": str(label),
                            "shape_type": str(shape.get("shape_type")),
                            "reason": "Label is not in the four-class whitelist.",
                        }
                    )
                    continue
                converted = convert_shape(shape, image_width, image_height)
                if converted is None:
                    stats.invalid_shapes += 1
                    issue_rows.append(
                        {
                            "split": split,
                            "json_path": str(json_path),
                            "shape_index": str(shape_index),
                            "label": str(label),
                            "shape_type": str(shape.get("shape_type")),
                            "reason": (
                                "Shape type or point geometry does not match "
                                "the required class annotation format."
                            ),
                        }
                    )
                    continue
                yolo_rows.append(converted)

            shutil.copy2(image_path, image_output / image_path.name)
            label_path = label_output / f"{image_path.stem}.txt"
            with label_path.open("w", encoding="utf-8", newline="\n") as handle:
                for class_id, x_center, y_center, box_width, box_height in yolo_rows:
                    handle.write(
                        f"{class_id} {x_center:.8f} {y_center:.8f} "
                        f"{box_width:.8f} {box_height:.8f}\n"
                    )

            stats.images += 1
            stats.labels += 1
            stats.shapes_written += len(yolo_rows)
            if not yolo_rows:
                stats.empty_labels += 1

    return all_stats, issue_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert cleaned LabelMe JSON annotations to YOLO detection labels."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Root of the cleaned split_data dataset.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Destination root for YOLO_Baseline_Data.",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete the existing output dataset before conversion.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if source_root.is_relative_to(output_root):
        raise ValueError("The output folder must not contain the source dataset.")
    if not source_root.is_dir():
        raise FileNotFoundError(f"Source dataset does not exist: {source_root}")
    prepare_output(output_root, args.clean_output)
    stats, issue_rows = convert_dataset(source_root, output_root)

    issue_log = output_root / "conversion_issues.csv"
    with issue_log.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "split",
                "json_path",
                "shape_index",
                "label",
                "shape_type",
                "reason",
            ),
        )
        writer.writeheader()
        writer.writerows(issue_rows)

    print(f"Source dataset: {source_root}")
    print(f"YOLO dataset:   {output_root}")
    for split, split_stats in stats.items():
        print(
            f"{split:>5}: images={split_stats.images}, "
            f"labels={split_stats.labels}, "
            f"objects={split_stats.shapes_written}, "
            f"empty_labels={split_stats.empty_labels}, "
            f"invalid_labels={split_stats.invalid_labels}, "
            f"invalid_shapes={split_stats.invalid_shapes}"
        )
    print(f"Conversion issue log: {issue_log}")


if __name__ == "__main__":
    main()
