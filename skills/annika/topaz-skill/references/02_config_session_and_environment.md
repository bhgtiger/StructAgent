# 02 — Config session, environment & device support

This is the skill's heart. **Run the read-only probe first.** Once it reports a fresh
`valid` state for the current host, concrete commands with the user's real paths are
allowed, and — after explicit user confirmation — so is running real Topaz jobs.

## When to (re)run the config session
Run the read-only probe (or read a fresh existing report) if ANY of:
- No `site_config.local.md`/`.json` or probe output exists.
- `validation_status` is `stale`/`partial`/`blocked`, or `topaz.installed=false`.
- `now > stale_after` (default TTL **14 days**).
- The topaz executable path/version changed.
- The active Python/conda env changed.
- OS / GPU / driver state changed.
- The user switched target project path.

## How to run it (read-only, ask first)
```
python3 scripts/topaz_env_probe.py --output <project>/site_config.local.md
# optional framework GPU probe (isolated subprocess): add --check-torch
# filesystem-only (skip topaz --version/--help):       add --no-topaz-exec
```
The probe **never installs anything and never runs a Topaz compute job**. It only
launches inert metadata subprocesses (`topaz --version` / `topaz --help`, skippable with
`--no-topaz-exec`; and — only with `--check-torch` — a short `import torch` probe) and
writes the single `--output` file. All three flags are implemented
(`scripts/topaz_env_probe.py`: `--output`, `--check-torch`, `--no-topaz-exec`).

> Probe note: the current build's subcommand parser scrapes the grouped top-level
> `--help` and can list group labels/noise instead of the real commands
> (a known probe parser limitation). Once that parser is fixed,
> `subcommands_captured` will list the real commands
> (`train, segment, extract, precision_recall_curve, downsample, normalize, preprocess,
> denoise, denoise3d, convert, split, particle_stack, train_test_split, gui` plus the
> deprecated set). The real command set is confirmed in
> `[validated topaz 0.3.20 — captured: topaz.help.txt]`.

## Config schema (fields the skill relies on)
```yaml
generated_at: ISO-8601
hostname: string
os: {system, release, arch, is_apple_silicon, macos_version?}
shell: {SHELL, TERM}
package_managers: {conda, mamba, micromamba, pip, active_conda_env, conda_prefix}
python: {executable, version, active_env, topaz_python_requires, in_topaz_supported_range}
topaz:
  installed: bool
  executable: string|null
  version: string|null
  version_matches_source_evidence: bool|null
  help_captured: bool
  subcommands_captured: [string]
devices:
  nvidia: {nvidia_smi: available|missing|error, gpus: [..]}
  torch: {checked, torch_available, cuda_available, mps_available, ...}   # only if --check-torch
  topaz_cpu_supported:  true|false|unknown   # SOURCED, not torch-inferred
  topaz_cuda_supported: true|false|unknown
  topaz_mps_supported:  true|false|unknown
  usability_here: {cpu_usable_here, cuda_usable_here, mps_usable_here, ...}
source_snapshot: {repo_url, commit_or_tag, commit, fetched_at}
validation_status: valid|stale|partial|blocked
stale_after: ISO-8601
blocked_capabilities: [string]
notes: [string]
```

## DEVICE SUPPORT — the MPS question, settled by source
**Topaz v0.3.20 dispatches to CUDA or CPU only. There is NO MPS path.** This is a general
per-platform fact driven by source, applied per host by the probe.

Evidence (all `[sourced 0.3.20 @ 58fe5237]`):
- `topaz/cuda.py set_device()` only consults `torch.cuda` (`torch.cuda.is_available()`,
  `torch.cuda.set_device`). On failure it warns `CudaWarning` and falls back to CPU.
- Tensor/model placement is `.cuda()` guarded by a `use_cuda` bool
  (`training.py`, `extract.py`, `denoise.py`, `filters.py`).
- `grep -i "mps|backends.mps"` over `topaz/` → **0 matches**.
- Models load with `map_location='cpu'` (`topaz/model/utils.py`).
- README Prerequisites: *"An Nvidia GPU with CUDA support for GPU acceleration."*

Confirmed live on a Linux + NVIDIA GPU host: `topaz_mps_supported = False`,
`cuda_usable_here = True` `[smoke: the probe]`.

Therefore:

| Field | Value | Meaning |
|---|---|---|
| `topaz_cpu_supported` | **true** | CPU always works (and is the fallback). |
| `topaz_cuda_supported` | **true** | Used only when an NVIDIA GPU + CUDA-enabled torch are present. |
| `topaz_mps_supported` | **false** | Apple-Silicon GPU is **never** used, even if PyTorch reports MPS available. |

