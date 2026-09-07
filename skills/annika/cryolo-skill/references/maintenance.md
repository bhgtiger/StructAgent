# Update the crYOLO skill

Use for an authorized documentation/source/tutorial refresh. This lane edits the knowledge bundle and skips runtime environment probing. It does not authorize a software installation/upgrade, dataset/model download, processing job, live-project mutation, or publication. Resume the entrypoint's config and execution gates for those tasks; reuse authorization already given within its scope.

## Checked scope — 2026-09-07

**1.9.9** is the highest version in the stable changelog, matching the local **1.9.9** test on 2026-06-06. The changelog supplies no release date. Documentation verification, historical local testing, and the software installed on a target host are three separate facts. Preserve existing validation dates, captures and source pins; label new unexecuted behavior as documentation-verified. Do not call a release current based only on search snippets or a moving documentation URL.

## Tool-specific source map

| Purpose | Primary source | What to inspect |
|---|---|---|
| Release changes | [Release changes](https://cryolo.readthedocs.io/en/stable/changes.html) | Read crYOLO and BoxManager sections separately; component versions differ. |
| Installation/model links | [Installation/model links](https://cryolo.readthedocs.io/en/stable/installation.html) | Resolve runtime requirements and model families from this page; downloading is a separate action. |
| Six workflow tutorials | [Six workflow tutorials](https://cryolo.readthedocs.io/en/stable/tutorials/tutorial_overview.html) | General SPA, dataset training, 2D filaments, fine-tuning, tomo particles, tomo filaments. |
| Source pin | [Source pin](https://github.com/MPI-Dortmund/cryolo) | Resolve a matching tag before replacing historical parser/format claims. |

## Refresh procedure

1. Locate this skill from its loaded `SKILL.md`. Compare the repository and authorized installed copy before editing. Keep a diff/backup and evidence outside the installable skill; preserve private `site_config` files, probe reports, queue settings and populated lessons.
2. Open release index and actual relevant release bodies. Record release date, stable/prerelease status, source URL, retrieval date/status and resolved version or SHA. Read selected tutorial pages as well as release notes; compare page content, not just titles or hashes. If a page fails, try an official alternate and record the gap without advancing that page's freshness claim.
3. Edit `01_source_map.md` for version evidence, `02_config_session_and_environment.md` for supported runtime facts, `05_core_workflows.md` for filter/model matching and tutorial choice, `04_data_model_and_formats.md`/`06_interoperability.md` for CBOX/STAR/BOX conversion, and `09_troubleshooting.md` for tracing failures. Keep the native CLI reference separate from the CryoSPARC-specific `11_cryosparc_picking_workflow.md` route; propagate coordinate-scale corrections to both.
4. Store snapshots and a compact manifest (URL, retrieval date/status, SHA-256, claim → destination reference, gaps) in the user's maintenance workspace outside this package. Historical archive paths in references are provenance, not required runtime files. Keep full manuals, notebooks with embedded images, datasets, logs and site reports out of the portable skill.
5. Keep `SKILL.md` a short router for maintenance; load only affected references. Resolve contradictions in owning references and linked decision trees. Keep current-release source assertions separate from historical live-help/smoke assertions. Updating runtime pins/probe logic requires targeted validation; documentation maintenance alone cannot promote a new tested baseline.
6. Run the available skill-creator `quick_validate.py`; check changed local links and referenced script paths, YAML metadata, and diff for private paths/settings. If scripts change, exercise meaningful offline behavior without invoking real tools or scheduler submissions. Rehearse a self-update request (no probe), a release-specific question (version-aware source), and a real run (config/execution gate). Synchronize only authorized copies after validation, preserving local data.
7. Report checked versions/dates, owning-reference changes, validation results, and remaining gaps. Keep evidence of baseline validation failures. Publishing or live upgrading needs its own task scope.

## Current gaps

Current stable changelog, installation and six-workflow tutorial page checked; no release date established, no new GPU tests, and no fresh source checkout/model download. This is selected-source coverage rather than an audit of every tutorial screenshot or external link.

Example: “Refresh this crYOLO skill against official releases and tutorials, preserving its locally validated baseline and keeping snapshots outside the package.”
