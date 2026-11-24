"""Prepare contact sheets from event-selected, full-frame evidence."""

import argparse
import json

from PIL import Image, ImageDraw, ImageFont

from board_paths import EVENTS, EVIDENCE, WORK, font_path


ROLES = ("start", "middle", "end")


def load_events():
    return json.loads(EVENTS.read_text(encoding="utf-8-sig"))


def make_sheet(group, width, with_grid, reviewed_masks):
    height = width * 9 // 16
    row_height = height + 49
    sheet = Image.new("RGB", (3 * (width + 4), row_height * len(group)), "#f5f8fa")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(font_path(), 13)
    for row, (number, event) in enumerate(group):
        y = row * row_height
        title = f'{number:02d}  {event["id"]}  {event["label"]}  |  {event["region"]}'
        draw.text((5, y + 2), title, font=font, fill="#142d3a")
        frames = {f["role"]: f for f in event["frames"]}
        for col, role in enumerate(ROLES):
            meta = frames[role]
            x = col * (width + 4)
            photo = Image.open(EVIDENCE / meta["image"]).convert("RGB")
            native_w, native_h = photo.size
            if reviewed_masks:
                mask_path = WORK / "masks" / event["case"] / event["id"] / f"{role}.png"
                if mask_path.is_file():
                    mask = Image.open(mask_path).convert("L")
                    ink = Image.new("RGB", photo.size, ("#6AC2E7", "#BAF492", "#EE751C")[col])
                    photo.paste(ink, (0, 0), mask.point(lambda value: round(value * 0.55)))
            sheet.paste(photo.resize((width, height), Image.Resampling.LANCZOS), (x, y + 25))
            draw.text(
                (x + 5, y + height + 27),
                f'{role}  {meta["frame_zero_based"]}  {meta["nominal_seconds"]:.2f}s',
                font=font,
                fill="#4f6570",
            )
            if with_grid:
                # Draw sparse tick marks and coordinate labels, keeping subjects clear.
                for tick in range(1, 8):
                    i = native_w * tick // 8
                    xx = x + round(i * width / native_w)
                    draw.line((xx, y + 25, xx, y + 32), fill="white")
                    draw.text((xx + 2, y + 25), str(i), font=font, fill="white", stroke_width=1, stroke_fill="black")
                for tick in range(1, 6):
                    j = native_h * tick // 6
                    yy = y + 25 + round(j * height / native_h)
                    draw.line((x, yy, x + 4, yy), fill="white")
                    draw.text((x + 4, yy), str(j), font=font, fill="white", stroke_width=1, stroke_fill="black")
    return sheet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*")
    parser.add_argument("--width", type=int, default=416)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int)
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--masks", action="store_true")
    args = parser.parse_args()
    events = load_events()
    for case in args.cases or sorted({e["case"] for e in events}):
        directory = WORK / ("mask_review" if args.masks else "frame_review") / case
        directory.mkdir(parents=True, exist_ok=True)
        rows = list(enumerate((e for e in events if e["case"] == case), 1))
        descriptions = [
            f'{i:02d} {e["id"]} {e["label"]} | {e["description"]}'
            for i, e in rows
        ]
        (directory / "events.txt").write_text("\n".join(descriptions) + "\n", encoding="utf-8")
        selected = rows[args.first - 1:args.last]
        for start in range(0, len(selected), args.rows):
            block = selected[start:start + args.rows]
            sheet = make_sheet(block, args.width, args.grid, args.masks)
            sheet.save(directory / f"{block[0][0]:02d}-{block[-1][0]:02d}.jpg", quality=87)


if __name__ == "__main__":
    main()
