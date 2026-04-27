# Implementing the full StructAgent system

This document describes how to reproduce the Annika/Maria/A2A design without using private configuration from the original deployment.

## 1. Requirements

- OpenClaw or an equivalent multi-agent runtime with:
  - separate agent workspaces;
  - tool/skill loading;
  - a message bus or A2A JSON-RPC endpoint;
  - filesystem access for structural-biology tools.
- Structural-biology tools as needed:
  - ChimeraX;
  - ISOLDE;
  - PHENIX;
  - Coot;
  - CCP4 / REFMAC5 / Servalcat;
  - gemmi;
  - Python scientific stack.
- Model providers or local models chosen by the implementer.

## 2. Create the agents

Create two agent workspaces.

```text
workspace-maria/
  AGENTS.md
  skills/
  memory/ or project database/

workspace-annika/
  AGENTS.md
  skills/
  runs/
  tools/
```

Recommended division:

- install `skills/maria/*` into Maria's `skills/` directory;
- install `skills/annika/*` into Annika's `skills/` directory.

## 3. Minimal agent role prompts

Maria:

```text
You are Maria, the domain-reasoning agent for StructAgent. Your job is to read literature, maintain the project knowledge base, propose structural-biology workflows, critique results, identify risks, and decide whether evidence supports a claim. You do not leak private data or raw unpublished datasets. You ask Annika to execute when tool work is needed.
```

Annika:

```text
You are Annika, the execution orchestrator for StructAgent. Your job is to run structural-biology tools, maintain provenance, capture metrics, recover from failures, and report concise results. You ask Maria for scientific planning or review when choices depend on domain judgment.
```

## 4. Configure A2A messaging

Use a local A2A gateway or equivalent JSON-RPC endpoint. Do **not** hard-code tokens in scripts. Use environment variables.

```bash
export STRUCTAGENT_A2A_URL="http://127.0.0.1:18800"
export STRUCTAGENT_A2A_TOKEN="replace-with-generated-token"
```

A sanitized sender template is provided at [`../scripts/a2a-send-template.sh`](../scripts/a2a-send-template.sh).

Example:

```bash
./scripts/a2a-send-template.sh --to maria --message "Review this refinement plan and define stop criteria."
./scripts/a2a-send-template.sh --to annika --message "Run PHENIX validation and return MolProbity, clashscore and rotamer outliers."
```

## 5. Recommended task loop

1. User asks for a structural-biology task.
2. Annika captures inputs, constraints and success criteria.
3. Annika asks Maria for a scientific plan when needed.
4. Annika executes tool steps and records provenance.
5. Maria reviews outputs and flags scientific concerns.
6. Annika reports final status and artifacts.

## 6. Privacy and release hygiene

Never publish:

- private identities/persona files;
- raw chat transcripts;
- API tokens or A2A bearer tokens;
- private routing config;
- unpublished structure IDs or coordinates unless cleared;
- full PDFs unless license permits redistribution.

Publishable material should be protocols, wrappers, derived notes, citations, BibTeX, and sanitized provenance summaries.
