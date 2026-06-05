# 01 — Source map (how this skill is grounded)

## Pin
- Repo: `https://github.com/tbepler/topaz`
- Commit: `58fe52370f4accb8215525df2ea8f2c7ee6d340a`
- Tag/branch: **v0.3.20** (= `master` HEAD), `git describe --tags` → `v0.3.20`
- Fetched: 2026-06-05 (shallow clone)
- License: **GPLv3**; PyPI dist `topaz-em`; import `topaz`; entry point `topaz.main:main`
- Python supported: `>=3.8,<=3.13` (README: 3.8–3.12)

Full raw capture lives in the **project** (not shipped in the installed skill):
`references/source/SNAPSHOT.md`, `references/source/source_inventory.md`,
`references/web/source_map.md`, `references/cli/…`, `references/data_model/…`,
and the working clone `references/source/topaz_clone/`.

## Primary sources behind each skill reference
| Skill ref | Grounded in |
|---|---|
| 02 config/device | `topaz/cuda.py`, `topaz/torch.py`, `topaz/extract.py`, `topaz/denoise.py`, `topaz/training.py`, README "Prerequisites", per-command `--device` |
| 03 CLI | `topaz/main.py`, `topaz/commands/*.py` (`name`/`help`/`add_arguments`) |
| 04 formats | `topaz/mrc.py`, `topaz/commands/convert.py`, `topaz/training.py`, README "File formats" |
| 05 workflows | README usage, `docs/source/tutorial.md`, `docs/source/commands/*`, `tutorial/*.ipynb` |
| 08 validation | Nat Methods 2019 paper, denoising preprint, `test/` |
| 09 troubleshooting | `topaz/cuda.py` CudaWarning, install docs, requirements |

## External pointers (secondary to pinned source)
- Docs site: https://topaz-em.readthedocs.io/en/latest/
- Discussions: https://github.com/tbepler/topaz/discussions
- Method paper: https://doi.org/10.1038/s41592-019-0575-8
- Denoising preprint: https://doi.org/10.1101/838920
- Conda channel: https://anaconda.org/tbepler/topaz
- PyTorch install: https://pytorch.org/get-started/locally/

## Re-grounding procedure (when pin changes)
1. Re-clone at the new tag; update `references/source/SNAPSHOT.md`.
2. Update `scripts/topaz_env_probe.py` `SOURCE_EVIDENCE` (commit/tag + device evidence).
3. Re-verify device dispatch (`grep -i mps topaz/`), `--device` defaults, CLI help.
4. Update skill refs 02/03/04 and this file. Bump SKILL.md `metadata.topaz_pin`.
