"""Render complete case boards in the approved V04 robot-mask/resultant layout."""

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from math import atan2, degrees, hypot, isfinite
from pathlib import Path
import re

from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from machine_board import tint
import render_boards as b
from review_frames import load_events
from robot_force_board import CA, CB, CR, arrow, font, point, tag


ROOT = b.WORK / "replication"
CONTACT_COLORS = CA, CB
TILE_W = (b.COL_W - 20) / 3
TILE_H = TILE_W * 9 / 16


@dataclass(frozen=True)
class Contact:
    position: complex
    direction: complex | None
    label: str | None = None


@dataclass(frozen=True)
class Pair:
    a: Contact
    b: Contact

    @property
    def ua(self):
        return self.a.direction

    @property
    def ub(self):
        return self.b.direction

    @property
    def resultant(self):
        return self.ua + self.ub

    @property
    def cancels_at_resolution(self):
        # Lines are reported to 5 degrees. Opposing bearings within that
        # resolution do not support a stable resultant direction at 1:1.
        return abs(self.resultant) < 0.088

    @property
    def application(self):
        separation = self.b.position - self.a.position
        denom = (separation.conjugate() * self.resultant).imag
        if abs(denom) < 1e-6:
            return None
        fraction = (separation.conjugate() * self.ub).imag / denom
        if 0 <= fraction <= 1:
            return self.a.position + fraction * separation
        return None


def read_contact(raw, size):
    coords = raw["point"]
    b.validate_coordinates({"point": coords}, "point", 2, size)
    label = raw.get("label")
    if label is not None and label not in {"A", "B"}:
        raise ValueError(f"Invalid contact label: {label}")
    line = raw.get("line")
    if line is None:
        return Contact(complex(*coords), None, label)
    b.validate_coordinates({"line": line}, "line", 4, size)
    direction = complex(*line[2:]) - complex(*line[:2])
    return Contact(complex(*coords), direction / abs(direction), label)


def checked_case(case, annotation_path=None):
    events = [e for e in load_events() if e["case"] == case]
    if case == "V04":
        events.sort(key=lambda e: (e["start"], e["id"]))
    elif case == "V26":
        events.sort(key=lambda e: (e["video"], e["start"]))
    else:
        events.sort(key=lambda e: e["start"])
    path = annotation_path or ROOT / f"{case}.json"
    records = json.loads(path.read_text(encoding="utf-8-sig"))
    earlier = json.loads((b.WORK / "annotations" / f"{case}.json").read_text(encoding="utf-8-sig"))
    assert len(events) == b.CASE_COUNTS[case] and {e["id"] for e in events} == set(records)
    checked_images = set()
    for event in events:
        eid = event["id"]
        a = records[eid]
        assert a["object"] and set(a["frames"]) == set(b.ROLES), eid
        for state in a["frames"].values():
            state["contact"] = "Confirmed" if state.get("contacts") else "Unconfirmed"
            if state.get("member"):
                state.setdefault("member_edge", "Traced reference member edge")
            if state.get("tool"):
                state.setdefault("tool_edge", "Traced held timber edge")
        fs = b.load_frames(event, a, False)
        for frame in fs:
            raw = frame.traced("contacts") or []
            assert len(raw) <= 2, (eid, frame.role, raw)
            contacts = tuple(read_contact(c, frame.size) for c in raw)
            if len(contacts) == 2:
                assert abs(contacts[0].position - contacts[1].position) > 1, (eid, frame.role)
            frame.annotation["read_contacts"] = contacts
            if frame.photo not in checked_images:
                meta = next(f for f in event["frames"] if f["role"] == frame.role)
                with frame.photo.open("rb") as handle:
                    assert hashlib.file_digest(handle, "sha256").hexdigest() == meta["sha256"]
                checked_images.add(frame.photo)
        a["english_description"] = a.get("description_en") or earlier[eid].get("description_en") or event["description"]
        assert not re.search(r"[\u3400-\u9fff]", a["english_description"]), (eid, a["english_description"])
        yield event, a, fs


