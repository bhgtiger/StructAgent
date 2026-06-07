# 06 — Troubleshooting & decision trees

Grounded in pinned-source behavior + README/Biowulf known issues + errors observed on a real Linux/GPU install (`references/09`). Live target errors override these. Mutating fixes (install, model download, re-run) still require user confirmation (`references/00`).

## Quick symptom → cause → action

| Symptom | Likely cause | Action |
|---|---|---|
| `Deep learning models not found … Downloading default models with --download or indicate its location with --deepLearningModelPath` then exit 1 | No `deepEMhancer_tightTarget.hd5` in the model dir | Point `--deepLearningModelPath` at an existing dir, or (with consent) fetch them: `setup_deepemhancer_env.sh --download-models`. State stays `blocked` until models exist. |
| `TypeError: moments() got an unexpected keyword argument 'keep_dims'` (while loading a checkpoint) | `keras_contrib` on TF 2.x; `tf.nn.moments` renamed `keep_dims`→`keepdims` | Apply the patch: `python3 scripts/patch_keras_contrib.py` (idempotent). `setup_deepemhancer_env.sh` does this automatically. |
| `ModuleNotFoundError: No module named 'keras_contrib'` / `'keras_radam'` (while loading a checkpoint) | DEH 0.17 dropped these from its deps, but the 2021 checkpoints need them | Install them `--no-deps`: handled by `setup_deepemhancer_env.sh` (keras-contrib pinned + `keras-rectified-adam==0.20.0`). See `references/09`. |
| `AssertionError: -p option should not be provided if --deepLearningModelPath points to an hd5 file` | Passed `-p` with `--deepLearningModelPath` as a single `.hd5` | Drop `-p` (a file forces `tightTarget`). |
| `AssertionError: if binary mask provided, -p option should not be provided` | Passed `-p` with `-m/--binaryMask` | Drop `-p`; mask mode forces `tightTarget` + the masked model. |
| `AssertionError: only one of the following options can be provided: noise_stats, binary_mask` | Passed both `--noiseStats` and `-m/--binaryMask` | Use exactly one normalization mode — drop one of them. |
| `AssertionError: Error, output fnameIn already exists` | The `-o` target already exists; DeepEMhancer refuses to overwrite (fires late, after model load) | Use a new `-o` filename, or remove/rename the existing output, then re-run. The runner warns if `-o` exists but never deletes it. |
| `AssertionError: … output name is not in mrc format` | `-o` doesn't end `.mrc`/`.map` | End the output name with `.mrc` or `.map`. |
| `AssertionError: input file … not found` | `-i` path wrong | Fix the input path; remember `-i2` if `-i` is a half map. |
| `unrecognized arguments: --deepLearningModelDir` (or `-c`, `--precomputedModel`) | Stale/phantom flag from README/example | Use the real flag `--deepLearningModelPath`. See `references/03`. |
| `CUDA Out Of Memory` / `OOM when allocating` | Batch too large / map too big for VRAM | Lower `-b/--batch_size` (8 → 4 → 2 …). `run_deepemhancer.sh` already sets `TF_FORCE_GPU_ALLOW_GROWTH=true`; if you call deepemhancer directly, export it first. |
| Low GPU utilization / slow | Batch too small | Raise `-b/--batch_size`. |
| Crash only with multiple GPUs | Known multi-GPU instability for some box sizes | Use a single GPU (`-g 0`) **and/or** `-b 1`. |
| `cudaGetDevice() failed … CUDA driver version is insufficient for CUDA runtime version` | NVIDIA driver too old for the runtime | Update the driver to **≥ 418.39** (README). Environment-specific; config `blocked` until fixed. A 535-series driver runs the CUDA-11.8 wheels fine. |
| `Could not create cudnn handle: CUDNN_STATUS_INTERNAL_ERROR` (often with "Failed to get convolution algorithm") | cuDNN init failure — GPU-memory pressure or CUDA/cuDNN mismatch | First try `TF_FORCE_GPU_ALLOW_GROWTH=true` (the runner sets it). If it persists, CUDA↔cuDNN incompatibility — reinstall the pinned wheels (`references/09`); config `blocked`. |
| `Could not load dynamic library 'libnvinfer.so.7'` / `TF-TRT Warning` / `Unable to register cuBLAS factory … already registered` | TensorRT not installed; benign TF 2.10 startup noise | **Ignore** — these are warnings, not errors, on the verified stack. The run proceeds. |
| `Could not load dynamic library 'libcudart…' / 'libcudnn…'` (TF can't import) | pip CUDA-11 libs not on `LD_LIBRARY_PATH` | Activate via the env's `activate.d` hook or use `run_deepemhancer.sh` (it adds the libs). See `references/09`. |
| `Automatic radial noise detection may have failed … Guessing radial noise of radius 50 %` | Auto-normalization found no clear radial solvent trend (common on tightly-cropped/atypical maps) | Benign note — the run continues. If the result looks wrong, supply `--noiseStats MEAN STD` or `-m mask.mrc` (`references/04`). |
| Extremely slow run (~a day) | Running on CPU (`-g -1`) | Use a GPU; CPU is a last resort only. |
| Output looks over-masked / clipped | `tightTarget`/`highRes` too aggressive, or the input wasn't truly raw/unmasked | Try `-p wideTarget`; re-check the input is a raw refinement map. |
| Output noisier than expected | `highRes` used on a lower-resolution map | Use `highRes` only when overall FSC < 4 Å; otherwise `tightTarget`. |

## Side effects of a real run (so the probe never triggers them)

- With no `--deepLearningModelPath`, a real run **creates** `~/.local/share/deepEMhancerModels/production_checkpoints` if absent (`os.makedirs`). The read-only probe never does this.
- The download action performs a network GET (~705 MB from Zenodo) and unzips. The skill performs it only via `setup_deepemhancer_env.sh --download-models`, with consent.

## Decision tree A — "Can I run DeepEMhancer on machine X?"

```text
1. Current config whose host_identity == machine X?    No -> unknown/stale; probe X. STOP.
2. Is X Linux?                                          No -> blocked (Linux-only).
3. deepemhancer installed (PATH or package)?           No -> blocked; offer setup_deepemhancer_env.sh.
4. Required models present (tightTarget at least)?      No -> blocked; place .hd5 or --download-models.
5. TensorFlow probe failed/timed out?                  Yes -> blocked; fix CUDA/cuDNN (references/09).
6. NVIDIA GPU visible?                                  No -> partial (CPU-only very slow; must accept).
7. Anything required untested (TF/live not probed)?    Yes -> partial; complete the probe.
   Else -> ready (run only after the user confirms).
```

## Decision tree B — "Which model / normalization?"

```text
Input must be raw, unmasked, unsharpened (else stop — wrong input).
Resolution < 4 Å and want detail? -> -p highRes (may be noisier).
Over-masking with tight/highRes?  -> -p wideTarget.
Otherwise                         -> default tightTarget.
Normalization: trust auto first.
  Auto wrong + can estimate noise -> --noiseStats MEAN STD.
  Have a reliable binary mask      -> -m mask.mrc (forces tightTarget; drop -p).
```

## Decision tree C — GPU memory / performance

```text
CUDA OOM?            -> lower -b (8 -> 4 -> 2 ...); ensure TF_FORCE_GPU_ALLOW_GROWTH=true.
Low GPU usage/slow?  -> raise -b.
Crash with >1 GPU?   -> single GPU (-g 0) and/or -b 1.
cuDNN handle error?  -> TF_FORCE_GPU_ALLOW_GROWTH=true; else CUDA/cuDNN mismatch -> reinstall wheels (refs/09).
Driver insufficient? -> update NVIDIA driver to >= 418.39.
No GPU at all?       -> CPU (-g -1) last resort (very slow); prefer a GPU host.
```

## When to declare `blocked` vs `partial`

- **`blocked`** when a fatal fact is known: non-Linux, no install, missing required models, TF/live-help failure, no GPU when a GPU run is required. Explain the blocker and the next fix; do not run a map.
- **`partial`** when nothing is fatal but something required is untested (TF not probed, live help skipped, GPU absent but CPU acceptable, optional `masked.hd5` missing). Name the gap and offer to complete it with confirmation.
- Never upgrade to `ready` on the strength of `--version`/`-h` alone — that proves only the import chain loaded, not that a checkpoint loads or a map processes.
