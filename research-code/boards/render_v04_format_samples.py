"""Apply the confirmed V04 layout to two source-checked transfer examples."""

import json
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas

import replicate_force_boards as board
import render_boards as layout
import revise_force_boards as revision
from review_frames import load_events
from robot_force_board import CA, CB, CR


SAMPLES = (("V24", 19), ("V28", 8))
OUTPUT = layout.OUTPUTS / "v04_format_samples"


def angle_table(pdf, frames):
    x = layout.RIGHT
    layout.txt(pdf, "On-screen angles to the traced member edge", x, 556, 13, bold=True)
    layout.rect(pdf, x, 568, layout.COL_W, 165, fill=layout.CARD, radius=5)
    columns = [x + offset for offset in (14, 120, 217, 311, 405)]
    headings = ("Sample", "Timber edge", "FA at A", "FB at B", "R (1:1 model)")
    for px, heading in zip(columns, headings):
        layout.txt(pdf, heading, px, 588, 9.5, bold=True)
    colors = (layout.INK, layout.HexColor(CA), layout.HexColor(CB), layout.HexColor(CR))
    for j, (frame, color) in enumerate(zip(frames, layout.COLORS)):
        y = 615 + j * 39
        layout.segment(pdf, (columns[0], y - 3), (columns[0] + 10, y - 3), color, 2)
        layout.txt(pdf, frame.time_label, columns[0] + 15, y, 9.6, bold=True)
        edge = frame.traced("member")
        timber = frame.traced("tool")
        contacts = frame.traced("read_contacts")
        pair = board.get_pair(frame)
        vectors = (revision.vector(timber) if timber else None,
                   contacts[0].direction if contacts else None,
                   contacts[1].direction if len(contacts) == 2 else None,
                   pair.resultant if pair else None)
        for k, (px, vector, ink) in enumerate(zip(columns[1:], vectors, colors)):
            value = board.angle_label(vector, edge) if edge and vector is not None else "—"
            if k == 3 and pair and pair.cancels_at_resolution:
                value = "R ≈ 0"
            layout.txt(pdf, value, px, y, 9.6, layout.MUTED if value == "—" else ink, k == 3)
        layout.segment(pdf, (x + 12, y + 12), (x + layout.COL_W - 12, y + 12))
    layout.text_block(
        pdf, "R combines the two selected image-plane directions at equal projected magnitude.",
        x, 751, layout.COL_W, 9, 2,
    )


def force_panel(pdf, frames, images, contact_caption=None, *, detail_index=1, single_force_caption=None,
                panel_heading=None, model_note=None, single_symbol="F"):
    frame = frames[detail_index]
    contacts = frame.traced("read_contacts")
    directed = [(contact, contact.label or "AB"[i])
                for i, contact in enumerate(contacts) if contact.direction is not None]
    single = len(directed) == 1
    x, y = layout.RIGHT, 333
    width = (layout.COL_W - 10) / 2
    height = width * .63
    pixels = (720, 454)
    if single:
        contact, label = directed[0]
        heading = panel_heading or "Single working contact"
        diagram = board.single_force_diagram(contact.direction, *pixels, label, single_symbol)
        contact_caption = contact_caption or f"{label} marks the tool tip at the panel surface."
        diagram_caption = single_force_caption or f"{single_symbol}{label} follows the projected tool axis."
    else:
        pair = board.get_pair(frame)
        assert pair
        heading = panel_heading or "Equal-force model at two contacts"
        diagram = (board.cancelling_pair(pair, *pixels) if pair.cancels_at_resolution
                   else board.force_construction(pair, *pixels))
        contact_caption = contact_caption or "A and B mark the two visible interfaces."
        diagram_caption = ("Opposing vectors cancel at equal projected magnitude." if pair.cancels_at_resolution
                           else "FA + FB = R, drawn head to tail.")
    overlay = board.plot_on_photo(frame, images[detail_index], pixels, not single, show_tool_axis=not single)
    layout.txt(pdf, f"{frame.role.capitalize()} frame   ·   {heading}", x, 322, 12, bold=True)
    board.photo(pdf, overlay, x, y, width, height)
    layout.picture(pdf, diagram, x + width + 10, y, width, height)
    caption_y = y + height + 14
    layout.text_block(pdf, contact_caption, x, caption_y, width, 8.7, 2)
    layout.text_block(pdf, diagram_caption, x + width + 10, caption_y, width, 8.7, 2)
    if not single:
        if model_note is None:
            model_note = frame.traced("force_basis")
            if not board.get_pair(frames[2]):
                model_note += " The end view hides the loaded faces."
        captions_wrap = any(len(layout.wrap(caption, width, 8.7)) > 1
                            for caption in (contact_caption, diagram_caption))
        layout.text_block(pdf, model_note, x, 536 if captions_wrap else 526, layout.COL_W, 8.5, 2)


