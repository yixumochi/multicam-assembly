# Observation board generation

These scripts turn sampled frames, reviewed masks, and manual annotations into event-level PDF boards. The diagrams show image-plane geometry and explicitly marked assumptions about working directions.

## Setup

Use Python 3.11 or newer. Install the PDF and image dependencies from this directory.

```sh
python -m pip install -r requirements.txt
```

For the optional frame-extraction utility `grip_inspect.py`, also install `opencv-python-headless`.

## Provide the input files

Set the environment variables below before running the scripts. Relative override paths are interpreted from the current directory. Defaults are relative to this source folder or the configured work folder.

| Variable | Default | Input or destination |
| --- | --- | --- |
| `MULTICAM_BOARD_WORK` | `work/` | Review workspace for annotations, masks, and pilot inputs |
| `MULTICAM_BOARD_OUTPUTS` | `outputs/` | Destination for generated PDFs |
| `MULTICAM_BOARD_EVENTS` | `work/events.json` | Array of source events with case IDs, video names, and selected frames |
| `MULTICAM_BOARD_EVIDENCE` | `work/` | Base directory for the frame `image` paths in the event JSON |
| `MULTICAM_BOARD_V04_VIDEO` | `work/videos/v04.mp4` | Source recording for V04 frame and gripper inspections |
| `MULTICAM_BOARD_FONT_REGULAR` | `work/fonts/regular.ttf` | Regular TrueType font |
| `MULTICAM_BOARD_FONT_BOLD` | `work/fonts/bold.ttf` | Bold TrueType font |

The event array uses `case`, `id`, `video`, `start`, and `frames`. Each event needs one `start`, `middle`, and `end` frame. Frame records identify the image path, original frame index, timestamp, native size, and checksum. Keep the original case-specific event sets and image sizes when reproducing the published boards. Any `mask` path in annotation JSON must point to a readable local file, either by absolute path or relative to the current directory. Masks must match the source frame size and use binary pixel values of 0 or 255. Use the original fonts to retain the original spacing and line breaks.

Event records, masks, raw footage, reviewed PDFs, and fonts are external inputs to the source release.

## Choose an entry point

- `python review_frames.py V04 --grid` creates a contact sheet for checking selected frames. Add `--masks` to overlay masks already in the work folder.
- `python render_boards.py --case V04` renders basic observation sheets from `work/annotations/V04.json`. Pass `--annotations` to provide another annotation file. Use `--draft --event-id EVENT_ID` to render one event with partial annotations.
- `python replicate_force_boards.py V04` renders the equipment-mask and grip-direction layout using `work/replication/V04.json`.
- `python revise_force_boards.py V04` reads verified revisions and page ordering from `work/revision/V04.json` and `work/pdf_review_20261121/V04/pages.json` before writing the revised case PDF.
- `python render_v30_full.py V04 V30` assembles final case PDFs under `outputs/V30_full/`. It uses the event order, base annotations, case revisions, optional `work/full_v30/overrides/CASE.json`, and the 48 approved pilot pages listed in `pilot_index()`. The pilot files belong in `work/replication/` and `outputs/v04_format_samples/`.
- `machine_refine.py`, `machine_board.py`, `grip_inspect.py`, `grip_board.py`, `robot_force_board.py`, and the `render_v04_*` scripts provide case-specific diagnostics and pilots. Supply their designated source media and review artifacts to reproduce those steps.
