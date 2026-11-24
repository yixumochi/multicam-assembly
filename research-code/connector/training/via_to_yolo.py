#!/usr/bin/env python3
"""Convert VIA CSV rectangle annotations to YOLO detection labels.

Supported class names:
    rectangular_opening -> 0
    edge_notch          -> 1
    interlocking_slot   -> 2

The parser supports the common VIA 2.x CSV structure and VIA 3.x CSV rows
that contain a filename plus rectangular spatial coordinates.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DATASET_ROOT = Path.cwd() / "data"
DEFAULT_CSV = DATASET_ROOT / "annotations" / "via_export.csv"
DEFAULT_IMAGES = DATASET_ROOT / "labelframes"
DEFAULT_OUTPUT = DATASET_ROOT / "annotations" / "yolo_labels"
DEFAULT_CLASSES = DATASET_ROOT / "annotations" / "classes.txt"

CLASS_MAP = {
    "rectangular_opening": 0,
    "edge_notch": 1,
    "interlocking_slot": 2,
}

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def parse_serialized(value: Any) -> Any:
    """Parse JSON/Python-like values exported by different VIA versions."""
    if value is None or not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return {}
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            pass
    return text


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from iter_strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from iter_strings(child)


def find_class(attributes: Any) -> str | None:
    """Find one of the fixed class names anywhere in VIA attributes."""
    normalized = {
        text.strip().lower().replace(" ", "_")
        for text in iter_strings(attributes)
        if text.strip()
    }
    matches = [name for name in CLASS_MAP if name in normalized]
    return matches[0] if len(matches) == 1 else None


def numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().lower().replace("%", "")
        try:
            number = float(text)
            return number / 100.0 if number > 1.0 else number
        except ValueError:
            return None
    return None


def visibility_score(attributes: Any) -> float:
    """Read visibility or occlusion metadata; absent metadata means visible."""
    if not isinstance(attributes, dict):
        return 1.0

    for key, value in attributes.items():
        normalized_key = str(key).strip().lower().replace(" ", "_")
        if normalized_key in {"visibility", "visible", "visible_ratio"}:
            score = numeric_value(value)
            if score is not None:
                return max(0.0, min(1.0, score))
        if normalized_key in {"occlusion", "occluded", "occlusion_ratio"}:
            occlusion = numeric_value(value)
            if occlusion is not None:
                return max(0.0, min(1.0, 1.0 - occlusion))
        nested = visibility_score(value)
        if nested != 1.0:
            return nested
    return 1.0


def get_image_size(path: Path) -> tuple[int, int]:
    """Read PNG/JPEG dimensions using only the Python standard library."""
    with path.open("rb") as handle:
        header = handle.read(24)
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            width, height = struct.unpack(">II", header[16:24])
            return width, height

        handle.seek(0)
        if handle.read(2) != b"\xff\xd8":
            raise ValueError(f"Unsupported image format: {path}")

        while True:
            marker_start = handle.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if marker in {
                b"\xc0", b"\xc1", b"\xc2", b"\xc3",
                b"\xc5", b"\xc6", b"\xc7",
                b"\xc9", b"\xca", b"\xcb",
                b"\xcd", b"\xce", b"\xcf",
            }:
                handle.read(3)
                height, width = struct.unpack(">HH", handle.read(4))
                return width, height
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                break
            segment_length = struct.unpack(">H", length_bytes)[0]
            handle.seek(max(0, segment_length - 2), 1)

    raise ValueError(f"Could not determine image dimensions: {path}")


def find_image(images_dir: Path, filename: str) -> Path | None:
    candidate = images_dir / Path(filename).name
    if candidate.is_file():
        return candidate
    stem = Path(filename).stem
    for suffix in IMAGE_SUFFIXES:
        candidate = images_dir / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def extract_filename(row: dict[str, str], images_dir: Path) -> str | None:
    for key in ("filename", "file_name", "name"):
        value = row.get(key, "").strip()
        if value:
            return Path(value).name

    file_list = parse_serialized(row.get("file_list", ""))
    candidates = list(iter_strings(file_list))
    for candidate in candidates:
        if Path(candidate).suffix.lower() in IMAGE_SUFFIXES:
            return Path(candidate).name

    # Some VIA3 CSV exports store a numeric file ID rather than a filename.
    # Guessing this mapping would silently attach labels to the wrong images.
    return None


def extract_rectangle(row: dict[str, str]) -> tuple[float, float, float, float] | None:
    shape = parse_serialized(row.get("region_shape_attributes", ""))
    if isinstance(shape, dict):
        shape_name = str(shape.get("name", "rect")).lower()
        if shape_name not in {"rect", "rectangle"}:
            return None
        keys = ("x", "y", "width", "height")
        if all(key in shape for key in keys):
            return tuple(float(shape[key]) for key in keys)

    spatial = parse_serialized(row.get("spatial_coordinates", ""))
    if isinstance(spatial, dict):
        keys = ("x", "y", "width", "height")
        if all(key in spatial for key in keys):
            return tuple(float(spatial[key]) for key in keys)

    if isinstance(spatial, (list, tuple)):
        values = list(spatial)
        # VIA3 rectangle commonly uses [2, x, y, width, height].
        if len(values) >= 5 and str(values[0]) in {"2", "rect", "rectangle"}:
            return tuple(float(value) for value in values[1:5])
        if len(values) == 4:
            return tuple(float(value) for value in values)

    return None


def read_via_rows(csv_path: Path) -> list[dict[str, str]]:
    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    header_from_comment: list[str] | None = None
    data_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            marker = "CSV_HEADER"
            if marker in stripped and "=" in stripped:
                raw_header = stripped.split("=", 1)[1].strip()
                header_from_comment = next(csv.reader([raw_header]))
            continue
        if stripped:
            data_lines.append(line)

    if not data_lines:
        return []

    if header_from_comment:
        return list(csv.DictReader(data_lines, fieldnames=header_from_comment))
    return list(csv.DictReader(data_lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--min-visibility",
        type=float,
        default=0.50,
        help="Keep annotations with visible ratio >= this value.",
    )
    args = parser.parse_args()

    if not args.csv.is_file():
        raise FileNotFoundError(f"VIA CSV not found: {args.csv}")
    if not args.images.is_dir():
        raise FileNotFoundError(f"Label image directory not found: {args.images}")
    if not 0.0 <= args.min_visibility <= 1.0:
        raise ValueError("--min-visibility must be between 0 and 1")

    args.output.mkdir(parents=True, exist_ok=True)
    DEFAULT_CLASSES.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CLASSES.write_text(
        "\n".join(CLASS_MAP) + "\n",
        encoding="utf-8",
    )

    rows = read_via_rows(args.csv)
    labels: dict[str, list[str]] = defaultdict(list)
    observed_images: set[str] = set()
    skipped = defaultdict(int)

    for row in rows:
        filename = extract_filename(row, args.images)
        if not filename:
            skipped["missing_filename"] += 1
            continue
        observed_images.add(filename)

        rectangle = extract_rectangle(row)
        if rectangle is None:
            # A row without a region is valid and produces an empty txt file.
            if not row.get("region_shape_attributes") and not row.get("spatial_coordinates"):
                continue
            skipped["non_rectangle_or_invalid_shape"] += 1
            continue

        attributes = parse_serialized(
            row.get("region_attributes")
            or row.get("metadata")
            or row.get("attributes")
            or ""
        )
        class_name = find_class(attributes)
        if class_name is None:
            skipped["unknown_or_ambiguous_class"] += 1
            continue
        if visibility_score(attributes) < args.min_visibility:
            skipped["low_visibility"] += 1
            continue

        image_path = find_image(args.images, filename)
        if image_path is None:
            skipped["image_not_found"] += 1
            continue

        image_width, image_height = get_image_size(image_path)
        x, y, width, height = rectangle
        if not all(math.isfinite(value) for value in rectangle):
            skipped["non_finite_box"] += 1
            continue

        x1 = max(0.0, min(float(image_width), x))
        y1 = max(0.0, min(float(image_height), y))
        x2 = max(0.0, min(float(image_width), x + width))
        y2 = max(0.0, min(float(image_height), y + height))
        clipped_width = x2 - x1
        clipped_height = y2 - y1
        if clipped_width < 2.0 or clipped_height < 2.0:
            skipped["box_too_small_or_invalid"] += 1
            continue

        center_x = ((x1 + x2) / 2.0) / image_width
        center_y = ((y1 + y2) / 2.0) / image_height
        normalized_width = clipped_width / image_width
        normalized_height = clipped_height / image_height
        class_id = CLASS_MAP[class_name]
        labels[Path(filename).stem].append(
            f"{class_id} {center_x:.6f} {center_y:.6f} "
            f"{normalized_width:.6f} {normalized_height:.6f}"
        )

    # Create labels for every image mentioned in the CSV. Images with no valid
    # region receive an empty txt file, which is valid for YOLO backgrounds.
    for filename in sorted(observed_images):
        stem = Path(filename).stem
        output_path = args.output / f"{stem}.txt"
        content = "\n".join(labels.get(stem, []))
        output_path.write_text(content + ("\n" if content else ""), encoding="utf-8")

    print(f"CSV rows:              {len(rows)}")
    print(f"Images represented:    {len(observed_images)}")
    print(f"YOLO boxes written:    {sum(map(len, labels.values()))}")
    print(f"YOLO label directory:  {args.output}")
    print(f"Minimum visibility:    {args.min_visibility:.0%}")
    if skipped:
        print("Skipped annotations:")
        for reason, count in sorted(skipped.items()):
            print(f"  {reason}: {count}")

    if skipped.get("missing_filename"):
        print(
            "\nWARNING: Some VIA3 rows used file IDs without filenames. "
            "Export CSV with filenames included; do not guess file-ID mappings."
        )


if __name__ == "__main__":
    main()
