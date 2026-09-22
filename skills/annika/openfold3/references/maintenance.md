# Update the OpenFold3 skill

Use this page when the user explicitly asks to update or refresh the skill's software knowledge, tutorials or sources.
Maintaining the knowledge bundle does not invoke the runtime and needs no GPU probe. Installation, weight or CCD
downloads, image builds, inference, host configuration and publishing each still need their own task authorization.

## Verified coverage

Latest GitHub release verified 2026-09-22: **v0.5.0 "OpenBind Model Release", 2026-08-21**, commit
`c4771653c5d0a3ebb0b3af71b05efd64bc44ee86`. Its default checkpoint is `openbind-2025-06-30-174k`. The legacy tag is **0.4.1**,
`d12f59554adacf8638e41f1ebc2d7725a8bb7a4b`. The kit is `anthropics/uplifting-biomolecular-modeling` @
`f4f62fa6592ae4938d49b1757bea0cfeff9f468e` (2026-09-17, unmaintained reference release) and pins exactly these two tags.
The inspected upstream `main` is `68b9c5e7fc44b1ca6f16e36bff2aee1656ca6919` (2026-09-22), 48 commits after v0.5.0. It is
not a release and the kit refuses it.

Historical GPU validation: 2026-09-22 on A100-SXM4 40 GB and H100 94 GB (kit `openfold3_ob0`, Apptainer image, inputs of
13–995 polymer residues / 52–995 model tokens, single-sequence, no templates; see `09_validation_and_benchmarks.md`). That validation belongs to that
stack and date only.

Watch list. These are on `main` or a branch and not in v0.5.0. Do not document them as usable until a tagged release
contains them:
- a chain field `ligand_name` for SMILES ligands (the v0.5.0 schema forbids unknown fields);
- template fetches skipped when no templates are given, and batched RCSB requests;
- the hand-kept conda environment files and `docker/Dockerfile.conda` removed (pixi is the only supported build path);
- `covalent_bonds` support (branch `pr-397`; the v0.5.0 schema field is not consumed);
- the chemical-steering branch (`feature/stereo-steering-framework`).

## Authoritative sources

