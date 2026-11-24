"""Offline three-channel color CLAHE enhancement with unchanged dataset annotations."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    """Read source, destination, and CLAHE parameters."""
    parser = argparse.ArgumentParser(description="Enhance color-image luminance with offline CLAHE.")
    parser.add_argument("--source", type=Path, required=True, help="Input dataset root.")
    parser.add_argument(
        "--destination",
        type=Path,
        required=True,
        help="Enhanced dataset root.",
    )
    parser.add_argument("--clip-limit", type=float, default=2.0, help="CLAHE clipping limit.")
    parser.add_argument("--tile-grid", type=int, default=8, help="Square CLAHE tile count.")
    parser.add_argument("--overwrite", action="store_true", help="Allow an existing non-empty destination.")
    return parser.parse_args()


def enhance_color_image(source: Path, destination: Path, clahe: cv2.CLAHE) -> None:
    """Apply CLAHE to LAB luminance and preserve a normal three-channel color output."""
    import cv2

    image_bgr = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise ValueError(f"OpenCV could not read: {source}")
    image_lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    luminance, channel_a, channel_b = cv2.split(image_lab)
    enhanced_luminance = clahe.apply(luminance)
    enhanced_lab = cv2.merge((enhanced_luminance, channel_a, channel_b))
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), enhanced_bgr):
        raise IOError(f"OpenCV could not write: {destination}")


def main() -> None:
    """Enhance split-tree images and copy every annotation or metadata file unchanged."""
    args = parse_args()
    source_root = args.source.resolve()
    destination_root = args.destination.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Dataset root does not exist: {source_root}")
    if destination_root.is_relative_to(source_root) or source_root.is_relative_to(destination_root):
        raise ValueError("The source and destination folders must be separate.")
    if destination_root.exists() and any(destination_root.iterdir()) and not args.overwrite:
        raise FileExistsError(f"Destination is not empty: {destination_root}")
    import cv2

    clahe = cv2.createCLAHE(
        clipLimit=args.clip_limit,
        tileGridSize=(args.tile_grid, args.tile_grid),
    )
    image_count = 0
    copied_file_count = 0
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(source_root)
        destination_path = destination_root / relative_path
        if relative_path.parts[0] in {"train", "val", "test"} and source_path.suffix.lower() in IMAGE_SUFFIXES:
            enhance_color_image(source_path, destination_path, clahe)
            image_count += 1
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            copied_file_count += 1
    print(f"Enhanced color images: {image_count}")
    print(f"Copied unchanged annotations and metadata: {copied_file_count}")
    print(f"Output dataset: {destination_root}")


if __name__ == "__main__":
    main()
