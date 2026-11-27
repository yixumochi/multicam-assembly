# MultiCam Assembly

MultiCam documents 15 timber assembly cases through video, action timelines, spatial comparisons, and annotated frames.

**[Open the project website](https://yixumochi.github.io/multicam-assembly/)** · **[Browse the 15 cases](cases/README.md)** · **[Browse the research code](research-code/README.md)**

## Use the website

- [Start here / Methods](https://yixumochi.github.io/multicam-assembly/) introduces the study and its evidence.
- [Fifteen assembly cases](https://yixumochi.github.io/multicam-assembly/#overview) opens the case overview. Each case page brings together its video, drawings, and timeline.
- [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections) and [Action Pair Summary](https://yixumochi.github.io/multicam-assembly/action-pair-summary/scatter.html) compare actions across cases.
- [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html) compares assembly footprints and layouts.
- [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html) presents annotated masks and working directions, with 13 case PDFs.

## Find files in this repository

| Location | Contents |
| --- | --- |
| [`cases/`](cases/README.md) | One folder per case, with a combined video in `01_video/` and drawing images in `04_drawings/`. The case index links to the interactive pages and available PDFs. |
| [`research-code/`](research-code/README.md) | Python source, dependency files, and instructions for the research workflows. |
| [`observation/`](observation/) and [`spatial/`](spatial/) | Website source for Assembly in Motion and the Atlas of Assembly Space. Final observation PDFs are in [`observation/boards/`](observation/boards/). |
| [`index.html`](index.html), [`action-pair-summary/`](action-pair-summary/), [`body_five/`](body_five/), and [`video-to-top-view/`](video-to-top-view/) | Website source for the main interface, action comparisons, body motion, and video-to-plan views. |
| [`media/`](media/), [`plates/`](plates/), [`runs/`](runs/), and [`analysis/`](analysis/) | Shared media, evidence images, and analysis outputs used by the website. |

## Work with the research code

| Workflow | Start here |
| --- | --- |
| Analyze events, action relationships, and semantic spread | [Research analysis](research-code/research/README.md) |
| Generate annotated PDF boards from reviewed frames and masks | [Observation boards](research-code/boards/README.md) |
| Refine V01 mallet and timber masks | [V01 case tools](research-code/case-tools/README.md) |
| Build manuscript figures and documents | [Paper builder](research-code/paper/README.md) |
| Reconstruct the V21 timber form and check its Rhino solids | [V21 reconstruction](research-code/v21-rebuild/README.md) |
| Prepare labels, train the detector, or run connector inference | [Connector workflow](research-code/connector/README.md) |

To check out the research code without downloading all the case media:

```sh
git clone --filter=blob:none --sparse https://github.com/yixumochi/multicam-assembly.git
cd multicam-assembly
git sparse-checkout set research-code
```

Open the README for the workflow you want to run. It lists the required inputs, dependencies, and commands. Full reruns use local source videos, reviewed annotations, masks, model weights, or CAD files as specified by each workflow. The published website and PDFs can be viewed directly in a browser.
