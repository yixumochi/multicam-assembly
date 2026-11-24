"""Spread existing semantic groups across three comparison types.

The 142 groups and their event ids are reused. Labels are not re-embedded.
Verb counts describe the corpus. They are not a design ranking.
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from context_common import BASELINE, PACKAGE, sha256_file, write_json  # noqa: E402
from operation_context import get_notes  # noqa: E402

OUT = PACKAGE / "project" / "outputs" / "grok_semantic_spread"
GROUPS_PATH = BASELINE / "outputs" / "action_comparison_round2" / "semantic_groups.json"
EMBEDDINGS_PATH = BASELINE / "outputs" / "action_comparison_round2" / "event_text_embeddings.npy"
STORED_EVENTS_PATH = BASELINE / "outputs" / "action_comparison_round2" / "events.json"
NAME_DISTANCE = 0.35
OBJECTS = (
    "timber", "member", "joint", "gripper", "clamp", "panel",
    "module", "tool", "beam", "plate", "strut", "grid", "cassette",
)

TYPE_AXES = {
    "interface_grip": {
        "interface_configuration", "grip_configuration", "grip_distribution",
        "grip", "tool_body", "tool_support",
    },
    "process": {"sequence", "support", "actor_arrangement"},
    "phase_space": {"phase_space", "operator_extent"},
}
TYPE_TITLE = {
    "interface_grip": "Interface and grip",
    "process": "Process",
    "phase_space": "Phase and space",
}
TYPE_ZH = {
    "interface_grip": "Interface and grip",
    "process": "Process",
    "phase_space": "Phase and space",
}
LEADING = {
    "manual", "repeated", "collectively", "visible", "standing", "shared",
    "cooperative", "side", "plate", "end-region", "lower-edge", "tool",
    "overhead", "strut", "segment", "edge", "driver", "hammer-like",
}
SKIP = {
    "a", "an", "the", "at", "to", "of", "from", "with", "by", "into", "around",
    "near", "below", "above", "on", "in", "for", "toward", "towards", "using",
    "and", "or",
}
VERBS = {
    "move", "hold", "handle", "reposition", "approach", "position", "keep",
    "place", "transport", "operate", "reach", "maintain", "withdraw", "guide",
    "close", "lower", "lift", "hoist", "rotate", "insert", "carry", "apply",
    "retract", "reorient", "open", "adjust", "align", "feed", "remove",
    "attempt", "nail", "pick", "mill", "use", "bend", "prepare", "support",
    "stabilize", "assist", "finish", "raise", "touch", "suspend", "pull",
    "connect", "disconnect", "settle", "walk", "lay", "orient", "drive",
    "change", "unload", "reduce", "communicate", "screw", "retry", "load",
    "fasten", "drill", "saw", "chisel", "machine", "work", "turn", "slide",
    "clamp", "positioning", "lowering",
}
CASES = ["V01", "V06", "V07", "V11", "V20", "V04", "V21", "V22", "V27", "V29", "V23", "V24", "V26", "V28", "V30"]
INSTALLATION = [
    {
        "id": "G1",
        "key": "manual",
        "en": "Manual-led",
        "zh": "Human-led assembly",
        "cases": ["V01", "V06", "V07", "V11", "V20"],
        "note": "Group G1 from case_classification.json. This case-level navigation allows robotic fabrication in earlier steps.",
    },
    {
        "id": "G2",
        "key": "mixed",
        "en": "Mixed",
        "zh": "Hybrid human-robot assembly",
        "cases": ["V04", "V21", "V22", "V27", "V29"],
        "note": "G2 originally listed V04, V21, V22, and V27. V29 CRoW completes this group as specified in case_candidates_research.json.",
    },
    {
        "id": "G3",
        "key": "robot",
        "en": "Robot-led",
        "zh": "Robot or automation-led assembly",
        "cases": ["V23", "V24", "V26", "V28", "V30"],
        "note": "G3 originally listed V24, V26, and V28. The same candidate list adds V23 and V30. The cases can still include manual preparation or finishing.",
    },
]
CASE_GROUP = {case: group for group in INSTALLATION for case in group["cases"]}
WITHIN = {
    "manual": [
        "V01 shows an end entering a hole; hands are outside the frame.",
        "V06 shows hands at different heights along the edge, with people beside the panel.",
        "V07 shows a hand guiding flexible fibres into a seam without a rigid grip.",
        "V11 shows one person supporting the upper grid and another working at a lower joint.",
        "V20 shows three people standing below the module.",
        "Human-led assembly permits different positions. Working beside a panel, below a module, at a hole, and at a seam call for different checks.",
    ],
    "mixed": [
        "In V04 a robot holds the beam along its length while a person works at the joint.",
        "V21 compares a mounted drill and a handheld drill with different supports.",
        "In V22 each arm holds a separate panel.",
        "In V27 the gripping point remains almost between the arms while the far end sweeps through space.",
        "In V29 a small gripper holds a short member; the person with the control pendant does not hold it.",
        "Hybrid cases use different role divisions. A robot can hold material while a person works at the joint, or a person can supervise from nearby.",
    ],
    "robot": [
        "In V23 the nailer body enters from above. The working tip shows only part of the tool.",
        "In V24 two grippers hold one rod. A visible jaw opening does not establish load transfer.",
        "In V26 the nailer tip is below the beam while the body extends off-frame.",
        "In V28 the holder follows the length of the beam and a separate clamp acts at the joint.",
        "In V30 the two lateral grip pads remain between the outer interfaces.",
        "Robot-led cases still distinguish holding, joint closure, and tool approach. V23 and V26 are tool comparisons and add no grasp samples.",
    ],
}
GRASP_CASES = ["V01", "V04", "V06", "V11", "V20", "V22", "V24", "V27", "V28", "V29", "V30"]
GRASP_BOARD = [
    {
        "case": "V01",
        "visible_extent": "End enters a hole; hands out of frame",
        "camera": "unknown",
        "operator_side": "unknown",
        "second": "No second device is visible",
        "next_check": "A gap remains; no lock is visible",
        "source_kind": "video_observed",
        "figure": "D01",
    },
    {
        "case": "V04",
        "visible_extent": "Pads visible along beam; not contact span",
        "camera": "Seen from below",
        "operator_side": "unknown",
        "second": "No joint clamp in this frame",
        "next_check": "Beam turns; ends leave the frame",
        "source_kind": "video_observed",
        "figure": "D02",
    },
    {
        "case": "V06",
        "visible_extent": "Hands at different heights on the edge",
        "camera": "unknown",
        "operator_side": "People beside the panel",
        "second": "No separate fixture",
        "next_check": "The later edge shot is another composition",
        "source_kind": "video_observed",
        "figure": "D03",
    },
    {
        "case": "V11",
        "visible_extent": "Hands on upper and lower nodes",
        "camera": "unknown",
        "operator_side": "One stands, one kneels",
        "second": "Two roles, one frame",
        "next_check": "Holding is not measured load transfer",
        "source_kind": "video_observed",
        "figure": "D05",
    },
    {
        "case": "V20",
        "visible_extent": "Hands at underside; span not measured",
        "camera": "unknown",
        "operator_side": "Three people under the module",
        "second": "No joint device",
        "next_check": "Upright timber is not the support",
        "source_kind": "video_observed",
        "figure": "D03",
    },
    {
        "case": "V22",
        "visible_extent": "One gripper visible on one plate",
        "camera": "Wide shot",
        "operator_side": "Each arm holds its own plate",
        "second": "Other arm is not on this plate",
        "next_check": "Later seam is not tied to one plate",
        "source_kind": "video_observed",
        "figure": "D08",
    },
    {
        "case": "V24",
        "visible_extent": "Two jaws on one strut; gap is not load",
        "camera": "Top view",
        "operator_side": "Grippers sit along the strut",
        "second": "A second jaw is on the same strut",
        "next_check": "A visible jaw gap is not load transfer",
        "source_kind": "video_observed",
        "figure": "D10",
    },
    {
        "case": "V27",
        "visible_extent": "Grip stays; sweep is separate",
        "camera": "unknown",
        "operator_side": "Both arms stay by the grip",
        "second": "Two arms, one member",
        "next_check": "Far end sweeps; exit is not release",
        "source_kind": "video_observed",
        "figure": "D12",
    },
    {
        "case": "V28",
        "visible_extent": "Holder along beam; not contact span",
        "camera": "unknown",
        "operator_side": "Holder on beam; person is later",
        "second": "Interface clamp is another device",
        "next_check": "Later removal is not one step",
        "source_kind": "video_observed",
        "figure": "V28",
    },
    {
        "case": "V29",
        "visible_extent": "A compact gripper holds a short member",
        "camera": "unknown",
        "operator_side": "Arm to the side; person stands aside",
        "second": "The person is not the holder",
        "next_check": "This frame is a lift, not a joint",
        "source_kind": "video_observed",
        "figure": "D11",
    },
    {
        "case": "V30",
        "visible_extent": "Side pads stay between the outer laps",
        "camera": "Close-up of the lap",
        "operator_side": "The gripper remains on the member",
        "second": "Mating faces, not a second gripper",
        "next_check": "Faces meet or member lowers; mm in D13",
        "source_kind": "video_observed",
        "figure": "D13",
    },
]


def esc(value):
    return html.escape(str(value), quote=True)


def display_token(token):
    if token.isupper() or "-" in token:
        return token
    return token[:1].upper() + token[1:]


def verb_of(label):
    text = label.strip()
    if text.upper().startswith("ACTION") and "|" in text:
        text = text.split("|", 1)[1].strip()
    tokens = [token.strip(".,;:") for token in text.split() if token.strip(".,;:")]
    heads = [token for token in tokens if token.lower() not in LEADING and token.lower() not in SKIP]
    verbs = [token for token in heads if token.lower() in VERBS]
    if not verbs:
        return {"verb": None, "kind": "nominal_label", "phrase": text}
    phrase = [display_token(verbs[0])]
    position = tokens.index(verbs[0])
    if position + 2 < len(tokens) and tokens[position + 1].lower() in {"and", "or"}:
        follower = tokens[position + 2]
        if follower.lower() in VERBS:
            phrase.extend([tokens[position + 1].lower(), display_token(follower)])
    return {"verb": " ".join(phrase), "kind": "verb", "phrase": " ".join(phrase)}


def merge_seconds(intervals):
    ordered = sorted((start, end) for start, end in intervals if end > start)
    if not ordered:
        return 0.0
    cursor, close = ordered[0]
    total = 0.0
    for start, end in ordered[1:]:
        if start <= close:
            close = max(close, end)
        else:
            total += close - cursor
            cursor, close = start, end
    return total + close - cursor


def load_events():
    events = json.loads((PACKAGE / "inputs" / "all_events.json").read_text(encoding="utf-8"))
    if len(events) != 549 or len({item["id"] for item in events}) != 549:
        raise RuntimeError("Expected 549 unique actions")
    return events


def load_groups():
    groups = json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    if len(groups) != 142:
        raise RuntimeError(f"Expected 142 historical groups, found {len(groups)}")
    return groups


def join_groups(events, groups):
    by_event = {}
    seen = []
    for group in groups:
        members = list(group.get("event_ids") or [])
        seen.extend(members)
        for event_id in members:
            if event_id in by_event:
                raise RuntimeError(f"Event {event_id} is in two historical groups")
            by_event[event_id] = {
                "group_id": group["id"],
                "group_name": group["name"],
                "labels": list(group.get("labels") or []),
            }
    if len(seen) != len(set(seen)):
        raise RuntimeError("Historical group membership is not unique")
    event_ids = {item["id"] for item in events}
    missing = sorted(event_ids - set(by_event))
    unknown = sorted(set(by_event) - event_ids)
    if unknown:
        raise RuntimeError(f"Historical groups cite events absent from the 549: {unknown[:5]}")
    return by_event, missing


def case_minutes(events):
    buckets = defaultdict(lambda: defaultdict(list))
    raw = defaultdict(float)
    for event in events:
        duration = max(float(event["end"]) - float(event["start"]), 0.0)
        raw[event["case"]] += duration
        buckets[event["case"]][event["source_sha256"]].append((float(event["start"]), float(event["end"])))
    minutes = {}
    for case in CASES:
        union = sum(merge_seconds(intervals) for intervals in buckets[case].values())
        minutes[case] = {
            "union_seconds": union,
            "summed_seconds": raw[case],
            "minutes": union / 60.0,
            "sources": len(buckets[case]),
        }
        if union - raw[case] > 1e-6:
            raise RuntimeError(f"Union exceeded the summed duration in {case}")
    return minutes


def event_types(event_id):
    axes = set((get_notes().get(event_id) or {}).get("axes") or [])
    return [name for name, wanted in TYPE_AXES.items() if axes & wanted]


def neighbor_ids(events, membership, focus_ids):
    grouped = defaultdict(set)
    labels = defaultdict(set)
    for event in events:
        info = membership.get(event["id"])
        if info:
            grouped[info["group_id"]].add(event["id"])
        else:
            labels[event["label"]].add(event["id"])
    result = {}
    for type_name in TYPE_AXES:
        seeds = [event_id for event_id in focus_ids if type_name in event_types(event_id)]
        groups = {membership[event_id]["group_id"] for event_id in seeds if event_id in membership}
        names = {next(item["label"] for item in events if item["id"] == event_id) for event_id in seeds if event_id not in membership}
        found = set()
        for group_id in groups:
            found.update(grouped[group_id])
        for label in names:
            found.update(labels[label])
        result[type_name] = {
            "checked": sorted(seeds),
            "neighbors": sorted(found - set(focus_ids)),
        }
    return result


def tally(events, ids):
    counts = defaultdict(int)
    sources = defaultdict(set)
    by_id = {item["id"]: item for item in events}
    for event_id in ids:
        event = by_id[event_id]
        parsed = verb_of(event["label"])
        if not parsed["verb"]:
            continue
        counts[parsed["verb"]] += 1
        sources[parsed["verb"]].add(event["source_sha256"])
    return counts, sources


def top_verbs(rows, limit):
    ranked = sorted(rows, key=lambda item: (-item["events"], item["verb"]))
    return ranked[:limit]


def label_objects(label):
    text = label.lower()
    return [noun for noun in OBJECTS if re.search(rf"\b{noun}s?\b", text)]


def coverage_rows(events):
    by_source = defaultdict(lambda: defaultdict(list))
    durations = []
    for event in events:
        start, end = float(event["start"]), float(event["end"])
        durations.append(round(max(end - start, 0.0), 3))
        by_source[event["case"]][event["source_sha256"]].append((start, end))
    rows = []
    for case in CASES:
        union = summed = hole = 0.0
        for intervals in by_source[case].values():
            merged = merge_seconds(intervals)
            total = sum(end - start for start, end in intervals)
            span = max(end for _, end in intervals) - min(start for start, _ in intervals)
            union += merged
            summed += total
            hole += span - merged
        rows.append({
            "case": case,
            "installation": CASE_GROUP[case]["en"],
            "union_seconds": round(union, 1),
            "summed_seconds": round(summed, 1),
            "hole_seconds": round(hole, 1),
        })
    return rows, durations


def verb_object_matrix(parsed):
    counts = defaultdict(lambda: defaultdict(int))
    sources = defaultdict(lambda: defaultdict(set))
    for event, item in parsed:
        if not item["verb"]:
            continue
        for noun in label_objects(event["label"]):
            counts[item["verb"]][noun] += 1
            sources[item["verb"]][noun].add(event["source_sha256"])
    ranked = sorted(counts, key=lambda verb: (-sum(counts[verb].values()), verb))
    return {
        "objects": list(OBJECTS),
        "rows": [
            {
                "verb": verb,
                "cells": [
                    {"events": counts[verb][noun], "sources": len(sources[verb][noun])}
                    for noun in OBJECTS
                ],
            }
            for verb in ranked
            if sum(counts[verb].values()) >= 3
        ],
    }


def name_links(events, groups, membership):
    """Test the 92 later names against the frozen groups with stored vectors."""
    stored = json.loads(STORED_EVENTS_PATH.read_text(encoding="utf-8"))
    matrix = np.load(EMBEDDINGS_PATH)
    if matrix.shape != (len(stored), 384):
        raise RuntimeError("Stored text embeddings do not match the stored event list")
    if float(np.max(np.abs(np.linalg.norm(matrix, axis=1) - 1.0))) > 1e-4:
        raise RuntimeError("Stored text embeddings are not unit length")
    index = {row["id"]: position for position, row in enumerate(stored)}
    if set(index) != {event["id"] for event in events}:
        raise RuntimeError("Stored embedding ids do not match the 549 actions")
    blocks = {}
    names = {}
    for group in groups:
        ids = list(group.get("event_ids") or [])
        blocks[group["id"]] = matrix[[index[event_id] for event_id in ids]]
        names[group["id"]] = group["name"]
    by_label = defaultdict(list)
    for event in events:
        if event["id"] in membership:
            continue
        vector = matrix[index[event["id"]]]
        ranked = []
        for group_id, rows in blocks.items():
            distance = float(np.max(1.0 - rows @ vector))
            ranked.append((distance, group_id))
        ranked.sort()
        joins = [
            {
                "group_id": group_id,
                "name": names[group_id],
                "max_cosine_distance": round(distance, 3),
            }
            for distance, group_id in ranked
            if distance <= NAME_DISTANCE + 1e-9
        ]
        by_label[event["label"]].append({
            "case": event["case"],
            "nearest_distance": round(ranked[0][0], 3),
            "nearest_id": ranked[0][1],
            "joins": joins,
        })
    labels = []
    for label, rows in by_label.items():
        signatures = {(row["nearest_id"], row["nearest_distance"], tuple(item["group_id"] for item in row["joins"])) for row in rows}
        if len(signatures) != 1:
            raise RuntimeError(f"Label {label} does not share one nearest group")
        first = rows[0]
        labels.append({
            "label": label,
            "events": len(rows),
            "cases": sorted({row["case"] for row in rows}),
            "nearest_group_id": first["nearest_id"],
            "nearest_group_name": names[first["nearest_id"]],
            "max_cosine_distance": first["nearest_distance"],
            "joins": first["joins"],
            "within_threshold": bool(first["joins"]),
        })
    labels.sort(key=lambda row: (row["max_cosine_distance"], row["label"]))
    within = sum(row["events"] for row in labels if row["within_threshold"])
    pending = sum(row["events"] for row in labels)
    return {
        "threshold": NAME_DISTANCE,
        "linkage": "complete",
        "new_embeddings": False,
        "groups_rewritten": False,
        "events": pending,
        "within_threshold_events": within,
        "outside_threshold_events": pending - within,
        "labels": labels,
    }


def adjacent_verbs(events):
    by_source = defaultdict(list)
    for event in events:
        by_source[event["source_sha256"]].append(event)
    rows = []
    for case in GRASP_CASES:
        chosen = [event for event in events if event["case"] == case and event["id"] in get_notes()]
        if not chosen:
            raise RuntimeError(f"Grasp case {case} has no checked event")
        chosen.sort(key=lambda item: (float(item["start"]), item["id"]))
        anchor = chosen[0]
        same = sorted(by_source[anchor["source_sha256"]], key=lambda item: (float(item["start"]), item["id"]))
        position = next(index for index, item in enumerate(same) if item["id"] == anchor["id"])
        previous = same[position - 1] if position else None
        following = same[position + 1] if position + 1 < len(same) else None

        def pack(other):
            if other is None:
                return None
            gap = float(anchor["start"]) - float(other["end"]) if other is previous else float(other["start"]) - float(anchor["end"])
            return {
                "event_id": other["id"],
                "label": other["label"],
                "verb": verb_of(other["label"])["verb"] or verb_of(other["label"])["phrase"],
                "gap_seconds": round(gap, 2),
                "adjacent": gap <= 15,
            }

        rows.append({
            "case": case,
            "installation": CASE_GROUP[case]["en"],
            "event_id": anchor["id"],
            "label": anchor["label"],
            "verb": verb_of(anchor["label"])["verb"] or verb_of(anchor["label"])["phrase"],
            "source_sha256": anchor["source_sha256"],
            "previous": pack(previous),
            "next": pack(following),
        })
    return rows


def grasp_scope(events, groups):
    """Count same-name hold, transport, and insert events that still lack a process reading."""
    by_id = {event["id"]: event for event in events}
    note_ids = set(get_notes())

    def rows(match):
        found = []
        for group in groups:
            blob = " ".join([group.get("name") or "", *(group.get("labels") or [])]).lower()
            if not match(blob):
                continue
            ids = list(group.get("event_ids") or [])
            found.append({
                "id": group["id"],
                "name": group["name"],
                "events": len(ids),
                "checked": sum(event_id in note_ids for event_id in ids),
                "cases": sorted({by_id[event_id]["case"] for event_id in ids if event_id in by_id}),
            })
        return found

    inserts = [event for event in events if "insert" in event["label"].lower()]
    return {
        "hold": rows(lambda blob: "hold" in blob),
        "transport": rows(lambda blob: "transport" in blob),
        "insert_events": len(inserts),
        "insert_checked": sum(event["id"] in note_ids for event in inserts),
        "insert_cases": sorted({event["case"] for event in inserts}),
        "insert_in_historical_groups": sum(any(event["id"] in (group.get("event_ids") or []) for group in groups) for event in inserts),
    }


def semantic_families(events):
    """Group all 549 actions by the extracted verb, without dropping single-case labels."""
    note_ids = set(get_notes())
    by_source = defaultdict(list)
    for event in events:
        by_source[event["source_sha256"]].append(event)
    for rows in by_source.values():
        rows.sort(key=lambda item: (float(item["start"]), item["id"]))
    located = {}
    for rows in by_source.values():
        for position, event in enumerate(rows):
            located[event["id"]] = (rows, position)
    families = {}
    for event in events:
        item = verb_of(event["label"])
        key = item["verb"] or item["phrase"]
        bucket = families.setdefault(key, {
            "name": key,
            "kind": item["kind"],
            "events": 0,
            "checked": 0,
            "cases": defaultdict(int),
            "labels": {},
            "before": defaultdict(int),
            "after": defaultdict(int),
        })
        bucket["events"] += 1
        bucket["cases"][event["case"]] += 1
        if event["id"] in note_ids:
            bucket["checked"] += 1
        label = bucket["labels"].setdefault(event["label"], {"events": 0, "checked": 0, "cases": set()})
        label["events"] += 1
        label["cases"].add(event["case"])
        if event["id"] in note_ids:
            label["checked"] += 1
        rows, position = located[event["id"]]
        if position:
            previous = rows[position - 1]
            if float(event["start"]) - float(previous["end"]) <= 15:
                other = verb_of(previous["label"])
                bucket["before"][other["verb"] or other["phrase"]] += 1
        if position + 1 < len(rows):
            following = rows[position + 1]
            if float(following["start"]) - float(event["end"]) <= 15:
                other = verb_of(following["label"])
                bucket["after"][other["verb"] or other["phrase"]] += 1
    output = []
    for bucket in families.values():
        output.append({
            "name": bucket["name"],
            "kind": bucket["kind"],
            "events": bucket["events"],
            "checked": bucket["checked"],
            "cases": [{"case": case, "events": count} for case, count in sorted(bucket["cases"].items())],
            "labels": [
                {
                    "label": label,
                    "events": info["events"],
                    "checked": info["checked"],
                    "cases": sorted(info["cases"]),
                }
                for label, info in sorted(bucket["labels"].items(), key=lambda item: (-item[1]["events"], item[0]))
            ],
            "before": [{"name": name, "events": count} for name, count in sorted(bucket["before"].items(), key=lambda item: (-item[1], item[0]))],
            "after": [{"name": name, "events": count} for name, count in sorted(bucket["after"].items(), key=lambda item: (-item[1], item[0]))],
        })
    output.sort(key=lambda row: (-row["events"], row["name"]))
    if sum(row["events"] for row in output) != 549:
        raise RuntimeError("Semantic families do not cover 549 actions")
    return output


def build_statistics(events, groups, membership, missing):
    parsed = [(event, verb_of(event["label"])) for event in events]
    verb_events = defaultdict(int)
    verb_sources = defaultdict(set)
    verb_cases = defaultdict(set)
    nominal = defaultdict(int)
    for event, item in parsed:
        if item["kind"] != "verb":
            nominal[item["phrase"]] += 1
            continue
        verb_events[item["verb"]] += 1
        verb_sources[item["verb"]].add(event["source_sha256"])
        verb_cases[item["verb"]].add(event["case"])
    corpus = [
        {
            "verb": verb,
            "events": verb_events[verb],
            "sources": len(verb_sources[verb]),
            "cases": len(verb_cases[verb]),
        }
        for verb in verb_events
    ]
    minutes = case_minutes(events)
    heat_verbs = [item["verb"] for item in top_verbs(corpus, 12)]
    heat = []
    for case in CASES:
        cells = []
        for verb in heat_verbs:
            matched = [
                event for event, item in parsed
                if event["case"] == case and item["verb"] == verb
            ]
            count = len(matched)
            rate = count / minutes[case]["minutes"] if minutes[case]["minutes"] else None
            cells.append({
                "verb": verb,
                "events": count,
                "sources": len({event["source_sha256"] for event in matched}),
                "per_annotated_minute": None if rate is None else round(rate, 3),
            })
        heat.append({"case": case, **minutes[case], "cells": cells})
    focus_ids = set(get_notes())
    neighborhoods = neighbor_ids(events, membership, focus_ids)
    types = {}
    for type_name, buckets in neighborhoods.items():
        checked_counts, checked_sources = tally(events, buckets["checked"])
        neighbor_counts, neighbor_sources = tally(events, buckets["neighbors"])
        names = sorted(set(checked_counts) | set(neighbor_counts), key=lambda verb: (
            -(checked_counts[verb] + neighbor_counts[verb]), verb
        ))
        types[type_name] = {
            "checked_events": len(buckets["checked"]),
            "neighbor_events": len(buckets["neighbors"]),
            "verbs": [
                {
                    "verb": verb,
                    "checked_events": checked_counts[verb],
                    "checked_sources": len(checked_sources[verb]),
                    "neighbor_events": neighbor_counts[verb],
                    "neighbor_sources": len(neighbor_sources[verb]),
                }
                for verb in names[:8]
            ],
        }
    multi_case = []
    for group in groups:
        cases = sorted({event["case"] for event in events if membership.get(event["id"], {}).get("group_id") == group["id"]})
        if len(cases) < 2:
            continue
        multi_case.append({
            "group_id": group["id"],
            "name": group["name"],
            "labels": list(group.get("labels") or []),
            "events": len(group.get("event_ids") or []),
            "cases": cases,
        })
    multi_case.sort(key=lambda item: (-len(item["cases"]), -item["events"], item["group_id"]))
    by_id = {event["id"]: event for event in events}
    semantic_groups = []
    for group in groups:
        ids = list(group.get("event_ids") or [])
        semantic_groups.append({
            "group_id": group["id"],
            "name": group["name"],
            "labels": list(group.get("labels") or []),
            "events": len(ids),
            "checked": sum(event_id in focus_ids for event_id in ids),
            "cases": sorted({by_id[event_id]["case"] for event_id in ids}),
        })
    semantic_groups.sort(key=lambda item: (-len(item["cases"]), -item["events"], item["group_id"]))
    catalog = []
    for event, item in parsed:
        info = membership.get(event["id"])
        catalog.append({
            "id": event["id"],
            "case": event["case"],
            "task": event["task"],
            "start": round(float(event["start"]), 2),
            "end": round(float(event["end"]), 2),
            "label": event["label"],
            "verb": item["verb"] or item["phrase"],
            "group_id": None if info is None else info["group_id"],
            "group_name": None if info is None else info["group_name"],
            "frame_checked": event["id"] in focus_ids,
        })
    catalog.sort(key=lambda row: (row["case"], row["start"], row["id"]))
    historical_labels = {event["label"] for event in events if event["id"] in membership}
    links = name_links(events, groups, membership)
    link_by_label = {row["label"]: row for row in links["labels"]}
    for row in catalog:
        if row["group_id"]:
            row["name_layer"] = "historical_id"
            row["vector_candidate"] = False
            row["max_cosine_distance"] = None
        else:
            row["name_layer"] = "same_name_outside_group" if row["label"] in historical_labels else "new_label"
            link = link_by_label[row["label"]]
            row["nearest_group_id"] = link["nearest_group_id"]
            row["vector_candidate"] = link["within_threshold"]
            row["max_cosine_distance"] = link["max_cosine_distance"]
        row["research_operation"] = row["label"] if row["group_id"] in {"S009", "S017", "S028"} else None
    verb_matrix = []
    for verb in [item["verb"] for item in sorted(corpus, key=lambda item: (-item["events"], item["verb"]))]:
        cells = [
            sum(1 for event, item in parsed if event["case"] == case and item["verb"] == verb)
            for case in CASES
        ]
        verb_matrix.append({"verb": verb, "events": sum(cells), "cells": cells})
    missing_labels = sorted({event["label"] for event in events if event["id"] in set(missing)})
    columns = ["visible_extent", "camera", "operator_side", "second", "next_check"]
    shared = {}
    for column in columns:
        filled = [row[column] for row in GRASP_BOARD if row[column] != "unknown"]
        shared[column] = len(set(filled)) == 1 and len(filled) == len(GRASP_BOARD)
    board = [{**row, "installation": CASE_GROUP[row["case"]]["en"]} for row in GRASP_BOARD]
    installation = []
    for group in INSTALLATION:
        chosen = [event["case"] for event in events if event["case"] in group["cases"]]
        if sorted(set(group["cases"])) != sorted(set(chosen)):
            raise RuntimeError(f"Installation group {group['id']} is missing events")
        verb_counts = defaultdict(int)
        verb_sources = defaultdict(set)
        for event, item in parsed:
            if event["case"] not in group["cases"] or not item["verb"]:
                continue
            verb_counts[item["verb"]] += 1
            verb_sources[item["verb"]].add(event["source_sha256"])
        group_minutes = sum(minutes[case]["minutes"] for case in group["cases"])
        ranked = sorted(verb_counts, key=lambda verb: (-verb_counts[verb], verb))
        installation.append({
            **{key: group[key] for key in ("id", "key", "en", "zh", "cases", "note")},
            "events": sum(verb_counts.values()),
            "sources": len({event["source_sha256"] for event in events if event["case"] in group["cases"]}),
            "annotated_minutes": round(group_minutes, 3),
            "verbs": [
                {
                    "verb": verb,
                    "events": verb_counts[verb],
                    "sources": len(verb_sources[verb]),
                    "per_annotated_minute": None if not group_minutes else round(verb_counts[verb] / group_minutes, 3),
                }
                for verb in ranked
            ],
        })
        case_verbs = defaultdict(lambda: defaultdict(int))
        case_sources = defaultdict(lambda: defaultdict(set))
        for event, item in parsed:
            if event["case"] not in group["cases"] or not item["verb"]:
                continue
            case_verbs[item["verb"]][event["case"]] += 1
            case_sources[item["verb"]][event["case"]].add(event["source_sha256"])
        ranked_cases = sorted(case_verbs, key=lambda verb: (-sum(case_verbs[verb].values()), verb))[:6]
        installation[-1]["within"] = {
            "verbs": ranked_cases,
            "rows": [
                {
                    "case": case,
                    "cells": [
                        {
                            "verb": verb,
                            "events": case_verbs[verb][case],
                            "sources": len(case_sources[verb][case]),
                        }
                        for verb in ranked_cases
                    ],
                }
                for case in group["cases"]
            ],
            "reading": WITHIN[group["key"]],
        }
    return {
        "schema": "multicam-semantic-spread-v1",
        "model_calls": 0,
        "training": False,
        "loss": None,
        "clustering": "reused complete-linkage cosine distance 0.35; 142 groups; not re-fit",
        "verb_rule": "Remove a leading ACTION prefix. Skip closed-class words and a closed list of leading modifiers. Keep the first remaining token that is on the verb list, plus a following and/or coordinate when that word is also a verb. Labels with no verb, including Mallet and Shared strut engagement, stay out of the verb charts.",
        "time_rule": "The rate denominator is the union of annotated intervals inside each source video, summed within the case. It is labelled time, not work time. V30 carries a 5x overlay, so its rate is not a speed.",
        "counts": {
            "actions": 549,
            "historical_groups": 142,
            "events_in_historical_groups": 457,
            "events_outside_historical_groups": len(missing),
            "labels_outside_historical_groups": len(missing_labels),
            "nominal_labels": dict(nominal),
        },
        "corpus_verbs": sorted(corpus, key=lambda item: (-item["events"], item["verb"])),
        "heatmap_verbs": heat_verbs,
        "heatmap": heat,
        "types": types,
        "neighborhoods": {key: {"checked": value["checked"], "neighbor_count": len(value["neighbors"])} for key, value in neighborhoods.items()},
        "multi_case_groups": multi_case,
        "semantic_groups": semantic_groups,
        "catalog": catalog,
        "verb_matrix": verb_matrix,
        "case_order": CASES,
        "missing_labels": missing_labels,
        "grasp_board": board,
        "grasp_column_is_constant": shared,
        "within_video": adjacent_verbs(events),
        "installation": installation,
        "grasp_scope": grasp_scope(events, groups),
        "name_links": links,
        "coverage": coverage_rows(events)[0],
        "durations": coverage_rows(events)[1],
        "verb_object": verb_object_matrix(parsed),
        "families": semantic_families(events),
    }


def style_axes(axis):
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(labelsize=8)


def draw_verb_bars(stats):
    rows = [item for item in stats["corpus_verbs"] if item["events"] >= 1][:12]
    rows.reverse()
    figure, axis = plt.subplots(figsize=(9.2, 6.2))
    positions = range(len(rows))
    axis.barh([item - 0.16 for item in positions], [item["events"] for item in rows], height=0.32, color="#2f6f5e", label="Events")
    axis.barh([item + 0.16 for item in positions], [item["sources"] for item in rows], height=0.32, color="#c4a574", label="Source videos")
    axis.set_yticks(list(positions), [item["verb"] for item in rows])
    axis.set_xlabel("Count")
    axis.set_title(f"Frequent verbs in 549 actions  |  N={stats['counts']['actions']} events")
    axis.legend(frameon=False, fontsize=8)
    style_axes(axis)
    figure.tight_layout()
    path = OUT / "fig1_verb_counts.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_heatmap(stats):
    verbs = stats["heatmap_verbs"]
    counts = [[cell["events"] for cell in row["cells"]] for row in stats["heatmap"]]
    rates = [[0 if cell["per_annotated_minute"] is None else cell["per_annotated_minute"] for cell in row["cells"]] for row in stats["heatmap"]]
    figure, axes = plt.subplots(1, 2, figsize=(14.5, 7.2))
    panels = (
        (counts, "Event count", True),
        (rates, "Events per annotated minute", False),
    )
    for axis, (matrix, title, show_sources) in zip(axes, panels):
        limit = 20 if not show_sources else None
        image = axis.imshow(matrix, cmap="YlGn", aspect="auto", vmin=0, vmax=limit)
        axis.set_xticks(range(len(verbs)), verbs, rotation=55, ha="right", fontsize=7)
        axis.set_yticks(range(len(CASES)), [f"{case}  {CASE_GROUP[case]['en']}" for case in CASES], fontsize=8)
        caption = title if show_sources else f"{title}; color capped at 20"
        axis.set_title(f"{caption}  |  15 cases")
        darkest = (limit or max(max(row) for row in matrix) or 1) * 0.62
        for y, row in enumerate(matrix):
            for x, value in enumerate(row):
                if value <= 0:
                    continue
                if show_sources:
                    sources = stats["heatmap"][y]["cells"][x]["sources"]
                    text = f"{int(value)}/{sources}"
                else:
                    text = f"{value:.1f}"
                axis.text(x, y, text, ha="center", va="center", fontsize=6, color="#17332c" if value < darkest else "white")
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.tight_layout()
    path = OUT / "fig2_case_verb_heatmap.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_types(stats):
    figure, axes = plt.subplots(1, 3, figsize=(13.8, 5.4))
    for axis, type_name in zip(axes, TYPE_AXES):
        payload = stats["types"][type_name]
        rows = list(reversed(payload["verbs"]))
        positions = range(len(rows))
        axis.barh([item - 0.16 for item in positions], [item["checked_events"] for item in rows], height=0.32, color="#2f6f5e", label="Frame-checked")
        axis.barh([item + 0.16 for item in positions], [item["neighbor_events"] for item in rows], height=0.32, color="#d9d3c7", label="Same-group neighbor")
        axis.set_yticks(list(positions), [item["verb"] for item in rows], fontsize=7)
        axis.set_title(
            f"{TYPE_TITLE[type_name]}\nchecked {payload['checked_events']}, neighbors {payload['neighbor_events']}",
            fontsize=9,
        )
        style_axes(axis)
    axes[0].legend(frameon=False, fontsize=7, loc="lower right")
    figure.suptitle("Verb counts inside the three comparison types", fontsize=12)
    figure.tight_layout()
    path = OUT / "fig3_type_small_multiples.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_installation(stats):
    verbs = [item["verb"] for item in stats["corpus_verbs"][:8]]
    lookup = {
        (group["key"], item["verb"]): item
        for group in stats["installation"]
        for item in group["verbs"]
    }
    figure, axes = plt.subplots(1, 2, figsize=(12.8, 5.6))
    positions = list(range(len(verbs)))
    width = 0.24
    colors = {"manual": "#8c4a3a", "mixed": "#c4a574", "robot": "#2f6f5e"}
    for axis, field, title in (
        (axes[0], "events", "Event count"),
        (axes[1], "per_annotated_minute", "Events per annotated minute"),
    ):
        for offset, group in enumerate(stats["installation"]):
            values = [lookup.get((group["key"], verb), {}).get(field) or 0 for verb in verbs]
            axis.bar(
                [item + (offset - 1) * width for item in positions],
                values, width=width, color=colors[group["key"]], label=group["en"],
            )
        axis.set_xticks(positions, verbs, rotation=35, ha="right")
        axis.set_title(f"{title}  |  5 cases each")
        style_axes(axis)
    axes[0].legend(frameon=False, fontsize=8)
    figure.suptitle("Same verbs, split by who leads the assembly", fontsize=12)
    figure.tight_layout()
    path = OUT / "fig5_installation_groups.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_within(stats):
    figure, axes = plt.subplots(3, 1, figsize=(11.2, 8.4))
    for axis, group in zip(axes, stats["installation"]):
        within = group["within"]
        matrix = [[cell["events"] for cell in row["cells"]] for row in within["rows"]]
        limit = max(max(row) for row in matrix) or 1
        image = axis.imshow(matrix, cmap="YlGn", aspect="auto", vmin=0, vmax=limit)
        axis.set_xticks(range(len(within["verbs"])), within["verbs"], rotation=30, ha="right", fontsize=8)
        axis.set_yticks(range(len(group["cases"])), group["cases"], fontsize=8)
        axis.set_title(f"{group['en']}  |  5 cases", fontsize=10)
        for y, row in enumerate(matrix):
            for x, value in enumerate(row):
                if value <= 0:
                    continue
                sources = within["rows"][y]["cells"][x]["sources"]
                axis.text(x, y, f"{value}/{sources}", ha="center", va="center", fontsize=7,
                          color="white" if value > limit * 0.62 else "#17332c")
        figure.colorbar(image, ax=axis, fraction=0.03, pad=0.02)
    figure.suptitle("Inside each installation group: event count / source videos", fontsize=12)
    figure.tight_layout()
    path = OUT / "fig6_within_groups.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_board(stats):
    figure = plt.figure(figsize=(18.4, 11.2))
    grid = figure.add_gridspec(2, 1, height_ratios=[1.45, 1])
    table_axis = figure.add_subplot(grid[0])
    sequence_axis = figure.add_subplot(grid[1])
    table_axis.axis("off")
    columns = ["Case", "Visible extent", "Camera", "Operator side", "Second device", "Next check"]
    cells = [
        [
            row["case"] + " · " + row["installation"],
            row["visible_extent"], row["camera"], row["operator_side"], row["second"], row["next_check"],
        ]
        for row in stats["grasp_board"]
    ]
    table = table_axis.table(
        cellText=cells, colLabels=columns, loc="center", cellLoc="left",
        colWidths=[0.14, 0.20, 0.16, 0.18, 0.16, 0.16],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.7)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("#e4ddd2")
        cell.set_linewidth(0.4)
        if row == 0:
            cell.set_facecolor("#2f6f5e")
            cell.set_text_props(color="white", fontsize=7.5)
        elif column == 0:
            cell.set_facecolor("#f3efe7")
        else:
            cell.set_facecolor("white")
    table_axis.set_title(f"Grasp readings across {len(GRASP_BOARD)} cases  |  V23 and V26 stay with tools", fontsize=12, pad=10)
    labels = [row["case"] for row in stats["within_video"]]
    positions = list(range(len(labels)))
    sequence_axis.hlines(positions, -1, 1, color="#e4ddd2", linewidth=4)
    for index, row in enumerate(stats["within_video"]):
        sequence_axis.scatter(0, index, s=28, color="#2f6f5e", zorder=3)
        sequence_axis.text(0, index + 0.28, row["verb"], ha="center", va="bottom", fontsize=6.5, color="#17332c")
        if row["previous"]:
            mark = row["previous"]["verb"]
            gap = row["previous"]["gap_seconds"]
            sequence_axis.text(-1, index, f"{mark}  {gap:+.1f}s", ha="left", va="center", fontsize=6, color="#6d624f")
        if row["next"]:
            mark = row["next"]["verb"]
            gap = row["next"]["gap_seconds"]
            sequence_axis.text(1, index, f"{gap:+.1f}s  {mark}", ha="right", va="center", fontsize=6, color="#6d624f")
    sequence_axis.set_xlim(-1.05, 1.05)
    sequence_axis.set_ylim(-0.7, len(stats["within_video"]) - 0.3)
    sequence_axis.set_yticks(list(positions), labels, fontsize=7)
    sequence_axis.set_xticks([])
    sequence_axis.set_title("Previous and next label on the same source video", fontsize=10)
    for spine in sequence_axis.spines.values():
        spine.set_visible(False)
    figure.tight_layout()
    path = OUT / "fig4_grasp_board.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_coverage(stats):
    durations = stats["durations"]
    rows = list(reversed(stats["coverage"]))
    figure, axes = plt.subplots(1, 2, figsize=(12.4, 6.6), gridspec_kw={"width_ratios": [1, 1.35]})
    axes[0].hist(durations, bins=[0, 0.5, 1, 2, 4, 8, 18], color="#2f6f5e", edgecolor="white")
    axes[0].set_xlabel("Annotated interval (media seconds)")
    axes[0].set_ylabel("Actions")
    axes[0].set_title(f"Action length  |  N={len(durations)}")
    style_axes(axes[0])
    positions = range(len(rows))
    union = [row["union_seconds"] for row in rows]
    overlap = [round(row["summed_seconds"] - row["union_seconds"], 1) for row in rows]
    holes = [row["hole_seconds"] for row in rows]
    axes[1].barh(positions, union, color="#2f6f5e", label="Union of labelled intervals")
    axes[1].barh(positions, overlap, left=union, color="#c4a574", label="Extra from overlapping labels")
    axes[1].barh([item + 0.38 for item in positions], holes, height=0.28, color="#d9d3c7", label="Unlabelled gap inside first-to-last")
    axes[1].set_yticks(list(positions), [f"{row['case']}  {row['installation'].split()[0]}" for row in rows], fontsize=8)
    axes[1].set_xlabel("Seconds on the video clock")
    axes[1].set_title("Labelled time, overlap, and gaps")
    axes[1].legend(frameon=False, fontsize=7, loc="lower right")
    style_axes(axes[1])
    figure.tight_layout()
    path = OUT / "fig7_duration_coverage.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_verb_object(stats):
    matrix_rows = stats["verb_object"]["rows"][:18]
    nouns = stats["verb_object"]["objects"]
    matrix = [[cell["events"] for cell in row["cells"]] for row in matrix_rows]
    figure, axis = plt.subplots(figsize=(11.6, 7.2))
    limit = max(max(row) for row in matrix) if matrix else 1
    image = axis.imshow(matrix, cmap="YlGn", aspect="auto", vmin=0, vmax=min(limit, 20))
    axis.set_xticks(range(len(nouns)), nouns, rotation=30, ha="right", fontsize=8)
    axis.set_yticks(range(len(matrix_rows)), [row["verb"] for row in matrix_rows], fontsize=8)
    axis.set_title("Verb–object token co-occurrence  |  event count, colour capped at 20")
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            if value <= 0:
                continue
            sources = matrix_rows[y]["cells"][x]["sources"]
            axis.text(x, y, f"{value}/{sources}", ha="center", va="center", fontsize=6.5,
                      color="white" if value > 12 else "#17332c")
    figure.colorbar(image, ax=axis, fraction=0.03, pad=0.02)
    figure.tight_layout()
    path = OUT / "fig10_verb_object.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_name_distance(stats):
    rows = list(reversed(stats["name_links"]["labels"]))
    figure, axis = plt.subplots(figsize=(10.2, 8.6))
    positions = range(len(rows))
    colors = ["#2f6f5e" if row["within_threshold"] else "#c4a574" for row in rows]
    axis.barh(list(positions), [row["max_cosine_distance"] for row in rows], color=colors)
    axis.axvline(0.35, color="#8c3b2a", linewidth=1)
    axis.set_yticks(list(positions), [row["label"] for row in rows], fontsize=7)
    axis.set_xlabel("Max cosine distance to the nearest frozen group")
    axis.set_title("Later names against the 142 groups  |  line at 0.35")
    style_axes(axis)
    figure.tight_layout()
    path = OUT / "fig8_name_distance.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def draw_phases(stats):
    by_id = {row["id"]: row for row in stats["catalog"]}

    def box(event_id):
        row = by_id[event_id]
        return f"{row['label']}\n{event_id}\n{row['start']:.2f}–{row['end']:.2f}s"

    figure, axis = plt.subplots(figsize=(12.4, 6.2))
    axis.set_xlim(0, 12)
    axis.set_ylim(0, 4.6)
    axis.axis("off")
    later = by_id["E-aeec492759276f"]
    rows = [
        (3.7, "V30 single-lap", box("E-40558b96405bcc"), "same file as the double-lap trial; not one member"),
        (2.7, "V30 double-lap", box("E-281f02ffaf59dc"), "no arrow to the single-lap trial"),
        (1.7, "V27 overlap", box("E-8a5eec318093fd") + "\noverlaps\n" + box("E-2b87e891620d31"), "D12: 5.25 px, 80.37 deg, +344.7 px; not release"),
        (0.5, "V28 early / later", box("E-55b82c11e1c58f"), f"Remove clamp {later['id']} is {later['start']:.2f}–{later['end']:.2f}s; gap, no before-edge"),
    ]
    for y, title, text, note in rows:
        axis.text(0.1, y, title, fontsize=9, fontweight="bold", color="#17332c", va="center")
        axis.text(3.3, y, text, ha="left", va="center", fontsize=7,
                  bbox={"boxstyle": "round,pad=0.3", "facecolor": "#e7f0ec", "edgecolor": "#2f6f5e"})
        axis.text(11.8, y, note, ha="right", va="center", fontsize=7.5, color="#5d6b66")
    axis.set_title("Watched states with event id and media time  |  no cross-cut chain", loc="left", fontsize=11)
    figure.tight_layout()
    path = OUT / "fig9_phase_edges.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def page(stats):
    def group_row(item):
        return "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(item["group_id"]), esc(item["name"]), item["events"], item["checked"],
            esc(", ".join(item["cases"])), esc(", ".join(item["labels"])),
        )

    group_rows = "".join(group_row(item) for item in stats["semantic_groups"])
    cross_groups = sum(len(item["cases"]) >= 2 for item in stats["semantic_groups"])
    links = stats["name_links"]
    by_link = {row["label"]: row for row in links["labels"]}
    link_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{} {}</td><td>{}</td><td>{}</td></tr>".format(
            esc(row["label"]), row["events"], esc(", ".join(row["cases"])),
            esc(row["nearest_group_id"]), esc(row["nearest_group_name"]),
            row["max_cosine_distance"],
            "Within threshold" if row["within_threshold"] else "Outside threshold",
        )
        for row in stats["name_links"]["labels"]
    )
    header = "".join(f"<th>{esc(case)}</th>" for case in stats["case_order"])
    verb_rows = "".join(
        "<tr><td>{}</td><td>{}</td>{}</tr>".format(
            esc(row["verb"]), row["events"],
            "".join(f"<td>{cell if cell else ''}</td>" for cell in row["cells"]),
        )
        for row in stats["verb_matrix"]
    )
    layer_zh = {"historical_id": "Historical event ID", "same_name_outside_group": "New event with an existing name", "new_label": "New label"}
    catalog_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{:.2f}–{:.2f}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(row["case"]), row["task"], row["start"], row["end"], esc(row["label"]), esc(row["verb"]),
            esc(row["group_id"] or "—"), layer_zh[row["name_layer"]],
            "Frame checked" if row["frame_checked"] else "Label only",
        )
        for row in stats["catalog"]
    )
    sequence_rows = []
    for row in stats["within_video"]:
        def side(item):
            if not item:
                return "None"
            flag = "Adjacent" if item["adjacent"] else "Same source video, longer gap"
            return f"{esc(item['verb'])} ({item['gap_seconds']:+.1f}s，{flag})"
        sequence_rows.append(
            f"<tr><td>{esc(row['case'])}</td><td>{side(row['previous'])}</td><td>{esc(row['verb'])}</td><td>{side(row['next'])}</td></tr>"
        )
    counts = stats["counts"]
    scope = stats["grasp_scope"]
    lib = "../../../../Shared_analysis_library_2026-11-11/"

    def figures(items):
        cards = []
        for src, title, caption in items:
            cards.append(
                "<figure><img src=\"{}{}\" alt=\"{}\"><figcaption><strong>{}</strong> {}</figcaption></figure>".format(
                    lib, src, esc(title), esc(title), esc(caption),
                )
            )
        return "<div class=\"figs\">" + "".join(cards) + "</div>"

    case_figures = {
        "manual": [
            ("archive/outputs/research_state/diagram_delivery/current/D01.png", "D01", "In V01 the end enters a hole and hands are off-frame. The juxtaposition with V30 lacks a common physical scale and is not a matched human-robot comparison."),
            ("archive/outputs/research_state/diagram_delivery/D03_grasp_process/human_grasp_configuration_comparison.png", "D03 configuration", "In V06 hands are distributed along the panel edge with people beside the panel. V20 shows people below a module. Distributed grips alone do not establish a below-member position."),
            ("archive/outputs/research_state/diagram_delivery/D03_grasp_process/grasp_height_process.png", "D03 process", "Visible hands shift in relative height while lifting. Occluded points are omitted. The line between hands does not measure panel rotation in 3D."),
            ("archive/outputs/research_state/diagram_delivery/current/D04.png", "D04", "In V07 exposed fibres draw in toward the seam before the hand withdraws. Tension and full seam fastening are unmeasured."),
            ("archive/outputs/research_state/diagram_delivery/current/D05.png", "D05", "One V11 source shows people along the grid, while another shows fewer people at a joint. These are separate sequences. Headcount does not measure force or efficiency."),
            ("archive/outputs/ml_retrieval_evaluation/repaired_comparisons/figure_1.png", "C121", "V20 shows people beneath the module with hands overhead. The right panel shows V21 side transport, distinct from the drill comparison. The crop was selected for analysis and gives no new retrieval accuracy."),
        ],
        "mixed": [
            ("archive/outputs/research_state/diagram_delivery/current/D02.png", "D02", "In V04 the visible fixture extends along the beam and both ends are outside the frame. Apparent length is not the contact span. The joint clamp is absent from this frame."),
            ("archive/outputs/research_state/diagram_delivery/D07.png", "D07", "Handheld and mechanically supported drills in V21 use different access modes. Visible support does not establish clamping force or the full body envelope."),
            ("archive/outputs/research_state/diagram_delivery/current/D08.png", "D08", "V22 shows two panels attached to different arms. The wide shot does not show arms sharing one panel, and the later edge shot does not identify the same panel."),
            ("archive/outputs/research_state/diagram_delivery/D12_observed_turn/02_observed_turn_sequence.png", "D12 turning", "For V27 frames f95 to f96, the fixture reference point moves about 5.25 px, the axis turns about 80.37 degrees, and left overhang grows about 344.7 px. Pixel measures are uncalibrated. Leaving the frame does not establish release."),
            ("archive/outputs/research_state/diagram_delivery/D12_observed_turn/01_observed_phase_space.png", "D12 phase and space", "The same frame pair shows small grip-point movement and substantial turning. The earlier estimate of about 72 px uses a different pair."),
            ("archive/outputs/research_state/diagram_delivery/D06_metric_binding/V29_local_metric_comparison.png", "V29", "A short member is held locally with the arm extending to the side. Orange marks the grip and purple marks a nearby person. The metres refer to a reference plane rather than a surveyed floor."),
            ("archive/outputs/ml_retrieval_evaluation/repaired_comparisons/figure_3.png", "C152", "The left panel shows a wood block below a V22 panel and a tool near its edge. The right shows a kneeling V20 worker aligning one end. Both are distinct from the activities in the corresponding wide frames."),
        ],
        "robot": [
            ("archive/outputs/research_state/diagram_delivery/D09_tool_outline/tool_outline_comparison.png", "D09", "The V23 and V26 comparison uses the same sampled times. Tool-tip position omits the body. Each image is normalized independently, and both outlines are cropped. Physical clearance is not measured."),
            ("archive/outputs/research_state/diagram_delivery/D10.png", "D10", "Top view in V24 shows two grippers around one rod with a visible jaw opening. That observation alone does not measure load transfer."),
            ("archive/outputs/research_state/diagram_delivery/V28_joint_extension/01_roles_and_process.png", "V28 roles", "The holder and joint clamp have distinct roles along the diagonal beam. Synchrony comes from the source report. Force and minimum clearance were not measured."),
            ("archive/outputs/research_state/diagram_delivery/V28_joint_extension/03_clamp_space.png", "V28 withdrawal", "Clamp withdrawal comes from the source model and member identity remains conditional_not_confirmed. Holding at 40 seconds and clamp removal at 195 seconds do not form a continuous observed sequence."),
            ("archive/outputs/research_state/diagram_delivery/D13_access_path/layout_tradeoff.png", "D13", "Conditional model with baseline interface spacing 959.2105 mm, grip margin 284.6053 mm, and yaw 0.0573 degrees. Wider spacing increases the margin and reduces allowable yaw. These are not video-derived success rates."),
            ("archive/outputs/ml_retrieval_evaluation/repaired_comparisons/figure_2.png", "C096", "The V11 image shows workers at different heights near the grid. The V26 image shows holding a box, distinct from the D09 nailer. The two observations are kept separately."),
        ],
    }

    def scope_line(rows):
        events = sum(row["events"] for row in rows)
        checked = sum(row["checked"] for row in rows)
        return f"{len(rows)} groups and {events} events, including {checked} of the 38 focus events"

    def case_text(row):
        return ", ".join(f"{item['case']}×{item['events']}" for item in row["cases"])

    def label_text(row):
        parts = [
            f"{item['label']} ({item['events']}; {', '.join(item['cases'])})"
            for item in row["labels"][:6]
        ]
        extra = len(row["labels"]) - 6
        if extra > 0:
            parts.append(f"{extra} additional original labels")
        return "; ".join(parts)

    def neighbor_text(items):
        if not items:
            return "—"
        return ", ".join(f"{item['name']}×{item['events']}" for item in items[:4])

    by_family = {row["name"]: row for row in stats["families"]}
    multi_case_families = sum(len(row["cases"]) >= 2 for row in stats["families"])
    family_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(row["name"]), row["events"], row["checked"], len(row["cases"]),
            esc(case_text(row)), esc(label_text(row)),
        )
        for row in stats["families"]
    )
    adjacent_family_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(row["name"]), row["events"], esc(neighbor_text(row["before"])), esc(neighbor_text(row["after"])),
        )
        for row in stats["families"]
        if row["before"] or row["after"]
    )
    body = f"""
