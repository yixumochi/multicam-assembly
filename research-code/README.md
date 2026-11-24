# MultiCam research code

The website presents assembly case studies and their supporting evidence. This directory contains the processing and reproduction scripts.

| Folder | Entry point |
| --- | --- |
| [Research analysis](research/) | Event context, reviewed comparisons, and semantic spread analysis |
| [Observation boards](boards/) | Assemble case boards from source frames, masks, and directions |
| [V01 manual masks](case-tools/) | Trace the reviewed mallet and held-timber frames |
| [Manuscript builder](paper/) | Generate evidence figures, DOCX, HTML, and a source manifest |
| [V21 reconstruction](v21-rebuild/) | Extract frames, reconstruct the timber form, and check the native Rhino solids |
| [Connector demos](connector/) | Prepare labels, train the detector, and run inference with tracking and assembly-state logic |

See each folder for its inputs, dependencies, and run commands. Source videos, recorded frames, review exports, CAD outputs, private settings, and trained weights are local inputs. Some workflows require Rhino 8 or the original training environment.

[Open the MultiCam website](https://yixumochi.github.io/multicam-assembly/)
