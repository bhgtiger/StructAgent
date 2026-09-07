# Update the Topaz skill

Use for an authorized documentation/source/tutorial refresh. This lane edits the knowledge bundle and skips runtime environment probing. It does not authorize a software installation/upgrade, dataset/model download, processing job, live-project mutation, or publication. Resume the entrypoint's config and execution gates for those tasks; reuse authorization already given within its scope.

## Checked scope — 2026-09-07

Stable **0.3.20** (2026-05-11); historical local GPU/CLI baseline remains **0.3.20**, 2026-06-06. Documentation verification, historical local testing, and the software installed on a target host are three separate facts. Preserve existing validation dates, captures and source pins; label new unexecuted behavior as documentation-verified. Do not call a release current based only on search snippets or a moving documentation URL.

## Tool-specific source map

| Purpose | Primary source | What to inspect |
|---|---|---|
| Releases | [Releases](https://github.com/tbepler/topaz/releases) | Open actual release; API: `https://api.github.com/repos/tbepler/topaz/releases`. |
| Pinned tutorials | [Pinned tutorials](https://github.com/tbepler/topaz/tree/v0.3.20/tutorial) | Four notebooks: quick start, walkthrough, cross-validation, denoising; inspect cells without executing. |
| Tagged CLI/source | [Tagged CLI/source](https://github.com/tbepler/topaz/tree/v0.3.20/topaz) | Inspect command parsers, device dispatch, loaders and denoise API before updating flags. |
| README | [README](https://github.com/tbepler/topaz/blob/v0.3.20/README.md) | Overview, tutorial links, distribution and usage; validate exact flags against source/help. |
| Documentation age check | [Documentation age check](https://topaz-em.readthedocs.io/en/latest/tutorial.html) | Currently 0.2.5 and a coming-soon placeholder; latest URL does not imply latest software documentation. |

## Refresh procedure

1. Locate this skill from its loaded `SKILL.md`. Compare the repository and authorized installed copy before editing. Keep a diff/backup and evidence outside the installable skill; preserve private `site_config` files, probe reports, queue settings and populated lessons.
2. Open release index and actual relevant release bodies. Record release date, stable/prerelease status, source URL, retrieval date/status and resolved version or SHA. Read selected tutorial pages as well as release notes; compare page content, not just titles or hashes. If a page fails, try an official alternate and record the gap without advancing that page's freshness claim.
3. Edit `01_source_map.md` for release/source age, `03_cli_reference.md` for CLI/defaults, `05_core_workflows.md` for cross-validation/denoising, `04_data_model_and_formats.md` for coordinate scaling, and `02_config_session_and_environment.md` for device support. Check `train` preloading and Python `denoise_stream` return values when integrating wrappers. Notebook cells can preserve obsolete commands or unsafe variable names even at the current tag; adapt them rather than copying blindly.
4. Store snapshots and a compact manifest (URL, retrieval date/status, SHA-256, claim → destination reference, gaps) in the user's maintenance workspace outside this package. Historical archive paths in references are provenance, not required runtime files. Keep full manuals, notebooks with embedded images, datasets, logs and site reports out of the portable skill.
5. Keep `SKILL.md` a short router for maintenance; load only affected references. Resolve contradictions in owning references and linked decision trees. Keep current-release source assertions separate from historical live-help/smoke assertions. Updating runtime pins/probe logic requires targeted validation; documentation maintenance alone cannot promote a new tested baseline.
6. Run the available skill-creator `quick_validate.py`; check changed local links and referenced script paths, YAML metadata, and diff for private paths/settings. If scripts change, exercise meaningful offline behavior without invoking real tools or scheduler submissions. Rehearse a self-update request (no probe), a release-specific question (version-aware source), and a real run (config/execution gate). Synchronize only authorized copies after validation, preserving local data.
7. Report checked versions/dates, owning-reference changes, validation results, and remaining gaps. Keep evidence of baseline validation failures. Publishing or live upgrading needs its own task scope.

## Current gaps

Release metadata, README, tutorial directory, cross-validation/denoising notebooks and training parser checked. No new compute tests. ReadTheDocs is stale; primary notebooks are the usable tutorial route, but their historic cells still require command reconciliation.

Example: “Refresh this Topaz skill against official releases and tutorials, preserving its locally validated baseline and keeping snapshots outside the package.”
