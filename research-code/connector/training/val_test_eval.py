#!/usr/bin/env python3
"""Evaluate standard YOLO metrics and point-center tolerance metrics."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_ROOT = PROJECT_ROOT / "YOLO_Baseline_Data"
DEFAULT_WEIGHTS = PROJECT_ROOT / "runs/baseline_yolo11s/weights/best.pt"
POINT_CLASS_NAMES = {0: "female_interface", 1: "male_connector"}
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
DISTANCE_TOLERANCE_RATIO = 0.03
DISTANCE_TOLERANCE_PIXELS = DISTANCE_TOLERANCE_RATIO * math.hypot(
    IMAGE_WIDTH, IMAGE_HEIGHT
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class MatchCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0


def read_point_ground_truth(label_path: Path) -> dict[int, list[tuple[float, float]]]:
    """Read class 0/1 YOLO box centers and convert them to pixel coordinates."""
    points = {class_id: [] for class_id in POINT_CLASS_NAMES}
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 5:
            continue
        class_id = int(fields[0])
        if class_id not in points:
            continue
        center_x = float(fields[1]) * IMAGE_WIDTH
        center_y = float(fields[2]) * IMAGE_HEIGHT
        points[class_id].append((center_x, center_y))
    return points


def greedy_tolerance_match(
    ground_truth: list[tuple[float, float]],
    predictions: list[tuple[float, float, float]],
    tolerance_pixels: float,
) -> MatchCounts:
    """Perform one-to-one nearest matching inside the distance tolerance."""
    candidates: list[tuple[float, int, int]] = []
    for ground_index, ground_point in enumerate(ground_truth):
        for prediction_index, prediction in enumerate(predictions):
            distance = math.dist(ground_point, prediction[:2])
            if distance < tolerance_pixels:
                candidates.append((distance, ground_index, prediction_index))
    candidates.sort()

    used_ground: set[int] = set()
    used_predictions: set[int] = set()
    true_positive = 0
    for _, ground_index, prediction_index in candidates:
        if ground_index in used_ground or prediction_index in used_predictions:
            continue
        used_ground.add(ground_index)
        used_predictions.add(prediction_index)
        true_positive += 1

    return MatchCounts(
        true_positive=true_positive,
        false_positive=len(predictions) - true_positive,
        false_negative=len(ground_truth) - true_positive,
    )


def evaluate_point_tolerance(
    model: YOLO,
    split: str,
    confidence: float,
    dataset_root: Path, device: str,
) -> dict[int, MatchCounts]:
    """Evaluate point classes using the requested 3%-diagonal center tolerance."""
    image_directory = dataset_root / "images" / split
    label_directory = dataset_root / "labels" / split
    totals = {class_id: MatchCounts() for class_id in POINT_CLASS_NAMES}

    image_paths = sorted(
        path
        for path in image_directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    results = model.predict(
        source=[str(path) for path in image_paths],
        imgsz=768,
        conf=confidence,
        device=device,
        save=False,
        verbose=False,
        stream=True,
    )

    for image_path, result in zip(image_paths, results):
        ground_truth = read_point_ground_truth(
            label_directory / f"{image_path.stem}.txt"
        )
        predictions = {class_id: [] for class_id in POINT_CLASS_NAMES}
        if result.boxes is not None:
            xywh = result.boxes.xywh.cpu().tolist()
            classes = result.boxes.cls.cpu().tolist()
            confidences = result.boxes.conf.cpu().tolist()
            for box, class_value, score in zip(xywh, classes, confidences):
                class_id = int(class_value)
                if class_id in predictions:
                    predictions[class_id].append((box[0], box[1], score))

        for class_id in POINT_CLASS_NAMES:
            counts = greedy_tolerance_match(
                ground_truth[class_id],
                predictions[class_id],
                DISTANCE_TOLERANCE_PIXELS,
            )
            totals[class_id].true_positive += counts.true_positive
            totals[class_id].false_positive += counts.false_positive
            totals[class_id].false_negative += counts.false_negative
    return totals


def print_standard_metrics(split: str, metrics: object) -> None:
    """Print aggregate Ultralytics detection metrics."""
    box = metrics.box
    print(f"\n===== {split.upper()} STANDARD YOLO METRICS =====")
    print(f"Precision: {float(box.mp):.6f}")
    print(f"Recall:    {float(box.mr):.6f}")
    print(f"mAP50:     {float(box.map50):.6f}")
    print(f"mAP50-95:  {float(box.map):.6f}")


def print_point_metrics(split: str, totals: dict[int, MatchCounts]) -> None:
    """Print custom tolerance-based metrics for both point classes."""
    print(f"\n===== {split.upper()} POINT-CENTER TOLERANCE METRICS =====")
    print(
        "Correct match rule: center distance < "
        f"{DISTANCE_TOLERANCE_PIXELS:.2f} pixels "
        f"({DISTANCE_TOLERANCE_RATIO:.0%} of the 1280x720 image diagonal)."
    )
    for class_id, class_name in POINT_CLASS_NAMES.items():
        counts = totals[class_id]
        print(
            f"{class_name}: precision={counts.precision:.6f}, "
            f"recall={counts.recall:.6f}, TP={counts.true_positive}, "
            f"FP={counts.false_positive}, FN={counts.false_negative}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the YOLO11s baseline on val and offline test splits."
    )
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--device", default="0", help="CUDA device ID or cpu.")
    parser.add_argument("--data", type=Path, required=True, help="YOLO dataset YAML with an absolute path field.")
    parser.add_argument("--dataset-root", type=Path, default=DATASET_ROOT)
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold for custom point-tolerance evaluation.",
    )
    args = parser.parse_args()

    if not args.weights.is_file():
        raise FileNotFoundError(f"Model weights not found: {args.weights}")

    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    for split in ("val", "test"):
        metrics = model.val(
            data=str(args.data.resolve()),
            split=split,
            imgsz=768,
            batch=8,
            device=args.device,
            project=str(PROJECT_ROOT / "runs/evaluation"),
            name=split,
            exist_ok=True,
            plots=True,
            verbose=True,
        )
        print_standard_metrics(split, metrics)
        point_totals = evaluate_point_tolerance(model, split, args.conf, args.dataset_root.resolve(), args.device)
        print_point_metrics(split, point_totals)


if __name__ == "__main__":
    main()
