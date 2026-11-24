# V21 source-form reconstruction

These scripts rebuild an image-constrained interpretation of the Gradual Assemblies case. The native Rhino file is unitless. The reconstruction supports visual and topological comparison.

Use a separate working copy of this directory. Install the Python dependencies for frame extraction, fitting, report generation, and independent validation. The two RhinoCommon scripts run inside Rhino 8.

1. Extract reference frames from a local copy of the source video with `python extract_sources.py --video /path/to/video.mp4 --out source`.
2. Run `recover_form.py` to fit the paths and `prepare_solids.py` to prepare the slats and joints.
3. Run `build_source_rhino.py` in Rhino 8 to write native closed BReps in `model_run04`. Use a new version directory if files already exist.
4. Run `independent_check.py` in Python and `verify_and_faces_rhino.py` in Rhino 8.
5. Run `make_delivery.py` in Python to make the local HTML report and its images.

The source film, the optional source paper image, generated models, and validation JSONs belong to the local case materials.
