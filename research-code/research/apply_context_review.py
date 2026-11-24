"""Apply saved review choices onto relations and comparisons.

Choices stay in the analysis layer. Source annotations are not edited.
A blank choice does not become a negative finding.
"""
from __future__ import annotations

import copy
import html
import json
from pathlib import Path

from context_common import OUT, REVIEW_SCHEMA, read_json, write_json


def load_review(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def apply_review(questions, relations, comparisons, review):
    relations = copy.deepcopy(relations)
    comparisons = copy.deepcopy(comparisons)
    changes = []
    records = {} if review is None else review.get("records") or {}
    by_relation = {item["relation_id"]: item for item in relations["relations"]}
    by_comparison = {item["comparison_id"]: item for item in comparisons["comparisons"]}
    for question in questions:
        chosen = (records.get(question["id"]) or {}).get("decision") or ""
        note = (records.get(question["id"]) or {}).get("note") or ""
        if not chosen:
            continue
        for effect in question.get("effects", {}).get(chosen, []):
            target = by_relation.get(effect["target_id"]) if effect["target_type"] == "relation" else by_comparison.get(effect["target_id"])
            if target is None:
                raise RuntimeError(f"Review target missing: {effect['target_id']}")
            for key, value in effect.get("set", {}).items():
                if key == "note_suffix":
                    target["note"] = target.get("note", "") + value
                    target["review_note"] = note
                else:
                    target[key] = value
            target["review_status"] = "human_choice_applied"
            target["review_decision"] = chosen
            changes.append({
                "question_id": question["id"],
                "decision": chosen,
                "target_type": effect["target_type"],
                "target_id": effect["target_id"],
                "summary": effect["summary"],
                "blocks_current_conclusion": question.get("blocks_current_conclusion", False),
            })
    return {
        "schema": "multicam-grok-context-reviewed-v1",
        "source_annotations_changed": False,
        "review_file_present": review is not None,
        "decisions_applied": len(changes),
        "changes": changes,
        "relations": relations,
        "comparisons": comparisons,
    }


def write_reviewed(outcome):
    public = {key: value for key, value in outcome.items() if key not in {"relations", "comparisons"}}
    write_json(OUT / "reviewed_outcomes.json", public)
    write_json(OUT / "reviewed_relations.json", outcome["relations"])
    write_json(OUT / "reviewed_comparison_matrix.json", outcome["comparisons"])
    return public


def reviewed_html(outcome):
    rows = []
    for row in outcome["comparisons"]["comparisons"]:
        kind = "Single observation" if len(row["sides"]) < 2 else row["question"]
        mark = row.get("review_decision") or ""
        rows.append(
            "<tr><td>{cid}</td><td>{kind}</td><td>{difference}</td><td>{unknowns}</td><td>{mark}</td></tr>".format(
                cid=html.escape(row["comparison_id"]), kind=html.escape(kind),
                difference=html.escape(row["difference"]),
                unknowns=html.escape("; ".join(row.get("unknowns") or [])),
                mark=html.escape(mark or "Not reviewed"),
            )
        )
    table = ("<table><tr><th>Comparison</th><th>Type</th><th>Difference</th><th>Unknowns</th><th>Review</th></tr>"
             + "".join(rows) + "</table>")
    if not outcome["review_file_present"]:
        body = "<p>No review has been imported. The table shows candidate results. Blank choices are unassessed. Import review_results.json to apply each chosen answer to its comparison or relation.</p>"
    elif not outcome["changes"]:
        body = "<p>The review file has no selected answers. The table still shows the original candidates.</p>"
    else:
        items = "".join(
            "<li>{qid} selected {decision} and updated {target_type} <code>{target}</code>. {summary}</li>".format(
                qid=item["question_id"], decision=item["decision"], target_type=item["target_type"],
                target=item["target_id"], summary=item["summary"],
            )
            for item in outcome["changes"]
        )
        body = f"<p>The table reflects review_results.json. Source annotations are unchanged.</p><ul>{items}</ul>"
    return f"<!-- reviewed-layer -->{body}{table}<!-- /reviewed-layer -->"


def refresh_reviewed_html(outcome):
    path = OUT / "index.html"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    start = text.find("<!-- reviewed-layer -->")
    end = text.find("<!-- /reviewed-layer -->")
    if start < 0 or end < 0:
        return
    end += len("<!-- /reviewed-layer -->")
    path.write_text(text[:start] + reviewed_html(outcome) + text[end:], encoding="utf-8")
    write_reviewed(outcome)
