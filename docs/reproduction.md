# Reproduce MultiCam results

The public repository contains the website, published case media, observation boards, and the source of several processing workflows. The routes below state where each run starts and what it generates.

| Route | Input | Output and verified scope |
| --- | --- | --- |
| Browse locally | A full repository checkout | The published site. A local HTTP check covered six main pages, 15 case videos, 30 case drawings, and 13 PDFs. |
| Recalculate an action comparison | Published action-pair data | A turning gap of 24.6° between the absolute turns of “Hold timber at joint” and “Position timber at joint”. |
| Re-encode historical action names | Local all-MiniLM-L6-v2 model and the matching SentenceTransformer handoff | All 210 label vectors matched the saved values exactly. Clustering reproduced all 142 groups. The selected cosine matches the published score within `1e-6`. |
| Recalculate V22 S01 drawing lift | Released pixel coordinates for feature 80, the fixed focal length, and the fixed depth | All 23 saved drawing coordinates in camera space match. The saved shot-local geometry record retains the unsupported camera frame 2112. |
| Regenerate V04 boards | Local core research ZIP with V04 event frames, masks, contact annotations, and revisions | Five retained events were rendered into a new PDF from the reviewed inputs. Three source frame hashes per board were checked, and all pages were inspected visually. |
| Regenerate upstream camera-supported tracks | Source shot, original SAM2.1 inputs and weights, feature tracking setup, Depth Pro, camera-fitting code and configuration | The V22 walkthrough shows cached evidence and processing decisions. The complete upstream run and its verified configurations remain to be recovered for an independent run from the original film. |

## Start with the public examples

From a full checkout with Python 3.11 or newer:

```sh
python examples/verify_published_examples.py
python -m http.server 8000
```

Open `http://localhost:8000/` while the server runs. The example script requires only the Python standard library and returns both results as JSON. The recorded turns are +27.5° and −2.9°. Their magnitudes differ by 24.6°, and the published cosine is approximately 0.897. For V22, the example uses the released per-frame `uv` coordinates and projects them with the documented fixed focal length and depth, using the center of the 960 × 540 frame. The camera-supported local path is a separate result in the lineage data. [Action pair data](../action-pair-summary/data.json) · [V22 point lineage](../video-to-top-view/point_lineage.json) · [Spatial method](../video-to-top-view/technical.html)

## Regenerate the retained V04 boards

Use the core research ZIP from the local project archive. It contains the event and evidence collection and the archived observation board workspace. Use the compatible regular and bold TrueType fonts from the original workflow for comparable text layout. In the verified Windows run these were Microsoft YaHei regular and bold.

Run from the repository root in PowerShell. Substitute the archive and font paths on your machine.

```powershell
python -m pip install -r research-code/boards/requirements.txt
python examples/prepare_v04_archive.py --archive "D:/path/to/core-research.zip" --output "../v04-inputs"
$v04Input = (Resolve-Path "../v04-inputs").Path
$env:MULTICAM_BOARD_WORK = Join-Path $v04Input "work"
$env:MULTICAM_BOARD_EVENTS = Join-Path $v04Input "events.json"
$env:MULTICAM_BOARD_EVIDENCE = $v04Input
$env:MULTICAM_BOARD_FONT_REGULAR = "C:/Windows/Fonts/msyh.ttc"
$env:MULTICAM_BOARD_FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
python research-code/boards/reproduce_retained_v04.py --catalog observation/boards/catalog.json --output ../V04-reproduced.pdf
```

The renderer uses the retained event IDs in the catalog, applies archived revisions and overrides, and builds the five pages in catalog order. Its output uses the current renderer. The published PDF also reflects the original layout and page-selection process. Complete assembly of the historical 22-page V04 draft additionally needs the approved pilot PDFs and legacy reviewed masks, including the mask referenced by the old “Move robot within module” record. [Board workflow](../research-code/boards/README.md) · [Published V04](../observation/boards/V04.pdf)

## Re-encode the historical action names

Use the local SentenceTransformer handoff containing `work/semantic_run/`, `outputs/semantic_action_groups.json`, and the saved all-MiniLM-L6-v2 model. The handoff includes `requirements-sbert.txt`. The verified run used Python 3.12.14, SentenceTransformers 5.1.2, Transformers 4.57.1, PyTorch 2.9.1, NumPy 2.2.6, and scikit-learn 1.7.2.

```powershell
$handoff = "D:/path/to/SentenceTransformer-handoff"
python -m pip install -r "$handoff/requirements-sbert.txt"
$env:MULTICAM_BASELINE_ROOT = $handoff
python research-code/research/sbert_handoff.py audit
python research-code/research/sbert_handoff.py encode-check
```

The audit checks cluster membership. The encoding check runs the local model on CPU and compares its normalized embeddings with the saved matrix. [Research workflow and model settings](../research-code/research/README.md)

## Run the historical research workflows

| Module | Inputs to provide | Outputs |
| --- | --- | --- |
| [Research analysis](../research-code/research/README.md) | Event index, source frame evidence, prior reports, review choices, historical groups and vectors, and the SentenceTransformer checkpoint for text encoding | Semantic grouping and search, context annotations, related episodes, comparison matrices, and review reports. |
| [Observation boards](../research-code/boards/README.md) and [V01 mask refinement](../research-code/case-tools/README.md) | Source frames, event records, masks, contact annotations, fonts, and revisions | Review sheets, rendered boards, and assembled PDFs. |
| [V21 reconstruction](../research-code/v21-rebuild/README.md) | Source film, optional source figure, and Rhino 8 | Image-constrained, unitless geometry for visual and topological comparison, plus a validation report. |
| [Connector demonstration](../research-code/connector/README.md) | Connector video and trusted detector weights. Training also requires the split LabelMe dataset and the matching training environment. | Annotated video and per-frame CSV with detections, tracks, and assembly-state estimates. |
| [Manuscript builder](../research-code/paper/README.md) | Events, pair selections, frame evidence, source manifest, and manuscript content | Evidence figures, document and HTML, and the frame provenance manifest. |

The historical archive contains 549 events. The current website action explorer contains 536 distinct events and 239 names. All 536 event IDs were found in the historical index. Thirteen archived records fall outside that published selection. Use event IDs and the released site data when reconciling the two versions. The archived vector comparison reproduced all 1,673 published edges whose two labels were present in the earlier 210-label matrix, within `1e-5`.
