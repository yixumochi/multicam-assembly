# MultiCam Assembly

How do people, robots, and timber components coordinate during assembly, and what space do their operations occupy? MultiCam studies these questions across 15 video-based case records, grouped into human-led, human–robot, and robotic assembly. The website brings each case's video, timelines, drawings, and movement evidence together.

[Open the project website](https://yixumochi.github.io/multicam-assembly/) · [Browse the 15 cases](cases/README.md) · [Reproduce the examples](docs/reproduction.md)

## What the project did

1. **Build comparable case records.** Source films and project material were organized into case sheets. Label Studio annotations connect English action names to intervals in the source footage. The timelines link those intervals to the available visual evidence.
2. **Compare named actions with observed movement.** Stored SentenceTransformer vectors and cosine scores help find related actions across cases. The paired drawings and frames let readers compare grip, orientation, and turning in the recorded views. The comparison of “Hold timber at joint” and “Position timber at joint” is one example. [Action Relationships](https://yixumochi.github.io/multicam-assembly/#action-connections) · [Action Names and Turning](https://yixumochi.github.io/multicam-assembly/action-pair-summary/scatter.html)
3. **Compare assembly space.** Segmentation, feature tracking, depth, and geometric checks inform plan representations. The atlas compares finished footprints with activity areas and the coverage of humans, machines, and parts. V22 S01 documents both a shot-local spatial route and a schematic placement on a Rhino workshop plan. [Atlas of Assembly Space](https://yixumochi.github.io/multicam-assembly/spatial/index.html) · [Video to top view](https://yixumochi.github.io/multicam-assembly/video-to-top-view/technical.html)
4. **Inspect selected interactions.** Assembly in Motion links selected timeline intervals to three-frame equipment masks, contact locations, and working directions. The angles are image-plane annotations. Where a resultant appears, it follows the assumptions stated on the board. [Assembly in Motion](https://yixumochi.github.io/multicam-assembly/observation/index.html) · [V04 example](https://yixumochi.github.io/multicam-assembly/observation/index.html#V04/04)

## Read the project

Start with the methods and one complete case. V22 connects a case timeline to the documented spatial workflow. Then explore related action names, compare their recorded motion, compare space across cases, and use Assembly in Motion to inspect a particular operation. [Start here / Methods](https://yixumochi.github.io/multicam-assembly/) · [V22 case record](https://yixumochi.github.io/multicam-assembly/#robotic-assembly/V22) · [Compare two cases](https://yixumochi.github.io/multicam-assembly/spatial/compare.html)

## Find files

| Location | Contents |
| --- | --- |
| [cases/](cases/README.md) | The 15 case folders with published videos and drawings, plus links to case pages and PDFs. |
| [research-code/](research-code/README.md) | Python workflows with module instructions for research analysis, boards, V01 mask refinement, V21 reconstruction, connector inference and training, and manuscript generation. |
| [examples/](examples/) and [docs/reproduction.md](docs/reproduction.md) | Small verification scripts, released example inputs, and the instructions and status for each workflow. |
| [index.html](index.html), [action-pair-summary/](action-pair-summary/), [spatial/](spatial/), and [observation/](observation/) | Website source for timelines, action comparisons, space comparisons, and observation boards. Final PDFs are in [observation/boards/](observation/boards/). |
| [video-to-top-view/](video-to-top-view/), [body_five/](body_five/), [media/](media/), [plates/](plates/), [runs/](runs/), and [analysis/](analysis/) | Method walkthroughs, visual evidence, source fragments, and saved analysis used by the site. |

## Reproduce results

With Python 3.11 or newer, run the public example from the repository root.

```sh
python examples/verify_published_examples.py
```

It recomputes the turning gap for one action pair and one V22 drawing calculation from the published data. To browse the published site locally, run `python -m http.server 8000` at the repository root and open `http://localhost:8000/`.

The reproduction guide lists the local inputs needed to regenerate the five retained V04 boards and the conditions for replaying the historical analysis. It also records the remaining dependencies for regenerating spatial tracks from the original footage. [Reproduction guide](docs/reproduction.md)
