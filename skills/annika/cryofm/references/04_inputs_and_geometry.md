# 04 — Inputs, geometry, normalisation (what the code does to your map)

All statements are read from the pinned code (`sampling_helper.py`, `uncond_sampling.py`, `cond_sampling.py`,
`utils/infer_relion_utils.py`, `core/datasets/transforms/patchify.py`) unless marked [derived] or [live]. The
validated site's fixture run (EMD-11638, [09](09_evidence_and_benchmarks.md)) confirmed the box/pixel/origin behaviour live.

## 1. Accepted inputs

| Input | Rule |
|---|---|
| Maps (`-i`, `-i1`, `-i2`) | extension `.mrc` or `.map` (case-insensitive) → read with `mrcfile.open(path, 'r')` (non-permissive: a short header, missing `MAP` id, bad machine stamp, unknown mode or truncated data raise; NVERSION 0 and other `validate()` complaints are accepted). Anything else (`.map.gz`, `.ccp4`, `.mrcs`, `.hdf`) → `ValueError: Unknown input file type: …`. **Gunzip EMDB downloads first.** |
| RELION external-reconstruct STAR (`*.star`) as `-i1/-i2` | the file RELION writes for `--external_reconstruct` (`data_external_reconstruct_general` with `rlnExtReconsDataReal/Imag/Weight`, `rlnPixelSize`, `rlnParticleDiameter`, …), not a particle STAR. Both halves must be the same type. Use absolute paths (the loader `chdir`s to the data directory). |
| Axis order | MAPC/MAPR/MAPS must be (1,2,3), (3,2,1) or (2,1,3); otherwise `RuntimeError("MRC file axis arrangement not supported!")`. |
| Pixel size | **`voxel_size.x` of `-i1` only**, used for both halves and for the mask. `cfm denoise -i` ignores `-i`'s header pixel size. Only `cfm enhance -i … -i1 … -i2 …` checks that `-i` and `-i1` agree in shape and pixel size (`abs_tol=0.005`). Anisotropic voxels are not detected. |
| Origin | read (ORIGIN + NXSTART·voxel) and **discarded by every caller**; outputs get origin (0,0,0), NXSTART 0 (§7). |
| Shape | all volumes of one run must share a shape (`ValueError: All volumes must have the same shape. Got shapes: …`). EMDB primary maps often differ from their half maps (EMD-12042: 128³ vs 256³; EMD-35143: 130×134×108 vs 206×206×140), so `-i primary -i1 half1 -i2 half2` fails for them; feed a half map (or the half-map average) as `-i`. |
| dtype | whatever the file holds; everything is cast to float32/complex64. |

## 2. Resampling to the model grid

1. Non-cubic boxes are zero-padded to an even cube (`Padding volumes from (…) to (…)` in the log) and cropped back at
   the end. **Odd cubic boxes are not padded and fail** `assert iz % 2 == 0` (bare `AssertionError`): pad to an
   even box yourself (e.g. `relion_image_handler --new_box`), keeping half maps identical.
2. Fourier crop/zero-pad to the even box closest to `N·apix/1.5`; the actual model voxel is ≈1.5 Å, not exactly
   (256³ @ 1.06 Å → 180³ @ 1.5076 Å; 256³ @ 0.5332 Å → 92³ @ 1.484 Å [live]).
3. Normalise: divide by the 99.999th percentile (computed inside the bbox if `--bbox`), then `(x − 0.04)/0.09`.
4. Tile into 64³ patches with overlap 32 (stride 32); offsets per axis `[0, 32, …, S−64]` (the last offset is
   appended if not on the grid). Patches per axis n(S) = ⌈(S−64)/32⌉ + 1; total n³ for a cube.
5. Sample each patch batch; blend overlaps by **plain averaging** (no taper); de-normalise; Fourier-resample back to
   the input box; crop padding; write float32.

Worked sizes (defaults):

