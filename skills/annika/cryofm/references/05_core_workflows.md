# 05 — Core workflows

Every command below is a template unless it names a validated-site job id. Replace `<MODELS>` with the folder holding
`cryofm2-pretrain/`, `cryofm2-emhancer/`, `cryofm2-emready/` (where a site launcher resolves the shorthand
`--model-dir pretrain|emhancer|emready`, that works too: [03 §7](03_cli_reference.md)). Use absolute paths and a **new** `-o` per run. Add `--bf16` on
A100/H100-class GPUs (upstream: "Always use `--bf16` if possible"). Add `--log-file-path <existing dir>/run.log`
so the job keeps its own log. Progress bars count patch batches; each batch runs all `--num-timesteps`.

## 0. First contact (any host)

1. Probe: `python3 scripts/cryofm_env_probe.py` on the node you will use. Read the verdict and the site config.
2. Inspect inputs: `python3 scripts/inspect_map.py /abs/half1.mrc /abs/half2.mrc` (gates: extension, axis order,
   odd cube, S ≥ 64, equal boxes and pixel sizes, origin/NSTART; prints patches and batches).
3. Build the command: `python3 scripts/build_cfm_command.py <mode> …` (refuses the documented traps) or copy from
   below. Show the plan ([templates/run_plan.md](../templates/run_plan.md)) and get the go-ahead for GPU spend.
4. Run on a GPU node (Slurm template in §9). Then `python3 scripts/check_cfm_output.py OUT --input /abs/half1.mrc`
   and, if the input origin/NSTART was non-zero, `scripts/restore_origin.py`.
5. Validate scientifically ([08](08_outputs_and_validation.md)): visual inspection at a chosen contour, map-model
   FSC/CC with the deposited model, never the FSC between the two outputs. Record the run in the ledger.

## 1. Denoise two half maps (isotropic likelihood) — VALIDATED on the example site (A100 40 GB, job 27772096)

```bash
cfm denoise -i1 /abs/half_map_1.mrc -i2 /abs/half_map_2.mrc -o /abs/out_denoise \
    --model-dir <MODELS>/cryofm2-pretrain --op denoise --norm-grad --use-lamb-w \
    --lamb-base 1000.0 --lamb-w-max 5.0 --num-timesteps 200 --batch-size 4 --bf16 --seed 0 \
    --log-file-path /abs/out_denoise/run.log      # create /abs/out_denoise first, or drop --log-file-path
```

- Inputs: the refinement's two half maps, same box and pixel size, even box, `.mrc`/`.map`. Which half maps
  (unfiltered vs post-processed) is undocumented upstream; the training data were EMDB (unmasked, unfiltered) halves.
- Outputs: `half_map_1_external_reconstruct.mrc`, `half_map_2_external_reconstruct.mrc`, `avg_external_reconstruct.mrc`.
- Expected log: `Use z_scale mean None std None`, `~~~~~~~~ Use model type UNet ~~~~~~~~`, `Keeping EMAs of 382.`,
  `[Resize to model apix] took … seconds`, a scipy `RuntimeWarning: invalid value encountered in divide` and a
  torch non-leaf `.grad` `UserWarning` (both benign), one tqdm bar per half, `Output to file …` twice.
- Cost: ≈54 s per batch of 4 patches on an A100 (200 steps). Patches from §2 of [04](04_inputs_and_geometry.md).
- Speed-up with a solvent mask on the same grid: add `--mask-path /abs/mask.mrc --bbox` (cubic mask only; voxels
  outside the bbox stay unprocessed input). Untested here.

## 2. Anisotropy / preferred orientation (`denoise inpaint` + particle poses) — untested here

```bash
cfm denoise -i1 /abs/half_map_1.mrc -i2 /abs/half_map_2.mrc -o /abs/out_aniso \
    --model-dir <MODELS>/cryofm2-pretrain \
    --op denoise inpaint --data-starfile-path /abs/Refine3D/jobNNN/run_data.star --fmask-threshold 10.0 \
    --norm-grad --use-lamb-w --bf16
```

- One `--op` list only (`denoise inpaint` or `inpaint denoise`; order inside the list is irrelevant). The upstream
  quick-start command repeats `--op` and silently runs plain denoise.
