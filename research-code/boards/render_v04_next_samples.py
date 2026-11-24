"""Render a limited V04-format pilot across three types of image evidence."""

from copy import deepcopy
from dataclasses import replace
import json
from math import atan2, dist, degrees
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from pypdf import PdfReader
from reportlab.pdfgen import canvas

import replicate_force_boards as board
import render_boards as b
import revise_force_boards as revision
from render_v04_format_samples import angle_table, force_panel
from review_frames import load_events
from robot_force_board import CA, CB, CR, arrow


SAMPLES = (("V07", 3, "pair"), ("V26", 53, "axis"), ("V30", 5, "split_pair"))
OUT = b.OUTPUTS / "v04_format_samples"


def set_anchor(a, label, target, points):
    a.update(point_label=label, alignment_target=target, aligned_verified=True)
    for role, point in zip(b.ROLES, points):
        frame = a["frames"][role]
        if point is None:
            frame.pop("point", None)
        else:
            frame["point"] = list(point)


def base_annotation(case, eid, event):
    records = json.loads((revision.ROOT / f"{case}.json").read_text(encoding="utf-8-sig"))
    a = deepcopy(records[eid])
    descriptions = json.loads((b.WORK / "annotations" / f"{case}.json").read_text(encoding="utf-8-sig"))
    a["english_description"] = (
        a.get("description_en") or descriptions[eid].get("description_en") or event["description"]
    )
    return a


def prepare(case, number, eid, event):
    a = base_annotation(case, eid, event)
    if (case, number) == ("V07", 3):
        set_anchor(a, "Left circular hole on the fixed lower platen", "the test fixture",
                   [(376, 490), (377, 491), (376, 491)])
        for role, coords in zip(b.ROLES, (((396, 177), (535, 177)), ((399, 207), (537, 208)),
                                          ((400, 253), (540, 253)))):
            a["frames"][role]["contacts"] = [
                {"point": [x, y], "line": [x, y, x, y + 35]} for x, y in coords
            ]
    elif (case, number) == ("V26", 53):
        set_anchor(a, "Front-right top corner of the plywood panel", "the panel",
                   [(530, 383), (504, 363), (502, 380)])
        a["object"] = "Visible blue nailer and working nose"
        a["note"] = "The nose meets the panel only in the middle sample."
        f = a["frames"]["middle"]
        # The old mask stops on the housing. Include the visible black nose up to the panel.
        with Image.open(f["mask"]) as raw:
            mask = raw.convert("L")
        draw = ImageDraw.Draw(mask)
        draw.polygon([(515, 274), (545, 271), (545, 288), (539, 298), (533, 309),
                      (528, 310), (524, 306), (520, 301), (516, 293)], fill=255)
        path = b.WORK / "pilot_qa" / "V26-p53-middle-mask.png"
        path.parent.mkdir(exist_ok=True)
        mask.save(path)
        f["mask"] = str(path)
        f["tool"] = [533, 229, 534, 310]
        f["contacts"] = [{"point": f["tool"][2:], "line": f["tool"]}]
        f["member"] = [257, 373, 501, 360]
        f["working_direction"] = "The arrow follows the visible axis toward the panel."
        a["frames"]["start"]["roi"] = [470, 25, 640, 400]
        a["frames"]["end"]["roi"] = [483, 61, 650, 396]
    elif (case, number) == ("V30", 5):
        set_anchor(a, "Camera L: lower timber end, lower-right corner", "the lower timber",
                   [(343, 383), (344, 385), (344, 385)])
        a["note"] = "The mask, alignment and contact arrows use camera L. The timber joint angle uses camera R."
        a["english_description"] = "The overhead gripper carries the upper timber into the single-lap joint."
        a["force_basis"] = "The marked directions in camera L are modeled at equal projected magnitude."
        edges = ([48, 317, 425, 317], [48, 327, 425, 326], [48, 339, 425, 333])
        for role, edge in zip(b.ROLES, edges):
            f = a["frames"][role]
            f["force_reference"] = edge
            f["force_arrow_length"] = 43
            for contact in f["contacts"]:
                x, y = contact["point"]
                contact["line"] = [x, y, x, y + 43]
    return a


