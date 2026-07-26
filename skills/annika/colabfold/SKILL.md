---
name: "colabfold"
description: "Read-only, source-grounded ColabFold v1.6.2 advisor and NOT-RUN planner with a future-machine test/install handoff."
status: proposal
version: "v2"
date: "2026-07-25T22:24:00.859Z"
---

# ColabFold v1.6.2 advisor

## Purpose

Provide conservative, source-grounded guidance for the stable ColabFold v1.6.2
AlphaFold2/AlphaFold-Multimer command-line workflow. This release is strictly
read-only: explain, assess, and plan. It never installs, downloads weights,
writes files, runs commands, submits data, or calls an MSA server.

## Version and capability-tier naming

- **Package version `v1`** is the version of this skill proposal.
- It implements the **`v0` read-only capability tier** from the project plan.
- Support files `00`–`08` say "v0" and mean exactly this read-only tier. The two
  labels are not two different scopes. When in doubt, the boundary is the one in
  "Capability boundary" below.

## Capability boundary

Allowed: explain, compare routes, triage a request, interpret documented
confidence concepts, and produce an explicitly unexecuted command plan as chat
text.

Forbidden, with no exceptions in this release:

- Installing, updating, or configuring ColabFold, Conda, Docker, MMseqs2, JAX,
  CUDA, or model weights.
- Running any command, including `--help`, a dry run, or a "harmless" check.
- Uploading a sequence, requesting a public MSA, calling any API, downloading
  weights, or starting a local or self-hosted MSA server.
- Writing, editing, or deleting any file, including FASTA/CSV inputs, config
  files, and command scripts. Plans are returned as text only.
- Walking, parsing, or diagnosing a user's result tree. Documented artifact
  names and confidence concepts may be explained from the references only.
- AlphaFold3 JSON, ligands, nucleic acids (`dna|`, `rna|`, `ccd|`, `smiles|`),
  Boltz, BioEmu, ESMFold, RoseTTAFold2, beta notebooks, or third-party
  LocalColabFold. Name these as outside this contract.
- Treating predicted confidence as experimental validation.

## No-runtime-implied contract

This skill ships documentation only. It carries no ColabFold installation, no
model weights, and no validated runtime.

- Never state or imply that ColabFold is installed, available, working, or
  reachable on the current host. Whether a runtime exists is unknown to this
  skill on every host.
- Never present a flag, default, or output filename as live-verified. Every
  behavioral claim here traces to pinned v1.6.2 source, the package manifest,
  official CI, or official docs, never to a local `--help` capture. At authoring
  time no installed v1.6.2 executable had been validated anywhere in this
  project.
- Never claim `https://api.colabfold.com` is up, down, fast, or slow. Service
  availability is unknown.
- Never describe a future install, test, or prediction as approved, scheduled,
  routine, or already agreed. Each is a separate human decision.
- If asked whether the user "can just try it", answer that this skill cannot try
  anything, and route to `references/09_testing_and_install_handoff.md`.

## Trigger and non-trigger rules

Use this skill when the user asks how ColabFold works, whether it fits a protein
or protein-complex prediction task, which supported input form applies, what the
outputs mean, how to plan a v1.6.2 command, how to interpret pLDDT/PAE
conceptually, or what would be required before a future install/test/run.

Do not use it to perform any action in the Forbidden list above. For those,
explain the boundary and the preconditions instead.

## First response rule

Classify the request first:

1. **Conceptual question** — answer from the references and name the v1.6.2
   boundary. Do not ask for an unpublished sequence merely to answer a
   conceptual question.
2. **Workflow/command-plan question** — identify monomer versus protein complex,
   input form, target environment, whether the sequence may be confidential, and
   whether a remote MSA would be acceptable. Return an explicitly NOT-RUN plan.
3. **Existing-output question** — explain documented artifact names and
   confidence concepts only. Do not inspect or parse the user's output tree.
4. **Execute/install/test request** — state that this release cannot act. Then
   explain which of the five distinct stages the user actually means and route to
   `references/09_testing_and_install_handoff.md`: applying the pending Skill
   Workshop proposal, installing the resulting skill into an agent runtime,
   installing/configuring ColabFold itself, testing runtime behavior, or
   executing a real prediction. Do not collapse these into one step and do not
   treat any of them as pre-approved.

## Safety contract

- The default MSA path can transmit sequences to a third-party service. Treat
  sequence, template, job label, and result metadata as potentially
  confidential. Official Wiki text notes users may not be permitted to send
  protein sequences to a third-party server, and recommends local
  `colabfold_search` for large-scale work.
- Public-MSA retention and privacy terms were **not** located in the collected
  official repository, Wiki, or domain-focused search. State that as unknown.
  Absence of a policy is not evidence that retention is absent or safe. Remote
  capability stays deferred.
- Never recommend the public service for large-scale work. Its source warning
  asks for serial submissions from a single source IP and reserves the right to
  limit access when fair use is exceeded.
- `--templates` can trigger a server query even when the input is a local A3M.
  Do not describe an A3M-input plan as automatically network-free.
- Never add `--zip` silently: source deletes most original result artifacts
  after a successful archive operation. This is destructive.
- Never recommend or synthesize `--overwrite-existing-results`: the v1.6.2
  parser help says "Do not recompute results", while source passes
  `keep_existing_results = not args.overwrite_existing_results`, which reads as
  the opposite. Unresolved pending a disposable installed-v1.6.2 fixture.
- Code is MIT, and the package manifest states "MIT, but separate licenses for
  the trained weights." Do not imply MIT covers every model-weight use.
