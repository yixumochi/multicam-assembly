"""Publish source-checked annotations as a new edition of the case PDFs."""

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from math import atan2, cos, degrees, pi, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat
from pypdf import PdfReader
from reportlab.pdfgen import canvas

import render_boards as b
import replicate_force_boards as prior
from machine_board import tint
from review_frames import load_events
from robot_force_board import CA, CB, arrow


ROOT = b.WORK / "revision"
OUT = b.OUTPUTS / "revised"
AUDIT = b.WORK / "pdf_review_20261121"
AXIS = "#294C73"
REGION = "#914AAC"
ROLE_NAMES = {"start": "Start", "middle": "Middle", "end": "End"}


def vector(line):
    return complex(*line[2:]) - complex(*line[:2])


def geometry(f):
    if f.traced("geometry_kind") and f.traced("member") and f.traced("tool"):
        return f.traced("member"), f.traced("tool")
    return None


@lru_cache(maxsize=1800)
def verify_original(photo, digest):
    with photo.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError(f"Source image hash mismatch: {photo}")


def approved_frames(event, annotation):
    for state in annotation["frames"].values():
        if not state.get("mask_verified"):
            if state.pop("mask", None):
                state["mask_unreadable"] = "The visible equipment boundary could not be isolated confidently."
            state.setdefault("mask_unreadable", "The equipment boundary is unresolved in this view.")
        if not state.get("contacts_verified"):
            state["contacts"] = []
            state.pop("contact_region", None)
        if not state.get("geometry_kind"):
            state.pop("tool", None)
            state.pop("member", None)
        if not annotation.get("aligned_verified"):
            state.pop("point", None)
        state.pop("angles_pending", None)
        state["contact"] = "Confirmed" if state.get("contacts") else "Unconfirmed"
        state.setdefault("member_edge", "Reference timber edge")
        state.setdefault("tool_edge", "Observed line")

    frames = b.load_frames(event, annotation, False)
    sources = {src["role"]:src for src in event["frames"] if src["role"] in b.ROLES}
    for f in frames:
        src = sources[f.role]
        verify_original(f.photo, src["sha256"])
        frame_state = f.annotation
        for key in ("roi", "contact_region"):
            if frame_state.get(key):
                q = frame_state[key]
                if len(q) != 4 or not (0 <= q[0] < q[2] <= f.size[0] and 0 <= q[1] < q[3] <= f.size[1]):
                    raise ValueError(f"Invalid {key} at {event['id']} / {f.role}: {q}")
        model_basis = frame_state.get("force_basis") or annotation.get("force_basis")
        direction_basis = model_basis or frame_state.get("working_direction")
        contacts = []
        for raw in frame_state.get("contacts") or []:
            item = dict(raw)
            if not direction_basis:
                item.pop("line", None)
            contacts.append(prior.read_contact(item, f.size))
        if len(contacts) > 2:
            raise ValueError(f"Expected at most two contact labels at {event['id']}")
        if len(contacts) == 2 and abs(contacts[0].position - contacts[1].position) <= 1:
            raise ValueError(f"Repeated contact locations at {event['id']} / {f.role}")
        frame_state["read_contacts"] = tuple(contacts)
        if model_basis:
            frame_state["force_basis"] = model_basis
    return frames


def focus_crop(f, ratio, tight=False, for_geometry=False):
    coords = []
    if for_geometry and geometry(f):
        for line in geometry(f):
            coords += [complex(*line[:2]), complex(*line[2:])]
    else:
        for contact in f.traced("read_contacts"):
            coords.append(contact.position)
            if contact.direction is not None:
                coords.append(contact.position + 23 * contact.direction)
        region = f.traced("contact_region")
        if region:
            coords += [complex(*region[:2]), complex(*region[2:])]
    if coords:
        xs, ys = [p.real for p in coords], [p.imag for p in coords]
        mx, my = (24, 20) if for_geometry else (58, 40)
        rect = min(xs)-mx, min(ys)-my, max(xs)+mx, max(ys)+my
    else:
        rect = f.traced("roi") or (f.mask.getbbox() if f.mask else None)
    padding = 1.04 if tight else 1.19
    if for_geometry and f.traced("geometry_view") in ("Camera R","Right camera"):
        left = f.size[0] / 2
        l,t,r,bot = rect
        a,c,d,e = prior.fit_crop((f.size[0]-left,f.size[1]),(l-left,t,r-left,bot),ratio,padding)
        return a+left,c,d+left,e
    return prior.fit_crop(f.size, rect, ratio, padding)


