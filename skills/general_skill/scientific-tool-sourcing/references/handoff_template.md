# HANDOFF.md template (evidence pack → skill builder)

`HANDOFF.md` is the only file the skill builder must read first. Keep it under ~300
lines. Every fact cites raw evidence under `sources/`, never a distilled note (the
Namdinator lesson: "ground truth beats distillation"). Facts that live only in this
hand-off and not in `sources/` are not allowed.

````markdown
# `<TARGET>` evidence pack — hand-off for skill building

Status: evidence pack ready / ready with gaps · Date: `<YYYY-MM-DD>` · Gathered by: `<executor>`
Plan: `plan/source_plan.md` · Verification: `sources/crosscheck/verification.md`

## 1. Pins
| Component | Version | Commit / digest | Date | Evidence |
|---|---|---|---|---|
| upstream repo | | | | `sources/source/SNAPSHOT.md:<line>` |
| docs (rendered) | version shown | — | fetched | |
| wrapper / kit | | | | |
| weights / models | name | SHA-256 if published | | |

## 2. Hosts
- Gathering host: `<…>` (`logs/gathering_host.txt`). The target tool was **not**
  installed or run here.
- Target runtime: `<known facts or "unknown">`. Live capture: done (`sources/live/`) / not
  done → `sources/crosscheck/live_verification_checklist.md`.

## 3. Evidence index
| Folder | What it holds | Files / MB |
|---|---|---|
(from `build_manifest.py` output; list files > 50 MB separately: never package them)

## 4. Facts the skill may state (cited)
Group by future reference file. Mark each fact LIVE / SOURCE / DOCS / PAPER / COMMUNITY.
- Install / environment: …
- Command or API surface: see `sources/crosscheck/cli_parity.md`. That table is the
  **allowlist**: a flag or subcommand that is not in it must not appear in the skill.
- Input / output formats: …
- Defaults that change results: …
- Default network calls / data egress and how to disable them: …
- License / terms / citation requirement: …
- Hardware and platform support: …

## 5. Contradictions and how they were resolved
| Topic | Side A (cite) | Side B (cite) | Winner under the trust ladder | Status |
|---|---|---|---|---|

## 6. Gaps
| Gap | Priority | Blocks which skill feature | How to resolve |
|---|---|---|---|

### Must NOT claim
- `<things that look plausible but have no evidence, or are contradicted>`

## 7. Decisions for the user
1. …

## 8. Recommendations for the build (advisory; the builder decides)
- v0 slice: `<read-only / command-generating, config-first>`
- Reference layout used by the existing house skills (cryolo, topaz, cryodrgn, deepemhancer):
  `00_scope_and_trust · 01_source_map · 02_config_session_and_environment ·
  03_cli_reference · 04_data_model_and_formats · 05_core_workflows · 06_interoperability ·
  07_safety_license_privacy · 08_validation_and_benchmarks · 09_troubleshooting ·
  10_decision_trees`, plus `SKILL.md`, an environment probe script, `lessons.md`, and tests.
  Map each evidence folder to the reference file(s) it feeds.
- `01_source_map.md` of the built skill should copy section 1 (pins) and use Tier 1
  (VALIDATED: live) / Tier 2 (SOURCED: source + docs) labels.
- Build-time guard: audit every flag in the draft against `cli_parity.md` and the pinned
  source. In past projects drafting invented aliases and flags even with good evidence.
- Keep raw `sources/` out of the packaged skill.
````
