# Past skill projects: what the gathering looked like and what went wrong

Lab history from the projects behind the StructAgent skills `openfold3`, `modelangelo`,
`namdinator`, `boltz`, `cryoatom` and `cryodrgn-skill`. Project folders are named as in the
local `Maria_projects/` workspace; they are not part of this repository. Use this file as
worked examples and as the source of the pitfalls in `../references/`. It was surveyed on
2026-11-24.

## Best worked example: `opnefold_skill/` (OpenFold 3 + Anthropic kits, 2026-09-22)
The closest match to this skill's workflow. Claude orchestrated; Codex gathered (2 at a time).
- `tasks/_common_rules.md`, `tasks/task_{A..D}_*.md`, `tasks/run_codex_task.sh`: the
  templates in `gathering_tasks.md` generalize these.
- `sources/{source,anthropic_kit,web,papers,crosscheck}/`. 32 inventories, 50 page/paper
  copies, 3,360 `path:line` citations; `check_citations.py` finds 0 errors (2026-11-24).
- Task D (cross-check) produced `pin_consistency`, `cli_parity`, `io_parity`,
  `live_verification_checklist`, and `gap_report`: the hand-off backbone.
- Findings that only cross-checking surfaced: `install` rejects `--config` despite the README;
  boolean flags take values; `use_msa_server` defaults to True (sequence egress to
  api.colabfold.com); preview weights are gated while OpenBind-0 weights are public.
- Weak spots: 583 MB raw store (two clones, 411 MB kit); no `HANDOFF.md` (the session
  summary served instead); live capture postponed.

## Other projects (Annika jobs layout: `jobs/Job_001_*gathering`, `artifacts/sources/`)
| Project | Good practice | Problem that the skill now guards against |
|---|---|---|
| `ModelAngelo_skill` | tag + commit in `jobs/Job_001_resource_gathering/log/parameters.json`; P0/P1/P2 gap table | no line-level citations (0 `path:line` in `references/`); empty sha256 table; web pages listed but not snapshotted; a documented probe flag did not exist (`jobs/Job_002_skill_authoring/JOB_LOG.md:52`) |
| `Namddinator_skill` | pin in snapshot filenames (`_<sha>_<date>`); claim-by-claim verification report (`jobs/Job_002_build_namdinator_skill/output/verification_report_2026-06-30.md`) | user-supplied repo was not canonical; two `.pdf` files are PMC HTML challenge pages; README accession typo; 185 MB duplicate raw store |
| `boltz_skill` | live `--help` resolved every docs-vs-source default (`jobs/Job_002_build_skill/JOB_LOG.md:54-57`) | live captures left in `artifacts/scratch/`; papers DOI-only; sha256 rows with host-absolute paths |
| `cryoAtom` | release vs master labelled; "not collected deliberately" list | hashes "printed to stdout" that is empty; README badge/tag/master disagree; Claude draft invented aliases; deep audit ran out of budget, compact packet worked |
| `cryodrgn_skill` | tag + commit + timestamp in `sources/source/source_refs.md` | tag object vs commit confusion; stale README `-h` defaults; server live capture never brought back; 2.1 MB raw HTML per page |

## Patterns across all six
- Live `--help` and fixtures always arrived after gathering, at build time. Now there
  is either a Task D or a mandatory live-verification checklist.
- Audits against the pinned source found real errors every time. That is why
  `verification.md` and the "allowlist" rule in the hand-off exist.
- Fetch commands were rarely saved (empty `scripts/` folders). Briefs and logs are now
  kept, or `logs/fetch_commands.md` for inline gathering.
- Folder layouts drifted (`sources/`, `artifacts/sources/`, `references/`). The skill
  defaults to `sources/`; the scripts take `--sources` and `--prefix` for other layouts.