def angle_key(draw, coords, size):
    """Sketch the smaller included angle on a separate key, using the traced endpoints."""
    u, v = (vector(line) for line in coords)
    theta = atan2(u.imag, u.real)
    dtheta = (atan2(v.imag, v.real) - theta + pi / 2) % pi - pi / 2
    x, y = size[0] - 53, 53
    draw.rounded_rectangle((x-46, y-46, x+46, y+46), radius=7, fill="#FBFCFD", outline="#D0DDE2")
    for a, color in ((theta, "#996118"), (theta + dtheta, AXIS)):
        draw.line((x, y, x+37*cos(a), y+37*sin(a)), fill=color, width=4)
    count = max(3, int(abs(degrees(dtheta))))
    if abs(dtheta) > .01:
        pts = [(x + 23*cos(theta+dtheta*i/count), y + 23*sin(theta+dtheta*i/count)) for i in range(count+1)]
        draw.line(pts, fill="#35444A", width=2)


def detail(f, image, size, *, model=False, for_geometry=False):
    box = focus_crop(f, size[0]/size[1], for_geometry=for_geometry)
    pic = prior.crop(image, box, size)
    draw = ImageDraw.Draw(pic)
    scale = size[0] / (box[2] - box[0])
    offset = complex(*box[:2])

    def xy(p):
        z = (p - offset) * scale
        return z.real, z.imag

    if for_geometry and geometry(f):
        for line, color in zip(geometry(f), ("#996118", AXIS)):
            line_xy = (xy(complex(*line[:2])), xy(complex(*line[2:])))
            draw.line(line_xy, fill="white", width=6)
            draw.line(line_xy, fill=color, width=4)
        angle_key(draw, geometry(f), size)
        return pic

    region = f.traced("contact_region")
    if region:
        rect = (*xy(complex(*region[:2])), *xy(complex(*region[2:])))
        draw.rectangle(rect, outline="white", width=6)
        draw.rectangle(rect, outline=REGION, width=3)
    for i, contact in enumerate(f.traced("read_contacts")):
        px, py = xy(contact.position)
        color = (CA, CB)[i]
        if model and contact.direction is not None:
            tip = xy(contact.position + contact.direction * 23)
            arrow(draw, complex(px, py), complex(*tip), color, 4, True)
        draw.ellipse((px-5, py-5, px+5, py+5), fill="white", outline=color, width=3)
        dx = -20 if i == 0 else 20
        lx = min(size[0]-16, max(16, px + dx))
        ly = min(size[1]-16, max(16, py-15))
        draw.line(((px, py), (lx, ly)), fill="white", width=3)
        prior.tag(draw, (lx, ly), "AB"[i], color, 17)
    return pic


def unique_sample_indices(frames):
    if len({f.number for f in frames}) == 1:
        return [1]
    keep = []
    for i, f in enumerate(frames):
        if not any(frames[j].number == f.number for j in keep):
            keep.append(i)
    return keep


def sample_label(frames, index):
    f = frames[index]
    roles = " / ".join(ROLE_NAMES[a.role] for a in frames if a.number == f.number)
    if roles == "Start / Middle / End":
        roles = "Single source frame"
    return f"{roles}  {f.time_label}"


def shot_label(frame):
    view = frame.traced("shot")
    if isinstance(view,int):
        return f"Shot {view}"
    return view or ""


def mask_message(f, a):
    status = f.traced("mask_status")
    kind = a.get("analysis_kind") or a.get("interaction_kind")
    if status == "not_applicable" or kind in ("context", "manual", "support", "joint"):
        return "No equipment mask for this action."
    if status == "occluded":
        return "Equipment boundary occluded."
    return f.traced("mask_unreadable") or "Equipment boundary unresolved."


