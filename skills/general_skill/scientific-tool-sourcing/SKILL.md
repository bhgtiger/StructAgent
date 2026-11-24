---
name: scientific-tool-sourcing
description: >-
  Collect, pin and verify all the source material needed to build a skill for a
  scientific application later: a software package or CLI, GUI tool with scripting,
  database/API, file format, analysis pipeline, instrument or protocol. Use whenever
  the user wants to gather, collect or prepare sources, material, evidence or
  references for a future skill ("collect material for a ModelAngelo skill", "gather
  sources before we build a skill for X", "what do we need before making a skill
  for this tool"), including a source plan only.
  Produces a project folder: source plan, gathering briefs for subagents or Codex,
  raw evidence pinned to commits with file:line or URL+date citations, citation and
  manifest checks, a cross-check/gap report, a live-verification checklist, and a
  HANDOFF.md for the skill builder. Does not write the target skill, install the
  tool, download weights or databases, or run its jobs. Not for using an existing
  tool skill, digesting a single paper, or general literature search.
---

# Scientific Tool Sourcing

This is the step **before** building a scientific-tool skill. It produces an **evidence
pack**: every fact a skill-writer will need, pinned to a version and cited to a file line
or a dated URL, plus the gaps, contradictions and checks that tell them what not to
trust. Building the skill itself happens afterwards (with `skill-creator` or the house
layout described in the hand-off).

Earlier projects show why this matters. Audits against the pinned source found errors
in every one of them: stale README defaults, tutorial aliases taken for real commands,
invented flags, HTML saved as PDF. See `examples/past_runs.md`.

## Boundaries (defaults; the user may lift any of them explicitly)
- **Collect, don't build.** Do not write the target skill's SKILL.md or runtime
  references. The hand-off only recommends a layout.
- **The gathering host is not the target runtime.** Do not install the target tool or its
  dependencies, run it, or download anything > 50 MB (weights, databases, images, datasets).
- **Live capture** (`--help`, `--version`, read-only probes) only on a host where the tool
  is already installed, and only with the user's OK. A smoke run needs approval of the
  exact command.
- **Public sources only.** Respect ToS and rate limits. Never send the user's data,
  credentials or unpublished material to any service. No paywalled content.
- Write only inside the project folder.

## Workflow

### 0. Set up
1. Project folder: `<projects dir>/<tool>_skill/`. Ask if the location is unclear. If
   the project already uses the annika-log jobs layout (`jobs/INDEX.md`), log this
   work as a gathering job and keep the project's existing evidence folder. The
   scripts take `--sources` and `--prefix` for that layout.
2. Default layout:
   ```text
   plan/source_plan.md      tasks/_common_rules.md, task_<ID>_*.md
   sources/{source,web,papers,community,live,crosscheck,<wrapper>}/   (+ MANIFEST.tsv)
   logs/                    tmp/                  HANDOFF.md   README.md
   ```
   Add git clones and `tmp/` to `.gitignore` if the project is a git repo.
3. `bash scripts/probe_gathering_host.sh <target-cli-names> > logs/gathering_host.txt`
   records which tools exist on this host (git, gh auth, pdftotext, yt-dlp, codex…).
4. Check what already exists: an installed skill for this tool, an earlier project
   folder, and papers in the local databases (`database` skill). Reuse; don't re-collect.

### 1. Source plan
Fill `references/source_plan_template.md` into `plan/source_plan.md`. Use
`references/source_classes.md` to set P0/P1/P2/Out per class. Settle these first: the
**canonical upstream** (not a fork or mirror) and the **version to pin** (latest
release; also record the latest pre-release and the default-branch HEAD).

**Checkpoint:** show the user a short summary: target and pin, P0 classes, tasks,
executor, rough time and cost, domains to be contacted. Wait for an OK before
launching gatherers, unless the user already said to go ahead. If they asked for a
plan only, stop here.

### 2. Gather
Write `tasks/_common_rules.md` and one brief per task from
`references/gathering_tasks.md`. Default tasks: **A** pinned source · **B**
wrappers/forks/plugins (if any) · **C** docs, terms, papers, community · **D** live
capture (optional) · **E** cross-check and gap report (last). Executors: inline for
small targets, Claude Code subagents (default), or Codex via
`scripts/run_codex_task.sh`. Run at most 2–3 concurrently. When gathering inline, keep
`logs/fetch_commands.md` so the collection can be reproduced.

### 3. Verify
Follow `references/verification.md`:
- `scripts/check_citations.py` must report 0 errors;
- `scripts/build_manifest.py` (SHA-256 for every file, HEAD for every clone; fake PDFs and oversized files flagged);
- check the run logs;
- eyeball the cited-line sample;
- spot-check 5–10 high-risk claims yourself against primary evidence;
- optionally, get an independent review.

Record the results in `sources/crosscheck/verification.md`. Re-task or fix failures;
anything unresolved becomes a gap.

### 4. Hand off
Write `HANDOFF.md` from `references/handoff_template.md`, citing raw evidence only. Add a
status line to the project README. Report to the user:
- what the pack contains and its pins;
- the top P0 gaps and contradictions;
- the decisions they need to make;
- the suggested next step (build the skill, or run the live-verification checklist on the target host).

## Trust ladder and evidence labels
When sources conflict, the higher rank wins:
1. live behavior;
2. pinned source/schema;
3. docs source;
4. rendered docs;
5. peer-reviewed papers;
6. first-party talks;
7. community (issues, forums);
8. LLM summaries, NotebookLM included (navigation only, never evidence).

Papers and videos justify *why/when*. They never settle flags, defaults, field names or
support status. Inventories label facts `LIVE` / `SOURCE` / `DOCS` / `PAPER` / `TALK` /
`COMMUNITY` / `UNVERIFIED`. The built skill's `01_source_map.md` maps these to Tier 1
VALIDATED (live) and Tier 2 SOURCED.

## Source classes
Details, artifact names and known pitfalls are in `references/source_classes.md`:
1. identity and canonical upstream
2. pinned source/schema
3. docs
4. live behavior
5. data formats
6. models/weights/databases
7. fixtures
8. environment (gathering host vs target runtime)
9. papers
10. talks/videos
11. community
12. license, terms, privacy and data egress
13. wrappers/forks/plugins/interop

It also covers targets with no public source code.

## Common mistakes (each one happened in an earlier project)
- Pinning a fork or the tag *object*. Use `git rev-parse <tag>^{commit}` on the canonical repo.
- Trusting README or rendered help over the parser, or taking tutorial aliases for real commands.
- Saving a publisher or PMC challenge page as `.pdf`, or counting a DOI as a paper read.
- Leaving live captures on the server or in scratch. Writing hashes to stdout instead of
  `MANIFEST.tsv`. Recording host-absolute paths.
- Duplicate clones and big test data in the raw store.
- Writing hand-off facts from distilled notes instead of raw evidence.
- Skipping weights terms or default data egress (e.g. sequences sent to a public MSA server).
- Accepting a gatherer's exit code or summary without the checks in step 3.
- Treating video or NotebookLM summaries as evidence.

## Reference routing
| Need | Read |
|---|---|
| Step 1 plan | `references/source_plan_template.md`, `references/source_classes.md` |
| Step 2 rules, briefs, executors | `references/gathering_tasks.md` |
| Step 3 checks | `references/verification.md` |
| Step 4 hand-off | `references/handoff_template.md` |
| Worked example and lessons | `examples/past_runs.md` (OpenFold 3 run: `opnefold_skill/`) |

| Script (stdlib, read-only unless noted) | Purpose |
|---|---|
| `scripts/probe_gathering_host.sh [cli…]` | tools, gh auth and network on the gathering host |
| `scripts/run_codex_task.sh <root> <ID> <brief>` | one Codex gatherer with full logs and failure scan |
| `scripts/check_citations.py --root <p>` | `path:line` and verbatim checks, URL dates, gaps sections, random sample |
| `scripts/build_manifest.py --root <p>` | writes `sources/MANIFEST.tsv`; flags fake PDFs and files > 50 MB |
