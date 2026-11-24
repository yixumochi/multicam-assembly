"""Keep all 549 Action records and add context only for the 38 figure events.

New fields are agent candidates from the original text plus the middle frame
opened in this round. They are not user confirmations and do not rewrite labels.
"""
from __future__ import annotations

from collections import defaultdict

from context_common import empty_slot, historical_evidence, slot

def get_notes():
    """Read middle-frame notes keyed by their original event IDs."""
    return historical_evidence()["operation_notes"]


def _frames(event):
    rows = []
    for frame in event.get("frames") or []:
        rows.append({
            "role": frame.get("role"),
            "frame_zero_based": frame.get("frame_zero_based"),
            "nominal_seconds": frame.get("nominal_seconds"),
            "image": frame.get("image"),
            "sha256": frame.get("sha256"),
        })
    return rows


def _window_roles(event):
    seen = []
    for window in event.get("windows") or []:
        row = {
            "role": window.get("role"),
            "identity_status": window.get("identity_status"),
            "anchor_identity_status": window.get("anchor_identity_status"),
        }
        if row not in seen:
            seen.append(row)
    return seen


def _figure_index(matrix):
    by_event = defaultdict(list)
    for figure in matrix["figures"]:
        for event_id in figure.get("event_ids") or []:
            by_event[event_id].append(figure["id"])
    return by_event


def _claim_roles(matrix):
    by_event = defaultdict(dict)
    for case in matrix["cases"]:
        for event in case["events"]:
            by_event[event["id"]] = dict(case["cells"])
    return by_event


def _focus_record(event, note, figures, claims):
    evidence = [f"frame:{event['id']}:middle", f"description:{event['id']}", f"label:{event['id']}"]
    return {
        "analysis_status": "agent_candidate",
        "operation_goal": slot(note["goal"], "agent_candidate", evidence),
        "phase": slot(note["phases"], "agent_candidate", evidence),
        "actor": slot(note["actor"], "agent_candidate", evidence),
        "physical_category": slot(note["physical"], "agent_candidate", [f"frame:{event['id']}:middle"]),
        "research_role": {
            "active_component": note["active"],
            "target_component": note["target"],
            "interface": note["interface"],
            "tool_or_support": note["tool"],
            "status": "agent_candidate",
            "note": "Research roles are separate from physical categories. Roles describe this frame and the original description.",
        },
        "active_component": slot(note["active"], "agent_candidate", evidence),
        "target_component": slot(note["target"], "agent_candidate", evidence),
        "interface": slot(note["interface"], "agent_candidate", evidence),
        "tool_or_support": slot(note["tool"], "agent_candidate", evidence),
        "comparison_axes": note["axes"],
        "source_kind": note["source_kind"],
        "review_status": "agent_candidate",
        "human_confirmation": {
            "new_fields": False,
            "scope": "The original action text and frame index are retained. Goal, phase, and objects are candidate fields. A previous review of a region does not confirm them.",
        },
        "observation": note["observation"],
        "interpretation": None,
        "unknowns": note["unknowns"],
        "evidence_ids": evidence + [f"figure:{item}" for item in figures],
        "figure_ids": figures,
        "claim_roles": claims,
        "middle_frame_checked": True,
    }


def _catalog_record():
    reason = "This record is outside the 38 events referenced by existing figures. Only the original index is retained and empty fields are unassessed."
    return {
        "analysis_status": "not_analyzed",
        "operation_goal": empty_slot(reason),
        "phase": empty_slot(reason),
        "actor": empty_slot(reason),
        "physical_category": empty_slot(reason),
        "research_role": None,
        "active_component": empty_slot(reason),
        "target_component": empty_slot(reason),
        "interface": empty_slot(reason),
        "tool_or_support": empty_slot(reason),
        "comparison_axes": [],
        "source_kind": "not_analyzed",
        "review_status": "not_analyzed",
        "human_confirmation": {"new_fields": False, "scope": "Unanalyzed"},
        "observation": None,
        "interpretation": None,
        "unknowns": [reason],
        "evidence_ids": [],
        "figure_ids": [],
        "claim_roles": {},
        "middle_frame_checked": False,
    }


def build_operation_contexts(inputs):
    events = inputs["events"]
    focus_ids = [item["id"] for item in inputs["focus"]]
    notes = get_notes()
    if len(events) != 549 or len(set(item["id"] for item in events)) != 549:
        raise RuntimeError("Expected 549 unique Action events")
    if set(focus_ids) != set(notes):
        missing = sorted(set(focus_ids) - set(notes))
        extra = sorted(set(notes) - set(focus_ids))
        raise RuntimeError(f"Focus notes do not match the 38 events: missing={missing} extra={extra}")
    figures = _figure_index(inputs["matrix"])
    claims = _claim_roles(inputs["matrix"])
    rows = []
    for event in events:
        base = {
            "event_id": event["id"],
            "original_action": {
                "id": event["id"],
                "label": event["label"],
                "text": event["text"],
                "description": event["description"],
                "case": event["case"],
                "task": event["task"],
                "region": event["region"],
                "start": event["start"],
                "end": event["end"],
                "fps": event["fps"],
                "source_sha256": event["source_sha256"],
                "ls_url": event["ls_url"],
                "video": event.get("video"),
                "event_fingerprint": event.get("event_fingerprint"),
                "quality_policy": event.get("quality_policy") or [],
                "frames": _frames(event),
            },
            "region_windows": _window_roles(event),
        }
        if event["id"] in notes:
            base.update(_focus_record(event, notes[event["id"]], figures[event["id"]], claims[event["id"]]))
        else:
            base.update(_catalog_record())
        rows.append(base)
    by_id = {row["event_id"]: row for row in rows}
    return {
        "schema": "multicam-operation-context-v1",
        "records": rows,
        "by_id": by_id,
        "counts": {
            "actions": len(rows),
            "focus_events": len(focus_ids),
            "not_analyzed": sum(row["analysis_status"] == "not_analyzed" for row in rows),
            "agent_candidate": sum(row["analysis_status"] == "agent_candidate" for row in rows),
            "human_confirmed_new_fields": 0,
            "cases": sorted({row["original_action"]["case"] for row in rows}, key=lambda item: int(item[1:])),
        },
    }
