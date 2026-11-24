"""Process groups for V30 insertion, V28 holding/clamps, and V27 move/turn.

Edges keep action time separate from object contact. Missing steps stay missing.
"""
from __future__ import annotations

from context_common import historical_text, sha256_text


def _event(inputs, event_id):
    return next(item for item in inputs["events"] if item["id"] == event_id)


def _span(inputs, event_ids):
    rows = [_event(inputs, event_id) for event_id in event_ids]
    return min(row["start"] for row in rows), max(row["end"] for row in rows)


def _episode(inputs, episode_id, group_id, event_ids, goal, phases, active, target, participants,
             completeness, cut_status, source_kinds, origin, unknowns, findings):
    event_ids = sorted(event_ids, key=lambda event_id: (_event(inputs, event_id)["start"], event_id))
    start, end = _span(inputs, event_ids)
    first = _event(inputs, event_ids[0])
    return {
        "episode_id": episode_id,
        "group_id": group_id,
        "case": first["case"],
        "task": first["task"],
        "source_video_sha256": first["source_sha256"],
        "goal": goal,
        "goal_status": "agent_candidate",
        "phase": phases,
        "active_component": active,
        "target_component": target,
        "participants": participants,
        "event_ids": event_ids,
        "start": start,
        "end": end,
        "clock": "label_studio_source_clock",
        "cut_status": cut_status,
        "completeness": completeness,
        "steps_added": False,
        "source_kinds": source_kinds,
        "origin": origin,
        "human_confirmed": False,
        "unknowns": unknowns,
        "frame_findings": findings,
    }


def _relation(rel_id, edge_class, rel_type, source, target, source_kind, evidence_ids, note, not_implied):
    return {
        "relation_id": rel_id,
        "edge_class": edge_class,
        "type": rel_type,
        "source": source,
        "target": target,
        "source_kind": source_kind,
        "evidence_ids": evidence_ids,
        "status": "agent_candidate",
        "human_confirmed": False,
        "note": note,
        "not_implied": not_implied,
    }


def _v30_catalog(inputs):
    episodes = []
    for item in inputs["episodes"]:
        origins = item.get("origins") or []
        if not origins:
            continue
        record = origins[0]["record"]
        episode_id = record.get("id") or record.get("episode_id")
        if not episode_id or not str(episode_id).startswith("EP-V30-"):
            continue
        event_ids = item["event_ids"]
        descriptions = [_event(inputs, event_id)["description"] for event_id in event_ids]
        topology = "unspecified"
        text = " ".join(descriptions)
        if "single-lap" in text:
            topology = "single-lap"
        elif "double-lap" in text or "H-shaped" in text:
            topology = "H-shaped double-lap"
        incomplete = historical_text("episode_relations:85:21") in text
        focus = {"E-40558b96405bcc", "E-281f02ffaf59dc"} & set(event_ids)
        episodes.append(_episode(
            inputs, episode_id, "GRP-V30-insertion", event_ids,
            historical_text("episode_relations:89:12"),
            ["approach", "insertion"],
            {"label": "gripped timber member", "identity": "trial_local", "status": "agent_candidate"},
            {"label": "mating joint", "topology_from_source_text": topology, "status": "agent_candidate"},
            ["robot gripper", "active member", "mating member"],
            "partial_approach_then_insert" if not incomplete else "source_text_says_mating_still_incomplete",
            "one_source_clock_two_abutting_actions",
            ["video_observed"],
            f"episode_candidates:{item['id']}",
            [historical_text("episode_relations:98:13"), historical_text("episode_relations:98:28"), historical_text("episode_relations:98:43")],
            [historical_text("episode_relations:99:13")] if not focus else [
                historical_text("episode_relations:100:16") if topology == "single-lap"
                else historical_text("episode_relations:101:21"),
                historical_text("episode_relations:102:16"),
            ],
        ))
    episodes.sort(key=lambda item: item["start"])
    return episodes


