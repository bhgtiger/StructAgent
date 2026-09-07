# Update the CryoAtom Advisor skill

Use for an explicit request to update/refresh this skill's software knowledge, tutorials or sources. Maintain the knowledge bundle without invoking the runtime or requiring a GPU probe. Installation, downloads of weights/data, inference, host configuration and publishing retain their separate task authorization.

## Verified coverage

Verified 2026-09-07: latest GitHub release **v2.1.0, 2026-03-17**, commit `10fd7f4be3722d6a1ea6646c69e93476014184ab`, remains this advisor's static baseline. Untagged master `856e250df7b784b854b892f1b619d32d51188cef` reports 2.1.1. Do not inherit the executable CryoAtom skill's image evidence or pin.

Removed a baked-in Mac-host assertion, added current release provenance and documented the partial-sequence omission and timing-log traps in the static advisor.

## Authoritative sources

| Purpose | Source | Inspect |
|---|---|---|
| Release notes | [Release notes](https://github.com/YangLab-SDU/CryoAtom/releases) | Tagged release and feature changes. |
| Pinned README/tutorial examples | [Pinned README/tutorial examples](https://github.com/YangLab-SDU/CryoAtom/blob/v2.1.0/README.md) | Read-only workflow planning and tutorial discovery. |
| Pinned build code | [Pinned build code](https://github.com/YangLab-SDU/CryoAtom/blob/v2.1.0/CryoAtom2/build.py) | Static flags, outputs, defaults and timing-log behavior. |
| Pinned output filter | [Pinned output filter](https://github.com/YangLab-SDU/CryoAtom/blob/v2.1.0/CryoAtom2/utils/flood_fill.py) | Polymer retention with a partial sequence set. |

## Refresh procedure

1. Locate the repository and loaded skill directory; compare copies and preserve a diff/backup outside the package. Preserve external site configs, existing fixtures and populated lessons. Do not assume an installation path or overwrite a local variant.
2. Open the release index and actual release body; record version, release date, prerelease status, resolved commit and retrieval date. Compare the previous baseline and current documentation tree. Read changed pages as well as new tutorial URLs; unchanged version numbers do not prove unchanged documentation.
3. Review release versus master, README examples, build/output-filter code, requirements and paper status. Update `01_version_environment.md` and `02_static_cli_and_outputs.md`, keeping all claims static and commands NOT-RUN. Replace accidental host assertions with target-specific unknowns. This maintenance lane permits authorized edits to the knowledge bundle; the advisor remains read-only for installation, inference, configuration and user data.
4. Save selected snapshots and a small manifest outside the installable skill: URL, retrieval date, status/error, content hash and destination reference. Use concise scenario → decision → validation guidance with direct source links. Label historical, development-only and unavailable-source claims; never turn a successful fetch into a claim of full coverage or local validation.
5. Keep the entrypoint a short route to this file and the owning references. Run the available skill-creator `quick_validate.py`, resolve local links and check added upstream links. If executable helpers change, run their relevant offline checks; real software tests require the appropriate target and task scope.
6. Rehearse a self-update request, an ordinary tool question and a version-mismatch/tutorial question. Review the diff for scope changes or private material. Synchronize only authorized copies, preserving local settings. Report what changed, evidence checked, validation results and remaining gaps; advance freshness dates only for the inspected scope.

Example: **“Update the CryoAtom Advisor skill from official releases and tutorials, retaining its execution boundaries and historical validation evidence.”**
