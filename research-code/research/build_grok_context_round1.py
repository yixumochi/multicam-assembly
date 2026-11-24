"""Build the context, episode, comparison, and review deliverables for this round."""
from __future__ import annotations

import html
import json
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from context_common import (  # noqa: E402
    BASELINE, DIAGRAMS, FRAMES, OUT, PACKAGE, PROJECT, RESEARCH, REVIEW_SCHEMA, SCHEMA,
    VIDEOS, load_inputs, sha256_file, sha256_text, write_json,
)
from apply_context_review import apply_review, load_review, reviewed_html, write_reviewed  # noqa: E402
from compare_operation_contexts import build_comparisons  # noqa: E402
from episode_relations import build_episode_relations  # noqa: E402
from import_grok_context_review import validate as validate_review  # noqa: E402
from operation_context import build_operation_contexts  # noqa: E402

INPUT_PATHS = [
    PACKAGE / "inputs" / "all_events.json",
    PACKAGE / "inputs" / "focus_events.json",
    PACKAGE / "inputs" / "claim_evidence_matrix.json",
    PACKAGE / "inputs" / "episode_candidates.json",
    PROJECT / "outputs" / "research_blueprint_v1" / "source_audit.json",
    PROJECT / "outputs" / "ml_retrieval_evaluation" / "evaluation.json",
]
CODE_PATHS = [
    RESEARCH / "context_common.py",
    RESEARCH / "operation_context.py",
    RESEARCH / "episode_relations.py",
    RESEARCH / "compare_operation_contexts.py",
    RESEARCH / "import_grok_context_review.py",
    RESEARCH / "apply_context_review.py",
    RESEARCH / "build_grok_context_round1.py",
]


def esc(value):
    return html.escape(str(value), quote=True)


def middle(event):
    return next(frame for frame in event["frames"] if frame["role"] == "middle")


def copy_frames(inputs):
    OUT.joinpath("frames").mkdir(parents=True, exist_ok=True)
    copied = []
    by_id = {event["id"]: event for event in inputs["events"]}
    for event_id in {item["id"] for item in inputs["focus"]}:
        frame = middle(by_id[event_id])
        name = Path(frame["image"]).name
        source = FRAMES / name
        if not source.exists():
            raise RuntimeError(f"Missing frame {source}")
        digest = sha256_file(source)
        if digest != frame["sha256"]:
            raise RuntimeError(f"Frame hash changed for {name}")
        target = OUT / "frames" / name
        if not target.exists() or sha256_file(target) != digest:
            shutil.copy2(source, target)
        copied.append({"event_id": event_id, "file": f"frames/{name}", "sha256": digest,
                       "frame_zero_based": frame["frame_zero_based"], "seconds": frame["nominal_seconds"]})
    return copied


def copy_named_frames(events, names):
    index = {}
    for event in events:
        for frame in event["frames"]:
            index.setdefault(Path(frame["image"]).name, frame)
    copied = []
    for name in dict.fromkeys(names):
        frame = index.get(name)
        source = FRAMES / name
        if frame is None or not source.exists():
            raise RuntimeError(f"Missing interval frame {name}")
        digest = sha256_file(source)
        if digest != frame["sha256"]:
            raise RuntimeError(f"Frame hash changed for {name}")
        target = OUT / "frames" / name
        if not target.exists() or sha256_file(target) != digest:
            shutil.copy2(source, target)
        copied.append({"file": f"frames/{name}", "sha256": digest, "frame_zero_based": frame["frame_zero_based"],
                       "seconds": frame["nominal_seconds"]})
    return copied


def clip_link(video_name, start, end):
    path = BASELINE / 'outputs' / 'operation_groups' / 'evidence' / 'videos' / video_name
    if not path.exists():
        return ''
    return path.as_uri() + f'#t={start:.2f},{end:.2f}'