def process_boards():
    return [
        {
            "id": "BOARD-V30",
            "case": "V30",
            "question": historical_text("episode_relations:114:24"),
            "video": "task44.mp4",
            "clips": [{"label": historical_text("episode_relations:116:32"), "start": 50.48, "end": 55.48},
                      {"label": historical_text("episode_relations:117:32"), "start": 130.00, "end": 136.48}],
            "frames": [
                {"file": "task44_001262.jpg", "frame": 1262, "seconds": 50.48, "label": "Single-lap start", "kind": "video_observed",
                 "text": historical_text("episode_relations:120:25")},
                {"file": "task44_001387.jpg", "frame": 1387, "seconds": 55.48, "label": "Single-lap end", "kind": "video_observed",
                 "text": historical_text("episode_relations:122:25")},
                {"file": "task44_003250.jpg", "frame": 3250, "seconds": 130.00, "label": "Double-lap start", "kind": "video_observed",
                 "text": historical_text("episode_relations:124:25")},
                {"file": "task44_003412.jpg", "frame": 3412, "seconds": 136.48, "label": "Double-lap end", "kind": "video_observed",
                 "text": historical_text("episode_relations:126:25")},
            ],
            "relations": [
                {"type": "holds", "kind": "video_observed", "text": "Gripper holds the member from both sides, inside the outer joint zones."},
                {"type": "interface", "kind": "video_observed", "text": "Single lap has one visible interface. Double lap has two outer interfaces."},
                {"type": "conditional model", "kind": "model_conditional", "text": "D13, fixed D/J/W/b: larger interface span S increases central grip allowance U and reduces the shared yaw limit. Baseline S 959.2 mm, U 284.6 mm, yaw 0.0573°. The video does not measure these millimetres."},
            ],
            "difference": historical_text("episode_relations:133:26"),
            "not_required": [historical_text("episode_relations:134:29"), historical_text("episode_relations:134:40"), historical_text("episode_relations:134:48")],
        },
        {
            "id": "BOARD-V28",
            "case": "V28",
            "question": historical_text("episode_relations:139:24"),
            "video": "task28.mp4",
            "clips": [{"label": historical_text("episode_relations:141:32"), "start": 40.00, "end": 61.47},
                      {"label": historical_text("episode_relations:142:32"), "start": 195.50, "end": 198.47}],
            "frames": [
                {"file": "task28_001200.jpg", "frame": 1200, "seconds": 40.00, "label": "Holder and clamp", "kind": "video_observed",
                 "text": historical_text("episode_relations:145:25")},
                {"file": "task28_001627.jpg", "frame": 1627, "seconds": 54.23, "label": "Caption: jammed", "kind": "video_caption_reported",
                 "text": historical_text("episode_relations:147:25")},
                {"file": "task28_001844.jpg", "frame": 1844, "seconds": 61.47, "label": "Caption: path planned", "kind": "video_caption_reported",
                 "text": historical_text("episode_relations:149:25")},
                {"file": "task28_005865.jpg", "frame": 5865, "seconds": 195.50, "label": "Person at clamp", "kind": "video_observed",
                 "text": historical_text("episode_relations:151:25")},
            ],
            "relations": [
                {"type": "holds", "kind": "video_observed", "text": "Member holder grips the beam body."},
                {"type": "visible contact", "kind": "video_observed", "text": "A separate interface clamp sits at the joint."},
                {"type": "collaborates", "kind": "video_observed", "text": "A person handles an interface clamp. Same assembly goal, different role."},
                {"type": "caption", "kind": "video_caption_reported", "text": "Jam, retry, planned path and manual-step wording are on-screen captions."},
                {"type": "saved route", "kind": "model_conditional", "text": "b21 withdrawal, 20 mm then 100 mm, stays a source-model edge."},
            ],
            "difference": historical_text("episode_relations:160:26"),
            "not_required": [historical_text("episode_relations:161:29"), historical_text("episode_relations:161:43"), historical_text("episode_relations:161:57")],
        },
        {
            "id": "BOARD-V27",
            "case": "V27",
            "question": historical_text("episode_relations:166:24"),
            "video": "task24.mp4",
            "clips": [{"label": historical_text("episode_relations:168:32"), "start": 3.76, "end": 3.96}],
            "frames": [
                {"file": "task24_000094.jpg", "frame": 94, "seconds": 3.76, "label": "Before the turn", "kind": "video_observed",
                 "text": historical_text("episode_relations:171:25")},
                {"file": "task24_000096.jpg", "frame": 96, "seconds": 3.84, "label": "After the turn", "kind": "video_observed",
                 "text": historical_text("episode_relations:173:25")},
                {"file": "task24_000099.jpg", "frame": 99, "seconds": 3.96, "label": "Following frame", "kind": "video_observed",
                 "text": historical_text("episode_relations:175:25")},
            ],
            "relations": [
                {"type": "grip point", "kind": "video_observed", "text": "Existing D12 measurement, not redone: f95 to f96 grip reference moves 5.25 px."},
                {"type": "member axis", "kind": "video_observed", "text": "The same step changes the visible axis by about 80.37°."},
                {"type": "far end", "kind": "video_observed", "text": "Left extension increases by about 344.7 px. The sweep belongs to the member end, not the grip point."},
            ],
            "difference": historical_text("episode_relations:182:26"),
            "not_required": [historical_text("episode_relations:183:29"), historical_text("episode_relations:183:40"), historical_text("episode_relations:183:62")],
        },
    ]


