# MultiCam research workflows

These Python entry points analyze previously collected MultiCam evidence, trace
semantic groups, and render the operation-context review. They use local source
data, media, and saved model artifacts. The example evidence describes the format.

## Setup

Use Python 3.12 or newer. Install the dependencies with
`python -m pip install -r requirements.txt`.

Set the following environment variables to point to the local research files:

| Variable | Location | Default relative to this directory |
| --- | --- | --- |
| `MULTICAM_DATA_ROOT` | The context handoff folder containing `inputs/` and `project/outputs/` | `data/` |
| `MULTICAM_BASELINE_ROOT` | The baseline handoff folder containing saved outputs and embeddings | `data/baseline/` |
| `MULTICAM_EVIDENCE_TEXT` | The local JSON with historical evidence and observations | `data/inputs/historical_evidence.json` under the default data root |
| `MULTICAM_SBERT_MODEL` | A local SentenceTransformer model used by the audit and search commands | The original model subdirectory under the baseline root |

Prepare the historical evidence input from the archived `project/research`
folder of the matching context handoff. The exporter reads the original source
as data and does not execute it.

```sh
python export_local_evidence.py --legacy-research "/path/to/archived/project/research" --out "/path/to/local/evidence.json"
```

Keep the exported evidence JSON in your local data folder. It preserves the
language and contents of the original research records. The example
`historical_evidence.example.json` shows the schema with invented values.

## Entry points

| Command | Input and result |
| --- | --- |
| `python build_grok_context_round1.py` | Reads the action index, focus events, claim matrix, episode candidates, audit, evaluation, and referenced local media. Builds context records, episode relations, the comparison matrix, and the review interface under `project/outputs/grok_context_round1/`. |
| `python import_grok_context_review.py /path/to/review.json` | Validates exported choices and applies them to the generated analysis overlay. |
| `python semantic_spread.py` | Joins the action index with saved semantic groups and embeddings. Rebuilds the full semantic report under `project/outputs/grok_semantic_spread/`. Keep the original referenced figures and report assets in those output folders when rebuilding links. |
| `python sbert_handoff.py audit` | Checks local clustering against the historical grouping. |
| `python sbert_handoff.py encode-check` | Checks the local model's embeddings against the archived arrays. |
| `python sbert_handoff.py search "place a timber member"` | Searches the original expressions using the locally supplied model and records. |

A fresh clone can inspect the code and run argument help. Full workflows use
the original local research inputs, including referenced source frames,
figures, model files, and prior reports.
