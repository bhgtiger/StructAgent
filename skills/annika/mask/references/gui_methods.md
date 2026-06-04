# GUI-only Methods — Reference

Documented for completeness. **The mask_skill scripts do not automate these** — they require human interaction with the ChimeraX UI. Use the model-reference (molmap) path instead whenever a model is available.

## Method 1: Segger / Volume Segmentation

Watershed-segment a blurred map, then hide/keep regions to define the mask.

1. `open map.mrc` → `#1`
2. `volume gaussian #1 sDev 2` → `#2`
3. Tools → Volume Data → **Segment Map**. Open Shortcuts Options. Pick `#2`. Click **Segment** → `#3`.
4. Ctrl-click regions to select; click **Hide** to remove from mask. (Ctrl-Shift adds, Ctrl-drag box-selects.)
5. If a region spans wanted/unwanted, Ctrl-click → **Ungroup** → iterate.
6. Select all visible regions → **Group** → File → **Save selected regions to .mrc file** → cropped `#4`.
7. `volume resample #4 onGrid #1` → `#5`
8. `save mask_base.mrc #5`
9. For subtraction mask: `Show regions: All`, Ctrl-click the saved group, Hide → save the rest the same way.

Strengths: handles complex topology. Weaknesses: no undo, fully manual.

## Method 2: Volume Eraser

Sphere-erase regions of a copy of the map.

1. `open map.mrc` → `#1`
2. `volume gaussian #1 sDev 2` → `#2`
3. `volume copy #2` → `#3` (eraser modifies in place)
4. Right Mouse ribbon → **Erase**. Move the sphere (right-click drag), resize, click **Erase outside sphere**.
5. Clean dust with smaller sphere + **Erase inside sphere**.
6. `save erased.mrc #3`
7. Subtraction mask: `volume subtract #2 #3` → save.

Strengths: fast for big simple blobs. Weaknesses: imprecise, leaves dust, no undo.

## Why we don't automate these

Both rely on per-region picking in the 3D view. molmap + threshold/dilation/soft achieves the same end result deterministically when a model is available — which is the case for nearly all our targets.
