# 02 — Config session, environment & device support

This is the skill's heart. **No concrete Topaz advice before this is satisfied.**

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
# filesystem-only (skip topaz --version/--help): add --no-topaz-exec
```
The probe **never installs anything and never runs a Topaz compute job**. It only
launches inert metadata subprocesses and writes the single `--output` file.

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
**Topaz v0.3.20 dispatches to CUDA or CPU only. There is NO MPS path.**

Evidence (all at commit `58fe5237`):
- `topaz/cuda.py set_device()` only consults `torch.cuda` (`torch.cuda.is_available()`,
  `torch.cuda.set_device`). On failure it warns `CudaWarning` and falls back to CPU.
- Tensor/model placement is `.cuda()` guarded by a `use_cuda` bool
  (`training.py`, `extract.py`, `denoise.py`, `filters.py`).
- `grep -i "mps|backends.mps"` over `topaz/` → **0 matches**.
- Models load with `map_location='cpu'` (`topaz/model/utils.py`).
- README Prerequisites: *"An Nvidia GPU with CUDA support for GPU acceleration."*

Therefore:

| Field | Value | Meaning |
|---|---|---|
| `topaz_cpu_supported` | **true** | CPU always works (and is the fallback). |
| `topaz_cuda_supported` | **true** | Used only when an NVIDIA GPU + CUDA-enabled torch are present. |
| `topaz_mps_supported` | **false** | Apple-Silicon GPU is **never** used, even if PyTorch reports MPS available. |

**Do NOT infer Topaz MPS support from `torch.backends.mps.is_available()`.** That flag
describes the framework only; Topaz ignores MPS. The probe reports the torch MPS flag
separately under `devices.torch.mps_available` with this exact caveat.

### Apple Silicon / arm64 Mac reality
- Topaz runs **CPU-only**. The M-series GPU gives no Topaz speedup.
- `--device 0` (default for train/extract/denoise) will request a GPU, find none,
  emit a `CudaWarning`, and fall back to CPU. Pass **`-d -1`** to select CPU cleanly.
- CPU **denoise**, **extract** (with bundled models), **preprocess**, and **format
  conversion** are feasible. CPU **training** is possible but slow — prefer a CUDA box
  or cloud GPU for training-heavy work.
- Heavy work is better on a Linux + NVIDIA machine or HPC/cloud.

## "Topaz not installed" degradation path (most likely first scenario)
When `topaz.installed=false` (trust-ladder #1 absent):
- Keep `validation_status=partial`; `blocked_capabilities` includes
  `concrete_command_generation_with_real_paths`, `topaz_job_execution`,
  `local_binary_behavior_validation`.
- You MAY explain Topaz, install options, workflows, and placeholder templates.
- You MUST label every workflow/command answer **"NOT validated against a local
  Topaz executable"** and must NOT invent a version or device fact.
- Offer install next steps from `09_troubleshooting.md` (still requires confirmation).

## Python-version gotcha
Topaz supports Python **3.8–3.13**. If the active interpreter is outside that range
(e.g. this machine's 3.14.x), an install into it may fail — recommend a dedicated
conda/venv at a supported version before any install.
