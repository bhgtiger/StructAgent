# 00 — Scope and Trust

## What this skill is for

Helping a user **understand, configure, and run Boltz** for biomolecular
structure prediction and (Boltz-2) ligand binding-affinity prediction:

- choose Boltz-2 vs Boltz-1;
- write valid YAML inputs (protein/DNA/RNA/ligand, MSA, templates, constraints);
- generate correct `boltz predict` commands grounded in real CLI help;
- run predictions on a validated GPU host, with consent and safeguards;
- interpret the output tree and confidence/affinity fields honestly;
- triage install, CUDA/kernel, OOM, MSA, and input errors.

## What this skill is NOT

- Not a wet-lab oracle: affinity outputs are triage signals, not measurements.
- Not a retraining/eval guide: upstream Boltz-2 training/eval docs are explicitly
  incomplete ("coming soon"). Don't improvise those workflows.
- Not a CPU/Apple-Silicon production endorsement: those paths exist but are not a
  quality-validated default. NVIDIA+CUDA is the supported path.
- Not a benchmark authority: report paper/README numbers as *claims*, attributed.

## Source trust ladder (highest first)

1. **Live behavior** on the actual target host (`boltz --help`, a real run).
2. **Pinned source** at tag `v2.2.1`, commit `cb04aec` (the clone shipped with
   the source project, and `references/01_source_map.md`).
3. Official repo docs/examples at that tag.
4. PyPI metadata (package/dependency/Python constraints).
5. Boltz-1 / Boltz-2 / ColabFold papers (method + benchmark context).
6. GitHub release notes.
7. GitHub issues — *leads only* for failure modes, never ground truth.

When two sources disagree, prefer the higher rung. If live help and docs
disagree about a flag default, **trust live help and say which host it came
from**. Help strings themselves can be stale (see `03_cli_reference.md`).

## Must-not claims (these have burned people)

- "Boltz released full Boltz-2 training/eval pipelines." (They haven't.)
- "CPU / Apple Silicon is validated for production geometry." (Not established.)
- "`affinity_pred_value` is the experimental affinity." (It is a predicted,
  comparative `log10(IC50)`; meaningful mainly among *active* binders.)
- "These README/paper benchmark numbers are independently verified." (Attribute
  them; don't launder them into guarantees.)

## Versioning

This skill is pinned to Boltz **v2.2.1** (matches PyPI and the install validated
on `volta`). Boltz's `main` moves fast; if a user is on a different version,
re-capture live help before generating execution-grade commands.
