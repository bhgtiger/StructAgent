# 05 — Workflow recipes (runnable, confirmation-gated)

These are the concrete recipes for common DeepEMhancer tasks. They are **runnable**, but only after (a) a current, identity-matched config in the right `state` (`references/02`) and (b) the user confirming the specific action (`references/00`). Pick flags with `references/03` (CLI) and `references/04` (inputs/models); fill `<…>` placeholders with real paths once the config is current.

All map runs go through `scripts/run_deepemhancer.sh`, which activates the env, puts the pip CUDA-11 libraries on `LD_LIBRARY_PATH`, sets `TF_FORCE_GPU_ALLOW_GROWTH=true`, and execs `deepemhancer`. Add `--dry-run` to preview the resolved command without running. `<env>` is the conda env name or prefix from the config.

## 0 — Config session (always first; read-only, safe to run)

```text
python3 scripts/deepemhancer_env_probe.py --tensorflow-probe --live-help \
    --model-dir <models_dir> --format md --output configs/site_config.local.md
```

Read the resulting `state`. `ready` → you may plan and (with confirmation) run. `partial`/`blocked` → resolve the named gap first (install, models, GPU/TF). `unknown`/`stale` → re-probe the real target.

## 1 — Install / model availability (state `blocked` on a fresh Linux host)

If DeepEMhancer or the models are missing, install with the verified recipe (`references/09`) — confirm first:

```text
bash scripts/setup_deepemhancer_env.sh --env <env>                  # install env (you place .hd5 files)
bash scripts/setup_deepemhancer_env.sh --env <env> --download-models # also fetch weights (~705 MB)
```

Required model files in the model dir: `deepEMhancer_tightTarget.hd5`, `deepEMhancer_wideTarget.hd5`, `deepEMhancer_highRes.hd5` (+ `deepEMhancer_masked.hd5` for `-m`). Default dir: `~/.local/share/deepEMhancerModels/production_checkpoints`. If a site already has the `.hd5` files, skip the download and point at them with `--deepLearningModelPath`.

## 2 — Single full-map, default model

```text
bash scripts/run_deepemhancer.sh --env <env> -- -i <input_fullmap.mrc> -o <output.mrc>
```

Defaults to `-p tightTarget`, `-g 0`, `-b 8`. Input must be a raw, unmasked, unsharpened refinement map (`references/04`).

## 3 — Half-map processing (preferred when you have half maps)

```text
bash scripts/run_deepemhancer.sh --env <env> -- \
    -i <half1.mrc> -i2 <half2.mrc> -o <output.mrc> -p tightTarget -g 0 -b 4
```

Half map 1 → `-i`, half map 2 → `-i2` (do not forget `-i2`).

## 4 — Model choice

```text
# highRes — ONLY when overall FSC < 4 Å (can look noisier):
bash scripts/run_deepemhancer.sh --env <env> -- -p highRes -i <input.mrc> -o <output.mrc>
# wideTarget — if tight/highRes over-mask or clip density (less sharp):
bash scripts/run_deepemhancer.sh --env <env> -- -p wideTarget -i <input.mrc> -o <output.mrc>
```

## 5 — Normalization mode 1: manual noise stats

```text
# Two floats: noise mean then noise std (estimate from a solvent region).
bash scripts/run_deepemhancer.sh --env <env> -- \
    -i <input.mrc> -o <output.mrc> --noiseStats <NOISE_MEAN> <NOISE_STD>
```

**Mutually exclusive with `-m/--binaryMask`** — supplying both asserts and aborts (`references/03`/`06`); choose one mode. Use when auto-normalization looks wrong.

## 6 — Normalization mode 2: binary mask (forces tightTarget)

```text
# Do NOT also pass -p; the mask forces tightTarget + the masked model.
bash scripts/run_deepemhancer.sh --env <env> -- -i <input.mrc> -o <output.mrc> -m <binary_mask.mrc>
```

Needs `deepEMhancer_masked.hd5` present. 1 = protein, 0 = solvent.

## 7 — GPU / batch-size tuning

```text
# Choose GPU id; lower -b on CUDA OOM, raise for low utilization:
bash scripts/run_deepemhancer.sh --env <env> -- -i <input.mrc> -o <output.mrc> -g <gpu_id> -b <batch_size>
# Multi-GPU can crash on some box sizes -> use a single GPU (and/or -b 1):
bash scripts/run_deepemhancer.sh --env <env> -- -i <input.mrc> -o <output.mrc> -g <single_gpu_id>
# CPU only (VERY slow ~a day; only as a last resort, with the user's acceptance):
bash scripts/run_deepemhancer.sh --env <env> -- -i <input.mrc> -o <output.mrc> -g -1
```

`run_deepemhancer.sh` already exports `TF_FORCE_GPU_ALLOW_GROWTH=true`, which also mitigates cuDNN-init/OOM errors.

## 8 — Custom model path (REAL flag is `--deepLearningModelPath`)

```text
# Directory of models:
bash scripts/run_deepemhancer.sh --env <env> -- \
    -i <input.mrc> -o <output.mrc> --deepLearningModelPath <models_dir>
# A single .hd5 file forces -p tightTarget (do not pass another -p):
bash scripts/run_deepemhancer.sh --env <env> -- \
    -i <input.mrc> -o <output.mrc> --deepLearningModelPath <model.hd5>
```

NEVER use `--deepLearningModelDir` (stale README flag), `-c`, or `--precomputedModel` (phantoms). See `references/03`.

## 9 — CryoSPARC / HPC

Path symmetry and separate-conda cautions live in `references/07`. The skill does not auto-create wrapper files, `chmod`, or submit `sbatch`/`cryosparcm` jobs; exact module/scheduler lines need a captured site config first. The concept: install DeepEMhancer in its own conda env (`setup_deepemhancer_env.sh`), make the `deepemhancer` path resolve identically on master + every worker, and ensure the `.hd5` files are readable on the execution node.

## Provenance to record with every output

Model/preset, normalization mode, input map(s), `-g`/`-b`, DeepEMhancer version, and the exact command. Then validate the output independently (`references/08`) — a successful run is not a quality claim.
