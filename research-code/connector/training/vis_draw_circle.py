"""Read-only YOLO-label visualization that draws circles around tiny targets."""

# ==================== STEP 1: IMPORT REQUIRED LOCAL LIBRARIES ====================
import argparse
from pathlib import Path

# ==================== STEP 2: KEEP THE REQUIRED FIXED READ-ONLY DATASET PATH ====================

# ==================== STEP 3: CONFIGURE PREVIEW OUTPUT WITHOUT MODIFYING THE DATASET ====================
CIRCLE_COLOR_BGR = (0, 0, 255)
CIRCLE_THICKNESS = 2
MIN_CIRCLE_RADIUS = 5
RADIUS_SCALE = 0.75
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--preview-root", type=Path, required=True)
    args = parser.parse_args()
    dataset_root = args.dataset_root.resolve()
    preview_root = args.preview_root.resolve()
    if preview_root.is_relative_to(dataset_root) or dataset_root.is_relative_to(preview_root):
        parser.error("The dataset and preview folders must be separate.")

    import cv2

    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Visualization dataset does not exist: {dataset_root}")

    # ==================== STEP 5: FIND AND VISUALIZE EVERY LABELED IMAGE ====================
    visualized_images = 0
    drawn_targets = 0

    for image_path in sorted(dataset_root.rglob("*")):
        # Skip directories and unsupported files.
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        # Process only files located under an images directory.
        relative_path = image_path.relative_to(dataset_root)
        if "images" not in relative_path.parts:
            continue

        # Build the matching labels path without changing the source dataset.
        label_parts = list(relative_path.parts)
        image_directory_index = label_parts.index("images")
        label_parts[image_directory_index] = "labels"
        label_path = (dataset_root / Path(*label_parts)).with_suffix(".txt")

        # Skip images without a label file because there is no target to mark.
        if not label_path.is_file():
            continue

        # Load the source as a normal three-channel color image.
        preview_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if preview_bgr is None:
            raise ValueError(f"OpenCV could not read image: {image_path}")

        # Read the current image dimensions for YOLO-coordinate conversion.
        image_height, image_width = preview_bgr.shape[:2]

        # Parse each YOLO label line as class, center-x, center-y, width, and height.
        for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
            fields = line.split()
            if len(fields) < 5:
                raise ValueError(f"Invalid YOLO label at {label_path}:{line_number}")

            # Convert normalized target center coordinates to image pixels.
            center_x = int(round(float(fields[1]) * image_width))
            center_y = int(round(float(fields[2]) * image_height))

            # Convert normalized target dimensions to image pixels.
            target_width = float(fields[3]) * image_width
            target_height = float(fields[4]) * image_height

            # Choose a visible circle radius from the larger target dimension.
            circle_radius = max(
                MIN_CIRCLE_RADIUS,
                int(round(max(target_width, target_height) * RADIUS_SCALE)),
            )

            # Draw the requested target-point circle on the preview copy.
            cv2.circle(
                preview_bgr,
                (center_x, center_y),
                circle_radius,
                CIRCLE_COLOR_BGR,
                CIRCLE_THICKNESS,
                lineType=cv2.LINE_AA,
            )
            drawn_targets += 1

        # Store previews separately so source images and labels remain untouched.
        preview_relative_path = Path(*relative_path.parts[image_directory_index + 1 :])
        preview_path = preview_root / preview_relative_path
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(preview_path), preview_bgr):
            raise IOError(f"OpenCV could not write preview: {preview_path}")
        visualized_images += 1

    # ==================== STEP 6: PRINT A CLEAR COMPLETION REPORT ====================
    print(f"Images visualized: {visualized_images}")
    print(f"Target circles drawn: {drawn_targets}")
    print(f"Preview folder: {preview_root}")


if __name__ == "__main__":
    main()
