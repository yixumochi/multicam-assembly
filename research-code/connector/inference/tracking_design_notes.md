# Tracking design notes

## Corrections to the initial pseudo-code
- Ultralytics BYTETracker returns `[x1, y1, x2, y2, track_id, score, cls, detection_index]`; score and cls must not be swapped.
- `match_thresh` is a maximum matching cost, approximately `1 - IoU`, not a literal IoU requirement. Setting it to 0.90 can allow very weak matches, so this demo starts at 0.75.
- Standard BYTETracker associates by IoU and stores class labels but does not class-gate its association. The demo therefore maintains one tracker per class.

## Starting thresholds
- YOLO detection confidence: 0.12 (keeps candidate boxes for the second ByteTrack association)
- track_high_thresh: 0.35
- track_low_thresh: 0.12
- new_track_thresh: 0.50
- match_thresh (cost): 0.75
- track_buffer: 40 frames

## Required validation on the six videos
1. Review 30–60 seconds from each camera view.
2. Count ID switches for female and male separately.
3. Verify that the yellow pair arrow stays on the physical connector pair.
4. Check FSM transitions against the actual assemble/disassemble moments.
5. Tune thresholds per camera only after inspecting the generated CSV and annotated MP4.

The exported distance and angle are image-plane values, useful for a visual-guidance demo. They are not calibrated robot millimetres or 3-D pose.