| Input box @ apix | model box S | patches | batches at `--batch-size 4` | note |
|---|---|---|---|---|
| 104³ @ 0.96 (EMD-29934) | 66 | 8 | 2 | smallest public held-out fixture |
| 256³ @ 0.5332 (EMD-11638) | 92 | 8 | 2 | validated-site smoke [live]: ≈54 s/batch denoise on A100 |
| 128³ @ 1.0 | 86 | 8 | 2 | |
| 256³ @ 1.029 (EMD-12042) | 176 | 125 | 32 | matches issue #2's `0/32` bar; ≈33 min per half at 63 s/batch |
| 256³ @ 1.5 | 256 | 343 | 86 | |
| 400³ @ 1.0 | 266 | 512 | 128 | |
| 640³ @ 0.832 (EMD-42231 halves) | 354 | 1331 | 333 | hours per half |
| 128³ @ 0.5 | 42 | **fails** | — | resampled box < 64 → `IndexError` in `GridPatches3D` |

`scripts/inspect_map.py` computes S, patches and batches from the header. Rules: S ≥ 64 (box·apix ≳ 96 Å); large boxes
cost ∝ patches; `--mask-path … --bbox` crops to the mask's bounding box (+5 voxels, ≥ 64 per axis) and is how the
paper's "six patches in 44 s" was measured.

## 3. Resolution consequences of the 1.5 Å grid

- Input finer than 1.5 Å/px: Fourier **cropping** discards everything beyond the model Nyquist (3.0 Å) on the axes;
  because the crop is a cube, corners keep content to ≈3.0/√3 ≈ 1.73 Å. On the way back the discarded shells are
  zero-padded. **Default outputs therefore carry no (on-axis) signal beyond ≈3 Å** regardless of the input
  resolution. [live] the 0.53 Å fixture output has whole-spectrum CC 0.30 vs the input but 0.986 after low-passing
  both to 3.5 Å.
- `--spectral-mixing` (MRC path): above the shell of 3.0 Å (minus a 3-shell cosine crossover) the output takes the
  **raw input's** Fourier components inside a soft sphere, i.e. those frequencies are not denoised. Whether that is
  what you want for a 2 Å map is undocumented; say so.
- Input coarser than 1.5 Å/px: Fourier zero-padding (up-sampling); nothing is lost on the way back, but the
  FSC/energy weights are frequency-compressed and the prior was trained on < 3 Å maps.
- STAR path (RELION): a soft radial mask with the particle diameter is applied; with `--spectral-mixing` the RELION
  regularised map is mixed in beyond the FSC = 1/7 index (Blush-style "spectral trailing" unless
  `--skip-spectral-trailing`).

## 4. Half maps and the noise model

- `cfm denoise` samples **each half separately**, but the likelihood weight of both is `1/(1−FSC)/power` from the
  **one unmasked global FSC between the two inputs** (`--mask-path` does not enter the FSC). `non-uniform` adds
  per-band spatial weights from `0.5·(A−B)²`. `--fsc-weighting` filters both outputs by the FSC between the outputs.
  A fixed `--seed` re-seeds every batch, so both halves start from the same noise.
- Consequence: the two outputs are **not independent half maps**; their FSC is not a gold-standard estimate
  ([08](08_outputs_and_validation.md)). [live] the fixture's denoised halves have shell FSC 1.000 → 0.999 to 3 Å, identical to the inputs.
- Which half maps to feed (unfiltered/unmasked/unsharpened vs post-processed) is **undocumented** by upstream. The
  pretraining data were EMDB half maps, which EMDB requires to be unmasked and unfiltered; the EMhancer-style model was
  trained on half-map inputs; the EMReady-style model on deposited (sharpened) maps. State this as context, not as a rule.
- Pixel size of `-i2` is never read; if the halves disagree the run still proceeds with `-i1`'s value.

## 5. Mask (`--mask-path`)

- Loaded with the same reader, resampled with the **input's** pixel size (its own header is ignored), binarised
  `> 0.5`; must be on the input grid (same box, same pixel). Non-cubic masks are **not padded** and fail the cubic
  assert (EMD-35143's 206×206×140 mask would fail; EMD-0560's 200³ mask works).