def build_episode_relations(inputs):
    episodes = []
    relations = []

    episodes.extend(_v30_catalog(inputs))
    relations.append(_relation(
        "REL-V30-trials-not-one-process", "action_time", "identity_withheld",
        "EP-V30-T01", "EP-V30-T08", "video_observed",
        ["frame:E-40558b96405bcc:middle", "frame:E-281f02ffaf59dc:middle"],
        historical_text("episode_relations:197:8"),
        ["efficiency_ranking", "continuous_installation", "same_member_required"],
    ))
    for episode in episodes:
        if episode["group_id"] != "GRP-V30-insertion" or len(episode["event_ids"]) != 2:
            continue
        left, right = episode["event_ids"]
        relations.append(_relation(
            f"REL-{episode['episode_id']}-before", "action_time", "before",
            left, right, "video_observed", [f"event:{left}", f"event:{right}"],
            historical_text("episode_relations:207:12"),
            ["load_path", "completed_seating"],
        ))
        relations.append(_relation(
            f"REL-{episode['episode_id']}-holds", "object", "holds",
            "robot gripper", "active member", "video_observed",
            [f"description:{left}"],
            historical_text("episode_relations:214:12"),
            ["measured_grip_force"],
        ))

    episodes.append(_episode(
        inputs, "EP-V28-closeup-hold-clamp", "GRP-V28-holder-and-clamps",
        ["E-55b82c11e1c58f", "E-c2ac733f3b7d59", "E-4955d1f2073f23", "E-1a20e60dc5c0ed"],
        historical_text("episode_relations:221:8"),
        ["approach", "holding", "clamp_closure", "retry_reported"],
        {"label": "inclined timber beam", "identity": "closeup_local", "status": "agent_candidate"},
        {"label": "joint clamp", "identity": "closeup_local", "status": "agent_candidate"},
        ["member holder", "interface clamp", "timber beam"],
        "partial_closeup_without_a_verified_closed_joint",
        "same_closeup_camera_abutting_intervals",
        ["video_observed", "video_caption_reported"],
        "focus events r04-r07; existing EP-W03 covers the last three",
        [historical_text("episode_relations:230:9"), historical_text("episode_relations:230:19")],
        [historical_text("episode_relations:231:9"), historical_text("episode_relations:231:33")],
    ))
    episodes.append(_episode(
        inputs, "EP-V28-planned-transfer-shot", "GRP-V28-holder-and-clamps",
        ["E-f25e3e719cdf40"],
        historical_text("episode_relations:236:8"),
        ["transport"],
        {"label": "inclined timber beam", "identity": "not_joined_to_closeup", "status": "agent_candidate"},
        {"label": "none resolved", "status": "unknown"},
        ["robot arm", "beam gripper", "person at a console"],
        "single_transport_shot",
        "camera_changes_after_the_closeup",
        ["video_observed"],
        "focus event r08, clock-adjacent but identity withheld",
        [historical_text("episode_relations:245:9"), historical_text("episode_relations:245:23")],
        [historical_text("episode_relations:246:9")],
    ))
    episodes.append(_episode(
        inputs, "EP-V28-later-wide-shot", "GRP-V28-holder-and-clamps",
        ["E-c05ee9c161e484", "E-5949a7e74364b9"],
        historical_text("episode_relations:251:8"),
        ["transport", "holding", "clamp_closure"],
        {"label": "inclined beam in a dense assembly", "identity": "wide_shot_local", "status": "agent_candidate"},
        {"label": "clamps at intersections", "status": "agent_candidate"},
        ["beam gripper", "interface clamps", "timber beam"],
        "partial_later_shot",
        "new_camera_not_joined_to_closeup",
        ["video_observed"],
        "focus events r13-r14",
        [historical_text("episode_relations:260:9")],
        [historical_text("episode_relations:261:9")],
    ))
    episodes.append(_episode(
        inputs, "EP-V28-manual-clamp", "GRP-V28-holder-and-clamps",
        ["E-aeec492759276f"],
        historical_text("episode_relations:266:8"),
        ["manual_clamp_handling"],
        {"label": "interface clamp", "identity": "role_local_not_equated_to_closeup", "status": "agent_candidate"},
        {"label": "timber joint", "status": "agent_candidate"},
        ["person", "interface clamp"],
        "human_role_in_the_same_assembly_goal",
        "same_project_goal_member_identity_not_required",
        ["video_observed", "video_caption_reported"],
        "focus event r22; judged by clamp role and assembly goal, not by beam identity",
        [historical_text("episode_relations:275:9"), historical_text("episode_relations:275:26")],
        [historical_text("episode_relations:276:9")],
    ))

    close = ["E-55b82c11e1c58f", "E-c2ac733f3b7d59", "E-4955d1f2073f23", "E-1a20e60dc5c0ed"]
    for left, right in zip(close, close[1:]):
        relations.append(_relation(
            f"REL-V28-before-{left[-4:]}", "action_time", "before", left, right, "video_observed",
            [f"event:{left}", f"event:{right}"],
            historical_text("episode_relations:284:12"), ["successful_retry", "closed_joint"],
        ))
    relations.append(_relation(
        "REL-V28-retry-caption", "video_caption", "repeats", "E-c2ac733f3b7d59", "E-4955d1f2073f23",
        "video_caption_reported", ["frame:E-4955d1f2073f23:middle", "frame:task28_001515", "frame:task28_001739"],
        historical_text("episode_relations:289:8"),
        ["paper_text", "measured_jam", "retry_succeeded"],
    ))
    relations.append(_relation(
        "REL-V28-holder-holds", "object", "holds", "member holder", "timber beam", "video_observed",
        ["frame:E-55b82c11e1c58f:middle"],
        historical_text("episode_relations:295:8"), ["grip_force"],
    ))
    relations.append(_relation(
        "REL-V28-clamp-visible", "object", "visible_contact", "interface clamp", "joint", "video_observed",
        ["frame:E-55b82c11e1c58f:middle", "frame:E-c2ac733f3b7d59:middle"],
        historical_text("episode_relations:300:8"), ["load_bearing", "closed_joint"],
    ))
    relations.append(_relation(
        "REL-V28-human-collaborates", "object_roles", "collaborates", "person", "interface clamp",
        "video_observed", ["frame:task28_005865"],
        historical_text("episode_relations:305:8"),
        ["robot_planned_path", "same_beam_required"],
    ))
    relations.append(_relation(
        "REL-V28-caption-path", "video_caption", "labels", "video caption", "transfer shot",
        "video_caption_reported", ["frame:task28_001844"],
        historical_text("episode_relations:311:8"),
        ["paper_text", "executed_cad_path"],
    ))
    relations.append(_relation(
        "REL-V28-closeup-to-transfer", "action_time", "identity_withheld",
        "EP-V28-closeup-hold-clamp", "EP-V28-planned-transfer-shot", "video_observed",
        ["frame:E-f25e3e719cdf40:middle"],
        historical_text("episode_relations:318:8"), ["executed_cad_path", "same_member_required"],
    ))
    relations.append(_relation(
        "REL-V28-model-withdrawal", "model", "before", "CL3M/CL3 retreat 20 mm along +Y",
        "then 100 mm withdrawal", "model_conditional",
        ["V28-R4", "figure:V28-JOIN"],
        historical_text("episode_relations:324:8"),
        ["video_execution", "minimum_workspace"],
    ))

    episodes.append(_episode(
        inputs, "EP-V27-keep-near", "GRP-V27-move-and-turn",
        ["E-8a5eec318093fd"],
        historical_text("episode_relations:331:8"),
        ["holding"],
        {"label": "vertical timber", "identity": "pending_track", "status": "agent_candidate"},
        {"label": "end effector", "status": "agent_candidate"},
        ["orange robot", "white robot", "person on ladder"],
        "single_overlapping_annotation",
        "same_wide_video_as_the_other_V27_focus_tracks",
        ["video_observed"],
        "D12 event, front layer name",
        [historical_text("episode_relations:340:9"), historical_text("episode_relations:340:30")],
        [historical_text("episode_relations:341:9")],
    ))
    episodes.append(_episode(
        inputs, "EP-V27-person-tool", "GRP-V27-move-and-turn",
        ["E-831f13757f9f85", "E-b1cbef5c9d8761"],
        historical_text("episode_relations:346:8"),
        ["tool_application"],
        {"label": "handheld tool", "identity": "orange_tool_in_frame", "status": "agent_candidate"},
        {"label": "timber junction", "status": "unresolved_at_the_lower_position"},
        ["person", "handheld tool"],
        "partial_tool_use_outcome_unknown",
        "same_video_two_abutting_person_tracks",
        ["video_observed"],
        "D12 person-layer events",
        [historical_text("episode_relations:355:9"), historical_text("episode_relations:355:24")],
        [historical_text("episode_relations:356:9"), historical_text("episode_relations:356:24")],
    ))
    episodes.append(_episode(
        inputs, "EP-V27-member-moves", "GRP-V27-move-and-turn",
        ["E-995bc976b50ee6", "E-2b87e891620d31"],
        historical_text("episode_relations:361:8"),
        ["transport", "reorientation"],
        {"label": "timber member", "identity": "shared_middle_frame_pending_track", "status": "agent_candidate"},
        {"label": "open side of the frame", "status": "agent_candidate"},
        ["orange robot", "white robot"],
        "turn_visible_release_not_present",
        "two_tracks_share_one_middle_frame",
        ["video_observed"],
        "D12 rear and front move events",
        [historical_text("episode_relations:370:9"), historical_text("episode_relations:370:27")],
        [historical_text("episode_relations:371:9")],
    ))
    relations.append(_relation(
        "REL-V27-tool-before", "action_time", "before",
        "E-831f13757f9f85", "E-b1cbef5c9d8761", "video_observed",
        ["event:E-831f13757f9f85", "event:E-b1cbef5c9d8761"],
        historical_text("episode_relations:377:8"), ["tool_completed"],
    ))
    relations.append(_relation(
        "REL-V27-keep-overlaps-tool", "action_time", "overlaps",
        "E-8a5eec318093fd", "E-831f13757f9f85", "video_observed",
        ["event:E-8a5eec318093fd", "event:E-831f13757f9f85"],
        historical_text("episode_relations:383:8"), ["same_physical_load_path"],
    ))
    relations.append(_relation(
        "REL-V27-moves-share-frame", "action_time", "overlaps",
        "E-995bc976b50ee6", "E-2b87e891620d31", "video_observed",
        ["frame:E-995bc976b50ee6:middle", "frame:E-2b87e891620d31:middle"],
        historical_text("episode_relations:389:8"),
        ["named_gripper_identity"],
    ))
    relations.append(_relation(
        "REL-V27-no-release", "object", "identity_withheld",
        "EP-V27-keep-near", "EP-V27-member-moves", "video_observed",
        ["frame:E-8a5eec318093fd:middle", "frame:E-2b87e891620d31:middle"],
        historical_text("episode_relations:396:8"),
        ["release", "load_transfer"],
    ))
    relations.append(_relation(
        "REL-V27-existing-pixel-turn", "measurement", "phase_difference",
        "D12 f94-f95", "D12 f95-f96", "video_observed",
        ["D12_observed_turn/measurements.json"],
        historical_text("episode_relations:403:8"),
        ["calibrated_millimetres", "generalisable_to_every_phase"],
    ))

    groups = [
        {
            "group_id": "GRP-V30-insertion",
            "title": "V30 insertion trials",
            "case": "V30",
            "episode_ids": [item["episode_id"] for item in episodes if item["group_id"] == "GRP-V30-insertion"],
            "focus_event_ids": ["E-40558b96405bcc", "E-281f02ffaf59dc"],
            "what_is_included": historical_text("episode_relations:414:32"),
            "what_is_not_included": historical_text("episode_relations:415:36"),
            "differences": [
                historical_text("episode_relations:417:16"),
                historical_text("episode_relations:418:16"),
                historical_text("episode_relations:419:16"),
                historical_text("episode_relations:420:16"),
            ],
        },
        {
            "group_id": "GRP-V28-holder-and-clamps",
            "title": "V28 member holder and interface clamps",
            "case": "V28",
            "episode_ids": [item["episode_id"] for item in episodes if item["group_id"] == "GRP-V28-holder-and-clamps"],
            "focus_event_ids": ["E-55b82c11e1c58f", "E-c2ac733f3b7d59", "E-4955d1f2073f23", "E-1a20e60dc5c0ed",
                                "E-f25e3e719cdf40", "E-c05ee9c161e484", "E-5949a7e74364b9", "E-aeec492759276f"],
            "what_is_included": historical_text("episode_relations:430:32"),
            "what_is_not_included": historical_text("episode_relations:431:36"),
            "differences": [
                historical_text("episode_relations:433:16"),
                historical_text("episode_relations:434:16"),
                historical_text("episode_relations:435:16"),
                historical_text("episode_relations:436:16"),
            ],
        },
        {
            "group_id": "GRP-V27-move-and-turn",
            "title": "V27 overlapping keep, tool use, and turn",
            "case": "V27",
            "episode_ids": [item["episode_id"] for item in episodes if item["group_id"] == "GRP-V27-move-and-turn"],
            "focus_event_ids": ["E-8a5eec318093fd", "E-831f13757f9f85", "E-b1cbef5c9d8761",
                                "E-995bc976b50ee6", "E-2b87e891620d31"],
            "what_is_included": historical_text("episode_relations:446:32"),
            "what_is_not_included": historical_text("episode_relations:447:36"),
            "differences": [
                historical_text("episode_relations:449:16"),
                historical_text("episode_relations:450:16"),
                historical_text("episode_relations:451:16"),
                historical_text("episode_relations:452:16"),
            ],
        },
    ]
    payload = {"schema": "multicam-episode-relations-v1", "episodes": episodes, "groups": groups, "boards": process_boards()}
    relations_payload = {
        "schema": "multicam-relations-v1",
        "relations": relations,
        "edge_types": {
            "action_time": ["before", "overlaps", "repeats", "identity_withheld"],
            "object": ["holds", "visible_contact", "connects", "identity_withheld"],
            "video_caption": ["repeats", "labels"],
            "object_roles": ["role_division", "collaborates"],
            "model": ["before"],
            "measurement": ["phase_difference"],
        },
        "version_fingerprint": sha256_text("|".join(item["relation_id"] for item in relations)),
    }
    return payload, relations_payload
