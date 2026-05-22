---
name: annika-log
description: Enforce a uniform, fully-retrievable folder layout for each structural-biology project so every job is self-contained, auditable, and feeds reproducibility / failure-recovery / lesson-distill claims mechanically. Use when the user says "new job", "log this run", "init project", "create project folder", "audit project", "close job", "export failures", "export lessons", or when starting any tool run (ChimeraX / Phenix / Refmac / Coot / ISOLDE / Merizo / etc.) that produces files worth citing later. Also use when retrofitting an existing run into the standard layout, or when preparing reviewer-facing failure/lesson exports.
---

# annika-log

Project / job folder discipline for Annika. Folder spec first, thin CLI second.

Framing: **user-guided auditable orchestration**, not autonomous recovery. Every human steer that changes the path is logged.

## When to use

- Starting any tool run that should be cite-able later → `annika_log.py new`.
- New project domain → `annika_log.py init`.
- Wrapping up a run (success or failure) → `annika_log.py close`.
- Reviewer-facing exports for the cryoagent paper → `export-failures`, `export-lessons`.
- Sanity check a project before claiming completeness → `audit`.

If a tool is run and **no `Job_NNN_*/` exists**, the run is undocumented. Redo it or reconstruct the folder before citing the result.

## Core layout

```
$ANNIKA_PROJECTS_ROOT/<PROJECT>/
├── INDEX.md                  # registry of evidence units (machine-readable table)
├── PROJECT_NOTES.md          # free-form decisions / context
├── shared_inputs/
│   ├── INPUTS.md             # sha256 + source + retrieval manifest
│   └── ...
└── Job_NNN_<short_name>/
    ├── JOB_LOG.md            # canonical job log
    ├── log/
    │   ├── description.md    # user/agent comms verbatim + objective
    │   ├── parameters.json   # tool params, versions, env, seeds
    │   ├── stdout.log
    │   ├── stderr.log
    │   ├── errors.md         # CANONICAL Supp. Table 3 schema (table only)
    │   ├── errors_detail.md  # optional rich debugging narrative
    │   └── decisions.md      # human approvals / steers
    ├── output/               # files produced BY tools
    └── scripts/              # scripts/configs Annika wrote to drive tools
```

`NNN` is zero-padded, scoped per project. No global IDs unless cross-project citation is real (then use `PROJECT:Job_NNN`).

## Workflow

1. **Init** (once per project): `python scripts/annika_log.py init <project>` — creates `INDEX.md`, `PROJECT_NOTES.md`, `shared_inputs/INPUTS.md`.
2. **New job** (every run): `python scripts/annika_log.py new <project> <short_name>` — allocates next `Job_NNN_*`, scaffolds `{log,output,scripts}` + JOB_LOG template, appends INDEX row as `running`.
3. **During the run**:
   - Save every script you write to drive tools under `scripts/`.
   - Tee tool output to `log/stdout.log` / `log/stderr.log`.
   - Append errors to `log/errors.md` **at the moment they happen**, in the canonical 6-column schema (see `references/schemas.md`).
   - Log human decisions/approvals to `log/decisions.md` and reference them from JOB_LOG §4.
   - Hash every input added to `shared_inputs/` and append a row to `shared_inputs/INPUTS.md`.
4. **Close**: `python scripts/annika_log.py close <job_path> <status> [--reason ...] [--superseded-by ...]` — stamps `Closed:`, validates mandatory fields, updates INDEX.md.
5. **Audit**: `python scripts/annika_log.py audit <project>` — flags missing `description.md`, `parameters.json`, `errors.md`, `## Result`, `## Lessons`.
6. **Export** for paper: `export-failures` (concat `errors.md` across jobs) / `export-lessons` (concat `## Lessons` blocks, filterable by `tool_tag` / `failure_class`).

## Operating rules

1. **No job without a folder.** Undocumented runs cannot be cited.
2. **Errors logged live**, not reconstructed.
3. **Human decisions are first-class** (`decisions.md` + JOB_LOG §4). This keeps the "user-guided" framing honest.
4. **Excluded ≠ deleted.** Excluded jobs stay in INDEX with a reason.
5. **Provenance required.** A file under `shared_inputs/` cannot be cited as input unless it has a row in `INPUTS.md`.
6. **Lessons mandatory at close.** Closed job with no lessons must explicitly write `## Lessons\nNone.` — silence is forbidden.

## Schemas

For `INDEX.md` columns, `JOB_LOG.md` sections, the canonical `errors.md` Supp. Table 3 schema, the hybrid `## Lessons` block (controlled vocab + free form), and `INPUTS.md` manifest, read **`references/schemas.md`**.

## Cryoagent paper traceability

For the mapping from manuscript claim → mechanical artefact under this skill (Supp. Table 3, `dream_deep`, reproducibility, etc.), read **`references/cryoagent-mapping.md`**. Consult before any reviewer-facing export.

## Controlled vocab (lessons)

Use these tags so `dream_deep` / `skill-merge` can group cleanly. Full enum in `references/schemas.md`:

- `tool_tag`: refmac, coot, phenix, gemmi, chimerax, isolde, python, llm, browser, file_io, database, other
- `failure_class`: input_missing, format_mismatch, parameter_error, tool_crash, semantic_misread, validation_failure, environment_issue, provenance_gap
- `recovery_pattern`: retry_with_changed_params, fallback_tool, manual_inspection, schema_fix, input_regeneration, human_approval, skill_update

## Notes

- Keep design-trail notes in the project root or a private project notebook; do not publish private review transcripts.
- Skill output for `export-lessons` is the canonical input for `skill-merge`.
- Add to AGENTS.md routing table once stable.
