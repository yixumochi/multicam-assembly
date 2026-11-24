"""YOLO-format box-size K-means diagnostic for the anchor-free YOLO11 detector."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    """Read clustering options."""
    parser = argparse.ArgumentParser(description="Cluster YOLO width-height values with IoU distance.")
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
    )
    parser.add_argument("--imgsz", type=int, default=768)
    parser.add_argument("--clusters", type=int, default=9)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("kmeans_anchors_768.txt"),
    )
    return parser.parse_args()


def load_dataset(yaml_path: Path) -> tuple[Path, object]:
    """Resolve the dataset root and training split."""
    import yaml

    config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    root = Path(config.get("path", yaml_path.parent))
    if not root.is_absolute():
        root = (yaml_path.parent / root).resolve()
    return root, config["train"]


def iter_images(root: Path, train_entry: object) -> Iterable[Path]:
    """Yield images from split directories or text manifests."""
    entries = train_entry if isinstance(train_entry, list) else [train_entry]
    for entry in entries:
        source = Path(entry)
        if not source.is_absolute():
            source = root / source
        if source.is_dir():
            for image_path in sorted(source.rglob("*")):
                if image_path.suffix.lower() in IMAGE_SUFFIXES:
                    yield image_path
        elif source.is_file() and source.suffix.lower() == ".txt":
            for line in source.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    image_path = Path(line)
                    yield image_path if image_path.is_absolute() else root / image_path
        else:
            raise FileNotFoundError(f"Training source not found: {source}")


def label_path_for(image_path: Path) -> Path:
    """Map images/.../name.ext to labels/.../name.txt."""
    parts = list(image_path.parts)
    indices = [index for index, part in enumerate(parts) if part == "images"]
    if not indices:
        raise ValueError(f"Image path has no images directory: {image_path}")
    parts[indices[-1]] = "labels"
    return Path(*parts).with_suffix(".txt")


def collect_dimensions(image_paths: Iterable[Path], imgsz: int) -> np.ndarray:
    """Collect letterbox-scaled width-height pairs from YOLO labels."""
    import cv2
    import numpy as np

    dimensions = []
    image_count = 0
    for image_path in image_paths:
        image_count += 1
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"OpenCV could not read: {image_path}")
        height, width = image.shape[:2]
        gain = min(imgsz / width, imgsz / height)
        label_path = label_path_for(image_path)
        if not label_path.is_file():
            continue
        for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
            fields = line.split()
            if len(fields) < 5:
                raise ValueError(f"Invalid label at {label_path}:{line_number}")
            box_width = float(fields[3])
            box_height = float(fields[4])
            if box_width > 0 and box_height > 0:
                dimensions.append([box_width * width * gain, box_height * height * gain])
    if image_count == 0:
        raise RuntimeError("No training images were found.")
    if not dimensions:
        raise RuntimeError("No valid boxes were found.")
    return np.asarray(dimensions, dtype=np.float32)


def wh_iou(boxes: np.ndarray, clusters: np.ndarray) -> np.ndarray:
    """Compute origin-aligned width-height IoU."""
    import numpy as np

    intersection = np.minimum(boxes[:, None, 0], clusters[None, :, 0]) * np.minimum(
        boxes[:, None, 1], clusters[None, :, 1]
    )
    box_area = boxes[:, None, 0] * boxes[:, None, 1]
    cluster_area = clusters[None, :, 0] * clusters[None, :, 1]
    return intersection / np.maximum(box_area + cluster_area - intersection, 1e-9)


def cluster_boxes(boxes: np.ndarray, cluster_count: int, seed: int) -> np.ndarray:
    """Run median-centroid K-means using one minus IoU distance."""
    import numpy as np

    if len(boxes) < cluster_count:
        raise ValueError(f"Only {len(boxes)} boxes are available for {cluster_count} clusters.")
    rng = np.random.default_rng(seed)
    clusters = boxes[rng.choice(len(boxes), size=cluster_count, replace=False)].copy()
    previous = np.full(len(boxes), -1, dtype=np.int64)
    for _ in range(1000):
        assignments = (1.0 - wh_iou(boxes, clusters)).argmin(axis=1)
        if np.array_equal(assignments, previous):
            break
        for index in range(cluster_count):
            members = boxes[assignments == index]
            if len(members):
                clusters[index] = np.median(members, axis=0)
        previous = assignments
    return clusters[np.argsort(clusters[:, 0] * clusters[:, 1])]


def main() -> None:
    """Write the diagnostic report without changing any detector configuration."""
    args = parse_args()
    root, train_entry = load_dataset(args.data.resolve())
    boxes = collect_dimensions(iter_images(root, train_entry), args.imgsz)
    clusters = cluster_boxes(boxes, args.clusters, args.seed)
    mean_best_iou = wh_iou(boxes, clusters).max(axis=1).mean()
    report = [
        "# Width-height K-means diagnostic",
        f"# imgsz={args.imgsz}, boxes={len(boxes)}, clusters={args.clusters}, seed={args.seed}",
        f"# mean_best_iou={mean_best_iou:.6f}",
        "# YOLO11 Detect is anchor-free. These values are not injected into the Detect head.",
        "clusters_px=" + ", ".join(f"{width:.2f},{height:.2f}" for width, height in clusters),
    ]
    args.output.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"Saved report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
