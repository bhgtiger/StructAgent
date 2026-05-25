# Topic 20a — Mask Generation in ChimeraX (model → mask base, scriptable)

## Scope and when to use this file vs `20_masks.md`

- Use **`20_masks.md`** for *mask design and validation* questions: what kind of mask, soft-edge math, dynamic vs static, FSC tells, Volume Tools parameters, version notes.
- Use **this file (`20a_mask_generation_chimerax.md`)** for *generating* a mask base off-cryoSPARC, scriptable in headless ChimeraX (`--nogui --exit --script`): model→mask (`molmap`), map-only fallback (Gaussian blur + threshold), and complementary subtraction masks.

These scripts are **file-local** — they read `.mrc`/`.cif`/`.pdb` files on disk and write `.mrc` + a `.json` sidecar. They do **not** touch any cryoSPARC instance. Importing the result into cryoSPARC and any downstream Volume Tools / Local Refinement / Particle Subtraction job still follows the usual cryoSPARC safety confirmation rules in `SKILL.md`.

## Decision: which method?

| Method | Needs GUI? | Input | Best for |
|---|---|---|---|
| **molmap (model-ref)** ← primary | No | Atomic model (PDB/CIF) + target map (for box/apix) | Local refinement on a chain/domain/selection when a model is available |
| Map blur + threshold (fallback) | No | Map only | Crude soft blob when no model exists; flag as low confidence |
| Segger segmentation | **Yes** | Map only | Complex topologies, no model — manual only, not automated here |
| Volume Eraser | **Yes** | Map only | Quick large-region masks — manual only, not automated here |
| Complement mask | No | Existing region + full-volume masks + target map | Pair the kept-region mask with a subtraction mask cleanly |

If a model exists, **prefer molmap**. Segger and Volume Eraser are GUI-only; see "GUI-only methods" at the bottom for documentation and `20_masks.md` for the higher-level workflow rules.

## ChimeraX binary discovery

The scripts run *inside* ChimeraX (`--script`), so they don't hardcode any binary path. The user (or wrapper) decides which ChimeraX to invoke. On macOS the latest installed `ChimeraX.app` can be picked with:

```bash
CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)
```

On Linux, use whatever `chimerax`/`ChimeraX` is on `$PATH`, or pass an explicit path via an environment variable. Do not assume a specific install location.

Requires ChimeraX **≥ 1.8**.

## Quick start — model → mask base

```bash
"$CHIMERAX" --nogui --exit --script skills/cryosparc/scripts/masks/make_mask_from_model.py -- \
  --model /path/to/model.cif \
  --selection "/A:120-340" \
  --target-map /path/to/refined_map.mrc \
  --resolution 16 \
  --out /path/to/mask_base.mrc
```

Output: an `.mrc` on the **same box/apix/origin as the target map**, plus a `<out>.mrc.json` sidecar with `{"ok": bool, "params": ..., "stats": ...}`. The sidecar is the only reliable success signal — **exit code is not reliable for ChimeraX batch runs**.

ChimeraX atomspec selection examples:
- `/A` — chain A
- `/A:120-340` — residues 120–340 of chain A
- `/A,B` — chains A and B
- `/A:120-340,#1/B:50-200` — multi-region
- `#1` — entire model #1
- empty / omit → whole opened model

## Quick start — map → mask base (no-model fallback)

Use only when no atomic model is available. Limited to Gaussian blur + threshold + optional dilation + soft edge. Cannot reproduce Segger or Volume Eraser results.

```bash
"$CHIMERAX" --nogui --exit --script skills/cryosparc/scripts/masks/make_mask_from_map.py -- \
  --map /path/to/map.mrc \
  --sdev 2.0 \
  --threshold 0.05 \
  --soft 4.0 \
  --out /path/to/mask_base.mrc
```

Flag this path as **low-confidence**; recommend manual segmentation cleanup in ChimeraX if the mask shape matters for the science.

## Quick start — complementary subtraction mask

For a Local Refinement on region R, the matched particle-subtraction mask = full − R.

```bash
# 1) make mask_R.mrc with make_mask_from_model.py for selection R
# 2) make mask_full.mrc with make_mask_from_model.py on the whole model
# 3) subtract:
"$CHIMERAX" --nogui --exit --script skills/cryosparc/scripts/masks/make_complement_mask.py -- \
  --full /path/mask_full.mrc \
  --region /path/mask_R.mrc \
  --target-map /path/refined_map.mrc \
  --out /path/mask_subtraction.mrc
```

Result is a soft, clamped, target-grid mask suitable as the `mask` input of cryoSPARC **Particle Subtraction**.

**Input-shape caveat.** `make_complement_mask.py` does `volume subtract → clamp → re-blur`. If both `--full` and `--region` already carry the default ~`5 × apix` soft edge, the subtraction operates on overlapping soft halos and the result is `soft − soft → clamp → soft again` — i.e. an over-blurred / shape-shifted boundary, not a clean `full − region` complement. Either:

