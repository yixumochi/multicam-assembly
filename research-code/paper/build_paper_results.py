"""Build a manuscript and traceable evidence figures from reviewed case material."""

import argparse
import hashlib
import html
import json
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from docx import Document
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont, ImageOps


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_figure(number, result, events, source_dir, output_dir, font):
    columns = result["cols"]
    tile_width, tile_height = 900, 530
    rows = (len(result["panels"]) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * tile_width, rows * tile_height), "white")
    draw = ImageDraw.Draw(canvas)
    panels = []

    for index, (order, selection, image_kind) in enumerate(result["panels"]):
        event = events[order]
        frame = event["context_frames"][0] if selection == "context" else event["evidence_frames"][selection]
        native = (source_dir / frame[image_kind]).resolve(strict=True)
        if not native.is_relative_to(source_dir):
            raise ValueError(f"Evidence image must be inside the source directory: {native.name}")
        label = chr(ord("a") + index)
        original = Path("originals") / f"figure_{number:02}_{label}{native.suffix.lower()}"
        shutil.copy2(native, output_dir / original)
        x, y = index % columns * tile_width, index // columns * tile_height
        with Image.open(native) as image:
            tile = ImageOps.contain(image.convert("RGB"), (tile_width - 24, tile_height - 70), Image.Resampling.LANCZOS)
        canvas.paste(tile, (x + (tile_width - tile.width) // 2, y + 52 + (tile_height - 70 - tile.height) // 2))
        draw.text((x + 12, y + 10), f"({label}) {event['case']}  {event['region']}  f{frame['frame']}", font=font, fill="black")
        panels.append({
            "panel": label,
            "case": event["case"],
            "region": event["region"],
            "event_id": event["event_id"],
            "frame_zero_based": frame["frame"],
            "source_pts_seconds": frame["pts"],
            "event_interval": [event["start"], event["end"]],
            "within_ls_seconds": event["start"] <= frame["pts"] < event["end"],
            "kind": image_kind,
            "source_sha256": event["source_sha256"],
            "image_sha256": sha256_file(native),
            "original_image": original.as_posix(),
            "ls_url": event.get("ls_url", ""),
        })

    relative = f"figures/figure_{number:02}.png"
    canvas.save(output_dir / relative)
    return {"number": number, "image": relative, "caption": result["caption"], "panels": panels, "size": list(canvas.size)}


def caption_detail(figure):
    captions = []
    for panel in figure["panels"]:
        text = (f"{panel['panel']}: {panel['case']} {panel['region']}, frame {panel['frame_zero_based']}, "
                f"{panel['source_pts_seconds']:.3f} s")
        if not panel["within_ls_seconds"]:
            text += " (context outside the annotated interval)"
        captions.append(text)
    return "; ".join(captions) + ". Frame numbers are zero-based. Times are source video presentation timestamps."


def pair_summary(pair, events):
    return " / ".join(f"{events[order]['case']} {events[order]['region']}" for order in pair["orders"])


def write_docx(path, content, figures, pairs, events):
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(.7)
    section.left_margin = section.right_margin = Inches(.75)
    for name, size in (("Normal", 11), ("Title", 22), ("Heading 1", 16), ("Heading 2", 13), ("Caption", 9)):
        style = doc.styles[name]
        style.font.name, style.font.size = "Times New Roman", Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
    doc.core_properties.title = content["title"]
    doc.core_properties.author = ""
    doc.add_paragraph(content["title"], "Title")
    doc.add_paragraph(content["scope"])
    doc.add_heading("1 Results")
    if content.get("intro"):
        doc.add_paragraph(content["intro"])
    for index, (result, figure) in enumerate(zip(content["results"], figures, strict=True), 1):
        doc.add_heading(f"1.{index} {result['title']}", level=2)
        for paragraph in result["paragraphs"]:
            doc.add_paragraph(paragraph)
        paragraph = doc.add_paragraph()
        paragraph.alignment = 1
        paragraph.paragraph_format.keep_with_next = True
        width, height = figure["size"]
        shape = paragraph.add_run().add_picture(str(path.parent / figure["image"]), width=Inches(min(6.9, 5.8 * width / height)))
        shape._inline.docPr.set("descr", figure["caption"])
        doc.add_paragraph(figure["caption"], "Caption")
        doc.add_paragraph(caption_detail(figure), "Caption")
    doc.add_page_break()
    doc.add_heading("2 Discussion")
    doc.add_paragraph("These observations describe questions for further review.")
    for index, item in enumerate(content["discussion"], 1):
        doc.add_heading(f"2.{index} {item['title']}", level=2)
        doc.add_paragraph(item["text"])
        doc.add_paragraph(item["evidence"])
    doc.add_heading("3 Evidence index and review scope")
    doc.add_paragraph("The evidence manifest records source events, frame indices and timestamps, and file hashes.")
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for cell, title in zip(table.rows[0].cells, ("Pair", "Case events", "Results"), strict=True):
        cell.text = title
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, pair in enumerate(pairs, 1):
        cells = table.add_row().cells
        cells[0].text = str(index)
        cells[1].text = pair_summary(pair, events)
        cells[2].text = ", ".join(result["id"] for result in content["results"] if index in result["pairs"])
    doc.save(path)


def evidence_link(panel):
    title = f"Panel {panel['panel']} source image"
    link = f'<a href="{html.escape(panel["original_image"], quote=True)}">{html.escape(title)}</a>'
    url = panel["ls_url"]
    if url and urlsplit(url).scheme in {"http", "https"}:
        link += f' · <a href="{html.escape(url, quote=True)}">Annotation</a>'
    return f'<li>{link} · {html.escape(panel["event_id"])}</li>'


def write_html(path, content, figures, pairs, events, manuscript_name):
    esc = html.escape
    chunks = [
        '<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{esc(content["title"])}</title>',
        '<style>body{font:17px/1.7 system-ui,sans-serif;color:#172738;max-width:1040px;margin:auto;padding:28px}',
        'img{max-width:100%;height:auto}figure{margin:20px 0}table{border-collapse:collapse}',
        'td,th{border:1px solid #b0bbc2;padding:6px 9px;text-align:left}a{color:#035e69}</style>',
        f'<h1>{esc(content["title"])}</h1><p>{esc(content["scope"])}</p>',
        f'<p><a href="{esc(manuscript_name, quote=True)}">Editable manuscript</a> · '
        '<a href="evidence_manifest.json">Evidence manifest</a></p>',
        f'<h2>1 Results</h2><p>{esc(content.get("intro", ""))}</p>',
    ]
    for result, figure in zip(content["results"], figures, strict=True):
        chunks.append(f'<section id="{esc(result["id"], quote=True)}"><h3>{esc(result["title"])}</h3>')
        chunks.extend(f"<p>{esc(text)}</p>" for text in result["paragraphs"])
        chunks.append(f'<figure><img src="{figure["image"]}" alt="{esc(figure["caption"], quote=True)}">'
                      f'<figcaption>{esc(figure["caption"])}</figcaption></figure><p>{esc(caption_detail(figure))}</p>')
        chunks.append("<details><summary>Source images and event references</summary><ul>")
        chunks.extend(evidence_link(panel) for panel in figure["panels"])
        chunks.append("</ul></details></section>")
    chunks.append("<h2>2 Discussion</h2>")
    for item in content["discussion"]:
        chunks.append(f'<h3>{esc(item["title"])}</h3><p>{esc(item["text"])}</p><p>{esc(item["evidence"])}</p>')
    chunks.append("<h2>3 Evidence index</h2><table><tr><th>Pair</th><th>Case events</th><th>Results</th></tr>")
    for number, pair in enumerate(pairs, 1):
        ids = [result["id"] for result in content["results"] if number in result["pairs"]]
        links = " ".join(f'<a href="#{esc(key, quote=True)}">{esc(key)}</a>' for key in ids)
        chunks.append(f"<tr><td>{number}</td><td>{esc(pair_summary(pair, events))}</td><td>{links}</td></tr>")
    chunks.append("</table></html>")
    path.write_text("\n".join(chunks), encoding="utf-8")


def build(source_dir, output_dir, content_path, font_path=None):
    source_dir = source_dir.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir == source_dir:
        raise ValueError("Use a separate output directory.")
    content = read_json(content_path)
    events = {event["order"]: event for event in read_json(source_dir / "events.json")}
    pairs = read_json(source_dir / "pairs.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("originals", "figures"):
        (output_dir / name).mkdir(exist_ok=True)
    font = ImageFont.truetype(str(font_path), 27) if font_path else ImageFont.load_default(size=27)
    figures = [make_figure(number, item, events, source_dir, output_dir, font)
               for number, item in enumerate(content["results"], 1)]
    docx_path = output_dir / "assembly_comparison.docx"
    write_docx(docx_path, content, figures, pairs, events)
    write_html(output_dir / "index.html", content, figures, pairs, events, docx_path.name)
    manifest = {
        **content,
        "figures": figures,
        "pairs": [{"number": number, "pair_id": pair["pair_id"], "event_ids": pair["event_ids"]}
                  for number, pair in enumerate(pairs, 1)],
        "source_inputs": {name: sha256_file(source_dir / name) for name in ("events.json", "pairs.json", "manifest.json")},
        "image_processing": "Layout and resize only. Originals are copied without modification.",
    }
    (output_dir / "evidence_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    text = [content["title"], content["scope"], "1 Results", content.get("intro", "")]
    for result, figure in zip(content["results"], figures, strict=True):
        text.extend((result["title"], *result["paragraphs"], figure["caption"], caption_detail(figure)))
    text.append("2 Discussion")
    for item in content["discussion"]:
        text.extend((item["title"], item["text"], item["evidence"]))
    (output_dir / "manuscript.txt").write_text("\n\n".join(text) + "\n", encoding="utf-8")
    print(f"Wrote {len(figures)} evidence figures and manuscript to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Directory containing event and evidence files.")
    parser.add_argument("--content", type=Path, required=True, help="Manuscript content JSON.")
    parser.add_argument("--output", type=Path, required=True, help="Separate destination for the generated manuscript.")
    parser.add_argument("--font", type=Path, help="Optional TrueType font file for figure captions.")
    args = parser.parse_args()
    build(args.source, args.output, args.content, args.font)


if __name__ == "__main__":
    main()
