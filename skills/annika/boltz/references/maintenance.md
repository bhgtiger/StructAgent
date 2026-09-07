# Update the Boltz skill

Use for an explicit request to update/refresh this skill's software knowledge, tutorials or sources. Maintain the knowledge bundle without invoking the runtime or requiring a GPU probe. Installation, downloads of weights/data, inference, host configuration and publishing retain their separate task authorization.

## Verified coverage

Latest GitHub release verified 2026-09-07: **v2.2.1, 2025-09-08**, commit `cb04aeccdd480fd4db707f0bbafde538397fa2ac`. This matches the skill's historical 2026-06-23 test baseline; no new prediction was run. The inspected main revision is `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc` (2026-05-29).

The current prediction guide corrects the model-dependent `step_scale` default; the skill's CLI table was already correct. Core workflows now explain how to check tutorial drift and reuse an approved protein MSA in screening.

## Authoritative sources

| Purpose | Source | Inspect |
|---|---|---|
| Releases and tags | [Releases and tags](https://github.com/jwohlwend/boltz/releases) | Release status, dates, resolved commits; check PyPI independently if using packaged installs. |
| Prediction guide | [Prediction guide](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md) | Input schema, constraints, affinity, output fields and authenticated MSA examples; compare with the pinned tag. |
| README and documentation tree | [README and documentation tree](https://github.com/jwohlwend/boltz) | Discover changed prediction/training/evaluation docs and examples; a new main commit is not a new release. |
| CLI implementation | [CLI implementation](https://github.com/jwohlwend/boltz/blob/v2.2.1/src/boltz/main.py) | Resolve guide/help/default conflicts against the selected revision. |

## Refresh procedure

1. Locate the repository and loaded skill directory; compare copies and preserve a diff/backup outside the package. Preserve external site configs, existing fixtures and populated lessons. Do not assume an installation path or overwrite a local variant.
2. Open the release index and actual release body; record version, release date, prerelease status, resolved commit and retrieval date. Compare the previous baseline and current documentation tree. Read changed pages as well as new tutorial URLs; unchanged version numbers do not prove unchanged documentation.
3. Compare `docs/prediction.md`, `src/boltz/main.py`, schema, writer and dependency manifests. Check model-dependent defaults, contact/template conditioning, MSA authentication, cache reuse and the meaning of both affinity fields. Update `01_source_map.md`, `03_cli_reference.md`, `04_input_yaml_schema.md`, and the owning workflow/output/troubleshooting pages together. Never relabel an old GPU fixture as testing a newer version.
4. Save selected snapshots and a small manifest outside the installable skill: URL, retrieval date, status/error, content hash and destination reference. Use concise scenario → decision → validation guidance with direct source links. Label historical, development-only and unavailable-source claims; never turn a successful fetch into a claim of full coverage or local validation.
5. Keep the entrypoint a short route to this file and the owning references. Run the available skill-creator `quick_validate.py`, resolve local links and check added upstream links. If executable helpers change, run their relevant offline checks; real software tests require the appropriate target and task scope.
6. Rehearse a self-update request, an ordinary tool question and a version-mismatch/tutorial question. Review the diff for scope changes or private material. Synchronize only authorized copies, preserving local settings. Report what changed, evidence checked, validation results and remaining gaps; advance freshness dates only for the inspected scope.

Example: **“Update the Boltz skill from official releases and tutorials, retaining its execution boundaries and historical validation evidence.”**
