"""Render the five published V04 selections from archived source frames and annotations."""

import argparse
import hashlib
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

import render_v30_full as renderer
from board_paths import EVIDENCE, WORK


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = renderer.read_json(args.catalog)["cases"]["V04"]
    events = {event["id"]: event for event in renderer.load_events()}
    revisions = renderer.read_json(WORK / "revision/V04.json")
    descriptions = renderer.read_json(WORK / "annotations/V04.json")
    edits = renderer.read_json(WORK / "full_v30/overrides/V04.json")
    renderer.register_fonts()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = args.output.with_suffix(".pending.pdf")
    pdf = canvas.Canvas(str(pending), pagesize=(renderer.layout.PAGE_W, renderer.layout.PAGE_H))
    for order, row in enumerate(rows, 1):
        event = events[row["eventId"]]
        for frame in event["frames"]:
            with (EVIDENCE / frame["image"]).open("rb") as image:
                if hashlib.file_digest(image, "sha256").hexdigest() != frame["sha256"]:
                    raise ValueError(f"{event['id']}: {frame['role']} frame hash differs")
        annotation, frames, mode = renderer.prepare(event, revisions, descriptions, edits)
        if any(frame.mask is None for frame in frames):
            raise ValueError(f"{event['id']}: expected three archived masks")
        renderer.render_page(pdf, event, annotation, frames, int(row["id"]), order, len(rows), mode)
    pdf.save()

    pages = PdfReader(pending).pages
    if len(pages) != len(rows) or any(
        row["eventId"] not in page.extract_text() for page, row in zip(pages, rows)
    ):
        raise ValueError("Rendered page IDs do not match the catalog")
    pending.replace(args.output)
    print(f"Rendered {len(rows)} V04 boards to {args.output}")


if __name__ == "__main__":
    main()
