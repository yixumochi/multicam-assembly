"""Train YOLO11s with one preprocessing or training change per run."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parent
MODEL_YAML = ROOT / "yolov11s_ablation.yaml"
DATASET_FOLDERS = {
    "pre0_baseline": "split_pre0_baseline",
    "pre1_median": "split_pre1_median",
    "pre2_tophat": "split_pre2_tophat",
    "pre3_fusion": "split_pre3_fusion",
    "pre4_resize": "split_pre4_resize",
    "pre5_all_combined": "split_pre5_all_combined",
}
CLASS_NAMES = {
    0: "female_interface",
    1: "male_connector",
    2: "movable_part",
    3: "assembled_structure",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True, help="Trusted local YOLO11s checkpoint.")
    parser.add_argument("--data-root", type=Path, required=True, help="Parent of all preprocessed dataset versions.")
    parser.add_argument("--experiment", choices=(*DATASET_FOLDERS, "light_aug", "focal_loss"), default="pre0_baseline")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "ablation")
    parser.add_argument("--device", default="0", help="CUDA device ID or cpu.")
    parser.add_argument("--ultralytics-source", type=Path, help="Optional source directory for the original editable fork.")
    return parser.parse_args()


def validate_dataset(dataset: Path) -> None:
    for kind in ("images", "labels"):
        for split in ("train", "val", "test"):
            directory = dataset / kind / split
            if not directory.is_dir():
                raise FileNotFoundError(f"YOLO split is missing: {directory}. Run the LabelMe converter first.")


def write_dataset_config(dataset: Path, output: Path, experiment: str) -> Path:
    import yaml

    directory = output / "dataset-configs"
    directory.mkdir(parents=True, exist_ok=True)
    config = {
        "path": str(dataset),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": CLASS_NAMES,
    }
    # Keep the exact input configuration for each run without overwriting a prior run.
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=f"{experiment}-",
        suffix=".yaml", dir=directory, delete=False,
    ) as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
        return Path(handle.name)


def enable_focal_classification_loss() -> None:
    from ultralytics.nn.tasks import DetectionModel
    from ultralytics.utils.loss import FocalLoss, v8DetectionLoss

    def focal_criterion(self):
        criterion = v8DetectionLoss(self)
        criterion.bce = FocalLoss(gamma=1.5, alpha=0.25)
        return criterion

    DetectionModel.init_criterion = focal_criterion


def training_options(experiment: str, config: Path, output: Path, device: str) -> dict:
    light = experiment == "light_aug"
    return {
        "data": str(config),
        "imgsz": 768,
        "epochs": 200,
        "batch": 8,
        "workers": 8,
        "device": device,
        "project": str(output),
        "name": experiment,
        "pretrained": False,
        "resume": False,
        "seed": 42,
        "deterministic": True,
        "degrees": 0.0,
        "shear": 0.0,
        "mosaic": 0.0,
        "mixup": 0.0,
        "perspective": 0.0,
        "flipud": 0.0,
        "hsv_h": 0.0,
        "hsv_s": 0.0,
        "copy_paste": 0.0,
        "cutmix": 0.0,
        "fliplr": 0.5 if light else 0.0,
        "translate": 0.12 if light else 0.0,
        "scale": 0.10 if light else 0.0,
        "hsv_v": 0.15 if light else 0.0,
    }


def main() -> None:
    args = parse_args()
    weights = args.weights.resolve()
    if not weights.is_file():
        raise FileNotFoundError(f"Local model checkpoint is missing: {weights}")
    variant = DATASET_FOLDERS.get(args.experiment, DATASET_FOLDERS["pre0_baseline"])
    dataset = args.data_root.resolve() / variant / "YOLO_Data"
    validate_dataset(dataset)

    os.environ["YOLO_AUTOINSTALL"] = "False"
    os.environ["YOLO_OFFLINE"] = "True"
    if args.ultralytics_source:
        source = args.ultralytics_source.resolve()
        if not (source / "ultralytics" / "__init__.py").is_file():
            raise FileNotFoundError(f"Expected an ultralytics package in {source}")
        sys.path.insert(0, str(source))

    import ultralytics
    from ultralytics.utils import checks

    if args.ultralytics_source and not Path(ultralytics.__file__).resolve().is_relative_to(source):
        raise RuntimeError(f"The supplied editable source was not imported: {source}")
    checks.check_pip_update_available = lambda: False

    if args.experiment == "focal_loss":
        enable_focal_classification_loss()

    output = args.output.resolve()
    config = write_dataset_config(dataset, output, args.experiment)
    model = ultralytics.YOLO(str(MODEL_YAML), task="detect", verbose=True)
    model.load(str(weights))
    model.train(**training_options(args.experiment, config, output, args.device))


if __name__ == "__main__":
    main()
