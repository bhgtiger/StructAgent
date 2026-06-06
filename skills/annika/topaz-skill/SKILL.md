---
name: topaz-skill
description: >-
  Source-grounded assistant for Topaz (tbepler/topaz), the cryo-EM particle
  picking and micrograph/tomogram denoising package (CLI `topaz`, PyPI
  `topaz-em`). Use when the user asks to install, configure, understand, or
  generate commands for Topaz workflows — training/segmentation/extraction for
  particle picking, denoise/denoise3d, preprocess/downsample/normalize, or
  coordinate-format conversion. ALWAYS runs a config/environment session first
  and never installs Topaz or runs Topaz compute jobs without explicit
  confirmation. Emits concrete, validated commands with the user's real paths
  and, after explicit confirmation on a probe-'valid' machine, MAY run real
  Topaz jobs on the user's data with output safeguards.
version: 1.0.0
license: Skill text MIT-style for this repo; Topaz itself is GPLv3.
metadata:
  topaz_pin: v0.3.20 @ 58fe52370f4accb8215525df2ea8f2c7ee6d340a
  grounded_on: 2026-06-05
  validated_on: 2026-06-06 (live help + GPU smoke on a Linux + NVIDIA GPU host, topaz 0.3.20)
---

# Topaz skill (config-first, validated against 0.3.20)

Topaz is a cryo-EM pipeline: **positive-unlabeled CNN particle picking** plus
**deep denoising** of micrographs (`denoise`) and tomograms (`denoise3d`). CLI is
`topaz <command>`; PyPI package is `topaz-em`; license **GPLv3**. All facts here
are grounded against **v0.3.20 / commit `58fe5237`** (see `references/01_source_map.md`),
and CLI behavior is now **VALIDATED** via captured live help
(`topaz.*.help.txt`, one per subcommand) plus a GPU smoke run
(on a Linux + NVIDIA GPU host, topaz 0.3.20).

## 🔴 MANDATORY FIRST STEP — config/environment session

**Before giving any concrete Topaz usage advice, commands, or device/version
claims, you MUST establish environment state.** Do this on the *first* Topaz
request of a session and whenever config is missing or stale:

1. **Look for an existing config report** — for example `configs/site_config.local.md`
   in this skill folder, or a user/project-local probe output named like
   `site_config.local.md` / `topaz_env_probe_*.md`. If found and **fresh** (see
   staleness rules in `references/02_config_session_and_environment.md`), read it and proceed.
2. **If none exists / it is stale / Topaz is "not installed":** STOP normal
   workflow output. Offer to run the read-only probe and explain why:
   ```
   python3 scripts/topaz_env_probe.py --output <project>/site_config.local.md
   ```
   (add `--check-torch` only if the user wants the framework GPU probe; default off).
   Do **not** run it silently — ask first, because it launches small read-only
   subprocesses (`topaz --version/--help`, `nvidia-smi -L`).
3. **Until a fresh probe exists, gather environment first.** You may explain what
   Topaz is, its workflows, and install options while the probe is pending. Once a
   fresh probe reports `validation_status = valid`, you **MAY emit concrete commands
   with the user's real paths**, and — **after explicit user confirmation** — you MAY
   run real Topaz jobs on the user's data (with output safeguards; see Safety).

If `validation_status` is `partial`/`blocked` or `topaz.installed=false`, do not
emit concrete run commands as ready-to-run: surface `blocked_capabilities` and the
remediation (install / fix torch CUDA build) to the user first.

## Triggers (use this skill)
- "Install / set up / configure Topaz on this machine."
- "Can Topaz use my Mac / M-series GPU / CUDA?" (device question — answer from the
  **per-host probe outcome**, not a hardcoded verdict)
- "How do I pick particles / train / extract / denoise with Topaz?"
- "Generate a Topaz `train`/`extract`/`denoise` command for my data."
- "Convert these coordinates to/from STAR/BOX for Topaz."
- "Why is Topaz slow / falling back to CPU / erroring on install?"

## Non-triggers (do NOT use / redirect)
- General cryo-EM questions unrelated to Topaz → answer normally, no config gate.
- Non-Topaz pickers (crYOLO, Warp, RELION autopick) unless comparing to Topaz.
- Requests to actually run jobs/installs **without** confirmation → see Safety.
- Anything requiring upload/movement of private micrographs → refuse by default.

