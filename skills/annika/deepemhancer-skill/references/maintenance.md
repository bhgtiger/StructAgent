# Update the DeepEMhancer skill

Use for an authorized documentation/source/tutorial refresh. This lane edits the knowledge bundle and skips runtime environment probing. It does not authorize a software installation/upgrade, dataset/model download, processing job, live-project mutation, or publication. Resume the entrypoint's config and execution gates for those tasks; reuse authorization already given within its scope.

## Checked scope — 2026-09-07

Stable GitHub release **0.17** (2025-06-26). Master resolves to historical source commit **961f028ca609017990de4473ab368cf1787e8282**. Historical source/runtime/distribution versions remain separate. Documentation verification, historical local testing, and the software installed on a target host are three separate facts. Preserve existing validation dates, captures and source pins; label new unexecuted behavior as documentation-verified. Do not call a release current based only on search snippets or a moving documentation URL.

## Tool-specific source map

| Purpose | Primary source | What to inspect |
|---|---|---|
| Release status | [Release status](https://github.com/rsanchezgarc/deepEMhancer/releases) | Read actual release; API: `https://api.github.com/repos/rsanchezgarc/deepEMhancer/releases`. |
| Current source identity | [Current source identity](https://api.github.com/repos/rsanchezgarc/deepEMhancer/commits/master) | Record SHA; a matching SHA proves repository identity, not runtime or model availability. |
| Usage/tutorial/installation | [Usage/tutorial/installation](https://github.com/rsanchezgarc/deepEMhancer/blob/961f028ca609017990de4473ab368cf1787e8282/README.md) | Read input, normalization, model-choice, batch and troubleshooting sections. README flag examples can be stale. |
| CLI parser | [CLI parser](https://github.com/rsanchezgarc/deepEMhancer/blob/961f028ca609017990de4473ab368cf1787e8282/deepEMhancer/applyProcessVol/cmdParserOptionsDeepEMHancer.py) | Resolve exact option spellings; inspect runtime assertions too. |
| Model distribution | [Model distribution](https://zenodo.org/records/7432763) | Recheck metadata/checksums when needed; do not download weights during docs maintenance. |

## Refresh procedure

1. Locate this skill from its loaded `SKILL.md`. Compare the repository and authorized installed copy before editing. Keep a diff/backup and evidence outside the installable skill; preserve private `site_config` files, probe reports, queue settings and populated lessons.
2. Open release index and actual relevant release bodies. Record release date, stable/prerelease status, source URL, retrieval date/status and resolved version or SHA. Read selected tutorial pages as well as release notes; compare page content, not just titles or hashes. If a page fails, try an official alternate and record the gap without advancing that page's freshness claim.
3. Edit `01_source_map.md` for conda/source/TensorFlow version divergence, `03_cli_reference.md` for real vs phantom flags, `04_inputs_outputs_models.md` for normalization/input decisions, and propagate these to `05_workflow_templates.md`, `06_troubleshooting_and_decision_trees.md`, and `08_validation_and_limits.md`. Keep `09_installation_and_runtime.md` tied to its tested recipe; a README refresh cannot validate new CUDA libraries. Check the special masked-input mode without weakening the prohibition on already sharpened/enhanced input.
4. Store snapshots and a compact manifest (URL, retrieval date/status, SHA-256, claim → destination reference, gaps) in the user's maintenance workspace outside this package. Historical archive paths in references are provenance, not required runtime files. Keep full manuals, notebooks with embedded images, datasets, logs and site reports out of the portable skill.
5. Keep `SKILL.md` a short router for maintenance; load only affected references. Resolve contradictions in owning references and linked decision trees. Keep current-release source assertions separate from historical live-help/smoke assertions. Updating runtime pins/probe logic requires targeted validation; documentation maintenance alone cannot promote a new tested baseline.
6. Run the available skill-creator `quick_validate.py`; check changed local links and referenced script paths, YAML metadata, and diff for private paths/settings. If scripts change, exercise meaningful offline behavior without invoking real tools or scheduler submissions. Rehearse a self-update request (no probe), a release-specific question (version-aware source), and a real run (config/execution gate). Synchronize only authorized copies after validation, preserving local data.
7. Report checked versions/dates, owning-reference changes, validation results, and remaining gaps. Keep evidence of baseline validation failures. Publishing or live upgrading needs its own task scope.

## Current gaps

Checked release, master SHA, README and pinned parser. Model record/download availability and model bytes were not rechecked; an older source map records Zenodo fetch failure. Installed version, TensorFlow/GPU and new maps were not probed or run.

Example: “Refresh this DeepEMhancer skill against official releases and tutorials, preserving its locally validated baseline and keeping snapshots outside the package.”
