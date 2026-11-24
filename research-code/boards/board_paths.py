"""Filesystem locations shared by the observation-board scripts."""

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def configured_path(key, default):
    value = os.environ.get(key)
    return Path(value).expanduser().resolve() if value else default


WORK = configured_path("MULTICAM_BOARD_WORK", ROOT / "work")
OUTPUTS = configured_path("MULTICAM_BOARD_OUTPUTS", ROOT / "outputs")
EVENTS = configured_path("MULTICAM_BOARD_EVENTS", WORK / "events.json")
EVIDENCE = configured_path("MULTICAM_BOARD_EVIDENCE", WORK)
V04_VIDEO = configured_path("MULTICAM_BOARD_V04_VIDEO", WORK / "videos" / "v04.mp4")


def font_path(bold=False):
    key = "MULTICAM_BOARD_FONT_BOLD" if bold else "MULTICAM_BOARD_FONT_REGULAR"
    filename = "bold.ttf" if bold else "regular.ttf"
    path = configured_path(key, WORK / "fonts" / filename)
    if not path.is_file():
        raise FileNotFoundError(f"Set {key} to a TrueType font or place it at {path}")
    return str(path)
