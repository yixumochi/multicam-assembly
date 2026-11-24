"""Render event-level tool observation boards using the approved V04/V01 layout."""

import argparse
from dataclasses import dataclass
import json
from math import atan2, cos, degrees, hypot, isfinite, radians, sin
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops, ImageFilter
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from board_paths import EVENTS, EVIDENCE, OUTPUTS, WORK, font_path


ROLES = ("start", "middle", "end")
KINDS = ("tool", "force", "grip")
CASE_COUNTS = {
    "V01": 58, "V04": 22, "V06": 19, "V07": 27, "V11": 30,
    "V20": 21, "V21": 41, "V22": 38, "V23": 52, "V24": 33,
    "V26": 67, "V27": 78, "V28": 23, "V29": 19, "V30": 21,
}
PAGE_W, PAGE_H = 1190.55, 841.89
MARGIN, GAP = 46, 34
COL_W = (PAGE_W - MARGIN * 2 - GAP) / 2
RIGHT = MARGIN + COL_W + GAP
INK = HexColor("#142D3A")
MUTED = HexColor("#4F6570")
LINE = HexColor("#CBD9DF")
CARD = HexColor("#F5F8FA")
WHITE = HexColor("#FFFFFF")
REF = HexColor("#996118")
COLORS = tuple(map(HexColor, ("#6AC2E7", "#BAF492", "#EE751C")))
FONT, BOLD = "YaHei", "YaHei-Bold"


def register_fonts():
    for role, name in ((False, FONT), (True, BOLD)):
        pdfmetrics.registerFont(TTFont(name, font_path(role), subfontIndex=0))


@dataclass(frozen=True)
class Frame:
    role: str
    number: int
    seconds: float
    photo: Path
    size: tuple
    annotation: dict | None
    mask: Image.Image | None

    @property
    def time_label(self):
        return f"{self.seconds:.2f} s"

    def traced(self, key):
        return self.annotation.get(key) if self.annotation else None

    def angle(self, key):
        member = self.traced("member")
        line = self.traced(key)
        if member and line:
            angles = [atan2(y2 - y1, x2 - x1) for x1, y1, x2, y2 in (member, line)]
            return abs((degrees(angles[1] - angles[0]) + 90) % 180 - 90)
        return None

    def angle_label(self, key):
        angle = self.angle(key)
        if angle is not None:
            return f"about {int(angle / 5 + 0.5) * 5}°"
        if self.annotation is None or self.traced("angles_pending"):
            return "Pending review"
        return "Not readable"


def txt(c, value, x, y, size=11, color=INK, bold=False):
    c.setFillColor(color)
    c.setFont(BOLD if bold else FONT, size)
    c.drawString(x, PAGE_H - y, str(value))


def aligned(c, value, x, y, size, color, alignment, bold=False):
    width = pdfmetrics.stringWidth(value, BOLD if bold else FONT, size)
    txt(c, value, x - width * alignment, y, size, color, bold)


