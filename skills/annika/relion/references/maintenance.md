# Update the RELION skill

Use for an authorized documentation/source/tutorial refresh. This lane edits the knowledge bundle and skips runtime environment probing. It does not authorize a software installation/upgrade, dataset/model download, processing job, live-project mutation, or publication. Resume the entrypoint's config and execution gates for those tasks; reuse authorization already given within its scope.

## Checked scope — 2026-09-07

Stable **5.0.1** (2025-09-22); **5.1.0** (2026-03-13) explicitly marked prerelease. Historical local CLI capture remains **5.0.0**, 2026-06-04. Documentation verification, historical local testing, and the software installed on a target host are three separate facts. Preserve existing validation dates, captures and source pins; label new unexecuted behavior as documentation-verified. Do not call a release current based only on search snippets or a moving documentation URL.

## Tool-specific source map

| Purpose | Primary source | What to inspect |
|---|---|---|
| Release/status/compiler changes | [Release/status/compiler changes](https://github.com/3dem/relion/releases) | Open actual pages and confirm prerelease field; API: `https://api.github.com/repos/3dem/relion/releases`. |
| Stable manual | [Stable manual](https://relion.readthedocs.io/en/release-5.0/) | Resolve version branch explicitly; latest currently also identifies 5.0.x as stable. |
| SPA tutorial | [SPA tutorial](https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/index.html) | Discover affected stage pages before changing workflow guidance. |
| Tomo refinement cycle | [Tomo refinement cycle](https://relion.readthedocs.io/en/release-5.0/STA_tutorial/TomoRefinement.html) | Check reference origin, binning, optimisation-set propagation and re-extraction. |
| Helical tutorial | [Helical tutorial](https://relion.readthedocs.io/en/release-5.0/Reference/Helix.html) | Keep stable helical guidance distinct from 5.1 prerelease amyloid additions. |
| Tagged source | [Tagged source](https://github.com/3dem/relion/tree/5.0.1) | Reconcile `src/pipeline_jobs.cpp`, help, environment YAMLs and compiler requirements at the chosen tag. |

## Refresh procedure

1. Locate this skill from its loaded `SKILL.md`. Compare the repository and authorized installed copy before editing. Keep a diff/backup and evidence outside the installable skill; preserve private `site_config` files, probe reports, queue settings and populated lessons.
2. Open release index and actual relevant release bodies. Record release date, stable/prerelease status, source URL, retrieval date/status and resolved version or SHA. Read selected tutorial pages as well as release notes; compare page content, not just titles or hashes. If a page fails, try an official alternate and record the gap without advancing that page's freshness claim.
3. Edit `00_overview.md` for version map, `20_troubleshooting.md` for compiler/GPU dependency changes, `13_helical_amyloid.md` for amyloid algorithms/Schemes/network, and `14_tomo_sta.md` for 5.1 reconstruction/extraction changes. Inspect `03_cli_inventory.md` if new commands are added. Preserve `references/cli/relion5_cli_capture_20260604/` as historical evidence; never overwrite it with unexecuted or newer-version claims.
4. Store snapshots and a compact manifest (URL, retrieval date/status, SHA-256, claim → destination reference, gaps) in the user's maintenance workspace outside this package. Historical archive paths in references are provenance, not required runtime files. Keep full manuals, notebooks with embedded images, datasets, logs and site reports out of the portable skill.
5. Keep `SKILL.md` a short router for maintenance; load only affected references. Resolve contradictions in owning references and linked decision trees. Keep current-release source assertions separate from historical live-help/smoke assertions. Updating runtime pins/probe logic requires targeted validation; documentation maintenance alone cannot promote a new tested baseline.
6. Run the available skill-creator `quick_validate.py`; check changed local links and referenced script paths, YAML metadata, and diff for private paths/settings. If scripts change, exercise meaningful offline behavior without invoking real tools or scheduler submissions. Rehearse a self-update request (no probe), a release-specific question (version-aware source), and a real run (config/execution gate). Synchronize only authorized copies after validation, preserving local data.
7. Report checked versions/dates, owning-reference changes, validation results, and remaining gaps. Keep evidence of baseline validation failures. Publishing or live upgrading needs its own task scope.

## Current gaps

Release metadata and stable manual/tutorial pages checked, with selected owning-reference corrections. No 5.0.1/5.1 binary execution, new GPU compatibility testing, or live project inspection. A 5.0 `--amyloid` option does not prove new 5.1 algorithms are installed.

Example: “Refresh this RELION skill against official releases and tutorials, preserving its locally validated baseline and keeping snapshots outside the package.”
