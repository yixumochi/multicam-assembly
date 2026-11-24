"""Assemble all case boards in original event order using the confirmed V30 format."""

import argparse
from collections import Counter
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject, TextStringObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

import render_boards as layout
import replicate_force_boards as board
import revise_force_boards as revision
from render_v04_next_samples import OUT as PILOTS, render_page
from render_v04_review_batch_05 import update_annotation
from review_frames import load_events


WORK = layout.WORK / "full_v30"
OUTPUT = layout.OUTPUTS / "V30_full"
VETTED = (
    "V24_V28_V04_format_samples.pdf",
    "V07_V26_V30_V04_format_samples_v4.pdf",
    "V04_format_review_batch_02.pdf",
    "V04_format_review_batch_03.pdf",
    "V04_format_review_batch_04_v2.pdf",
    "V04_format_review_batch_05_v3.pdf",
    "V04_format_review_batch_06.pdf",
    "V04_format_review_batch_07.pdf",
    "V04_format_review_batch_08.pdf",
)
EVENT_ID = re.compile(r"E-[a-f0-9]{14}")
PAGINATION = re.compile(r"(?:Review )?\d+ / \d+")
IDEAL_DETAIL = (1, 0, 2)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def register_fonts():
    layout.register_fonts()


def pilot_index():
    reference = layout.WORK / "replication"
    pages = [PdfReader(reference / "test.pdf").pages[0],
             PdfReader(reference / "V04_confirmed_two_page_reference.pdf").pages[1]]
    for name in VETTED:
        pages.extend(PdfReader(PILOTS / name).pages)
    result = {EVENT_ID.search(page.extract_text()).group(): page for page in pages}
    if len(pages) != 48 or len(result) != len(pages):
        raise ValueError("The confirmed pilot set must contain 48 distinct event pages")
    return result


def renumber_pilot(page, event, number, total):
    stream = page.get_contents()
    label = f"{number} / {total}"
    footer_index = next(i for i in range(len(stream.operations) - 1, -1, -1)
                        if stream.operations[i][1] == b"Tj"
                        and PAGINATION.fullmatch(str(stream.operations[i][0][0])))
    stream.operations[footer_index][0][0] = TextStringObject(label)
    matrix = next(stream.operations[i][0] for i in range(footer_index - 1, -1, -1)
                  if stream.operations[i][1] == b"Tm")
    matrix[4] = FloatObject(layout.PAGE_W - layout.MARGIN - pdfmetrics.stringWidth(label, layout.FONT, 9))
    if event["id"] in {"E-656081cd849333", "E-df1e5ad54fb77c"}:
        for values, opcode in stream.operations:
            if opcode != b"Tj":
                continue
            original = str(values[0])
            if original == "TWO-EVENT REVIEW" or original == "01 Approach local joint":
                values[0] = TextStringObject(f"{number:02d} {event['label']}")
                break
    page.replace_contents(stream)


def select_alignment(a, frames):
    requested = a.get("overlay_roles")
    same_view = defaultdict(list)
    for frame in frames:
        if frame.mask and frame.traced("point") and (requested is None or frame.role in requested):
            key = "explicit" if requested is not None else str(frame.traced("shot") or "same view")
            same_view[key].append(frame.role)
    groups = sorted(same_view.values(), key=lambda roles: (len(roles), "middle" in roles), reverse=True)
    selected = groups[0] if groups else []
    if len(selected) >= 2 or requested and selected:
        if len(selected) < 3:
            a["overlay_roles"] = tuple(selected)
        return
    a["separate_masks"] = True
    a.setdefault("common_point_status", "Alignment could not be established across the available masks.")