**Do NOT infer Topaz MPS support from `torch.backends.mps.is_available()`.** That flag
describes the framework only; Topaz ignores MPS. The probe reports the torch MPS flag
separately under `devices.torch.mps_available` with this exact caveat.

### Per-command device defaults
`[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt]`. `-d/--device`: `>=0` selects a
GPU number, `<0` selects CPU (e.g. `-1`).

| Command | `-d` default | Captured help |
|---|---|---|
| `train` | **0** (GPU 0; `-1` forces CPU) | `topaz.train.help.txt` |
| `segment` | **0** ("GPU if available"; `<0` = CPU) | `topaz.segment.help.txt` |
| `extract` | **0** (`<0` = CPU; default not printed in help text — value per ground truth) | `topaz.extract.help.txt` |
| `denoise` | **0** (GPU 0; `-1` forces CPU) | `topaz.denoise.help.txt` |
| `normalize` | **-1** (CPU; `>=0` = GPU number) | `topaz.normalize.help.txt` |
| `preprocess` | **-1** (CPU; `>=0` = GPU number) | `topaz.preprocess.help.txt` |
| `denoise3d` | **-2** (multi-GPU; `>=0` single GPU, `-1` CPU) | `topaz.denoise3d.help.txt` |

Note: `preprocess` defaults to `-1` (CPU) just like `normalize` — `topaz.preprocess.help.txt`
line 27–29 prints `default: -1`. If `references/03_cli_reference.md` states the `-1` default
applies only to `normalize`, that is wrong; it applies to `preprocess` too.

### Apple Silicon / no-NVIDIA host reality (probe-driven)
When the probe reports **Apple Silicon / no NVIDIA GPU**:
- Topaz runs **CPU-only**. An M-series (or any non-NVIDIA) GPU gives no Topaz speedup.
- The GPU-default commands (`train`, `segment`, `extract`, `denoise` default `-d 0`) will
  request a GPU, find none, emit a `CudaWarning`, and fall back to CPU. Pass **`-d -1`**
  to select CPU cleanly (use `-d -1` whatever the per-command default).
- CPU **denoise**, **extract** (with bundled models), **preprocess**, and **format
  conversion** are feasible. CPU **training** is possible but slow — prefer a Linux + CUDA
  box or cloud GPU for training-heavy work.

## Per-host "Topaz not installed" branch
This is the **per-host uninstalled branch** for hosts where the probe reports
`topaz.installed=false`. It is NOT the skill's default posture — Topaz is installed and
validated on Linux + NVIDIA (`[validated topaz 0.3.20]`, `[smoke]`).

When `topaz.installed=false` **on this host** (trust-ladder #1 absent on this machine):
- Keep `validation_status=partial`; `blocked_capabilities` includes
  `concrete_command_generation_with_real_paths`, `topaz_job_execution`,
  `local_binary_behavior_validation`.
- You MAY explain Topaz, install options, and workflows.
- Label answers **"Topaz not installed on this host"** — do NOT label them globally invalid
  (the CLI facts here are still `[validated topaz 0.3.20 — captured: ...]`). Do not invent a
  version or per-host device fact for the uninstalled machine.
- Offer install next steps from `09_troubleshooting.md` (still requires confirmation).

When `topaz.installed=true` **and** a version was captured → `validation_status=valid` →
concrete commands with the user's real paths are allowed, and real jobs MAY run after
explicit user confirmation.

## Python-version gotcha
Topaz supports Python **3.8–3.13** (`python_requires='>=3.8,<=3.13'`,
`[sourced 0.3.20 @ 58fe5237: setup.py:45]`; README says 3.8–3.12 currently tested). If the
active interpreter is outside **3.8–3.13**, an install into it may fail — recommend a
dedicated conda/venv at a supported version before any install.

## ENV gotcha — torch CUDA build
The default PyPI `torch` is now a **CUDA-13 (cu130)** build, which reports `cuda=False` on a
CUDA-12 driver (observed during validation: torch `2.12+cu130` → `cuda=False`). Pin a **cu12x**
build instead (e.g. `torch==2.9.1+cu128`), which gave `cuda=True`
`[smoke]`. Run the probe with **`--check-torch`** to confirm the
torch CUDA build (`devices.torch.cuda_available` and the reported build string) before
relying on GPU execution. See `09_troubleshooting.md` for the install/pin recipe.
