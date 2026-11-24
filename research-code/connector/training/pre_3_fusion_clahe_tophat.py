"""Single-variable variant: fuse baseline CLAHE and color TopHat outputs."""

# ==================== STEP 1: IMPORT REQUIRED LOCAL LIBRARIES ====================
import argparse
from pathlib import Path
import shutil

import numpy as np

# ==================== STEP 3: KEEP BASELINE AND TOPHAT SETTINGS FIXED ====================
GAUSSIAN_KERNEL = (5, 5)
GAUSSIAN_SIGMA = 0
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)
TOPHAT_KERNEL_SIZE = 9
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}

# ==================== STEP 4: EXPOSE ONLY THE REQUESTED FUSION PARAMETERS ====================
# Alpha controls the contribution from the baseline CLAHE image.
FUSION_ALPHA = 1.0
# Beta controls the contribution from the TopHat image.
FUSION_BETA = 0.5
# Gamma adds a constant output brightness offset.
FUSION_GAMMA = 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="Source split dataset.")
    parser.add_argument("--output-root", type=Path, required=True, help="Separate preprocessing output folder.")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.is_relative_to(source_root) or source_root.is_relative_to(output_root):
        parser.error("The source and output folders must be separate.")

    import cv2

    if not source_root.is_dir():
        raise FileNotFoundError(f"Source dataset does not exist: {source_root}")

    # ==================== STEP 6: CREATE REUSABLE PROCESSING OBJECTS ====================
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    tophat_kernel = np.ones((TOPHAT_KERNEL_SIZE, TOPHAT_KERNEL_SIZE), dtype=np.uint8)

    # ==================== STEP 7: PROCESS IMAGES AND COPY ALL OTHER FILES ====================
    processed_images = 0
    copied_files = 0

    for source_path in sorted(source_root.rglob("*")):
        # Skip directories.
        if not source_path.is_file():
            continue

        # Preserve every source-relative dataset path.
        relative_path = source_path.relative_to(source_root)
        output_path = output_root / relative_path

        # Process every image found under the train, val, or test split tree.
        if relative_path.parts[0] in {"train", "val", "test"} and source_path.suffix.lower() in IMAGE_SUFFIXES:
            # Load the source as a normal color image.
            image_bgr = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
            if image_bgr is None:
                raise ValueError(f"OpenCV could not read image: {source_path}")

            # Run the baseline Gaussian operation.
            blurred_bgr = cv2.GaussianBlur(image_bgr, GAUSSIAN_KERNEL, GAUSSIAN_SIGMA)

            # Run the baseline LAB CLAHE operation.
            blurred_lab = cv2.cvtColor(blurred_bgr, cv2.COLOR_BGR2LAB)
            luminance, channel_a, channel_b = cv2.split(blurred_lab)
            enhanced_luminance = clahe.apply(luminance)
            enhanced_lab = cv2.merge((enhanced_luminance, channel_a, channel_b))
            enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

            # Produce the same standalone color TopHat component as the TopHat experiment.
            tophat_bgr = cv2.morphologyEx(enhanced_bgr, cv2.MORPH_TOPHAT, tophat_kernel)

            # Add the single experimental weighted-fusion operation.
            output_bgr = cv2.addWeighted(
                enhanced_bgr,
                FUSION_ALPHA,
                tophat_bgr,
                FUSION_BETA,
                FUSION_GAMMA,
            )

            # Save the fused color image.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(output_path), output_bgr):
                raise IOError(f"OpenCV could not write image: {output_path}")
            processed_images += 1
        else:
            # Copy labels and metadata unchanged.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, output_path)
            copied_files += 1

    # ==================== STEP 8: PRINT A CLEAR COMPLETION REPORT ====================
    print(f"Fusion-variant images processed: {processed_images}")
    print(f"Unchanged dataset files copied: {copied_files}")
    print(f"Fusion alpha/beta/gamma: {FUSION_ALPHA}/{FUSION_BETA}/{FUSION_GAMMA}")
    print(f"Output dataset: {output_root}")


if __name__ == "__main__":
    main()
