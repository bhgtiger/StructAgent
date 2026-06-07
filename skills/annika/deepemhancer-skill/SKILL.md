---
name: deepemhancer
description: Use this skill to run, install, configure, troubleshoot, or explain DeepEMhancer (rsanchezgarc/deepEMhancer) — the deep-learning post-processing tool for cryo-EM maps (combined masking-like + sharpening-like enhancement). Covers the CLI (-i/-i2/-o, -p tightTarget/wideTarget/highRes, --deepLearningModelPath, --noiseStats, -m/--binaryMask, -g/--gpuIds, -b/--batch_size, --cleaningStrengh, --download), model .hd5 files, input/half-map suitability, the TensorFlow/CUDA/GPU environment, CryoSPARC/HPC integration, and whether a given machine can run it. It is config-first: it reads or generates a target-environment config report before giving machine-specific commands, and it confirms before installing, downloading models, or running on a map. MANDATORY TRIGGERS: DeepEMhancer, deepemhancer, map post-processing, map sharpening + denoising in one step, deepEMhancer_tightTarget.hd5, --deepLearningModelPath, "run deepemhancer", "install deepemhancer", "deepemhancer GPU/CUDA error".
version: 1.0.0
author: Xiaohu Guo + Hermes/Claude
license: local
platforms: [linux]
metadata:
  hermes:
    tags: [cryo-em, post-processing, sharpening, denoising, deepemhancer, tensorflow, gpu]
    related_skills: [cryosparc, relion, chimerax, phenix, structural-strategy]
---

# DeepEMhancer

DeepEMhancer (Sánchez-García et al., *Communications Biology* 2021; repo `rsanchezgarc/deepEMhancer`, Apache 2.0) is a deep-learning post-processing tool for cryo-EM maps. A 3D U-net applies **masking-like and sharpening-like operations in one step** using pretrained `.hd5` models. Input is a **raw, unmasked, unsharpened** map straight from refinement (half maps preferred); output is a post-processed map for visualization and model building.

Use this skill when the task mentions **DeepEMhancer / deepemhancer**, post-processing a map with it, its CLI flags or model files, installing or fixing its TensorFlow/CUDA/GPU environment, or CryoSPARC/HPC integration. This skill **executes** (it can install the env, download models, and run maps) — but only on the local machine, only with the right config, and only after confirming the action.

## The config-first rule (do this first, every session)

DeepEMhancer is environment-sensitive (Linux-only, a specific TensorFlow/CUDA/cuDNN/GPU stack, large model files). The machine you are running on is **not** assumed to be the runtime.

> **Before any machine-specific command, readiness claim, install, model download, or map run, you MUST have a *current* config report whose recorded host identity matches the target machine.**

Generate or read it with the read-only probe (`references/02`), then classify the `state`:

```text
python3 scripts/deepemhancer_env_probe.py --tensorflow-probe --live-help \
    --model-dir <models_dir> --format md --output configs/site_config.local.md
```

(`configs/site_config.local.md` is private/local and is never packaged — see *Local config privacy*. Run the probe **on the target machine**; the default run is read-only, and `--tensorflow-probe`/`--live-help` are opt-in heavyweight checks that load TensorFlow in a timed subprocess.)