def review_questions(inputs):
    events = {event['id']: event for event in inputs['events']}
    event = events['E-4955d1f2073f23']
    return [{
        'id': 'Q-V28-jaw-travel',
        'blocks_current_conclusion': False,
        'event_ids': ['E-4955d1f2073f23'],
        'case': 'V28',
        'region': [event['region']],
        'time': '50.50-58.00s',
        'ls_url': event['ls_url'],
        'video': clip_link('task28.mp4', 50.50, 58.00),
        'images': ['frames/task28_001515.jpg', 'frames/task28_001739.jpg'],
        'frame_zero_based': 1515,
        'question': 'Is any clamp-jaw travel visible from 50.50 to 58.00 seconds?',
        'why': 'The member holder and the joint clamp already have distinct roles at 40.00 seconds. The endpoints are close-ups; the jammed caption appears in the middle frame. The endpoints do not establish jaw movement. That does not affect the role division.',
        'options': [
            {'id': 'caption_only', 'label': 'Only the caption is confirmed; jaw travel is not visible'},
            {'id': 'motion_visible', 'label': 'Jaw motion is visible between the endpoints'},
            {'id': 'cannot_tell', 'label': 'Inconclusive'},
        ],
        'effects_text': {
            '': 'No selection; the comparison table is unchanged.',
            'caption_only': 'Jaw travel stays unconfirmed in CMP-V28. The role division is unchanged.',
            'motion_visible': 'Set the evidence source for REL-V28-retry-caption to direct video observation and revise the comparison unknown.',
            'cannot_tell': 'Record an inconclusive result without turning a blank answer into a negative or changing the role division.',
        },
        'effects': {
            'caption_only': [{
                'target_type': 'comparison', 'target_id': 'CMP-V28-holder-versus-clamp',
                'summary': 'Jaw travel stays unconfirmed; the role division is unchanged.',
                'set': {'review_jaw': 'caption_only'},
            }],
            'motion_visible': [{
                'target_type': 'relation', 'target_id': 'REL-V28-retry-caption',
                'summary': 'The retry relation source changes from video caption to direct observation.',
                'set': {'source_kind': 'video_observed', 'note_suffix': ' The reviewer identified jaw motion between the endpoints.'},
            }, {
                'target_type': 'comparison', 'target_id': 'CMP-V28-holder-versus-clamp',
                'summary': 'The comparison now records the reviewed observation of jaw travel.',
                'set': {'unknowns': ['The reviewer identified jaw travel in the caption interval'], 'review_jaw': 'motion_visible'},
            }],
            'cannot_tell': [{
                'target_type': 'comparison', 'target_id': 'CMP-V28-holder-versus-clamp',
                'summary': 'Jaw travel remains inconclusive; the role division is unchanged.',
                'set': {'review_jaw': 'cannot_tell'},
            }],
        },
    }]


