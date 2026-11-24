"""Conservative, explainable state machine for a 2-D connector video demo."""

from __future__ import annotations

from collections import deque


IDLE = "IDLE"
ASSEMBLING = "ASSEMBLING"
ASSEMBLED = "ASSEMBLED"
DISASSEMBLING = "DISASSEMBLING"


class ConnectorFSM:
    """Use smoothed pair distance and persistent assembled evidence, not a single frame."""

    def __init__(self, frame_rate: float, smoothing: float = 0.25, assembled_max_distance_px: float = 120.0) -> None:
        self.frame_rate = frame_rate
        self.smoothing = smoothing
        self.assembled_max_distance_px = assembled_max_distance_px
        self.state = IDLE
        self.smoothed_distance: float | None = None
        self.history: deque[float] = deque(maxlen=max(4, round(frame_rate * 0.25)))
        self.missing_frames = 0
        self.max_hold_frames = max(3, round(frame_rate * 0.4))
        # These are initial per-video defaults. Tune only after reviewing CSV/video,
        # ideally per camera view, rather than treating them as physical distances.
        self.motion_px_per_frame = 0.6

    def update(self, distance_px: float | None, male: dict | None, female: dict | None, assembled_confirmed: bool) -> str:
        if distance_px is None or male is None or female is None:
            self.missing_frames += 1
            # Preserve the last state for short occlusions; one missed tiny box must
            # not turn a completed assembly back into IDLE.
            if self.missing_frames > self.max_hold_frames and self.state != ASSEMBLED:
                self.state = IDLE
            return self.state

        self.missing_frames = 0
        self.smoothed_distance = distance_px if self.smoothed_distance is None else (
            self.smoothing * distance_px + (1.0 - self.smoothing) * self.smoothed_distance
        )
        self.history.append(self.smoothed_distance)
        slope = 0.0 if len(self.history) < 2 else (self.history[-1] - self.history[0]) / (len(self.history) - 1)

        if assembled_confirmed and self.smoothed_distance <= self.assembled_max_distance_px:
            self.state = ASSEMBLED
        elif self.state == ASSEMBLED and self.smoothed_distance > self.assembled_max_distance_px:
            self.state = DISASSEMBLING if slope > 0 else IDLE
        elif self.state == ASSEMBLED and slope > self.motion_px_per_frame:
            self.state = DISASSEMBLING
        elif slope < -self.motion_px_per_frame:
            self.state = ASSEMBLING
        elif self.state in {ASSEMBLING, DISASSEMBLING} and abs(slope) < self.motion_px_per_frame * 0.35:
            self.state = IDLE
        return self.state
