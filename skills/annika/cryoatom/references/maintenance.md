# Update the CryoAtom skill

Use for an explicit request to update/refresh this skill's software knowledge, tutorials or sources. Maintain the knowledge bundle without invoking the runtime or requiring a GPU probe. Installation, downloads of weights/data, inference, host configuration and publishing retain their separate task authorization.

## Verified coverage

Verified 2026-09-07: latest GitHub release **v2.1.0, 2026-03-17**, commit `10fd7f4be3722d6a1ea6646c69e93476014184ab`. Main remains `856e250df7b784b854b892f1b619d32d51188cef` (2026-06-17), reporting **2.1.1 without a release tag**. This package intentionally pins that snapshot. Existing image observations remain historical; no new runtime was tested.

Reconfirmed both version identities and added an example-to-workflow map with output checks. Current release multi-GPU claims remain distinct from host-tested configurations.

## Authoritative sources

| Purpose | Source | Inspect |
|---|---|---|
| Release notes and tags | [Release notes and tags](https://github.com/YangLab-SDU/CryoAtom/releases) | Separate tagged release, untagged source version and actual installed runtime. |
| Pinned README examples | [Pinned README examples](https://github.com/YangLab-SDU/CryoAtom/blob/856e250df7b784b854b892f1b619d32d51188cef/README.md) | 7XHT sequence-guided, 9ENB identification, mask and backbone workflows. |
| Source tree and notebook | [Source tree and notebook](https://github.com/YangLab-SDU/CryoAtom) | Discover tutorial/weight changes; inspect notebooks without executing them. |
| Pinned build implementation | [Pinned build implementation](https://github.com/YangLab-SDU/CryoAtom/blob/856e250df7b784b854b892f1b619d32d51188cef/CryoAtom2/build.py) | CLI, rounds, outputs, timing and overwrite behavior. |

## Refresh procedure

1. Locate the repository and loaded skill directory; compare copies and preserve a diff/backup outside the package. Preserve external site configs, existing fixtures and populated lessons. Do not assume an installation path or overwrite a local variant.
2. Open the release index and actual release body; record version, release date, prerelease status, resolved commit and retrieval date. Compare the previous baseline and current documentation tree. Read changed pages as well as new tutorial URLs; unchanged version numbers do not prove unchanged documentation.
3. Compare README/notebook, build parser, output filtering, device selection, dependencies and weight acquisition. Check all polymer classes, six-weight cache layout and absent timing-log behavior. Update `03_cli_and_outputs.md`, `04_versions_and_requirements.md` and the owning install/operations references. A new pin must update both container recipes, config templates and verification expectations together; documentation refresh alone is not grounds to advance a runtime pin.
4. Save selected snapshots and a small manifest outside the installable skill: URL, retrieval date, status/error, content hash and destination reference. Use concise scenario → decision → validation guidance with direct source links. Label historical, development-only and unavailable-source claims; never turn a successful fetch into a claim of full coverage or local validation.
5. Keep the entrypoint a short route to this file and the owning references. Run the available skill-creator `quick_validate.py`, resolve local links and check added upstream links. If executable helpers change, run their relevant offline checks; real software tests require the appropriate target and task scope.
6. Rehearse a self-update request, an ordinary tool question and a version-mismatch/tutorial question. Review the diff for scope changes or private material. Synchronize only authorized copies, preserving local settings. Report what changed, evidence checked, validation results and remaining gaps; advance freshness dates only for the inspected scope.

Example: **“Update the CryoAtom skill from official releases and tutorials, retaining its execution boundaries and historical validation evidence.”**
