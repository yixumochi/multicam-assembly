#!/usr/bin/env python3
"""Train an unmodified YOLO11s 4-class detection baseline."""

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIRECTORY = PROJECT_ROOT / "runs"


def main() -> None:
    """Train the official YOLO11s model without architectural modifications."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True, help="Local YOLO11s checkpoint.")
    parser.add_argument("--data", type=Path, required=True, help="YOLO dataset YAML with an absolute path field.")
    parser.add_argument("--device", default="0", help="CUDA device ID or cpu.")
    args = parser.parse_args()
    if not args.weights.is_file():
        raise FileNotFoundError(f"Missing model checkpoint: {args.weights}")

    from ultralytics import YOLO

    model = YOLO(str(args.weights))

    model.train(
        data=str(args.data.resolve()),
        imgsz=768,
        batch=8,
        epochs=120,
        patience=30,
        cache=True,
        device=args.device,
        workers=8,
        project=str(RUNS_DIRECTORY),
        name="baseline_yolo11s",
        exist_ok=True,
        seed=42,
        deterministic=True,
        # Disable mosaic, mixup, copy-paste, and geometric/color augmentation.
        # This creates a clean baseline before any semi-supervised or
        # architecture-modification experiments are introduced.
        mosaic=0.0,
        mixup=0.0,
        copy_paste=0.0,
        degrees=0.0,
        translate=0.0,
        scale=0.0,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.0,
        hsv_h=0.0,
        hsv_s=0.0,
        hsv_v=0.0,
        erasing=0.0,
        plots=True,
        val=True,
        verbose=True,
    )


if __name__ == "__main__":
    main()