def axis_table(pdf, frames, reference_name, contact_statuses, axis_label, angle_note):
    x = b.RIGHT
    b.txt(pdf, f"On-screen angle to the traced {reference_name} edge", x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    for px, cell in zip((x + 14, x + 130, x + 312),
                        ("Sample", f"{axis_label} to {reference_name} edge", "Contact evidence")):
        b.txt(pdf, cell, px, 588, 9.5, bold=True)
    for j, (frame, color) in enumerate(zip(frames, b.COLORS)):
        y = 615 + j * 39
        b.segment(pdf, (x + 14, y - 3), (x + 24, y - 3), color, 2)
        b.txt(pdf, frame.time_label, x + 31, y, 9.6, bold=True)
        geom = revision.geometry(frame)
        angle = board.angle_label(revision.vector(geom[1]), geom[0]) if geom else "—"
        b.txt(pdf, angle, x + 130, y, 9.6)
        b.txt(pdf, contact_statuses[j], x + 312, y, 9.6)
        b.segment(pdf, (x + 12, y + 12), (x + b.COL_W - 12, y + 12))
    b.text_block(pdf, angle_note, x, 751, b.COL_W, 9, 2)


def split_angle_table(pdf, frames, images):
    x = b.RIGHT
    cols = [x + offset for offset in (14, 91, 145, 199, 267)]
    b.txt(pdf, "On-screen contact and joint angles by camera", x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    b.txt(pdf, "Camera L · to the held timber edge", cols[1], 587, 9, b.MUTED)
    b.txt(pdf, "Camera R", cols[-1], 587, 9, b.MUTED)
    b.segment(pdf, (x + 256, 576), (x + 256, 722))
    b.segment(pdf, (x + 330, 576), (x + 330, 722))
    for col, header in zip(cols, ("Sample", "FA at A", "FB at B", "R (1:1)", "Joint angle")):
        b.txt(pdf, header, col, 607, 9.3, bold=True)
    for j, (frame, color) in enumerate(zip(frames, b.COLORS)):
        y = 633 + j * 36
        b.segment(pdf, (cols[0], y - 3), (cols[0] + 10, y - 3), color, 2)
        b.txt(pdf, frame.time_label, cols[0] + 15, y, 9.6, bold=True)
        edge = frame.traced("force_reference")
        pair = board.get_pair(frame)
        values = tuple(board.angle_label(vector, edge) if edge else "—" for vector in
                       (pair.ua, pair.ub, pair.resultant)) if pair else ("—",) * 3
        geom = revision.geometry(frame)
        joint = board.angle_label(revision.vector(geom[1]), geom[0]) if geom else "—"
        for col, value, ink in zip(cols[1:], (*values, joint), (CA, CB, CR, None)):
            b.txt(pdf, value, col, y, 9.3, b.HexColor(ink) if ink else b.MUTED, ink == CR)
        b.segment(pdf, (x + 12, y + 11), (x + 317, y + 11))
    inset_x = x + 341
    inset_width = b.COL_W - 352
    index = next((i for i in (1, 0, 2) if revision.geometry(frames[i])), 1)
    frame = frames[index]
    b.txt(pdf, f"Camera R · {frame.role} frame", inset_x, 588, 9, bold=True)
    if revision.geometry(frame):
        angles = revision.detail(frame, images[index], (560, 325), for_geometry=True)
        caption = "Traced edges near the timber joint."
    else:
        width, height = frame.size
        rect = frame.traced("joint_crop") or (width // 2, 0, width, height)
        angles = board.crop(images[index], rect, (560, 325))
        caption = "Joint region in the source frame."
    board.photo(pdf, angles, inset_x, 597, inset_width, inset_width * 325 / 560)
    b.txt(pdf, caption, inset_x, 716, 8.5, b.MUTED)
    b.text_block(pdf, "Camera L and camera R angles use their own image planes.", x, 751, b.COL_W, 9, 2)


def contact_region_panel(pdf, frames, images, a):
    index = a.get("detail_index", 1)
    frame = frames[index]
    x, y = b.RIGHT, 333
    width = (b.COL_W - 10) / 2
    height = width * .63
    pixels = (720, 454)
    heading = a.get("region_heading", "Visible contact area")
    b.txt(pdf, f"{frame.role.capitalize()} frame   ·   {heading}", x, 322, 12, bold=True)
    timber_sections, fingers = (
        [tuple(map(tuple, shape)) for shape in frame.traced(key)]
        for key in ("visible_timber_sections", "visible_jaw_fingers")
    )
    photo = images[index].copy()
    trace = ImageDraw.Draw(photo)
    for section in timber_sections:
        edges = zip(section, (*section[1:], section[0]))
        trace.line(max(edges, key=lambda edge: dist(*edge)), fill="#AA732C", width=2)
    for finger in fingers:
        trace.line((*finger, finger[0]), fill="#236281", width=1)
    photo = board.plot_on_photo(frame, photo, pixels, show_region=True)
    board.photo(pdf, photo, x, y, width, height)
    diagram = Image.new("RGB", frame.size, "#F5F8FA")
    detail = ImageDraw.Draw(diagram)
    for section in timber_sections:
        detail.polygon(section, fill="#E1C9A5", outline="#AA732C", width=1)
    for finger in fingers:
        detail.polygon(finger, fill="#ADC6D2", outline="#236281", width=1)
    diagram = board.plot_on_photo(frame, diagram, pixels, show_region=True)
    b.picture(pdf, diagram, x + width + 10, y, width, height)
    b.text_block(pdf, a["contact_caption"], x, y + height + 14, width, 8.7, 2)
    b.text_block(pdf, a.get("region_diagram_caption", "Timber edges and jaw fingers traced in the same view."),
                 x + width + 10, y + height + 14, width, 8.7, 2)
    table_title = a.get("region_table_title", "Contact evidence across the source frames")
    b.txt(pdf, table_title, x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    b.txt(pdf, "Sample", x + 14, 588, 9.5, bold=True)
    b.txt(pdf, a.get("region_column_label", "Visible interface"), x + 130, 588, 9.5, bold=True)
    for j, (source, color, status) in enumerate(zip(frames, b.COLORS, a["contact_statuses"])):
        row = 615 + j * 39
        b.segment(pdf, (x + 14, row - 3), (x + 24, row - 3), color, 2)
        b.txt(pdf, source.time_label, x + 31, row, 9.6, bold=True)
        b.text_block(pdf, status, x + 130, row, b.COL_W - 145, 9.6, 2)
        b.segment(pdf, (x + 12, row + 12), (x + b.COL_W - 12, row + 12))
    b.text_block(pdf, a["region_note"], x, 751, b.COL_W, 9, 2)


def motion_panel(pdf, frames, images, a):
    first_index, last_index = a.get("motion_span", (1, 2))
    first, last = frames[first_index], frames[last_index]
    interval = f"{first.role.capitalize()} to {last.role}"
    pts = [complex(*p) for p in a["motion_points"]]
    ref = complex(*first.traced("point"))
    start = pts[first_index]
    finish = pts[last_index] + ref - complex(*last.traced("point"))
    size = (720, 454)
    box = board.fit_crop(first.size, a["motion_crop"], size[0] / size[1])
    scale = size[0] / (box[2] - box[0])
    origin = complex(*box[:2])
    p, q = ((point - origin) * scale for point in (start, finish))
    ink = "#235D7B"
    photo = board.crop(images[first_index], box, size)
    diagram = Image.new("RGB", size, "#F5F8FA")
    draw = ImageDraw.Draw(photo)
    board.arrow(draw, p, q, ink, 6, True)
    draw.ellipse((p.real - 5, p.imag - 5, p.real + 5, p.imag + 5), fill="white", outline=ink, width=2)
    delta = q - p
    factor = min(1, size[0] * .56 / max(1, abs(delta.real)), size[1] * .54 / max(1, abs(delta.imag)))
    center = complex(size[0] / 2, size[1] / 2)
    start_dot, end_dot = center - delta * factor / 2, center + delta * factor / 2
    keys = ((start_dot, first.role.capitalize(), b.COLORS[first_index]),
            (end_dot, last.role.capitalize(), b.COLORS[last_index]))
    draw = ImageDraw.Draw(diagram)
    board.arrow(draw, start_dot, end_dot, ink, 6)
    for dot, role, color in keys:
        if abs(delta.real) > abs(delta.imag):
            position, alignment = (dot.real, dot.imag + 21), "mt"
        else:
            position, alignment = (dot.real + 24, dot.imag), "lm"
        draw.text(position, role, font=board.font(26, True), fill=ink, anchor=alignment)
        hue = tuple(round(v * 255) for v in (color.red, color.green, color.blue))
        draw.ellipse((dot.real - 5, dot.imag - 5, dot.real + 5, dot.imag + 5), fill=hue, outline=ink, width=2)
    x, y = b.RIGHT, 333
    width = (b.COL_W - 10) / 2
    height = width * .63
    b.txt(pdf, f"{interval}   ·   Projected equipment travel", x, 322, 12, bold=True)
    board.photo(pdf, photo, x, y, width, height)
    b.picture(pdf, diagram, x + width + 10, y, width, height)
    b.txt(pdf, "Arrow starts at the tracked position in the photo.", x, y + height + 14, 8.7, b.MUTED)
    b.txt(pdf, "Aligned displacement in the image plane.", x + width + 10, y + height + 14, 8.7, b.MUTED)
    b.txt(pdf, "Observed positions across the source frames", x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    b.txt(pdf, "Sample", x + 14, 588, 9.5, bold=True)
    b.txt(pdf, f"{a['motion_subject']} (px)", x + 130, 588, 9.5, bold=True)
    b.txt(pdf, "Observed position", x + 300, 588, 9.5, bold=True)
    for j, (frame, color, point, status) in enumerate(zip(frames, b.COLORS, pts, a["contact_statuses"])):
        row = 615 + j * 39
        b.segment(pdf, (x + 14, row - 3), (x + 24, row - 3), color, 2)
        b.txt(pdf, frame.time_label, x + 31, row, 9.6, bold=True)
        b.txt(pdf, f"({point.real:g}, {point.imag:g})", x + 130, row, 9.6)
        b.text_block(pdf, status, x + 300, row, b.COL_W - 310, 9.6, 2)
        b.segment(pdf, (x + 12, row + 12), (x + b.COL_W - 12, row + 12))
    angle = board.angle_label(finish - start, [0, 0, 1, 0])
    note = f"Aligned {interval.lower()} displacement is {abs(finish - start):.0f} px at {angle} to screen horizontal."
    b.text_block(pdf, note, x, 751, b.COL_W, 9, 2)


def marked_panel(pdf, frames, images, a):
    i = a.get("detail_index", 1)
    frame = frames[i]
    marks = frame.traced("marked_arrows")
    pixels = 720, 454
    x, y = b.RIGHT, 333
    width = (b.COL_W - 10) / 2
    height = width * .63
    b.txt(pdf, f"{frame.role.capitalize()} frame   ·   {a['marked_heading']}", x, 322, 12, bold=True)
    board.photo(pdf, board.marked_photo(frame, images[i], pixels), x, y, width, height)
    b.picture(pdf, board.marked_diagram(marks, pixels), x + width + 10, y, width, height)
    b.text_block(pdf, a["contact_caption"], x, y + height + 14, width, 8.7, 2)
    b.text_block(pdf, a["diagram_caption"], x + width + 10, y + height + 14, width, 8.7, 2)
    b.txt(pdf, "Marked directions across the source frames", x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    b.txt(pdf, "Sample", x + 14, 588, 9.5, bold=True)
    b.txt(pdf, "Marked direction", x + 130, 588, 9.5, bold=True)
    b.txt(pdf, "Angle to image horizontal", x + 353, 588, 9.5, bold=True)
    for j, (source, color, status) in enumerate(zip(frames, b.COLORS, a["contact_statuses"])):
        row = 615 + j * 39
        b.segment(pdf, (x + 14, row - 3), (x + 24, row - 3), color, 2)
        b.txt(pdf, source.time_label, x + 31, row, 9.6, bold=True)
        b.text_block(pdf, status, x + 130, row, 205, 9.6, 2)
        directions = source.traced("marked_arrows") or ()
        angles = [board.angle_label(complex(*path[-1]) - complex(*path[0]), [0, 0, 1, 0])
                  for path in directions if len(path) == 2]
        if len(angles) == 2:
            reading = "A " + angles[0].removeprefix("about ") + "   ·   B " + angles[1].removeprefix("about ")
        elif angles:
            reading = angles[0]
        else:
            reading = "—"
        b.txt(pdf, reading, x + 353, row, 9.6)
        b.segment(pdf, (x + 12, row + 12), (x + b.COL_W - 12, row + 12))
    b.text_block(pdf, a["direction_note"], x, 751, b.COL_W, 9, 2)


def projected_force_angles(pdf, frames, a, paired):
    x = b.RIGHT
    b.txt(pdf, a.get("right_table_title", "On-screen angles to the traced timber edge"), x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    columns = (x + 14, x + 140, x + 266, x + 392) if paired else (x + 14, x + 140, x + 266)
    single_id = a.get("single_force_id", "A")
    symbol = a.get("single_symbol", "F")
    headers = ("Sample", "FA at A", "FB at B", "R (1:1 model)") if paired else (
        "Sample", a.get("single_angle_header", f"{symbol}{single_id} at {single_id}"), "Working direction",
    )
    for px, label in zip(columns, headers):
        b.txt(pdf, label, px, 588, 9.5, bold=True)
    for j, (frame, color) in enumerate(zip(frames, b.COLORS)):
        row = 615 + 39 * j
        b.segment(pdf, (columns[0], row - 3), (columns[0] + 10, row - 3), color, 2)
        b.txt(pdf, frame.time_label, columns[0] + 15, row, 9.6, bold=True)
        edge = frame.traced("force_reference") or frame.traced("member")
        contacts = frame.traced("read_contacts")
        pair = board.get_pair(frame)
        directions = {contact.label or "AB"[i]: contact.direction for i, contact in enumerate(contacts)}
        vectors = (
            directions.get("A"),
            directions.get("B"),
            pair.resultant if pair else None,
        )
        if paired:
            angle_cells = zip(columns[1:], vectors, (CA, CB, CR))
        else:
            active_id = next((label for label, direction in directions.items() if direction is not None),
                             single_id)
            angle_cells = ((columns[1], directions.get(active_id), CA if active_id == "A" else CB),)
        for col, direction, ink in angle_cells:
            label = board.angle_label(direction, edge) if direction is not None and edge else "—"
            if ink == CR and pair and pair.cancels_at_resolution:
                label = "R ≈ 0"
            b.txt(pdf, label, col, row, 9.6, b.HexColor(ink) if label != "—" else b.MUTED, ink == CR)
        if not paired:
            b.txt(pdf, a["contact_statuses"][j], columns[2], row, 9.6)
        b.segment(pdf, (x + 12, row + 12), (x + b.COL_W - 12, row + 12))
    b.text_block(pdf, a["angle_note"], x, 751, b.COL_W, 9, 2)


def observation(frame):
    if frame.traced("evidence_observation"):
        return frame.traced("evidence_observation")
    contacts = frame.traced("read_contacts")
    if contacts:
        if len(contacts) == 2:
            return "A and B locate the visible interfaces"
        return f"{contacts[0].label or 'A'} locates the visible interface"
    if frame.traced("contact_region"):
        return "Visible interface region"
    if revision.geometry(frame):
        return "Visible geometry edges"
    return "Equipment outline visible" if frame.mask else "Source view"


def right_panel_frame(frame):
    state = frame.annotation.copy()
    state.update(member=frame.traced("right_member"), tool=frame.traced("right_tool"),
                 force_reference=None, force_crop=frame.traced("right_crop"))
    return replace(frame, annotation=state)


def angle_diagram(frame, pixels):
    image = Image.new("RGB", pixels, "#F5F8FA")
    draw = ImageDraw.Draw(image)
    ref = revision.vector(frame.traced("member"))
    axis = revision.vector(frame.traced("tool"))
    contact = next((c for c in frame.traced("read_contacts") if c.direction is not None), None)
    unit_u = ref / abs(ref)
    unit_v = contact.direction if contact else axis / abs(axis)
    if (unit_u.conjugate() * unit_v).real < 0:
        unit_u *= -1
    turning = unit_u.conjugate() * unit_v
    sweep = atan2(turning.imag, turning.real)
    width, height = pixels
    length = min(width, height) * .32
    ends = (0j, unit_u * length, unit_v * length)
    origin = complex(
        (width - min(p.real for p in ends) - max(p.real for p in ends)) / 2,
        (height - min(p.imag for p in ends) - max(p.imag for p in ends)) / 2,
    )

    def xy(p):
        return p.real, p.imag

    ref_ink, axis_ink = "#996118", CA if contact else "#3C5670"
    draw.line((xy(origin), xy(origin + ends[1])), fill=ref_ink, width=6)
    if contact:
        arrow(draw, origin, origin + ends[2], axis_ink, 6)
        label = origin + unit_v * (length + 22)
        draw.text(xy(label), "F" + (contact.label or "A"), fill=axis_ink,
                  font=board.font(30, True), anchor="mm")
    else:
        draw.line((xy(origin), xy(origin + ends[2])), fill=axis_ink, width=6)
    theta = atan2(unit_u.imag, unit_u.real)
    radius = length * .46
    box = (origin.real - radius, origin.imag - radius, origin.real + radius, origin.imag + radius)
    begin, end = sorted((degrees(theta), degrees(theta + sweep)))
    draw.arc(box, begin, end, fill="#435C6B", width=4)
    middle = unit_u + unit_v
    bisector = middle / abs(middle)
    label = origin + (radius + 48) * bisector
    if abs(degrees(sweep)) < 35:
        label += 1j * bisector * (60 if sweep >= 0 else -60)
    draw.text(xy(label), board.angle_label(unit_v, frame.traced("member")).removeprefix("about "),
              font=board.font(32, True), fill="#142D3A", anchor="mm",
              stroke_width=2, stroke_fill="#F5F8FA")
    return image


def traced_angle_panel(pdf, frames, images, a):
    x, y = b.RIGHT, 333
    width = (b.COL_W - 10) / 2
    height = width * .63
    pixels = 720, 454
    index = a["detail_index"]
    frame = frames[index]
    title = a.get("right_detail_title", "Traced angle at the gripper")
    b.txt(pdf, f"{frame.role.capitalize()} frame   ·   {title}", x, 322, 12, bold=True)
    detail = board.plot_on_photo(frame, images[index], pixels, show_region=True)
    board.photo(pdf, detail, x, y, width, height)
    b.picture(pdf, angle_diagram(frame, pixels), x + width + 10, y, width, height)
    b.text_block(pdf, observation(frame).rstrip(".") + ".", x, y + height + 14, width, 8.7, 2)
    b.text_block(pdf, "The same two directions, drawn from a common origin.",
                 x + width + 10, y + height + 14, width, 8.7, 2)

    b.txt(pdf, a["right_table_title"], x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    cols = x + 14, x + 133, x + 232
    for xx, title in zip(cols, ("Sample", "Angle", "Visible evidence")):
        b.txt(pdf, title, xx, 588, 9.5, bold=True)
    for j, (sample, color) in enumerate(zip(frames, b.COLORS)):
        row = 615 + j * 39
        b.segment(pdf, (cols[0], row - 3), (cols[0] + 10, row - 3), color, 2)
        b.txt(pdf, sample.time_label, cols[0] + 15, row, 9.6, bold=True)
        edge, axis = sample.traced("member"), sample.traced("tool")
        direction = next((c.direction for c in sample.traced("read_contacts") if c.direction is not None), None)
        angle = board.angle_label(direction or revision.vector(axis), edge) if axis and edge else "—"
        b.txt(pdf, angle, cols[1], row, 9.6, bold=angle != "—")
        b.text_block(pdf, observation(sample), cols[2], row, b.COL_W - 245, 9.4, 2)
        b.segment(pdf, (x + 12, row + 12), (x + b.COL_W - 12, row + 12))
    b.text_block(pdf, a["right_angle_note"], x, 751, b.COL_W, 9, 2)


def evidence_panel(pdf, frames, images, a):
    index = a["detail_index"]
    frame = frames[index]
    x, y = b.RIGHT, 333
    width = (b.COL_W - 10) / 2
    height = width * .63
    pixels = 720, 454
    b.txt(pdf, f"{frame.role.capitalize()} frame   ·   Source detail", x, 322, 12, bold=True)
    detail = board.plot_on_photo(frame, images[index], pixels, show_contact_arrows=False, show_region=True)
    board.photo(pdf, detail, x, y, width, height)
    b.text_block(pdf, observation(frame).rstrip(".") + ".", x, y + height + 14, width, 8.7, 2)
    diagram = None
    has_trace = frame.mask or frame.traced("read_contacts") or frame.traced("contact_region") or revision.geometry(frame)
    if has_trace and not a.get("evidence_source_pair"):
        schematic = Image.new("RGB", frame.size, "#F5F8FA")
        if frame.mask:
            outline = ImageChops.subtract(frame.mask, frame.mask.filter(ImageFilter.MinFilter(5)))
            schematic.paste("#527C91", (0, 0, *frame.size), outline)
        candidate = board.plot_on_photo(frame, schematic, pixels, show_contact_arrows=False, show_region=True)
        background = Image.new("RGB", pixels, "#F5F8FA")
        if ImageChops.difference(candidate, background).getbbox():
            diagram = candidate
    if diagram is not None:
        b.picture(pdf, diagram, x + width + 10, y, width, height)
        caption = ("Marked region in the same view." if frame.traced("contact_region")
                   and not frame.traced("read_contacts") and not revision.geometry(frame)
                   else "Traced evidence in the same view.")
    else:
        comparison = frames[2 if index != 2 else 0]
        source = images[2 if index != 2 else 0]
        detail = board.plot_on_photo(comparison, source, pixels, show_contact_arrows=False)
        board.photo(pdf, detail, x + width + 10, y, width, height)
        caption = f"{comparison.role.capitalize()} frame for context."
    b.text_block(pdf, caption, x + width + 10, y + height + 14, width, 8.7, 2)
    evidence_table(pdf, frames, a)


def evidence_table(pdf, frames, a, *, include_angles=True):
    x = b.RIGHT
    geometry = include_angles and any(revision.geometry(f) for f in frames)
    b.txt(pdf, a.get("evidence_table_title", "On-screen evidence across the source frames"), x, 556, 13, bold=True)
    b.rect(pdf, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    b.txt(pdf, "Sample", x + 14, 588, 9.5, bold=True)
    b.txt(pdf, "Visible evidence", x + 130, 588, 9.5, bold=True)
    if geometry:
        b.txt(pdf, "Angle between traced edges", x + 365, 588, 9.5, bold=True)
    for j, (f, color) in enumerate(zip(frames, b.COLORS)):
        row = 615 + j * 39
        b.segment(pdf, (x + 14, row - 3), (x + 24, row - 3), color, 2)
        b.txt(pdf, f.time_label, x + 31, row, 9.6, bold=True)
        b.text_block(pdf, observation(f), x + 130, row, 218 if geometry else b.COL_W - 145, 9.6, 2)
        if geometry:
            lines = revision.geometry(f)
            label = board.angle_label(revision.vector(lines[1]), lines[0]) if lines else "—"
            b.txt(pdf, label, x + 365, row, 9.6)
        b.segment(pdf, (x + 12, row + 12), (x + b.COL_W - 12, row + 12))
    if geometry:
        b.text_block(pdf, "Angles describe the visible edges in each source frame.", x, 751, b.COL_W, 9, 2)
    elif a.get("evidence_note"):
        b.text_block(pdf, a["evidence_note"], x, 751, b.COL_W, 9, 2)


def render_page(pdf, event, a, frames, number, order, total, mode, *, right_only=False):
    x = b.MARGIN
    video = Path(event["video"]).name
    if not right_only:
        b.txt(pdf, f"MULTICAM  /  {event['case']} ROBOT AND GRIP", x, 32, 11, b.MUTED, True)
        b.text_block(pdf, f"{number:02d} {event['label']}", x, 68, b.PAGE_W - 2*x, 25, 1, b.INK, True)
        b.txt(pdf, f"{event['start']:.2f}–{event['end']:.2f} s", x, 94, 12, b.MUTED)
        rate = event.get("fps")
        suffix = f"   ·   {rate:.4g} fps" if rate else ""
        b.aligned(pdf, f"{event['id']}   ·   {video}{suffix}", b.PAGE_W - x, 94, 10, b.MUTED, 1)
        b.segment(pdf, (x, 112), (b.PAGE_W - x, 112))
        b.txt(pdf, a.get("left_title", "01   Mechanical arm or tool mask and extent"), x, 140, 16, bold=True)
        b.segment(pdf, (b.RIGHT - b.GAP/2, 128), (b.RIGHT - b.GAP/2, 776))
    title = {"pair":a.get("contact_title", "02   Contact locations, angles and resultant"),
             "axis":a.get("contact_title", "02   Working contact and tool axis"),
             "split_pair":a.get("contact_title", "02   Grasp locations, angles and resultant"),
             "region":a.get("contact_title", "02   Grasp location and contact evidence"),
             "motion":"02   Motion in the image plane",
             "marked":a.get("contact_title", "02   Marked working direction"),
             "traced_angle":a.get("contact_title", "02   Traced angles at the working interface"),
             "evidence":a.get("contact_title", "02   Working location and visible evidence")}[mode]
    b.txt(pdf, title, b.RIGHT, 140, 16, bold=True)
    images = []
    for frame in frames:
        with Image.open(frame.photo) as img:
            images.append(img.convert("RGB"))
    evidence = {"pair":a.get("evidence_title", "Loading interfaces on the specimen"),
                "axis":a.get("evidence_title", "Tool position across the three frames"),
                "split_pair":a.get("evidence_title", "Grip positions on the held timber · Camera L"),
                "region":a.get("evidence_title", "Visible clamp and timber interface"),
                "motion":"Equipment positions across the three frames",
                "marked":a.get("evidence_title", "Marked directions in the source frames"),
                "traced_angle":a.get("evidence_title", "Working interface across the three frames"),
                "evidence":a.get("evidence_title", "Working area across the three frames")}[mode]
    separate_right = mode == "traced_angle" or a.get("right_panel_traces")
    right_frames = tuple(map(right_panel_frame, frames)) if separate_right else frames
    board.grid(pdf, frames, images, evidence_title=evidence,
               single_contact_preview=(mode == "axis" and not a.get("show_sample_arrows")),
               show_region=(mode in {"region", "evidence", "traced_angle"}), show_marks=(mode == "marked"),
               right_frames=right_frames, show_left=not right_only,
               mask_title=a.get("mask_title", "Mechanical arm or tool mask"))
    if not right_only:
        board.extent(pdf, frames, a)
    if mode in {"pair", "axis"}:
        caption = "A marks the nailer tip at the panel surface." if mode == "axis" else None
        force_panel(pdf, right_frames, images, a.get("contact_caption", caption),
                    detail_index=a.get("detail_index", 1), single_force_caption=a.get("single_force_caption"),
                    panel_heading=a.get("force_heading"), model_note=a.get("model_note"),
                    single_symbol=a.get("single_symbol", "F"))
        if mode == "axis" and a.get("direction_only"):
            evidence_table(pdf, right_frames, a, include_angles=False)
        elif a.get("projected_force_angles"):
            projected_force_angles(pdf, right_frames, a, paired=(mode == "pair"))
        elif mode == "pair":
            angle_table(pdf, frames)
        else:
            axis_table(pdf, frames, a.get("axis_reference_name", "panel"), a.get("contact_statuses", (
                "Nose clear of the panel", "A · Nose reaches the panel", "Nose clear of the panel",
            )), a.get("axis_label", "Working axis"),
                a.get("angle_note", "Angles use the projected tool axis in each source frame."))
    elif mode == "split_pair":
        force_panel(pdf, frames, images, a.get("contact_caption", "Camera L · A and B at the clamp pads."),
                    detail_index=a.get("detail_index", 1), panel_heading=a.get("force_heading"),
                    model_note=a.get("model_note"))
        split_angle_table(pdf, frames, images)
    elif mode == "region":
        contact_region_panel(pdf, frames, images, a)
    elif mode == "motion":
        motion_panel(pdf, frames, images, a)
    elif mode == "traced_angle":
        traced_angle_panel(pdf, right_frames, images, a)
    elif mode == "evidence":
        evidence_panel(pdf, right_frames, images, a)
    else:
        marked_panel(pdf, frames, images, a)
    if right_only:
        pdf.showPage()
        return
    b.segment(pdf, (x, 778), (b.PAGE_W - x, 778))
    numbers = " / ".join(f"{f.number:06d}" for f in frames)
    b.txt(pdf, f"Source  {video}, frames {numbers}, {frames[0].size[0]} × {frames[0].size[1]} px.",
          x, 798, 9, b.MUTED)
    foot = {"region": a.get("region_footer", "Box A shows the visible interface region."),
            "motion": "Travel is a displacement measured in the image plane.",
            "marked": "Directions are shown in the image plane. Straight-arrow angles are rounded to 5°.",
            "evidence": "Traces describe geometry visible in the sampled frames."}.get(
                mode, "Brown line marks the reference edge. Image-plane angles are rounded to 5°.")
    b.txt(pdf, foot, x, 814, 8.8, b.MUTED)
    b.aligned(pdf, f"{order} / {total}", b.PAGE_W - x, 814, 9, b.MUTED, 1)
    pdf.showPage()


def publish_samples(samples, target, title, prepare_annotation):
    b.register_fonts()
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_suffix(".pending.pdf")
    events = {e["id"]:e for e in load_events()}
    pdf = canvas.Canvas(str(pending), pagesize=(b.PAGE_W, b.PAGE_H), pageCompression=1)
    pdf.setTitle(title)
    checks = []
    for order, (case, number, mode) in enumerate(samples, 1):
        rows = json.loads((revision.AUDIT / case / "pages.json").read_text(encoding="utf-8"))
        row = rows[number - 1]
        eid = row["id"]
        event = events[eid]
        a = prepare_annotation(case, number, eid, event)
        frames = revision.approved_frames(event, a)
        overlay_roles = a.get("overlay_roles", b.ROLES)
        assert all(f.mask and f.traced("point") for f in frames if f.role in overlay_roles), (case, number, overlay_roles)
        render_page(pdf, event, a, frames, number, order, len(samples), mode)
        checks.append((eid, mode))
    pdf.save()
    pages = PdfReader(pending).pages
    assert len(pages) == len(checks)
    for page, (eid, mode) in zip(pages, checks):
        txt = page.extract_text()
        assert eid in txt and "Common point" in txt
        assert "Resultant not readable" not in txt
        assert ("FA + FB = R" in txt) == (mode in ("pair", "split_pair"))
    pending.replace(target)
    print(target)


def main():
    publish_samples(SAMPLES, OUT / "V07_V26_V30_V04_format_samples_v4.pdf",
                    "V07, V26 and V30 | V04 layout pilot", prepare)


if __name__ == "__main__":
    main()
