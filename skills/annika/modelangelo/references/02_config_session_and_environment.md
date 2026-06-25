# 02 — Config session, environment & the readiness state machine

This is the enforcement core of the config-first rule. The skill must not give
concrete machine-specific commands, readiness claims, or **install / clone /
download anything** unless a current config exists AND its recorded host identity
matches the machine the user is asking about. Mutating actions additionally
require explicit user confirmation (`references/00`).

## The probe (read-only, stdlib-only)

`scripts/modelangelo_env_probe.py` gathers config facts and computes a `state`.
It is read-only and safe to run on the target:

```text
python3 scripts/modelangelo_env_probe.py --format md --output configs/site_config.local.md
```

- **Default run does nothing heavyweight or side-effecting:** no install, no
  `git clone`, no `pip`/`conda` mutation, no weight download, no `torch` import,
  no network, no directory creation. It reads `platform`/`socket`, looks up
  executables on PATH (`conda`, `mamba`, `git`, `model_angelo`, `hhblits`,
  `module`), reads `importlib.metadata` for an installed `model_angelo`, runs
  read-only `nvidia-smi` if present, inspects `conda env list` (read-only),
  computes the would-be weight-cache dir from `TORCH_HOME`/`~/.cache`, and `stat`s
  it for existing weights + free disk.
- **Opt-in heavyweight check (only when explicitly chosen):**
  - `--torch-probe` → imports `torch` in an isolated child process to report
    version + `cuda.is_available()` + device names, with a hard timeout. Never
    imported in the probe process itself.
- Other flags: `--env NAME` (conda env to look for, default
  `model_angelo`), `--torch-home PATH` (override for the cache check),
  `--timeout SECONDS`, `--format json|md`, `--output FILE`.
- The probe **never creates directories** and **redacts the home path**.
  `--output` must point into an existing directory (use `configs/`).

`configs/site_config.local.md` is **per-environment, private, git-ignored, and
never packaged**. Only `configs/site_config.template.md` ships.

## Required config identity fields

- `created_at` (ISO, UTC) + `probe_version` / `schema_version`.
- `host_identity`: hostname, OS system, release/version, architecture,
  `is_linux`, username-redaction status.
- `python`: executable (home-redacted), version, conda/mamba/micromamba present,
  conda env active, `git` present.
- `model_angelo`: executable on PATH (path) if found; package metadata version if
  importable; whether a conda env of the target name exists.
- `gpu_cuda`: `nvidia-smi` presence/result, GPU names/count, per-GPU memory
  (for the ≥8 GB recommendation), `CUDA_VISIBLE_DEVICES` presence.
- `torch`: probe state (`not_run` / `ok` / `failed` / `timeout`) + version +
  `cuda_available` only if safely captured in a subprocess.
- `weights`: `TORCH_HOME` value (or unset), the computed cache dir
  (`$TORCH_HOME/hub` or `~/.cache/torch/hub`), presence of
  `checkpoints/model_angelo_v1.0/{nucleotides,nucleotides_no_seq}/success.txt`
  and `checkpoints/esm1b_t33_650M_UR50S.pt`, and free disk at the cache target.
- `external`: `hhblits` (hhsuite) on PATH (optional, for the HHblits ID path);
  `module` command present (HPC).
- `source_basis`: the pinned commit the skill is grounded on.

## State definitions (installation-oriented)

- **`ready`** — A Linux target with the prerequisites to install: `conda` (or
  `mamba`) present, `git` present, ≥~10–15 GB free at the weight-cache target,
  and an NVIDIA GPU visible; **or** ModelAngelo is already installed
  (`model_angelo` on PATH or package metadata present). The skill may, **after
  the user confirms**, run `install_modelangelo.sh`, fetch weights, and verify.
  The official installer is idempotent, so re-running on an existing install is
  safe.
- **`partial`** — Installable, but a non-fatal prerequisite is missing or
  untested. Examples: no NVIDIA GPU detected (install works, but *building* is
  impractical on CPU and must be explicitly accepted); a GPU smaller than the
  recommended ~8 GB (may OOM when building); `conda` present but `git`
  missing; tight disk at the cache target; `TORCH_HOME` unset (weights would land
  in per-user `~/.cache/torch` rather than a chosen/shared dir); torch/CUDA not
  probed. Name the gap, offer to address it **with confirmation**, then install.
- **`blocked`** — A fatal mismatch for the official route: a **non-Linux host**
  (macOS/Apple Silicon, Windows). Upstream targets Linux + NVIDIA/CUDA and SBGrid
  ships Linux-64 only; there is no supported macOS build. Explain the blocker and
  the real paths: a Linux workstation, an HPC module (Biowulf/SBGrid), or a Linux
  container/VM. No local install.
- **`unknown`** — No usable config, required identity fields absent, or the user
  asks about a target the config does not represent. Ask to run the probe first;
  give only general (non-machine) guidance until then.
- **`stale`** — A prior config exists but cannot be trusted. **Treat as
  `unknown`** for concrete advice.

## Staleness rules (any one ⇒ stale)

1. `created_at` older than **14 days** for general advice, or older than **24
   hours** for an actual install / weight download / HPC planning.
2. Hostname / OS / arch in the config does not match the target described.
3. The user provides a different conda setup, `TORCH_HOME`, env name, or cluster
   than the config recorded.
4. Required identity fields missing, or `schema_version` older than this skill
   requires (current: `0.1.0`).
5. A torch probe timed out/failed and the user now asks for a readiness claim.

## How the probe computes `state` (deterministic)

Implemented in `determine_state()`. Fatal blockers dominate; otherwise any
untested/absent prerequisite downgrades `ready → partial`:

1. If host OS can't be determined → `unknown`.
2. **Blocker** (→ `blocked`): not Linux (and ModelAngelo not already installed).
3. If `model_angelo` already installed → `ready` (with a note to verify; weight
   presence may still flag a `partial`-style follow-up to fetch weights).
4. **Partials** (→ `partial` if no blocker): no `conda`/`mamba`; no `git`; no
   NVIDIA GPU; free disk below the weight threshold at the cache target;
   `TORCH_HOME` unset; torch `not_run`.
5. Otherwise → `ready`.

This makes the gate deterministic and testable. Expected: a Mac mini (Darwin,
no install) → **`blocked`**; a Linux host with conda+git+GPU+disk and no install
→ **`ready`** (ready to install); the same host already running ModelAngelo →
**`ready`** (verify/use).

## Identity binding (don't trust a pasted config blindly)

If a user pastes or points at a config, confirm its `host_identity` (hostname +
OS/arch + any executable path + package version) matches the machine in question
and that `created_at` is within the staleness window. On any mismatch → treat as
`stale`/`unknown` and re-probe the real target. A config for machine A never
licenses advice for machine B.

## First-response decision (pseudosteps)

```text
[config-state gate]
1. Config whose host_identity matches the target, within the staleness window?
   - No  -> state = unknown (or stale). Run the read-only probe on the target.
            Give general (non-machine) explanation only until a config exists.
   - Yes -> read its `state`.
2. state == blocked -> explain (non-Linux); point to Linux workstation / HPC
                       module / container. No local install.
   state == partial -> name the missing prerequisite; offer to address it
                       (install conda/git, set TORCH_HOME, free disk, accept
                       CPU-only) WITH confirmation; then install.
   state == ready   -> pick the route, echo the exact install command, and run
                       install_modelangelo.sh ONLY after the user confirms; then
                       verify_modelangelo.sh.
```
