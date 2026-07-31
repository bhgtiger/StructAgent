---
name: "colabfold"
description: "Use for ColabFold/colabfold_batch: configure hosts, plan or run AlphaFold2(-Multimer), choose MSA/privacy, inspect outputs, or troubleshoot."
---

# ColabFold

Use this skill for the stable ColabFold AlphaFold2/AlphaFold-Multimer command-line workflow. Treat upstream v1.6.2 as the pinned source baseline, but prefer captured live help and validated behavior from the configured host whenever they differ.

## Start with intent and configuration

Classify the request as conceptual guidance, environment/configuration, command planning, execution, existing-output interpretation, or troubleshooting.

For general conceptual questions, answer without claiming anything about the current host. For every host-specific claim or action:

1. Resolve the config path from `COLABFOLD_SKILL_CONFIG`, otherwise use `${XDG_CONFIG_HOME:-~/.config}/colabfold-skill/site-config.json`.
2. If the config is absent, run the default read-only probe from this skill and show the result. Add `--live-help` only when the user wants a runtime check; it starts the configured launcher with `--help` but performs no prediction and may initialize launcher cache files.
3. Validate an existing config with `python3 scripts/colabfold_env_probe.py --validate-config <path>`.
4. Bind every readiness claim to the config's host pattern, timestamp, runtime version, and evidence. Configuration records facts; it never grants permission.

Create a private external config, not a file inside the portable skill:

```text
python3 scripts/colabfold_env_probe.py \
  --launcher /absolute/path/to/colabfold_batch \
  --runtime-version 1.6.2 \
  --scheduler auto \
  --msa-policy deny_remote \
  --output ~/.config/colabfold-skill/site-config.json
```

Use `templates/site-config.example.json` for manual configuration and read `references/configuration.md` for the schema and state rules.

## State controls what may be claimed

- `ready`: launcher/version plus matching structured CPU/GPU fixture evidence pass for this host/profile. Plan concrete commands; execute only after per-action approval.
- `probed`: launcher or environment was inspected, but GPU/fixture evidence is incomplete. Give gap-aware plans; do not claim prediction readiness.
- `blocked`: a required runtime/launcher is absent or unusable. Explain the blocker; do not improvise an install or run.
- `stale`: version, runtime identity, receipt, or host no longer matches. Treat as unknown and re-probe.
- `unknown`: no trustworthy config. Give general guidance only.

## Action and approval boundaries

Proceed without additional confirmation only for read-only work: read the config/references, inspect files the user supplied, run the default environment probe, capture `--help` after explaining its possible cache initialization, and summarize an existing local result tree.

Obtain explicit confirmation before each action that writes, downloads, submits, or consumes meaningful compute:

- create or alter FASTA/A3M/CSV, job scripts, result directories, or configs;
- install/update ColabFold, containers, JAX/CUDA dependencies, model weights, or databases;
- submit/run a CPU, GPU, scheduler, container, or MSA job;
- send any sequence or template query to a remote MSA/template service;
- reuse or replace an existing result directory;
- enable `--zip`, `--overwrite-existing-results`, or another destructive/ambiguous option.

Before a prediction, echo the exact command, input and result paths, model/MSA route, expected network and weight-download behavior, scheduler/GPU resources, and preservation plan. Never infer blanket approval for future sequences from one approved job.

Every executable-looking command must contain only syntax and values supported by captured live help, the validated config, or explicit user input. Never put illustrative or guessed flag values inside a command block, including recycle, seed, model, scheduler, or resource values. Omit unsupported options or use a visibly non-executable `<NOT_SUPPLIED>` placeholder. Describe the possible loss of evolutionary information from `single_sequence` as a target-dependent tradeoff; do not promise that a particular confidence score will rise or fall.

## Privacy and destructive options

Treat sequences, templates, labels, paths, and result metadata as potentially confidential. Public MSA use can transmit sequence data to a third party. The collected official sources do not establish current retention/processing terms, so unknown must not be presented as safe. Default to `deny_remote`; `per_job_approval` still requires explicit approval for every submitted sequence. Use `single_sequence` or an approved local A3M/database route when off-host transfer is not permitted, while explaining the scientific tradeoff.

`--templates` may query a server even with A3M input. `--zip` deletes most original outputs after making the archive. Never add it silently. The v1.6.2 `--overwrite-existing-results` help wording conflicts with source-flow interpretation; do not recommend or synthesize it until behavior is established in a disposable fixture.

## Plan and execute a workflow

1. Read and validate the workstation config.
2. Confirm protein-only scope, input form, monomer versus complex, and colon-separated chain grammar. Route ligand, DNA/RNA, or AlphaFold3 work to a separate grounded workflow.
3. Choose the MSA route. State whether it transmits sequence data and whether templates add network access.
4. Select a model from captured live help. Do not claim an untested model type is validated merely because it is listed.
5. Choose a fresh result directory. Preserve inputs, command, runtime/config snapshot, stdout/stderr, and checksums in the active project/job ledger.
6. Present the exact command and resource/network effects, then wait for explicit approval.
7. Execute only within the approved scope. Stop on version/config drift, unexpected download/network behavior, or an existing non-disposable output path.
8. Inspect outputs with `scripts/summarize_colabfold_output.py`; record missing or extra artifacts rather than inventing them.
9. Interpret confidence conservatively and recommend orthogonal validation.

Read `references/workflows.md` for input forms, command planning, scheduler use, and expected outputs. Read `references/validation-and-troubleshooting.md` for fixture and failure gates.

## Interpret results without overclaiming

pLDDT is local model confidence, not a measured B-factor or proof of a correct fold. Although ColabFold writes pLDDT into the PDB B-factor column, its direction and meaning differ from experimental displacement parameters. For complexes, discuss inter-chain PAE and interface metrics such as ipTM together with independent biological evidence. Never infer binding, mechanism, oligomeric state, or publication readiness from a threshold alone.

Use the summarizer for local evidence:

```text
python3 scripts/summarize_colabfold_output.py /path/to/results
```

## Reference and resource routing

- Scope, approvals, privacy, licensing, and scientific claim limits: `references/scope-and-safety.md`.
- Config path, schema, state machine, host identity, and portability: `references/configuration.md`.
- Inputs, MSA choices, command plans, execution, and outputs: `references/workflows.md`.
- Runtime/fixture checks and failure triage: `references/validation-and-troubleshooting.md`.
- Pinned upstream sources and evidence hierarchy: `references/source-map.md`.
- Workstation-config generator/validator: `scripts/colabfold_env_probe.py`.
- Read-only output summarizer: `scripts/summarize_colabfold_output.py`.
- Package validator: `scripts/validate_skill.py`.
- Portable config skeleton: `templates/site-config.example.json`.
- Behavioral eval cases: `examples/evals.json`.
- Public network-free fixture contract: `examples/gcn4p1-dimer.fasta` and `examples/smoke-expectations.json`.

## Portability contract

Ship one canonical skill package and keep the filled workstation config external. Never package a real hostname, username, home path, cluster partition, API credential, private sequence, or validation-job path. Another workstation needs this package plus a valid config and an existing ColabFold runtime; configuration does not install ColabFold itself.
