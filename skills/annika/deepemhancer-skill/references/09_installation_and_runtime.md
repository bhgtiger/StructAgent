# 09 — Installation & runtime (verified recipe)

DeepEMhancer 0.17 ships as a TensorFlow-2.10 program but its bundled 2021 model
checkpoints need two libraries that 0.17's `setup.py` no longer declares, and a
one-line TF-2.x compatibility patch. This file records a recipe **verified
running end-to-end on a Linux + NVIDIA RTX 2080 Ti host (driver 535 / CUDA 12.2)**
— a checkpoint loads, cubes process on the GPU, and a valid `.mrc` is written.

The same env works across newer drivers because an NVIDIA driver is
backward-compatible with the older CUDA 11.8 *runtime* the wheels carry. Confirm
the actual target with the probe (`references/02`) and `nvidia-smi`.

## What "correct config" means here

| Component | Verified-good value | Notes |
|---|---|---|
| OS | Linux | DeepEMhancer is Linux-only. |
| Python | 3.10 | conda-forge. |
| DeepEMhancer | 0.17 | `deepemhancer --version`. Anaconda channel may report 0.16. |
| TensorFlow | `tensorflow-gpu==2.10.1` (+ `keras==2.10.0`) | source `setup.py` pins 2.10.*; env.yml/meta.yaml say 2.12 — both seen in the wild. |
| keras-contrib | pinned commit `3fc5ef709e061416f4bc8a92ca3750c824b5d2b0`, **+ TF-2 `moments()` patch** | needed by the checkpoints; dropped from 0.17 deps. |
| keras_radam | `keras-rectified-adam==0.20.0` | provides `keras_radam`; dropped from 0.17 deps. |
| CUDA/cuDNN | pip wheels: `nvidia-cuda-runtime-cu11==11.8.89`, `nvidia-cudnn-cu11==8.6.0.163`, `nvidia-cublas-cu11`, `nvidia-cufft/curand/cusolver/cusparse/cupti/nvrtc-cu11`, `nvidia-nccl-cu11` | TF 2.10 does not bundle them; an `activate.d` hook puts them on `LD_LIBRARY_PATH`. |
| other deps | `numpy==1.23.5`, `scikit-image==0.19.3`, `scipy==1.9.3`, `mrcfile==1.4.3` | TF 2.10 needs numpy < 1.24. |
| models | `~/.local/share/deepEMhancerModels/production_checkpoints/*.hd5` | 2021 checkpoints still load after the patch. |

## Install (consent-gated, one script)

`scripts/setup_deepemhancer_env.sh` performs the whole recipe and **refuses to
run until you confirm** (interactively or `--yes`). It creates the env with
`mamba`/`conda` over conda-forge (sidestepping broken `defaults` channels),
pip-installs DeepEMhancer + the two extra libraries + the CUDA-11 wheels, writes
the `LD_LIBRARY_PATH` activate hook, and applies the `keras_contrib` patch.

```text
# Named env, no model download (place .hd5 files yourself):
bash scripts/setup_deepemhancer_env.sh --env deepemhancer

# Env at a prefix, also fetch the ~705 MB model weights (network + write):
bash scripts/setup_deepemhancer_env.sh --env-prefix ~/.conda/envs/deepemhancer \
     --download-models --yes
```

Only run an install after the user agrees to it. Without `--download-models` the
script leaves model placement to you (a site may already have the `.hd5` files).

## The two gotchas the install script handles for you

1. **Missing checkpoint dependencies.** 0.17 dropped `keras-contrib` and
   `keras-radam` from `install_requires`, but the checkpoints reference them via
   embedded code. They are installed `--no-deps` at the pinned versions above.
2. **`keras_contrib.moments()` keyword.** It calls
   `tf.nn.moments(..., keep_dims=...)`; TF 2.x renamed that to `keepdims`.
   `scripts/patch_keras_contrib.py` rewrites that one function to accept both
   spellings. It is idempotent (`--check` to inspect, no-op if already patched).
   Re-run it if `keras_contrib` is ever reinstalled.

## Running a map

Use `scripts/run_deepemhancer.sh` — it activates the env, ensures the CUDA-11
libs are on `LD_LIBRARY_PATH`, sets `TF_FORCE_GPU_ALLOW_GROWTH=true`, and execs
`deepemhancer` with your arguments (everything after `--`). Confirm inputs/output
with the user first.

```text
bash scripts/run_deepemhancer.sh --env <env> -- \
    -i <half1.mrc> -i2 <half2.mrc> -o <out.mrc> -p tightTarget -g 0 -b 4
```

`--conda-sh <path>` if conda is in a non-standard place; `--dry-run` to preview;
`--no-allow-growth` to leave TF's memory policy default. See `references/03`/`04`
for flag and model choice, `references/05` for per-workflow recipes.

## Performance & resource notes (observed)

- A ~128³ box (padded to 160³, 49 cubes) finishes in ~70 s on one RTX 2080 Ti;
  a full ~400³ map is ~8 min. Model load + TF init adds ~30–60 s up front.
- `-b/--batch_size` default is 8. On an 11 GB card, `-b 4` is a safe start for
  large boxes; lower further on CUDA OOM, raise for low GPU utilization.
- Use **one** GPU (`-g 0`) unless you have a reason not to: some box sizes crash
  with multiple GPUs (`references/06`). To run several maps on one node, queue
  them rather than racing for VRAM.
- Benign log lines on this stack (not errors): `Unable to register cuBLAS
  factory ... already registered`, and `Could not load dynamic library
  'libnvinfer.so.7'` / TF-TRT warnings (TensorRT is simply not installed).
