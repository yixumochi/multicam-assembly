"""Stage the reviewed V04 inputs from a local MultiCam core research ZIP."""

import argparse
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = (
    "work/annotations/V04.json", "work/revision/V04", "work/masks/V04/",
    "work/replication/V04", "work/machine_review/", "work/robot_force_review/",
    "work/full_v30/overrides/V04.json", "work/full_v30/masks/V04/",
)


def write_entry(archive, member, target_root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or any(":" in part or "\\" in part for part in path.parts):
        raise ValueError(f"Invalid archive path: {relative}")
    target = target_root.joinpath(*path.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(archive.read(member))


def rebase(value, target):
    if isinstance(value, dict):
        return {key: rebase(item, target) for key, item in value.items()}
    if isinstance(value, list):
        return [rebase(item, target) for item in value]
    if isinstance(value, str):
        source = PureWindowsPath(value)
        if source.is_absolute() and "work" in source.parts:
            suffix = source.parts[source.parts.index("work"):]
            return str(target.joinpath(*suffix))
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError("Choose a new or empty staging directory")
    catalog = json.loads((ROOT / "observation/boards/catalog.json").read_text(encoding="utf-8"))
    event_ids = {row["eventId"] for row in catalog["cases"]["V04"]}
    with ZipFile(args.archive) as archive:
        entries = archive.namelist()
        events_member, = (name for name in entries if name.count("/") == 1 and name.endswith("/events.json"))
        revision_member, = (name for name in entries if name.endswith("/work/revision/V04.json"))
        evidence_prefix = events_member.rsplit("/", 1)[0] + "/"
        board_prefix = revision_member.split("/work/")[0] + "/"
        events = [event for event in json.loads(archive.read(events_member)) if event["id"] in event_ids]
        if {event["id"] for event in events} != event_ids:
            raise ValueError("The archive is missing published V04 events")
        for event in events:
            for frame in event["frames"]:
                image = frame["image"]
                write_entry(archive, evidence_prefix + image, target, image)
        for member in entries:
            suffix = member.removeprefix(board_prefix)
            if member.startswith(board_prefix) and suffix.startswith(PREFIXES) and not suffix.endswith("/"):
                write_entry(archive, member, target, suffix)
    (target / "events.json").write_text(json.dumps(events) + "\n", encoding="utf-8")
    for path in (target / "work").rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        path.write_text(json.dumps(rebase(data, target)) + "\n", encoding="utf-8")
    print(f"Staged inputs for {len(events)} V04 boards in {target}")


if __name__ == "__main__":
    main()
