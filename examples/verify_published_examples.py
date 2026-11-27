"""Recalculate an action turn gap and V22 drawing lift from released inputs."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def action_example():
    names = {"Hold timber at joint", "Position timber at joint"}
    rows = read("action-pair-summary/data.json")["rows"]
    pair = next(row for row in rows if set(row["names"]) == names)
    first, second = [stage["net"] for stage in pair["stages"]]
    gap = round(abs(abs(first) - abs(second)), 1)
    if gap != 24.6:
        raise ValueError(f"Unexpected turn gap for {pair['id']}: {gap}")
    return {"names": pair["names"], "signed_turns_deg": [first, second],
            "turn_gap_deg": gap, "published_cosine": pair["score"]}


def spatial_example():
    data = read("video-to-top-view/point_lineage.json")
    focal, depth = data["drawing_fixed_focal"], data["drawing_fixed_depth"]
    records = data["records"]
    errors = []
    unsupported = []
    for record in records:
        u, v = record["uv"]
        xyz = ((u - 480) * depth / focal, (v - 270) * depth / focal, depth)
        errors.extend(abs(a - b) for a, b in zip(xyz, record["drawing_lift_xyz"], strict=True))
        if not record["supported"]:
            unsupported.append(record["frame"])
    error = max(errors)
    if error > 1e-9 or unsupported != [2112]:
        raise ValueError(f"Unexpected V22 replay result: error={error}, unsupported={unsupported}")
    return {"case": data["case"], "shot": data["shot"], "feature": data["feature_id"],
            "records": len(records), "unsupported_camera_frames": unsupported, "max_lift_error": error}


if __name__ == "__main__":
    print(json.dumps({"action_pair": action_example(), "v22_drawing_lift": spatial_example()}, indent=2))
