# 07 — RELION `--external_reconstruct` integration, cryoSeed, cryoSPARC bridge

Status: **static reading** of `relion/relion_wrapper.py` (pinned commit) and RELION source (tags 3.0.8 → 5.1.1),
plus the paper. **Never run end to end anywhere in this project** (no RELION on the validated site). One live observation:
calling the wrapper by hand without a STAR on a GPU-less node loops forever (lessons.md). Treat every "fails" below as
a static prediction to confirm on a real RELION host.

## 1. Documented recipe (upstream quick-start, "Use in RELION")

```bash
# template — not run (upstream form; a form with a site launcher in templates/relion_external_reconstruct.sh)
export NCCL_DEBUG=ERROR
export CRYOFM_MODEL_DIR=/path/to/cryofm-v2/cryofm2-pretrain
export RELION_EXTERNAL_RECONSTRUCT_EXECUTABLE="/path/to/conda/envs/cryofm/bin/python /path/to/cryofm/relion/relion_wrapper.py \
  --mask-path ${MASK_MAP_PATH} --bbox --op denoise inpaint --fmask-threshold 10 --threshold-res 10 \
  --norm-grad --use-lamb-w --skip-spectral-trailing --spectral-mixing"
cd ${EXP_DIR}
mpirun relion_refine_mpi --o Refine3D_cryofm2/job001/run --auto_refine --split_random_halves \
  --i particles.star --ref ${REF_MAP_PATH} ... --external_reconstruct |& tee Refine3D_cryofm2/job001/console_log.txt
```

Corrections to the docs text: `--threshold-res 10` is inert; the bullet "`--num_processes`: Number of GPUs" is
stale (the wrapper discards it); `--bf16` is missing although the docs recommend it elsewhere; no RELION version is
stated but **RELION ≥ 4.0.1** is required by code. The string is passed to `system()`, so shell syntax is interpreted
and relative paths resolve against RELION's project directory.

## 2. Protocol (what RELION does, what the wrapper does)

1. In every iteration RELION writes, per half, `<root>_external_reconstruct_{data_real,data_imag,weight}.mrc` and
   `<root>_external_reconstruct.star` (`<root>` = `run_itNNN_half1_class001`), then runs
   `"$RELION_EXTERNAL_RECONSTRUCT_EXECUTABLE" <root>_external_reconstruct.star` and reads back
   `<root>_external_reconstruct.mrc` (`rlnExtReconsResult`). A non-zero exit is fatal (`ERROR: there was something
   wrong with system call`). The STAR carries `rlnTau2FudgeFactor`, `rlnOriginalImageSize`, `rlnCurrentImageSize`,
   `rlnPaddingFactor`, `rlnPixelSize`, `rlnParticleDiameter` and the tau2/FSC table.
