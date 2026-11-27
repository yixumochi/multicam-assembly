# MultiCam Assembly

## 1. Project overview

A drawing shows where a timber member belongs. Putting it there takes room to move the member, turn it, and hold it at the joint. MultiCam Assembly studies how that work is organised across 15 filmed timber projects assembled by people, robots, or both.

From the footage, we mark when each operation takes place. We use computer vision to identify visible people, equipment, and timber and track selected points across frames. Depth estimates and camera checks help map movement onto a local ground plane. Plans and timelines show where work happens and in what order. Close views of the joint record where equipment grips the member and how it moves into position.

The case comparisons show that assemblies with similar finished footprints can occupy different amounts of space while they are being built. At the joint, actions with similar names can involve different turns. MultiCam brings the construction process into the architectural drawing by linking plans, timelines, and studies of individual joints to the source footage. These records let designers study the space used to move and handle timber alongside the finished form.

| Human-led | Human–robot | Robotic assembly |
| :---: | :---: | :---: |
| <a href="https://yixumochi.github.io/multicam-assembly/#human-led/V01"><img src="media/case-gallery/V01.webp" width="240" alt="A worker assembles a timber frame by hand in V01"></a> | <a href="https://yixumochi.github.io/multicam-assembly/#human-robot/V04"><img src="media/case-gallery/V04.webp" width="240" alt="A robot carries a timber member at the V04 assembly site"></a> | <a href="https://yixumochi.github.io/multicam-assembly/#robotic-assembly/V22"><img src="media/case-gallery/V22.webp" width="240" alt="Robots assemble large timber components in the V22 workshop"></a> |
| [V01 · UTFSM timber frame](https://yixumochi.github.io/multicam-assembly/#human-led/V01) | [V04 · Spatial Timber Assemblies](https://yixumochi.github.io/multicam-assembly/#human-robot/V04) | [V22 · Semiramis](https://yixumochi.github.io/multicam-assembly/#robotic-assembly/V22) |

[Open the project website](https://yixumochi.github.io/multicam-assembly/) · [Browse all 15 cases](cases/README.md) · [Research code](research-code/README.md)

### Quick Start

**Explore in your browser.** Open V04 and follow the video and timeline together. Select the highlighted interval for *Approach local joint* to see how the three frames, machine masks, and grip directions relate. [V04 case](https://yixumochi.github.io/multicam-assembly/#human-robot/V04) · [Open the observation directly](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04)

**Run a public example.** With Git and Python 3.11 or newer, run these commands.

```sh
git clone https://github.com/yixumochi/multicam-assembly.git
cd multicam-assembly
python examples/verify_published_examples.py
```

The script checks the turning comparison and verifies 23 V22 drawing coordinates from saved image points using the data in this repository.

## 2. Cases and evidence

1. **Collect the case material.** Link each source film to the available project drawings and references.
2. **Mark actions in the film.** Use Label Studio to attach an English action name to a time interval and keep representative frames.
3. **Prepare each comparison.** Use name similarity to select action pairs, use image tracks and geometry to produce plan views, and review selected frames for masks, contacts, and working directions.

[Case index](cases/README.md) · [Start here / Methods](https://yixumochi.github.io/multicam-assembly/)

## 3. Research outputs

### Actions and movement

**Action names → vectors → similarity → review the footage.** SentenceTransformer uses `all-MiniLM-L6-v2` to encode each action name as a 384-value vector. Cosine similarity helps select actions to compare.

The clip follows V21 *Transport held timber* and V04 *Transport and rotate timber*, whose name similarity is **0.822**. The source frames show how each operation was performed.

[![Animation of two timber transport labels being encoded, compared by cosine similarity, and checked against source frames](media/readme/sentence-transformer.gif)](https://yixumochi.github.io/multicam-assembly/media/methods/sentence-transformer.mp4)

**A second comparison at the joint.** V28 *Hold timber at joint* and V21 *Position timber at joint* have a name similarity of **0.897**. The animation starts with matched keyframes, then shows the changes between them, the angle at each frame, and the outlines aligned at the grip.

[![V28 and V21 comparison animation. It shows their paired source keyframes and outlines, followed by movement between keyframes, image-plane angle curves, and grip-aligned overlays.](media/readme/v28-v21-joint-comparison.gif)](https://yixumochi.github.io/multicam-assembly/#action-pair=90:171)

From middle to end, the timber axis turns **+24.6°** in V28 and **−3.2°** in V21. Angles are read in each camera image. Grip displacement is measured from the middle keyframe and divided by the case’s scale H. [Open the two-event comparison](https://yixumochi.github.io/multicam-assembly/#action-pair=90:171)

[Play the original video](https://yixumochi.github.io/multicam-assembly/media/methods/sentence-transformer.mp4) · [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections) · [Action Names and Turning](https://yixumochi.github.io/multicam-assembly/action-pair-summary/scatter.html)

### From video to top view

In V22, a mask selects the robot and surface points are tracked across frames. Those image tracks feed two views:

1. **Local top view:** depth and camera checks give supported coordinates on the shot's ground plane.
2. **Workshop drawing:** a separate fixed-depth projection is rotated and translated onto the plan as a schematic overlay.

The clip shows both views, each with its own coordinate frame.

[![Animation of V22 from the source video and robot mask through feature tracking and depth to the local path and workshop plan](media/readme/v22-video-to-top-view.gif)](https://yixumochi.github.io/multicam-assembly/video-to-top-view/index.html)

[![V22 feature 80 on the local ground plane, with start and end frames and a gap at unsupported frame F2112](media/readme/v22-trajectory-preview.png)](https://yixumochi.github.io/multicam-assembly/video-to-top-view/technical.html#animation)

The plot follows **feature 80**, the same robot surface point shown in the clip. It marks the start and end on the shot’s local ground plane and leaves a gap where the observation is unsupported. [All robot feature tracks and support checks](video-to-top-view/assets/24_robot_tracks_local.png) · [Coordinates used in this preview](video-to-top-view/point_lineage.json)

[Play the full walkthrough](https://yixumochi.github.io/multicam-assembly/video-to-top-view/index.html) · [Open the workshop plan](video-to-top-view/assets/31_v22_published_plan.png) · [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html)

### Local assembly observations

In V04, one robot brings a timber member toward a joint. These details come from the published *Approach local joint* board.

**Equipment masks at the start, middle, and end**

[![The V04 mechanical arm highlighted in blue, green, and orange in the three source frames](media/readme/v04-machine-masks.png)](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04)

**The three masks aligned to a common point**

<a href="https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04"><img src="media/readme/v04-mask-overlay.png" width="250" alt="Three translated V04 machine masks overlaid in blue, green and orange, with a shared timber reference point"></a>

Blue, green, and orange show the start, middle, and end masks after translation to the same timber reference point.

**Grip locations and working directions**

[![A and B marked on the V04 gripper photograph with a separate equal-force model diagram](media/readme/v04-grip-directions.png)](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04)

A and B mark the visible contacts. R combines two equal projected force vectors in an illustrative model; their physical magnitudes were not measured.

[Open the full V04 observation](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04) · [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html)

## 4. Reading order

1. [Start here / Methods](https://yixumochi.github.io/multicam-assembly/) explains how the video evidence was prepared.
2. [Fifteen assembly cases](https://yixumochi.github.io/multicam-assembly/#overview) shows a video, timeline, and drawings for each case.
3. [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections) helps you find a pair of related operations.
4. [Action Names and Turning](https://yixumochi.github.io/multicam-assembly/action-pair-summary/scatter.html) compares wording with recorded turning.
5. [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html) compares activity areas and footprints. [Compare two cases](https://yixumochi.github.io/multicam-assembly/spatial/compare.html)
6. [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html) shows the masks, grips, and working directions for selected timeline intervals.

## 5. Repository layout

| Location | Contents |
| --- | --- |
| [cases/](cases/README.md) | The 15 case folders with published videos and drawings, plus links to case pages and PDFs. |
| [research-code/](research-code/README.md) | Python workflows with module instructions for research analysis, boards, V01 mask refinement, V21 reconstruction, connector inference and training, and manuscript generation. |
| [examples/](examples/) and [docs/reproduction.md](docs/reproduction.md) | Small verification scripts, links to example inputs, and the instructions and status for each workflow. |
| [index.html](index.html), [action-pair-summary/](action-pair-summary/), [spatial/](spatial/), and [observation/](observation/) | Website source for timelines, action comparisons, space comparisons, and observation boards. Final PDFs are in [observation/boards/](observation/boards/). |
| [video-to-top-view/](video-to-top-view/), [body_five/](body_five/), [media/](media/), [plates/](plates/), [runs/](runs/), and [analysis/](analysis/) | Method walkthroughs, visual evidence, source fragments, and saved analysis used by the site. |

## 6. Reproduction

1. **Serve the website locally.** From the checkout created in [Quick Start](#quick-start), run `python -m http.server 8000` and open `http://localhost:8000/`.
2. **Check the public results.** Run `python examples/verify_published_examples.py` in the checkout. The script recalculates the documented turning example and V22 drawing projection from the released results.
3. **Use the original inputs to rerun a specific workflow.** Follow the commands and expected outputs in the guide.

   | Workflow | Verified run and inputs |
   | --- | --- |
   | Actions and semantics | Local SentenceTransformer handoff and model. Reproduced all 210 historical vectors and 142 semantic groups. |
   | Assembly space | Released pixel positions. Reproduced the V22 drawing projection. Rerunning from source footage requires the original segmentation, tracking, depth, and camera-fitting code and settings. |
   | V04 observation boards | Local core research ZIP and rendering fonts. Regenerated the five retained pages from reviewed frames, masks, and annotations. |

   [Reproduction guide with setup and commands](docs/reproduction.md)
