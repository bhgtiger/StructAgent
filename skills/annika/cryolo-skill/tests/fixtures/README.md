# Fixtures

**This skill ships no fixtures and downloads none by default.** No micrographs, models, or
reference data are included or fetched automatically. Execution against fixtures is now
possible (the CLI is INSTALLED and VALIDATED against crYOLO 1.9.9), but only against a
user-provided dataset or an explicitly-confirmed public example — never silently.

## Why no fixtures are shipped

- Keeping the package light: micrographs and reference datasets are large and do not belong
  inside the skill.
- Avoiding weight/license issues: pretrained weights/models must not be packaged or
  auto-downloaded; they may carry separate terms (`references/07_safety_license_privacy.md`).
- Execution against a user-provided dataset, or an explicitly-confirmed small **public**
  example (e.g. the official reference example), is allowed — but downloading/extracting it
  and running crYOLO on it require explicit user confirmation
  (`references/00_scope_and_trust.md`).

## If you add a fixture

1. Choose a small **public** dataset/example with a recorded source URL + license/terms.
2. Record provenance here (URL, version, license, fetch date, checksum).
3. Record expected outputs in `tests/eval/reference_answers.md`.
4. Run crYOLO against it only with explicit confirmation and logging, inside the project
   cwd — never on private user data without confirmation.

The probe-driven local machine (via the read-only env probe) is still always available as a
"fixture" of sorts; see the eval cases.

## Validated smoke (reference, not shipped)

The crYOLO smoke run that grounds this skill used **synthetic micrographs** plus an
**external general model** (PhosaurusNet `gmodel_phosnet_201912_N63.h5`, not shipped here),
and produced output folders `EMAN/`, `STAR/`, `CBOX/`, `CRYOSPARC/`, and `DISTR/` under the
`-o` output dir (the validation run; on-disk `out/` tree). The general-model file is a real,
named artifact but
is **not** distributed with the skill — cite its license/privacy before using one.
