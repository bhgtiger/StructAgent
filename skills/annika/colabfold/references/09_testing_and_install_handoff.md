# Testing and install handoff

**Status of this document: nothing here has been performed.** It is a checklist
for a human operator on a future machine. It grants no approval, schedules no
work, and records no test result. Every command shown is a *candidate to review*,
not an instruction to execute now.

Authoring context: this skill was written on a macOS/arm64 host (user reports a
Mac mini) with, according to the recorded source-gathering runtime probe, no
ColabFold, no MMseqs2, no Conda, and no NVIDIA tooling; default `python3` was
3.9.6, below the required `>=3.10`; Docker CLI was present but its daemon and
GPU runtime were never validated and no image was pulled. A source-only
`python -m ... --help` attempt was blocked by missing dependencies, confirming
the clone is source evidence, not an installed runtime.

## Five distinct stages — do not collapse them

These are separate decisions with separate risks. Completing one never
authorizes the next.

| Stage | What it does | Touches ColabFold? | Can predict? |
|---|---|---|---|
| **A. Apply the proposal** | Turns pending Skill Workshop proposal `colabfold-20260725-3bfa27716a` into an approved skill artifact | No | No |
| **B. Install the skill into an agent runtime** | Makes the approved skill loadable by a future agent | No | No |
| **C. Install/configure ColabFold** | Creates a real ColabFold v1.6.2 environment and weights | Yes | Not yet |
| **D. Test runtime behavior** | D1: does the *skill* behave. D2: does the *ColabFold runtime* behave | D2 only | Fixture only |
| **E. Execute a real prediction** | Runs a user's actual scientific job | Yes | Yes |

Stages A and B produce a documentation-only advisor. After A and B, and with no
C at all, the skill is fully functional for its intended purpose: it advises and
plans. **C, D2, and E are not prerequisites for using this skill.** Only pursue
them if someone actually needs to run ColabFold.

Stage E is outside this skill's contract entirely. The skill cannot perform it,
and no expansion into an executing skill is authorized by this document.

### Stage A — apply the pending Skill Workshop proposal

- Requires an explicit instruction from Xiaohu. The project record states the
  proposal is deliberately not applied without one.
- Apply through the same Skill Workshop interface that created the proposal.
  This document intentionally does not reproduce an apply command, because no
  such command was captured in the project record; inventing one would be a
  fabrication.
- Expected artifact: `SKILL.md` plus ten support files, `00`–`09`.
- Note the proposal carries package version `v1` while support files `00`–`08`
  describe the capability tier as `v0`. These are the same read-only scope; see
  "Version and capability-tier naming" in `SKILL.md`.
- Acceptance: frontmatter valid, all ten support files present, every
  `references/NN_*.md` path referenced in `SKILL.md` resolves.
- Prior audit state, carried forward honestly: design audit B approved the
  scope/safety design; factual spot-check audit C was attempted three times and
  returned no usable verdict. **Audit C is inconclusive, not approval.** Consider
  rerunning it before or after applying.

### Stage B — install the skill into the future agent runtime

- Place the applied skill wherever the target agent runtime loads skills from.
  The correct path is runtime-specific and was not captured here; confirm it from
  that runtime's own documentation rather than assuming one.
- Acceptance: the agent loads the skill, and the support files are readable.
- This stage installs *documentation*. It does not create any ability to run
  ColabFold, and must not be described as "installing ColabFold".

### Stage C — install/configure ColabFold itself (separate authorization)

- Requires its own explicit decision, a target host, and a `jobs/Job_NNN_*`
  ledger entry per the project's execution-project convention.
- The official README at the pinned tag documents Conda + pip and Docker routes.
  **Use the README at commit `c7d1772352cc9619df25c6d36cb0f218c0c6610e` as the
  authority.** This document deliberately does not reproduce install commands,
  because none were captured from source during collection.
- Installing prediction extras pulls `alphafold-colabfold`, JAX, Haiku, dm-tree,
  absl, and optionally OpenMM/PDBFixer. This is not a lightweight pip install.
- Weight download is a separate concern: source `download.py` can fetch model
  parameters automatically. Confirm weight licenses *before* download, not after.

### Stage D — testing

**D1 — skill behavior (no ColabFold needed).** Run the natural-language cases in
`references/07_trigger_tests.md` and `references/08_eval_cases.md` against the
installed skill. Pass criteria are in those files. Key failure signals: the skill
offers to run or install something, emits a command as though executed, treats
privacy as settled, implies a runtime exists, or claims a confidence score proves
biology.