def left_panel(c, fs, images, indices, annotation):
    x = b.MARGIN
    gap = 10
    w = prior.TILE_W if len(indices) == 3 else min(255, (b.COL_W-gap)/2)
    h = w * 9 / 16
    if len(indices) == 1:
        w, h = 253, 142
    b.txt(c, "Selected source frames" if len(indices)>1 else "Selected source frame", x, 169, 12, bold=True)
    mask_top = 181+h+43
    any_mask = any(fs[i].mask for i in indices)
    b.txt(c, "Equipment mask detail" if any_mask else "Equipment visibility", x, mask_top-10, 12, bold=True)
    for slot, i in enumerate(indices):
        f, im = fs[i], images[i]
        col = b.COLORS[i]
        lx = x + slot * (w+gap)
        b.picture(c, f.photo, lx, 181, w, h)
        b.segment(c, (lx, 192+h), (lx+11, 192+h), col, 2)
        caption = "  ·  ".join(filter(None,(sample_label(fs,i),shot_label(f))))
        b.text_block(c,caption,lx+16,196+h,w-16,8.5,1)
        if f.mask is not None:
            # Crop the already-composited source and its mask together.
            roi = prior.fit_crop(f.size,f.mask.getbbox(),16/9,padding=1.36)
            masked = prior.crop(tint(im,f.mask,col),roi,(640,360))
            prior.photo(c,masked,lx,mask_top,w,h)
        elif any_mask:
            b.text_block(c, mask_message(f, annotation), lx, mask_top+20, w-4, 9, 3)
    if not any_mask:
        reasons = list(dict.fromkeys(mask_message(fs[i], annotation) for i in indices))
        for j, reason in enumerate(reasons):
            b.text_block(c, reason, x, mask_top+14+j*26, b.COL_W, 10, 2)
    y = mask_top+(h if any_mask else 75)+24
    b.text_block(c, annotation["object"], x, y, b.COL_W, 12, 2, b.INK, True)
    desc = annotation["english_description"]
    b.text_block(c, desc, x, y+33, b.COL_W, 10, 4)
    note = annotation.get("review_note")
    if note:
        b.text_block(c, note, x, y+85, b.COL_W, 9.5, 3)

    if annotation.get("aligned_verified") and len(indices) == 3 and all(f.mask and f.traced("point") for f in fs):
        overlay, ref, bounds = b.registered_overlay(fs)
        if bounds:
            l,t,r,bot = bounds
            box = min(l, ref[0])-6, min(t, ref[1])-6, max(r, ref[0])+7, max(bot, ref[1])+7
            patch = overlay.crop(box)
            scale = min(235/patch.width, 116/patch.height)
            b.txt(c,"Extent aligned to a shared landmark",x,y+101,11,b.INK,True)
            b.picture(c,patch,x+10,y+113,patch.width*scale,patch.height*scale)
            b.circle(c, (x+10+(ref[0]-box[0])*scale,y+113+(ref[1]-box[1])*scale), 2.5, b.REF)
            b.txt(c,f"W {r-l} px    H {bot-t} px",x+251,y+156,11,b.INK,True)
            b.text_block(c,annotation.get("point_label","Reference landmark"),x+251,y+177,b.COL_W-254,9,2)
    elif any_mask:
        b.txt(c,"Visible equipment extent",x,y+105,11,b.INK,True)
        for j, i in enumerate(i for i in indices if fs[i].mask):
            if fs[i].mask:
                l,t,r,bot = fs[i].mask.getbbox()
                b.txt(c,f"{ROLE_NAMES[fs[i].role]}    W {r-l} px    H {bot-t} px",x+4,y+126+j*18,9.5)
        b.text_block(c,"Per-frame image footprints at source scale.",x,y+184,b.COL_W,9,1)


def choose_frame(fs, images, indices, a):
    preferred = a.get("preferred_frame")
    if preferred:
        for i in indices:
            if fs[i].role == preferred or (len(indices)==1 and preferred in b.ROLES):
                return i

    def score(i):
        f = fs[i]
        pic = images[i].crop(focus_crop(f, 1.6)).convert("L")
        contrast = ImageStat.Stat(pic).stddev[0]
        return (
            bool(prior.get_pair(f)),
            len(f.traced("read_contacts")),
            bool(f.traced("contact_region")),
            f.traced("quality") or 0,
            bool(geometry(f)),
            bool(f.mask),
            contrast,
        )

    return max(indices, key=score)


