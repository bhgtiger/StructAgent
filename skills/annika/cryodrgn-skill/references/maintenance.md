# Update the cryoDRGN skill

Use for an authorized documentation/source/tutorial refresh. This lane edits the knowledge bundle and skips runtime environment probing. It does not authorize a software installation/upgrade, dataset/model download, processing job, live-project mutation, or publication. Resume the entrypoint's config and execution gates for those tasks; reuse authorization already given within its scope.

## Checked scope — 2026-09-07

Stable **4.3.1** (2026-08-04), preceded by stable 4.3.0 (2026-06-12). Local tested baseline remains **4.2.1**, 2026-06-06. Documentation verification, historical local testing, and the software installed on a target host are three separate facts. Preserve existing validation dates, captures and source pins; label new unexecuted behavior as documentation-verified. Do not call a release current based only on search snippets or a moving documentation URL.

## Tool-specific source map

| Purpose | Primary source | What to inspect |
|---|---|---|
| Release/status | [Release/status](https://github.com/ml-struct-bio/cryodrgn/releases) | Open actual release and confirm stable/prerelease date; API: `https://api.github.com/repos/ml-struct-bio/cryodrgn/releases`. |
| Guide discovery | [Guide discovery](https://ez-lab.gitbook.io/cryodrgn/llms.txt) | Select relevant pages; append `.md` to retrieve GitBook pages. Do not load the full corpus. |
| Pose-conditioned tutorial | [Pose-conditioned tutorial](https://ez-lab.gitbook.io/cryodrgn/cryodrgn-empiar-10076-tutorial) | Reconcile historical syntax, sign, box/pixel scale, and 1-based epoch labels. |
| Ab initio tutorial | [Ab initio tutorial](https://ez-lab.gitbook.io/cryodrgn/cryodrgn-ai-ab-initio-reconstruction/cryodrgn-ai-ab-initio-empiar-10076-tutorial) | Keep AI pose-search and fixed-pose training routes distinct. |
| Packaging/CLI | [Packaging/CLI](https://github.com/ml-struct-bio/cryodrgn/tree/4.3.1) | Inspect `pyproject.toml`, command modules, parsers and tests at a release tag. |
| Interactive command builder | [Interactive command builder](https://ml-struct-bio.github.io/cryodrgn/) | Builder moves with releases; generated flags require target-version reconciliation. |

## Refresh procedure

1. Locate this skill from its loaded `SKILL.md`. Compare the repository and authorized installed copy before editing. Keep a diff/backup and evidence outside the installable skill; preserve private `site_config` files, probe reports, queue settings and populated lessons.
2. Open release index and actual relevant release bodies. Record release date, stable/prerelease status, source URL, retrieval date/status and resolved version or SHA. Read selected tutorial pages as well as release notes; compare page content, not just titles or hashes. If a page fails, try an official alternate and record the gap without advancing that page's freshness claim.
3. Edit `01_source_map.md` for release/dependency drift, `03_cli_reference.md` for command inventories, `05_core_workflows.md` for tutorials/dashboard, and `06_interoperability.md` for parser/CTF/indexing changes. The current refresh adds 4.3 dashboard and WarpTools guidance but retains 4.2.1 runnable templates. Do not mark new 4.3 commands `VALIDATED: 4.2.1`. Upgrade probes or pins only with separate source review and runtime validation.
4. Store snapshots and a compact manifest (URL, retrieval date/status, SHA-256, claim → destination reference, gaps) in the user's maintenance workspace outside this package. Historical archive paths in references are provenance, not required runtime files. Keep full manuals, notebooks with embedded images, datasets, logs and site reports out of the portable skill.
5. Keep `SKILL.md` a short router for maintenance; load only affected references. Resolve contradictions in owning references and linked decision trees. Keep current-release source assertions separate from historical live-help/smoke assertions. Updating runtime pins/probe logic requires targeted validation; documentation maintenance alone cannot promote a new tested baseline.
6. Run the available skill-creator `quick_validate.py`; check changed local links and referenced script paths, YAML metadata, and diff for private paths/settings. If scripts change, exercise meaningful offline behavior without invoking real tools or scheduler submissions. Rehearse a self-update request (no probe), a release-specific question (version-aware source), and a real run (config/execution gate). Synchronize only authorized copies after validation, preserving local data.
7. Report checked versions/dates, owning-reference changes, validation results, and remaining gaps. Keep evidence of baseline validation failures. Publishing or live upgrading needs its own task scope.

## Current gaps

The guessed `www.cryodrgn.com` endpoint failed DNS; the canonical GitBook index/tutorials were successfully retrieved. The GitBook install page still combines older testing ranges and examples with newer releases; use tagged packaging for dependency facts. No new runtime validation or installed-host inspection.

Example: “Refresh this cryoDRGN skill against official releases and tutorials, preserving its locally validated baseline and keeping snapshots outside the package.”
