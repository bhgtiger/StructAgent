# ModelAngelo site config — TEMPLATE (ships with the skill)

This is the **distributable template**. The real, filled-in report is
`site_config.local.md` — **per-environment, private, git-ignored, and never
packaged**. Generate the local report **on the target machine**:

```text
python3 scripts/modelangelo_env_probe.py --format md --output configs/site_config.local.md
```

The probe is read-only by default (no install / clone / pip / conda /
weight-download / torch-import / network / mkdir), redacts the home path, and
never creates directories. See `references/02_config_session_and_environment.md`
for the state machine and staleness rules.

Schema version this template/skill expects: **0.1.0**. A report with an older
schema, missing identity fields, or a host that doesn't match the user's target
is treated as `stale`/`unknown`.

---

## Fields a valid report must contain

| Field group | Fields |
|---|---|
| meta | `created_at` (ISO/UTC), `probe_version`, `schema_version`, `state`, `state_reasons`, `source_basis` |
| host_identity | hostname, os_system, os_release, os_version, machine/arch, `is_linux`, username redacted |
| python | executable (home-redacted), version, conda/mamba present, git present, conda env active, package managers |
| model_angelo | already installed?, executable on PATH, package version, conda env present |
| gpu_cuda | nvidia-smi present, gpu_count, gpu names, max GPU mem (GB), `CUDA_VISIBLE_DEVICES` set |
| weights | TORCH_HOME set/value, cache root source, hub dir, nucleotides / nucleotides_no_seq / esm1b present, free disk (GB) |
| external | hhblits (hhsuite) present, module command present, sbgrid present |
| torch | probe state (`not_run`/`ok`/`failed`/`timeout`), version, cuda_available (only if safely captured) |

## State (one of)

- `ready` — Linux target with conda + git + an NVIDIA GPU + enough free disk; **or** ModelAngelo already installed. The skill may install / fetch weights / verify **after the user confirms** (`references/00`).
- `partial` — installable but a non-fatal prerequisite is missing/untested (no GPU → CPU-only must be accepted; no git; tight disk; `TORCH_HOME` unset; torch/CUDA not probed). Address the named gap with confirmation, then install.
- `blocked` — fatal mismatch: non-Linux host (macOS/Apple Silicon, Windows) with no existing install. Use a Linux box / HPC module / Linux container.
- `unknown` — no usable config / missing identity / asking about an unrepresented target.
- `stale` — prior config no longer trustworthy (age/identity/path change); treat as `unknown`.

## Filled-report skeleton (illustrative placeholders — not a real machine)

```text
created_at:     <ISO-8601 UTC>
probe_version:  0.1.0
schema_version: 0.1.0
state:          <ready|partial|blocked|unknown|stale>
source_basis:   commit 994945bdfa6e5368e0d62349a47792f4864eebc3   (v1.0.18)

host_identity:  hostname=<...> os_system=<Linux|Darwin|...> arch=<x86_64|arm64> is_linux=<yes|no>
python:         executable=<~/...> version=<3.x> conda_present=<yes|no> git_present=<yes|no>
model_angelo:   installed=<yes|no> exe=<~/.../model_angelo|n/a> version=<1.0.18|n/a> env_present=<yes|no>
gpu_cuda:       nvidia_smi=<yes|no> gpu_count=<N> max_mem_gb=<11.0|...> gpus=<names|none>
weights:        torch_home_set=<yes|no> hub_dir=<.../torch/hub> nucleotides=<yes|no> esm1b=<yes|no> free_gb=<N>
external:       hhblits=<yes|no> module=<yes|no> sbgrid=<yes|no>
torch:          state=<not_run|ok|failed|timeout> version=<2.9.1|n/a> cuda_available=<yes|no|n/a>
state_reasons:  - <human-readable reasons from determine_state()>
```

> Reminder: never commit or package a real `site_config.local.md`. It records a
> specific machine's environment. Only this template is distributable.
