# Cryoagent paper ↔ annika-log artefact mapping

Manuscript claims must be backed by mechanical artefacts produced by this skill, not by after-the-fact reconstruction.

| Paper claim | Mechanical source |
|---|---|
| Reproducibility | `log/parameters.json` + `Job_NNN_*/scripts/` + `shared_inputs/INPUTS.md` (sha256 + source) |
| Failure recovery (Supp. Table 3) | `annika_log.py export-failures <project>` over all jobs (concatenates `log/errors.md`) |
| Lesson distill (`dream_deep`) | `annika_log.py export-lessons <project> [--tool ... --class ...]` (concatenates `## Lessons` blocks) |
| User-guided auditable orchestration | JOB_LOG `§4 Human decisions` + `log/decisions.md` per job |
| Evidence units actually used vs. excluded | `INDEX.md` rows: `status=complete` counted; `excluded` / `superseded` rows show what was *not* used and why |
| End-to-end auditability | `INDEX.md` + JOB_LOG.md per row resolve every cited result to a folder; passing `audit` is the gate |

## Pre-export checklist

Before running `export-failures` or `export-lessons` for the manuscript:

1. `annika_log.py audit <project>` is clean (no missing description / parameters / errors / result / lessons).
2. Every input cited in any JOB_LOG has a row in `shared_inputs/INPUTS.md` with sha256.
3. Every `excluded` / `superseded` INDEX row has its mandatory reason field filled.
4. Every `decisions.md` referenced from JOB_LOG §4 exists (or §4 explicitly says "None.").
5. `log/errors.md` headers conform to the canonical 6-column schema (`schemas.md` §3) — exporters refuse non-conforming tables.

## Anti-overclaim guardrails

- Do not describe a recovery as "autonomous" if `decisions.md` shows a human decision changed the path. The export tool tags such entries `human_approval` in the recovery_pattern column when emitted as lessons.
- Do not cite a job whose status is `running` or `failed` as evidence of success.
- Do not concatenate `errors_detail.md` into Supp. Table 3 — only `errors.md` is schema-stable.
