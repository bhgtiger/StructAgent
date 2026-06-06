# 02 — Config session and environment (the gate)

This is the mechanism that makes the skill **config-first**. No machine-specific
suitability claim, concrete command, or workflow recommendation may be emitted
until a **current** environment report exists for the target host.

## The report

A report is either:

- `configs/site_config.local.md` produced by `scripts/cryodrgn_env_probe.py`, or
- a probe JSON (`--format json`) / equivalent the user pasted from the target host.

It records: host OS/arch, macOS version (if any), Python (version + tested-range
flag + conda/venv), package managers (conda/mamba/micromamba/pip presence +
version), GPU/CUDA (nvidia-smi presence, GPU list, `CUDA_*` env), cryoDRGN
(executable paths, package version, optional live `--version`/help), a computed
`config_state`, its rationale, generation time, TTL, and staleness triggers.

The probe is **read-only**: it installs nothing, downloads nothing, makes no
network call, runs no cryoDRGN job, redacts the home directory to `~`, and writes
only the requested output file. See `scripts/cryodrgn_env_probe.py` and §"Probe
allowlist" below.

## Running the probe (the one action allowed pre-config)

```text
# [config-state: absent]
# Read-only probe. No installs/downloads/network/jobs; writes only the report file.
# Default: does NOT invoke cryoDRGN — only locates executables + reports Python/GPU.
python3 scripts/cryodrgn_env_probe.py --format markdown --output configs/site_config.local.md
```

```text
# [config-state: partial]
# Only when cryoDRGN is already installed on the target host, capture help-only
# CLI text (`cryodrgn --version`/`-h`, selected `cryodrgn <cmd> -h`, `cryodrgn_utils -h`).
# Still no compute: every subcommand call is terminated by `-h`.
python3 scripts/cryodrgn_env_probe.py --live-help --format json --output configs/site_config.local.json
```

> The probe snippets above are the probe itself — it is read-only (no installs,
> downloads, network, or cryoDRGN jobs; writes only the report file), so it
> carries neither `[not-run]` nor `[live-unverified]`; only the `[config-state]`
> it advances. `--live-help` was exercised on a Linux + NVIDIA GPU host (2026-06-06) and
> succeeds: it captures `cryodrgn --version`/`-h`, `cryodrgn_utils -h`, and every
> selected `cryodrgn <cmd> -h` / `cryodrgn_utils <cmd> -h`
> [src: the validation run].

Flags: `--format markdown|json`, `--output PATH`, `--live-help`,
`--selected-help CMD[,CMD...]`, `--stale-after-days N`, `--timeout SECONDS`.

If you cannot run the probe on the target host (e.g. you are on a different
machine), ask the user to run it on the target server and paste the result. Never
fabricate environment facts.

## "Current" — TTL and staleness

- **TTL:** default **14 days** (`--stale-after-days`). After
  `valid_until_utc`, treat as **stale**.
- **Invalidation triggers** (any one makes a report stale, even within TTL):
  1. OS / host change,
  2. GPU / driver / CUDA change,
  3. Python / conda environment change,
  4. cryoDRGN executable path or version change,
  5. the user states the target server changed.

When stale: behave as `absent` and ask to re-run the probe.

## State machine

```text
            no report / wrong host          report older than TTL or
                  │                            invalidation trigger
                  ▼                                   │
   ┌──────────► absent ◄───────────────── stale ◄─────┘
   │              │  (run/paste probe)       ▲
   │              ▼                          │ (env changed)
   │        probe produces a current report ─┘
   │              │
   │      ┌───────┼─────────────┬───────────────┐
   │      ▼       ▼             ▼               ▼
   │  unknown  blocked       partial          ready
   │ (probe   (absent /     (installed,      (installed, Linux,
   │  failed) unsuitable)   missing live/     NVIDIA GPU, help
   │                        GPU/scheduler)    captured)
   └────────────────────────────────────────────────────
   Gate fails CLOSED: absent / stale / unknown ⇒ no machine-specific advice.
```

`config_state` is computed by the probe (`determine_config_state`):

- **unknown** — a probe error occurred or results are ambiguous.
- **blocked** — cryoDRGN not installed (no executable and no package metadata),
  **or** the host is non-Linux, **or** no NVIDIA GPU is visible. This is a
  general, per-platform outcome, not a statement about any one machine: cryoDRGN
  4.2.1 ships the classifier `Operating System :: POSIX :: Linux`
  [src: `sources/source/cryodrgn_4.2.1/pyproject.toml`] and its installation docs
  require a Linux workstation/cluster with NVIDIA GPUs
  [src: `references/01_source_map.md` → Installation]. So on *any* host that is
  non-Linux or GPU-less, the probe returns `blocked` for compute — whether that
  host is a laptop, a macOS desktop, or a CPU-only Linux node. The skill reads
  this outcome from the per-host report; it never hardcodes a verdict.
- **partial** — cryoDRGN installed on Linux + NVIDIA GPU, but live CLI help not
  captured and/or scheduler/project details unknown.
- **ready** — cryoDRGN installed; Linux + NVIDIA GPU; live help captured.

