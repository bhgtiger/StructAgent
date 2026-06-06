# Lessons

Running notes from building/using this skill. Append; keep each lesson short with a why.

## v0 build (2026-06-05)

- **Capture before claim.** The single factual base is `sources/web/docs_inventory.md`
  (distilled into `references/01_source_map.md`). Several "obvious" crYOLO facts — MRC
  input, standalone `cryolo_train.py`/`cryolo_evaluation.py` scripts, coordinate origin,
  config section→field mapping, filter-selection criteria — are **not** in the captures and
  are deliberately marked GAP. Resisting "I know crYOLO does X" is the whole point.
- **Support ≠ runs.** The trust ladder gives live behavior authority over flags/output
  only; support status follows official install docs. macOS is officially unsupported even
  if a build runs. Encoded in the probe's `support_assessment` so it can't drift.
- **Config-first must be a runtime gate, not a slogan.** `SKILL.md §0` + `10_decision_trees.md`
  Tree 1 make it executable: concrete advice requires a current report.
- **Probe safety by construction.** Default does not execute crYOLO scripts (TF import is
  heavy and may touch the GPU); `--cryolo-exec` opts into a timeout-bounded `--version`
  only. `safety_attestation.commands_run` self-documents the no-install/no-network claim.
- **Privacy.** `configs/site_config.local.md` holds host/env details → home redaction +
  `.gitignore` + "do not upload" labeling.

## v1.0.0 validation (2026-06-06) — GAPs resolved against crYOLO 1.9.9

The v0 GAPs listed above are now **RESOLVED** by captured live `--help` (crYOLO 1.9.9) plus a
GPU smoke run on a Linux + NVIDIA GPU host. Each former GAP and its
grounding:

- **MRC input — CONFIRMED, no longer a GAP.** `predict.log` read `synth_0001.mrc` directly
  (validation run). Cite as VALIDATED against crYOLO 1.9.9.
- **Standalone `cryolo_train.py` / `cryolo_evaluation.py` exist — no longer a GAP.** Both are
  in the installed `which` list (`_versions.txt`), alongside `cryolo_predict.py`,
  `janni_denoise.py`, `cryolo_boxmanager_legacy.py`, `cryolo_boxmanager_tools.py`,
  `cryolo_evaluation_tomo.py`, `napari_boxmanager`. The front-end is
  `cryolo_gui.py {config,train,predict,evaluation,boxmanager}` (`cryolo_gui.py.help.txt`).
- **Coordinate origin / format — RESOLVED.** STAR output uses RELION `_rlnCoordinateX` /
  `_rlnCoordinateY` (confirmed in `out/STAR/synth_0001.star`; validation run).
  crYOLO also natively writes a cryoSPARC-style export (`predict.log`: "Write cryoSPARC
  coordinates"; a `CRYOSPARC/` dir is produced) — so STAR→RELION and the cryoSPARC export are
  confirmable interop facts, not deferred.
- **config section→field mapping — RESOLVED.** Smoke `config_cryolo.json` minimal shape:
  `{"model":{architecture,input_size,anchors:[160,160],max_box_per_image:700,norm},
  "other":{log_path}}`. Box size maps into `model.anchors`; `max_box_per_image` default 700;
  `train`/`valid` sections are only written when training fields are supplied
  (`cryolo_gui.config.help.txt`; `work/cryolo/config_cryolo.json`).
- **filter-selection defaults — RESOLVED.** `-f/--filter` default `LOWPASS`
  `{NONE,LOWPASS,JANNI}`, `--low_pass_cutoff 0.1`, JANNI is the real denoiser
  (`janni_denoise.py {config,train,denoise}`). `--num_patches`/`--overlap_patches` are
  DEPRECATED (`cryolo_gui.config.help.txt`).
- **Gotcha worth keeping:** `--otf` is silently ignored when the config filter is `NONE`
  (`predict.log`: "You specified the --otf option. However, filtering is not configured …
  therefore crYOLO will ignore --otf"). Good troubleshooting note.
- **Output layout note:** `EMAN/` (.box, thresholded), `STAR/` (.star, thresholded, RELION
  coords), `CBOX/` (.cbox, all detections incl. below-threshold + confidence + size) are
  produced; `CRYOSPARC/` and `DISTR/` were BOTH created even in the minimal non-filament run
  (empty). Treat all four as folders crYOLO creates — do NOT claim `DISTR/` is filament-only
  (the validation run observed all four created even in a non-filament run).

**Posture shift:** the skill moved from a no-execute v0 to an **execution-capable 1.0.0**,
VALIDATED against crYOLO 1.9.9 (`_versions.txt`: cryolo 1.9.9 / tensorflow 1.15.5 / keras 2.3.1,
matching the docs source pin tag 1.9.9 / commit 30039bde34d65c179541568b0c27f09916ac5652). On a
probe verdict of supported/partial the skill MAY emit concrete commands with the user's real
paths and run real jobs after explicit user confirmation. The `support_assessment` and the
macOS-unsupported fact (below) remain probe-driven, not hardcoded to any one host.

## Open follow-ups

DONE / partially-done per the 2026-06-06 captures (kept here for provenance; see the v1.0.0
lesson above for the grounding):

- ✅ **DONE** — Live `--help`/`--version` captured on a supported Linux+NVIDIA install;
  `live-unverified` markers replaced with
  "VALIDATED against crYOLO 1.9.9 (captured help: <filename>)".
- ✅ **DONE** — config docs captured in full (`cryolo_gui.config.help.txt`): section→field
  mapping, defaults, allowed `architecture {PhosaurusNet,YOLO,crYOLO}` / `filter
  {NONE,LOWPASS,JANNI}` / `norm {STANDARD,GMM}` values, and `anchors`/`input_size` confirmed
  from the written `config_cryolo.json`.
- ◑ **PARTIAL** — general model is a real named artifact: the validated run used a
  PhosaurusNet general model `gmodel_phosnet_201912_N63.h5`
  (`command_predict_20260606-131938.txt`). Names/provenance are now grounded, but the weight
  terms (separate from package license) still need a captured statement before any download
  advice; the skill ships no weights.
- ✅ **DONE** — BOX/STAR/CBOX layout + RELION `_rlnCoordinateX/Y` and the native cryoSPARC
  export verified on disk (`out/STAR/synth_0001.star`, `out/CRYOSPARC/`). Coordinate
  origin/y-flip against a live RELION/cryoSPARC *import* is the only remaining verification.
- ⬜ **OPEN** — Read the method papers (ref 08) before any benchmark/accuracy statement.
  This is the remaining open item.
