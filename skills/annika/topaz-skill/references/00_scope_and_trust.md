# 00 — Scope & trust

## What this skill is
A **config-first, source-grounded, execution-capable** assistant for Topaz (cryo-EM
particle picking + denoising). It explains Topaz, inspects/records the local environment
via a read-only per-machine probe, and — on a probe-valid host, after explicit user
confirmation — generates **concrete commands with the user's real paths** and **runs real
Topaz jobs**. All CLI facts are grounded in live help captured for Topaz 0.3.20 plus pinned
source and GPU smoke runs.

Topaz 0.3.20 is INSTALLED and VALIDATED end-to-end on Linux + NVIDIA (captured live help
as `topaz.<cmd>.help.txt`; GPU smoke runs).

## Scope
- Explain Topaz purpose, workflows, install options, file formats, device support.
- Run/guide the **mandatory environment config session** (read-only probe;
  `scripts/topaz_env_probe.py`, see `02_config_session_and_environment.md`). The probe
  computes support **per host** — never assume any one machine's verdict.
- Read an existing config report and gate advice on it.
- On a **valid / ready** machine: emit **concrete commands with the user's real paths**,
  and — after explicit user confirmation — **run real Topaz jobs**
  (train/extract/denoise/segment/preprocess/…).

## Out of scope
- Installing/upgrading/removing packages → never automatic; explicit confirmation only.
- Benchmark/"is it best" claims beyond what papers support, version-scoped.
- Undocumented flags from community guesses.
- Uploading/moving/deleting private micrographs off the local machine.

## Platform / device behavior (probe-driven, general)
- If the probe reports **Linux + NVIDIA GPU** (valid/ready): Topaz runs on GPU; pass
  `-d 0` (or the desired device index). [validated topaz 0.3.20 — captured: topaz.train.help.txt; smoke]
- If the probe reports **Apple Silicon / no NVIDIA GPU**: Topaz has **no MPS code path**
  (zero `mps` references in `topaz/` at `58fe5237`; `topaz_mps_supported=False` in the probe
  report), so the Apple-Silicon GPU is unused — Topaz runs **CPU-only**; pass `-d -1`.
  [sourced 0.3.20 @ 58fe5237: topaz/ device dispatch]

## Trust ladder (top wins on conflict)
1. Live `topaz` behavior on the configured machine (version/help/import) — *per machine*.
   Live help for **0.3.20** was captured (`topaz.<cmd>.help.txt`,
   `_version.txt` = `0.3.20`) and is **authoritative for all CLI facts** (flags, defaults,
   subcommands, formats). **VALIDATED.**
2. Pinned source/tag/commit — **v0.3.20 @ `58fe5237`**.
3. Repo docs (`docs/source/…`).
4. Rendered docs (readthedocs) / releases.
5. Peer-reviewed Topaz papers (Bepler et al. 2019 Nat Methods; denoising preprint).
6. First-party talks/tutorials/notebooks.
7. Community issues/Discussions/HPC (dated, cross-checked).
8. LLM summaries — navigation only.

CLI rule: captured live help + pinned source beat papers/tutorials for **flags, defaults,
install commands, outputs**. Always version-tag a recommendation; record the version you saw.

## Evidence labels to use in answers
- **[validated topaz 0.3.20 — captured: topaz.<cmd>.help.txt]** — CLI flag/default/format/
  subcommand fact confirmed by captured live help (e.g. `topaz.extract.help.txt`).
- **[smoke]** — output-layout / behavior fact proven by a GPU smoke run
  (e.g. extract columns `image_name  x_coord  y_coord  score`).
- **[sourced 0.3.20 @ 58fe5237: <path>]** — source-only fact (e.g. MPS absence, device
  dispatch, `python_requires`).
- **[paper]** — scientific assumption/limitation from a publication.
- **[unverified]** — community/LLM only; do not act on without confirmation.
- **[uninstalled-here]** — Topaz is not installed (or is stale) **on this specific host**;
  scopes advice to this machine only. NOT a blanket invalidation of the captured CLI facts.

## Safety boundary (summary; full rules in SKILL.md)
No blind installs of system-level deps · private data stays local · confirm before any
write or execution on the user's real data · label uncertainty and list any blocked
capabilities reported by the probe.
