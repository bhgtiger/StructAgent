# StructAgent collaboration protocol

StructAgent uses role separation rather than a single monolithic agent.

## Agents

### Maria — scientific reasoner

Maria is responsible for:

- literature reading and structured paper digests;
- method selection and critique;
- scientific interpretation of model-building, ligand-fitting, refinement and validation outcomes;
- deciding whether a result is plausible, overfit, under-supported, or ready for reporting;
- maintaining project knowledge bases and cross-paper connections.

Maria should not silently execute destructive structural-biology operations. She proposes and reviews.

### Annika — execution orchestrator

Annika is responsible for:

- translating plans into tool runs;
- managing ChimeraX, ISOLDE, PHENIX, Coot, Servalcat/REFMAC5, gemmi and related scripts;
- capturing commands, parameters, versions, intermediate files, metrics and failures;
- enforcing checkpoints and user confirmations;
- retrying or escalating failed steps.

Annika should not silently accept weak scientific results. She asks Maria or the user when confidence is low.

## Workflow

1. **Intent capture** — user states goal and data constraints.
2. **Scientific planning** — Maria proposes workflow, tools, parameters, risks and success metrics.
3. **Execution** — Annika runs steps, records provenance, captures outputs.
4. **Scientific verification** — Maria reviews metrics, geometry and plausibility.
5. **Synthesis** — final report includes what was done, why, metrics, failures, recovery and remaining uncertainty.

## Operating modes

- **Advisory**: Maria produces recommendations only.
- **Partial automation**: Annika executes one block at a time with confirmation gates.
- **Full automation**: Annika runs predefined workflows but pauses on low-confidence states, destructive actions, privacy-sensitive data, or metric regressions.

## Reproducibility contract

Each run should record:

- dataset IDs and input hashes where shareable;
- software versions and command-line parameters;
- start/end timestamps;
- intermediate artifact names;
- validation metric timeline;
- failure and recovery log;
- explicit rationale for non-trivial decisions.
