# 00 — Scope & trust

## What this skill is
A **config-first, source-grounded** assistant for Topaz (cryo-EM particle picking +
denoising). It explains Topaz, inspects/records the local environment, and produces
**source-cited** guidance and **placeholder command templates**.

## v0 scope (current)
- Explain Topaz purpose, workflows, install options, file formats, device support.
- Run/guide the **mandatory environment config session** (read-only probe).
- Read an existing config report and gate advice on it.
- Emit **placeholder** command templates (no real paths, no execution).

## Out of scope in v0 (deferred)
- Concrete commands with the user's real paths → **v1**.
- Running any Topaz job (train/extract/denoise/segment/…) → **v2+** (fixtures), **v3** (real data).
- Installing/upgrading/removing packages → never automatic; explicit confirmation only.
- Benchmark/"is it best" claims beyond what papers support, version-scoped.
- Undocumented flags from community guesses.
- Uploading/moving/deleting/converting private micrographs.

## Trust ladder (top wins on conflict)
1. Live `topaz` behavior on the configured machine (version/help/import) — *this machine only*.
2. Pinned source/tag/commit — **v0.3.20 @ `58fe5237`**.
3. Repo docs (`docs/source/…`).
4. Rendered docs (readthedocs) / releases.
5. Peer-reviewed Topaz papers (Bepler et al. 2019 Nat Methods; denoising preprint).
6. First-party talks/tutorials/notebooks.
7. Community issues/Discussions/HPC (dated, cross-checked).
8. LLM summaries — navigation only.

CLI rule: live + pinned source beat papers/tutorials for **flags, defaults, install
commands, outputs**. Always version-tag a recommendation; record the version you saw.

## Evidence labels to use in answers
- **[sourced v0.3.20]** — from the pinned source/docs.
- **[live <version>]** — confirmed against the installed executable on this machine.
- **[paper]** — scientific assumption/limitation from a publication.
- **[unverified]** — community/LLM only; do not act on without confirmation.
- **[NOT validated against local binary]** — required whenever Topaz is uninstalled/stale.

## Safety boundary (summary; full rules in SKILL.md)
No blind installs · no compute execution in v0–v1 · private data stays local ·
confirm before any write/execution · label uncertainty and list blocked capabilities.
