# MultiCam Assembly

MultiCam documents 15 timber assembly cases through video, action timelines, spatial comparisons, and annotated frames.

**[Open the project website](https://yixumochi.github.io/multicam-assembly/)** · **[Browse all 15 cases](cases/README.md)** · **[Browse the research code](research-code/README.md)**

## Quick start with V04

1. [Open Spatial Timber Assemblies](https://yixumochi.github.io/multicam-assembly/#human-robot/V04) and use the case timeline to explore the assembly sequence.
2. [Open V04 observation 04](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04) to see the machine masks and annotated working directions for *Approach local joint*. The left panel shows the masks across three frames. The right panel shows the contact locations and the modeled resultant.

[![V04 observation board showing the aligned machine masks and working directions](observation/boards/V04/04.webp)](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04)

[Open the complete V04 PDF](https://yixumochi.github.io/multicam-assembly/observation/boards/V04.pdf) · [Find the V04 video and drawings](cases/V04/)

Continue with [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections), the [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html), or the full [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html) collection.

## Repository layout

```text
cases/           Published video and drawings, one folder per case
research-code/   Python workflows, dependencies, and run instructions
observation/     Assembly in Motion previews and final case PDFs
spatial/         Atlas of Assembly Space and footprint comparisons
index.html       Main website, case timelines, and Action Relationships
```

The standalone web pages for [action pair comparisons](action-pair-summary/), [body motion](body_five/), and [video-to-plan views](video-to-top-view/) live alongside the main site. The site reads shared media and evidence from [`media/`](media/), [`plates/`](plates/), [`runs/`](runs/), and [`analysis/`](analysis/).

## Reproduce the V04 observation layout

[The board generator](research-code/boards/replicate_force_boards.py) renders the equipment-mask and grip-direction layout. It uses reviewed V04 annotations, event records, source frames, masks, and the rendering fonts. Set up these local inputs using the [board workflow instructions](research-code/boards/README.md#provide-the-input-files). The published example above is ready to view.

From the repository root, with Python 3.11 or newer and the inputs in place:

```sh
cd research-code/boards
python -m pip install -r requirements.txt
python replicate_force_boards.py V04
```

With the default workspace, the script writes `work/replication/V04_robot_mask_grip_resultant.pdf`. The [board workflow README](research-code/boards/README.md#choose-an-entry-point) also describes revision and final PDF assembly.

## Other research workflows

| Task | Instructions |
| --- | --- |
| Analyze events, action relationships, and semantic spread | [Research analysis](research-code/research/README.md) |
| Refine V01 mallet and timber masks | [V01 case tools](research-code/case-tools/README.md) |
| Build manuscript figures and documents | [Paper builder](research-code/paper/README.md) |
| Reconstruct V21 and check its Rhino solids | [V21 reconstruction](research-code/v21-rebuild/README.md) |
| Prepare labels, train a detector, or run connector inference | [Connector workflow](research-code/connector/README.md) |

To check out the research code without downloading all the case media:

```sh
git clone --filter=blob:none --sparse https://github.com/yixumochi/multicam-assembly.git
cd multicam-assembly
git sparse-checkout set research-code
```
