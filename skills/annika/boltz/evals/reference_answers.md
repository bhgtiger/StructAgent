# Reference answers (graders' key)

Concise "good answer" sketches for `evals/evals.json`. Grounded in the
references; a strong response need not match wording, only substance + safety.

## 0 — basic-protein-run
YAML: `version: 1` + one `protein` with `id`/`sequence` (omit `msa` for auto).
Command: `boltz predict prot.yaml --use_msa_server --out_dir results`. Mentions
output at `results/boltz_results_prot/predictions/prot/prot_model_0.cif`. Says to
run `scripts/boltz_env_probe.py` first / does not claim it executed. (See 04, 05.)

## 1 — affinity-interpretation
`affinity_probability_binary=0.92` → high binder probability (binder-vs-decoy,
hit triage). `affinity_pred_value=-1.5` → comparative `log10(IC50 µM)`; lower =
stronger (≈ 30 nM), meaningful only among active analogs. Triage signal, not an
experimental affinity; confirm with assays/FEP. (See 06.)

## 2 — msa-privacy
`--use_msa_server` posts the sequence to the public ColabFold/MMseqs2 API → do
not use for unpublished IP. Build a custom MSA offline and reference `msa:
./file.a3m` in the YAML; run without `--use_msa_server`. (See 02, 04.)

## 3 — oom-troubleshoot
Lower `--diffusion_samples` (→1), `--max_parallel_samples`, `--sampling_steps`,
`--recycling_steps`; split/shrink the system; use more VRAM. No official
size→VRAM table. `--no_kernels` is for *kernel* errors, not a primary OOM fix
(though it changes the memory profile). (See 09.)

## 4 — affinity-ligand-too-large
140 atoms > 128 → affinity module **rejects** it (error). Even >56 atoms triggers
a reliability warning. Affinity needs a single ligand chain. Suggest structure-
only prediction for the macrocycle. (See 06.)

## 5 — model-choice
Boltz-2 (the default). Affinity, templates, contact constraints, and method
conditioning are Boltz-2 only. Use Boltz-1 only to reproduce older results.
(See 10, 00.)
