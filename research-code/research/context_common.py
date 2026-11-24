"""Shared paths and record helpers for the context round. Read-only inputs."""
from __future__ import annotations

import hashlib
import json
import os
from functools import cache
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent


def local_path(variable: str, default: Path) -> Path:
    value = os.environ.get(variable)
    return (Path(value) if value else default).expanduser().resolve()


PACKAGE = local_path("MULTICAM_DATA_ROOT", RESEARCH / "data")
PROJECT = PACKAGE / "project"
OUT = PROJECT / "outputs" / "grok_context_round1"
BASELINE = local_path("MULTICAM_BASELINE_ROOT", PACKAGE / "baseline")
EVIDENCE = local_path("MULTICAM_EVIDENCE_TEXT", PACKAGE / "inputs" / "historical_evidence.json")
FRAMES = PROJECT / "outputs" / "operation_groups" / "evidence" / "frames"
VIDEOS = PROJECT / "outputs" / "operation_groups" / "evidence" / "videos"
DIAGRAMS = PROJECT / "outputs" / "research_state" / "diagram_delivery"

SCHEMA = "multicam-grok-context-round1"
REVIEW_SCHEMA = "multicam-grok-context-review-v1"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_inputs():
    events = read_json(PACKAGE / "inputs" / "all_events.json")
    focus = read_json(PACKAGE / "inputs" / "focus_events.json")
    matrix = read_json(PACKAGE / "inputs" / "claim_evidence_matrix.json")
    episodes = read_json(PACKAGE / "inputs" / "episode_candidates.json")
    audit = read_json(PROJECT / "outputs" / "research_blueprint_v1" / "source_audit.json")
    evaluation = read_json(PROJECT / "outputs" / "ml_retrieval_evaluation" / "evaluation.json")
    return {
        "events": events,
        "focus": focus,
        "matrix": matrix,
        "episodes": episodes,
        "audit": audit,
        "evaluation": evaluation,
    }


def slot(value, status, evidence_ids, unknown_reason=None):
    return {
        "value": value,
        "status": status,
        "evidence_ids": list(evidence_ids),
        "unknown_reason": unknown_reason,
    }


def empty_slot(reason):
    return slot(None, "not_analyzed", [], reason)


@cache
def historical_evidence():
    """Read locally supplied research notes without altering their contents."""
    try:
        payload = read_json(EVIDENCE)
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Historical evidence is required at {EVIDENCE}. "
            "Set MULTICAM_EVIDENCE_TEXT or use export_local_evidence.py with the original checkout."
        ) from error
    if payload.get("schema") != "multicam-local-evidence-v1":
        raise ValueError("Unrecognized historical evidence schema")
    for field in ("operation_notes", "texts"):
        if not isinstance(payload.get(field), dict):
            raise ValueError(f"Historical evidence requires an object named {field}")
    return payload


def historical_text(key: str) -> str:
    value = historical_evidence()["texts"].get(key)
    if not isinstance(value, str):
        raise ValueError(f"Missing historical evidence text: {key}")
    return value
