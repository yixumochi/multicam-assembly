from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def iou_xyxy(a: Iterable[float], b: Iterable[float]) -> float:
    ax1, ay1, ax2, ay2 = [float(v) for v in a]
    bx1, by1, bx2, by2 = [float(v) for v in b]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    track_id: int
    cls: int
    box: list[float]
    score: float
    age: int = 0


class ByteTrackLite:
    """Small dependency-free tracker for web demos when full ByteTrack is unavailable."""

    def __init__(self, track_thresh: float = 0.35, match_thresh: float = 0.90, track_buffer: int = 40):
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self.next_id = 1
        self.tracks: list[Track] = []

    def update(self, detections: list[dict]) -> list[dict]:
        detections = [d for d in detections if d["score"] >= self.track_thresh]
        for t in self.tracks:
            t.age += 1

        used = set()
        for det in detections:
            best_iou = 0.0
            best_track = None
            for trk in self.tracks:
                if trk.cls != det["cls"] or trk.track_id in used:
                    continue
                value = iou_xyxy(trk.box, det["box"])
                if value > best_iou:
                    best_iou = value
                    best_track = trk
            if best_track is not None and best_iou >= self.match_thresh:
                best_track.box = det["box"]
                best_track.score = det["score"]
                best_track.age = 0
                det["track_id"] = best_track.track_id
                used.add(best_track.track_id)
            else:
                det["track_id"] = self.next_id
                self.tracks.append(Track(self.next_id, det["cls"], det["box"], det["score"], 0))
                self.next_id += 1

        self.tracks = [t for t in self.tracks if t.age <= self.track_buffer]
        active_ids = {d["track_id"] for d in detections}
        output = detections[:]
        for trk in self.tracks:
            if trk.track_id not in active_ids and trk.age <= self.track_buffer:
                output.append({"track_id": trk.track_id, "cls": trk.cls, "box": trk.box, "score": trk.score, "lost": True})
        return output
