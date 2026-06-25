---
name: modelangelo
description: >-
  Install and set up ModelAngelo (3dem/model-angelo), the cryo-EM atomic model
  builder, on a Linux/NVIDIA target. Config-first: it probes the target, picks an
  install route (personal conda, shared-cluster TORCH_HOME, container, SBGrid, or
  an HPC module like Biowulf), runs the official install_script.sh with
  confirmation, plans the ~10 GB weight + ESM download and TORCH_HOME cache, and
  verifies the install. Use whenever the user wants to install, set up, or
  configure the ModelAngelo environment, asks whether a machine can run it, hits
  an install / conda / torch / CUDA / weights / TORCH_HOME / hhblits error, or
  needs ModelAngelo wired into RELION 5. It assumes nothing about the current
  machine; configuration is captured per target first. It installs and verifies
  but does NOT run production builds and is NOT a validation tool. Triggers:
  ModelAngelo, model_angelo, install ModelAngelo, setup_weights, TORCH_HOME,
  ModelAngelo GPU/CUDA error, on Biowulf/SBGrid/Singularity, RELION
  ModuleNotFoundError.
---

# ModelAngelo — installation & environment setup

ModelAngelo (Jamali et al., *Nature* 2024; repo `3dem/model-angelo`, MIT; pinned
**v1.0.18**, commit `994945b`) is an automated atomic model builder for cryo-EM
maps. **This skill installs and sets it up — it does not run production builds
and does not validate models.** Building a `.cif` is the start of a workflow, not
the end: route outputs to refinement (Servalcat/Phenix) and independent
validation (MolProbity/Q-score/EMRinger/manual inspection). See
`references/00_scope_and_trust.md`.

The official install is unusually clean: clone the repo and `source
install_script.sh`. The skill's value is everything *around* that — deciding
whether a target can run ModelAngelo, choosing the right route, planning the
large weight cache, doing it reproducibly (pinned tag), and verifying it worked.

## The config-first rule (do this first, every session)

ModelAngelo is environment-sensitive: **Linux + NVIDIA/CUDA**, conda, ≥8 GB GPU,
and **~10 GB of weights** (a seq-aware bundle plus the ~7 GB ESM-1b language
model). The machine you are running on is **not** assumed to be the install
target — the user has said configuration happens later, per device.

> **Before any machine-specific command, readiness claim, install, weight
> download, or verification, you MUST have a *current* config report whose
> recorded host identity matches the target machine.**

Generate or read it with the read-only probe (`references/02`), then read its
`state`:

```text
python3 scripts/modelangelo_env_probe.py --format md --output configs/site_config.local.md
```

Run the probe **on the target machine**. Its default run is read-only and
side-effect-free (no install, no clone, no download, no torch import, no network,
no directory creation); `--torch-probe` is an opt-in heavyweight check.

General, non-machine questions (what ModelAngelo is, what a flag means, which
route fits a described setup, what the weights are) you may answer from the
references without a config — just don't tie the answer to "your machine."

## State → what you may do

| State | Meaning | What you may do |
|---|---|---|
| `ready` | Linux target with conda + git + enough free disk + an NVIDIA GPU visible; **or** ModelAngelo already installed | Plan the route and, **with explicit user confirmation**, INSTALL via `scripts/install_modelangelo.sh`, fetch weights, and VERIFY via `scripts/verify_modelangelo.sh`. If already installed, verify and report; the installer is idempotent. |
| `partial` | Installable but a non-fatal prerequisite is missing/untested (no GPU detected → CPU-only is impractical for building and must be explicitly accepted; a GPU below the recommended ~8 GB; conda present but `git` missing; tight disk at the cache target; `TORCH_HOME` unset so weights would land in per-user `~/.cache`; torch/CUDA not probed) | Name the missing check; offer to address it (point to miniconda/git, set `TORCH_HOME`, free disk) **with confirmation**; then install. Don't claim run-readiness while GPU/CUDA is untested. |
| `blocked` | Fatal mismatch: non-Linux host (macOS/Apple Silicon, Windows) — the official route is Linux/CUDA-only (SBGrid ships Linux-64 only) | Explain the blocker and the real paths: a Linux workstation, an HPC module (Biowulf/SBGrid), or a Linux container/VM. No local install. |
| `unknown` | No usable config / missing host identity / asking about a target the config doesn't represent | Ask to run the probe on the target first; give only general (non-machine) guidance until then. |
| `stale` | Prior config no longer trustworthy (age, or host/path/env changed) | Treat as `unknown`; re-probe the target. |

State machine, staleness rules, and identity binding: `references/02`.

## Operating rules (confirm before acting)