- produce `--full` and `--region` as **binary** mask bases (run `make_mask_from_model.py` with `--soft 0`), and let `make_complement_mask.py` add the single soft edge; or
- accept the over-blurred boundary as a workflow trade-off and note it in the QA review (Tight FSC vs Corrected FSC is a sensitive tell for this — see `20_masks.md`).

## What `make_mask_from_model.py` does (pipeline)

Given target map (box `B`, apix `p`) and model:

1. `close all` — model numbering is otherwise non-deterministic across runs.
2. `open <target_map>` → `#1` (used only for the grid).
3. `open <model>` → `#2`.
4. Sanity-check selection: `select <spec>`; if 0 atoms, abort with sidecar `ok=false`.
5. `molmap <selection> <resolution> gridSpacing <p>` → simulated map.
   - **Resolution rule of thumb: 8–20 Å.** 16 Å is the cryoSPARC tutorial default and a safe start.
   - **Never use `--resolution` < ~2× map resolution** — produces over-tight masks that inflate FSC (see `20_masks.md` diagnostics).
6. **Binarize** (default on) using two `volume threshold` calls (each produces a *new* volume):
   - `volume threshold #N minimum <t> set 0` → values `< t` → 0
   - `volume threshold #M maximum 0 setMaximum 1` → values `> 0` → 1
   - Default `t = 0.5 * max(molmap)`. `setMinimum`/`setMinimumFrom` are **not** valid ChimeraX keywords; the script uses `set`.
7. **Dilation** (optional, in Å). ChimeraX has no native morphology op, so the script uses a blur + re-threshold trick:
   - `volume gaussian #N sDev <dilation_A>` (smears the 1-region; σ in Å)
   - re-binarize at `minimum 0.25` to expand by roughly `dilation_A`.
   - Lower the 0.25 cutoff for wider dilation; raise it for narrower.
8. **Soft edge** via `volume gaussian #N sDev <soft_A>`. σ is in **Å**, not voxels.
   - Default: `5 × apix`, or `5 × --gsfsc-resolution` if supplied.
   - This matches the cryoSPARC guide minimum: `soft_width_Å ≥ 5 × resolution_Å`.
9. `volume resample #N onGrid #1` → snap to the target's exact box/origin.
   - **Always finish here** — cryoSPARC rejects mismatched box sizes.
10. `save <out.mrc> #<final>` + write `<out>.json` sidecar.

## Parameters cheat sheet (`make_mask_from_model.py`)

| Flag | Default | Notes |
|---|---|---|
| `--model` | required | PDB or CIF atomic model |
| `--target-map` | required | Defines output box, origin, apix |
| `--out` | required | Output `.mrc` path (sidecar = `<out>.json`) |
| `--selection` | whole model | ChimeraX atomspec (e.g. `/A:120-340`) |
| `--resolution` | 16 | `molmap` resolution in Å. 12 = tight, 20 = loose. |
| `--binarize` / `--no-binarize` | on | Threshold molmap output to 0/1 |
| `--threshold` | `0.5 × max(molmap)` | Only relevant with `--binarize` |
| `--dilation` | 0 | Extra dilation in Å before soft edge (blur + re-threshold) |
| `--soft` | `5 × apix` or `5 × gsfsc-resolution` | Soft padding width in Å. **0 ⇒ no soft edge — almost always wrong** |
| `--gsfsc-resolution` | none | If set and `--soft` not given, soft = `5 × gsfsc-resolution` Å |

## Critical rules (script-level)

1. **Always start with `close all`** so model numbering resets across runs.
2. **Always finish with `volume resample ... onGrid <map>`** before saving.
3. **Never set `--resolution` below ~2× the map's nominal resolution.**
4. **Soft edge is non-optional in production.** Hard masks cause ringing. If you intend to add the soft edge in cryoSPARC Volume Tools, output a hard binarized base from ChimeraX and let Volume Tools handle dilation + padding (Option B below).
5. **Selection sanity check**: the script counts atoms and aborts if 0.
6. **Sidecar is the only success signal.** ChimeraX exit code can be 0 on internal errors. Always check `<out>.mrc.json["ok"]`.
7. **Save to a new filename each run** — ChimeraX caches volumes; reusing names can give silently stale output.

## ChimeraX command notes that bite

Drawn from `scripts/masks/*.py` and the standalone reference:

- `volume threshold` keywords are exactly `minimum`, `set`, `maximum`, `setMaximum`. There is **no** `setMinimum` or `setMinimumFrom`.
- `volume gaussian sDev <σ>` takes σ in **Å**, not voxels.
- `volume resample #X onGrid #target` is required even when the model looks "in frame".
- `molmap … onGrid #1` is allowed but clips when the model lies outside the existing volume's box; `gridSpacing <p>` + later `volume resample` is safer.
- `volume subtract A B minRMS false` can produce negative values; the complement script clamps with `volume threshold ... minimum 0 set 0`.
- `close all` is the only reliable way to reset numbering. `close #N` does not renumber.
- `volume copy #id` is needed before Volume Eraser-style edits (eraser modifies in place).

## CryoSPARC handoff (two options)

### Option A — finalise in ChimeraX
- Run with `--binarize --dilation D --soft S` set to final values.
- **Import 3D Volumes** with `Volume type = mask`.
- Use directly in Local Refinement / Particle Subtraction.

### Option B — produce a "mask base" and finish in Volume Tools (usually simpler)
- Run **without** dilation/soft (or with binarize only).
- **Import 3D Volumes** with `Volume type = map`.
- **Volume Tools**: `Type of operation = threshold`, threshold `0.5` (already 0/1) or ~`0.15` for unbinarized molmap output, `Dilation distance for mask in pixels` = `3–6`, `Soft padding width for mask in pixels` ≈ `round(5 × GSFSC_resolution / apix)` (typically 6–10 px or larger). Leave output box/apix blank.
- Iterate dilation/padding cheaply without re-running ChimeraX.

In either case: confirm `project_uid`, `workspace_uid`, lane, and dry-run vs queue before queueing any cryoSPARC job that consumes the mask. See `SKILL.md` and `13_cryosparc_tools_api.md`.

## Mask roles in cryoSPARC jobs (quick map)

| Job | Mask role |
|---|---|
| Local Refinement | `Mask` input — region to refine |
| Particle Subtraction | `Mask` input — region to **subtract** (use the complementary mask) |
| 3D Variability Analysis | `Mask` input — restricts analysis to the region |
| 3D Classification | optional `Solvent mask` / focus mask |
| Homogeneous / Non-uniform Refinement | optional `Static mask` — tight masks here easily inflate FSC; be conservative |

For deeper rules on choosing tightness, soft padding, and inspecting Tight vs Corrected FSC, see `20_masks.md`.

## Sanity checks before running expensive jobs

1. Open mask + map together in ChimeraX, contour mask at `0.5`. The 1-region should match what you expect.
2. Check apix / box / origin in header: `"$CHIMERAX" --nogui --exit --cmd 'open mask.mrc; volume info #1'` (`volume info` is the canonical metadata dump — `volume #1 settings` is not a documented batch-friendly form).
3. Check box size matches the map.
4. After Local Refinement: Tight FSC should track Corrected FSC. If Tight runs well above Corrected → mask too tight; dilate or soften more.

## GUI-only methods (documented, not automated)

`mask_skill` scripts do not automate these — they require manual interaction with the ChimeraX UI. Use the model-reference (`molmap`) path whenever a model is available.

### Segger / Volume Segmentation
1. `open map.mrc` → `#1`
2. `volume gaussian #1 sDev 2` → `#2`
3. Tools → Volume Data → **Segment Map**, pick `#2`, click **Segment** → `#3`.
4. Ctrl-click regions to select; **Hide** to remove from mask. (Ctrl-Shift adds, Ctrl-drag box-selects.)
5. If a region spans wanted/unwanted, Ctrl-click → **Ungroup** → iterate.
6. Select all visible regions → **Group** → File → **Save selected regions to .mrc** → cropped `#4`.
7. `volume resample #4 onGrid #1` → `#5` → `save mask_base.mrc #5`.
8. For a subtraction mask: `Show regions: All`, Ctrl-click the saved group, **Hide**, save the rest.

Strengths: handles complex topology. Weaknesses: no undo, fully manual.

### Volume Eraser
1. `open map.mrc` → `#1`; `volume gaussian #1 sDev 2` → `#2`.
2. `volume copy #2` → `#3` (eraser modifies in place).
3. Right Mouse ribbon → **Erase**. Position sphere (right-click drag), resize, **Erase outside sphere** to keep the ROI.
4. Clean dust with smaller sphere + **Erase inside sphere**.
5. `save erased.mrc #3`. Subtraction mask: `volume subtract #2 #3` → save.

Strengths: fast for big simple blobs. Weaknesses: imprecise, leaves dust, no undo.

## Diagram

A schematic of the model→mask pipeline is bundled at `assets/mask_skill_overview.svg`.

## Lineage / provenance

This file is synthesised from the standalone `mask_skill` project (`/Users/x_guo/Documents/Annika_projects/mask_skill/`), specifically `SKILL.md`, `references/mask_theory.md`, `references/chimerax_commands.md`, `references/cryosparc_volume_tools.md`, and `references/gui_methods.md`, plus the cryoSPARC-side rules already in `20_masks.md`. The standalone project remains in place as provenance; the runtime copy under this cryoSPARC skill is now the active integrated version.