**D2 — ColabFold runtime behavior.** Only after Stage C, and only using the
NOT-RUN checklist below with explicit human authorization per item.

## NOT-RUN checklist for the future machine

**NOT RUN — no item below has been performed, by this skill or by anyone, at the
time of writing.** Each box is an action for an authorized human operator.
Capture every output into the job ledger (`log/stdout.log`, `log/stderr.log`,
`log/errors.md` as errors happen, `log/decisions.md` for approvals, and hashes in
`shared_inputs/INPUTS.md`).

### 1. Version and help capture

- [ ] Record the installed distribution version through your package manager's
      show/list command. Do not assume a distribution name; read it from the
      environment you built.
- [ ] Capture `colabfold_batch --help` verbatim.
- [ ] Capture `colabfold_search --help` verbatim.
- [ ] Capture `colabfold_split_msas --help` verbatim.
      (These three are the exact commands official CI smoke-tests.)
- [ ] Check whether a `--version` flag exists. **Unknown** — it was never
      confirmed. If absent, do not invent one.
- [ ] Diff captured help against the pinned v1.6.2 source baseline and this
      skill's documented safety claims; record every discrepancy. Live help
      outranks source-derived notes.

### 2. Python and package prerequisites

- [ ] Confirm the interpreter is Python `>=3.10` (manifest requirement).
- [ ] Prefer 3.10–3.12, the range official CI actually exercises. Anything newer
      is untested by upstream CI as of v1.6.2.
- [ ] Record the resolved versions of JAX and the AlphaFold-related dependencies.

### 3. Operating system, GPU, CUDA, JAX, Docker-NVIDIA

- [ ] Record OS and architecture. Upstream CI covers Ubuntu only; macOS/Apple
      Silicon prediction support is **not** established.
- [ ] Record GPU model, architecture, and driver version.
- [ ] Record the CUDA version and confirm the JAX wheel matches it. v1.6.2
      publishes CUDA 12/13 and ARM64 Docker improvements; confirm which applies.
- [ ] If using `--use-pallas`: confirm the GPU is NVIDIA Ampere or newer.
- [ ] If relying on Amber relaxation: source states GPU Amber relaxation is
      unsupported on AMD/ROCm and Apple Silicon.
- [ ] If using Docker: confirm the daemon runs, the NVIDIA container runtime
      actually exposes the GPU inside a container, and the image tag matches the
      pinned version. **Docker CLI presence proves none of this.**
