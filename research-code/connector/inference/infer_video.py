"""Batch connector-video inference for the low-cost industrial visual-guidance demo.

This is deliberately an inference-only program. It uses the archived aligned300
slow-stage2 checkpoint, class-aware official ByteTrack, geometry, and a small FSM.
It does not control a robot; it creates annotated MP4 files and auditable CSV data
for the website demonstration.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path



ROOT = Path(__file__).resolve().parent
CLASS_NAMES = {0: "female_interface", 1: "male_connector", 2: "movable_part", 3: "assembled_structure"}
CLASS_SHORT = {0: "F", 1: "M", 2: "P", 3: "A"}
COLORS = {0: (255, 120, 120), 1: (120, 220, 255), 2: (120, 255, 120), 3: (255, 220, 80)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLOv11 + class-aware ByteTrack + ConnectorFSM batch inference")
    parser.add_argument("--weights", type=Path, required=True, help="Local detector checkpoint.")
    parser.add_argument("--input", type=Path, required=True, help="Video file or input directory.")
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    parser.add_argument("--device", default="0", help="CUDA device id, e.g. 0; use cpu when needed")
    parser.add_argument("--imgsz", type=int, default=768)
    # YOLO must emit low-confidence boxes for ByteTrack's second association.
    parser.add_argument("--det-conf", type=float, default=0.12)
    parser.add_argument("--nms-iou", type=float, default=0.60)
    parser.add_argument("--roi-top-ratio", type=float, default=0.42, help="Ignore detections whose center is above this image-height ratio; set 0 to disable")
    parser.add_argument("--max-pair-distance", type=float, default=140.0, help="Reject male/female pairs farther than this many pixels; set 0 to disable")
    parser.add_argument("--assembled-max-distance", type=float, default=120.0, help="ASSEMBLED requires a confirmed assembled box and a pair distance below this threshold")
    parser.add_argument("--max-videos", type=int, default=0, help="0 means process every video")
    return parser.parse_args()


def iter_videos(path: Path) -> list[Path]:
    extensions = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}
    if path.is_file() and path.suffix.lower() in extensions:
        return [path]
    return sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in extensions)


def draw_track(frame, track: dict) -> None:
    import cv2

    x1, y1, x2, y2 = [int(v) for v in track["xyxy"]]
    cls = track["cls"]
    color = COLORS.get(cls, (220, 220, 220))
    label = f"{CLASS_SHORT.get(cls, '?')}-{track['track_id']} {track['score']:.2f}"
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2, cv2.LINE_AA)


def in_workbench_roi(track: dict, frame_height: int, roi_top_ratio: float) -> bool:
    """Keep demo geometry focused on the lower workbench area.

    The lab background can produce tiny false male/female boxes on the wall,
    shelves, or tools. Those are useful to see as detections during debugging,
    but they should not drive pair geometry or FSM state.
    """
    if roi_top_ratio <= 0:
        return True
    _, center_y = box_center_xyxy(track["xyxy"])
    return center_y >= frame_height * roi_top_ratio


def process_video(model: YOLO, video_path: Path, output_dir: Path, args: argparse.Namespace) -> None:
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_dir.mkdir(parents=True, exist_ok=True)
    video_out = output_dir / f"{video_path.stem}_annotated.mp4"
    csv_out = output_dir / f"{video_path.stem}_track_data.csv"
    writer = cv2.VideoWriter(str(video_out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    # Separate trackers make matching class-aware. This is essential because the
    # upstream ByteTrack association itself uses IoU only and otherwise may match
    # a female detection to an existing male trajectory.
    from fsm.connector_fsm import ConnectorFSM
    from utils.class_aware_bytetrack import ClassAwareByteTrack
    from utils.geometry import PairLock, box_center_xyxy, closest_pair

    tracker = ClassAwareByteTrack(frame_rate=round(fps))
    fsm = ConnectorFSM(frame_rate=fps, assembled_max_distance_px=args.assembled_max_distance)
    pair_lock = PairLock(
        max_missing_frames=max(3, round(fps * 0.5)),
        max_pair_distance_px=None if args.max_pair_distance <= 0 else args.max_pair_distance,
    )
    assembled_streak = 0
    frame_index = 0
    output_rows: list[dict[str, object]] = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        result = model.predict(
            frame,
            conf=args.det_conf,
            iou=args.nms_iou,
            imgsz=args.imgsz,
            device=args.device,
            classes=list(CLASS_NAMES),
            verbose=False,
        )[0]
        tracks = tracker.update(result.boxes, frame)
        visible = [track for track in tracks if track["visible"]]
        geometry_tracks = [track for track in visible if in_workbench_roi(track, height, args.roi_top_ratio)]
        by_class: dict[int, list[dict]] = defaultdict(list)
        for track in geometry_tracks:
            by_class[track["cls"]].append(track)

        # A single assembled_structure detection is not enough to change state.
        # Require three adjacent frames to reject transient background false positives.
        assembled_now = bool(by_class[3])
        assembled_streak = assembled_streak + 1 if assembled_now else 0
        assembled_confirmed = assembled_streak >= 3

        max_pair_distance = None if args.max_pair_distance <= 0 else args.max_pair_distance
        male, female, distance_px, angle_deg = closest_pair(by_class[1], by_class[0], max_pair_distance_px=max_pair_distance)
        male, female = pair_lock.update(male, female, by_class[1], by_class[0])
        if male is not None and female is not None:
            male_center = box_center_xyxy(male["xyxy"])
            female_center = box_center_xyxy(female["xyxy"])
            # Recompute after pair-locking, not before it.
            dx, dy = female_center[0] - male_center[0], female_center[1] - male_center[1]
            distance_px = (dx * dx + dy * dy) ** 0.5
            angle_deg = math.degrees(math.atan2(dy, dx))

        state = fsm.update(distance_px, male, female, assembled_confirmed)

        for track in visible:
            draw_track(frame, track)
        if male is not None and female is not None:
            a = tuple(int(v) for v in box_center_xyxy(male["xyxy"]))
            b = tuple(int(v) for v in box_center_xyxy(female["xyxy"]))
            cv2.arrowedLine(frame, a, b, (0, 255, 255), 2, tipLength=0.12)

        info = f"FSM: {state} | frame {frame_index} | fps {fps:.1f}"
        cv2.putText(frame, info, (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2, cv2.LINE_AA)
        if distance_px is not None:
            cv2.putText(
                frame,
                f"pair distance={distance_px:.1f}px  angle={angle_deg:.1f} deg  smooth={fsm.smoothed_distance:.1f}px",
                (16, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2, cv2.LINE_AA,
            )

        output_rows.append({
            "video": video_path.name,
            "frame": frame_index,
            "time_sec": round(frame_index / fps, 4),
            "fsm_state": state,
            "female_track": "" if female is None else f"F-{female['track_id']}",
            "male_track": "" if male is None else f"M-{male['track_id']}",
            "distance_px": "" if distance_px is None else round(distance_px, 3),
            "smoothed_distance_px": "" if fsm.smoothed_distance is None else round(fsm.smoothed_distance, 3),
            "angle_image_plane_deg": "" if angle_deg is None else round(angle_deg, 3),
            "assembled_confirmed": int(assembled_confirmed),
            "visible_tracks": len(visible),
        })
        writer.write(frame)
        frame_index += 1

    cap.release()
    writer.release()
    with csv_out.open("w", encoding="utf-8", newline="") as file:
        fieldnames = list(output_rows[0]) if output_rows else ["video", "frame", "time_sec", "fsm_state"]
        writer_csv = csv.DictWriter(file, fieldnames=fieldnames)
        writer_csv.writeheader()
        writer_csv.writerows(output_rows)
    print(f"Saved annotated video: {video_out}")
    print(f"Saved timeline CSV:    {csv_out}")


def main() -> None:
    args = parse_args()
    if not args.weights.is_file():
        raise FileNotFoundError(f"Missing model weight: {args.weights}")
    videos = iter_videos(args.input)
    if not videos:
        raise FileNotFoundError(f"No video found under: {args.input}")
    if args.max_videos:
        videos = videos[: args.max_videos]
    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    for video in videos:
        print(f"\nProcessing {video.name}")
        process_video(model, video, args.output, args)


if __name__ == "__main__":
    main()