1. **Identify intent first:** an explanation, a "can this machine run it?" check,
   a route recommendation, an install, a weight download, or a post-install
   verification. Match the action to the config `state`.
2. **Confirm before each mutating or network action** and echo back exactly what
   will happen:
   - **Install** (clones the repo, creates a conda env, pip-installs torch +
     ModelAngelo): `scripts/install_modelangelo.sh` — refuses to run without
     `--yes`/an interactive prompt. Confirm env name, repo location, pinned tag.
   - **Weight download** (~10 GB from Zenodo + FAIR-ESM, network + write):
     `install_modelangelo.sh --download-weights` or `model_angelo setup_weights`
     — confirm the destination (`TORCH_HOME`) and that ≥10 GB is free.
   - **Verify** (`scripts/verify_modelangelo.sh`): imports torch + model_angelo;
     safe but not free. Fine to run after an install.
3. **Never download private/unpublished maps or bundle map data into the skill.**
   This skill installs software and weights only; it does not touch the user's
   cryo-EM data.
4. **Keep ModelAngelo in its own conda env** (default `model_angelo`). Do not
   install it into another tool's bundled environment (e.g. RELION's or
   CryoSPARC's) — `references/07` covers RELION 5 integration, which imports
   `model_angelo` as a *module* rather than calling the PATH binary.
5. **Pin for reproducibility:** install from tag **v1.0.18** by default; record
   the version, route, `TORCH_HOME`, and the exact command alongside the result.
6. **Don't oversell the output.** A working install ≠ a good model. ModelAngelo
   does not build ligands/cofactors/glycans, struggles below ~3.5–4 Å local
   resolution, and never validates. Always hand off downstream.

## Quick start (a `ready` Linux + NVIDIA host)

```text
# 1. Probe the target (read-only):
python3 scripts/modelangelo_env_probe.py --format md --output configs/site_config.local.md

# 2. Personal install, pinned tag, into a conda env named model_angelo,
#    with weights to a chosen cache (confirm first):
bash scripts/install_modelangelo.sh --route personal --env model_angelo \
    --torch-home ~/model_angelo_weights --download-weights --yes

# 3. Verify:
bash scripts/verify_modelangelo.sh --env model_angelo --check-gpu --check-weights
```

For a **shared cluster**, set `TORCH_HOME` to a world-readable directory and use
`--route shared` (installs once, weights readable by all, plus a thin wrapper).
For **containers / SBGrid / Biowulf module**, see `references/03`. Choose the
route and flags using the references; never install before the user confirms.

## Install-route picker (one line each — detail in `references/03`)

- **Personal Linux + conda** → clone + `install_script.sh`; per-user weights.
- **Shared cluster (self-managed)** → `TORCH_HOME=/public/...` + `--download-weights` + wrapper script.
- **Container** → Docker (`Dockerfile`) or Singularity/Apptainer (`Singularity.from.scratch` / `.from.ghcr.io`).
- **SBGrid** → `sbgrid-cli install modelangelo` (Linux-64; ~17 GB incl. common files).
- **HPC module (e.g. NIH Biowulf)** → `module load model-angelo`; site sets weights/queue. Confirm the real module name with `module avail`/`module spider`.

## Reference routing

| File | Use it for |
|---|---|
| `references/00_scope_and_trust.md` | Scope, confirmation model, trust ladder, license, the "installer ≠ validator" boundary |
| `references/01_source_map.md` | Which source backs which claim; version/currency notes |
| `references/02_config_session_and_environment.md` | Config-first state machine, staleness, identity binding, probe usage |
| `references/03_installation_routes.md` | The five routes step by step (personal / shared / container / SBGrid / HPC module) |
| `references/04_weights_and_cache.md` | `setup_weights`, bundles, ESM-1b, exact cache paths, `TORCH_HOME`, disk planning |
| `references/05_cli_and_verification.md` | Subcommand surface + post-install smoke tests; what "working" means |
| `references/06_troubleshooting.md` | Install/conda/torch/CUDA/weights/`hhblits` failure modes |
| `references/07_codex_and_integration.md` | Codex portability of this skill + RELION 5 / pipeline integration |

## Local config privacy

`configs/site_config.local.md` is a **per-environment, private** report
(hostname, GPU, paths). It is git-ignored and excluded from any distributed copy
of this skill. Only `configs/site_config.template.md` ships. Never commit or
package a real machine's local config.

## Portability note (Codex)

This skill is **optimized for Claude** but **Codex-compatible**: the frontmatter
is the universal `name` + `description`, the scripts are stdlib-Python / portable
bash, and `agents/openai.yaml` carries Codex UI metadata. To use it under Codex,
copy the folder into `~/.codex/skills/`. See `references/07`.
