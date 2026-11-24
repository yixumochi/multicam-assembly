# Manuscript and evidence builder

Use Python 3.11 or later and install `requirements.txt`.

```bash
python build_paper_results.py --source /path/to/operation_synthesis --content /path/to/manuscript.json --output ./paper-output
```

The source directory supplies `events.json`, `pairs.json`, `manifest.json`, and the evidence images referenced by each event. The content file supplies the manuscript text and the result-to-frame selections. Use `manuscript.example.json` as a schema example, or adapt a locally generated `evidence_manifest.json` from the manuscript archive.

Each panel selection is `[event order, frame index or "context", "full" or "crop"]`. Pair indices in a result start at 1. Event frame indices are zero-based. Keep review records, source videos, figures, and unpublished manuscript text with the local inputs.

The builder writes DOCX, HTML, text, figure PNGs, and an evidence manifest. The manifest records the original frame images and hashes for source tracing.