## Source trust ladder (resolve conflicts top-down)
1. **Live** `topaz`/package behavior on the configured machine (`--version`, `--help`,
   subcommand help, import metadata) — authoritative for *this machine's state only*.
   Live behavior **was actually captured** for 0.3.20 (every subcommand's `--help` as
   `topaz.*.help.txt`), so flag/default/format claims here
   are marked **VALIDATED**, not live-unverified.
2. Pinned Topaz source / release tag / commit (currently v0.3.20 @ 58fe5237) — for facts
   not surfaced by help (MPS absence, device dispatch, `python_requires`).
3. Official docs in the repo (`docs/source/…`).
4. Rendered docs (readthedocs) / release pages.
5. Peer-reviewed Topaz papers (method, denoising).
6. First-party talks/tutorials.
7. Community issues/Discussions/HPC notes (dated, cross-checked).
8. LLM summaries — navigation only, never a citation.

> Because Topaz is a CLI tool, **live behavior + pinned source override papers/
> tutorials for exact flags, defaults, install commands, and output files.** Always
> version-tag recommendations; do not treat "whatever is installed" as ground truth
> without recording its version.

## Reference routing (read the right file)
| Need | File |
|---|---|
| Scope, safety boundary, trust ladder | `references/00_scope_and_trust.md` |
| Source pin, URLs, how grounded | `references/01_source_map.md` |
| Config session, schema, staleness, **device/MPS** | `references/02_config_session_and_environment.md` |
| Subcommands, flags, defaults | `references/03_cli_reference.md` |
| File formats, coordinates, models | `references/04_data_model_and_formats.md` |
| End-to-end workflows (validated commands) | `references/05_core_workflows.md` |
| Benchmarks/validation, paper scope | `references/08_validation_and_benchmarks.md` |
| Errors & fixes | `references/09_troubleshooting.md` |
| Decision trees (install/device/workflow) | `references/10_decision_trees.md` |
| Read-only environment probe | `scripts/topaz_env_probe.py` |
| Site config template + schema | `configs/site_config.template.md` |

## Device support — general per-platform fact (driven by the probe)
Topaz device dispatch is **binary CUDA-or-CPU**. There is **no MPS / Apple-Silicon
GPU code path** in v0.3.20 (`topaz/cuda.py` consults only `torch.cuda`; zero `mps`
references in `topaz/`) [sourced 0.3.20 @ 58fe5237; confirmed `topaz_mps_supported = False`
by the probe (run `topaz_env_probe.py --check-torch`)]. A green
`torch.backends.mps.is_available()` proves the **framework**, not Topaz; never infer
Topaz MPS support from PyTorch. The verdict is **per host, from the probe**:
- If the probe reports **Apple Silicon / no NVIDIA GPU**, Topaz runs **CPU-only** —
  pass `-d -1`. The M-series GPU is not used.
- On a probe-validated **Linux + NVIDIA** host, Topaz uses **CUDA**
  (the probe reports `cuda_usable_here = True`) — pass `-d 0` (or `-d -2` for
  multi-GPU `denoise3d`).

Do **not** hardcode any one machine's verdict; read it from the fresh probe. See
`references/02_config_session_and_environment.md`.

## Safety (hard rules)
- **No blind installs.** Topaz install changes the environment — propose the exact
  command, state risks, and require explicit confirmation. Never auto-run an installer.
- **Execution allowed on a probe-valid machine, after confirmation.** On a host where the
  fresh probe reports `validation_status = valid`, the skill **MAY run real Topaz jobs**
  (`train`/`extract`/`denoise`/etc.) on the user's data **only after explicit user
  confirmation**, and with output safeguards (write to a fresh/empty output dir, never
  overwrite inputs, capture the run log).
- **Private data stays local.** Treat micrographs/coordinates/STAR as private project
  data. Never upload, move, delete, or convert them without explicit approval.
- **Confirm before any write or execution.** The probe writes only its `--output` file.
- **Label uncertainty.** If config is missing/stale or Topaz uninstalled, do not present
  run commands as ready-to-run; list blocked capabilities and remediation first.
