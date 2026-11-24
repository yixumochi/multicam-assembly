"""Class-aware wrapper around the local Ultralytics BYTETracker implementation."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker


TRACKED_CLASSES = (0, 1, 2, 3)


class ClassAwareByteTrack:
    """Maintain one official ByteTrack instance per class to prevent cross-class ID swaps."""

    def __init__(self, frame_rate: int) -> None:
        # In Ultralytics, match_thresh is a maximum matching *cost* (1 - IoU),
        # not a direct IoU threshold. 0.90 would allow IoU as low as roughly 0.10.
        # 0.75 is a safer starting point for tiny boxes; verify it on the six videos.
        args = SimpleNamespace(
            track_high_thresh=0.35,
            track_low_thresh=0.12,
            new_track_thresh=0.50,
            track_buffer=40,
            match_thresh=0.75,
            fuse_score=True,
        )
        self.trackers = {class_id: BYTETracker(args, frame_rate=frame_rate) for class_id in TRACKED_CLASSES}

    def update(self, boxes, frame: np.ndarray) -> list[dict]:
        if boxes is None:
            return []
        boxes_np = boxes.cpu().numpy()
        output: list[dict] = []
        for class_id, tracker in self.trackers.items():
            class_boxes = boxes_np[boxes_np.cls.astype(int) == class_id]
            tracks = tracker.update(class_boxes, frame)
            for item in tracks:
                # Ultralytics BYTETracker result layout:
                # [x1, y1, x2, y2, track_id, score, cls, detection_index]
                output.append({
                    "xyxy": [float(v) for v in item[:4]],
                    "track_id": int(item[4]),
                    "score": float(item[5]),
                    "cls": int(item[6]),
                    "visible": True,
                })
        return output