2. The wrapper (started without `LOCAL_RANK`/`RANK`) relaunches itself: `accelerate launch --main_process_port
   <port> relion_wrapper.py <args>` with **all visible GPUs** (accelerate default = `torch.cuda.device_count()` or
   the user's `accelerate` config). `--num_processes` in the string is dropped. Ports: half1 `CRYOFM_HALF1_PORT`
   (29500), half2 `CRYOFM_HALF2_PORT` (29501).
3. Inside: the STAR must be the **last** argument; `--model-dir` or `CRYOFM_MODEL_DIR`; all other `cfm denoise`
   flags are parsed with the same argparse (`-i/-i1/-i2` are ignored). `--data-starfile-path` defaults to
   `run_it(NNN−1)_data.star` derived from the result path (needs RELION's default `--o …/run` naming; `inpaint`
   without a resolvable particle STAR fails).
4. **Only the half1 call does the work.** It locates the half2 STAR by name, takes `<half2 star>.processing.lock`,
   reconstructs both halves from RELION's Fourier data/weights (unregularised `recons_unfil` is what gets sampled),
   runs FPS on both with the shared FSC, and writes both `<root>_external_reconstruct.mrc`. The half2 call waits up
   to 30 s for the lock to appear, then waits (unbounded) for its release and exits 0. The lock file stays in the job dir.
5. Post-processing on the STAR path: soft radial mask with `rlnParticleDiameter`; with `--spectral-mixing` RELION's
   regularised map is mixed in beyond the FSC = 1/7 index, with Blush-style spectral trailing unless
   `--skip-spectral-trailing`.
6. Every iteration costs two FPS runs on the half-map boxes (crop to the solvent-mask bbox with `--mask-path …
   --bbox` to keep it to a few patches: the paper's 44 s / six patches figure is exactly this).

## 3. Hazards (static; CONFLICT lines from the evidence)

| # | Hazard | Consequence | Mitigation |
|---|---|---|---|
| C-1 | **Final joined iteration**: after convergence RELION makes one more external call without `half1/half2` in the name (`run_itNNN_class001_external_reconstruct.star`). The wrapper raises `ValueError("Starfile path must contain 'half1' or 'half2'. Got: …")`. | the documented workflow aborts at the last iteration by static reading (the paper says FPS was simply not applied there) | the half maps of the previous iteration are the converged result; or patch the wrapper to route half-less STARs to RELION's own reconstruction / `refine_final` (not public) |
| C-2 | `--num_processes` ignored; all visible GPUs used | memory per GPU unchanged; RELION's own GPU processes compete | `CUDA_VISIBLE_DEVICES` / accelerate config; `--batch-size 2` on 16–24 GB cards |
| C-4 | paper's 10 Å low-resolution retention (`keep_lowres`) is unusable | less low-frequency anchoring than the paper | none; do not add `keep_lowres` |
| C-5 | docs string skips spectral trailing and does not apply `--fsc-weighting`; the paper says outputs were FSC-filtered | FSC-based filtering differs from the paper; RELION warns the Blush analogue "may inflate resolution estimates" | consider dropping `--skip-spectral-trailing`; report what you used |
| C-6 | RELION < 4.0.1 lacks `rlnPixelSize`/`rlnParticleDiameter` in the STAR → `KeyError` | 3.1.x / 4.0.0 cannot work | RELION ≥ 4.0.1 (5.0/5.1 tested in source only) |
| — | RELION 4.0.1 `--continue` keeps `rlnDoExternalReconstruct`; from 4.0.2 the flag must be given again on the continue command line | a continuation without `--external_reconstruct` silently reverts to RELION's reconstruction | re-export the env var and re-pass the flag when continuing |
| — | `--sequential_halves_recons` makes half1 run before the half2 STAR exists → `FileNotFoundError` | job aborts | keep the default parallel halves |
| — | Class3D / InitialModel / MultiBody / non-MPI `relion_refine` / `relion_reconstruct --external_reconstruct` | no half tag → `ValueError`; `classification` mode → `NotImplementedError` | Refine3D with `--split_random_halves` only |
| — | `--blush` together with `--external_reconstruct` | Blush runs, CryoFM2 is never called (silent) | drop `--blush` |
| — | two CryoFM-RELION jobs on one host | both halves default to ports 29500/29501 → `EADDRINUSE` | set `CRYOFM_HALF1_PORT`/`CRYOFM_HALF2_PORT` per job |
| — | shared prior for both halves | half-map FSC inflation; the paper itself warns about it | judge by map-model FSC/CC and visual quality, not GS-FSC |
| — | `--fsc-weighting` with > 1 GPU | barrier called only on rank 0 → possible hang [derived] | avoid |
| — | lock on a filesystem without cross-node `flock` and halves on different nodes | half2 may exit early | both halves on one node (default MPI layout) |

## 4. Form with a site launcher (NOT RUN; no RELION on the validated site)

```bash
# template — not run
<site activation, e.g. source /abs/path/activate.sh>
export CRYOFM_MODEL_DIR=/abs/cryofm-v2/cryofm2-pretrain   # or a shorthand such as `pretrain` where the site launcher resolves it
export CRYOFM_HALF1_PORT=29500 CRYOFM_HALF2_PORT=29501 NCCL_DEBUG=ERROR
export RELION_EXTERNAL_RECONSTRUCT_EXECUTABLE="/abs/path/cfm-relion --mask-path /abs/solvent_mask.mrc --bbox \
  --op denoise inpaint --fmask-threshold 10 --norm-grad --use-lamb-w --bf16 --batch-size 4 --spectral-mixing"
```

On the validated site `cfm-relion` is the launcher's alias for `python /opt/cryofm/relion/relion_wrapper.py` inside the
container with `--nv` on a GPU node; without such a wrapper write `"/abs/env/bin/python /abs/cryofm/relion/relion_wrapper.py …"`
in its place (§1). RELION itself would have to run on the same GPU node(s). Full template with checks:
[templates/relion_external_reconstruct.sh](../templates/relion_external_reconstruct.sh).

## 5. Offline replay of RELION iterations


```bash
# template — not run
cfm denoise -i1 /abs/Refine3D/job001/run_it010_half1_class001_external_reconstruct.star \
    -i2 /abs/Refine3D/job001/run_it010_half2_class001_external_reconstruct.star -o /abs/out_replay \
    --model-dir <MODELS>/cryofm2-pretrain --op denoise --norm-grad --use-lamb-w --bf16
```

This reconstructs from RELION's Fourier data and samples both halves
(outputs named `…_external_reconstruct_external_reconstruct.mrc`). Needs the per-iteration files kept (RELION's job
cleaning may remove them) and absolute STAR paths.

## 6. cryoSPARC bridge (derived from the code's requirements; no upstream text)

- For `cfm denoise`: export the refinement's **`map_half_A` / `map_half_B`** (unfiltered half maps; same box and
  pixel). cryoSPARC-written maps have origin 0, so no origin restore is needed. Import outputs with "Import 3D Volumes".
- For `inpaint`: poses must become a RELION ≥ 3.1 STAR (pyem `csparc2star.py`) whose `rlnImageSize` equals the
  half-map box and whose particle stacks resolve from an ancestor directory. Check the mask with `--debug`.
- No cryoSPARC job type calls CryoFM2; there is no adapter.

## 7. cryoSeed (`unstable` branch only; not installed, not documented upstream)

A PyTorch/Triton research reconstruction module (`relion/cryoseed/`, 144 files) with its own CLI and
`scripts/cryoseed_wrapper.py`, which always calls `uncond_sampling` with `--norm-grad --use-lamb-w` and can fetch
weights from HF (`--model-id`, with a sub-folder `allow_patterns` mismatch). Mention it only as "in development"; do
not write commands for it.
