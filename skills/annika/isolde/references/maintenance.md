# Update the ISOLDE skill

Use for “update/refresh this skill,” latest-release/tutorial audits, and source maintenance. This changes the knowledge bundle and authorized copies; it does not authorize installing/upgrading software, launching compute, changing a live GUI/session, or publishing.

## Verification scope

Toolshed checked 2026-09-07: **1.12.1 macOS (2026-09-04)** and **1.12.0 Linux/Windows (2026-06-26)**, both for **ChimeraX 1.12.x**. Online docs identify **1.12.0**. Historical local Mac lessons include April 2026 runs, not tests of these releases; retain those dates and locally validated ligand precedents. Installed ISOLDE, ChimeraX, OpenMM platform/precision and GPU usability require a target-session check.

## Authoritative source map

Destinations below are relative to `references/` unless marked entrypoint.

| Purpose | Source | Owning reference |
|---|---|---|
| Published bundle and compatibility | [Toolshed release history](https://cxtoolshed.rbvi.ucsf.edu/apps/chimeraxisolde), [download instructions](https://tristanic.github.io/isolde/download/index.html) | `commands.md`: platform-specific releases, missing macOS preflight fix |
| Public command interface | [Command manual](https://tristanic.github.io/isolde/static/isolde/doc/commands/isolde.html) | `commands.md`, `debugging.md`: preflight/status/validation before private patches |
| Model preparation/map frames | [Getting Started](https://tristanic.github.io/isolde/static/isolde/doc/tools/gui/getting_started.html) | Entrypoint preflight and `commands.md`: targeted chemistry fixes and Clipper association |
| Tutorial discovery | [GUI/tutorial index](https://tristanic.github.io/isolde/static/isolde/doc/tools/ISOLDE.html), [AlphaFold multimer cryo-EM](https://tristanic.github.io/isolde/static/isolde/doc/tutorials/alphafold/multimer/alphafold_multimer_cryoem.html) | `commands.md`: current AlphaFold route; superseded bulk fitting |
| Implementation fallback | [Upstream repository](https://github.com/tristanic/isolde) | Version-pin private API investigations; never infer published release from branch name |

## Refresh procedure

1. Resolve the loaded skill root and source checkout; compare authorized copies and save a diff/backup outside the skill. Preserve populated lessons, local configuration, host paths and prior validation reports. The public source is `skills/annika/isolde/` in [StructAgent](https://github.com/bhgtiger/StructAgent); installed paths vary.
2. Open the release source and actual compatibility/release details, then selected manuals/tutorials. Record version, date, production/prerelease/source status and retrieval date. Do not call a search excerpt, an HTTP success code, or an unchanged page title proof of freshness. Check page contents; label missing or partially verified coverage.
3. Check Toolshed per platform: the version on the online manual can lag a wheel fix. Revisit public preflight/status/validation, parameter loading, terminal residue handling, and GUI warning behavior before carrying forward private patches or blanket deletions. Inspect the tutorial index for superseded workflows. Rehearse a 1.12.0 macOS missing-command failure, an unmatched ligand, and a map association problem without starting a simulation.
4. Save source snapshots and a manifest **outside the installable package** (URL, retrieval status/date, SHA-256 when available, claim → owning reference, errors). Update affected advice in place; preserve historical test provenance and distinguish documentation checks from executed tests. Keep long transcripts, downloaded wheels/data, and real job artifacts out of the package.
5. Add concise scenario → decision → validation guidance with direct sources and applicable version gates. Keep the entrypoint focused on routing; avoid a new reference per release. Preserve execution safeguards and user authorization already established for the task.
6. Run the available skill-creator validator `quick_validate.py` (from that skill’s own scripts directory) on this skill and check local reference/script paths, changed external links, and the diff. Test changed scripts with meaningful offline inputs when feasible; do not report documentation review as a software smoke test. Review existing failures separately from introduced regressions.
7. Synchronize only reviewed general-purpose files to authorized copies; preserve local settings/lessons. Report sources, concrete corrections, validation, entrypoint size changes and verification gaps. Installation upgrades and publishing remain separate tasks.

## Known verification gaps (2026-09-07)

GitHub Releases returned an empty list; a guessed standalone changelog URL returned 404. `isolde load parameters` is announced in Toolshed but the fetched command page lacks full syntax: inspect installed help before emitting arguments. Historical monitored scripts still require version-specific adaptation (chemistry cleanup, popup loop, private APIs, checkpoint spelling); no 1.12 GUI or OpenMM run was performed.
