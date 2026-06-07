# DeepEMhancer site config — TEMPLATE (ships with the skill)

This is the **distributable template**. The real, filled-in report is
`site_config.local.md` — which is **per-environment, private, git-ignored, and
never packaged**. Generate the local report **on the target machine**:

```text
python3 scripts/deepemhancer_env_probe.py --format md --output configs/site_config.local.md
```

The probe is read-only by default (no DeepEMhancer/TensorFlow/network/install/map
I/O), redacts the home path, and never creates directories. See
`references/02_config_session_and_environment.md` for the state machine and
staleness rules.

Schema version this template/skill expects: **0.1.0**. A report with an older
schema, missing identity fields, or a host that doesn't match the user's target
is treated as `stale`/`unknown`.

---

## Fields a valid report must contain

| Field group | Fields |
|---|---|
| meta | `created_at` (ISO/UTC), `probe_version`, `schema_version`, `state`, `state_reasons`, `source_basis` |
| host_identity | hostname, os_system, os_release, os_version, machine/arch, `is_linux`, username redacted |
| python | executable (home-redacted), version, implementation, conda/venv indicators, package managers present |
| deepemhancer | package metadata found + version, executable source/path/exists, (optional) live `--version`/`-h` exit code + timeout |
| tensorflow | probe state (`not_run`/`ok`/`failed`/`timeout`), version, GPUs (only if safely captured) |
| gpu_cuda | nvidia-smi present, gpu_count, gpu names, `CUDA_VISIBLE_DEVICES` set |
| models | default model dir + exists, checked dir, per-file presence of `deepEMhancer_{tightTarget,wideTarget,highRes,masked}.hd5`, missing-required list |

## State (one of)

- `ready` — current, matching, Linux, installed, required models present, TF/live-help not failing, NVIDIA GPU visible (a no-GPU host is `partial`; CPU-only is very slow and must be explicitly accepted). The skill may run a map **after the user confirms** (`references/00`).
- `partial` — some required runtime detail untested/missing; complete the named check (probe TF/GPU, install, models) with confirmation before running.
- `blocked` — known fatal mismatch (non-Linux, no install, missing required models, TF/CUDA failure, no GPU when GPU required).
- `unknown` — no usable config / missing identity / asking about an unrepresented target.
- `stale` — prior config no longer trustworthy (age/identity/path change); treat as `unknown`.

## Filled-report skeleton (illustrative placeholders — not a real machine)

```text
created_at:     <ISO-8601 UTC>
probe_version:  0.1.0
schema_version: 0.1.0
state:          <ready|partial|blocked|unknown|stale>
source_basis:   commit 961f028ca609017990de4473ab368cf1787e8282

host_identity:  hostname=<...> os_system=<Linux|Darwin|...> arch=<x86_64|arm64> is_linux=<yes|no>
python:         executable=<~/...> version=<3.x> conda_env_active=<yes|no>
deepemhancer:   package_found=<yes|no> version=<0.16|0.17|...> executable=<~/.../deepemhancer|n/a>
tensorflow:     state=<not_run|ok|failed|timeout> version=<2.10|2.12|n/a>
gpu_cuda:       nvidia_smi=<yes|no> gpu_count=<N> gpus=<names|none>
models:         dir=<~/.local/share/deepEMhancerModels/production_checkpoints|...>
                tightTarget=<yes|no> wideTarget=<yes|no> highRes=<yes|no> masked=<yes|no>
state_reasons:  - <human-readable reasons from determine_state()>
```

> Reminder: never commit or package a real `site_config.local.md`. It records a
> specific machine's environment. Only this template is distributable.