- The particle STAR must be RELION ≥ 3.1 style with Euler angles and image names whose stacks resolve from an
  ancestor directory; particle box = half-map box in voxels. All particles are used (no half split for MRC inputs).
- `--op inpaint` alone = hard Fourier replacement of observed voxels (noisy, no denoising); the λ flags do nothing there.
- The paper's extra "retain the reference to 10 Å" step (`keep_lowres`) is **not usable** in the public code.
- Check the mask: add `--debug` once and open `<stem>_fmask.mrc` (back-projection count; ≥ 10 = observed).

## 3. Non-uniform (spatially varying noise) — untested here

```bash
cfm denoise -i1 /abs/half_map_1.mrc -i2 /abs/half_map_2.mrc -o /abs/out_nu \
    --model-dir <MODELS>/cryofm2-pretrain --op non-uniform --nbands 64 --norm-grad --use-lamb-w --bf16
```

- Weights per voxel and band from `0.5·(A−B)²` of the resampled halves; needs both halves.
- `--op denoise non-uniform` runs the plain denoise likelihood (branch order), so do not combine them.
- Host RAM: ≈64 MiB per patch per process for the wavelet stacks (125 patches ≈ 8 GiB, 343 ≈ 21 GiB, 1728 ≈ 108
  GiB) [derived] — request `--mem` accordingly or use `--mask-path … --bbox`.
- Batch > 1 sums the non-uniform weights over the batch [derived]; `--batch-size 1` gives per-patch weighting at 4× the time.
- Avoid `--fsc-weighting` with `non-uniform` for anything you will measure FSC on (wavelet filter inflates it).

## 4. Style enhancement of a single map — VALIDATED on the example site (A100 40 GB, job 27772096)

```bash
# LocScale/DeepEMhancer-like look
cfm enhance -i /abs/map.mrc -o /abs/out_emhancer --model-dir <MODELS>/cryofm2-emhancer --output-tag 1 --cfg-weight 2.0 --bf16
# EMReady-like (model-simulated) look
cfm enhance -i /abs/map.mrc -o /abs/out_emready  --model-dir <MODELS>/cryofm2-emready  --output-tag 0 --cfg-weight 0.5 --bf16
```

- No half maps, no data-consistency term, `--norm-grad` not needed, `--seed` ignored (outputs vary run to run).
- Tag/CFG pairing is unchecked by the code: emready with the default tag 1 / CFG 2.0 runs silently with the wrong
  conditioning. Documented ranges: EMhancer CFG 1.5–3.0, EMReady 0.3–0.7.
- Input type is undocumented: the EMhancer-style model was trained on half maps (demo feeds a half map), the
  EMReady-style model on deposited sharpened maps. Output amplitudes are rescaled to the input's 99.999th percentile.
- Output: `map_external_reconstruct.mrc`. Cost ≈ 2 forwards per step (CFG), ≈50 s per batch of 4 on an A100.
- These outputs are post-processed maps: never deposit them as half maps or primary map without saying what they are.

## 5. Style + data term (conditional posterior sampling) — untested here

```bash
cfm enhance -i /abs/map.mrc -i1 /abs/half_map_1.mrc -i2 /abs/half_map_2.mrc -o /abs/out_ctrl \
    --model-dir <MODELS>/cryofm2-emhancer --output-tag 1 --cfg-weight 2.0 \
    --op denoise --norm-grad --use-lamb-w --lamb-base 1000.0 --bf16
# or without -i: cfm enhance -i1 … -i2 … (three outputs, like denoise)
```

- This is the paper's "controllable post-processing"; the quick-start writes it with `cfm denoise`, which is wrong.
- `-i` must match `-i1` in box and pixel size (±0.005 Å); EMDB primary maps often do not — use a half map as `-i`.
- CFG wraps the likelihood-guided velocity, so the data term is ≈(1 + CFG)× stronger than in `cfm denoise`
  [derived]; lower `--lamb-base` if the output hugs the input too closely. `--cfg-weight 0` turns the style guidance off.
