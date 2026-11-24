# Connector video inference and detector training

These are the project scripts behind the connector video demonstration. The inference engine reads video and writes annotated video and a frame-by-frame CSV. The training tools convert LabelMe annotations, preprocess images, train the four-class detector, and evaluate its predictions.

## Setup

Create a Python environment, then install dependencies from this directory.

```bash
python -m pip install -r requirements.txt
```

The default dependency is the upstream [Ultralytics 8.3.185](https://github.com/ultralytics/ultralytics/tree/v8.3.185) release. The original ablation environment used an editable fork. For a run that requires that environment, supply your local copy with `--ultralytics-source path/to/source`. The public scripts do not bundle the fork or guarantee identical results across versions. Supply your own authorized videos, annotations, and trusted model checkpoints.

## Read the inference code

1. `inference/infer_video.py` reads frames, runs the detector, and writes the video and CSV.
2. `inference/utils/class_aware_bytetrack.py` maintains separate trackers for each detection class.
3. `inference/utils/geometry.py` computes image-plane distance and angle for a connector pair.
4. `inference/fsm/connector_fsm.py` updates the reported assembly state.

```bash
python inference/infer_video.py --input path/to/video.mp4 --weights path/to/best.pt --output path/to/output --device cpu
```

The running thresholds are in `class_aware_bytetrack.py`. The YAML under `inference/trackers/` records a separate reference configuration. Distances are in image pixels and angles are projected into the image plane.

## Train and evaluate

From this directory, preprocess a split LabelMe dataset and convert its aligned image and annotation pairs into YOLO splits. The converter reads the `labeled_human/assembly` and `labeled_human/disassembly` subdirectories of each `train`, `val`, and `test` split. Each LabelMe JSON file shares its basename with the corresponding image. Pass the directory that holds each preprocessing variant to the trainer.

```bash
python training/pre_0_baseline.py --source-root path/to/split_data --output-root training/data/split_pre0_baseline
python training/json2yolo.py --source-root training/data/split_pre0_baseline --output-root training/data/split_pre0_baseline/YOLO_Data
python training/split_check.py --dataset-root training/data/split_pre0_baseline/YOLO_Data
python training/train_ablation.py --weights path/to/yolo11s.pt --data-root training/data --experiment pre0_baseline
```

The six preprocessing variants retain their original image-processing parameters. The light-augmentation and focal-loss experiments use the baseline dataset. A runtime YAML in the run output records the input split paths and the four connector class names.

For the standalone official-model baseline, give `train_baseline.py` a trusted checkpoint and a dataset YAML with an absolute `path` field. `val_test_eval.py` takes the same `--data` YAML and a matching `--dataset-root` for point-tolerance evaluation. `data.yaml` and `data_contrast.yaml` are starting configurations you can adapt to your files.

`batch_clahe_enhance.py` and `vis_draw_circle.py` write to separate folders. `kmeans_anchor.py` summarizes box sizes for inspection. `via_to_yolo.py` is a separate converter for the earlier three-class VIA annotations.