def get_pair(f):
    contacts = f.traced("read_contacts")
    if len(contacts) == 2 and all(c.direction is not None for c in contacts):
        return Pair(*contacts)
    return None


def fit_crop(size, rect, ratio, padding=1.16):
    width, height = size
    if not rect:
        rect = (0, 0, width, height)
    a, top, z, bottom = rect
    cx, cy = (a + z) / 2, (top + bottom) / 2
    rw = max(20, z - a)
    rh = max(20, bottom - top)
    rw = padding * max(rw, rh * ratio)
    rh = rw / ratio
    scale = max(rw / width, rh / height, 1)
    rw, rh = rw / scale, rh / scale
    left = min(max(0, cx - rw / 2), width - rw)
    y = min(max(0, cy - rh / 2), height - rh)
    return (left, y, left + rw, y + rh)


def crop(img, roi, pixel_size):
    return img.transform(pixel_size, Image.Transform.EXTENT, roi, Image.Resampling.BICUBIC)


def photo(c, image, x, y, width, height):
    encoded = BytesIO()
    image.save(encoded, format="JPEG", quality=92, subsampling=0)
    encoded.seek(0)
    b.picture(c, encoded, x, y, width, height)


def cancelling_pair(pair, width, height):
    image = Image.new("RGB", (width, height), "#F5F8FA")
    draw = ImageDraw.Draw(image)
    center = complex(width / 2, height * .40)
    length = min(width, height) * .42
    gap = 1j * pair.ua * (height * .14)
    a = center - pair.ua * (length / 2) - gap / 2
    b0 = center - pair.ub * (length / 2) + gap / 2
    stroke = max(4, round(width / 106))
    arrow(draw, a, a + pair.ua * length, CA, stroke)
    arrow(draw, b0, b0 + pair.ub * length, CB, stroke)
    draw.text((width / 2, height * .78), "R ≈ 0 at 1:1", font=font(round(height * .085), True), fill=CR, anchor="mm")
    return image


def force_construction(pair, width, height):
    image = Image.new("RGB", (width, height), "#F5F8FA")
    draw = ImageDraw.Draw(image)
    limit = min(width, height)
    normal = 1j * pair.resultant / abs(pair.resultant)
    spacing = normal * (limit * .20)
    start = 0j
    turn = pair.ua * (limit * .30)
    end = turn + pair.ub * (limit * .30)
    labels = (
        (turn / 2 - normal * (limit * .11), "FA", CA),
        ((turn + end) / 2 - normal * (limit * .11), "FB", CB),
        (end / 2 + spacing + normal * (limit * .10), "R", CR),
    )
    positions = (start, turn, end, start + spacing, end + spacing, *(p for p, _, _ in labels))
    min_x, max_x = min(p.real for p in positions), max(p.real for p in positions)
    min_y, max_y = min(p.imag for p in positions), max(p.imag for p in positions)
    shift = complex((width - min_x - max_x) / 2, (height - min_y - max_y) / 2)
    for tip in (start, end):
        for j in range(0, 24, 2):
            p = tip + shift + spacing * (j / 24)
            draw.line((point(p), point(p + spacing / 24)), fill="#93AAB0", width=2)
    stroke = max(3, round(width / 110))
    arrow(draw, start + shift, turn + shift, CA, stroke)
    arrow(draw, turn + shift, end + shift, CB, stroke)
    arrow(draw, start + spacing + shift, end + spacing + shift, CR, stroke)
    for position, caption, color in labels:
        draw.text(point(position + shift), caption, font=font(max(14, round(limit * .072)), True), fill=color, anchor="mm")
    return image


def single_force_diagram(direction, width, height, label="A", symbol="F"):
    image = Image.new("RGB", (width, height), "#F5F8FA")
    draw = ImageDraw.Draw(image)
    center = complex(width / 2, height / 2)
    half_arrow = direction * (min(width, height) * .19)
    ink = CONTACT_COLORS["AB".index(label)]
    arrow(draw, center - half_arrow, center + half_arrow, ink, max(3, round(width / 110)))
    position = center - 1j * direction * (min(width, height) * .11)
    draw.text(point(position), symbol + label, font=font(round(height * .072), True), fill=ink, anchor="mm")
    return image