- Any `--op` of §1–§3 is allowed here (`non-uniform` was the paper's Fig. 5f choice; the caption says anisotropy-aware).

## 6. Multi-GPU — untested here

```bash
cfm denoise --num_processes 4 -i1 … -i2 … -o … --model-dir … --op denoise --norm-grad --use-lamb-w --bf16
```

- Underscore spelling, after the subcommand; optionally `--main_process_port 29501`. Builds `accelerate launch
  --num_processes 4 -m cryofm.projects.cryofm2.uncond_sampling …`.
- Patches are split across processes; **every GPU still holds the model and a full batch**, so per-GPU memory does
  not drop (issue #1: 4×16 GB cards still OOM at batch 4). Results can differ slightly from a single-GPU run
  (batch composition). Avoid `--fsc-weighting` with > 1 process (barrier mismatch, possible hang) [derived].
- Only rank 0 logs and writes. Request the GPUs on one node with the matching CPU/memory share (the example site:
  18 CPUs / 120 GB per A100); export `NCCL_DEBUG=ERROR` as the docs do.

## 7. Masks, bbox and large maps

- A soft solvent mask on the input grid + `--bbox` restricts sampling to the mask's bounding box (+5 voxels at 1.5 Å,
  ≥ 64 per axis); outside stays the unprocessed input. Cubic masks only (masks are not padded).
- Big boxes: time ∝ patches ((⌈(S−64)/32⌉+1)³); 400³ @ 1 Å ≈ 512 patches ≈ 128 batches ≈ 2 h per half on an A100.
  The prior was trained on boxes ≤ 576 Å and maps < 3 Å; behaviour beyond is unevaluated.
- Non-cubic maps are padded automatically; odd cubes must be padded by you (even box).

## 8. RELION `--external_reconstruct`

See [07](07_relion_integration.md) and [templates/relion_external_reconstruct.sh](../templates/relion_external_reconstruct.sh).
Not run on the validated site (no RELION there); the documented workflow fails by static reading at the final
joined iteration, so plan for that.

## 9. Slurm (generic template; numbers from the validated A100 site)

Copy [templates/slurm_cfm.sbatch.template](../templates/slurm_cfm.sbatch.template), fill every `<PLACEHOLDER>` (account,
partition, CPU/memory share per GPU, site activation, node-local scratch, output root, skill dir), `bash -n` it, show
[templates/run_plan.md](../templates/run_plan.md), then submit. `scripts/build_cfm_command.py --sbatch` fills the command
and the paths it knows. The template's command pattern ran as smoke job 27772096 on the validated site; the file itself
has never been submitted as-is. Essentials:

```bash
#SBATCH --account=<ACCOUNT> --partition=<GPU_PARTITION> -N 1 -n 1 --gpus=1 --cpus-per-task=<CPUS> --mem=<MEM> -t 01:00:00
<site activation, e.g. source /abs/path/activate.sh>   # jobs started with --export=NONE need it inside the job
set -uo pipefail                                        # no set -e: keep the rc, finish the summary
export TMPDIR=<NODE_LOCAL_TMP>/cfm-$SLURM_JOB_ID; mkdir -p "$TMPDIR"
OUT=<OUTPUT_ROOT>/<name>_$SLURM_JOB_ID; mkdir -p "$OUT"
cfm denoise -i1 /abs/h1.mrc -i2 /abs/h2.mrc -o "$OUT" --model-dir <MODELS>/cryofm2-pretrain --op denoise --norm-grad --use-lamb-w --bf16 --seed 0 \
    --log-file-path "$OUT/run.log"; rc=$?; echo "cfm rc=$rc"
python3 <SKILL_DIR>/scripts/check_cfm_output.py "$OUT" --input /abs/h1.mrc
```

Walltime: ≈1 min per batch-of-4 per half plus 1 min startup; `--mem` is the 1-GPU share (raise for `non-uniform`).
The example site's shares: 18 CPUs / 120 GB per A100 40 GB (validated), 16 CPUs / 160 GB per H100 94 GB (untested).

## 10. Ledger

Record for every real run: exact command, image sha256 (or env), weights revision, job id, rc, wall time, peak
memory if sampled (`nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > gpumem.log &`),
output files with grid/origin, the validation numbers, and the user's go-ahead. annika-log layout where that convention exists.
