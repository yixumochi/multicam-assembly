# MultiCam Assembly

## 1. Project overview

MultiCam studies how people, robots, and timber components coordinate during assembly and how much space their operations occupy. The study compares 15 filmed cases across human-led, human–robot, and robotic assembly. Comparing these modes lets readers examine the roles, movements, and space involved in different ways of assembling timber.

## 2. Cases and evidence

The case records draw on source films, project drawings, and related references. Each case sheet connects a published video, an action timeline, and drawings of the assembled structure. The evidence was prepared in four steps.

1. **Assemble the case records.** Identify the source films and related project material, and link them to the corresponding case.
2. **Index events.** Use Label Studio annotations to connect English action names to intervals in the source films. Retain the event times and representative frames for review.
3. **Prepare comparable evidence.** Use SentenceTransformer vectors to find related action names. Use segmentation, feature tracking, depth, and geometric checks to develop movement evidence and plan views.
4. **Review selected events.** Inspect frames against the source footage. For local observations, draw and align equipment masks and annotate visible contacts and working directions.

[Case index](cases/README.md) · [Methods](https://yixumochi.github.io/multicam-assembly/) · [Video to top view](https://yixumochi.github.io/multicam-assembly/video-to-top-view/technical.html)

## 3. Research outputs

| Research strand | What it shows | Where to see it |
| --- | --- | --- |
| **Actions and movement** | Related action names and the recorded differences in grip, orientation, and turning. Cosine scores describe the wording, while the case frames and drawings show the operations. | [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections) · [Action Names and Turning](https://yixumochi.github.io/multicam-assembly/action-pair-summary/scatter.html) |
| **Assembly space** | The finished footprint, the area used during assembly, and coverage by humans, machines, and parts. The V22 walkthrough shows a shot-local spatial route and schematic placement on a Rhino plan. | [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html) · [V22 walkthrough](https://yixumochi.github.io/multicam-assembly/video-to-top-view/technical.html) |
| **Local assembly observations** | Three frames from a selected event, equipment or tool masks, visible contacts, and working directions. Where a resultant is drawn, the board gives the assumptions for that image-plane model. | [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html) · [V04 example](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04) |

## 4. Reading order

1. Start with **Methods** to see how source footage becomes action and spatial evidence. [Start here / Methods](https://yixumochi.github.io/multicam-assembly/)
2. Open **Fifteen assembly cases** and follow one video, its timeline, and the assembly drawings together. [Case overview](https://yixumochi.github.io/multicam-assembly/#overview) · [V22 case](https://yixumochi.github.io/multicam-assembly/#robotic-assembly/V22)
3. Use **Action Relationships** to select a pair of related actions and open its supporting frames. [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections)
4. Use **Action Names and Turning** to compare name similarity with recorded turning. [Action Names and Turning](https://yixumochi.github.io/multicam-assembly/action-pair-summary/scatter.html)
5. Open **Atlas of Assembly Space** to compare activity areas, footprints, and the roles occupying the space. [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html) · [Compare two cases](https://yixumochi.github.io/multicam-assembly/spatial/compare.html)
6. Finish with **Assembly in Motion** to inspect an individual event. In V04, compare the sample frames, machine masks, and working-direction diagrams. [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html) · [V04 observation 04](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04)

## 5. Repository layout

| Location | Contents |
| --- | --- |
| [cases/](cases/README.md) | The 15 case folders with published videos and drawings, plus links to case pages and PDFs. |
| [research-code/](research-code/README.md) | Python workflows with module instructions for research analysis, boards, V01 mask refinement, V21 reconstruction, connector inference and training, and manuscript generation. |
| [examples/](examples/) and [docs/reproduction.md](docs/reproduction.md) | Small verification scripts, links to example inputs, and the instructions and status for each workflow. |
| [index.html](index.html), [action-pair-summary/](action-pair-summary/), [spatial/](spatial/), and [observation/](observation/) | Website source for timelines, action comparisons, space comparisons, and observation boards. Final PDFs are in [observation/boards/](observation/boards/). |
| [video-to-top-view/](video-to-top-view/), [body_five/](body_five/), [media/](media/), [plates/](plates/), [runs/](runs/), and [analysis/](analysis/) | Method walkthroughs, visual evidence, source fragments, and saved analysis used by the site. |

## 6. Reproduction

1. **Open the published results locally.** Clone the repository, start the HTTP server from its root, and open `http://localhost:8000/`.

   ```sh
   git clone https://github.com/yixumochi/multicam-assembly.git
   cd multicam-assembly
   python -m http.server 8000
   ```

2. **Recalculate the published examples.** From the repository root, run the command below with Python 3.11 or newer. It checks a 24.6° action turn gap and recalculates the V22 drawing projection for 23 saved pixel records.

   ```sh
   python examples/verify_published_examples.py
   ```

3. **Follow the workflow for the result you want to regenerate.**

   | Workflow | Required inputs and verified result |
   | --- | --- |
   | Actions and semantics | The local SentenceTransformer handoff and matching model. The verified local run reproduced 210 historical vectors and 142 semantic groups. |
   | Assembly space | The public example starts with saved pixel positions. For a full run from footage, the original segmentation, tracking, depth, and camera-fitting pipeline and configurations still need to be recovered. |
   | V04 observation boards | The local core research ZIP and the rendering fonts. The verified local run generated the five retained pages from reviewed frames, masks, and annotations. |

   [Input locations, commands, and verification results](docs/reproduction.md)