def draw_marked_arrows(image, marks, transform, *, halo=False):
    draw = ImageDraw.Draw(image)
    width, height = image.size
    stroke = max(4, round(width / 125))
    for index, mark in enumerate(marks):
        points = [transform(complex(*p)) for p in mark]
        ink = CONTACT_COLORS[index]
        if len(points) > 2:
            path = [point(p) for p in points]
            if halo:
                draw.line(path, fill="white", width=stroke + 3, joint="curve")
            draw.line(path, fill=ink, width=stroke, joint="curve")
        arrow(draw, points[-2], points[-1], ink, stroke, halo)
        if len(marks) == 2:
            tail = points[0]
            tag(draw, (min(max(tail.real, 16), width - 16),
                       min(max(tail.imag - 4 * stroke, 16), height - 16)),
                "AB"[index], ink, max(14, round(width / 35)))


def marked_photo(f, source, pixels):
    marks = f.traced("marked_arrows") or ()
    rect = f.traced("marked_crop") or f.traced("force_crop") or f.traced("roi")
    if not rect and f.mask:
        rect = f.mask.getbbox()
    if marks:
        xs, ys = zip(*(p for mark in marks for p in mark))
        around = min(xs) - 24, min(ys) - 20, max(xs) + 24, max(ys) + 20
        if rect:
            rect = min(rect[0], around[0]), min(rect[1], around[1]), max(rect[2], around[2]), max(rect[3], around[3])
        else:
            rect = around
    box = fit_crop(f.size, rect, pixels[0] / pixels[1])
    image = crop(source, box, pixels)
    origin = complex(*box[:2])
    scale = pixels[0] / (box[2] - box[0])
    draw_marked_arrows(image, marks, lambda p: (p - origin) * scale, halo=True)
    return image


