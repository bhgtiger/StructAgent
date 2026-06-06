# 08 · Validation and benchmarks

## Two kinds of validation (keep them separate)

This file distinguishes **skill validation** (does the skill emit correct, version-matched
commands and behavior?) from **scientific validation** (how accurate is crYOLO picking, in
numbers?). The skill is now **VALIDATED end-to-end against crYOLO 1.9.9** (see below).
Scientific accuracy/benchmark numbers are a different matter and still require a sourced
paper read — none has been done in this project yet.

## Accuracy / benchmark numbers still require a sourced paper read

**Do not state any benchmark, accuracy, speed, or "better-than-X" number unless it is tied
to a captured paper/doc and a version context.** No such paper has been read into this
project's source inventory (`sources/`, see `references/01_source_map.md`). If asked "how
good is crYOLO?", explain that it is a fast automated CNN-based picker (general purpose, with
shipped general models) and that specific accuracy/speed numbers are a **GAP** pending a
sourced paper read. This discipline is independent of the fact that the CLI behavior itself
is validated.

## Method papers (bibliographic pointers — NOT yet independently read)

These DOIs are the official crYOLO papers as listed in the planning document. They are
**bibliographic pointers only**: they have **not** been read into this project's source
inventory (`sources/`), so do not quote results, figures, or benchmark numbers from them
until they are captured/read.

| Paper | Venue | DOI (verify before citing) |
|---|---|---|
| Wagner et al. 2019, *SPHIRE-crYOLO is a fast and accurate fully automated particle picker for cryo-EM* | Communications Biology | 10.1038/s42003-019-0437-z |
| Wagner et al. 2020, filament picking / SPHIRE-STRIPER | Acta Crystallographica Section D | 10.1107/s2059798320007342 |
| Wagner & Raunser 2020, crYOLO evolution / comment | Communications Biology | 10.1038/s42003-020-0790-y |

Before citing any of these: confirm the DOI resolves, record the capture in a paper
inventory (`references/papers/paper_inventory.md` if/when created), extract only
skill-relevant content (assumptions, data requirements, validation logic, limitations,
version dependencies), and keep paper claims separate from live CLI/install behavior.

## Validation status — VALIDATED against crYOLO 1.9.9

The skill's CLI/behavior claims were validated against a live, GPU install on
2026-06-06 (the validation run, crYOLO section). Ground
truth:

- **Version pin:** crYOLO **1.9.9 / TensorFlow 1.15.5 / keras 2.3.1**
  (`_versions.txt`). This matches the docs source pin
  (`MPI-Dortmund/cryolo` tag `1.9.9` / commit `30039bde34d65c179541568b0c27f09916ac5652`),
  so all captured `--help` is **VALIDATED against crYOLO 1.9.9**.
- **Probe verdict:** `cryolo_env_probe.py` returned **status = supported** on a Linux +
  NVIDIA GPU host. (crYOLO's docs list the RTX 2080 Ti among officially-tested GPUs.) The
  verdict is computed **per machine**; a
  `supported` host may emit concrete commands with the user's real paths and run real jobs
  **after explicit user confirmation**.
- **Config smoke — PASS:** `cryolo_gui.py config config_cryolo.json 160 --filter NONE`
  wrote a valid config (`work/cryolo/config_gen.log`, `work/cryolo/config_cryolo.json`).
  The positional integer `160` is the **box size** and maps into `model.anchors: [160, 160]`;
  the minimal config also wrote `model.max_box_per_image: 700` (default) and only the
  `model`/`other` sections — train/valid sections appear only when training fields are
  supplied (`cryolo_gui.config.help.txt`; the validation run).
- **Predict smoke — PASS (NVIDIA GPU):**
  `cryolo_predict.py -c config_cryolo.json -w <general_model.h5> -i mics/ -o out/ -g 0 --otf -t 0.2`
  read a `.mrc` micrograph directly and produced outputs
  (`logs/cmdlogs/command_predict_20260606-131938.txt`, `predict.log`,
  the validation run). MRC micrograph input is therefore **confirmed**,
  not a gap.
- **Outputs produced under `-o`:** `EMAN/*.box` (thresholded), `STAR/*.star` (thresholded,
  RELION `_rlnCoordinateX`/`_rlnCoordinateY` columns — confirmed in
  `out/STAR/synth_0001.star`), `CBOX/*.cbox` (all detections incl. below-threshold +
  confidence + size), plus `CRYOSPARC/` and `DISTR/` subfolders, **both created even in this
  minimal non-filament run** (they were empty). State `DISTR/` and `CRYOSPARC/` as folders
  crYOLO creates; do not claim `DISTR/` is filament-only (the validation run observed all
  four created even in a non-filament run). The `CRYOSPARC/` folder
  plus the `predict.log` line `Write cryoSPARC coordinates` confirm crYOLO natively emits a
  cryoSPARC-style coordinate export — see `references/06_interoperability.md`.
- **`--otf` gotcha (observed):** with `--filter NONE` in the config, `predict.log` reports
  `You specified the --otf option. However, filtering is not configured ... therefore crYOLO
  will ignore --otf` — `--otf` is silently a no-op unless a filter (LOWPASS/JANNI) is
  configured. See `references/09_troubleshooting.md`.
- **The validated model was a general model** (`gmodel_phosnet_201912_N63.h5`, a
  PhosaurusNet general model). A general-model `.h5` file is a real, named artifact; this
  skill ships none — cite license/privacy (`references/07_safety_license_privacy.md`).

## What counts as skill validation here

- The config gate fires when the per-machine probe report is absent/stale (`02_*`, `10_*`).
- CLI templates are marked **VALIDATED against crYOLO 1.9.9 (captured help: <filename>)**,
  with citations, wherever the captured help resolves them (`01_*`, `03_*`); only genuinely
  uncaptured items remain labeled gaps.
- Support status is **probe-driven, per machine** (`02_*`). The captured install docs and the
  smoke run together confirm support on Linux+NVIDIA; macOS-unsupported stays a true sourced
  per-platform outcome, expressed as a probe verdict — not as "this machine is blocked".
- The probe is read-only and self-attests its commands (`scripts/cryolo_env_probe.py`,
  `safety_attestation.commands_run`). Note: the read-only probe's internal `probe_version`
  is a separate artifact and stays at `0.1.0`, independent of the `SKILL.md` frontmatter
  version (now `1.0.0`).

See `tests/eval/eval_cases.md` for the behavioral eval cases.

## Validating crYOLO's own picking quality (public fixture)

Reproducing/validating crYOLO **picking quality in numbers** requires a public fixture (e.g.,
the official reference example) downloaded and run. This is now **possible with explicit user
confirmation** on a `supported`/`partial` machine — the end-to-end smoke already exercised
`config` + `predict` on synthetic micrographs with an external general model
(`VALIDATION_SUMMARY.md` lines 18–20). Before such a run: confirm with the user, respect
license/privacy (`07_*`), and record the fixture and expected outcomes in
`tests/fixtures/README.md`. Generating accuracy/benchmark numbers still requires the sourced
paper read described above.
