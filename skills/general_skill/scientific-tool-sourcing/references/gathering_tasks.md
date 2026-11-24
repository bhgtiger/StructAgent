# Gathering tasks: shared rules, brief templates, executors

Copy the rules block into `<project>/tasks/_common_rules.md` (fill `<TARGET>`), then write
one brief per task as `tasks/task_<ID>_<slug>.md`. Every gatherer's prompt is
`_common_rules.md` + its brief, verbatim. Keep both files: they make the gathering reproducible.

## 1. `_common_rules.md` template

````markdown
# Common rules for every gathering task (read first, obey all)

You are a SOURCE GATHERER for a future `<TARGET>` skill. The project root is your working
directory. Everything you write is evidence that a later skill-writer will cite.
Precision beats volume.

Hard rules
1. Do not install <TARGET> or any dependency (no pip/conda/uv/pixi/brew/docker/apptainer
   installs or pulls). This host is NOT the target runtime unless your brief says so.
2. Do not download model weights, databases, datasets, container images, or any single
   file > 50 MB. Clone repos with `git clone --filter=blob:none`. Public web pages and
   PDFs ≤ 50 MB are fine.
3. Do not run <TARGET>, its scripts, or `import` its package. Allowed: git, curl, gh api,
   grep, find, jq, pdftotext, `python3 -c` for parsing text.
4. Write ONLY inside `sources/<your-area>/` (listed in your brief) and `tmp/`. Never edit
   `plan/`, `tasks/`, `logs/`, `HANDOFF.md`, or another task's folder.
5. Cite every factual claim:
   - local file: `sources/<path>:<line>` or `sources/<path>:<start>-<end>` — path relative
     to the project root, no `./`, no spaces;
   - web: `<URL> (fetched YYYY-MM-DD)`.
   Quote flags, defaults, field names, help strings and license clauses verbatim; never
   paraphrase CLI syntax. For multi-line quotes use exactly:

       Verbatim `sources/<path>:<start>-<end>`:
       ```<lang>
       <the exact lines>
       ```
6. If you could not verify something, write `UNVERIFIED` next to it. Every inventory file
   ends with a `## Gaps / unknowns` section. Never guess a flag, path, version, number,
   default or license term.
7. Repos: record URL, clone date (UTC), HEAD SHA, checked-out tag/branch, the tags that
   matter (with dates), license file + SPDX id. Check out the pinned tag named in the
   brief; if it does not exist, say so and stop that step.
8. Web pages: save raw HTML to `sources/web/raw/<slug>.html` and a text copy to
   `sources/web/<slug>.md` whose first lines are `URL:`, `Fetch date UTC:`,
   `HTTP status:`, and the version shown on the page. Prefer versioned URLs over `latest`.
9. PDFs: save as `sources/papers/<year>_<firstauthor>_<short>.pdf`; record URL + fetch date,
   bytes, pages, SHA-256; put a text extract next to it (`pdftotext -layout`).
10. Respect ToS, robots and rate limits. For GitHub use `gh api` when authenticated; stop
    and report if rate-limited. Never fetch paywalled content, and never send credentials,
    private data or the user's files to any external service.
11. Keep inventories skimmable: headings, tables, short bullets. Large raw dumps (trees,
    JSON, issue records) go in `sources/<area>/evidence/` and are cited, not pasted.
12. Finish with a final message containing exactly these sections: `## Files written`,
    `## Key facts` (≤ 15 cited bullets), `## Gaps / blockers`, `## Suggested follow-up tasks`.
    Do not repeat file contents in the final message.
````

## 2. Task brief templates

Each brief: goal (one paragraph), inputs (which other task folders exist; read their
`SNAPSHOT.md` first and link instead of duplicating), numbered steps naming the exact output
files, and "Output: final message per `_common_rules.md` §12". Adapt — drop steps that do
not apply and say so in the brief.

Default order: **A, B, C** may run in parallel (≤ 2–3 at once) → **D** only if a host with
the tool exists and the user approved → **E** last (it reads everything).

### A — Pinned upstream source  → `sources/source/`
1. Clone at the pinned tag/commit; write `SNAPSHOT.md` (rule 7 + declared Python/language
   version, packaging files, docs system and docs URL).
2. `source_inventory.md`: 2-level annotated tree; where entry points, config, data I/O,
   model/algorithm core, docs and tests live.
3. `cli_reference_extracted.md` (or `api_reference_extracted.md`): EVERY user-facing entry
   point (console_scripts, `__main__`, argparse/click/typer/hydra/Snakemake/Nextflow) with
   every option, default and help string verbatim + `file:line`. Config-driven tools:
   document the schema and override syntax instead.
4. `input_output_formats.md`: input fields/types/units/conventions with parser `file:line`;
   output files, names and fields with writer `file:line`; one minimal verbatim example input.
5. `install_environment.md`: install routes, pinned key dependencies, OS/arch/GPU/CUDA/
   driver/MPI requirements, hardware/memory statements — all cited.
6. `models_data_dependencies.md`: weights, reference databases, model zoos: names, URLs,
   sizes, checksums if published, license/gating, env vars/flags that locate them.
   Do NOT download.