def marked_diagram(marks, pixels):
    xs, ys = zip(*(p for mark in marks for p in mark))
    width, height = pixels
    center = complex(width / 2, height / 2)
    origin = complex((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    scale = min(width * .58 / max(max(xs) - min(xs), 1), height * .50 / max(max(ys) - min(ys), 1))
    image = Image.new("RGB", pixels, "#F5F8FA")
    draw_marked_arrows(image, marks, lambda p: center + (p - origin) * scale)
    return image


def plot_on_photo(f, image, pixels, show_sum=False, *, show_contact_arrows=True, show_tool_axis=True,
                  show_region=False):
    contacts = f.traced("read_contacts")
    pair = get_pair(f) if show_sum else None
    w, h = pixels
    vec_native = f.traced("force_arrow_length") or min(f.size) * .044
    force_crop = f.traced("force_crop")
    rect = force_crop or f.traced("roi")
    region = f.traced("contact_region") if show_region and not contacts else None
    if region and not force_crop:
        left, top, right, bottom = region
        rect = left - 52, top - 43, right + 64, bottom + 44
    plotted = [(c.position, c.direction) for c in contacts if c.direction is not None]
    if pair and not pair.cancels_at_resolution and pair.application is not None:
        plotted.append((pair.application, pair.resultant))
    for p, direction in plotted:
        for value, delta, boundary in zip(point(p), point(direction), f.size):
            if delta > 0:
                vec_native = min(vec_native, max(1, (boundary - 5 - value) / delta))
            elif delta < 0:
                vec_native = min(vec_native, max(1, (value - 5) / -delta))
    if contacts and not force_crop:
        horizontal_margin = 82 if len(contacts) == 1 else 36
        vertical_margin = 48 if len(contacts) == 1 else 25
        locations = [c.position for c in contacts]
        locations.extend(c.position + c.direction * vec_native for c in contacts if c.direction is not None)
        if pair and not pair.cancels_at_resolution and pair.application is not None:
            locations += [pair.application, pair.application + pair.resultant * vec_native]
        rect = (
            min(uv.real for uv in locations) - horizontal_margin,
            min(uv.imag for uv in locations) - vertical_margin,
            max(uv.real for uv in locations) + horizontal_margin,
            max(uv.imag for uv in locations) + vertical_margin,
        )
    elif not rect and f.mask:
        rect = f.mask.getbbox()
    box = fit_crop(f.size, rect, w / h, 1.16)
    result = crop(image, box, pixels)
    draw = ImageDraw.Draw(result)
    scale = w / (box[2] - box[0])
    stroke = max(3, round(w / 140))
    force_reference = f.traced("force_reference")
    reference = force_reference or f.traced("member")
    tool = f.traced("tool") if show_tool_axis and not force_reference else None
    for line, color in ((reference, "#996118"), (tool, "#3C5670")):
        if line:
            start = ((line[0] - box[0]) * scale, (line[1] - box[1]) * scale)
            end = ((line[2] - box[0]) * scale, (line[3] - box[1]) * scale)
            draw.line((start, end), fill="white", width=stroke + 2)
            draw.line((start, end), fill=color, width=max(2, stroke - 1))
    for i, contact in enumerate(contacts):
        label = contact.label or "AB"[i]
        color = CONTACT_COLORS["AB".index(label)]
        px, py = point(contact.position)
        p = complex((px - box[0]) * scale, (py - box[1]) * scale)
        if show_contact_arrows and contact.direction is not None:
            arrow(draw, p, p + contact.direction * scale * vec_native, color, stroke, True)
        r = stroke + 1
        draw.ellipse((p.real - r, p.imag - r, p.real + r, p.imag + r), fill="white", outline=color, width=2)
        direction = contact.direction or (-1j)
        pos = p - direction * (4 * stroke)
        x = min(max(pos.real, 15), w - 15)
        y = min(max(pos.imag, 15), h - 15)
        tag(draw, (x, y), label, color, max(13, round(w / 30)))
    if region:
        area = tuple((value - box[i % 2]) * scale for i, value in enumerate(region))
        draw.rectangle(area, outline="white", width=stroke + 3)
        draw.rectangle(area, outline=CA, width=stroke)
        tag(draw, (area[0] + 2 * stroke, area[1] - 3 * stroke), "A", CA, max(13, round(w / 30)))
    if pair and not pair.cancels_at_resolution and pair.application is not None:
        p = (pair.application - complex(box[0], box[1])) * scale
        arrow(draw, p, p + pair.resultant * scale * vec_native, CR, stroke + 1, True)
        d = pair.resultant / abs(pair.resultant)
        pos = p - d * (4 * stroke)
        x = min(max(pos.real, 15), w - 15)
        y = min(max(pos.imag, 15), h - 15)
        tag(draw, (x, y), "R", CR, max(13, round(w / 30)))
    return result


def grid(c, fs, images, evidence_title="Grip locations on the held member",
         *, single_contact_preview=False, show_region=False, show_marks=False, right_frames=None,
         show_left=True, mask_title="Mechanical arm or tool mask"):
    if show_left:
        b.txt(c, "Three source frames", b.MARGIN, 168, 12, bold=True)
        b.txt(c, mask_title, b.MARGIN, 312, 12, bold=True)
    b.txt(c, evidence_title, b.RIGHT, 168, 12, bold=True)
    for j, (f, right, image, col) in enumerate(zip(fs, right_frames or fs, images, b.COLORS)):
        lx = b.MARGIN + j * (TILE_W + 10)
        rx = b.RIGHT + j * (TILE_W + 10)
        if show_left:
            b.picture(c, f.photo, lx, 180, TILE_W, TILE_H)

            def to_frame(p):
                return lx + p[0] * TILE_W / f.size[0], 180 + p[1] * TILE_H / f.size[1]

            line = f.traced("member")
            if line:
                start, end = to_frame(line[:2]), to_frame(line[2:])
                b.segment(c, start, end, b.WHITE, 2.1)
                b.segment(c, start, end, b.REF, 1.1)
            anchor = f.traced("point")
            if anchor:
                b.circle(c, to_frame(anchor), 2.6, b.REF, b.WHITE, 1)
            if f.mask:
                roi = fit_crop(f.size, f.traced("mask_crop") or f.mask.getbbox(), 16 / 9)
                photo(c, crop(tint(image, f.mask, col), roi, (640, 360)), lx, 324, TILE_W, TILE_H)
            else:
                b.rect(c, lx, 324, TILE_W, TILE_H, fill=b.CARD)
                b.aligned(c, f.traced("mask_placeholder") or "Mask not readable",
                          lx + TILE_W / 2, 365, 9.2, b.MUTED, .5, True)
                b.text_block(c, f.traced("mask_unreadable"), lx + 9, 385, TILE_W - 18, 8.3, 3)
        if show_marks:
            preview = marked_photo(right, image, (640, 360))
        else:
            preview = plot_on_photo(right, image, (640, 360),
                                    show_contact_arrows=not single_contact_preview,
                                    show_tool_axis=not single_contact_preview, show_region=show_region)
        photo(c, preview, rx, 180, TILE_W, TILE_H)
        for x in ((lx, rx) if show_left else (rx,)):
            b.segment(c, (x, 292), (x + 14, 292), col, 2.2)
            b.txt(c, f"{f.role.capitalize()}  {f.time_label}", x + 17, 296, 9.4, bold=True)


def extent(c, fs, a):
    x = b.MARGIN
    roles = a.get("overlay_roles")
    separate = a.get("separate_masks")
    b.txt(c, "Common point", x, 456, 11, b.REF, True)
    overlay, ref, bounds = (None, None, None) if separate else b.registered_overlay(fs, roles)
    if ref is not None:
        selected = [frame for frame in fs if not roles or frame.role in roles]
        source = next((frame for frame in selected if frame.role == "middle"), selected[0])
        point_value = source.traced("point")
        point_label = a.get("point_label") or "Traced member landmark"
        common = f"{point_label}, {source.role} frame ({point_value[0]:g}, {point_value[1]:g})"
    else:
        common = a.get("common_point_status", "Not traced through all three frames.")
    b.text_block(c, common, x + 92, 456, b.COL_W - 92, 8.7, 2)
    subject_label = a.get("subject_label") or (
        "Highlighted equipment" if any(f.mask for f in fs) else "Event subject"
    )
    b.text_block(c, subject_label + "   " + a["object"], x, 477, b.COL_W, 10, 1, b.INK, True)
    b.text_block(c, a["english_description"], x, 492, b.COL_W, 8.5, 2)
    target = a.get("alignment_target", "the member")
    title = f"Machine masks aligned to {target}" if ref else "Machine masks in source positions"
    if roles and len(roles) == 1:
        title = "Visible machine mask and extent"
    if separate:
        title = "Visible equipment extent by frame"
    b.txt(c, a.get("overlay_title", title), x, 520, 13, bold=True)
    b.rect(c, x, 533, b.COL_W, 203, fill=b.CARD, radius=5)
    if separate:
        separate_extents(c, fs, a)
        b.text_block(c, a.get("note") or "", x, 752, b.COL_W, 9, 2)
        return
    extent_box = overlay.getbbox()
    if extent_box:
        l, t, r, bot = extent_box
        if ref:
            l, t, r, bot = min(l, ref[0]), min(t, ref[1]), max(r, ref[0]), max(bot, ref[1])
        crop_box = int(l - 9), int(t - 9), int(r + 10), int(bot + 10)
        patch = overlay.crop(crop_box)
        scale = min((b.COL_W - 110) / patch.width, 144 / patch.height)
        dw, dh = patch.width * scale, patch.height * scale
        left, top = x + (b.COL_W - dw) / 2, 541 + (144 - dh) / 2
        b.picture(c, patch, left, top, dw, dh)
        def locate(p):
            return left + (p[0] - crop_box[0]) * scale, top + (p[1] - crop_box[1]) * scale
        if bounds:
            a0, d0 = locate(bounds[:2]), locate(bounds[2:])
            for p, q in ((a0, (d0[0], a0[1])), ((d0[0], a0[1]), d0), (d0, (a0[0], d0[1])), ((a0[0], d0[1]), a0)):
                b.segment(c, p, q, b.MUTED, .75, (3, 2))
            width_label = f"W {bounds[2] - bounds[0]} px"
            label_x, label_y = (a0[0] + d0[0]) / 2, d0[1] + 12
            if ref:
                ref_x, ref_y = locate(ref)
                label_half = pdfmetrics.stringWidth(width_label, b.BOLD, 9) / 2
                if abs(ref_x - label_x) < label_half + 4 and label_y - 11 < ref_y < label_y + 5:
                    label_y = ref_y + 14
            b.aligned(c, width_label, label_x, label_y, 9, b.MUTED, .5, True)
            b.txt(c, f"H {bounds[3] - bounds[1]} px", d0[0] + 9, (a0[1] + d0[1]) / 2, 9, b.MUTED, True)
        if ref:
            b.circle(c, locate(ref), 2.8, b.REF)
    else:
        b.aligned(c, "Machine silhouette unresolved in all three samples", x + b.COL_W / 2, 622, 10, b.MUTED, .5)
    note = ("Three translated machine masks. Extent in source-frame pixels." if bounds else
            "Member landmark traced. Extent needs three readable masks." if ref else
            "Translation and extent require a shared member landmark.")
    if roles and bounds:
        selected_roles = " and ".join(roles).capitalize()
        if len(roles) == 1:
            note = f"{selected_roles} mask only. Extent in source-frame pixels."
        else:
            note = f"{selected_roles} masks aligned within their shared shot. Extent in source-frame pixels."
    b.txt(c, a.get("overlay_note", note), x + 12, 724, 8.7, b.MUTED)
    b.text_block(c, a.get("note") or "", x, 752, b.COL_W, 9, 2)


def separate_extents(c, frames, a):
    x = b.MARGIN + 11
    span = (b.COL_W - 22) / 3
    if not any(frame.mask for frame in frames):
        b.text_block(c, a["mask_summary"], x + 9, 612, b.COL_W - 40, 10, 3)
        return
    for i, (frame, color) in enumerate(zip(frames, b.COLORS)):
        left = x + i * span
        center = left + span / 2
        b.aligned(c, frame.role.capitalize(), center, 555, 9.6, b.MUTED, .5, True)
        if i:
            b.segment(c, (left, 548), (left, 701))
        if frame.mask:
            bounds = frame.mask.getbbox()
            silhouette = b.colored_mask(frame.mask.crop(bounds), color, .54)
            scale = min((span - 22) / silhouette.width, 104 / silhouette.height)
            width, height = silhouette.width * scale, silhouette.height * scale
            b.picture(c, silhouette, center - width / 2, 565 + (103 - height) / 2, width, height)
            b.aligned(c, f"W {silhouette.width} px   H {silhouette.height} px",
                      center, 694, 8.8, b.MUTED, .5, True)
        else:
            b.aligned(c, "—", center, 621, 12, b.MUTED, .5, True)
    b.txt(c, "Each extent is measured in its own source frame.", x, 724, 8.7, b.MUTED)


def sum_panel(c, fs, images):
    x = b.RIGHT
    pairs = tuple(get_pair(f) for f in fs)
    index = next((i for i in (1, 0, 2) if pairs[i]), None)
    if index is None:
        index = max((1, 0, 2), key=lambda i: len(fs[i].traced("read_contacts")))
    f = fs[index]
    pair = pairs[index]
    label = f"{f.role.capitalize()} frame   ·   Equal-force model at two contacts" if pair else f"{f.role.capitalize()} frame   ·   Grip detail"
    b.txt(c, label, x, 322, 12, bold=True)
    width = (b.COL_W - 10) / 2
    height = width * .63
    y = 333
    photo(c, plot_on_photo(f, images[index], (720, 454), True), x, y, width, height)
    rx = x + width + 10
    if pair and not pair.cancels_at_resolution:
        b.picture(c, force_construction(pair, 720, 454), rx, y, width, height)
        label_left = "A and B mark the two visible interfaces."
        label_right = "FA + FB = R, drawn head to tail."
    elif pair:
        b.picture(c, cancelling_pair(pair, 720, 454), rx, y, width, height)
        label_left = "Two opposing projected directions."
        label_right = "The equal-force model has no stable R angle."
    else:
        b.rect(c, rx, y, width, height, fill=b.CARD)
        b.txt(c, "Resultant not readable", rx + 17, y + 36, 12, b.INK, True)
        if len(f.traced("read_contacts")) == 1:
            reason = "One interface is visible in the selected frame. A second direction is needed to combine two forces."
        else:
            reason = ("Both directions are needed for the two-force construction." if f.traced("read_contacts") else
                      "Two interfaces and their directions are unresolved in these samples.")
        b.text_block(c, reason, rx + 17, y + 62, width - 34, 9.4, 4)
        label_left = f"Frame {f.number:06d}   ·   {f.time_label}"
        label_right = "Grip visibility assessed in each sample."
    b.text_block(c, label_left, x, y + height + 14, width, 8.7, 1)
    b.text_block(c, label_right, rx, y + height + 14, width, 8.7, 1)
    notes = [f"{u.role.capitalize()} {u.traced('note')}" for u in fs if u.traced("note")]
    if notes:
        b.text_block(c, "  ·  ".join(dict.fromkeys(notes)), x, 526, b.COL_W, 8.2, 2)


def angle_label(line_vector, reference):
    if line_vector is None or reference is None:
        return "Not readable"
    u = complex(*reference[2:]) - complex(*reference[:2])
    shift = u.conjugate() * line_vector
    acute = abs((degrees(atan2(shift.imag, shift.real)) + 90) % 180 - 90)
    return f"about {int(acute / 5 + .5) * 5}°"


def angle_panel(c, fs):
    x = b.RIGHT
    b.txt(c, "On-screen angles to the traced member edge", x, 556, 13, bold=True)
    b.rect(c, x, 568, b.COL_W, 165, fill=b.CARD, radius=5)
    cols = [x + 14, x + 120, x + 217, x + 311, x + 405]
    for xx, label in zip(cols, ("Sample", "Tool / grip axis", "FA at A", "FB at B", "R (1:1 model)")):
        b.txt(c, label, xx, 588, 9.5, bold=True)
    for j, (f, col) in enumerate(zip(fs, b.COLORS)):
        y = 615 + j * 39
        b.segment(c, (cols[0], y - 3), (cols[0] + 10, y - 3), col, 2)
        b.txt(c, f.time_label, cols[0] + 15, y, 9.6, bold=True)
        ref = f.traced("member")
        tool = f.traced("tool")
        contacts = f.traced("read_contacts")
        pair = get_pair(f)
        dirs = [contact.direction for contact in contacts]
        dirs += [None] * (2 - len(dirs))
        values = [
            angle_label(complex(*tool[2:]) - complex(*tool[:2]) if tool else None, ref),
            angle_label(dirs[0], ref),
            angle_label(dirs[1], ref),
            "R ≈ 0" if pair and pair.cancels_at_resolution else angle_label(pair.resultant if pair else None, ref),
        ]
        for k, (xx, val) in enumerate(zip(cols[1:], values)):
            color = b.MUTED if val == "Not readable" else (b.INK, b.HexColor(CA), b.HexColor(CB), b.HexColor(CR))[k]
            b.txt(c, val, xx, y, 9.6, color, k == 3 and val != "Not readable")
        b.segment(c, (x + 12, y + 12), (x + b.COL_W - 12, y + 12))
    if any(get_pair(f) for f in fs):
        note = "The model uses equal projected force magnitudes. R combines the two annotated contacts."
    else:
        note = "Force directions rely on visible interfaces. A two-force resultant needs two traceable directions."
    b.text_block(c, note, x, 751, b.COL_W, 9, 2)


def page(c, event, a, fs, index, total):
    x = b.MARGIN
    case = event["case"]
    b.txt(c, f"MULTICAM  /  {case} ROBOT AND GRIP", x, 32, 11, b.MUTED, True)
    b.text_block(c, f"{index:02d}   {event['label']}", x, 68, b.PAGE_W - 2 * x, 25, 1, b.INK, True)
    b.txt(c, f"{event['start']:.2f}–{event['end']:.2f} s", x, 94, 12, b.MUTED)
    source_video = Path(event["video"]).name
    rate = event.get("fps")
    provenance = f"{event['id']}   ·   {source_video}"
    if rate is not None:
        provenance += f"   ·   {rate:.4g} fps"
    b.aligned(c, provenance, b.PAGE_W - x, 94, 10, b.MUTED, 1)
    b.segment(c, (x, 112), (b.PAGE_W - x, 112))
    b.txt(c, "01   Mechanical arm mask and extent", x, 140, 16, bold=True)
    b.txt(c, "02   Grasp locations, angles and resultant", b.RIGHT, 140, 16, bold=True)
    b.segment(c, (b.RIGHT - b.GAP / 2, 128), (b.RIGHT - b.GAP / 2, 776))
    images = []
    for f in fs:
        with Image.open(f.photo) as raw:
            images.append(raw.convert("RGB"))
    grid(c, fs, images)
    extent(c, fs, a)
    sum_panel(c, fs, images)
    angle_panel(c, fs)
    b.segment(c, (x, 778), (b.PAGE_W - x, 778))
    w, h = fs[1].size
    nums = " / ".join(f"{f.number:06d}" for f in fs)
    b.txt(c, f"Source  {source_video}, frames {nums}, {w} × {h} px.", x, 798, 9, b.MUTED)
    b.txt(c, "Brown timber edge = 0°. Blue-grey = tool or grasp axis. Angles rounded to 5°. Contact force magnitudes are unmeasured.",
          x, 814, 8.8, b.MUTED)
    b.aligned(c, f"{index} / {total}", b.PAGE_W - x, 814, 9, b.MUTED, 1)
    c.showPage()


def render(case, annotation_path=None, out=None):
    events = list(checked_case(case, annotation_path))
    out = out or ROOT / f"{case}_robot_mask_grip_resultant.pdf"
    pending = out.with_suffix(".pending.pdf")
    c = canvas.Canvas(str(pending), pagesize=(b.PAGE_W, b.PAGE_H), pageCompression=1)
    c.setTitle(f"{case} | Mechanical arm masks, grip locations and resultants")
    stats = Counter()
    for j, (e, a, fs) in enumerate(events, 1):
        page(c, e, a, fs, j, len(events))
        for f in fs:
            pair = get_pair(f)
            stats["masks" if f.mask else "mask limits"] += 1
            stats["contacts"] += len(f.traced("read_contacts"))
            stats["pairs"] += bool(pair)
            stats["cancels"] += bool(pair and pair.cancels_at_resolution)
        stats["pages with pairs"] += any(get_pair(f) for f in fs)
    c.save()
    pdf = PdfReader(pending)
    assert len(pdf.pages) == len(events)
    for p, (e, a, fs) in zip(pdf.pages, events):
        body = " ".join(p.extract_text().split())
        assert all(t in body for t in (e["id"], e["label"], " ".join(a["english_description"].split()),
                                      "Mechanical arm or tool mask", "R (1:1 model)", *(f"{f.number:06d}" for f in fs))), e["id"]
        assert abs(float(p.mediabox.width) - b.PAGE_W) < .02 and abs(float(p.mediabox.height) - b.PAGE_H) < .02
    pending.replace(out)
    print(case, len(events), dict(stats), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="+", choices=sorted(b.CASE_COUNTS))
    args = parser.parse_args()
    b.register_fonts()
    for case in args.cases:
        render(case)