<h1>Semantic groups, assembly frequencies, and grasp configurations</h1>
<p><a href="similarity/index.html">Similarity ranges</a>. <a href="figures_en/index.html">Full-corpus figures</a>. The name-similarity threshold can be adjusted across all 549 actions. The 142 historical groups stay fixed. The figures do not use video time.</p>
<p>The semantic grouping uses all {counts['actions']} Label Studio actions. The retrieval top-five budget originally limited which candidates could be reviewed for each method. It does not limit this analysis. The full catalog is below.</p>
<p>{counts['events_in_historical_groups']} events match the {counts['historical_groups']} historical candidate groups, built with complete linkage and a cosine distance of 0.35. They are not confirmed operation classes. Embeddings and membership were reused. The {counts['events_outside_historical_groups']} ungrouped event IDs represent {counts['labels_outside_historical_groups']} labels. Move appears 49 times in eight cases, Hold 48 times in ten, and Insert seven times in V30. Checked frames provide a subset with comparable physical evidence. The 75 extracted verbs are lexical features. Manipulate panel interface by hand stays as its original phrase under the specified rule. Hold, Keep, and Maintain need not describe distinct physical behaviors. Case classifications describe the overall workflow rather than every performer.</p>
<p>The comparison dimensions cover interface, process, and spatial phase. Separately, dominant assembly mode divides the 15 cases into five human-led, five hybrid, and five robot-led cases. The October 20 classification held five, four, and three labeled cases, respectively. V29 joins the hybrid group and V23 and V30 join the robot-led group. Robot-led projects can still include manual preparation or finishing.</p>
<ul>
<li>Human-led assembly: V01, V06, V07, V11, V20.</li>
<li>Hybrid assembly: V04, V21, V22, V27, V29.</li>
<li>Robot or automation-led assembly: V23, V24, V26, V28, V30.</li>
</ul>
<h2>How the earlier figures support the analysis</h2>
<p>The frequency figures are generated here. Retrieval candidates use the original three corrected process figures and their 18 existing frames. Architectural comparisons reuse D01 through D13 and the V28 and V29 figures. See <a href="reuse/reuse_plan.html">reuse/reuse_plan.html</a>.</p>
{figures([
    ("archive/outputs/ml_retrieval_evaluation/repaired_comparisons/figure_1.png", "C121 operator and hand positions", "V20 shows people below the module. The right-hand V21 image shows side transport rather than a mounted drill."),
    ("archive/outputs/ml_retrieval_evaluation/repaired_comparisons/figure_2.png", "C096 grasp arrangement", "V11 shows workers at different heights near the grid. The V26 image shows box handling rather than a nailer."),
    ("archive/outputs/ml_retrieval_evaluation/repaired_comparisons/figure_3.png", "C152 support and tool positions", "V22 shows the block below the panel and the tool near its edge. V20 shows one person kneeling for alignment, distinct from the three people below the module."),
])}
<p class="small">The three corrected figures use AI-prefilled reviews and analyst-selected boundaries. The examples illustrate retrieval candidates and do not report new accuracy or combine independent frames.</p>
<img src="fig5_installation_groups.png" alt="Verbs by installation group">
<p class="small">The left chart counts the same verbs across three modes, while the right chart uses minutes of annotation. V27 has a short, densely annotated window that raises Move and Keep in the hybrid group without establishing faster assembly. Handle is most frequent in the human-led group, Keep appears only in hybrid, and Place occurs mainly in robot-led cases.</p>
<h2>Within each assembly mode</h2>
<p>Each panel below contains the five cases in one assembly mode. Columns show that mode's most frequent verbs. Cells report events and source counts. Blank cells indicate that the verb is absent for the case.</p>
<img src="fig6_within_groups.png" alt="Comparisons inside each installation group">
<p>The figures show which verbs occur. The paired analysis figures illustrate how configurations differ within one mode.</p>
{''.join(
    '<h3>' + esc(group['zh']) + '</h3><ul>' + ''.join(f'<li>{esc(line)}</li>' for line in group['within']['reading']) + '</ul>' + figures(case_figures[group['key']])
    for group in stats['installation']
)}
<h2>All historical semantic groups</h2>
<p>The table lists all {counts['historical_groups']} historical groups. {cross_groups} span two or more cases and the others occur in one case. Frame checks count membership in the original 38 focus events. Shared group membership indicates related action names and does not determine grasp configuration.</p>
<div class="scroll"><table><tr><th>Group</th><th>Representative label</th><th>Events</th><th>Frame checked</th><th>Cases</th><th>Labels</th></tr>{group_rows}</table></div>
<h2>Historical IDs, ungrouped events, and new labels</h2>
<p>The 92 unmatched items are event IDs. {sum(row['name_layer']=='same_name_outside_group' for row in stats['catalog'])} reuse historical labels: four Hold member and one Open gripper. The remaining {sum(row['name_layer']=='new_label' for row in stats['catalog'])} use labels absent from the historical table. The complete-linkage threshold of 0.35 is met by 29 events and {len({row['label'] for row in stats['catalog'] if row['vector_candidate']})} labels, including those five same-name events. This check does not refit clustering or change group membership.</p>
<img src="fig8_name_distance.png" alt="Distance of later names to frozen groups">
<div class="scroll"><table><tr><th>Label</th><th>Events</th><th>Cases</th><th>Nearest group</th><th>Maximum cosine distance</th><th>Original rule</th></tr>{link_rows}</table></div>
<h2>All verbs across all cases</h2>
<p>The charts highlight the 12 most frequent verbs. The table includes {len(stats['verb_matrix'])} verbs across 15 cases; blanks represent zero. {counts['actions'] - sum(row['events'] for row in stats['verb_matrix'])} labels, including Mallet, have no extracted verb and remain in the full catalog. Charts distinguish event counts from source counts and use the union of annotated intervals for rates. These are not labor-time measurements. V30 is marked 5x and V27 has overlapping annotations concentrated in a short window. Heatmap colors cap at 20 while cell labels retain actual rates.</p>
<img src="fig1_verb_counts.png" alt="Verb counts">
<img src="fig2_case_verb_heatmap.png" alt="Case by verb heatmap">
<p class="small">Rows follow the human-led, hybrid, and robot-led groups. Cells show event counts and source counts. Rule: {esc(stats['verb_rule'])}</p>
<h2>Annotation coverage</h2>
<p>The left chart shows interval lengths for all 549 annotations. The right chart separates the union of annotated intervals, excess overlap, and unannotated gaps within each source-video span. These are video times. V30 is marked 5x and the durations do not measure work time.</p>
<img src="fig7_duration_coverage.png" alt="Annotated duration and coverage">
<h2>Verb and object co-occurrence</h2>
<p>Cells report events and source videos. Object terms come from the action text and are not individually confirmed physical roles. The chart includes the most frequent 18 verbs with at least three co-occurrences and caps the color scale at 20. Temporal co-occurrence does not establish load bearing or a required step.</p>
<img src="fig10_verb_object.png" alt="Verb and object token co-occurrence">
<div class="scroll"><table><tr><th>Verb</th><th>Events</th>{header}</tr>{verb_rows}</table></div>
<h2>Verbs by comparison dimension</h2>
<p>Dark bars show events with frames checked for the dimension. Light bars show related historical-group or same-name events without frame review. Events can contribute to multiple dimensions; semantic proximity is not physical evidence.</p>
<img src="fig3_type_small_multiples.png" alt="Three comparison types">
<ul>
<li>Interface and grip: {stats['types']['interface_grip']['checked_events']} checked and {stats['types']['interface_grip']['neighbor_events']} related events.</li>
<li>Process: {stats['types']['process']['checked_events']} checked and {stats['types']['process']['neighbor_events']} related events.</li>
<li>Phase and space: {stats['types']['phase_space']['checked_events']} checked and {stats['types']['phase_space']['neighbor_events']} related events.</li>
</ul>
<h2>Shared action labels and different configurations</h2>
<p>The table lists {len(stats['families'])} families across 15 cases, including {multi_case_families} found in two or more cases. Insert has {by_family['Insert']['events']} events in V30 alone. Move has {by_family['Move']['events']} events in {len(by_family['Move']['cases'])} cases, with {by_family['Move']['checked']} checked. Hold has {by_family['Hold']['events']} events in {len(by_family['Hold']['cases'])} cases, with {by_family['Hold']['checked']} checked. Attempt joint insertion belongs to Attempt. An extracted verb does not specify a single grasp.</p>
<div class="scroll"><table><tr><th>Family</th><th>Events</th><th>Frame checked</th><th>Case count</th><th>Cases</th><th>Original labels, counts and cases</th></tr>{family_rows}</table></div>
<p>Observed differences concern interfaces, grip points, operators, and member orientation. Unreviewed cases stay in the catalog with these properties unspecified. Camera viewpoint and annotation span do not measure grasp angle or time.</p>
<ul>
<li>In D02, V04 distributes holding along the beam. V28 concentrates holding on one section and uses a separate joint clamp.</li>
<li>V29 uses a local grip on a short member. The arm extends sideways and the person with the pendant does not hold the member.</li>
<li>The V24 top view shows a rod shared by two bench grippers and a gap between a jaw and the rod. Completion of transfer is unassessed.</li>
<li>D03 contrasts workers beside a V06 panel with workers under a V20 module. Distributed gripping alone does not imply a below-member position.</li>
<li>The V22 wide shot in D08 shows separate panels connected to separate arms.</li>
<li>D01 compares V30 gripping between interfaces to V01 entering a hole with the member end. Both involve insertion with different interfaces and grasp locations.</li>
</ul>
{figures([
    ("archive/outputs/research_state/diagram_delivery/current/D02.png", "D02 arranged along a beam", "The V04 gripper extends along the beam beyond both sides of the frame. The grip coverage differs from V28, and the joint clamp is absent here."),
    ("archive/outputs/research_state/diagram_delivery/D10.png", "D10 opening the jaws", "Two grippers hold the same rod in V24. A visible gap does not establish completed load transfer."),
    ("archive/outputs/research_state/diagram_delivery/D03_grasp_process/human_grasp_configuration_comparison.png", "D03 beside and below", "People stand beside the panel in V06 and under the module in V20. These are different spatial configurations."),
    ("archive/outputs/research_state/diagram_delivery/current/D08.png", "D08 two panels", "Each arm is connected to a separate panel. Multiple arms in the same setting need not hold one item together."),
    ("archive/outputs/research_state/diagram_delivery/current/D01.png", "D01 two forms of insertion", "V01 shows an end entering a hole and V30 shows intersecting beams. The joint interfaces and grasp positions differ."),
    ("archive/outputs/research_state/diagram_delivery/D06_metric_binding/V29_local_metric_comparison.png", "V29 short member", "The short member is held locally. The nearby person is not holding it. Reference-plane metres are not ground calibration."),
])}
<p>Compare interface, grip points, operator, and orientation separately even when labels match. Unreviewed cases keep those fields unspecified.</p>
<h2>Shared actions and different process sequences</h2>
<p>Start and end frames are verified for the three sequences below. Remaining families use neighboring labels within 15 seconds in the same source video. This gives annotation order rather than observed phases or necessary steps. Time streams stay separate across videos.</p>
<ul>
<li>In V30, the member is held on two sides with a visible clearance in the approach. Later the surfaces meet or the member lowers into an opening. The conditional D13 dimensions do not measure that video sequence.</li>
<li>In V27 the member turns flat after holding and its far end sweeps outward. The grip point moves little while the envelope changes. Release stays unassessed.</li>
<li>In V28 a member holder operates beside a joint clamp and later a person handles a clamp. The captions are recorded separately from observed jaw motion.</li>
</ul>
{figures([
    ("archive/outputs/research_state/diagram_delivery/D13_access_path/layout_tradeoff.png", "D13 conditional model", "Millimetres and yaw refer to this diagram. The video evidence only shows surfaces meeting or a member lowering into an opening."),
    ("archive/outputs/research_state/diagram_delivery/D13_access_path/grip_interface_access.png", "D13 grasp and interface", "Grips remain between outer interfaces under the modeled conditions. Clearance is not measured from the video."),
    ("archive/outputs/research_state/diagram_delivery/D12_observed_turn/02_observed_turn_sequence.png", "D12 grip and far end", "The grip shifts about 5.25 px and overhang increases about 344.7 px. The operating envelope changes after holding, while release remains unassessed."),
    ("archive/outputs/research_state/diagram_delivery/V28_joint_extension/01_roles_and_process.png", "V28 holding and closing", "The member holder and joint clamp have separate roles. Later manual removal is not represented as the next observed frame."),
    ("archive/outputs/research_state/diagram_delivery/V28_joint_extension/03_clamp_space.png", "V28 modeled withdrawal", "The source model provides the withdrawal path. There is no before relation from the hold at 40 seconds to clamp removal at 195 seconds."),
])}
<p>Check identical action labels by phase. During approach, check the grip against the interface; during a turn, check the far-end envelope; and before release, check which device still holds the member. The table shows nearby annotations and highlights sequences still to review.</p>
<div class="scroll"><table><tr><th>Family</th><th>Events</th><th>Preceding label within 15 seconds in the same video</th><th>Following label</th></tr>{adjacent_family_rows}</table></div>
<p>The figure labels checked event IDs and video times. V30 single and double laps are separated by other trials. V27 labels overlap, and D12 provides 5.25 px, 80.37 degrees, and +344.7 px measurements. V28 removal after 195 seconds and holding at 40 seconds do not form an observed before relation.</p>
<img src="fig9_phase_edges.png" alt="Watched states with event ids">
<p class="small">The table gives preceding and following labels in each source video for locating clips. Gaps over 15 seconds are marked; they are not classified as adjacent steps. It does not establish a process phase.</p>
<table><tr><th>Case</th><th>Preceding label in source video</th><th>Current label</th><th>Following label</th></tr>{''.join(sequence_rows)}</table>
<h2>Design checks</h2>
<p>These observations do not establish frequencies of physical configurations. Move has {by_family['Move']['events']} events across {len(by_family['Move']['cases'])} cases, but only the V27 frame pair measures a turn. Hold has {by_family['Hold']['events']} events across {len(by_family['Hold']['cases'])} cases, and V28 does not establish a common role division. All {by_family['Insert']['events']} Insert events are in V30, with separate single- and double-lap trials. Compare interfaces, grip points, operators, and secondary devices case by case.</p>
<p>The three examples test the process format. The grasp table separates the visible extent, camera viewpoint, and operator position: V04 is viewed from below with unknown operator side, whereas V20 has operators below with unknown camera viewpoint. Device length does not measure contact span. The V23 and V26 nailers remain tool comparisons. Labels in S009, S017, and S028 retain distinct actions.</p>
{figures([
    ("archive/outputs/research_state/diagram_delivery/D09_tool_outline/tool_outline_comparison.png", "Tool body check", "The tip position alone does not represent the visible envelope. V23 and V26 belong to the tool comparison and add no grasp samples."),
    ("archive/outputs/research_state/diagram_delivery/D06_module_space/outside_member_analysis.png", "Operator position in projection", "Bodies on the human side lie within the end strips. On the robot side, the arm extends from the base and approximately 62 to 65 percent of the outline lies outside the strips. These are 2D layouts of two frames, not measured floor occupation or efficiency."),
    ("archive/outputs/research_state/diagram_delivery/design_checks/01_design_layers.png", "Four design checks", "Separate holding from closing, check the full tool body, then verify access and withdrawal and the placement of people and surrounding members. The 40 mm and 80 mm scenarios are assumptions. Source-model dimensions are not video clearance measurements."),
    ("archive/outputs/research_state/diagram_delivery/current/claim_evidence_overview.png", "Findings and primary figures", "R01 through R04 preserve the original evidence hierarchy. Repeat frames and parameter sweeps are not independent cases."),
])}
<img src="fig4_grasp_board.png" alt="Grasp board and adjacent labels">
<p>Reviewed grasp-related examples cover V01, V04, V06, V11, V20, V22, V24, V27, V28, V29, and V30. Historical labels containing hold cover {scope_line(scope['hold'])}; transport covers {scope_line(scope['transport'])}. Those groups can include nailing or placement. Insert occurs in {scope['insert_events']} labels, all in {esc(', '.join(scope['insert_cases']))}; {scope['insert_checked']} were frame-checked and {scope['insert_in_historical_groups']} belong to the 142 historical groups. Expanding review requires evidence and phase context for every record.</p>
<p>Pair provenance varies. D02, D03, and D08 reuse intentionally selected project figures. D01, D12, and D13 are also existing comparisons. The V30 endpoints, V28 roles, and V27 uncertainty about release address process questions. V24 jaw clearance and the V29 short member come from checked notes. Historical V23/V26 scores met the image threshold only, and the original discovery path stays unknown.</p>
<p>No new SentenceTransformer retrieval experiment or accuracy result is reported. Formal human relevance review is still required to assess accuracy.</p>
<h2>All 549 actions</h2>
<p>The catalog includes every Label Studio action. Historical IDs have group labels. Ungrouped events with known names are distinct from new labels. Frame checks cover the original focus events.</p>
<input id="catalog-filter" type="search" placeholder="Filter by case, label, verb, or group">
<div class="scroll"><table id="catalog"><thead><tr><th>Case</th><th>Task</th><th>Video time</th><th>Label</th><th>Verb or original phrase</th><th>Historical group</th><th>Label status</th><th>Frame</th></tr></thead><tbody>{catalog_rows}</tbody></table></div>
<script>
document.getElementById("catalog-filter").addEventListener("input", function () {{
  var query = this.value.toLowerCase();
  document.querySelectorAll("#catalog tbody tr").forEach(function (row) {{
    row.style.display = row.textContent.toLowerCase().indexOf(query) >= 0 ? "" : "none";
  }});
}});
</script>
"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Semantic groups and assembly frequencies</title>
<style>
body{{margin:0;background:#f3efe7;color:#24362f;font:16px/1.6 "Segoe UI",sans-serif}}
main{{max-width:1180px;margin:auto;padding:28px 20px 64px}}
img{{max-width:100%;height:auto;background:white;border:1px solid #ddd4c8;border-radius:8px;margin:12px 0}}
.figs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:14px;margin:12px 0 28px}}
.figs figure{{margin:0;background:white;border:1px solid #ddd4c8;border-radius:8px;padding:10px 12px 12px}}
.figs img{{margin:0;border:0;border-radius:4px}}
.figs figcaption{{font-size:14px;color:#3e514b;margin-top:8px}}
table{{border-collapse:collapse;width:100%;background:white}} th,td{{border-bottom:1px solid #eee;padding:8px;vertical-align:top;text-align:left}}
.small{{color:#5d6b66;font-size:14px}}
.scroll{{overflow:auto;max-height:70vh;border:1px solid #ddd4c8;background:white;margin:12px 0}}
.scroll th{{position:sticky;top:0;background:#f7f3ec}}
input{{padding:8px 10px;width:min(480px,100%);border:1px solid #cfc4b4;border-radius:6px}}
</style></head><body><main>{body}</main></body></html>"""


def check_page(path):
    text = path.read_text(encoding="utf-8")
    for token in ("src=\"", "href=\""):
        start = 0
        while True:
            found = text.find(token, start)
            if found < 0:
                break
            end = text.find("\"", found + len(token))
            link = text[found + len(token):end]
            if not link.startswith(("http://", "https://")):
                target = path.parent / link.split("#")[0]
                if not target.exists():
                    raise RuntimeError(f"Missing link {link}")
            start = end + 1


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    events = load_events()
    groups = load_groups()
    membership, missing = join_groups(events, groups)
    stats = build_statistics(events, groups, membership, missing)
    if stats["counts"]["events_in_historical_groups"] != 457:
        raise RuntimeError("Historical join changed")
    if len(stats["catalog"]) != 549 or sum(row["group_id"] is not None for row in stats["catalog"]) != 457:
        raise RuntimeError("The full action catalog is not 549 with 457 grouped")
    if len(stats["semantic_groups"]) != 142:
        raise RuntimeError("Semantic group table is not the full 142")
    if len(stats["verb_matrix"]) != 75:
        raise RuntimeError("Verb matrix is not the full verb list")
    families = {row["name"]: row for row in stats["families"]}
    if sum(row["events"] for row in stats["families"]) != 549:
        raise RuntimeError("Semantic families dropped actions")
    if families["Move"]["events"] != 49 or len(families["Move"]["cases"]) != 8 or families["Move"]["checked"] != 2:
        raise RuntimeError("Move is not 49 events across 8 cases with 2 checked")
    if families["Hold"]["events"] != 48 or len(families["Hold"]["cases"]) != 10 or families["Hold"]["checked"] != 1:
        raise RuntimeError("Hold is not 48 events across 10 cases with 1 checked")
    if families["Insert"]["events"] != 7 or [item["case"] for item in families["Insert"]["cases"]] != ["V30"]:
        raise RuntimeError("Insert is not 7 events, all in V30")
    if "Attempt" not in families:
        raise RuntimeError("Attempt joint insertion was merged into Insert")
    links = stats["name_links"]
    if links["new_embeddings"] or links["groups_rewritten"] or links["events"] != 92:
        raise RuntimeError("Name-link test did not cover the 92 ungrouped actions")
    if links["within_threshold_events"] != 29 or links["outside_threshold_events"] != 63:
        raise RuntimeError("Name-link counts changed; rewrite the paragraph")
    same_name = [row for row in stats["catalog"] if row["name_layer"] == "same_name_outside_group"]
    if len(same_name) != 5 or sorted(row["label"] for row in same_name) != ["Hold member"] * 4 + ["Open gripper"]:
        raise RuntimeError("Same-name new events are not the 4 Hold member and 1 Open gripper")
    if sum(row["name_layer"] == "new_label" for row in stats["catalog"]) != 87:
        raise RuntimeError("New-label event count is not 87")
    if len({row["label"] for row in stats["catalog"] if row["vector_candidate"]}) != 9:
        raise RuntimeError("Threshold hits are not 9 labels")
    board = {row["case"]: row for row in stats["grasp_board"]}
    if board["V04"]["operator_side"] != "unknown" or board["V04"]["camera"] == "unknown":
        raise RuntimeError("V04 still mixes camera viewpoint into the operator column")
    if board["V20"]["camera"] != "unknown" or "under" not in board["V20"]["operator_side"]:
        raise RuntimeError("V20 operator side is no longer the people under the module")
    by_label = {row["label"]: row for row in links["labels"]}
    if by_label["Insert joint"]["within_threshold"] or by_label["Open gripper"]["nearest_group_id"] != "S009":
        raise RuntimeError("Insert or Open gripper link no longer matches the stored vectors")
    if any(row["case"] in {"V23", "V26"} for row in stats["grasp_board"]):
        raise RuntimeError("Tool cases were added to the grasp board")
    if any(stats["grasp_column_is_constant"].values()):
        raise RuntimeError("A grasp column became constant; rewrite the commonality before publishing it")
    scope = stats["grasp_scope"]
    if sum(row["events"] for row in scope["hold"]) != 67 or sum(row["checked"] for row in scope["hold"]) != 2:
        raise RuntimeError("Hold-group coverage changed; rewrite the scope sentence")
    if sum(row["events"] for row in scope["transport"]) != 21 or sum(row["checked"] for row in scope["transport"]) != 3:
        raise RuntimeError("Transport-group coverage changed; rewrite the scope sentence")
    if scope["insert_events"] != 9 or scope["insert_in_historical_groups"] != 0:
        raise RuntimeError("Insert coverage changed; rewrite the scope sentence")
    if [len(group["cases"]) for group in INSTALLATION] != [5, 5, 5]:
        raise RuntimeError("Installation groups are not 5, 5 and 5")
    if set(CASES) != set(CASE_GROUP):
        raise RuntimeError("A case is missing from the installation groups")
    figures = [
        draw_verb_bars(stats), draw_heatmap(stats), draw_installation(stats), draw_within(stats),
        draw_types(stats), draw_board(stats), draw_coverage(stats), draw_verb_object(stats),
        draw_name_distance(stats), draw_phases(stats),
    ]
    for figure in figures:
        if figure.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"{figure.name} is not a PNG")
    public_membership = {
        "schema": "multicam-semantic-membership-v1",
        "groups_sha256": sha256_file(GROUPS_PATH),
        "events": [
            {
                "event_id": event["id"],
                "case": event["case"],
                "label": event["label"],
                "verb": verb_of(event["label"]),
                "group": membership.get(event["id"]),
                "types": event_types(event["id"]),
                "frame_checked": event["id"] in get_notes(),
            }
            for event in events
        ],
    }
    write_json(OUT / "membership.json", public_membership)
    write_json(OUT / "verb_statistics.json", stats)
    index = OUT / "index.html"
    index.write_text(page(stats), encoding="utf-8")
    check_page(index)
    readme = """Semantic groups and assembly frequencies

Open index.html for the generated report. Run python semantic_spread.py to build.
See the repository research README for the action index, read-only baseline
groups and embeddings, local historical evidence, and linked figure assets.

Historical groups and embeddings are reused. The catalog includes all 549
actions. Annotation time is the union of labeled intervals, not labor time.
"""
    (OUT / "README.txt").write_text(readme, encoding="utf-8")
    write_json(OUT / "verification.json", {
        "schema": "multicam-semantic-spread-verification",
        "passed": True,
        "actions": 549,
        "historical_groups": 142,
        "events_joined": 457,
        "events_ungrouped": stats["counts"]["events_outside_historical_groups"],
        "ungrouped_labels": stats["counts"]["labels_outside_historical_groups"],
        "installation_groups": {group["id"]: group["cases"] for group in INSTALLATION},
        "tool_cases_excluded_from_grasp_board": ["V23", "V26"],
        "figures": [path.name for path in figures],
        "model_calls": 0,
        "training": False,
        "loss": None,
        "new_embeddings": False,
        "frequency_is_design_rank": False,
        "top5_used": False,
        "catalog_rows": len(stats["catalog"]),
        "semantic_groups": len(stats["semantic_groups"]),
        "verbs": len(stats["verb_matrix"]),
    })
    print(json.dumps({
        "out": str(OUT),
        "joined": 457,
        "ungrouped": stats["counts"]["events_outside_historical_groups"],
        "figures": [path.name for path in figures],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
