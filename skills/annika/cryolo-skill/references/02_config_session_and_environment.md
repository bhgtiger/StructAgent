# 02 · Config session and environment

This is the heart of the config-first rule. Before any concrete command, device/support
claim, or workflow recommendation, a **current** local config report must exist
(`configs/site_config.local.md` or a JSON probe report). See `SKILL.md §0`.

The config report is the gate, not a ceiling. Once it exists and reports a `supported`
or `partial` machine, the downstream path yields **concrete commands with the user's real
paths** and — **after explicit user confirmation** — **real crYOLO execution**, not
placeholders. crYOLO is installed and VALIDATED on Linux + NVIDIA at the pinned version
(crYOLO 1.9.9 / TensorFlow 1.15.5 / keras 2.3.1; `_versions.txt`), with an
end-to-end GPU smoke run on a Linux + NVIDIA GPU host (the validation run).

## Verbatim platform/support evidence (the only basis for support claims)

From the crYOLO installation docs,
<https://cryolo.readthedocs.io/en/stable/installation.html>, fetched **2026-06-05**
(source pin `MPI-Dortmund/cryolo` `1.9.9` / `30039bde34d65c179541568b0c27f09916ac5652`):

> At our institute in Dortmund, crYOLO is running on the following operation systems:
> Ubuntu 18.04 LTS, Ubuntu 20.04, CentOS 7.
> We don't test it but it should run on Windows as well.
> Moreover the following GPUs are used: NVIDIA Titan V, NVIDIA GTX 1080, NVIDIA GTX
> 1080Ti, NVIDIA RTX 2080 TI, NVIDIA GV 100.
> **As the GPU accelerated version of tensorflow does not support MacOS, crYOLO does not
> support it either.**
> crYOLO depends on CUDA Toolkit and the cuDNN library. These will be automatically
> installed during crYOLO installation.

**Interpretation rule:** official installation requirements are authoritative for
*support status*. The macOS-unsupported fact above stays true and sourced, but it is a
**per-platform** statement applied by the probe to whatever host it runs on — not a claim
that any particular machine is "blocked". On a platform the docs do cover (Linux + NVIDIA),
a local install that runs is reported as **supported** (confirmed: probe `status=supported`
in the validation run). On macOS the same logic yields **blocked**.
(Closes Audit-A P0-1.)

## The config session must answer

1. What OS/arch is this machine?
2. Is it an officially supported platform per the captured docs?
3. Is crYOLO installed? Which scripts/package versions are visible?
4. Which Python/conda environment is active?
5. Is an NVIDIA GPU / CUDA visible? If not, what is blocked?
6. Is macOS / Apple Silicon detected, and how does that affect use?
7. Which skill actions are available here? On a `supported`/`partial` machine the
   available actions include: explain-only, install-planning, **concrete commands built
   with the user's real paths**, and — **after explicit user confirmation** — **real
   crYOLO execution** (config/train/predict/evaluation). On a `blocked` machine (e.g.
   macOS) execution is not offered; the skill stays in explain/plan mode for that host.

The read-only probe `scripts/cryolo_env_probe.py` answers 1–6 and computes
`support_assessment`; question 7 follows from the safety ladder (`00_scope_and_trust.md`),
gated by (a) the per-machine probe verdict and (b) confirmation before touching real data.

## support_assessment decision rules (P1-2)

The probe maps detected facts → `status`, with each `reason` citing the installation
source above. These rules are grounded **only** in captured docs:

| Detected | status | Rationale (sourced) | blocked_capabilities |
|---|---|---|---|
| macOS (any arch) | **blocked** | Docs: crYOLO does not support macOS (TF GPU unsupported on macOS) | config/train/predict/evaluation/GUI execution |
| Apple Silicon (arm64) | **blocked** (+ note) | Apple GPU/Metal/MPS ≠ NVIDIA CUDA; does not satisfy CUDA/cuDNN dependency | as above |
| Linux + NVIDIA GPU (nvidia-smi lists ≥1) | **supported** *(CONFIRMED by smoke)* | Matches docs (Ubuntu/CentOS + NVIDIA + CUDA/cuDNN). Probe returned `status=supported` in the validation run on an NVIDIA GPU. crYOLO's docs list the RTX 2080 Ti among officially-tested GPUs (Titan V, GTX 1080/1080Ti, RTX 2080 TI, GV 100) | none |
| Linux, no NVIDIA GPU | **partial** | Docs list NVIDIA GPUs + CUDA/cuDNN; GPU-accel may be unavailable | GPU-accelerated train/predict/evaluation |
| Windows | **partial** | Docs: "not tested … should run on Windows" → untested | officially untested platform |
| Other/unrecognized OS | **unknown** | Not covered by captured docs | platform not covered |

