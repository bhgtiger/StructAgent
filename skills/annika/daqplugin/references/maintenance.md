# Update the DAQplugin skill

Use for “update/refresh this skill,” latest-release/tutorial audits, and source maintenance. This changes the knowledge bundle and authorized copies; it does not authorize installing/upgrading software, launching compute, changing a live GUI/session, or publishing.

## Verification scope

Checked 2026-09-07: **Toolshed 1.0.7 (2026-07-17)**; **GitHub Release 1.0.1 (2026-05-12)**; **source metadata 1.0.8 at `7c158f35604d7647078ce62afd7e907afc16bdc5`**. Keep these channels separate. The earlier `8a367f6`/1.0.4 command source is historical provenance, not proof of an installed version or a new inference validation.

## Authoritative source map

Destinations below are relative to `references/` unless marked entrypoint.

| Purpose | Source | Owning reference |
|---|---|---|
| Distributed bundle behavior | [Toolshed release history](https://cxtoolshed.rbvi.ucsf.edu/apps/chimeraxdaqplugin) | `commands.md`: 1.0.5 plot workflow, 1.0.7 NVIDIA detection |
| Release artifacts | [GitHub releases](https://github.com/kiharalab/DAQplugin/releases) | `commands.md`: released wheel versus source version and lazy first-use weights |
| Current dependency constraints | [Bundle metadata](https://github.com/kiharalab/DAQplugin/blob/main/daqcolor/pyproject.toml) | `commands.md`: version-pin observed constraints; do not generalize to older wheels |
| Command and GUI tutorials | [Manual](https://github.com/kiharalab/DAQplugin/blob/main/MANUAL.md), [README](https://github.com/kiharalab/DAQplugin) | `commands.md` and entrypoint: compute/color/plot/monitor workflow |
| External notebook alternative | [Grid notebook](https://github.com/kiharalab/DAQplugin/blob/main/DAQ_Score_Grid.ipynb) | Discover when local compute is unsuitable; uploading private inputs is separate authorization |

## Refresh procedure

1. Resolve the loaded skill root and source checkout; compare authorized copies and save a diff/backup outside the skill. Preserve populated lessons, local configuration, host paths and prior validation reports. The public source is `skills/annika/daqplugin/` in [StructAgent](https://github.com/bhgtiger/StructAgent); installed paths vary.
2. Open the release source and actual compatibility/release details, then selected manuals/tutorials. Record version, date, production/prerelease/source status and retrieval date. Do not call a search excerpt, an HTTP success code, or an unchanged page title proof of freshness. Check page contents; label missing or partially verified coverage.
3. Compare Toolshed, GitHub release objects and source metadata independently. Pin the source commit used for manual/dependency claims. Check command registration if a manual example conflicts with its signature, especially monitor backend arguments and point-cloud metrics. Review backend detection, forced versus auto fallback, model downloads and per-residue inspection tutorials. Rehearse unexpected CPU fallback, green/unscored residues, and a precomputed-grid monitoring request.
4. Save source snapshots and a manifest **outside the installable package** (URL, retrieval status/date, SHA-256 when available, claim → owning reference, errors). Update affected advice in place; preserve historical test provenance and distinguish documentation checks from executed tests. Keep long transcripts, downloaded wheels/data, and real job artifacts out of the package.
5. Add concise scenario → decision → validation guidance with direct sources and applicable version gates. Keep the entrypoint focused on routing; avoid a new reference per release. Preserve execution safeguards and user authorization already established for the task.
6. Run the available skill-creator validator `quick_validate.py` (from that skill’s own scripts directory) on this skill and check local reference/script paths, changed external links, and the diff. Test changed scripts with meaningful offline inputs when feasible; do not report documentation review as a software smoke test. Review existing failures separately from introduced regressions.
7. Synchronize only reviewed general-purpose files to authorized copies; preserve local settings/lessons. Report sources, concrete corrections, validation, entrypoint size changes and verification gaps. Installation upgrades and publishing remain separate tasks.

## Known verification gaps (2026-09-07)

No installed bundle/backend probe or inference run was performed. Source 1.0.8 was not established as a published artifact. One manual backend example conflicts with its monitor signature; keep unsupported arguments out of generated commands until checked. The linked notebook was discovered, not executed.