> `absent` and `stale` are **not** emitted by the probe — they are determined by
> the skill when no current report file exists or it has expired. The probe
> always writes a *current* report describing the host it ran on.

## Config-state → capability table (authoritative)

| config_state | Allowed | Forbidden |
|---|---|---|
| **absent** | general (non-machine-specific) explanation; offer to run/paste the probe | machine-specific suitability; concrete commands; workflow recommendations |
| **stale** | same as absent; ask to re-run the probe | same as absent |
| **blocked** | explain the blockage with doc citations (`pyproject` Linux classifier + install docs); generic placeholder templates `[config-state: blocked] [VALIDATED: cryoDRGN 4.2.1]`; recommend a suitable Linux+NVIDIA target server / next config step | concrete commands for the blocked capability; any execution on the blocked host |
| **partial** | everything `ready` allows **except** GPU-/scheduler-dependent execution: concrete commands with the user's real paths (`[config-state: partial] [VALIDATED: cryoDRGN 4.2.1]`), and CPU-safe execution after explicit confirmation (e.g. `downsample`, parse/`write_*`, `view_header`); request `--live-help` to reach `ready` | running training/abinit/analyze/backproject/eval_* or launching dashboard/filter until GPU + live help are confirmed; scheduler/GPU claims not captured |
| **ready** | concrete commands with the user's real paths (`[config-state: ready] [VALIDATED: cryoDRGN 4.2.1]`, citing the captured help file), **and EXECUTION after explicit user confirmation** — `train_vae`/`train_nn`/`train_dec`, `abinit`, `analyze`, `backproject_voxel`, `eval_vol`/`eval_images`, `fsc`, and the `cryodrgn_utils` writers/parsers. `dashboard` and `filter` are interactive/served — launch them ONLY with confirmation, and tell the user the bind host/port from the captured help (`cryodrgn dashboard` default `127.0.0.1:5050` [src: `cryodrgn.dashboard.help.txt`]) | blind installs/downloads/uploads; unconfirmed destructive ops (overwriting/deleting the user's stacks, `.pkl`, or outputs); running anything on the user's real data without explicit confirmation |
| **unknown** | explain the uncertainty; request a re-run or a pasted report | machine-specific advice or commands |

## Probe allowlist (read-only, enforced in code)

The probe runs ONLY these command shapes (each timeout-protected); everything
else raises `PermissionError` in `_is_allowed`:

| Executable | Allowed invocation(s) | When |
|---|---|---|
| `sw_vers` | `sw_vers` | macOS only |
| `conda` / `mamba` / `micromamba` / `pip` / `pip3` | `<tool> --version` | if found |
| `nvidia-smi` | `nvidia-smi -L`; `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader` | if found |
| `cryodrgn` | `cryodrgn --version`; `cryodrgn -h`; `cryodrgn <cmd> -h` | `--version` if found; `-h` only with `--live-help` |
| `cryodrgn_utils` | `cryodrgn_utils -h`; `cryodrgn_utils <cmd> -h` | only with `--live-help` |

`uname`/arch/Python come from in-process `platform`/`os`/`sys` (no subprocess).
Package version uses `importlib.metadata` (does **not** import cryoDRGN/torch).

**Forbidden in the probe** (guarded by `FORBIDDEN_TOKENS` + the structural
allowlist): `install`, `create`, `update`, `remove`, `download`, `clone`,
`curl`, `wget`, `sbatch`/`srun`/`qsub`/`bsub`, `jupyter`/`notebook`, URLs, shell
redirection/pipes, dashboard/training/analysis launches, broad env dumps, or
private-data traversal. cryoDRGN subcommand calls are help-only (always end in
`-h`), so no compute can run.

## Worked examples (generic — the skill never hardcodes a verdict)

The probe computes support **per host**. The skill always reads `config_state`
from the per-host report; it never assumes a verdict for "this machine."

**A `ready` host (example).** On a Linux host with an NVIDIA GPU and cryoDRGN
4.2.1 installed, `--live-help` captures all selected subcommands and the probe
returns `config_state: ready`. The validation host was exactly such a
host: `config_state: ready`; Linux (`x86_64`); an NVIDIA GPU; `torch 2.9.1+cu128`,
`cuda True` (12.8); Python 3.10.20 (within the tested 3.10–3.13 range)
[src: the validation run]. Treat this as **an example
of a supported host**, not as "this host." On such a host the skill MAY emit
concrete commands with the user's real paths and — after explicit user
confirmation — run real jobs (training, abinit, analyze, backproject, eval_*,
fsc), per the `ready` row above.

**A `blocked` host (example).** On a host that lacks Linux (e.g. macOS) or lacks
an NVIDIA GPU, the same probe returns `config_state: blocked` for compute —
because cryoDRGN 4.2.1 ships the `Operating System :: POSIX :: Linux` classifier
[src: `sources/source/cryodrgn_4.2.1/pyproject.toml`] and its install docs
require a Linux + NVIDIA workstation/cluster [src: `references/01_source_map.md`].
Correct skill behavior: explain the blockage with those citations, offer generic
labeled placeholder templates, and recommend running the same probe on a Linux +
NVIDIA target server before any concrete planning. This is a per-platform
outcome, not a claim about a specific machine.
