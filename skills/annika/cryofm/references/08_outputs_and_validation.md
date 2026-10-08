# 08 — Outputs, what they are and are not, validation

## 1. Files

| Run | Files in `-o` | Content |
|---|---|---|
| `cfm denoise -i1 A -i2 B` | `<stem A>_external_reconstruct.mrc`, `<stem B>_external_reconstruct.mrc`, `avg_external_reconstruct.mrc` | posterior sample of each half (shared noise model); their mean |
| `cfm denoise -i F -i1 A -i2 B` | `<stem A>_external_reconstruct.mrc` (named after A!) | posterior sample of F |
| `cfm enhance -i F` | `<stem F>_external_reconstruct.mrc` | style sample (no data term) |
| `cfm enhance -i1 A -i2 B` | as denoise (3 files) | conditional posterior per half; mean |
| `cfm enhance -i F -i1 A -i2 B` | `<stem F>_external_reconstruct.mrc` | conditional posterior of F |
| RELION wrapper | `<root>_external_reconstruct.mrc` per half in the job dir (no avg) | FPS result RELION reads back |
| `--debug` | `<stem>_fsc.png`, `<stem>_fmask.mrc`, `<stem>_fmask_patch.mrc`, `<stem>_input_patch_NNN.mrc`, `<stem>_output_patch_NNN.mrc`, `<stem>_fscvol.mrc`, `<stem>_energy.mrc`, `<stem>_debug_recons_unfil.mrc`, `<stem>_debug_denoise_input.mrc`, `<stem>_debug_denoise_output.mrc` | diagnostics (model-grid files at 1.5 Å) |
| `--log-file-path` | your path | the console log without colour codes; no log file otherwise |

The log prints `Output to file <path>` per half (not for the average). Existing files are overwritten; the
directory is created with `exist_ok`. Two inputs with the same stem collide.

## 2. Header of every output

float32, box = input box (padding cropped), `cella = box × voxel_size.x of -i1` (or `-i` for enhance), MAPC/MAPR/MAPS
1,2,3, **ORIGIN (0,0,0), NXSTART/NYSTART/NZSTART 0**, mrcfile defaults otherwise, header stats updated. Intensity
scale ≈ the input's (percentile normalisation inverted). Consequences and the fix: [04 §7](04_inputs_and_geometry.md).
`scripts/check_cfm_output.py` compares each output header with the input and warns when the input had a non-zero
placement; `scripts/restore_origin.py` fixes it into a new file.

## 3. What the outputs are NOT

- **Not independent half maps.** Each output was sampled with the FSC of both inputs (and, with `non-uniform`, the
  shared difference map; with `--fsc-weighting`, the FSC of the outputs; with a fixed `--seed`, the same initial
  noise). The FSC between the two outputs is inflated and is **not a gold-standard resolution estimate** (the paper
  says so for shared priors in general; the validated site's fixture shows output-half FSC identical to the input FSC).
  Do not feed them to `relion_postprocess`/cryoSPARC as half maps for a resolution claim.
- **Not full-resolution.** Without `--spectral-mixing`, nothing (on-axis) beyond ≈3.0 Å survives, whatever the input
  pixel size. With it, the raw input is pasted back above 3 Å (not denoised).
- **Not in the input frame** when the input had a non-zero NSTART/ORIGIN (§2).
- **Not deterministic** for `cfm enhance` (no seeding); `cfm denoise` is reproducible only with `--seed`.
- **Not deposition-grade half maps or primary maps.** EMDB requires raw/half maps "with no filtering or masking
  operations applied to them after the 3D refinement protocol" and all volumes to overlay; CryoFM2 outputs are
  processed maps by construction (they belong, if anywhere, under "Other EM maps"). Upstream gives no deposition advice.
- **Not evidence of correctness.** The paper claims no hallucinated features but reports no dedicated hallucination
  test; the card asks users to "Validate generated structures through experimental verification".

## 4. How to validate (what the authors did, and what is honest)

1. **Look.** Set the contour by hand (issue #2: ChimeraX's auto level made a denoised map look like a solid cube).
   Compare input vs output at matching thresholds; check that side chains/bases appear where the input hinted at them,
   and that nothing new appears in solvent or in low-SNR periphery.
2. **Map-model metrics against the deposited/independent model** (Phenix `map_model_fsc`, real-space CC_mask /
   CC_box / CC_peaks; the paper used map-model FSC @0.5 and these CCs). Restore the origin first or the numbers are
   meaningless. Use the same mask for input and output.
3. **Half-map metrics with care**: GS-FSC, 3DFSC/sphericity, FSO and Bingham on CryoFM2 outputs are inflated by the
   shared prior (the paper found half-map anisotropy metrics favouring other methods while map-model metrics favoured
   CryoFM). Report them only with that caveat, and never as the resolution of the deposition.
4. **Negative controls** when the result matters: run the same command on phase-randomised or noise-substituted
   halves (nothing should sharpen), compare with and without the data term (`cfm enhance -i` vs `-i1/-i2`), and
   repeat with another `--seed` to see run-to-run variation.
5. **Fairness in comparisons** (ARCHER's rule): restore every arm or none; do not compare a CryoFM2-processed map
   with an unprocessed competitor map.
6. **Record** command, image/weights identity, seed, and the validation numbers; name the output as a processed map in
   any figure or deposition.

## 5. Smoke numbers from the validated site (A100 40 GB; reference points, not quality metrics)

EMD-11638 (apoferritin 1.22 Å, 256³ @ 0.5332 Å → 92³ at 1.484 Å, 8 patches), A100-SXM4-40GB, batch 4, bf16, seed 0:

| Output | wall | CC vs input (whole spectrum) | CC @ 3.5 Å / 6 Å low-pass | min / max |
|---|---|---|---|---|
| `denoise` avg (and both halves) | 251 s for both halves | 0.30 | 0.986 / 0.997 (0.991 in the molecule mask) | −0.024 / 0.042 |
| `emhancer` (tag 1, CFG 2.0) | 121 s | 0.31 | 0.952 / 0.796 (0.970 masked) | −0.106 / 0.138 |
| `emready` (tag 0, CFG 0.5) | 119 s | 0.20 | 0.705 / 0.806 (0.767 masked) | −0.012 / 0.086 |
| axis-permuted control | — | — | 0.34–0.42 | — |

Input half-map average vs input: 0.993 / 0.999. Denoised-half FSC per shell = input-half FSC (1.000 → 0.999 at 3 Å).
The low whole-spectrum CC is the 3 Å band limit on a 0.53 Å map, not a defect. Peak GPU memory 21 443 MiB.
