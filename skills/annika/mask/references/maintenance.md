# Update the mask skill

Use for “update/refresh this skill,” latest-release/tutorial audits, and source maintenance. This changes the knowledge bundle and authorized copies; it does not authorize installing/upgrading software, launching compute, changing a live GUI/session, or publishing.

## Verification scope

Checked 2026-09-07: ChimeraX production **1.12 (2026-06-11)** and current CryoSPARC mask/Volume Tools pages, including **v5** lowpass defaults. The mask skill is a local script workflow, not an upstream versioned software release. Its historical **≥1.8 macOS** scope and script defaults remain historical; no current target environment or output map was tested.

## Authoritative source map

Destinations below are relative to `references/` unless marked entrypoint.

| Purpose | Source | Owning reference |
|---|---|---|
| ChimeraX production/development | [Download metadata](https://www.rbvi.ucsf.edu/chimerax/data/release-info/production.json), [change log](https://www.rbvi.ucsf.edu/trac/ChimeraX/wiki/ChangeLog) | Entrypoint version scope; delegate general CLI compatibility to `chimerax` |
| Exact volume operations | [volume](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/volume.html), [molmap](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/molmap.html) | `chimerax_commands.md`: units, threshold syntax, grid handling |
| Mask tutorial and methods | [Mask Creation](https://guide.cryosparc.com/processing-data/tutorials-and-case-studies/mask-selection-and-generation-in-ucsf-chimera) | `mask_theory.md`, `gui_methods.md`: 12 Å floor, coverage, segmentation and complements |
| Handoff/version-specific parameters | [Volume Tools](https://guide.cryosparc.com/processing-data/all-job-types-in-cryosparc/utilities/job-volume-tools) | `cryosparc_volume_tools.md`: selected input, final-pixel units, v5 filtering, cosine edge |
| Find renamed tutorials | [CryoSPARC llms.txt](https://guide.cryosparc.com/llms.txt) | Resolve changed Guide URLs; fetch selected `.md` pages |

## Refresh procedure

1. Resolve the loaded skill root and source checkout; compare authorized copies and save a diff/backup outside the skill. Preserve populated lessons, local configuration, host paths and prior validation reports. The public source is `skills/annika/mask/` in [StructAgent](https://github.com/bhgtiger/StructAgent); installed paths vary.
2. Open the release source and actual compatibility/release details, then selected manuals/tutorials. Record version, date, production/prerelease/source status and retrieval date. Do not call a search excerpt, an HTTP success code, or an unchanged page title proof of freshness. Check page contents; label missing or partially verified coverage.
3. Read the script implementation alongside the owning references before changing parameter descriptions. Distinguish Gaussian sigma from cosine padding and approximate blur/threshold expansion from spherical dilation. Check current Guide method recommendations and Volume Tools operation ordering. Rehearse a model-to-base handoff, a changed-pixel-size padding calculation, and a subtraction complement. If code changes are needed, validate numeric/grid invariants with synthetic data before any user-map run.
4. Save source snapshots and a manifest **outside the installable package** (URL, retrieval status/date, SHA-256 when available, claim → owning reference, errors). Update affected advice in place; preserve historical test provenance and distinguish documentation checks from executed tests. Keep long transcripts, downloaded wheels/data, and real job artifacts out of the package.
5. Add concise scenario → decision → validation guidance with direct sources and applicable version gates. Keep the entrypoint focused on routing; avoid a new reference per release. Preserve execution safeguards and user authorization already established for the task.
6. Run the available skill-creator validator `quick_validate.py` (from that skill’s own scripts directory) on this skill and check local reference/script paths, changed external links, and the diff. Test changed scripts with meaningful offline inputs when feasible; do not report documentation review as a software smoke test. Review existing failures separately from introduced regressions.
7. Synchronize only reviewed general-purpose files to authorized copies; preserve local settings/lessons. Report sources, concrete corrections, validation, entrypoint size changes and verification gaps. Installation upgrades and publishing remain separate tasks.

## Known verification gaps (2026-09-07)

Two guessed Guide URLs returned HTTP 200 with a Page Not Found body; they were replaced via the current index. Script Gaussian defaults were not recalibrated or newly validated. This refresh documents their meaning and recommends explicit unsoftened bases with Volume Tools finalization. GUI tutorials were read but not executed.