def right_panel(c, fs, images, indices, annotation):
    x = b.RIGHT
    w = prior.TILE_W if len(indices) == 3 else min(255, (b.COL_W-10)/2)
    h = w * 9/16
    b.txt(c,"Contact evidence",x,169,12,b.INK,True)
    for slot,i in enumerate(indices):
        rx = x + slot*(w+10)
        prior.photo(c,detail(fs[i],images[i],(640,360)),rx,181,w,h)
        caption = "  ·  ".join(filter(None,(sample_label(fs,i),shot_label(fs[i]))))
        b.text_block(c,caption,rx,196+h,w,8.5,1)

    index = choose_frame(fs, images, indices, annotation)
    f = fs[index]
    pair = prior.get_pair(f)
    contacts = f.traced("read_contacts")
    y = 181 + h + 40
    local_width = (b.COL_W-10)/2
    if not pair:
        title = "Two visible contacts" if len(contacts)==2 else "Visible contact" if contacts else "Contact region" if f.traced("contact_region") else "Action detail"
    else:
        title = "Two contacts and their projected sum"
    b.txt(c,title,x,y-9,12,b.INK,True)
    if pair:
        prior.photo(c,detail(f,images[index],(720,454),model=True),x,y,local_width,164)
        img = prior.cancelling_pair(pair,720,454) if pair.cancels_at_resolution else prior.force_construction(pair,720,454)
        b.picture(c,img,x+local_width+10,y,local_width,164)
        b.txt(c,"A and B are the selected interfaces.",x,y+178,9)
        b.txt(c,"Equal projected magnitudes (1:1).",x+local_width+10,y+178,9)
    else:
        prior.photo(c,detail(f,images[index],(960,296),model=bool(f.traced("working_direction"))),x,y,b.COL_W,164)
    source = "  /  ".join(filter(None,(f"Frame {f.number:06d}",f.time_label,shot_label(f))))
    b.txt(c,source,x,y+(193 if pair else 178),9,b.MUTED)
    note = f.traced("force_basis") if pair else f.traced("working_direction") or f.traced("contact_note")
    if pair:
        if pair.cancels_at_resolution:
            note += " The projected sum is near zero. Rotational effects require a separate moment check."
        else:
            note += " R is the sum of the two shown projections."
    if not note:
        kind = annotation.get("analysis_kind") or annotation.get("interaction_kind")
        context = kind in ("context","auxiliary")
        note = ("One visible interface." if len(contacts)==1 else
                "Contact locations are visible. The force directions remain unresolved." if contacts else
                "Approximate contact area outlined." if f.traced("contact_region") else
                "The frame records the operation and its context." if context else
                "The sampled view does not establish a contact location.")
    b.text_block(c,note,x,y+(210 if pair else 195),b.COL_W,9.5,3)

    measured = [i for i in indices if geometry(fs[i])]
    if measured:
        gy = y+254
        j = index if index in measured else measured[0]
        gf = fs[j]
        view = gf.traced("geometry_view") or "Source view"
        b.txt(c,f"Projected geometry  /  {view}",x,gy-10,11,b.INK,True)
        prior.photo(c,detail(gf,images[j],(720,301),for_geometry=True),x,gy,local_width,109)
        mx = x+local_width+12
        b.txt(c,"Timber edges" if gf.traced("geometry_kind")=="member" else "Tool axis to timber edge",mx,gy+12,10,b.INK,True)
        b.txt(c,f"Image shown: {gf.time_label}",mx,gy+28,8.6,b.MUTED)
        for row,i in enumerate(measured):
            ref, line = geometry(fs[i])
            b.txt(c,f"{fs[i].time_label}     {prior.angle_label(vector(line),ref)}",mx,gy+49+16*row,10)
        b.txt(c,"Brown: reference edge   Blue: measured line",x,gy+123,8.6,b.MUTED)
        result_rows = []
        for i in measured:
            pf = fs[i]
            pair_i = prior.get_pair(pf)
            if not pair_i:
                continue
            ref, _ = geometry(pf)
            result_value = "near zero" if pair_i.cancels_at_resolution else prior.angle_label(pair_i.resultant,ref)
            result_rows.append(f"{pf.time_label}: A {prior.angle_label(pair_i.ua,ref)}, B {prior.angle_label(pair_i.ub,ref)}, R {result_value}")
        if result_rows:
            b.text_block(c,"Projected forces to reference edge  /  "+"  ·  ".join(result_rows),x,gy+139,b.COL_W,8.6,2)


