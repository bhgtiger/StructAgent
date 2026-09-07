# Mask Theory — Why & How

A mask is a volume on the target map’s grid, with values 1 inside the included region, 0 outside, and a smooth transition for downstream refinement. Hard boundaries create Fourier ringing that can bias alignment and inflate masked FSC. Source checked 2026-09-07: [CryoSPARC Mask Creation](https://guide.cryosparc.com/processing-data/tutorials-and-case-studies/mask-selection-and-generation-in-ucsf-chimera).

## Cosine padding versus Gaussian smoothing

The Guide recommends a starting **cosine-padding width** of at least `5 × GSFSC_resolution / apix` pixels, with empirical tuning. Volume Tools measures this width in **final resampled pixels**. For resolution 3.4 Å and final pixel size 1.06 Å, round up to 17 pixels to meet that recommendation. Dilation adds an interior 1-valued region; padding adds a graded exterior edge.

ChimeraX [volume gaussian](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/volume.html#gaussian) takes **sigma**, the standard deviation, in physical distance units. The scripts pass `--soft` directly to `sDev`. Therefore **`--soft 17` is not equivalent to 17 Å of cosine padding**. Gaussian blur also softens inward and can reduce small regions’ peak values; a narrow structure may no longer have a 1-valued core. The model script’s legacy default of `5 × apix` (or `5 × gsfsc-resolution`) remains an implementation heuristic, not a calibrated Guide conversion. Prefer `--soft 0 --dilation 0` for a base and finish in Volume Tools when following the official recipe.

Likewise, the scripts’ `--dilation` blurs and re-thresholds rather than performing exact spherical morphology; expansion depends on sigma, threshold, and topology. Use Volume Tools’ dilation radius for a controlled radius in pixels.

## Resolution and coverage

The current molmap tutorial uses **16 Å** and recommends **12 Å or coarser**. The older `2 × map resolution` table was a local heuristic, not an upstream rule. A single resolution cutoff cannot guarantee freedom from FSC artifacts: mask topology, threshold, dilation, and edge profile also matter. Prefer a trustworthy model selection; if the model lacks a flexible domain or unbuilt density that belongs in the mask, inspect a map-derived base instead.

## Diagnose the result

- **Too tight:** Tight FSC above Corrected FSC suggests mask-induced correlation; expand or soften and reassess.
- **Too loose:** added solvent or neighboring-domain signal can reduce useful alignment specificity; inspect masks and reconstructions together.
- **Too small:** insufficient alignment signal can produce noise, shells, or edge blobs; enlarge the region or consider the Local Refinement Gaussian prior.
- **Wrong grid:** match dimensions, voxel size, origin, and coordinate frame. Resample to the target grid and verify the saved file.
- **Complement mismatch:** generate region and particle-bounded complement on the same grid. Independent filtering can destroy exact complementarity; inspect coverage and avoid assuming their sum is exactly the full mask.

These checks guide an empirical comparison; tutorial parameters do not certify a mask. The script sidecar establishes execution success, not scientific suitability.