def wrap(value, width, size, bold=False):
    face = BOLD if bold else FONT
    lines, current = [], ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if current and pdfmetrics.stringWidth(candidate, face, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
        while pdfmetrics.stringWidth(current, face, size) > width:
            end = len(current) - 1
            while pdfmetrics.stringWidth(current[:end], face, size) > width:
                end -= 1
            lines.append(current[:end])
            current = current[end:]
    if current:
        lines.append(current)
    return lines


def text_block(c, value, x, y, width, size=9, line_count=2, color=MUTED, bold=False):
    lines = wrap(value, width, size, bold)
    face = BOLD if bold else FONT
    if len(lines) > line_count:
        lines = lines[:line_count]
        final = lines[-1]
        while pdfmetrics.stringWidth(final + "…", face, size) > width:
            final = final[:-1]
        lines[-1] = final + "…"
    for index, line in enumerate(lines):
        txt(c, line, x, y + index * (size + 2), size, color, bold)


def segment(c, p, q, color=LINE, weight=0.8, dash=()):
    c.saveState()
    c.setStrokeColor(color)
    c.setLineCap(1)
    c.setLineWidth(weight)
    if dash:
        c.setDash(dash)
    c.line(p[0], PAGE_H - p[1], q[0], PAGE_H - q[1])
    c.restoreState()


def rect(c, x, y, w, h, stroke=LINE, fill=None, radius=0):
    c.setStrokeColor(stroke or WHITE)
    c.setFillColor(fill or WHITE)
    c.setLineWidth(0.7)
    c.roundRect(x, PAGE_H - y - h, w, h, radius, stroke=bool(stroke), fill=bool(fill))


def circle(c, point, radius, fill, stroke=WHITE, weight=1):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(weight)
    c.circle(point[0], PAGE_H - point[1], radius, fill=1, stroke=1)


def picture(c, image, x, y, width, height):
    source = str(image) if isinstance(image, Path) else ImageReader(image)
    c.drawImage(source, x, PAGE_H - y - height, width, height, mask="auto")


def path_line(c, points, color, weight):
    path = c.beginPath()
    path.moveTo(points[0][0], PAGE_H - points[0][1])
    for x, y in points[1:]:
        path.lineTo(x, PAGE_H - y)
    c.setStrokeColor(color)
    c.setLineWidth(weight)
    c.drawPath(path)


def colored_mask(mask, color, opacity):
    rgb = tuple(round(channel * 255) for channel in (color.red, color.green, color.blue))
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
    alpha = ImageChops.lighter(edge, mask.point(lambda value: round(value * opacity)))
    image = Image.new("RGBA", mask.size, rgb)
    image.putalpha(alpha)
    return image


def project(point, position, draw_size, image_size):
    x, y = position
    w, h = draw_size
    source_w, source_h = image_size
    return x + point[0] * w / source_w, y + point[1] * h / source_h


def trace(c, p, q, kind, color, outline=None):
    length = hypot(q[0] - p[0], q[1] - p[1])
    if length == 0:
        return
    dash = {"force": (5, 3), "grip": (0.6, 3)}.get(kind, ())
    if outline is not None:
        segment(c, p, q, outline, 3.4, dash)
    segment(c, p, q, color, 1.8, dash)
    direction = (q[0] - p[0]) / length, (q[1] - p[1]) / length
    if kind == "force":
        for side in (-1, 1):
            wing = (
                q[0] - direction[0] * 6 - side * direction[1] * 3,
                q[1] - direction[1] * 6 + side * direction[0] * 3,
            )
            if outline is not None:
                segment(c, q, wing, outline, 3.3)
            segment(c, q, wing, color, 1.4)
    elif kind == "grip":
        for x, y in (p, q):
            end1 = x - direction[1] * 2.4, y + direction[0] * 2.4
            end2 = x + direction[1] * 2.4, y - direction[0] * 2.4
            if outline is not None:
                segment(c, end1, end2, outline, 3.4)
            segment(c, end1, end2, color, 1.4)


def frame_trace(c, frame, kind, color, position, draw_size):
    line = frame.traced(kind)
    if line:
        p, q = (project(point, position, draw_size, frame.size) for point in (line[:2], line[2:]))
        outline = WHITE if kind == "member" else INK
        trace(c, p, q, kind, color, outline)


def thumbnails(c, x, frames, show_angles):
    gutter = 10
    tile_w = (COL_W - 2 * gutter) / 3
    txt(c, "Three source frames", x, 168, 12, bold=True)
    txt(c, "The three masks", x, 312, 12, bold=True)
    for index, (frame, color) in enumerate(zip(frames, COLORS)):
        tx = x + index * (tile_w + gutter)
        tile_h = tile_w * frame.size[1] / frame.size[0]
        picture(c, frame.photo, tx, 180, tile_w, tile_h)
        if show_angles:
            frame_trace(c, frame, "member", REF, (tx, 180), (tile_w, tile_h))
            for kind in KINDS:
                frame_trace(c, frame, kind, color, (tx, 180), (tile_w, tile_h))
        elif frame.traced("point"):
            point = project(frame.traced("point"), (tx, 180), (tile_w, tile_h), frame.size)
            circle(c, point, 3.4, REF, weight=1.1)
        segment(c, (tx, 292), (tx + 14, 292), color, 2.2)
        txt(c, f"{frame.role.capitalize()}  {frame.time_label}", tx + 18, 296, 10, bold=True)
        rect(c, tx, 324, tile_w, tile_h, fill=CARD)
        if frame.mask is not None:
            picture(c, colored_mask(frame.mask, color, 0.72), tx, 324, tile_w, tile_h)
            if show_angles:
                frame_trace(c, frame, "tool", color, (tx, 324), (tile_w, tile_h))
        else:
            status = "Mask pending review"
            if frame.traced("mask_unreadable"):
                status = "Mask not readable"
            aligned(c, status, tx + tile_w / 2, 324 + tile_h / 2 + 3, 9, MUTED, 0.5)
            if frame.traced("mask_unreadable") and not show_angles:
                text_block(c, frame.traced("mask_unreadable"), tx, 432, tile_w, 8)
        if show_angles:
            for key, label, y in (("member", "Member", 436), ("tool", "Tool", 459)):
                edge_name = frame.traced(f"{key}_edge")
                if edge_name or frame.traced(key):
                    text_block(c, f"{label}  {edge_name or 'Edge name pending'}", tx, y, tile_w, 8.5)
            tool_angle = frame.angle("tool")
            force_angle = frame.angle("force")
            if tool_angle is not None and force_angle is not None:
                tool_line, force_line = frame.traced("tool"), frame.traced("force")
                tool_slope = atan2(tool_line[3] - tool_line[1], tool_line[2] - tool_line[0])
                force_slope = atan2(force_line[3] - force_line[1], force_line[2] - force_line[0])
                alignment = abs((degrees(tool_slope - force_slope) + 90) % 180 - 90)
                if frame.traced("force_along_tool") or alignment < 0.1:
                    txt(c, "Force follows tool axis", tx, 482, 8.5, MUTED)


def registered_overlay(frames, roles=None):
    selected = [(frame, color) for frame, color in zip(frames, COLORS)
                if roles is None or frame.role in roles]
    center_frame = next((frame for frame, _ in selected if frame.role == "middle"), selected[0][0])
    width, height = center_frame.size
    registered = all(frame.traced("point") for frame, _ in selected)
    ref = center_frame.traced("point") if registered else None
    offsets = [(0, 0)] * len(selected)
    if registered:
        offsets = [
            tuple(round(center - point) for center, point in zip(ref, frame.traced("point")))
            for frame, _ in selected
        ]
    # Keep any translated pixels beyond the middle frame in the enclosing box.
    left = min(offset[0] for offset in offsets)
    top = min(offset[1] for offset in offsets)
    right = max(width + offset[0] for offset in offsets)
    bottom = max(height + offset[1] for offset in offsets)
    size = right - left, bottom - top
    base = Image.new("RGBA", size)
    union = Image.new("L", size)
    for (frame, color), (dx, dy) in zip(selected, offsets):
        if frame.mask is None:
            continue
        moved = Image.new("L", size)
        moved.paste(frame.mask, (dx - left, dy - top))
        union = ImageChops.lighter(union, moved)
        base = Image.alpha_composite(base, colored_mask(moved, color, 0.42))
    bounds = union.getbbox() if registered and all(frame.mask is not None for frame, _ in selected) else None
    return base, (ref[0] - left, ref[1] - top) if ref else None, bounds


def coverage(c, frames, annotation, description):
    overlay, ref, bounds = registered_overlay(frames)
    x = MARGIN
    txt(c, "Common point", x, 459, 11, REF, bold=True)
    if ref:
        point_label = annotation.get("point_label") or frames[1].traced("member_edge") or "Member landmark"
        sought = frames[1].traced("point")
        common = f"{point_label}, middle frame ({sought[0]:g}, {sought[1]:g})"
    else:
        common = "Not traced. Overlaid at original frame positions."
    text_block(c, common, x + 92, 459, COL_W - 92, 9, 1)
    subject = annotation.get("object") or "Pending review"
    text_block(c, f"Entering object  {subject}", x, 477, COL_W, 10, 1, INK, True)
    text_block(c, description, x, 491, COL_W, 8.5, 2)
    label = "Three frames overlaid, and the extent" if bounds else "Three frames overlaid"
    txt(c, label, x, 520, 14, bold=True)
    y, h = 533, 203
    rect(c, x, y, COL_W, h, fill=CARD, radius=5)
    plot_height = h - 51
    scale = min((COL_W - 84) / overlay.width, plot_height / overlay.height)
    draw_w, draw_h = overlay.width * scale, overlay.height * scale
    plot_left = x + (COL_W - draw_w) / 2
    plot_top = y + 9 + (plot_height - draw_h) / 2
    picture(c, overlay, plot_left, plot_top, draw_w, draw_h)
    marker = (plot_left + ref[0] * scale, plot_top + ref[1] * scale) if ref else None
    if bounds:
        l, t, r, b = bounds
        a = plot_left + l * scale, plot_top + t * scale
        d = plot_left + r * scale, plot_top + b * scale
        for p, q in ((a, (d[0], a[1])), ((d[0], a[1]), d), (d, (a[0], d[1])), ((a[0], d[1]), a)):
            segment(c, p, q, MUTED, 0.85, (3, 2))
        wy = min(d[1] + 8, y + h - 34)
        wx = (a[0] + d[0]) / 2
        width_label_y = wy + 11
        if marker and abs(marker[0] - wx) < 28 and wy - 5 < marker[1] < width_label_y + 5:
            if a[1] - 24 > y:
                wy = a[1] - 8
                width_label_y = wy - 6
            else:
                wx = d[0] + 30 if marker[0] < wx else a[0] - 30
        segment(c, (a[0], wy), (d[0], wy), MUTED)
        for edge_x in (a[0], d[0]):
            segment(c, (edge_x, wy - 3), (edge_x, wy + 3), MUTED)
        aligned(c, f"W {r - l} px", wx, width_label_y, 8.5, MUTED, 0.5, True)
        hx = d[0] + 8
        hy = (a[1] + d[1]) / 2 + 3
        height_label_x, height_alignment = hx + 6, 0
        if marker and hx - 5 < marker[0] < hx + 52 and a[1] - 4 < marker[1] < d[1] + 4:
            hx = a[0] - 8
            height_label_x, height_alignment = hx - 6, 1
        segment(c, (hx, a[1]), (hx, d[1]), MUTED)
        for edge_y in (a[1], d[1]):
            segment(c, (hx - 3, edge_y), (hx + 3, edge_y), MUTED)
        aligned(c, f"H {b - t} px", height_label_x, hy, 8.5, MUTED, height_alignment, True)
    if marker:
        circle(c, marker, 3.6, REF)
    if bounds:
        note = "Translated to the middle-frame point. W and H enclose the three masks."
    elif ref:
        note = "Translated to the middle-frame point. Extent needs three readable masks."
    else:
        note = "Same frame positions. Extent needs a common point in all three frames."
    txt(c, note, x + 12, y + h - 10, 8.5, MUTED)
    text_block(c, annotation.get("note", ""), x, 752, COL_W, 9, 2)


def legend(c, x):
    for offset, kind, label in (
        (0, "member", "Member edge"),
        (120, "tool", "Tool edge"),
        (240, "force", "Force direction"),
        (372, "grip", "Grip direction"),
    ):
        start = x + offset
        if kind == "member":
            trace(c, (start, 494), (start + 18, 494), kind, REF)
        else:
            trace(c, (start, 494), (start + 18, 494), kind, INK)
        txt(c, label, start + 24, 497, 9.5, MUTED)


def angle_diagram(c, frames):
    x, y, h = RIGHT, 533, 203
    legend(c, x)
    txt(c, "On-screen angle, tool against the member edge", x, 520, 13, bold=True)
    rect(c, x, y, COL_W, h, fill=CARD, radius=5)
    origin = x + 32, y + 154

    def polar(theta, radius):
        return origin[0] + radius * cos(radians(theta)), origin[1] - radius * sin(radians(theta))

    for guide in (30, 60, 90):
        segment(c, origin, polar(guide, 107))
        px, py = polar(guide, 118)
        aligned(c, f"{guide}°", px, py + 1.5, 8, MUTED, 0.5)
    path_line(c, [polar(theta, 107) for theta in range(91)], LINE, 0.9)
    member_present = any(frame.traced("member") for frame in frames)
    segment(c, origin, polar(0, 132), REF if member_present else LINE, 1.5)
    for frame_index, (frame, color) in enumerate(zip(frames, COLORS)):
        for kind, length in zip(KINDS, (69, 81, 93)):
            angle = frame.angle(kind)
            if angle is not None:
                # Small radial offsets leave coincident angles distinguishable.
                radius = length + frame_index * 3
                trace(c, polar(angle, radius - 29), polar(angle, radius), kind, color, INK)
    circle(c, origin, 3.2, REF if member_present else MUTED)
    txt(c, "Member edge  0°" if member_present else "Member edge not traced", origin[0], origin[1] + 18, 8, MUTED)
    table_x = x + 189
    table_end = x + COL_W - 14
    segment(c, (x + 175, y + 17), (x + 175, y + h - 17))
    col_x = tuple(table_x + offset for offset in (79, 156, 239))
    txt(c, "Frame", table_x, y + 27, 9.5, bold=True)
    for header, cx in zip(("Tool edge", "Force direction", "Grip direction"), col_x):
        txt(c, header, cx, y + 27, 9.5, bold=True)
    for frame_index, (frame, color) in enumerate(zip(frames, COLORS)):
        baseline = y + 58 + frame_index * 47
        segment(c, (table_x, baseline + 22), (table_end, baseline + 22))
        segment(c, (table_x, baseline - 3), (table_x + 11, baseline - 3), color, 2.2)
        txt(c, frame.time_label, table_x + 16, baseline, 9.5, bold=True)
        contact = frame.traced("contact")
        if contact:
            txt(c, f"Contact {contact.lower()}", table_x, baseline + 14, 8.5, MUTED)
        elif frame.annotation is None:
            txt(c, "Contact pending review", table_x, baseline + 14, 8.5, MUTED)
        for kind, cx in zip(KINDS, col_x):
            txt(c, frame.angle_label(kind), cx, baseline, 9.5, MUTED)
    notes = [f"{frame.role.capitalize()}  {frame.traced('note')}" for frame in frames if frame.traced("note")]
    text_block(c, "  ·  ".join(notes), x, 752, COL_W, 9, 2)


def build_page(c, event, frames, annotation, page_index, page_count):
    case = event["case"]
    txt(c, f"MULTICAM  /  {case} TOOL OBSERVATION", MARGIN, 32, 11, MUTED, True)
    txt(c, f"{page_index:02d}   {event['label']}", MARGIN, 68, 26, INK, True)
    interval = f"{event['start']:.2f}–{event['end']:.2f} s"
    txt(c, f"Clip {interval}   ·   three sample frames", MARGIN, 94, 12, MUTED)
    fps = event.get("fps")
    rate = f"{fps:.4g} fps" if fps is not None else "FPS not recorded"
    provenance = f"{event['id']}   ·   {Path(event['video']).name}   ·   {rate}"
    aligned(c, provenance, PAGE_W - MARGIN, 94, 10, MUTED, 1)
    segment(c, (MARGIN, 112), (PAGE_W - MARGIN, 112), LINE, 1)
    txt(c, "01   Relative position and extent", MARGIN, 140, 16, bold=True)
    txt(c, "02   Change in angle", RIGHT, 140, 16, bold=True)
    segment(c, (RIGHT - GAP / 2, 128), (RIGHT - GAP / 2, 776))
    thumbnails(c, MARGIN, frames, False)
    thumbnails(c, RIGHT, frames, True)
    source_text = event["description"]
    english_source = "" if re.search(r"[\u3400-\u9fff]", source_text) else source_text
    coverage(c, frames, annotation, annotation.get("description_en") or english_source)
    angle_diagram(c, frames)
    segment(c, (MARGIN, 778), (PAGE_W - MARGIN, 778))
    width, height = frames[1].size
    numbers = " / ".join(f"{frame.number:06d}" for frame in frames)
    txt(c, f"Source  {Path(event['video']).name}, frames {numbers}, {width} × {height} px.", MARGIN, 798, 9, MUTED)
    txt(c, "Smaller on-screen angles are traced by hand to about 5°. Force direction shows direction of action. Clearance and force magnitude are unmeasured.",
        MARGIN, 814, 9, MUTED)
    aligned(c, f"{page_index} / {page_count}", PAGE_W - MARGIN, 814, 9, MUTED, 1)
    c.showPage()


def validate_coordinates(annotation, key, count, size):
    coords = annotation.get(key)
    if coords is None:
        return
    if not isinstance(coords, list) or len(coords) != count:
        raise ValueError(f"{key} requires {count} coordinates")
    pairs = zip(coords[::2], coords[1::2])
    if not all(
        isinstance(x, (int, float)) and isinstance(y, (int, float))
        and isfinite(x) and isfinite(y) and 0 <= x < size[0] and 0 <= y < size[1]
        for x, y in pairs
    ):
        raise ValueError(f"{key} coordinates outside the {size[0]} × {size[1]} source frame")
    if count == 4 and coords[:2] == coords[2:]:
        raise ValueError(f"{key} requires a nonzero line")


def load_frame(source, annotation, draft):
    photo = EVIDENCE / source["image"]
    with Image.open(photo) as image:
        size = image.size
    if size != tuple(source["saved_size"]):
        raise ValueError(f"{photo.name} is {size}; source records {source['saved_size']}")
    mask = None
    if annotation is None:
        if not draft:
            raise ValueError("frame annotation missing")
    else:
        for key in ("point", "member", *KINDS):
            validate_coordinates(annotation, key, 2 if key == "point" else 4, size)
        if annotation.get("mask"):
            with Image.open(Path(annotation["mask"])) as image:
                mask = image.convert("L")
            if mask.size != size:
                raise ValueError(f"mask size {mask.size} differs from {size}")
            histogram = mask.histogram()
            if not histogram[255] or sum(histogram[1:255]):
                raise ValueError("mask must be binary (0/255) and contain foreground")
        if not draft:
            if mask is None and not annotation.get("mask_unreadable"):
                raise ValueError("mask missing without a mask_unreadable reason")
            if annotation.get("angles_pending"):
                raise ValueError("angle review is incomplete")
            if annotation.get("contact") not in ("Confirmed", "Unconfirmed"):
                raise ValueError("contact must be Confirmed or Unconfirmed")
            for key in ("member", "tool"):
                if annotation.get(key) and not annotation.get(f"{key}_edge"):
                    raise ValueError(f"{key} line requires its edge name")
    return Frame(
        source["role"], source["frame_zero_based"], source["source_pts_seconds"], photo,
        size, annotation, mask,
    )


def load_frames(event, annotation, draft):
    selected = {}
    for source in event["frames"]:
        if source["role"] in ROLES:
            if source["role"] in selected:
                raise ValueError(f"duplicate source frame role {source['role']}")
            selected[source["role"]] = source
    if set(selected) != set(ROLES):
        raise ValueError("source must include start, middle, and end")
    frames = []
    for role in ROLES:
        try:
            frames.append(load_frame(selected[role], annotation.get("frames", {}).get(role), draft))
        except (OSError, ValueError) as error:
            raise ValueError(f"{role}: {error}") from error
    if len({frame.size for frame in frames}) != 1:
        raise ValueError("source frame sizes differ within the event")
    return frames


def load_case(case, annotation_path, event_id, draft):
    events = json.loads(EVENTS.read_text(encoding="utf-8-sig"))
    events = [event for event in events if event["case"] == case]
    if case == "V04":
        events.sort(key=lambda event: (event["start"], event["id"]))
    elif case == "V26":
        events.sort(key=lambda event: (event["video"], event["start"]))
    else:
        events.sort(key=lambda event: event["start"])
    if len(events) != CASE_COUNTS[case] or len({event["id"] for event in events}) != len(events):
        raise ValueError(f"invalid event count or duplicate event ID for {case}")
    if annotation_path.exists():
        annotations = json.loads(annotation_path.read_text(encoding="utf-8-sig"))
    elif draft:
        annotations = {}
    else:
        raise ValueError(f"annotation file is missing: {annotation_path}")
    if event_id:
        events = [event for event in events if event["id"] == event_id]
    if not events:
        raise ValueError(f"event {event_id} not found in {case}")
    for event in events:
        annotation = annotations.get(event["id"], {})
        if not draft and not annotation.get("object"):
            raise ValueError(f"{event['id']}: entering object identity missing")
        try:
            load_frames(event, annotation, draft)
        except ValueError as error:
            raise ValueError(f"{event['id']}: {error}") from error
    return [(event, annotations.get(event["id"], {})) for event in events]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASE_COUNTS, required=True)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--event-id")
    parser.add_argument("--draft", action="store_true", help="Allow pending annotations and save under work only")
    args = parser.parse_args()
    if args.event_id and not args.draft:
        parser.error("--event-id requires --draft")
    annotation_path = args.annotations or WORK / "annotations" / f"{args.case}.json"
    filename = f"{args.case}_object_board.pdf"
    default_dir = WORK / "drafts" if args.draft else OUTPUTS
    if args.event_id:
        filename = f"{args.case}_{args.event_id}_draft.pdf"
    output = (args.output or default_dir / filename).resolve()
    if args.draft and not output.is_relative_to(WORK):
        parser.error("--draft output must be under work")
    pairs = load_case(args.case, annotation_path, args.event_id, args.draft)
    output.parent.mkdir(parents=True, exist_ok=True)
    register_fonts()
    temp = output.with_suffix(".pending.pdf")
    board = canvas.Canvas(str(temp), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    title = f"{args.case} relative position and tool, force, and grip direction"
    board.setTitle(f"{title} (annotation draft)" if args.draft else title)
    try:
        for page_index, (event, annotation) in enumerate(pairs, 1):
            frames = load_frames(event, annotation, args.draft)
            build_page(board, event, frames, annotation, page_index, len(pairs))
        board.save()
        temp.replace(output)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    print(f"{len(pairs)} page(s) written to {output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