def make_page(c, event, a, fs, number, total):
    images = []
    for f in fs:
        with Image.open(f.photo) as img:
            images.append(img.convert("RGB"))
    indices = unique_sample_indices(fs)
    source = Path(event["video"]).name
    x = b.MARGIN
    b.txt(c,f"MULTICAM  /  {event['case']}  /  REVISED",x,32,11,b.MUTED,True)
    b.text_block(c,f"{number:02d}   {event['label']}",x,68,b.PAGE_W-2*x,24,1,b.INK,True)
    b.txt(c,f"{event['start']:.2f}–{event['end']:.2f} s",x,95,12,b.MUTED)
    b.aligned(c,f"{event['id']}   ·   {source}",b.PAGE_W-x,95,10,b.MUTED,1)
    b.segment(c,(x,112),(b.PAGE_W-x,112))
    b.segment(c,(b.RIGHT-b.GAP/2,128),(b.RIGHT-b.GAP/2,774))
    b.txt(c,"01   Equipment mask and extent",x,140,16,b.INK,True)
    b.txt(c,"02   Contacts, angles and force model",b.RIGHT,140,16,b.INK,True)
    left_panel(c,fs,images,indices,a)
    right_panel(c,fs,images,indices,a)
    b.segment(c,(x,778),(b.PAGE_W-x,778))
    w,h = fs[0].size
    frames = " / ".join(f"{f.number:06d}" for f in fs)
    b.txt(c,f"Source  {source}  /  start, middle, end: {frames}  /  {w} × {h} px",x,799,9,b.MUTED)
    b.txt(c,"Image-plane angles are rounded to 5°. Force models show only the annotated interfaces.",x,815,8.8,b.MUTED)
    b.aligned(c,f"{number} / {total}",b.PAGE_W-x,815,9,b.MUTED,1)
    c.showPage()
    return {
        "case": event["case"],
        "page": number,
        "event_id": event["id"],
        "label": event["label"],
        "frames": [f.number for f in fs],
        "masks": sum(f.mask is not None for f in fs),
        "points": sum(len(f.traced("read_contacts")) for f in fs),
        "regions": sum(bool(f.traced("contact_region")) for f in fs),
        "angles": sum(bool(geometry(f)) for f in fs),
        "pair": any(prior.get_pair(f) for f in fs),
    }


def render(case):
    annotations = json.loads((ROOT / f"{case}.json").read_text(encoding="utf-8-sig"))
    earlier = json.loads((b.WORK / "annotations" / f"{case}.json").read_text(encoding="utf-8-sig"))
    order = json.loads((AUDIT / case / "pages.json").read_text(encoding="utf-8"))
    events = {e["id"]: e for e in load_events() if e["case"] == case}
    assert set(events) == set(annotations) == {r["id"] for r in order}, case
    assert len(order) == b.CASE_COUNTS[case]
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{case}_robot_mask_grip_resultant_revised.pdf"
    pending = target.with_suffix(".pending.pdf")
    doc = canvas.Canvas(str(pending), pagesize=(b.PAGE_W,b.PAGE_H), pageCompression=1)
    doc.setTitle(f"{case} | Revised equipment masks and contact evidence")
    result = []
    for rev in order:
        eid = rev["id"]
        e, a = events[eid], annotations[eid]
        a["english_description"] = a.get("description_en") or earlier[eid].get("description_en") or e["description"]
        fs = approved_frames(e,a)
        result.append(make_page(doc,e,a,fs,rev["page"],len(order)))
    doc.save()
    pdf = PdfReader(pending)
    assert len(pdf.pages) == len(order)
    for p,row in zip(pdf.pages,result):
        body = p.extract_text()
        assert row["event_id"] in body and all(f"{num:06d}" in body for num in row["frames"])
        assert "Resultant not readable" not in body
    pending.replace(target)
    (ROOT / f"{case}_verified_pages.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    totals = Counter()
    for r in result:
        totals.update({k: r[k] for k in ("masks","points","regions","angles","pair")})
    print(case, len(result), dict(totals), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="+", choices=sorted(b.CASE_COUNTS))
    args = parser.parse_args()
    b.register_fonts()
    for case in args.cases:
        render(case)