def lane_svg(title, lanes, start, end):
    width, height = 980, 46 + 34 * len(lanes)
    span = max(end - start, 0.001)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
             '<rect width="100%" height="100%" fill="#f7f4ef"/>',
             f'<text x="16" y="22" font-family="Segoe UI, sans-serif" font-size="14" fill="#24362f">{esc(title)}</text>']
    colors = {"focus": "#2f6f5e", "catalog": "#b7aea4", "paper": "#a15c38", "manual": "#8d4b4b"}
    for index, lane in enumerate(lanes):
        top = 40 + index * 34
        parts.append(f'<text x="16" y="{top + 16}" font-family="Segoe UI, sans-serif" font-size="12" fill="#24362f">{esc(lane["name"])}</text>')
        for bar in lane["bars"]:
            x = 210 + (bar["start"] - start) / span * 740
            w = max((bar["end"] - bar["start"]) / span * 740, 4)
            parts.append(f'<rect x="{x:.1f}" y="{top + 4}" width="{w:.1f}" height="16" rx="3" fill="{colors.get(bar.get("tone"), "#2f6f5e")}"/>')
            if w > 48:
                parts.append(f'<text x="{x + 4:.1f}" y="{top + 16}" font-family="Segoe UI, sans-serif" font-size="10" fill="white">{esc(bar["label"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def build_svgs(episodes):
    files = {}
    def dump(name, svg):
        path = OUT / name
        path.write_text(svg, encoding="utf-8")
        files[name] = name
    v30 = [item for item in episodes["episodes"] if item["group_id"] == "GRP-V30-insertion"]
    dump("process_v30.svg", lane_svg(
        "V30 approach then insert; gray bars are catalogued trials, green bars were frame-checked",
        [{"name": "Approach / insert", "bars": [
            {"start": item["start"], "end": item["end"], "label": item["episode_id"].replace("EP-", ""),
             "tone": "focus" if set(item["event_ids"]) & {"E-40558b96405bcc", "E-281f02ffaf59dc"} else "catalog"}
            for item in v30]}],
        min(item["start"] for item in v30) - 1, max(item["end"] for item in v30) + 1))
    v28 = [item for item in episodes["episodes"] if item["group_id"] == "GRP-V28-holder-and-clamps"]
    dump("process_v28.svg", lane_svg(
        "V28 holder, clamps, planned-path shot, and manual step stay on separate bars",
        [{"name": item["episode_id"].replace("EP-V28-", ""), "bars": [
            {"start": item["start"], "end": item["end"], "label": ",".join(item["phase"][:2]),
             "tone": "manual" if "manual" in item["episode_id"] else "paper" if "planned" in item["episode_id"] else "focus"}]}
         for item in v28],
        35, 205))
    v27 = [item for item in episodes["episodes"] if item["group_id"] == "GRP-V27-move-and-turn"]
    dump("process_v27.svg", lane_svg(
        "V27 three tracks overlap on one source clock; no release bar was added",
        [{"name": item["episode_id"].replace("EP-V27-", ""), "bars": [
            {"start": item["start"], "end": item["end"], "label": item["phase"][0], "tone": "focus"}]}
         for item in v27],
        3.35, 4.10))
    return files


def page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>
<style>
body{{margin:0;background:#f3efe7;color:#24362f;font:16px/1.6 "Segoe UI",sans-serif}}
main{{max-width:1180px;margin:auto;padding:28px 20px 64px}}
h1,h2{{line-height:1.25}} a{{color:#1f5c4d}}
.card,.table-wrap{{background:white;border:1px solid #ddd4c8;border-radius:8px;padding:16px;margin:14px 0}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #eee;padding:8px;vertical-align:top;text-align:left}}
img,svg{{max-width:100%;height:auto}} .pair{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.board-grid{{display:grid;grid-template-columns:1.45fr .8fr .85fr;gap:16px}}
.film{{display:grid;grid-template-columns:1fr 1fr;gap:8px}} .film img{{width:100%;background:#111}}
.small{{color:#5d6b66;font-size:14px}} .tag{{display:inline-block;background:#e7f0ec;border-radius:99px;padding:2px 8px;margin-right:6px}}
textarea,select{{width:100%;font:inherit}} button{{font:inherit;padding:8px 12px;margin-right:8px}}
@media(max-width:900px){{.pair,.board-grid,.film{{grid-template-columns:1fr}}}}
</style></head><body><main>{body}</main></body></html>"""


def board_html(boards):
    blocks = ["<h2>Three processes</h2>"]
    for board in boards:
        clips = " · ".join(
            f"<a href='{esc(clip_link(board['video'], clip['start'], clip['end']))}'>{esc(clip['label'])}</a>"
            for clip in board["clips"]
        )
        frames = "".join(
            "<figure><img src='frames/{file}' alt='{label}'><figcaption><b>{label}</b> {seconds:.2f}s / f{frame}<br>{kind}<br>{text}</figcaption></figure>".format(
                file=esc(frame["file"]), label=esc(frame["label"]), seconds=frame["seconds"],
                frame=frame["frame"], kind=esc(frame["kind"]), text=esc(frame["text"]),
            )
            for frame in board["frames"]
        )
        relations = "".join(
            f"<li><b>{esc(item['type'])}</b> <span class='tag'>{esc(item['kind'])}</span> {esc(item['text'])}</li>"
            for item in board["relations"]
        )
        blocks.append(
            f"<article class='card'><h2>{esc(board['case'])}</h2><p>{esc(board['question'])}</p><p>{clips}</p>"
            "<div class='board-grid'>"
            f"<div><h3>Process frames</h3><div class='film'>{frames}</div></div>"
            f"<div><h3>Object relations</h3><ul>{relations}</ul></div>"
            f"<div><h3>Observed differences</h3><p>{esc(board['difference'])}</p>"
            f"<p class='small'>This comparison does not require: {esc(', '.join(board['not_required']))}</p></div></div></article>"
        )
    return "".join(blocks)


def write_index(contexts, episodes, relations, comparisons, questions, figures, outcome):
    counts = contexts["counts"]
    blocks = [
        "<h1>Operation context, process relations, and architectural comparisons</h1>",
        "<p>This round documents interval evidence for three processes. The 549 original actions remain the complete index. The additional work organizes context and does not introduce a new SentenceTransformer retrieval experiment.</p>",
        f"<p><a href='ambiguity_review.html'>Open video question</a> · <a href='reviewed_comparison_matrix.json'>Reviewed comparisons</a> · <a href='operation_contexts.json'>operation_contexts.json</a> · <a href='README.txt'>Reproduction notes</a></p>",
        board_html(episodes["boards"]),
        "<div class='card'><h2>Reviewed results</h2>" + reviewed_html(outcome) + "</div>",
        "<div class='card'><h2>Coverage</h2><ul>",
        f"<li>Original events: {counts['actions']}. Candidate context: {counts['agent_candidate']}. Unanalyzed: {counts['not_analyzed']}.</li>",
        f"<li>Cases: {', '.join(counts['cases'])}. V08 is excluded. V12 region IDs remain under the V11 case ID; the two source videos remain distinct.</li>",
        f"<li>Process candidates: {len(episodes['episodes'])}. Relation edges: {len(relations['relations'])}. Newly human-confirmed processes: 0.</li>",
        f"<li>Records: {comparisons['counts']['comparisons']}. One-sided records are individual observations. V23/V26 serves as the format check.</li>",
        f"<li>Video questions still open without affecting these three findings: {len(questions)}.</li></ul></div>",
        "<div class='card'><h2>Timelines</h2><p class='small'>The frame sequences above show the observed processes. Timelines retain order and are supplementary to the frames.</p>",
    ]
    for name in ("process_v30.svg", "process_v28.svg", "process_v27.svg"):
        blocks.append(f"<img src='{name}' alt='{name}'>")
    blocks.append("</div>")
    blocks.append("<div class='card'><h2>From events to a design check</h2>")
    blocks.append("<p>V23 <code>E-3f86dd2a08388f</code> is labeled Nail joint. The middle frame shows the nailer body and tip above the lap joint. V26 <code>E-df6a3ede33d628</code> is labeled as positioning the nailer beneath the beam. The tip is close to the underside and the body extends off-frame to the right.</p>")
    blocks.append("<p>The research audit gives a text cosine of 0.526 and a mean image score of 0.516. Under the original thresholds, only the image score passes. These scores were not recomputed, and the original discovery route remains unknown.</p>")
    blocks.append("<p>CMP-D09-V23-V26 concerns representation. Marking only the tip omits the visible tool body. It supports R02. Distinct action phases preclude rankings of nailing efficiency, success rate, and minimum clearance.</p></div>")
    blocks.append("<div class='table-wrap'><h2>Comparison table</h2><table><tr><th>Comparison</th><th>Question</th><th>Common ground</th><th>Difference</th><th>Design check</th><th>Existing figure</th></tr>")
    for row in comparisons["comparisons"]:
        figure_id = ""
        if "existing_figure:" in row["provenance"]:
            figure_id = row["provenance"].split("existing_figure:", 1)[1].split(";")[0].strip()
        image = figures.get(figure_id, "")
        link = ""
        if image and (DIAGRAMS / image).exists():
            link = f"<br><a href='../research_state/diagram_delivery/{esc(image)}'>Existing figure</a>"
        kind = "Single observation" if len(row["sides"]) < 2 else row["question"]
        blocks.append("<tr>" + f"<td>{esc(row['comparison_id'])}</td><td>{esc(kind)}</td>"
                      + "".join(f"<td>{esc(row[key])}</td>" for key in ("common", "difference", "design_check"))
                      + f"<td>{esc(', '.join(row['maps_to']) or 'Outside the four primary findings')}{link}<br><span class='small'>{esc(row['provenance'])}</span></td></tr>")
    blocks.append("</table></div>")
    blocks.append("<div class='card'><h2>Retrieval evaluation interface</h2><p>The prior evaluation remains awaiting_relevance_review with zero formal human relevance assessments. AI prefill is not ground truth. The query, crop, model, fusion, and ranking remained fixed; no run, loss, or accuracy is reported.</p><p>For subsequent assessment, review each candidate for goal_compatible, evidence_readable, and useful_for_specified_comparison. See retrieval_evaluation_interface.json.</p></div>")
    (OUT / "index.html").write_text(page("Operation context and comparisons", "".join(blocks)), encoding="utf-8")


def write_review(questions):
    data = json.dumps(questions, ensure_ascii=False)
    script = r"""
const KEY = 'multicam-grok-context-round1';
const SCHEMA = 'multicam-grok-context-review-v1';
function payload() {
  const records = {};
  for (const question of QUESTIONS) {
    const decision = document.querySelector(`select[data-id="${question.id}"]`).value;
    const note = document.querySelector(`textarea[data-note="${question.id}"]`).value;
    records[question.id] = {decision, note};
  }
  return {schema: SCHEMA, records, exported_at: new Date().toISOString(), source_annotations_changed: false};
}
function save() {
  localStorage.setItem(KEY, JSON.stringify(payload()));
  document.getElementById('status').textContent = 'Saved in this browser. Source annotations are unchanged.';
}
function renderLayer(data) {
  const lines = Object.entries(data.records).filter(([, row]) => row.decision || row.note)
    .map(([id, row]) => `${id}: ${row.decision || 'Unselected'}${row.note ? ' / ' + row.note : ''}`);
  document.getElementById('layer').textContent = lines.length ? lines.join('\n') : 'No analysis-layer choices yet. A blank choice is unassessed.';
}
function showEffect(select) {
  const question = QUESTIONS.find(item => item.id === select.dataset.id);
  const node = document.getElementById('effect-' + question.id);
  if (node) node.textContent = (question.effects_text || {})[select.value] || '';
}
function apply(data) {
  if (!data || data.schema !== SCHEMA || !data.records) throw new Error('schema');
  const known = new Set(QUESTIONS.map(question => question.id));
  for (const [id, row] of Object.entries(data.records)) {
    if (!known.has(id)) throw new Error('unknown ' + id);
    const allowed = new Set(['', ...QUESTIONS.find(question => question.id === id).options.map(option => option.id)]);
    if (!allowed.has(row.decision || '')) throw new Error('decision ' + id);
    const select = document.querySelector(`select[data-id="${id}"]`);
    select.value = row.decision || '';
    document.querySelector(`textarea[data-note="${id}"]`).value = row.note || '';
    showEffect(select);
  }
  save();
  renderLayer(payload());
}
function restore() {
  const raw = localStorage.getItem(KEY);
  if (!raw) { renderLayer(payload()); return; }
  apply(JSON.parse(raw));
}
function exportAll() {
  const data = payload();
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'multicam_grok_context_review.json';
  link.click();
  URL.revokeObjectURL(link.href);
  document.getElementById('status').textContent = 'All questions exported. Unselected answers are included as unassessed.';
  return data;
}
function clearSaved() {
  localStorage.removeItem(KEY);
  for (const question of QUESTIONS) {
    document.querySelector(`select[data-id="${question.id}"]`).value = '';
    document.querySelector(`textarea[data-note="${question.id}"]`).value = '';
    showEffect(document.querySelector(`select[data-id="${question.id}"]`));
  }
  renderLayer(payload());
  document.getElementById('status').textContent = 'Selections cleared in this browser.';
}
document.getElementById('save').addEventListener('click', save);
document.getElementById('export').addEventListener('click', exportAll);
document.getElementById('clear').addEventListener('click', clearSaved);
document.getElementById('import-file').addEventListener('change', event => {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try { apply(JSON.parse(reader.result)); document.getElementById('status').textContent = 'Imported to the analysis layer. Source annotations are unchanged.'; }
    catch (error) { document.getElementById('status').textContent = 'Import failed: ' + error.message; }
  };
  reader.readAsText(file);
});
document.querySelectorAll('select').forEach(node => node.addEventListener('change', () => showEffect(node)));
document.querySelectorAll('select,textarea').forEach(node => node.addEventListener('change', save));
window.__review = {payload, apply, save, exportAll, clearSaved, restore};
restore();
"""
    (OUT / "review.js").write_text("const QUESTIONS = " + data + ";\n" + script, encoding="utf-8")
    cards = []
    for question in questions:
        options = "".join(f"<option value='{esc(item['id'])}'>{esc(item['label'])}</option>" for item in question["options"])
        images = "".join(f"<img src='{esc(src)}' alt='{esc(question['id'])}'>" for src in question["images"])
        if len(question["images"]) > 1:
            images = f"<div class='pair'>{images}</div>"
        video = f"<a href='{esc(question['video'])}'>Open this video segment</a>" if question["video"] else "Video is missing from the local baseline directory"
        cards.append(
            f"<article class='card' id='{esc(question['id'])}'><h2>{esc(question['question'])}</h2>"
            f"{images}<p>{esc(question['case'])} · {esc(question['time'])}<br>"
            f"Events {esc(', '.join(question['event_ids']))}<br>"
            f"<a href='{esc(question['ls_url'])}'>Label Studio</a> · {video}</p>"
            f"<p class='small'>{esc(question['why'])}</p>"
            f"<select data-id='{esc(question['id'])}'><option value=''>Not selected</option>{options}</select>"
            f"<p class='small' id='effect-{esc(question['id'])}'>{esc(question['effects_text'][''])}</p>"
            f"<textarea data-note='{esc(question['id'])}' rows='2' placeholder='Optional notes'></textarea></article>"
        )
    body = ("<p><a href='index.html'>Back to overview</a></p><h1>A question the video leaves open</h1>"
            "<p>The overview uses interval frames to show insertion, assigned roles, and the cause of the sweep. This question does not alter those findings. A selected answer identifies the relation or comparison it changes. Export the review and run the import command to update the generated overview and table.</p>"
            "<p><button id='save' type='button'>Save</button><button id='export' type='button'>Export all as JSON</button>"
            "<label>Import JSON <input id='import-file' type='file' accept='application/json,.json'></label> "
            "<button id='clear' type='button'>Clear browser selections</button></p><p id='status' class='small'></p>"
            "<div class='card'><h2>Analysis overlay</h2><pre id='layer'></pre></div>" + "".join(cards)
            + "<script src='review.js'></script>")
    (OUT / "ambiguity_review.html").write_text(page("Open-question review", body), encoding="utf-8")


def local_links(path):
    text = path.read_text(encoding="utf-8")
    links = []
    for token in ("href='", 'href="', "src='", 'src="'):
        start = 0
        while True:
            found = text.find(token, start)
            if found < 0:
                break
            quote = token[-1]
            end = text.find(quote, found + len(token))
            links.append(text[found + len(token):end])
            start = end + 1
    return links


def check_links(paths):
    missing = []
    for path in paths:
        for link in local_links(path):
            if link.startswith(("http://", "https://", "mailto:", "file:")):
                continue
            target = (path.parent / link.split("#")[0]).resolve()
            if not target.exists():
                missing.append(f"{path.name}:{link}")
    if missing:
        raise RuntimeError("Missing links: " + ", ".join(missing[:12]))


def roundtrip(questions, relations, comparisons):
    sample = {
        "schema": REVIEW_SCHEMA,
        "records": {questions[0]["id"]: {"decision": "motion_visible", "note": "roundtrip only"}},
    }
    incoming = OUT / "_roundtrip_input.json"
    try:
        records = validate_review(json.loads(json.dumps(sample)), questions)
        if records[questions[0]["id"]]["note"] != "roundtrip only":
            raise RuntimeError("Import did not keep the note")
        trial = apply_review(questions, relations, comparisons, {"records": records})
        retry = next(item for item in trial["relations"]["relations"] if item["relation_id"] == "REL-V28-retry-caption")
        if retry["source_kind"] != "video_observed":
            raise RuntimeError("Review choice did not update the named relation")
        compared = next(item for item in trial["comparisons"]["comparisons"] if item["comparison_id"] == "CMP-V28-holder-versus-clamp")
        if compared.get("review_jaw") != "motion_visible":
            raise RuntimeError("Review choice did not update the named comparison")
        bad = dict(sample)
        bad["records"] = dict(sample["records"])
        bad["records"]["missing"] = {"decision": "", "note": ""}
        try:
            validate_review(bad, questions)
        except SystemExit:
            rejected = True
        else:
            rejected = False
        if not rejected:
            raise RuntimeError("Unknown question was accepted")
        if (OUT / "review_results.json").exists():
            raise RuntimeError("Roundtrip must not leave a review file")
    finally:
        incoming.unlink(missing_ok=True)


def retrieval_interface(inputs):
    rows = inputs["evaluation"]["rows"]
    return {
        "schema": "multicam-retrieval-evaluation-interface-v1",
        "status": inputs["evaluation"].get("status"),
        "human_review_count": inputs["evaluation"].get("human_review_count"),
        "relevance_review_count": inputs["evaluation"].get("relevance_review_count"),
        "queries_in_evaluation_file": sorted({row["query_id"] for row in rows}),
        "methods_in_evaluation_file": sorted({row["method"] for row in rows}),
        "evaluation_rows": len(rows),
        "merged_review_cards_recorded_by_blueprint": 161,
        "card_count_reopened_this_round": False,
        "ai_prefill_is_ground_truth": False,
        "prepared_fields": ["goal_compatible", "evidence_readable", "useful_for_specified_comparison"],
        "new_run_created": False,
        "reason": "The query, crop, model, fusion, and ranking are unchanged.",
        "model_calls": 0,
        "training": False,
        "loss": None,
        "optimizer": None,
        "precision_at_5": None,
    }


def main():
    before = {str(path): sha256_file(path) for path in INPUT_PATHS}
    inputs = load_inputs()
    contexts = build_operation_contexts(inputs)
    episodes, relations = build_episode_relations(inputs)
    comparisons = build_comparisons(inputs)
    OUT.mkdir(parents=True, exist_ok=True)
    copied = copy_frames(inputs)
    names = [frame["file"] for board in episodes["boards"] for frame in board["frames"]]
    names.extend(Path(src).name for question in review_questions(inputs) for src in question["images"])
    interval = copy_named_frames(inputs["events"], names)
    questions = review_questions(inputs)
    from PIL import Image
    for item in copied + interval:
        with Image.open(OUT / item["file"]) as image:
            image.verify()
    svgs = build_svgs(episodes)
    public_contexts = {key: value for key, value in contexts.items() if key != "by_id"}
    public_contexts["frame_files"] = copied
    write_json(OUT / "operation_contexts.json", public_contexts)
    write_json(OUT / "episodes.json", episodes)
    write_json(OUT / "relations.json", relations)
    write_json(OUT / "comparison_matrix.json", comparisons)
    write_json(OUT / "review_questions.json", questions)
    write_json(OUT / "retrieval_evaluation_interface.json", retrieval_interface(inputs))
    figures = {item["id"]: item.get("primary_image", "") for item in inputs["matrix"]["figures"]}
    outcome = apply_review(questions, relations, comparisons, load_review(OUT / "review_results.json"))
    write_reviewed(outcome)
    write_index(contexts, episodes, relations, comparisons, questions, figures, outcome)
    write_review(questions)
    (OUT / "README.txt").write_text("Reproduction notes are written after validation.\n", encoding="utf-8")
    check_links([OUT / "index.html", OUT / "ambiguity_review.html"])
    roundtrip(questions, relations, comparisons)
    after = {str(path): sha256_file(path) for path in INPUT_PATHS}
    if before != after:
        raise RuntimeError("Input files changed while building")
    cases = {row["original_action"]["case"] for row in contexts["records"]}
    if "V08" in cases or "V8" in cases:
        raise RuntimeError("V8 should stay excluded")
    v12 = [row for row in contexts["records"] if row["original_action"]["region"].startswith("V12")]
    v11 = [row for row in contexts["records"] if row["original_action"]["region"].startswith("V11")]
    if {row["original_action"]["case"] for row in v12 + v11} != {"V11"}:
        raise RuntimeError("V11/V12 case canonicalisation changed")
    if {row["original_action"]["source_sha256"] for row in v12} & {row["original_action"]["source_sha256"] for row in v11}:
        raise RuntimeError("V11 and V12 source videos were merged")
    focus_rows = [row for row in contexts["records"] if row["analysis_status"] == "agent_candidate"]
    if any(not row["operation_goal"]["value"] or not row["phase"]["value"] or not row["unknowns"] for row in focus_rows):
        raise RuntimeError("A focus record is missing goal, phase, or unknowns")
    if any(row["human_confirmation"]["new_fields"] for row in focus_rows):
        raise RuntimeError("Agent fields were marked as human-confirmed")
    manifest = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_calls": 0,
        "training": False,
        "loss": None,
        "new_thresholds": False,
        "new_embeddings": False,
        "inputs": {str(path): before[str(path)] for path in INPUT_PATHS},
        "code": {path.name: sha256_file(path) for path in CODE_PATHS},
        "parameters": {
            "focus_rule": "38 event ids already cited by claim_evidence_matrix",
            "text_model": "not called; historical all-MiniLM-L6-v2 scores only cited",
            "image_model": "not called",
            "ranking_limit": "no new Top5",
        },
        "coverage": contexts["counts"] | comparisons["counts"] | {
            "episodes": len(episodes["episodes"]),
            "relations": len(relations["relations"]),
            "review_questions": len(questions),
            "frames_copied": len({item["file"] for item in copied + interval}),
            "process_svgs": list(svgs),
        },
        "outputs": sorted(path.name for path in OUT.iterdir() if path.is_file()),
    }
    write_json(OUT / "run_manifest.json", manifest)
    readme = """Operation context and comparison results

Open index.html for the overview or ambiguity_review.html for review.
Run python build_grok_context_round1.py from the research source directory.
Run python import_grok_context_review.py path/to/review.json to apply choices
to the analysis layer. The source annotations and original inputs stay read-only.

See the repository research README for input and baseline setup.
No retrieval model, threshold, crop, ranking, or loss was changed.
"""
    (OUT / "README.txt").write_text(readme, encoding="utf-8")
    verification = {
        "schema": SCHEMA + "-verification",
        "passed": True,
        "input_hashes_unchanged": True,
        "actions": 549,
        "focus_events": 38,
        "human_confirmed_new_fields": 0,
        "v8_excluded": True,
        "v11_v12_case_merged_sources_not_merged": True,
        "links_checked": True,
        "frames_readable": len({item["file"] for item in copied + interval}),
        "import_roundtrip": True,
        "unknown_question_rejected": True,
        "model_calls": 0,
        "loss": None,
        "fake_decisions_left_in_output": False,
    }
    write_json(OUT / "verification.json", verification)
    manifest["outputs"] = sorted(path.name for path in OUT.iterdir() if path.is_file())
    write_json(OUT / "run_manifest.json", manifest)
    print(json.dumps({"out": str(OUT), "actions": 549, "focus": 38, "questions": len(questions)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
