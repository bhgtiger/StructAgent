# Update the ModelAngelo skill

Use for an explicit request to update/refresh this skill's software knowledge, tutorials or sources. Maintain the knowledge bundle without invoking the runtime or requiring a GPU probe. Installation, downloads of weights/data, inference, host configuration and publishing retain their separate task authorization.

## Verified coverage

Latest GitHub release and main HEAD verified 2026-09-07: **v1.0.18, 2026-06-15**, commit `994945bdfa6e5368e0d62349a47792f4864eebc3`. The installer pin remains unchanged. This session reviewed documentation/source, not a new install or map build.

Added tutorial selection and a source-backed warning about sequence-aware nucleotide omission; retained the tested/reproducible installation pin.

## Authoritative sources

| Purpose | Source | Inspect |
|---|---|---|
| Release notes | [Release notes](https://github.com/3dem/model-angelo/releases) | Release status, compatibility and installation fixes. |
| README tutorials/FAQs | [README tutorials/FAQs](https://github.com/3dem/model-angelo/blob/v1.0.18/README.md) | Setup, cache, sequence-aware/no-sequence examples and validation handoff. |
| Installer source | [Installer source](https://github.com/3dem/model-angelo/blob/v1.0.18/install_script.sh) | Python/torch pins and sourced-script behavior. |
| RELION ModelBuilding tutorial | [RELION ModelBuilding tutorial](https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/ModelBuilding.html) | GUI workflow, HMM search and version-specific integration; course settings are examples. |
| Inference source | [Inference source](https://github.com/3dem/model-angelo/blob/v1.0.18/model_angelo/gnn/inference.py) | Sequence input and nucleotide handling, including omitted RNA/DNA sequences. |

## Refresh procedure

1. Locate the repository and loaded skill directory; compare copies and preserve a diff/backup outside the package. Preserve external site configs, existing fixtures and populated lessons. Do not assume an installation path or overwrite a local variant.
2. Open the release index and actual release body; record version, release date, prerelease status, resolved commit and retrieval date. Compare the previous baseline and current documentation tree. Read changed pages as well as new tutorial URLs; unchanged version numbers do not prove unchanged documentation.
3. Review installer/setup manifest, model bundle definitions, cache download code, `apps/` parsers and RELION integration against the selected tag. Update `01_source_map.md`, the installation/cache/CLI references and `07_codex_and_integration.md`. A managed distribution's default is not the upstream release. Preserve the installation-only scope; a tutorial map build is not an installation check.
4. Save selected snapshots and a small manifest outside the installable skill: URL, retrieval date, status/error, content hash and destination reference. Use concise scenario → decision → validation guidance with direct source links. Label historical, development-only and unavailable-source claims; never turn a successful fetch into a claim of full coverage or local validation.
5. Keep the entrypoint a short route to this file and the owning references. Run the available skill-creator `quick_validate.py`, resolve local links and check added upstream links. If executable helpers change, run their relevant offline checks; real software tests require the appropriate target and task scope.
6. Rehearse a self-update request, an ordinary tool question and a version-mismatch/tutorial question. Review the diff for scope changes or private material. Synchronize only authorized copies, preserving local settings. Report what changed, evidence checked, validation results and remaining gaps; advance freshness dates only for the inspected scope.

Example: **“Update the ModelAngelo skill from official releases and tutorials, retaining its execution boundaries and historical validation evidence.”**