- Only with `--bbox` does it do anything: sampling is restricted to the mask's bounding box, voxels outside keep the
  unprocessed resampled input. The mask is never applied to the output and never used for the FSC. The docs call it a
  speed-up ("to speed up CryoFM inference"); the paper cropped to the solvent-mask bbox for cost.

## 6. Particle STAR for `--op inpaint` / `denoise inpaint` (`--data-starfile-path`)

- RELION ≥ 3.1-style STAR with `data_optics` (`rlnImagePixelSize`, `rlnImageSize`) and `data_particles`
  (`rlnAngleRot/Tilt/Psi`, `rlnImageName`; `rlnRandomSubset` only matters for STAR half inputs). The first particle
  stack must resolve relative to an ancestor (≤ 9 levels) of the STAR's directory.
- Only poses are used: all-ones central slices are back-projected at the particle orientations (RELION Euler
  convention), summed, and voxels with count ≥ `--fmask-threshold` (10.0, an absolute count) are "observed". All
  particles are used for MRC half maps (no half split). If all angles are 0 the mask becomes a full sphere.
- **The particle box (`rlnImageSize`) must equal the (cubic-padded) half-map box in voxels**, otherwise the FSC/mask
  arrays cannot broadcast (numpy error at `sampling_helper.py:718`) [derived]; the pixel size is assumed equal and unchecked.
- cryoSPARC poses need a STAR bridge (pyem `csparc2star.py`) with the RELION convention; verify with `--debug`
  (writes `<stem>_fmask.mrc`). Back-projection runs on the GPU with batch 256 particles and costs ≈0.65–11.6 GiB for
  boxes 128–512 [derived].
- The RELION wrapper derives the STAR automatically from `run_itNNN_…` → `run_it(NNN−1)_data.star`.

## 7. Output header

`save_mrc(grid, filename, voxel_size=<input voxel_size.x>, origin=[0,0,0])`: float32, `cella = shape × voxel`,
MAPC/MAPR/MAPS 1,2,3, **ORIGIN 0 and NXSTART/NYSTART/NZSTART 0**, `update_header_stats()`. Inputs that carry their
placement in NXSTART (EMDB maps such as EMD-35143: 77,77,110 voxels) or in ORIGIN (ChimeraX-written maps, the
demo's CDN half maps: 63.91, 63.91, 91.30 Å) produce outputs shifted by that vector in ChimeraX/Phenix/cctbx.
Models no longer fit; `phenix.map_model_cc` measures nothing; EMDB requires all volumes to overlay.
**Fix:** `python3 scripts/restore_origin.py REFERENCE_INPUT CRYOFM_OUTPUT REGISTERED_OUTPUT` (copies NSTART and
ORIGIN of the same-grid reference into a new file), or ChimeraX `volume #2 originIndex -i,-j,-k` (negative of the
reference NSTART) then `save …` (`.map` writes NSTART, `.mrc` writes ORIGIN). Do **not** use `volume resample
onGrid` for this: it interpolates through the wrong placement. Reference per output: `-i1` for half-1 and avg,
`-i2` for half-2, `-i` for enhance outputs; RELION-written half maps (origin 0) need nothing.

## 8. Normalisation constants (hard-coded, not in config.yaml)

`MODEL_VOXEL_SIZE = 1.5`, `CRYOEM_DENSITY_MEAN = 0.04`, `CRYOEM_DENSITY_STD = 0.09`, percentile 99.999, `EPS_FSC
= 1e-5`, `BBOX_ENLARGE = 5`, `FMScheduler(1000)` train steps, EMA decay 0.99 (inert at inference). Output intensities
are returned to the input's scale (× percentile). `config.yaml` supplies only `model.*`, `process: fm` and
`z_scale` (null, identity); every other key is training metadata. The HF `config.yaml` files use `!!python/tuple`
tags: PyYAML `safe_load` rejects them, mmengine's full loader (what the code uses) accepts them, which also means
**a tampered `config.yaml` can execute code** — use only the pinned, hash-verified weights folders.