| Purpose | Source | Inspect |
|---|---|---|
| Releases and tags | [Releases](https://github.com/aqlaboratory/openfold-3/releases) | Release body and date, resolved commit, checkpoint names (the v0.5.0 note misspells the key; trust `parameters.py`), deprecations. Check PyPI `openfold3` separately |
| Pinned CLI and schema | [run_openfold.py @ v0.5.0](https://github.com/aqlaboratory/openfold-3/blob/v0.5.0/openfold3/run_openfold.py) · [inference_query_format.py @ v0.5.0](https://github.com/aqlaboratory/openfold-3/blob/v0.5.0/openfold3/projects/of3_all_atom/config/inference_query_format.py) | Option names, `BOOLEAN` value flags, defaults. Query fields and their levels; extra fields forbidden |
| Weights registry | [parameters.py @ v0.5.0](https://github.com/aqlaboratory/openfold-3/blob/v0.5.0/openfold3/entry_points/parameters.py) · [S3 listing](https://openfold3-data.s3.amazonaws.com/?list-type=2&prefix=openfold3-parameters%2F) | Default and legacy names, `version_compatibility`, file names. Unregistered objects in the bucket are not defaults |
| Rendered docs | [ReadTheDocs stable](https://openfold-3.readthedocs.io/en/stable/) · [latest](https://openfold-3.readthedocs.io/en/latest/) | `stable` should equal the newest tag and `latest` tracks `main`. Resolve differences against the tagged source |
| Kit | [uplifting-biomolecular-modeling](https://github.com/anthropics/uplifting-biomolecular-modeling) | New commits or tags. `openfold3_ob0/{README.md,STOCK.md,CHANGES.md,run.sh,stock/PINS.json}`, `opt/openfold3_ob0_opt/{cli.py,modes.py}` |
| Weights terms and benchmarks | [OpenBind-0 announcement](https://openbind.uk/news/blog-openbind-0-advancing-open-molecular-structure-prediction/) · [Zenodo 10.5281/zenodo.22037460](https://zenodo.org/records/22037460) · [HF OpenFold/OpenFold3](https://huggingface.co/OpenFold/OpenFold3) | Licence statements, new OpenBind releases, benchmark supersession (official updated PLINDER) |
| Community | [Issues](https://github.com/aqlaboratory/openfold-3/issues) | New failure modes since 2026-09-18, cited by number and date |

## Refresh procedure

1. **Back up and compare.** Locate the repository copy and the loaded skill directory. Compare them and save a diff or
   backup outside the package. Preserve external site configs (`configs/site_config.local.md`), existing fixtures and
   populated `lessons.md`. Do not assume an install path and do not overwrite a local variant.
2. **Record the release state.** Open the release index and the actual release body. If the named release or tag does
   not exist, stop, report the latest tag, and edit nothing. Record version, date, prerelease
   status, resolved commit and retrieval date. Diff the new tag against `v0.5.0` for `run_openfold.py`, `setup_openfold.py`,
   `entry_points/{parameters,validator,experiment_runner}.py`, `inference_query_format.py`, `model_setting_presets.yml`,
   `core/runners/writer.py`, `colabfold_msa_server.py`, `rscb.py`, `pyproject.toml`/`pixi.toml`, `docker/` and
   `docs/source/`. An unchanged
   version number does not prove the docs are unchanged.
3. **Update references together.** Owning references must move in step:
   - CLI flags, defaults or console scripts → `03_cli_reference.md`, with a live `run_openfold predict --help` from a real
     install when possible.
   - Query fields → `04_input_query_format.md`, `scripts/make_query.py` and `templates/queries/`.
   - Checkpoint registry, weights licence or MSA/template behaviour → `07_msa_templates_weights.md` and
     `02_install_and_environment.md`.
   - Kit commit, pins, modes, flags or exit codes → `06_kit_modes_and_multigpu.md`. **If a new upstream release is not
     pinned by the kit, say so plainly.** The kit then supports only its old tags.
   - Outputs → `08_outputs_and_confidence.md` and `scripts/summarize_openfold3_output.py`.
   - Failures → `10_troubleshooting.md` and `11_decision_trees.md`.
   - Always update `01_source_map.md` and this page.
4. **Snapshot evidence outside the package.** Save selected snapshots and a small manifest outside the installable skill:
   URL, retrieval date, status or error, content hash and the destination reference. Label historical, development-only
   (`main`, branches) and unavailable-source claims. A successful fetch is not a claim of full coverage or of local
   validation.
5. **Validate the package.** Keep `SKILL.md` a short route to this file and the owning references. Run
   `tests/validate_static.py` and `quick_validate.py` from the skill-creator skill
   (`<skill-creator>/scripts/quick_validate.py <skill_dir>`; skip it with a note if absent), resolve local links and check added
   upstream links. If the scripts changed, run their offline checks (`--help`, probe `--json` on a non-GPU host).
   Real GPU tests need the right target and task scope.
6. **Rehearse and report.** Rehearse three requests: a self-update, an ordinary prediction question, and a version-mismatch
   question (e.g. "I have openfold3 0.6"). Review the diff for scope changes and for private material, which must include
   no host names, user names, accounts, partitions or local paths. Synchronize only authorized copies and preserve local
   settings. Report what changed, the evidence checked, validation results and remaining gaps. Advance freshness dates only
   for the scope you inspected.

## Rules

- Never relabel the 2026-09-22 GPU validation as testing a newer release, kit commit, card or input range. Newer versions
  are "source-reviewed, not host-validated" until a new fixture passes on a real host.
- Never recommend running the kit against an upstream tag it does not pin, preview-2 weights on `>=0.5`, or a checkpoint
  name that is only in release prose or the S3 listing and not in the registry.
- Preserve local site configs and lessons. Evidence snapshots live outside the package.
- Anything not confirmed in pinned source or live help stays **[unverified]**.

Example: **"Update the OpenFold3 skill from the latest openfold-3 release, the kit repository and the ReadTheDocs pages,
keeping its execution boundaries and historical validation evidence."**