def page(pdf, event, annotation, frames, original_page, order):
    x = layout.MARGIN
    layout.txt(pdf, f"MULTICAM  /  {event['case']} ROBOT AND GRIP", x, 32, 11, layout.MUTED, True)
    layout.text_block(pdf, f"{original_page:02d} {event['label']}", x, 68, layout.PAGE_W - 2 * x, 25, 1, layout.INK, True)
    layout.txt(pdf, f"{event['start']:.2f}–{event['end']:.2f} s", x, 94, 12, layout.MUTED)
    video = Path(event["video"]).name
    layout.aligned(pdf, f"{event['id']}   ·   {video}   ·   {event['fps']:.4g} fps",
                   layout.PAGE_W - x, 94, 10, layout.MUTED, 1)
    layout.segment(pdf, (x, 112), (layout.PAGE_W - x, 112))
    layout.txt(pdf, "01   Mechanical arm mask and extent", x, 140, 16, bold=True)
    layout.txt(pdf, "02   Grasp locations, angles and resultant", layout.RIGHT, 140, 16, bold=True)
    layout.segment(pdf, (layout.RIGHT - layout.GAP / 2, 128), (layout.RIGHT - layout.GAP / 2, 776))
    images = []
    for frame in frames:
        with Image.open(frame.photo) as img:
            images.append(img.convert("RGB"))
    board.grid(pdf, frames, images)
    board.extent(pdf, frames, annotation)
    force_panel(pdf, frames, images)
    angle_table(pdf, frames)
    layout.segment(pdf, (x, 778), (layout.PAGE_W - x, 778))
    nums = " / ".join(f"{f.number:06d}" for f in frames)
    layout.txt(pdf, f"Source  {video}, frames {nums}, {frames[0].size[0]} × {frames[0].size[1]} px.",
               x, 798, 9, layout.MUTED)
    layout.txt(pdf, "Brown timber edge = 0°. Smaller image-plane angles rounded to 5°. Contact force magnitudes are unmeasured.",
               x, 814, 8.8, layout.MUTED)
    layout.aligned(pdf, f"{order} / {len(SAMPLES)}", layout.PAGE_W - x, 814, 9, layout.MUTED, 1)
    pdf.showPage()


def main():
    layout.register_fonts()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "V24_V28_V04_format_samples.pdf"
    pending = path.with_suffix(".pending.pdf")
    pdf = canvas.Canvas(str(pending), pagesize=(layout.PAGE_W, layout.PAGE_H), pageCompression=1)
    pdf.setTitle("V24 and V28 | Confirmed V04 layout samples")
    events = {e["id"]: e for e in load_events()}
    ids = []
    for order, (case, number) in enumerate(SAMPLES, 1):
        prior_pages = json.loads((revision.AUDIT / case / "pages.json").read_text(encoding="utf-8"))
        event = events[prior_pages[number - 1]["id"]]
        ids.append(event["id"])
        records = json.loads((revision.ROOT / f"{case}.json").read_text(encoding="utf-8-sig"))
        annotation = records[event["id"]]
        descriptions = json.loads((layout.WORK / "annotations" / f"{case}.json").read_text(encoding="utf-8-sig"))
        annotation["english_description"] = (
            annotation.get("description_en") or descriptions[event["id"]].get("description_en") or event["description"]
        )
        annotation["aligned_verified"] = True
        # Keep contact IDs attached to the same gripper end as the rail turns.
        if case == "V28":
            annotation["frames"]["middle"]["contacts"].reverse()
            end = annotation["frames"]["end"]
            with Image.open(end["mask"]) as raw:
                mask = raw.convert("L")
            draw = ImageDraw.Draw(mask)
            # Clear the stationary rack slot and the upright which occludes the gripper.
            draw.rectangle((318, 52, 335, 168), fill=0)
            draw.polygon([(489, 152), (507, 146), (505, 479), (485, 479)], fill=0)
            sample_mask = layout.WORK / "revision" / "V28" / "v04-sample-p08-end.png"
            sample_mask.parent.mkdir(exist_ok=True)
            mask.save(sample_mask)
            end["mask"] = str(sample_mask)
        frames = revision.approved_frames(event, annotation)
        assert all(f.mask is not None and f.traced("point") for f in frames)
        assert len({f.number for f in frames}) == 3
        page(pdf, event, annotation, frames, number, order)
    pdf.save()
    reader = PdfReader(pending)
    assert len(reader.pages) == len(SAMPLES)
    for expected, output_page in zip(ids, reader.pages):
        body = output_page.extract_text()
        for label in (expected, "Common point", "Machine masks aligned to the member",
                      "FA + FB = R, drawn head to tail.", "R (1:1 model)"):
            assert label in body, (expected, label)
        assert "Resultant not readable" not in body
    pending.replace(path)
    print(path)


if __name__ == "__main__":
    main()
