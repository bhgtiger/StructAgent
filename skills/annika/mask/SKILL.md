---
name: mask
description: "Generate cryo-EM mask bases (.mrc) from atomic models or maps using ChimeraX --nogui batch jobs. Primary path is model-reference based (molmap → optional binarize/dilate → soft edge → resample onto target box). Output is a CryoSPARC-ready mask base; recommended Volume Tools parameters are included for the final binarize/dilate/pad step. Use when the user asks to make a local-refinement mask, particle-subtraction mask, or domain/chain mask from a PDB/CIF model."
---

# Mask Skill — Model-reference Mask Bases for CryoSPARC

Headless ChimeraX (≥1.8, macOS) pipeline for generating mask bases. Focus: **model-reference (molmap) workflow**, fully scriptable without a GUI. Volume-segmentation (Segger) and Volume Eraser methods require a GUI and are documented in `references/gui_methods.md` for completeness only.

Designed to plug into the `chimerax` skill later — uses the same `--nogui --exit --script` invocation pattern.

## When to use which method

| Method | Needs GUI? | Input | Best for |
|---|---|---|---|
| **molmap (model-ref)** ← primary | **No** | Atomic model (PDB/CIF) + target map (for box/apix) | Local refinement on a chain/domain/selection when you have a model |
| volume eraser | Yes | Map only | Quick large-region masks, no model available |
| Segger segmentation | Yes | Map only | Complex topologies, no model available |

If the user has an atomic model, **always prefer molmap**.

## Binary discovery

```bash
CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)
```

## Quick start — model → mask base

```bash
"$CHIMERAX" --nogui --exit --script scripts/make_mask_from_model.py -- \
  --model /path/to/model.cif \
  --selection "/A:120-340" \
  --target-map /path/to/refined_map.mrc \
  --resolution 16 \
  --out /path/to/mask_base.mrc
```

Outputs a `.mrc` with the **same box and pixel size as the target map**, ready for CryoSPARC `Import 3D Volumes`.

Common selection specs (ChimeraX atomspec):
- `/A` — chain A
- `/A:120-340` — residues 120–340 of chain A
- `/A,B` — chains A and B
- `/A:120-340,#1/B:50-200` — multi-region
- `#1` — entire model #1
- empty / omit → whole opened model

## Quick start — map → mask base (GUI-free fallback when no model)

Limited to Gaussian-blur + threshold + optional soft edge. No segmentation, no manual erasing.

```bash
"$CHIMERAX" --nogui --exit --script scripts/make_mask_from_map.py -- \
  --map /path/to/map.mrc \
  --sdev 2.0 \
  --threshold 0.05 \
  --soft 4.0 \
  --out /path/to/mask_base.mrc
```

## Pipeline (model-reference, what the script does)

Given target map (box B, apix p) and model:

1. `close all`
2. `open <target_map>` → `#1`  *(used only for grid)*
3. `open <model>` → `#2`
4. `molmap <selection> <resolution> gridSpacing <p>` → simulated map `#3`
   - **Resolution rule of thumb: 8–20 Å.** Lower = tighter mask. 16 Å is the cryoSPARC tutorial default and a safe start. Never use ≤ 2× map resolution (too tight ⇒ FSC inflation, see `references/mask_theory.md`).
5. *(optional, default on)* binarize at threshold `t` via **two** `volume threshold` calls (each produces a new volume):
   - `volume threshold #3 minimum <t> set 0` → values < t become 0
   - `volume threshold #4 maximum 0 setMaximum 1` → values > 0 become 1

   Default threshold `0.5 * max(#3)`. Note: `setMinimum` / `setMinimumFrom` are **not** real ChimeraX keywords — use `set`.
6. *(optional)* dilation by ~`dilation_A` Å — ChimeraX has **no native morphology op**, so use a blur + re-threshold trick:
   - `volume gaussian #N sDev <dilation_A>` (smears the 1-region outward; σ is in Å)
   - `volume threshold #N+1 minimum 0.25 set 0` then `volume threshold #N+2 maximum 0 setMaximum 1` (re-binarize)

   Lower the 0.25 cutoff for wider dilation, raise it for narrower.
7. *(optional)* soft edge: `volume gaussian #N sDev <soft_A>` — σ is in **Å**, not voxels.
   - Recommended **minimum soft padding width** (CryoSPARC guide): `5 × resolution_Å` (≈ `5 × resolution_Å / apix_Å` voxels)
8. `volume resample #N onGrid #1` → snap to target map's exact box/origin
9. `save <out.mrc> #<final>`

Result: a soft-edged, model-shaped mask in the original map's coordinate frame.