- [ ] Note dated community signals as triage hints only, never as fixes:
      MSA-server timeout/connectivity reports (#838, #843), GPU/MLIR errors on
      Blackwell hardware (#841, #813), and memory-mapping errors (#837).

### 4. Model weights and licensing

- [ ] Confirm which model weights each intended `--model-type` requires
      (`auto`, `alphafold2`, `alphafold2_ptm`, `alphafold2_multimer_v1|v2|v3`,
      `deepfold_v1`).
- [ ] Obtain and read the license for **every** weight set you intend to use.
      Code is MIT, but the manifest states "MIT, but separate licenses for the
      trained weights." MIT does not cover weights.
- [ ] Confirm the intended use (internal research, publication, redistribution,
      commercial) is permitted by those weight licenses. Record the decision in
      `log/decisions.md`.
- [ ] Decide deliberately whether automatic weight download is acceptable on
      this host and network, before first run.

### 5. MSA privacy and retention approval

- [ ] **Default position: no private sequence may be submitted anywhere, and no
      public-MSA submission is permissible.** This holds until a human explicitly
      approves a specific submission for a specific sequence.
- [ ] Obtain current written retention/processing terms from the operator of
      `https://api.colabfold.com`. None were found in the official repository,
      Wiki, or domain-focused search during collection. **Unknown ≠ safe.**
- [ ] Confirm the sequence owner permits third-party transmission at all.
      Official Wiki text notes users may not be allowed to send protein
      sequences to a third-party server.
- [ ] If proceeding: honor the source fair-use warning — serial submissions from
      a single source IP; the operator reserves the right to limit access.
- [ ] Verify `--host-url`, which changes the data destination.
- [ ] **Trap:** `--templates` can query the server even with a local A3M input.
      An "A3M means offline" assumption is wrong.
- [ ] For large-scale work, plan local `colabfold_search` instead — but treat it
      as infrastructure (prepared MMseqs2 databases, hundreds of GB to TB-class
      disk/RAM, `--threads` defaults to 64), not a laptop fallback.

### 6. Disposable public fixture

- [ ] Use only public files checked into the pinned repository, e.g.
      `test-data/batch/input/5AWL_1.fasta` (10-residue monomer) or
      `test-data/complex/input.csv` (two-chain complex). Never a user sequence.
- [ ] Run mocked/unit fixtures first (`tests/`,
      `test-data/mmseqs-api-reponses/*.json`) — these exercise the client
      offline and prove nothing about the live API.
- [ ] Do **not** submit repository fixtures to the public server merely to test
      it; that is the fixture discipline recorded in the project.
- [ ] For a network-free first live check, `single_sequence` is listed in source
      among the `--msa-mode` values and would in principle avoid a server call.
      **Confirm this from captured live help and by observing actual network
      behavior before relying on it.** Treat it as unverified until then.
- [ ] Use a fresh, disposable result directory containing nothing you care about.

### 7. Output-tree capture

- [ ] Preserve the complete result tree from the fixture run as the project's
      first real output evidence.
- [ ] Confirm presence and naming of: `config.json`, `cite.bibtex`, `<job>.a3m`,
      `<job>_unrelaxed_<rank/model tag>.pdb`,
      `<job>_scores_<rank/model tag>.json`, `<job>_coverage.png`,
      `<job>_predicted_aligned_error_v1.json`, `<job>_pae.png`,
      `<job>_plddt.png`.
- [ ] Record the actual score-JSON keys and array shapes. The single checked-in
      example (`utils/3G5O_A_3G5O_B_unrelaxed_rank_1_model_1_scores.json`) has
      `plddt`, `pae`, `max_pae`, `ptm`, with pLDDT vector and PAE matrix both of
      length 180. Do **not** generalize optional fields from one example.
- [ ] Confirm pLDDT is written into the PDB B-factor column, and note it for
      downstream tools that expect the opposite uncertainty convention.

### 8. `--overwrite-existing-results` ambiguity (explicit check)

- [ ] This is an unresolved P0 discrepancy. Parser help says "Do not recompute
      results"; source passes
      `keep_existing_results = not args.overwrite_existing_results`, which reads
      as the opposite.
- [ ] Test **only** in a disposable directory with expendable contents, on a
      machine where nothing valuable shares the path.
- [ ] Design the test to distinguish the two hypotheses: pre-populate a result
      directory with a recognizable prior artifact, run with the flag, run
      without it, and record in both cases whether the prior artifact was
      preserved, recomputed, or overwritten.
- [ ] Record captured help text alongside observed behavior.
- [ ] Until this is resolved by observation, the skill must continue to never
      recommend or synthesize the flag.

### 9. `--zip` destructive behavior (explicit check)

- [ ] Source creates `<job>.result.zip` and then **deletes most original result
      artifacts after a successful archive operation.** This is destructive.
- [ ] Test only in a disposable directory, and only after Item 7 has preserved a
      known-good copy of an output tree elsewhere.
- [ ] Record exactly which files survive and which are removed.
- [ ] Until then, `--zip` is never added silently to any plan.

### 10. Standing prohibitions during all of the above

- [ ] No user/private sequence enters any command, at any stage, without a
      recorded per-sequence human approval.
- [ ] No public-MSA submission by default, at any stage.
- [ ] No skipping the ledger: a tool run that matters gets a `jobs/Job_NNN_*`
      folder, inputs hashed, errors appended as they occur.

## Stop conditions

Halt and escalate to Xiaohu rather than improvising if:

- captured live help contradicts a documented safety claim in this skill or the
  pinned v1.6.2 source;
- retention/privacy or weight-license terms remain unobtainable and someone
  wants to proceed anyway;
- the overwrite test is ambiguous or non-reproducible;
- a fixture run produces artifacts materially different from Item 7;
- anyone proposes testing with a real, unpublished sequence.

## What successful stages would unlock — and what they would not

Per the project's deployment ladder, evidence from these stages *could support a
future proposal* to widen scope: inspecting a user-provided existing local output
directory (v1), writing validated input/command files after confirmation (v2),
or executing jobs after per-job privacy/compute/output/destructive-option
confirmation (v3).

None of that is authorized here. Each tier needs its own proposal, its own audit,
and its own explicit instruction from Xiaohu. Completing this checklist changes
the *evidence*, not the *permissions*.

## Unchanged regardless of any test result

pLDDT is local model confidence — not a measured B-factor, and not proof of a
correct fold, a binding event, an interaction, or a biological state. For
complexes, inspect inter-chain PAE and interface-oriented metrics, and require
orthogonal experimental evidence. No amount of runtime validation changes this.