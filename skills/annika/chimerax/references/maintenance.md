# Update the ChimeraX skill

Use for “update/refresh this skill,” latest-release/tutorial audits, and source maintenance. This changes the knowledge bundle and authorized copies; it does not authorize installing/upgrading software, launching compute, changing a live GUI/session, or publishing.

## Verification scope

Production **1.12 (2026-06-11)** verified 2026-09-07 from the download page’s production JSON and change log. Historical workflow floor: **≥1.8 on macOS**, with local observations in `learned.md`/`lessons.md`; no exact new execution baseline is asserted. Installed ChimeraX and bundles must be discovered for the target run.

## Authoritative source map

Destinations below are relative to `references/` unless marked entrypoint.

| Purpose | Source | Owning reference |
|---|---|---|
| Production versus development | [Download](https://www.rbvi.ucsf.edu/chimerax/download.html), [enabled release channels](https://www.rbvi.ucsf.edu/chimerax/data/release-info/enabled.json), [production JSON](https://www.rbvi.ucsf.edu/chimerax/data/release-info/production.json), [change log](https://www.rbvi.ucsf.edu/trac/ChimeraX/wiki/ChangeLog) | `commands.md`: compatibility and development-only caveats |
| Exact fit/export behavior | [fitmap](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/fitmap.html), [save](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/save.html) | `commands.md` and entrypoint transform/extraction caveats |
| Tutorial discovery | [Tutorial index](https://www.rbvi.ucsf.edu/chimerax/tutorials.html), [cryo-EM introduction](https://www.rbvi.ucsf.edu/chimerax/data/stanford-apr2022/cryoem_intro.html) | `commands.md`: worked fit and export validation |
| Plugin compatibility | [Toolshed](https://cxtoolshed.rbvi.ucsf.edu/) and each required bundle’s release history | Route ISOLDE and DAQplugin details to their skills |

## Refresh procedure

1. Resolve the loaded skill root and source checkout; compare authorized copies and save a diff/backup outside the skill. Preserve populated lessons, local configuration, host paths and prior validation reports. The public source is `skills/annika/chimerax/` in [StructAgent](https://github.com/bhgtiger/StructAgent); installed paths vary.
2. Open the release source and actual compatibility/release details, then selected manuals/tutorials. Record version, date, production/prerelease/source status and retrieval date. Do not call a search excerpt, an HTTP success code, or an unchanged page title proof of freshness. Check page contents; label missing or partially verified coverage.
3. Compare release channels rather than treating the newest change-log date as production. The download HTML populates versions from JSON; empty rendered version fields are not evidence of no release. Confirm fitmap defaults, selected-only export, and coordinate-frame behavior against the current manuals before modifying wrapper examples. Rehearse a transformed-model export, a bundle compatibility question, and a self-refresh request.
4. Save source snapshots and a manifest **outside the installable package** (URL, retrieval status/date, SHA-256 when available, claim → owning reference, errors). Update affected advice in place; preserve historical test provenance and distinguish documentation checks from executed tests. Keep long transcripts, downloaded wheels/data, and real job artifacts out of the package.
5. Add concise scenario → decision → validation guidance with direct sources and applicable version gates. Keep the entrypoint focused on routing; avoid a new reference per release. Preserve execution safeguards and user authorization already established for the task.
6. Run the available skill-creator validator `quick_validate.py` (from that skill’s own scripts directory) on this skill and check local reference/script paths, changed external links, and the diff. Test changed scripts with meaningful offline inputs when feasible; do not report documentation review as a software smoke test. Review existing failures separately from introduced regressions.
7. Synchronize only reviewed general-purpose files to authorized copies; preserve local settings/lessons. Report sources, concrete corrections, validation, entrypoint size changes and verification gaps. Installation upgrades and publishing remain separate tasks.

## Known verification gaps (2026-09-07)

The guessed `docs/relnotes.html` returned 404; use the linked change log. Documentation was retrieved directly when the web reader blocked UCSF pages. The wrapper was not executed in ChimeraX; ≥1.8 compatibility remains historical scope.
