"""Single-variable variant: replace baseline Gaussian blur with median blur."""

# ==================== STEP 1: IMPORT REQUIRED LOCAL LIBRARIES ====================
import argparse
from pathlib import Path
import shutil


# ==================== STEP 3: CHANGE ONLY THE DENOISING METHOD ====================
MEDIAN_KERNEL = 5
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


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

    # ==================== STEP 5: CREATE THE SAME CLAHE PROCESSOR AS THE BASELINE ====================
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)

    # ==================== STEP 6: PROCESS IMAGES AND COPY ALL OTHER FILES ====================
    processed_images = 0
    copied_files = 0

    for source_path in sorted(source_root.rglob("*")):
        # Skip directory entries.
        if not source_path.is_file():
            continue

        # Preserve the source dataset folder structure.
        relative_path = source_path.relative_to(source_root)
        output_path = output_root / relative_path

        # Process every image found under the train, val, or test split tree.
        if relative_path.parts[0] in {"train", "val", "test"} and source_path.suffix.lower() in IMAGE_SUFFIXES:
            # Load a normal three-channel color image.
            image_bgr = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
            if image_bgr is None:
                raise ValueError(f"OpenCV could not read image: {source_path}")

            # Replace only Gaussian denoising with median denoising.
            blurred_bgr = cv2.medianBlur(image_bgr, MEDIAN_KERNEL)

            # Keep the remaining LAB CLAHE flow identical to the baseline.
            blurred_lab = cv2.cvtColor(blurred_bgr, cv2.COLOR_BGR2LAB)
            luminance, channel_a, channel_b = cv2.split(blurred_lab)
            enhanced_luminance = clahe.apply(luminance)
            enhanced_lab = cv2.merge((enhanced_luminance, channel_a, channel_b))
            output_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

            # Create the destination directory and save the result.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(output_path), output_bgr):
                raise IOError(f"OpenCV could not write image: {output_path}")
            processed_images += 1
        else:
            # Copy every label and metadata file unchanged.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, output_path)
            copied_files += 1

    # ==================== STEP 7: PRINT A CLEAR COMPLETION REPORT ====================
    print(f"Median-variant images processed: {processed_images}")
    print(f"Unchanged dataset files copied: {copied_files}")
    print(f"Output dataset: {output_root}")


if __name__ == "__main__":
    main()
