# Mask Theory — Why & How

## What a mask is
A 3D volume, same box & apix as the target map, with values in `[0, 1]`:
- `1.0` inside region of interest
- `0.0` outside
- soft transition in between

## Why soft edges
Alignment happens in Fourier space. A hard 0/1 step in real space → infinitely-ringing sinc in Fourier space → ringing artifacts cross-correlate during alignment → noise gets aligned to noise. Soft edges damp the ringing.

**Minimum recommended soft padding** (CryoSPARC guide):
```
soft_width_Å  ≥  5 × resolution_Å
soft_width_px ≥  5 × resolution_Å / apix
```
For a 3 Å map at 1.0 Å/voxel → ≥ 15 Å ≈ 15 px soft edge.

## Pitfalls

### Too tight
- Mask hugs the structure → introduces high-frequency correlations between half-maps → **Tight FSC > Corrected FSC** by a wide margin → "spuriously good" resolution.
- Tell: in the FSC plot, the *tight* curve runs noticeably above the *corrected* curve.
- Fix: more dilation, more soft padding, or lower molmap resolution.

### Too loose / large soft edge
- Includes noise from outside the region → alignment drifts → effective resolution drops.
- Less catastrophic than too-tight.

### Too small
- Region itself too small for stable alignment → overfitting artifacts ("blips", shells at mask boundary).
- Fix: enlarge region, or use Gaussian prior in Local Refinement.

### Wrong box / origin
- Output mask must have the **exact same box, apix, origin** as the map it will be applied to.
- Always finish the pipeline with `volume resample onGrid #map`.

## molmap resolution ↔ tightness

| `molmap resolution` (Å) | Behaviour |
|---|---|
| ≤ 2× map resolution | **Too tight** — avoid. Will inflate FSC. |
| 2× – 4× map resolution | Tight; OK for well-defined rigid domains. |
| ~16 Å | CryoSPARC tutorial default — safe starter. |
| 20–30 Å | Loose; use for flexible regions or initial passes. |

## Quick math

Given:
- map apix `p` = 1.06 Å
- GSFSC resolution `r` = 3.4 Å
- want soft width ≥ `5r` = 17 Å

Then:
- `--soft 17` in scripts/make_mask_from_model.py
- equivalently in CryoSPARC Volume Tools: `Soft padding width = round(17/1.06)` = `16 px`
- pick `Dilation = 3–6 px` empirically
