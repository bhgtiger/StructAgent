# 00 · Scope and trust ladder

## What this skill is

A **config-first**, source-grounded assistant for **SPHIRE-crYOLO** (cryo-EM particle
picking). It explains crYOLO, assesses (via a per-machine read-only probe) whether the
current machine is suitable, and produces **concrete commands validated against crYOLO
1.9.9** (captured live `--help` + a GPU smoke run). On a machine the probe rates
**supported** or **partial**, the skill MAY emit concrete commands with the user's real
paths and **run crYOLO after explicit user confirmation**.

The installed, validated build is **crYOLO 1.9.9** (TensorFlow 1.15.5, keras 2.3.1) per
`captured/cryolo/_versions.txt`, matching the pinned docs source (tag `1.9.9` / commit
`30039bde34d65c179541568b0c27f09916ac5652`). All captured `--help` is therefore
**VALIDATED against crYOLO 1.9.9**.

## Scope (WILL)

- Explain crYOLO workflows from the captured sources (`01_source_map.md`).
- Run/read a **read-only** environment configuration session before normal usage.
- Inspect local state (when allowed): OS/arch, shell/Python, conda/mamba/micromamba/pip,
  NVIDIA/CUDA availability, crYOLO executable/package availability.
- State whether the local system is **supported / partial / blocked / unknown** for
  crYOLO, with source-grounded reasons (the probe computes this per host).
- Generate **concrete commands validated against crYOLO 1.9.9** for: configuration,
  prediction with a general model, training/refinement, evaluation, and visualization —
  every flag/default/subcommand citing the captured help
  (`captured/cryolo/*.help.txt`).
- On a **supported / partial** machine, **run** those commands with the user's real
  paths after **explicit user confirmation** (config-first gate + confirm-before-touching-
  real-data still apply).
- Provide troubleshooting decision trees grounded in captured docs, live behavior, and
  the validated smoke run.

## Non-scope (will NOT)

- No automatic conda/pip installs, no blind installs of system-level dependencies, no
  downloads of general models/weights, no env edits without approval.
- No execution on the user's real micrographs/annotations/models — and no movement,
  deletion, or conversion of that data — **without explicit user confirmation**.
  Execution **is** allowed once the probe rates the machine **supported / partial** and
  the user confirms.
- No benchmark/performance claims unless tied to a captured paper/doc + version context.
- No claim that crYOLO supports macOS/Apple-Silicon GPU. Official installation
  requirements govern per-platform support status (see
  `02_config_session_and_environment.md`).

## Interoperability is captured, not deferred

crYOLO **natively** writes downstream-ready coordinate exports — no separate v1 step:

- A `STAR/` subfolder of `.star` files with RELION `_rlnCoordinateX` / `_rlnCoordinateY`
  columns (confirmed in `work/cryolo/out/STAR/synth_0001.star`).
- A `CRYOSPARC/` subfolder; the predict log emits `Write cryoSPARC coordinates`
  (`work/cryolo/predict.log`), i.e. a cryoSPARC-style coordinate export.
- An `EMAN/` subfolder of `.box` files (thresholded) and a `CBOX/` subfolder of `.cbox`
  files (**all** detections, including below-threshold, plus confidence + size).
- `DISTR/` and `CRYOSPARC/` are both created even in the minimal non-filament run (they
  were empty there) — treat them as folders crYOLO always creates, not filament-only.

For column mappings, coordinate-origin / y-flip conventions, and import recipes, see the
updated `06_interoperability.md`.

## Execution model (probe + confirmation gated)

```text
1  Read-only env/config probe computes a per-machine verdict
   (supported / partial / blocked / unknown). The probe never executes crYOLO jobs.
2  Source-grounded explanation + concrete commands VALIDATED against crYOLO 1.9.9,
   filled with the user's real paths (citing captured help).
3  On a 'supported' or 'partial' verdict AND explicit user confirmation:
   run real crYOLO jobs (config / train / predict / evaluation) on the user's data.
4  On 'blocked' / 'unknown': explain why and what the probe found; do not run.
```

Representative task: *"Configure/check this machine for crYOLO, tell me exactly which
crYOLO workflows are available here, and — if I confirm — run the picking job."*

## Source trust ladder (precedence on conflict)

1. **Live crYOLO executable/package behavior on this machine** (`cryolo_*.py --help`,
   package metadata, installed version) — authoritative **only** for *this local
   executable's* flags / version / help text / output folders. Live `--help` for
   **1.9.9 has now been captured** (`captured/cryolo/*.help.txt`, `_versions.txt`) and is
   authoritative for flags / defaults / subcommands / output layout.
2. **Official platform/support status and license terms** from pinned official
   docs/source — authoritative for *whether a setup is officially supported/compliant*,
   even if an unofficial local executable happens to run.
3. Pinned crYOLO source/docs at the recorded commit/tag (`1.9.9` /
   `30039bde34d65c179541568b0c27f09916ac5652`).
4. Official documentation (rendered `cryolo.readthedocs.io/en/stable/`).
5. Official model/download pages linked from the docs.
6. Peer-reviewed crYOLO method / filament / workflow papers.
7. First-party tutorials/workshops/talks.
8. Community issues / forums / mailing list / HPC notes.
9. LLM summaries / NotebookLM — navigation aids only.

### Platform-support carve-out (critical)

Live behavior is authoritative for **flags / output folders / installed version only**.
For **per-platform device support status**, official installation requirements lead
(tier 2 > tier 1). On any platform, a setup that runs but is not officially supported is
reported as **"locally runnable but officially unsupported/untested"** — never promoted
to "supported". This is a probe-driven, per-platform outcome (e.g. crYOLO does not
officially support macOS/Apple-Silicon GPU), not a statement about any one host.

## Citation discipline

Every concrete claim carries a source: a docs page + fetch date, the source pin, a
captured paper, the captured live help, or the local config report. Uncaptured specifics
are labeled "not captured / source gap". Command, config, and output claims are
**VALIDATED against crYOLO 1.9.9**, citing the captured help filename
(`captured/cryolo/cryolo_gui.config.help.txt`, `cryolo_predict.py.help.txt`,
`cryolo_train.py.help.txt`, `cryolo_evaluation.py.help.txt`, etc.) and, where applicable,
the smoke run (`VALIDATION_SUMMARY.md` crYOLO section, `work/cryolo/`).
