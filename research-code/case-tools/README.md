# V01 manual mask refinement

`finish_manual_pages.py` builds masks and board overrides for the traced mallet and carried-timber views.

```bash
python finish_manual_pages.py --frames /path/to/v01-frames --masks /path/to/output-masks
```

Supply the original PNG files named `frame-XXXXXX.png` in the frames directory. The script writes mask PNGs to the provided mask directory and review overlays and override JSON to the frames directory. Run with Python 3.10 or later and Pillow.
