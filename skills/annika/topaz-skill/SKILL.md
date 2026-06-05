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
  confirmation. v0 explains workflows and emits placeholder command TEMPLATES
  only; concrete commands with real paths are v1.
version: 0.0.1
license: StructAgent skill text follows repository license; Topaz itself is GPLv3.
metadata:
  topaz_pin: v0.3.20 @ 58fe52370f4accb8215525df2ea8f2c7ee6d340a
  grounded_on: 2026-06-05
---

# Topaz skill (v0 — config-first, source-grounded)

Topaz is a cryo-EM pipeline: **positive-unlabeled CNN particle picking** plus
**deep denoising** of micrographs (`denoise`) and tomograms (`denoise3d`). CLI is
`topaz <command>`; PyPI package is `topaz-em`; license **GPLv3**. All facts here
are grounded against **v0.3.20 / commit `58fe5237`** (see `references/01_source_map.md`).

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
3. **Block concrete command generation/execution** until config exists. You may
   still explain what Topaz is, its workflows, install options, and **placeholder
   templates** — every such answer must be labeled
   **“NOT validated against a local Topaz executable.”**

If `validation_status` is `partial`/`blocked` or `topaz.installed=false`, treat
all command output as templates and surface `blocked_capabilities` to the user.

## Triggers (use this skill)
- "Install / set up / configure Topaz on this machine."
- "Can Topaz use my Mac / M-series GPU / CUDA?" (device question)
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
2. Pinned Topaz source / release tag / commit (currently v0.3.20 @ 58fe5237).
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
| End-to-end workflows (templates) | `references/05_core_workflows.md` |
| Benchmarks/validation, paper scope | `references/08_validation_and_benchmarks.md` |
| Errors & fixes | `references/09_troubleshooting.md` |
| Decision trees (install/device/workflow) | `references/10_decision_trees.md` |
| Read-only environment probe | `scripts/topaz_env_probe.py` |
| Site config template + schema | `configs/site_config.template.md` |

## Device support — load-bearing sourced fact
Topaz device dispatch is **binary CUDA-or-CPU**. There is **no MPS / Apple-Silicon
GPU code path** in v0.3.20 (`topaz/cuda.py` consults only `torch.cuda`; zero `mps`
references in `topaz/`). A green `torch.backends.mps.is_available()` proves the
**framework**, not Topaz. On Apple Silicon Macs, **Topaz runs CPU-only**; the
M-series GPU is not used. Never infer Topaz MPS support from PyTorch.
See `references/02_config_session_and_environment.md`.

## Safety (hard rules)
- **No blind installs.** Topaz install changes the environment — propose the exact
  command, state risks, and require explicit confirmation. Never auto-run an installer.
- **No compute execution in v0–v1.** Do not run `train`/`extract`/`denoise`/etc.
  Execution is v2+ (tiny fixtures, explicit confirmation) / v3 (real data).
- **Private data stays local.** Treat micrographs/coordinates/STAR as private project
  data. Never upload, move, delete, or convert them without explicit approval.
- **Confirm before any write or execution.** The probe writes only its `--output` file.
- **Label uncertainty.** If config is missing/stale or Topaz uninstalled, mark answers
  unvalidated and list blocked capabilities.

## Version ladder (what v0 may do)
- **v0 (now):** config-first explanation + **placeholder** command templates (no real
  user paths, no execution).
- **v1:** concrete commands from user-provided real paths — still **no execution**.
- **v2:** run tiny *sourced* fixtures only, with explicit confirmation + log capture.
- **v3:** run the user's real Topaz jobs after config + review + confirmation + output safeguards.
