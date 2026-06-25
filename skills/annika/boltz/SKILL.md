---
name: boltz
description: >-
  Config-first, validated assistant for Boltz (jwohlwend/boltz) — biomolecular
  structure and binding-affinity predictor (Boltz-1/Boltz-2; CLI `boltz
  predict`). Validated against Boltz v2.2.1 on Linux+NVIDIA (2026-06-23). Use
  whenever the user wants to install, configure, understand, or run Boltz:
  writing YAML inputs (protein/DNA/RNA/ligand, MSA, templates,
  pocket/contact/bond constraints), generating `boltz predict` commands without
  hallucinating flags, choosing Boltz-2 vs Boltz-1, running structure or
  ligand-affinity prediction, interpreting outputs (confidence/PAE/pLDDT,
  affinity_pred_value vs affinity_probability_binary), MSA-server vs custom MSA,
  or troubleshooting install/CUDA/kernel/OOM/MSA errors. ALWAYS runs a read-only
  env probe first; on a validated host it emits concrete commands with real
  paths and, after explicit confirmation, MAY run real Boltz jobs — never
  installs or runs without confirmation. Triggers: boltz, boltz predict, boltz2,
  affinity prediction, ColabFold MSA, use_msa_server.
---

# Boltz

Boltz (`jwohlwend/boltz`) predicts 3D structures of biomolecular complexes and,
with Boltz-2, ligand **binding affinity**. This skill helps you choose a model,
write valid YAML inputs, generate correct `boltz predict` commands, run them on a
validated host, and interpret outputs — without inventing flags or overstating
what affinity numbers mean.

Everything here is grounded in the pinned upstream tag **v2.2.1**
(commit `cb04aec`) and a live run on the host `volta`. When live behavior and
docs disagree, live behavior wins — re-probe rather than trust memory.

## The one rule: probe before you act

This is an environment-sensitive GPU tool. **The machine running this agent is
not assumed to be the Boltz runtime.** So you operate as a state machine, and
what you may do depends on having a *current* environment probe report — one you
captured this session, on the actual target host.

Run the probe (read-only, stdlib, touches nothing, downloads nothing):

```bash
python scripts/boltz_env_probe.py            # human-readable report
python scripts/boltz_env_probe.py --json      # machine-readable
python scripts/boltz_env_probe.py --deep      # opt-in: imports torch in a timed subprocess
```

| State | Meaning | You MAY | You MUST NOT |
|---|---|---|---|
| **UNCONFIGURED** | No probe report captured this session | Explain Boltz; draft YAML; write *example* command text clearly labeled "not yet run"; read references | Claim a specific machine can/can't run it; run `boltz`; install anything |
| **PROBED** | Fresh probe report exists for this host | Everything above with the host's **real** env name, cache path, GPU; recommend an install/update plan | Run a real prediction until the user confirms that specific action |
| **VALIDATED** | Probe shows `boltz` importable + weights present (and ideally a fixture passed) | After **explicit per-action confirmation**, run real `boltz predict` jobs with output safeguards | Run private/large screens without discussing cost, privacy, VRAM |

A probe report goes stale: if the host, conda env, or session changed, re-probe.
Do not carry a verdict from one machine to another.

After a probe, write/update a site config so the next session starts warm — see
`configs/site_config.template.md`. A filled, validated example for `volta` is in
`configs/site_config.volta.example.md`.

## Hard safety rails (these protect the user, not the tool)

- **Affinity is a triage signal, not an experiment.** `affinity_probability_binary`
  is a binder-vs-decoy probability for hit discovery; `affinity_pred_value` is a
  *comparative* affinity for ranking active binders, reported as `log10(IC50)`
  with IC50 in µM (**lower = stronger**). Never call either an experimental
  affinity or a substitute for FEP/assays. See `references/06_affinity_workflow.md`.
- **MSA server = sending sequences to a third party.** `--use_msa_server` posts
  your sequence to the public ColabFold/MMseqs2 API by default. For unpublished
  or confidential sequences, use a custom MSA instead. Flag this before running.
- **Don't overstate the environment.** CPU and Apple-Silicon/MPS paths are not a
  validated default for production-quality geometry. NVIDIA+CUDA is the supported
  path. Say so plainly.
- **Boltz-2 training/eval pipelines are incomplete upstream** ("coming soon").
  Don't improvise a retraining recipe.
- **Never install or run without explicit confirmation.** `scripts/install_boltz.sh`
  refuses without `--yes`. Prediction runs need the user to approve that action.

## Reference routing — read the one you need, don't dump them all

| You need to… | Read |
|---|---|
| Understand scope, trust ladder, what NOT to claim | `references/00_scope_and_trust.md` |
| Find the pinned source / docs / papers behind a claim | `references/01_source_map.md` |
| Install, pick CUDA vs CPU, set cache, handle kernels/VRAM | `references/02_install_and_environment.md` |
| Get exact flags, defaults, and known-stale help strings | `references/03_cli_reference.md` |
| Write a YAML input (any entity, MSA, templates, constraints) | `references/04_input_yaml_schema.md` |
| Run a standard prediction (monomer→complex, custom MSA, batch) | `references/05_core_workflows.md` |
| Run/interpret ligand affinity correctly | `references/06_affinity_workflow.md` |
| Read the output tree and confidence/PAE/pLDDT fields | `references/07_outputs_and_confidence.md` |
| Talk about benchmarks/quality honestly | `references/08_validation_and_benchmarks.md` |
| Diagnose an install/CUDA/kernel/OOM/MSA/input error | `references/09_troubleshooting.md` |
| Decide model/MSA/runtime quickly | `references/10_decision_trees.md` |

## Quick orientation (details in the references)

**Install (NVIDIA/CUDA, recommended):** `pip install boltz[cuda] -U`
(Python `>=3.10,<3.13`). CPU works but is much slower and not a quality-validated
default. Weights+data auto-download to `~/.boltz` (or `$BOLTZ_CACHE`).

**Minimal run (auto MSA):**

```bash
boltz predict input.yaml --use_msa_server --out_dir results
# -> results/boltz_results_input/predictions/input/input_model_0.cif (+ confidence/pae/pde/plddt)
```

**Minimal YAML (one protein, auto MSA):**

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MVK...           # omit `msa:` to auto-generate with --use_msa_server
```

**Default model is Boltz-2** (`--model boltz2`). Use `--model boltz1` only if you
specifically need Boltz-1; affinity, templates, contact constraints, and method
conditioning are **Boltz-2 only**.

When you generate a command, only use flags you can find in
`references/03_cli_reference.md` (live-captured from `boltz predict --help` on a
real install). If a user needs a flag you can't confirm, capture live help on
their host first.

## Scripts

- `scripts/boltz_env_probe.py` — read-only env/state probe (run first). Reports
  conda envs with Boltz, version, torch/CUDA, GPUs + compute capability, `~/.boltz`
  weights, and a state verdict. Default run never writes, mkdirs, or downloads.
- `scripts/install_boltz.sh` — consent-gated installer/updater (refuses without
  `--yes`). Creates/updates a conda env and `pip install boltz[cuda] -U`.
- `scripts/verify_boltz.py` — post-install verifier: import + version + `boltz
  --help` + weights check, optional tiny fixture (`--fixture`).

## House notes

- This skill works under both Claude (`~/.claude/skills/boltz`) and Codex
  (`~/.codex/skills/boltz-skill`); scripts are stdlib/portable. Codex UI metadata
  lives in `agents/openai.yaml`.
- Record anything you learn the hard way in `lessons.md`.
