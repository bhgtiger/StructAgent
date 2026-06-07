# Lessons (running log for this skill)

Append-only notes that improve the skill over time. v0 seed entries below come from the plan + Claude Audit A; v1.0 entries come from a real Linux/GPU install + run.

## v1.0 — verified on a Linux + RTX 2080 Ti host (2026-06-06)

- **The skill now executes** (install / model download / map run) instead of only emitting `[not-run]` templates. The old v0 read-only/escalation-ladder is replaced by a **confirmation model**: a current, identity-matched config in the right `state` **plus** explicit per-action user confirmation gate each mutating action (`references/00`). The permanent invariant — **never upload/copy/move/delete user map data; process only in place** — is unchanged. The validator was rewritten to enforce the v1.0 contract (confirmation + no-upload language, scripts carry their safety properties) while keeping all correctness/privacy checks.
- **DeepEMhancer 0.17 needs two undeclared libraries + a one-line patch.** 0.17's `setup.py` dropped `keras-contrib` and `keras-radam` from `install_requires`, but the 2021 checkpoints reference them. Install them `--no-deps` (keras-contrib pinned at `3fc5ef70…`, `keras-rectified-adam==0.20.0`). And `keras_contrib.backend.tensorflow_backend.moments()` calls `tf.nn.moments(..., keep_dims=...)`; TF 2.x renamed it `keepdims` → patch needed (`scripts/patch_keras_contrib.py`, idempotent). `--version` does NOT exercise this; only **loading a checkpoint** does, so the functional run is the real test, not `--version`.
- **`--version` succeeds even when a map run would fail.** Confirmed: `--version` returned `0.17` and the TF import worked before the checkpoint-dependency issues would have surfaced. Keep `ready` gated on more than live-help — model load + cube inference is the true check.
- **TF 2.10 + pip CUDA-11.8/cuDNN-8.6 wheels run on a 535-series driver / CUDA 12.2.** An NVIDIA driver is backward-compatible with the older CUDA runtime the wheels carry, so an env built for one box runs on another with a newer driver — provided an `activate.d` hook puts the pip `nvidia-*-cu11` libs on `LD_LIBRARY_PATH` (the runner does this too). cuDNN 8600 loaded; a GPU `Conv3D` and a full 49-cube inference both succeeded.
- **Benign startup noise on this stack:** `Unable to register cuBLAS factory … already registered`, `Could not load dynamic library 'libnvinfer.so.7'`, and TF-TRT warnings (TensorRT simply isn't installed). These are not errors; the run proceeds. Don't report them as failures.
- **Auto-normalization can warn and still work.** On atypical/cropped maps it may print `Automatic radial noise detection may have failed … Guessing radial noise of radius 50 %` and continue. If the result looks wrong, switch to `--noiseStats` or `-m`.
- **The `determine_state()` machine is now validated both ways:** a real `blocked` (Mac mini) and a real `ready` (Linux/GPU) report, in addition to the synthetic-fact checks.

## Seed lessons (from Audit A / source review)

- **`--version`/`-h` are NOT cheap.** The pinned `config.py` does `import tensorflow as tf` at module top level, and the entry point imports it transitively. So even "just check the version" loads the full TF/CUDA stack and can hang on a driver mismatch. Always treat these as heavyweight: isolated subprocess, hard timeout, `CUDA_VISIBLE_DEVICES=""`, never inline. Success ≠ runtime readiness.
- **Config-first only works if "stale/unknown" is defined.** A soft "please run config" instruction is bypassable. The deterministic state machine (`references/02`, `determine_state()`) is what makes the gate testable. Keep them in sync.
- **Three flag traps, repeatedly.** README's `--deepLearningModelDir` is stale (real: `--deepLearningModelPath`); `-c` and `--precomputedModel` are phantoms; `--cleaningStrengh` is genuinely misspelled and must be written verbatim. Users will paste the wrong ones from the README.
- **Version/dependency story is genuinely ambiguous.** Source says 0.17; conda/Anaconda say 0.16. TF is 2.10 (setup.py/README) vs 2.12 (env.yml/meta.yaml); Python 3.9 vs 3.10. Never hard-claim a recipe — read installed metadata via the probe.
- **Local config is a privacy hazard if shipped.** `site_config.local.md` records hostname/arch/GPU/paths. It must stay git-ignored and out of any packaged copy; only the template ships. The validator enforces this.
- **Identity binding matters.** A config for machine A must never license advice for machine B. Always match hostname/OS/arch/exe path/timestamp before machine-specific advice.
- **No quantitative generalization.** The paper's FSC/DeepRes numbers and 20-map benchmark are paper-contextual; never promise a user's map a resolution/quality gain. Output is for visualization/model building.
- **CryoSPARC: separate conda env + path symmetry.** Don't use CryoSPARC's bundled env; the same `deepemhancer` path must resolve on master + all workers; models readable on the execution node. Use the tighter 24 h staleness window for HPC/CryoSPARC advice.
- **A real run has side effects the probe must avoid.** Missing `--deepLearningModelPath` triggers `makedirs(DEFAULT_MODEL_DIR)`; missing `tightTarget.hd5` prints "not found" + `sys.exit(1)`; the download flag pulls ~705 MB from Zenodo. The probe stats files only.

## Open items

- [x] First real Linux/GPU config report — confirmed `determine_state` → `ready`; installed DeepEMhancer 0.17, TF 2.10.1, Python 3.10.
- [x] Live `deepemhancer -h`/`--version` on the target — entry point, `tightTarget` default, half-map/model-path behavior all match pinned source; `references/03` confirmed.
- [x] First fixture run — a 128³ test volume processed end-to-end on the GPU (direct CLI + the runner); valid output. Functional, not a quality benchmark.
- [ ] Model download via `--download` not yet exercised here (models were already present). Verify `setup_deepemhancer_env.sh --download-models` against the live Zenodo record on a fresh host before relying on the download path.
- [ ] Add site-specific module/container/Slurm templates only once a real site config exists (still out of scope until then).
- [ ] Re-test on a non-shared / single-GPU box to characterise the multi-GPU crash caveat directly (currently README-sourced).

## How to add a lesson

One bullet per lesson: what surprised you, the evidence (source ref or observed behavior), and the rule it changes. Update the matching reference + (if behavioral) `validate_static.py` so the lesson is enforced, not just noted.