7. `external_calls_and_egress.md`: every network call the tool makes by default (servers,
   telemetry, license checks, MSA/structure servers) with `file:line` and the flag that
   disables it.
8. `examples_fixtures.md`: small example inputs/tests usable as fixtures (path, size, what
   they exercise) and the documented test command (do not run it).
9. `changelog_versions.md`: release notes; CLI/config/format changes between the versions
   in scope (`git diff --stat`, notable changes cited).

### B — Wrappers, forks, plugins, integrations (only if they exist)  → `sources/<wrapper>/`
Optimized forks, GUI plugins, pipeline wrappers (e.g. a cryoSPARC external job, a RELION
scheme, a Scipion/CCP-EM plugin, a Galaxy tool, an HPC module), or a vendor kit.
`SNAPSHOT.md`; command surface verbatim; which upstream pins it uses and whether the vendored
code is identical (count files compared); passthrough limits; changed defaults; extra
options; exit codes; environment variables; license.

### C — Docs, terms, papers, community  → `sources/web/`, `sources/papers/`, `sources/community/`
1. Rendered official docs for the pinned version (rule 8); `web/docs_inventory.md` table:
   URL, title, version shown, what it covers, P0/P1/P2, and any conflict with
   `sources/source/` (cite both sides).
2. `web/license_and_terms.md`: software license; weights/model terms; database/API ToS;
   citation requirement; commercial-use and redistribution clauses verbatim; academic vs
   commercial distinctions; gated access (registration, contact-info gates).
3. Papers: primary method, release/update notes, benchmarks, protocols. `papers/paper_inventory.md`:
   citation, DOI/URL, role, SHA-256, and 3–5 bullets of what a skill may cite from it
   (assumptions, validation metrics, limitations, recommended parameters) — never CLI syntax.
4. `community/issues.md`: via `gh api repos/<o>/<r>/issues?state=all&per_page=100`
   (separate issues from PRs), cluster into failure-mode themes (install/CUDA, OOM, input
   format, version mismatch, platform, performance…) with 2–4 links each (number, title,
   date, state). Also Discussions/forum/mailing list if official. Mark the file
   "community evidence — lower trust".
5. `web/hardware_and_platform_claims.md`: every support statement (GPUs, VRAM, CPU-only,
   macOS/Apple Silicon, Windows, containers, HPC) with URL + date.
6. Talks/tutorials (only if P0/P1 in the plan): list official videos/workshops with URL,
   date, version discussed. Transcripts per `source_classes.md` §Video.

### D — Live behavior capture (optional; needs a host with the tool + user approval)  → `sources/live/`
Run only `--version`, `--help`/`-h` for the top level and every subcommand, `python -c
"import pkg; print(pkg.__version__)"`, and read-only environment probes (GPU/driver/CUDA,
scheduler). Save each verbatim to `sources/live/<cmd>[_<sub>].help.txt` with the exact
command line, date, host, exit code. Record `sources/live/_versions.txt`. A smoke run on a
tiny public fixture happens only if the user approved that exact command; record command,
exit code, wall time, and the output file listing. Never touch user data.

### E — Cross-check and gap report  → `sources/crosscheck/`
1. `pin_consistency.md`: the pinned versions agree across source, docs, wrapper and live
   capture (tags exist, commits match, docs version matches).
2. `cli_parity.md` (or `api_parity.md`): one row per option — source / docs / live /
   wrapper — default and evidence for each; flag disagreements.
3. `io_parity.md`: input/output formats agree across sources; one minimal verbatim valid
   example input with citation.
4. `contradictions.md`: docs vs code, README vs parser, paper vs implementation — both sides
   cited, which one wins under the trust ladder, and why.
5. `live_verification_checklist.md`: every claim that only a real install can confirm —
   exact command, expected output, which inventory line it confirms — all marked NOT RUN.
6. `gap_report.md`: P0/P1/P2 gaps across all inventories, and a "must NOT claim" list.

## 3. Executors

Pick one per project (ask the user if they have a preference; default to Claude subagents
inside Claude Code, Codex when the user asks for it or wants to save Claude tokens):

| Executor | When | How |
|---|---|---|
| Inline (you) | small target: one small repo, < ~15 doc pages | follow the briefs yourself; same rules and outputs |
| Claude Code subagents | default in Claude Code | Agent tool, `general-purpose`, background; prompt = full text of `_common_rules.md` + brief (subagents have no other context); ≤ 3 concurrent; E after the others report |
| Codex CLI | user prefers Codex / heavy repos | `scripts/run_codex_task.sh <root> <ID> tasks/task_<ID>_*.md`; ≤ 2 concurrent; 15–25 min per task in the OpenFold run |
| Workflow tool | only if the user explicitly asks for a multi-agent workflow | one agent per brief, then E, then verification |

Claude Code subagents exist only when this skill runs in Claude Code. Under Codex or agy,
gather inline or start Codex workers with `run_codex_task.sh`, and use the host's own
sub-agent features only if it has them.

Whatever the executor: never trust a success message or exit code alone. Read each final
message, then run the checks in `verification.md` before writing the hand-off.
