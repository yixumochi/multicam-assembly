"""Pair-locking and image-plane geometry helpers for connector-video analysis."""

from __future__ import annotations

import math


def box_center_xyxy(box: list[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = [float(value) for value in box]
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def closest_pair(
    males: list[dict],
    females: list[dict],
    max_distance_px: float | None = None,
) -> tuple[dict | None, dict | None, float | None, float | None]:
    best = (None, None, None, None)
    best_distance = float("inf")
    for male in males:
        male_center = box_center_xyxy(male["xyxy"])
        for female in females:
            female_center = box_center_xyxy(female["xyxy"])
            dx, dy = female_center[0] - male_center[0], female_center[1] - male_center[1]
            distance = math.hypot(dx, dy)
            if max_distance_px is not None and distance > max_distance_px:
                continue
            if distance < best_distance:
                best_distance = distance
                best = (male, female, distance, math.degrees(math.atan2(dy, dx)))
    return best


class PairLock:
    """Keep a male/female pair stable instead of recomputing nearest-neighbour every frame."""

    def __init__(self, max_missing_frames: int, max_pair_distance_px: float | None = None) -> None:
        self.max_missing_frames = max_missing_frames
        self.max_pair_distance_px = max_pair_distance_px
        self.locked: tuple[int, int] | None = None
        self.missing_frames = 0

    def update(self, candidate_male: dict | None, candidate_female: dict | None, males: list[dict], females: list[dict]) -> tuple[dict | None, dict | None]:
        if self.locked is not None:
            male = next((item for item in males if item["track_id"] == self.locked[0]), None)
            female = next((item for item in females if item["track_id"] == self.locked[1]), None)
            if male is not None and female is not None:
                male_center = box_center_xyxy(male["xyxy"])
                female_center = box_center_xyxy(female["xyxy"])
                distance = math.hypot(female_center[0] - male_center[0], female_center[1] - male_center[1])
                if self.max_pair_distance_px is not None and distance > self.max_pair_distance_px:
                    self.locked = None
                    self.missing_frames = 0
                else:
                    self.missing_frames = 0
                    return male, female
            else:
                self.missing_frames += 1
                if self.missing_frames <= self.max_missing_frames:
                    return None, None
                self.locked = None
                self.missing_frames = 0

        if candidate_male is not None and candidate_female is not None:
            self.locked = (candidate_male["track_id"], candidate_female["track_id"])
        return candidate_male, candidate_female
