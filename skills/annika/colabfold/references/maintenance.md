# Update the ColabFold skill

Use for an explicit request to update/refresh this skill's software knowledge, tutorials or sources. Maintain the knowledge bundle without invoking the runtime or requiring a GPU probe. Installation, downloads of weights/data, inference, host configuration and publishing retain their separate task authorization.

## Verified coverage

Latest GitHub release verified 2026-09-07: **v1.6.2, 2026-07-14**, commit `c7d1772352cc9619df25c6d36cb0f218c0c6610e`; the existing AF2 source pin remains. Current main `c35de0221f4d297a39edf4cf292ba2832e321edc` (2026-08-28) also lists an OpenFold3 notebook. Notebook availability is separate from the stable AF2 CLI and host validation.

Added v1.6.2 performance and compilation guidance plus routing for the newer OpenFold3 notebook. No AlphaFold3 execution capability or new host validation is claimed.

## Authoritative sources

| Purpose | Source | Inspect |
|---|---|---|
| Release notes | [Release notes](https://github.com/sokrypton/ColabFold/releases) | Actual release body/date; resolve cached /latest disagreements through the explicit tag and GitHub API. |
| Stable README/tutorial sections | [Stable README/tutorial sections](https://github.com/sokrypton/ColabFold/blob/v1.6.2/README.md) | Local/remote MSA, GPU search, compilation cache and linked presentations. |
| Current README/notebooks | [Current README/notebooks](https://github.com/sokrypton/ColabFold) | Discover new notebooks and compare with the stable release; identify the backend before importing examples. |
| Pinned CLI | [Pinned CLI](https://github.com/sokrypton/ColabFold/blob/v1.6.2/colabfold/batch.py) | Exact flag names, defaults, outputs and network/destructive behavior. |

## Refresh procedure

1. Locate the repository and loaded skill directory; compare copies and preserve a diff/backup outside the package. Preserve external site configs, existing fixtures and populated lessons. Do not assume an installation path or overwrite a local variant.
2. Open the release index and actual release body; record version, release date, prerelease status, resolved commit and retrieval date. Compare the previous baseline and current documentation tree. Read changed pages as well as new tutorial URLs; unchanged version numbers do not prove unchanged documentation.
3. Compare README, notebooks, `batch.py`, `input.py`, `mmseqs/`, package dependencies and container recipes at explicit commits. Review AF2 versus AF3/OpenFold3 scope, MSA/template network effects, JAX/CUDA requirements, Pallas/compile controls, output reuse and summarizer compatibility. Update `source-map.md`, `workflows.md` and `validation-and-troubleshooting.md`; change fixtures or version pins only with corresponding evidence.
4. Save selected snapshots and a small manifest outside the installable skill: URL, retrieval date, status/error, content hash and destination reference. Use concise scenario → decision → validation guidance with direct source links. Label historical, development-only and unavailable-source claims; never turn a successful fetch into a claim of full coverage or local validation.
5. Keep the entrypoint a short route to this file and the owning references. Run the available skill-creator `quick_validate.py`, resolve local links and check added upstream links. If executable helpers change, run their relevant offline checks; real software tests require the appropriate target and task scope.
6. Rehearse a self-update request, an ordinary tool question and a version-mismatch/tutorial question. Review the diff for scope changes or private material. Synchronize only authorized copies, preserving local settings. Report what changed, evidence checked, validation results and remaining gaps; advance freshness dates only for the inspected scope.

Example: **“Update the ColabFold skill from official releases and tutorials, retaining its execution boundaries and historical validation evidence.”**
