"""Build the ten source-checked event boards in review batch 05."""

import json

import render_boards as layout
from render_v04_next_samples import OUT, base_annotation, publish_samples, set_anchor


QA = layout.WORK / "pilot_qa"
MASKS = QA / "review_batch_05"
DEFAULT_SPECS = ("axis_pages.json", "grip_pages.json", "other_pages.json")
V20_PAGE = ("V20", 4, "motion")


def prepare_v20(annotation):
    set_anchor(annotation, "Lower-right corner of the upright white panel", "the fixed white panel",
               [(331, 179), (331, 180), (330, 180)])
    annotation["object"] = "Visible mallet head"
    annotation["english_description"] = "The builder raises the mallet and brings its head down toward the receiver."
    annotation["note"] = "The mask tracks the mallet head. Blur hides the exact impact interface in the sampled frames."
    annotation["motion_points"] = [(285, 128), (290, 61), (296, 114)]
    annotation["motion_subject"] = "Head center"
    annotation["motion_crop"] = [248, 37, 343, 159]
    annotation["contact_statuses"] = (
        "Head near the receiver seam",
        "Head raised above the seam",
        "Head returns toward the seam",
    )
    for role in layout.ROLES:
        frame = annotation["frames"][role]
        frame.update(mask=str(QA / "review_batch_04" / f"V20-p04-{role}-mask.png"),
                     mask_verified=True, contacts=[], contacts_verified=False,
                     force_crop=annotation["motion_crop"])


def load_specs(names):
    specs = {}
    for name in names:
        pages = json.loads((MASKS / name).read_text(encoding="utf-8-sig"))
        for page in pages:
            key = page["case"], int(page["page"])
            if key in specs:
                raise ValueError(f"Duplicate page {key}")
            specs[key] = page
    return specs


def update_annotation(annotation, updates):
    annotation.update({key: value for key, value in updates.items() if key != "frames"})
    for role, frame in updates.get("frames", {}).items():
        annotation["frames"][role].update(frame)


def render(specs, target, marked_edits=None, modes=None):
    marked_edits = marked_edits or {}
    modes = modes or {}

    def prepare(case, number, event_id, event):
        annotation = base_annotation(case, event_id, event)
        key = case, number
        if key == V20_PAGE[:2]:
            prepare_v20(annotation)
        else:
            update_annotation(annotation, specs[key]["annotation"])
        if key in marked_edits:
            update_annotation(annotation, marked_edits[key])
        return annotation

    entries = [(*key, spec["mode"]) for key, spec in specs.items()]
    samples = sorted((case, number, modes.get((case, number), "marked" if (case, number) in marked_edits else mode))
                     for case, number, mode in (V20_PAGE, *entries))
    publish_samples(samples, target, "V04 format | Review batch 05", prepare)


if __name__ == "__main__":
    specs = load_specs(DEFAULT_SPECS)
    if len(specs) + 1 != 10:
        raise ValueError(f"Expected 10 unique pages, found {len(specs) + 1}")
    render(specs, OUT / "V04_format_review_batch_05.pdf")