General, non-machine-specific questions (what DeepEMhancer does, what a flag means, input suitability, model choice rationale, the paper's purpose/limits) you may always answer from the references without a config — just don't tie them to "your machine."

## State → what you may do

| State | Meaning | What you may do |
|---|---|---|
| `ready` | All probed required facts present on a current, matching Linux+GPU host | Plan and, **with explicit user confirmation**, RUN `deepemhancer` on the user's local map via `scripts/run_deepemhancer.sh`. Always remind: a successful run ≠ a better map. |
| `partial` | Some required runtime detail untested/missing (e.g. TF/GPU not probed, no GPU so CPU-only, or an *optional* model like `masked.hd5` missing) | Explain the uncertainty; name the missing check; offer to complete the config (probe TF/GPU, install, download models) **with confirmation**. Close any TF/GPU gap before a GPU run; CPU-only must be explicitly accepted (very slow). |
| `blocked` | Known fatal mismatch (non-Linux, no install, missing required models, TF/CUDA failure, no GPU for a GPU run) | Explain the blocker and the next safe step (install via `setup_deepemhancer_env.sh`, fix CUDA, place models). No map run until resolved. |
| `unknown` | No usable config / missing identity / asking about an unrepresented target | Ask to run/read the config session first. |
| `stale` | Prior config no longer trustworthy (age, host/path/env change) | Treat as `unknown` for concrete advice; re-probe the target. |

State machine and staleness rules: `references/02_config_session_and_environment.md`.

## Operating rules (confirm before acting)

1. **Identify the intent first:** explanation, a dry-run/plan, an install, a model download, or a real GPU run. Match the action to the config `state`.
2. **Confirm before each mutating or heavyweight action** and echo back what will happen:
   - **Install** (creates a conda env, installs packages): `scripts/setup_deepemhancer_env.sh` — confirm env name/prefix and that packages will be installed.
   - **Model download** (~705 MB from Zenodo, network + write): `setup_deepemhancer_env.sh --download-models` — confirm the destination directory.
   - **Map run** (GPU, minutes, writes an output map): `scripts/run_deepemhancer.sh` — confirm input(s), output path, model, GPU id, and batch size.
3. **Never upload, copy, move, or delete the user's map data.** Cryo-EM maps are frequently unpublished/proprietary. This skill processes maps only in place on the local machine and sends nothing to any external service. The probe touches only environment metadata.
4. **Keep DeepEMhancer in its own conda environment** — never install it into CryoSPARC's bundled environment (`references/07`).
5. **Preserve provenance:** record the DeepEMhancer version, model/preset, normalization mode, input map(s), GPU/batch, and the exact command, alongside any output map.
6. **Treat the output as a hypothesis,** not a resolution claim. Do not generalize the paper's benchmark numbers to the user's map (`references/08`).

## Quick start (a `ready` host)

```text
# Half maps (preferred), default tightTarget model, GPU 0:
bash scripts/run_deepemhancer.sh --env <env> -- \
    -i <half1.mrc> -i2 <half2.mrc> -o <out.mrc> -p tightTarget -g 0 -b 4

# Single full refinement map:
bash scripts/run_deepemhancer.sh --env <env> -- -i <map.mrc> -o <out.mrc>
```

`run_deepemhancer.sh` activates the env, puts the pip CUDA-11 libraries on `LD_LIBRARY_PATH`, sets `TF_FORCE_GPU_ALLOW_GROWTH=true`, and execs `deepemhancer` with your arguments. Add `--dry-run` to preview without running. Pick flags using `references/03` (CLI) and `references/04` (inputs/models); never run before the user confirms.

## Flag traps you must not repeat

- The model-path flag is **`--deepLearningModelPath`**. The README's `--deepLearningModelDir` is **stale/not real**; `-c` and `--precomputedModel` are **phantoms**. Correct any pasted command that uses them.
- The dust-cleaning flag is spelled **`--cleaningStrengh`** (sic) — never "Strength".
- With `-m/--binaryMask` or a single-`.hd5` `--deepLearningModelPath`, the model is forced to `tightTarget`: **do not also pass a non-default `-p`** (it raises an `AssertionError`, not a silent ignore). Details: `references/03`.

## Reference routing

| File | Use it for |
|---|---|
| `references/00_scope_and_trust.md` | Scope, safety/confirmation model, trust ladder, license/privacy |
| `references/01_source_map.md` | Which source backs which claim; version divergence |
| `references/02_config_session_and_environment.md` | Config-first state machine, staleness, probe usage |
| `references/03_cli_reference.md` | Authoritative flags/defaults/choices + phantom/stale flags |
| `references/04_inputs_outputs_models.md` | Input/half-map suitability, models, normalization, outputs |
| `references/05_workflow_templates.md` | Runnable recipes per workflow (via the runner) |
| `references/06_troubleshooting_and_decision_trees.md` | Failure modes + decision trees (install, OOM, models, flags) |
| `references/07_cryosparc_hpc_integration.md` | CryoSPARC separate-env / path symmetry; HPC cautions |
| `references/08_validation_and_limits.md` | What you may and may not claim about results |
| `references/09_installation_and_runtime.md` | Verified install recipe, env management, the runner |

## Local config privacy

`configs/site_config.local.md` is a **per-environment, private** report (hostname, GPU, paths). It is git-ignored and **excluded from any distributed/installed copy** of this skill. Only `configs/site_config.template.md` ships. Never commit or package a real machine's local config.
