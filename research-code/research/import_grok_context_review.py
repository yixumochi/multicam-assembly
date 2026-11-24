"""Import review choices into an analysis overlay. Do not edit source annotations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from context_common import OUT, REVIEW_SCHEMA, read_json, sha256_file, write_json


def validate(data, questions):
    if data.get("schema") != REVIEW_SCHEMA:
        raise SystemExit("Wrong review schema")
    records = data.get("records")
    if not isinstance(records, dict):
        raise SystemExit("Missing records")
    known = {item["id"]: item for item in questions}
    if not set(records) <= set(known):
        raise SystemExit("Unknown question id")
    cleaned = {}
    for key, row in records.items():
        if not isinstance(row, dict):
            raise SystemExit("Record must be an object")
        decision = row.get("decision", "")
        options = [""] + [item["id"] for item in known[key]["options"]]
        if decision not in options:
            raise SystemExit(f"Unsupported decision for {key}")
        note = row.get("note", "")
        if not isinstance(note, str):
            raise SystemExit("Note must be text")
        cleaned[key] = {"decision": decision, "note": note}
    return cleaned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("review_json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    source = Path(args.review_json)
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    questions = read_json(OUT / "review_questions.json")
    records = validate(data, questions)
    destination = Path(args.out) if args.out else OUT / "review_results.json"
    result = {
        "schema": REVIEW_SCHEMA,
        "source_file": str(source.resolve()),
        "source_sha256": sha256_file(source),
        "records": records,
        "decided": sum(bool(row["decision"]) for row in records.values()),
        "source_annotations_changed": False,
        "promoted_to_human_confirmation": False,
        "note": "Review choices are applied to the analysis layer only. Source actions, prior reviews, and original conclusions are preserved. Unselected choices remain unassessed.",
    }
    write_json(destination, result)
    if destination.resolve() == (OUT / "review_results.json").resolve():
        from apply_context_review import apply_review, refresh_reviewed_html
        outcome = apply_review(
            questions,
            read_json(OUT / "relations.json"),
            read_json(OUT / "comparison_matrix.json"),
            result,
        )
        refresh_reviewed_html(outcome)
    print(json.dumps({
        "records": len(records),
        "decided": result["decided"],
        "output": str(destination),
        "source_annotations_changed": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