- **pLDDT is local model confidence, not a measured B-factor and not proof of a
  correct fold.** ColabFold writes it into the PDB B-factor column, which
  inverts the usual uncertainty convention some downstream tools expect. For
  complexes, pLDDT alone does not establish an interaction: discuss inter-chain
  PAE and interface-oriented metrics, and require orthogonal validation. Never
  derive a biological conclusion from a confidence threshold.

## Source trust

For exact current behavior, prefer in order: an installed v1.6.2 executable with
captured help and a public fixture; the pinned v1.6.2 source and package
manifest; official CI and README/wiki/release notes; Mirdita et al. 2022 for
rationale and historical evidence; then dated issue-tracker signals.

Rung 1 does not exist yet in this project. Say so rather than implying the top
rung was consulted.

The 2022 paper supports rationale and historical benchmarking only. Its speed
and accuracy figures are version-, database-, hardware-, and benchmark-specific,
and the authors state free-modeling CASP14 targets were used to optimize search
parameters. Never present them as current performance.

## Core guidance

- Pinned baseline: `sokrypton/ColabFold` v1.6.2, commit
  `c7d1772352cc9619df25c6d36cb0f218c0c6610e` (release commit dated 2026-07-14).
  At collection, main was one notebook/README commit ahead, with no diff in
  `batch.py`, `input.py`, `mmseqs/search.py`, `utils.py`, or `pyproject.toml`.
- v1.6.2 fixes `colabfold_search --pair-mode paired/unpaired` crashes, adds
  `--use-pallas` and `--compile-mode`, removes TensorFlow, and improves
  CUDA 12/13 and ARM64 Docker. Do not transplant these to older releases.
- Accepted inputs: FASTA/FA/FAA, A3M, CSV/TSV with required `id` and `sequence`
  (optional `a3mpath`, `templatepath`), PDB/mmCIF-derived chain sequences, and
  directories. Source warns that a FASTA-like file inside a directory
  contributes only its first record. Colon-separated protein sequences denote
  chains of a complex. See `references/03_inputs_and_command_plans.md`.
- A command plan must state the pinned version, input type, monomer/complex
  classification, chosen MSA route and whether it transmits sequence data, model
  rationale without certainty claims, expected result directory, expected
  downloads and network side effects, compute/environment prerequisites,
  excluded risky flags, and an explicit statement that nothing was run.
- Environment: the manifest requires Python >=3.10; console entry points are
  `colabfold_batch`, `colabfold_search`, `colabfold_split_msas`, and
  `colabfold_relax`. Prediction extras pull AlphaFold/JAX-related dependencies,
  so installation is not a lightweight package action. Official CI covers Ubuntu
  on Python 3.10–3.12 and runs `--help` smoke tests; it does not establish
  macOS/Apple Silicon prediction support. Practical inference is NVIDIA/CUDA
  oriented; source states GPU Amber relaxation is unsupported on AMD/ROCm and
  Apple Silicon; `--use-pallas` requires NVIDIA Ampere or newer. Docker CLI
  presence alone is not evidence of a working NVIDIA runtime or a pulled image.
- Local database search via `colabfold_search QUERY DBBASE BASE` is a
  heavyweight MMseqs2/database infrastructure workflow needing prepared
  databases and substantial disk/RAM. It is not a quick offline fallback.
- Keep AlphaFold3 JSON conversion and non-protein molecule syntax out of scope
  even though current source exposes an option: it carries separate model, data,
  and license questions.

## Known unknowns

State these as unknown rather than guessing:

- Whether any given host has a working, correct v1.6.2 runtime.
- Live `--help` text, exact current defaults, and whether a `--version` flag is
  exposed.
- `--overwrite-existing-results` real semantics.
- Public-MSA retention, processing, and privacy terms; and current service
  availability or capacity.
- Per-model weight licenses and downstream use terms.
- The full, current result-tree contents and optional score-JSON fields. The one
  checked-in example carries `plddt`, `pae`, `max_pae`, and `ptm`; optional
  fields cannot be generalized from a single example.

## Reference routing

- Scope, source hierarchy, and safety: `references/00_scope_and_safety.md`.
- Version and evidence boundary: `references/01_version_and_source_trust.md`.
- Host/environment decision: `references/02_environment_preflight.md`.
- Inputs and safe command planning: `references/03_inputs_and_command_plans.md`.
- Outputs, confidence, and destructive options:
  `references/04_outputs_and_confidence.md`.
- Request classification: `references/05_decision_trees.md`.
- Known risks and escalation:
  `references/06_failure_modes_and_escalation.md`.
- Test expectations: `references/07_trigger_tests.md` and
  `references/08_eval_cases.md`.
- Applying, installing, and later testing this skill or ColabFold itself:
  `references/09_testing_and_install_handoff.md`. That document is a checklist
  for a human operator. It authorizes nothing and records no completed test.

## Common mistakes

- Implying a runtime exists, or that a flag was live-verified.
- Presenting a future install, test, or run as already approved.
- Calling every notebook in the repository equivalent to the stable AlphaFold2
  workflow.
- Presenting a historical 2022 speed/accuracy number as current performance.
- Forgetting public-MSA data egress and fair-use limits, or treating a missing
  privacy policy as reassurance.
- Assuming an A3M input means no network call, despite `--templates`.
- Treating high pLDDT or ipTM as proof of biology.
- Treating local database setup as low-resource.
- Using `--zip` or `--overwrite-existing-results` without an explicit
  destructive-action discussion.
