# 01 — Source Map

Where every claim in this skill can be checked. Pinned baseline: **v2.2.1**,
commit `cb04aeccdd480fd4db707f0bbafde538397fa2ac`. Main HEAD observed
2026-06-22: `b1ebfc46...` (repo is active; pin for reproducibility).

## Upstream

- Repo: https://github.com/jwohlwend/boltz
- Release: https://github.com/jwohlwend/boltz/releases/tag/v2.2.1
- PyPI: https://pypi.org/project/boltz/2.2.1/  (latest as of 2026-06-23)
- License: MIT (see the clone's `LICENSE`).

## Key source files (in the pinned clone `src/boltz/`)

| Claim area | File | Notes |
|---|---|---|
| CLI flags + defaults + help strings | `main.py` (`predict` Click command) | Authoritative for option names; some help text is stale (see 03). |
| YAML schema, entity rules, affinity limits | `data/parse/schema.py` | Affinity >128 atoms rejected / >56 heavy-atoms warns (~lines 1205-1271). |
| Output file names + JSON fields | `data/write/writer.py` | confidence/pae/pde/plddt/affinity naming + field lists. |
| Method conditioning vocabulary | `data/const.py` (`method_types_ids`) | `--method` values; Boltz-2 only. |
| Affinity cropping/featurization | `data/crop/affinity.py`, `data/feature/featurizerv2.py` | single-binder logic. |
| Model defaults | `model/models/boltz2.py`, `boltz1.py` | step_scale etc. |

## Papers (method/benchmark context — not CLI authority)

- Boltz-1: DOI 10.1101/2024.11.19.624167
- Boltz-2: DOI 10.1101/2025.06.14.659707
- ColabFold (MSA server): DOI 10.1038/s41592-022-01488-1

## Companion source project (for deeper digs)

The skill was built from a curated workspace with the pinned clone and extracted
surfaces. If you have access to it, see (in `Maria_projects/boltz_skill/`):
`artifacts/sources/boltz_v2.2.1/`, `references/cli/cli_surface_v2.2.1.md`,
`references/validation/validation_and_failure_modes.md`. Otherwise the upstream
repo at tag v2.2.1 is the source of truth.
