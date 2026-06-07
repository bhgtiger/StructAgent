# 02 — Config session, environment & the readiness state machine

This is the enforcement core of the config-first rule. The skill must not give concrete machine-specific commands, readiness claims, scheduler/CryoSPARC path advice, or **run / install / download anything** unless a current config exists AND its recorded host identity matches the machine the user is asking about. Mutating actions additionally require explicit user confirmation (`references/00`).

## The probe (read-only, stdlib-only)

`scripts/deepemhancer_env_probe.py` gathers config facts and computes a `state`. It is read-only and safe to run yourself on the target machine:

```text
python3 scripts/deepemhancer_env_probe.py --format md --output configs/site_config.local.md
```

- **Default run does nothing heavyweight or side-effecting:** no DeepEMhancer call, no TensorFlow import, no network, no install, no map processing, no model download, no `chmod`, no scheduler, no CryoSPARC. It reads `importlib.metadata`, looks up executables on PATH, runs read-only `nvidia-smi` if present, and stats model files.
- **Opt-in heavyweight checks (only when explicitly chosen):**
  - `--live-help` → runs `deepemhancer --version` and `deepemhancer -h` only, in an isolated subprocess, hard timeout, `CUDA_VISIBLE_DEVICES=""`.
  - `--tensorflow-probe` → probes TensorFlow version/GPU in an isolated child process (never imported in the probe process).
- Other flags: `--deepemhancer-path PATH`, `--model-dir PATH_OR_HD5`, `--timeout SECONDS`, `--format json|md`, `--output FILE`.
- The probe **never creates directories** and **redacts the home path**. `--output` must point into an existing directory (use `configs/`).

`configs/site_config.local.md` is **per-environment, private, git-ignored, and never packaged**. Only `configs/site_config.template.md` ships. See the repo `.gitignore`.

## Required config identity fields

A usable config report must record:

- `created_at` (ISO, UTC) and `probe_version` / `schema_version`.
- `host_identity`: hostname, OS system, OS release/version, architecture, `is_linux`, username-redaction status.
- `python`: executable (home-redacted), version, conda/venv indicators, package managers present.
- `deepemhancer`: executable path if found/provided; package metadata version if available; optional live `--version`/`-h` result with exit code, timeout flag, stdout/stderr excerpts.
- `tensorflow`: probe state (`not_run` / `ok` / `failed` / `timeout`) plus version/GPU devices only if safely captured in a subprocess.
- `gpu_cuda`: `nvidia-smi` presence/result, GPU names/count, `CUDA_VISIBLE_DEVICES` presence (no raw env dump).
- `models`: default model dir, user-provided dir if any, existence of expected files (`deepEMhancer_tightTarget.hd5`, `deepEMhancer_wideTarget.hd5`, `deepEMhancer_highRes.hd5`, optional `deepEMhancer_masked.hd5`); no download attempt.
- `source_basis`: the source commit the skill is grounded on.

## State definitions

- **`ready`** — Linux/compatible target; DeepEMhancer executable or package metadata present; model dir contains required files for at least tight/wide/highRes (or a valid user-specified `.hd5`); TensorFlow import/live help did not fail when run; **an NVIDIA GPU is visible** (the probe downgrades a no-GPU host to `partial`, since CPU-only is very slow and must be explicitly accepted); config age and host identity current. The skill may plan and — **after the user confirms** — RUN `deepemhancer` on the local map (`scripts/run_deepemhancer.sh`). A successful run still ≠ a better map.
- **`partial`** — Some necessary facts present but at least one non-fatal required runtime detail is missing/untested (e.g. executable found but live help skipped; GPU visible but TensorFlow not tested; model path given but not all optional models found). Explain the uncertainty, name the missing check, and offer to complete the config (probe TF/GPU, install, download models) **with confirmation** before running. Do not assert runtime readiness without those checks.
- **`blocked`** — A known **fatal mismatch**: non-Linux development host for execution; no DeepEMhancer executable/package; missing required model files for the intended workflow; TensorFlow/live-help failure indicating an unusable install; no GPU when GPU execution is requested; or an explicit CUDA/driver conflict. May only explain blockers and the next safe checks.
- **`unknown`** — No usable config exists, required identity fields are absent, or the user asks about a target the current config does not represent. Must ask for / run the config session first.
- **`stale`** — A prior config exists but cannot be trusted (see staleness rules). **Treat `stale` as `unknown`** for concrete advice.

## Staleness rules (any one ⇒ stale)

1. `created_at` older than **14 days** for general advice, or older than **24 hours** for execution / HPC / CryoSPARC-wrapper planning.
2. Hostname / OS / arch in the config does not match the target the user describes.
3. The user provides a different executable path, conda env, model directory, or server than the config recorded.
4. Required identity fields are missing, or the probe `schema_version` is older than this skill requires (current: `0.1.0`).
5. Live help / TensorFlow probes timed out or failed and the user now asks for concrete commands or a readiness claim.

## How the probe computes `state` (deterministic)

Implemented in `determine_state()` in the probe. Fatal blockers dominate; otherwise any untested required fact downgrades `ready → partial`:

1. If host OS can't be determined → `unknown`.
2. **Blockers** (→ `blocked`): not Linux; no executable AND no package; required model dir/`tightTarget.hd5` absent (and not a valid custom `.hd5`); TensorFlow probe `failed`/`timeout`; requested live `--version`/`-h` failed or timed out.
3. **Partials** (→ `partial` if no blocker): package present but no PATH entry point; no NVIDIA GPU (CPU-only is very slow, must be accepted); TensorFlow `not_run`; live help not run; optional `masked.hd5` missing.
4. Otherwise → `ready`.

This makes the gate deterministic and testable. Confirmed both ways: a non-Linux dev host (a Mac mini) with no install and no models computes **`blocked`**; a Linux + RTX 2080 Ti host with DeepEMhancer 0.17, TF 2.10, and all four `.hd5` models computes **`ready`** (the first real `ready` report — see `references/09`).

## Identity binding (don't trust a pasted config blindly)

If a user pastes or points at a config, confirm its `host_identity` (hostname + OS/arch + executable path + package version) matches the machine the question is about, and that `created_at` is within the staleness window. On any mismatch → treat as `stale`/`unknown` and ask to re-run the probe on the real target. A config for machine A never licenses advice for machine B.

## First-response decision (pseudosteps)

```text
[config-state gate]
1. Is there a config whose host_identity matches the user's target, within the staleness window?
   - No  -> state = unknown (or stale). Run the read-only probe on the target / ask for a fresh report.
            Give general (non-machine) explanation only until a config exists.
   - Yes -> read its `state`.
2. state == blocked  -> explain blockers + the next fix (install via setup script, fix CUDA, place models).
                        No map run until resolved.
   state == partial  -> name the missing check; offer to complete it (probe TF/GPU, install,
                        download models) WITH confirmation; then plan/run.
   state == ready    -> plan the command with real paths, echo it back, and RUN it via
                        run_deepemhancer.sh ONLY after the user confirms.
```
