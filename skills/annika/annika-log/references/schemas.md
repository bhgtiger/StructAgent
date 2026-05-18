# annika-log schemas

Canonical schemas for every artefact this skill produces. Stable — manuscript exports depend on them.

## Table of contents
1. INDEX.md
2. JOB_LOG.md
3. log/errors.md (Supp. Table 3 schema)
4. log/decisions.md
5. shared_inputs/INPUTS.md
6. ## Lessons block (hybrid controlled + free-form)

---

## 1. INDEX.md

Machine-readable table at top, free notes below. Mandatory columns:

```md
| job_id | short_name | status | created | completed | primary_output | error_log | excluded_reason | superseded_by |
```

Status enum:
- `draft` — created, not started
- `running`
- `complete` — successful, evidence-ready
- `failed` — terminated with no usable output
- `excluded` — completed but not used (`excluded_reason` mandatory)
- `superseded` — replaced (`superseded_by` mandatory; reason in JOB_LOG)

Empty cells use `-`, never blanks.

---

## 2. JOB_LOG.md

```md
# Job NNN — <short name>

- Status: draft | running | complete | failed | excluded | superseded
- Created: <ISO 8601>
- Closed:  <ISO 8601>
- Tools:   chimerax 1.x, phenix 1.21, refmac 5.8.x, ...
- Inputs:  paths (with provenance pointer to shared_inputs/INPUTS.md)
- Outputs: paths under output/
- Depends on:    Job_NNN, Job_NNN
- Supersedes:    Job_NNN (and reason)
- Superseded by: Job_NNN (and reason)

## 1. Description
User request verbatim, agent restatement, objective, success criteria.

## 2. Parameters
Pointer to `log/parameters.json` + key choices in prose (why these values).

## 3. Steps
Numbered actions, each with timestamp + script path under `scripts/`.

## 4. Human decisions / approval gates
Pointer to `log/decisions.md`. Every human steer that changed the path
must appear here. If none, write "None.".

## 5. Errors & Recovery
Pointer to `log/errors.md` (canonical) + `errors_detail.md` (if present).

## 6. Result
Metrics (CC, Rama-Z, R-factors, etc.), pass/fail vs success criteria,
next-step recommendation.

## 7. Lessons
Hybrid controlled-tag + free-form (see §6). If none: "None.".
```

---

## 3. log/errors.md — canonical Supp. Table 3 schema

Metadata block (above the table):

```md
- job_id: 8B0X:Job_007
- timestamp_iso: 2026-04-27T15:47:00+02:00
- tool: refmac5
- tool_version: 5.8.0419
- linked_log_files: stdout.log, stderr.log, errors_detail.md
```

Then the table (exact column order, no extras):

```md
| ID | Stage | Failure mode | Diagnosis | Fix | Outcome |
|----|-------|--------------|-----------|-----|---------|
| E3-4 | Refmac5 EXTE ANGL | long single-line keyword exceeded parser length | reformatted across continuation lines | applied | exposed E3-5 |
```

`ID` follows manuscript convention (`Ex-y`) when paper-facing; otherwise `J007-1`, `J007-2`, ...

Rich debugging narrative (stack traces, hypothesis chains) → `errors_detail.md`. Keeps the canonical table clean and concatenable.

---

## 4. log/decisions.md

Append-only log of human approvals / steers that changed the path.

```md
- ts: 2026-04-27T16:02:00+02:00
  decision_id: J007-D1
  prompt_to_user: "Drop chain 3_1 or rename it before refmac?"
  user_decision: "rename"
  rationale: "preserve evidence; renaming is reversible"
  affected_steps: [step 4, step 5]
```

If none for the job, file may be empty but JOB_LOG §4 must say "None.".

---

## 5. shared_inputs/INPUTS.md

Per-file manifest. Required before a file can be cited as an input.

```md
| file | sha256 | source | retrieved | derived_from | notes |
|------|--------|--------|-----------|--------------|-------|
| 8b0x_emd.map | ab12...cd | EMDB-XXXXX | 2026-04-20 | -            | -     |
| ligand.cif   | 9f00...11 | AceDRG     | 2026-04-22 | smiles input | -     |
```

---

## 6. ## Lessons block (hybrid)

One YAML-ish block per lesson. Controlled vocab keeps `dream_deep` grouping clean; free-form `lesson` + `evidence` keep meaning.

```yaml
- lesson_id: J007-L1
  tool_tag: refmac
  failure_class: format_mismatch
  recovery_pattern: schema_fix
  reusable_skill_target: skills/ccp4/lessons.md
  lesson: >
    Servalcat-renamed nonpoly chains with underscore suffixes (3_p, 3_1)
    are not parseable by Refmac5 EXTE ANGL even via @keyword_file; emit
    1-3 distance restraints via law-of-cosines instead.
  evidence:
    - log/stderr.log:Number of defined atoms = 2
    - errors.md:E3-7
    - output/refmac_run2_angles.log
```

Controlled vocab (closed enums):

- `tool_tag`: `refmac` | `coot` | `phenix` | `gemmi` | `chimerax` | `isolde` | `python` | `llm` | `browser` | `file_io` | `database` | `other`
- `failure_class`: `input_missing` | `format_mismatch` | `parameter_error` | `tool_crash` | `semantic_misread` | `validation_failure` | `environment_issue` | `provenance_gap`
- `recovery_pattern`: `retry_with_changed_params` | `fallback_tool` | `manual_inspection` | `schema_fix` | `input_regeneration` | `human_approval` | `skill_update`

If a lesson does not fit, propose a vocab extension in PR-style review with Maria; do not silently invent tags.