## Parameters cheat sheet

| Flag | Default | Notes |
|---|---|---|
| `--resolution` | 16 | molmap resolution (Å). Try 12 for tight, 20 for loose. |
| `--binarize/--no-binarize` | on | Threshold molmap output to 0/1 |
| `--threshold` | auto = 0.5·max | Only relevant with `--binarize` |
| `--dilation` | 0 | Extra dilation in Å before soft edge |
| `--soft` | `5 * apix`, or `5 * gsfsc-resolution` if `--gsfsc-resolution` is given | Soft padding width in Å. **0 ⇒ no soft edge — almost always wrong.** |
| `--target-map` | required | Defines output box, origin, apix |
| `--selection` | whole model | ChimeraX atomspec |

## Critical rules

1. **Always start with `close all`** — model numbering is reset.
2. **Always finish with `volume resample ... onGrid <map>`** before saving. CryoSPARC rejects mismatched box sizes.
3. **Never set `--resolution` below ~2× the map's nominal resolution** — produces over-tight masks that inflate FSC.
4. **Soft edge is non-optional in production**. Hard masks cause ringing artifacts. CryoSPARC's Volume Tools can also add the soft edge — if you plan to use Volume Tools, you can output a hard binarized mask base from here and let Volume Tools handle dilation + padding (often simpler — see Suggested handoff below).
5. **Selection sanity check**: print residue count from `select` before molmap. If it returns 0 atoms, the script aborts.
6. **Result file is the only success signal.** Exit code 0 is not reliable for ChimeraX. Scripts here write `<out>.json` sidecar with `{"ok": true, ...}`.
7. **Save to a new filename each run** — ChimeraX caches volumes.

## Suggested CryoSPARC handoff

You have two options. **Option B is usually simpler** because it offloads soft-edge tuning to CryoSPARC where you can iterate cheaply.

### Option A — mask is finalised in ChimeraX
- Run with `--binarize --dilation D --soft S` set to final values.
- Import via `Import 3D Volumes`, type = `mask`.
- Use directly in Local Refinement / Particle Subtraction.

### Option B — produce a "mask base" and let Volume Tools finish it
- Run **without** dilation/soft (or with binarize only).
- Import via `Import 3D Volumes` as a regular volume.
- Run **Volume Tools** job with:
  - `Type of operation`: `threshold`
  - `Threshold for binarizing`: `0.5` (since our output is already 0/1) — or whatever splits your bell
  - `Dilation distance for mask in pixels`: typically `3–6 px`
  - `Soft padding width for mask in pixels`: typically `round(5 × GSFSC_resolution / apix)` — start with `6–10 px`
  - Leave `Output box size` blank to keep input box.
- Iterate dilation/padding combinations cheaply without re-running ChimeraX.

### Importing to CryoSPARC

1. Project workspace → **Import 3D Volumes**.
2. Set `Volume paths` to the `.mrc` (or directory glob).
3. Set `Volume type`: `mask` (Option A) or `map` (Option B then run Volume Tools).
4. Set `Pixel size (A)` if the header is missing it (our scripts preserve it from the target map).

## Complementary mask for Particle Subtraction

For a Local Refinement on region R, the particle-subtraction mask = everything **except** R.

```bash
# 1) make region mask R as above → mask_R.mrc
# 2) make full-volume "shell" mask: molmap of whole model at same resolution → mask_full.mrc
# 3) subtract (ChimeraX):
"$CHIMERAX" --nogui --exit --script scripts/make_complement_mask.py -- \
  --full /path/mask_full.mrc \
  --region /path/mask_R.mrc \
  --target-map /path/refined_map.mrc \
  --out /path/mask_subtraction.mrc
```

This gives you the matched complementary pair the CryoSPARC tutorial recommends.

## Files in this skill

```
mask/
  SKILL.md                          ← you are here
  scripts/
    make_mask_from_model.py         ← primary: molmap → mask base
    make_mask_from_map.py           ← fallback: blur + threshold (no model)
    make_complement_mask.py         ← region mask → complementary subtraction mask
  references/
    mask_theory.md                  ← soft edge math, pitfalls, FSC tells
    cryosparc_volume_tools.md       ← Import 3D Volumes + Volume Tools parameters
    chimerax_commands.md            ← volume gaussian/resample/threshold/morphology/molmap reference
    gui_methods.md                  ← Segger + Volume Eraser walkthroughs (GUI-only, for reference)
```

## Lineage

Built on the CryoSPARC mask-creation guide and the "Three Techniques for Mask Creation" ChimeraX tutorial. Aligns with the existing `chimerax` skill so it can be merged later as a sub-module.