Overlays applied to `reasons` (never to flip the base status upward):

- If crYOLO is **not** detected → add: installation required first; this skill does not
  install software.
- If macOS **but** a crYOLO executable/package is present → add the "locally
  present/runnable but officially unsupported/untested" note. **Do not** upgrade to
  supported.

`reasons[]` must each cite the installation source. Do not invent a `reason` from any
uncaptured fact.

## Staleness rules

A config report is **stale** (must be regenerated before gated advice) when any of:

- `generated_at` is older than `stale_after_days` (default **14**), OR
- the OS / architecture changed, OR
- the active conda/venv environment changed (`CONDA_PREFIX` / `CONDA_DEFAULT_ENV` /
  `VIRTUAL_ENV`), OR
- crYOLO was installed/upgraded/removed, or its executable path changed, OR
- GPU/driver state changed (GPU added/removed, `nvidia-smi` now present/absent), OR
- the targeted docs version/pin changed.

When stale: re-run `python3 scripts/cryolo_env_probe.py ...` (with consent) or refuse
gated content and explain. Gated content now includes concrete commands and real
execution — not just templates — so a stale report blocks those too. Never reuse a stale
report for device/command advice or to authorize a run on real data.

## Config report schema (canonical; the probe emits this)

The probe emits JSON (machine-readable) and Markdown (human-readable) carrying the same
fields. Canonical shape:

```yaml
generated_at: ISO-8601 timestamp (UTC, ...Z)
probe_version: "0.1.0"
hostname: string                 # local/private
os:
  system: Darwin|Linux|Windows|<other>
  release: string
  machine: string                # e.g. arm64, x86_64
  is_macos: bool
  is_apple_silicon: bool
python:
  executable: string             # home-redacted
  version: string
  active_env: string|null
package_managers:
  conda:       {available: bool, path: string|null}
  mamba:       {available: bool, path: string|null}
  micromamba:  {available: bool, path: string|null}
  pip:         {available: bool, path: string|null}
gpu:
  nvidia_smi: missing|present|skipped|error
  nvidia_gpus: [string, ...]     # from `nvidia-smi -L`
  cuda_home: string|null
cryolo:
  installed: bool
  executable_paths: {name: path}   # only those found; home-redacted
  package_versions: {dist: version}
  help_captured: bool              # true only if a live --version succeeded
  detected_version: string|null
  version_probes: {...}            # present only under --cryolo-exec
environment_variables: {KEY: value}  # allowlist only; home-redacted
support_assessment:
  status: supported|partial|blocked|unknown
  reasons: [string, ...]           # each cites a source
  blocked_capabilities: [string, ...]
source_snapshot:
  docs_url: string
  docs_source_commit: string
  docs_source_tag: string
  grounded_on: date
validation_status: full|partial|blocked
stale_after_days: integer
safety_attestation:
  installs_performed: "none"
  downloads_performed: "none"
  network_calls: "none"
  cryolo_jobs_run: "none"
  cryolo_exec_enabled: bool
  commands_run: [{cmd, status, returncode}, ...]
```

`validation_status`: `full` only when crYOLO is installed **and** a live `--version` was
captured (`help_captured: true`); otherwise `partial`. A not-installed or unsupported
machine stays `partial` — which is correct and expected. (`probe_version: "0.1.0"` is the
probe artifact's own version and is independent of the skill's pinned crYOLO version.)

## Privacy of the local report (P1-4)

`configs/site_config.local.md` (and any `references/environment/local_env_probe_*.md`)
contain hostname, paths, and env details. They are **local/private**:

- The shipped repo does **not** include a real machine report. `site_config.local.md` in
  the repo is only a short note saying it is generated per-machine by running
  `scripts/cryolo_env_probe.py` and is not shipped; `site_config.template.md` carries the
  schema. A real report is produced locally when the user runs the probe.
- Home directory is redacted to `~` in probe output; user path segments → `<user>`.
- They are git-ignored (see `skill/cryolo_skill/.gitignore`) and excluded from any shared
  / packaged copy of the skill.
- Never upload them. The installed local skill copy may retain the file for the user's own
  machine only.

## What the probe never does

This section is about the **probe**, not the skill. The probe is deliberately read-only so
that the config gate itself never has side effects; **running crYOLO jobs happens through
the workflows (see `05_core_workflows.md`), after the probe verdict and explicit user
confirmation — not through the probe.**

No installs, downloads, or network calls; never starts crYOLO train/predict/evaluation/
GUI/napari; never enumerates user micrograph/annotation/model data; never dumps the full
environment (allowlist only). By default it does not even execute crYOLO scripts (opt-in
via `--cryolo-exec`, which still only runs `--version` with a timeout). The
`safety_attestation.commands_run` log evidences exactly which external commands ran.