def configured_page(event, a):
    if a.get("mode") == "evidence":
        for state in a["frames"].values():
            for contact in state.get("contacts") or []:
                contact.pop("line", None)
    kind = a.get("analysis_kind") or a.get("interaction_kind")
    for state in a["frames"].values():
        if not state.get("mask_verified") and kind in {"manual", "context", "joint", "support"}:
            state.setdefault("mask_placeholder", "Source view")
    frames = revision.approved_frames(event, a)
    a["mask_summary"] = (
        "The sampled activity is shown in the source frames."
        if kind in {"manual", "context", "joint", "support"}
        else "The equipment outline could not be isolated in the sampled views."
    )
    select_alignment(a, frames)
    if a.get("right_angles"):
        traced = []
        for i in IDEAL_DETAIL:
            frame = frames[i]
            for field in ("right_member", "right_tool"):
                if frame.traced(field):
                    layout.validate_coordinates(frame.annotation, field, 4, frame.size)
            if frame.traced("right_member") and frame.traced("right_tool"):
                traced.append(i)
        if not traced:
            raise ValueError(f"{event['id']}: missing right-side angle geometry")
        if a.get("detail_index") not in traced:
            a["detail_index"] = traced[0]
        return a, frames, "traced_angle"
    pair_frames = [i for i in IDEAL_DETAIL if board.get_pair(frames[i])]
    single_frames = [i for i in IDEAL_DETAIL if any(c.direction is not None
                     for c in frames[i].traced("read_contacts"))]
    detail = a.get("detail_index")
    if pair_frames:
        i = detail if detail in pair_frames else pair_frames[0]
        mode = "split_pair" if a.get("mode") == "split_pair" else "pair"
        a.setdefault("evidence_title", "Visible interfaces across the three frames")
        a.setdefault("contact_caption", "A and B mark the two visible interfaces.")
        a.setdefault("model_note", frames[i].traced("force_basis") or
                     "The model adds two equal image-plane vectors.")
        a.setdefault("angle_note", "Angles use the traced timber edge in each source view.")
    elif single_frames:
        i = detail if detail in single_frames else single_frames[0]
        mode = "axis"
        contacts = frames[i].traced("read_contacts")
        force_id = next(c.label or "AB"[j] for j, c in enumerate(contacts) if c.direction is not None)
        a["single_force_id"] = force_id
        a.setdefault("contact_title", "02   Working contact, direction and angle")
        a.setdefault("contact_caption", f"{force_id} marks the visible working location.")
        a.setdefault("contact_statuses", tuple(
            "Projected working direction"
            if any(c.direction is not None for c in f.traced("read_contacts"))
            else "Visible interface" if f.traced("read_contacts") else "Source view"
            for f in frames
        ))
        a.setdefault("angle_note", "Angles use the projected working direction and the traced timber edge.")
    else:
        mode = "evidence"
        scores = [4 * bool(f.traced("read_contacts")) + 3 * bool(f.traced("contact_region"))
                  + 2 * bool(revision.geometry(f)) + bool(f.mask) for f in frames]
        i = detail if detail in IDEAL_DETAIL else max(IDEAL_DETAIL, key=lambda index: scores[index])
        a.setdefault("contact_title", "02   Working location and visible evidence")
        if re.search(r"\b(force model|equal magnitude|resultant|1:1)\b", a.get("note") or "", re.I):
            a["note"] = ""
    a.update(detail_index=i, show_sample_arrows=True, projected_force_angles=True)
    return a, frames, mode


def prepare(event, source, descriptions, edits):
    eid = event["id"]
    annotation = deepcopy(source[eid])
    annotation["english_description"] = (
        annotation.get("description_en") or descriptions.get(eid, {}).get("description_en") or event["description"]
    )
    if eid in edits:
        update_annotation(annotation, edits[eid])
    if re.search(r"[\u3400-\u9fff]", annotation["english_description"]):
        annotation["english_description"] = event["label"]
    return configured_page(event, annotation)


def publish_case(case, events, pilots):
    rows = read_json(revision.AUDIT / case / "pages.json")
    if len(rows) != layout.CASE_COUNTS[case]:
        raise ValueError(f"{case}: source event count does not match")
    source = read_json(revision.ROOT / f"{case}.json")
    descriptions = read_json(layout.WORK / "annotations" / f"{case}.json")
    overrides = WORK / "overrides" / f"{case}.json"
    edits = read_json(overrides) if overrides.exists() else {}
    parts = WORK / "render"
    parts.mkdir(parents=True, exist_ok=True)
    draft = parts / f"{case}-new.pdf"
    pdf = canvas.Canvas(str(draft), pagesize=(layout.PAGE_W, layout.PAGE_H), pageCompression=1)
    reviewed = {}
    counts = Counter()
    for i, row in enumerate(rows, 1):
        eid = row["id"]
        if eid in pilots:
            counts["pilot"] += 1
            continue
        event = events[eid]
        a, frames, mode = prepare(event, source, descriptions, edits)
        render_page(pdf, event, a, frames, i, i, len(rows), mode)
        counts[mode] += 1
        counts["any_mask"] += int(any(f.mask for f in frames))
        counts["all_masks"] += int(all(f.mask for f in frames))
        counts["aligned"] += int(not a.get("separate_masks"))
        reviewed[eid] = len(reviewed)
    pdf.save()
    new_pages = PdfReader(draft).pages
    if len(new_pages) != len(reviewed):
        raise ValueError(f"{case}: intermediate page count does not match")
    writer = PdfWriter()
    writer.add_metadata({"/Title": f"{case} | V30 equipment, contacts and angles"})
    for i, row in enumerate(rows, 1):
        eid = row["id"]
        if eid in pilots:
            renumber_pilot(writer.add_page(pilots[eid]), events[eid], i, len(rows))
        else:
            writer.add_page(new_pages[reviewed[eid]])
    target = OUTPUT / f"{case}_V30_final.pdf"
    pending = target.with_suffix(".pending.pdf")
    with pending.open("wb") as stream:
        writer.write(stream)
    validated = PdfReader(pending).pages
    if len(validated) != len(rows):
        raise ValueError(f"{case}: final page count does not match")
    for i, (page, row) in enumerate(zip(validated, rows), 1):
        text = page.extract_text()
        if row["id"] not in text or text.splitlines()[-1] != f"{i} / {len(rows)}":
            raise ValueError(f"{case} page {i}: event identity or pagination does not match")
        if "Resultant not readable" in text:
            raise ValueError(f"{case} page {i}: legacy resultant placeholder")
    pending.replace(target)
    stats = {"case": case, "pages": len(rows), "edited_event_records": len(edits), **counts}
    (parts / f"{case}-stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="+", choices=tuple(layout.CASE_COUNTS))
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    register_fonts()
    pilots = pilot_index()
    events = {event["id"]: event for event in load_events()}
    for case in args.cases:
        publish_case(case, events, pilots)


if __name__ == "__main__":
    main()
