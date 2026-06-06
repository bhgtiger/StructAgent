# site_config.template.md — Topaz environment/config session

Copy to `site_config.local.md` (keep private; do not commit) OR generate it with:
```
python3 scripts/topaz_env_probe.py --output site_config.local.md            # markdown
python3 scripts/topaz_env_probe.py --output site_config.local.json --format json
```
The probe is **read-only** (no installs, no Topaz jobs, no user-data access). The
fields below mirror the probe output schema (`references/02_config_session_and_environment.md`).

```yaml
generated_at:            # ISO-8601 UTC, e.g. 2026-06-05T20:12:18Z
hostname:                # machine name
project_path:            # optional target project dir (recorded, not scanned)

os:
  system:                # Darwin | Linux | Windows
  release:               # kernel/OS release
  arch:                  # arm64 | x86_64
  is_apple_silicon:      # true|false
  macos_version:         # if Darwin

shell:
  SHELL:                 # e.g. /bin/zsh

package_managers:
  conda: {available, path}
  mamba: {available, path}
  micromamba: {available, path}
  pip: {available, path}
  active_conda_env:      # or null
  conda_prefix:          # or null

python:
  executable:            # path
  version:               # e.g. 3.10.14
  active_env:            # conda/venv name or null
  topaz_python_requires: ">=3.8,<=3.13"
  in_topaz_supported_range: true|false

topaz:
  installed:             # true|false   <-- gates concrete commands
  executable:            # path or null
  version:               # or null
  version_matches_source_evidence: true|false|null
  help_captured:         # true|false
  subcommands_captured:  # [..]

devices:
  nvidia: {nvidia_smi: available|missing|error, gpus: [..]}
  torch: {checked, torch_available, cuda_available, mps_available}   # only if --check-torch
  topaz_cpu_supported:  true|false|unknown     # SOURCED (not torch-inferred)
  topaz_cuda_supported: true|false|unknown
  topaz_mps_supported:  true|false|unknown     # v0.3.20: FALSE (no MPS path)
  usability_here:
    cpu_usable_here:     true|false
    cuda_usable_here:    true|false
    mps_usable_here:     false   # always false for Topaz

source_snapshot:
  repo_url: https://github.com/tbepler/topaz
  commit_or_tag: v0.3.20
  commit: 58fe52370f4accb8215525df2ea8f2c7ee6d340a
  fetched_at: 2026-06-05

validation_status:       # valid | stale | partial | blocked
stale_after:             # ISO-8601 (default generated_at + 14 days)
blocked_capabilities:    # [concrete_command_generation_with_real_paths, topaz_job_execution, ...]
notes:                   # [..]
```

## Interpretation rules
- `topaz.installed=false` OR `validation_status∈{partial,blocked,stale}` → gather/refresh the
  environment and offer to install Topaz if it is uninstalled-on-this-host; on
  `validation_status=valid`, concrete commands with the user's real paths AND (confirmed)
  execution are allowed. Surface `blocked_capabilities` when present.
- `topaz_mps_supported` is **false** by source (no MPS code path in topaz/ at
  `58fe5237` — [sourced 0.3.20 @ 58fe5237: topaz/]); never override from a torch MPS flag.
  If the probe reports Apple Silicon / no NVIDIA GPU, Topaz runs CPU-only; pass `-d -1`.
- Run the probe with `--check-torch` to confirm the torch CUDA build: default PyPI torch is now
  CUDA-13 (cu130) and reports `cuda_available=false` on a CUDA-12 driver — pin a cu12x build
  (e.g. `torch==2.9.1+cu128`) [smoke].
- Refresh when stale (see staleness policy in the probe output / ref 02).
