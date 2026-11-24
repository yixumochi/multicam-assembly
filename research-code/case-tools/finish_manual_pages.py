"""Trace the mallet and held-beam examples against the original V01 frames."""

import argparse
import json
from functools import partial
from pathlib import Path

from PIL import Image, ImageDraw


ROLES = ("start", "middle", "end")

POLYGONS = {
    4269: [(334,332),(344,326),(380,327),(385,329),(389,310),(397,299),(436,311),
           (440,318),(434,340),(454,348),(474,359),(476,364),(447,443),(438,445),
           (322,410),(324,392)],
    4322: [(456,180),(476,177),(514,181),(515,159),(520,153),(555,160),(558,167),
           (554,186),(580,197),(594,207),(574,291),(565,294),(447,269),(448,259)],
    4376: [(394,282),(407,256),(420,238),(489,207),(510,202),(521,212),(534,235),
           (524,249),(510,285),(477,299),(452,307),(435,294),(410,305)],
    5648: [(510,347),(523,340),(537,336),(551,333),(564,337),(576,348),(577,366),
           (572,376),(528,386),(518,380),(513,370),(510,360)],
    5689: [(518,361),(535,347),(553,339),(568,337),(577,342),(589,356),(590,368),
           (582,384),(534,396),(526,391)],
    5730: [(515,362),(528,354),(547,345),(559,343),(573,346),(587,355),(589,369),
           (582,386),(531,400),(523,392)],
    6607: [(418,315),(436,310),(550,352),(536,374),(529,375),(526,365),(518,357),
           (511,358),(506,352),(498,355),(485,354),(467,343),(447,333),(425,326)],
    6678: [(287,249),(705,224),(708,228),(709,257),(607,264),(605,247),(570,250),
           (571,271),(536,273),(533,263),(526,257),(518,257),(514,262),(506,257),
           (499,262),(493,267),(494,275),(388,280),(389,271),(382,267),(377,261),
           (370,267),(365,264),(357,267),(349,269),(351,277),(287,278)],
    6749: [(305,248),(710,233),(714,238),(715,263),(630,267),(628,248),(592,250),
           (593,274),(572,275),(570,268),(560,267),(554,263),(547,264),(543,268),
           (535,267),(531,271),(534,277),(405,278),(402,271),(397,264),(388,262),
           (383,267),(374,268),(365,271),(363,277),(304,276)],
}


def mask(qa, masks, number, point, subject):
    masks.mkdir(parents=True, exist_ok=True)
    photo = Image.open(qa / f"frame-{number:06}.png").convert("RGB")
    silhouette = Image.new("L", photo.size)
    ImageDraw.Draw(silhouette).polygon(POLYGONS[number], fill=255)
    dest = masks / f"{subject}-{number:06}.png"
    silhouette.save(dest)
    photo.paste("#56C8E7", (0, 0, *photo.size), silhouette.point(lambda p: round(p * .49)))
    if point:
        x, y = point
        ImageDraw.Draw(photo).ellipse((x - 6, y - 6, x + 6, y + 6), fill="#996118", outline="white")
    photo.save(qa / f"mask-proof-{number:06}.jpg", quality=94)
    return str(dest)


def frame(qa, masks, number, point, shot, member, crop, contacts, basis, subject):
    return {
        "mask": mask(qa, masks, number, point, subject),
        "mask_verified": True,
        "point": point,
        "shot": shot,
        "right_member": member,
        "right_tool": None,
        "right_crop": crop,
        "contacts_verified": True,
        "contact_region": None,
        "working_direction": basis,
        "force_basis": basis if len(contacts) == 2 else None,
        "force_arrow_length": 33,
        "contacts": [
            {"label": label, "point": [x, y], "line": [x, y, x + dx, y + dy]}
            for label, (x, y), (dx, dy) in contacts
        ],
    }


def mallet(frames, obj, ref, align, caption, headings, statuses, detail, note):
    return {
        "mode": "axis",
        "right_panel_traces": True,
        "detail_index": detail,
        "object": obj,
        "aligned_verified": True,
        "point_label": ref,
        "alignment_target": align,
        "contact_title": "02   Mallet travel and angle to the timber",
        "evidence_title": headings,
        "contact_caption": caption,
        "force_heading": "Observed mallet travel at A",
        "single_symbol": "D",
        "single_force_caption": "DA follows the head's projected travel.",
        "single_angle_header": "Travel to timber edge",
        "angle_note": note,
        "contact_statuses": statuses,
        "frames": dict(zip(ROLES, frames, strict=True)),
    }


