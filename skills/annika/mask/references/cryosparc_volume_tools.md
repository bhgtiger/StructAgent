# CryoSPARC Handoff — Import & Volume Tools

## Import 3D Volumes

| Field | Value |
|---|---|
| `Volume paths` | path to your `mask_base.mrc` (or glob) |
| `Volume type` | `mask` if Option A (fully finalised in ChimeraX) <br> `map` if Option B (will run Volume Tools next) |
| `Pixel size (A)` | only fill if header is missing; our scripts preserve it from the target map |

## Volume Tools — Option B finalisation

Run **Volume Tools** on the imported mask base with `Volume type = map`.

| Parameter | Suggested | Notes |
|---|---|---|
| Type of operation | `threshold` | Produces a finalised mask |
| Threshold for binarizing | `0.5` | Our scripts already output ≈0/1 so 0.5 splits cleanly. For non-binarized molmap output, use ~`0.15` as in the tutorial. |
| Dilation distance for mask in pixels | `3–6` | Empirical. Larger = wider 1-region. Start at 3. |
| Soft padding width for mask in pixels | `round(5 × GSFSC_resolution / apix)` | Hard rule. For a 3 Å map at 1.0 apix → 15 px. Start at this value. |
| Output box size | leave blank | Keep input box |
| Output pixel size | leave blank | Keep input apix |

**Iteration strategy:** keep the same mask base, fork Volume Tools jobs with different `dilation` / `soft padding` combos. Cheap. Then test the resulting masks in a single Local Refinement and keep the one with Tight ≈ Corrected FSC.

## Where the mask plugs in

| Job | Mask role |
|---|---|
| Local Refinement | `Mask` input — defines region to refine |
| Particle Subtraction | `Mask` input — region to **subtract** (so it's the *complementary* mask) |
| 3D Variability Analysis | `Mask` input — restricts analysis to region |
| 3D Classification | optional `Solvent mask` |
| Homogeneous / Non-uniform Refinement | optional `Static mask` — tight masks here easily inflate FSC, be conservative |

## Sanity checks before running expensive jobs

1. Open mask + map together in ChimeraX, contour mask at 0.5. Mask region should match what you expect.
2. Check apix in header: `chimerax --nogui --exit --cmd "open mask.mrc; volume #1 settings"`.
3. Check box size matches the map.
4. After Local Refinement: Tight FSC curve should track Corrected FSC. If Tight runs well above Corrected → mask too tight, dilate or soften more.