def main(qa, masks):
    missing = [number for number in POLYGONS if not (qa / f"frame-{number:06}.png").is_file()]
    if missing:
        raise FileNotFoundError(f"Missing source frames: {missing}")
    make_frame = partial(frame, qa, masks)
    hold_basis = "The two selected palm supports are modeled as upward directions at equal projected magnitude."
    p44 = mallet(
        [
            make_frame(4269,[646,214],"upper peg close-up",[615,207,613,337],[318,164,668,463],[],
                  None,"mallet"),
            make_frame(4322,[638,211],"upper peg close-up",[605,212,602,344],[423,152,654,334],[],
                  None,"mallet"),
            make_frame(4376,[639,212],"upper peg close-up",[546,215,542,330],[390,177,610,335],
                  [("A",(508,249),(17,-10))],"The leading face advances up/right in frames 4376–4378.","mallet"),
        ],
        "Wooden mallet head beside the upper peg",
        "Dark round knot on the fixed upright",
        "the fixed post knot",
        "A marks the leading face of the wooden mallet beside the peg.",
        "One wooden mallet head and the upper peg",
        ["Head away from the upper joint", "Head covers the peg in this pose", "Head advances up and right"],
        2,
        "DA uses the leading-face travel in adjacent original frames. The brown line marks the fixed upright.",
    )
    p44["note"] = "The mask follows the wooden head. A second mallet crosses the foreground."
    p51 = mallet(
        [
            make_frame(5648,[528,309],"same upper brace close-up",[562,307,626,347],[479,306,650,410],
                  [("A",(550,363),(14,-3))],"Head advances right in frames 5646–5648.","mallet"),
            make_frame(5689,[530,311],"same upper brace close-up",[565,309,630,352],[477,307,648,409],
                  [("A",(560,372),(-11,4))],"Head moves left during rebound in frames 5687–5689.","mallet"),
            make_frame(5730,[531,313],"same upper brace close-up",[562,313,630,358],[474,311,651,416],
                  [("A",(563,371),(17,-4))],"Head advances toward the peg between frames 5730 and 5731.","mallet"),
        ],
        "Visible wooden mallet head at the upper joint",
        "Inside corner beside the pale diagonal brace",
        "the fixed brace corner",
        "A marks the mallet head during the approach to the peg.",
        "Mallet approach and rebound at the projecting peg",
        ["Head approaches right/up", "Head rebounds left/down", "Head approaches right/up again"],
        2,
        "DA shows adjacent-frame head motion. The angles use the visible long edge of the pale diagonal timber.",
    )
    p51["note"] = "The same upper brace corner aligns the visible mallet heads during the swings."
    p58 = {
        "mode": "pair", "right_panel_traces": True, "detail_index": 1, "aligned_verified": True,
        "overlay_roles": ["middle", "end"],
        "object": "Exposed length of the timber carried by both palms",
        "left_title": "01   Held timber mask and extent",
        "mask_title": "Visible held timber masks",
        "subject_label": "Highlighted member",
        "overlay_title": "Held timber masks aligned to the fixed post",
        "overlay_note": "Middle and end contours aligned within the raised view. Extent in source-frame pixels.",
        "point_label": "Upper left corner of the fixed right foreground post",
        "alignment_target": "the fixed right post",
        "note": "The start shows an inclined exposed span. The overlay uses the later shared view.",
        "contact_title": "02   Palm support directions, angles and resultant",
        "evidence_title": "Visible gloves at the underside of the carried timber",
        "contact_caption": "A and B mark the visible palm supports.",
        "force_heading": "Equal-force model at two palm supports",
        "model_note": "R adds the two upward palm directions at equal projected magnitude.",
        "angle_note": "Angles use the supported timber edge. The start exposes only support B.",
        "frames": dict(zip(ROLES, [
            make_frame(6607,None,"lower view",[439,322,544,368],[319,235,645,414],
                  [("B",(515,356),(0,-29))],hold_basis,"held-timber"),
            make_frame(6678,[570,250],"raised side view",[406,275,484,271],[279,203,714,376],
                  [("A",(371,272),(0,-31)),("B",(518,266),(0,-31))],hold_basis,"held-timber"),
            make_frame(6749,[591,249],"raised side view",[427,275,516,272],[289,210,726,378],
                  [("A",(389,273),(0,-31)),("B",(552,269),(0,-31))],hold_basis,"held-timber"),
        ], strict=True)),
    }
    records = {"E-88ff84a681fe25": p44, "E-968c4b0406cc9f": p51, "E-cb42b788df2316": p58}
    (qa / "p44-p51-p58-overrides.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True)
    args = parser.parse_args()
    main(args.frames, args.masks)
