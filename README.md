# StructAgent

StructAgent is a two-agent structural-biology assistant system for cryo-EM model building, refinement, validation, ligand fitting, and ion-site audit workflows.

This release contains two usable layers:

1. **Complete agent system** — an Annika/Maria/A2A architecture for separating scientific reasoning from execution control.
2. **Skills-only mode** — install the released skill protocols into any compatible OpenClaw-style agent and use them without running the full multi-agent system.

The public repository intentionally excludes private identities, tokens, chat routing configuration, raw session logs, and example structural datasets. Reviewer-only evidence bundles are tracked separately.

## Repository layout

```text
architecture/                 System architecture and collaboration protocol
docs/                         Installation, implementation, privacy, versions, release scope
scripts/                      Sanitized helper templates for A2A messaging/setup
skills/annika/                Execution-side structural-biology skills/protocols
skills/maria/                 Reading/reasoning/database/review skills
examples/                     Placeholder and reviewer-bundle notes only
reviewer_bundle_manifest.md   What belongs in the confidential reviewer bundle
LICENSE                       Apache-2.0
```

## Quick start

### Option A — use only the skills

Copy selected folders under `skills/annika/` or `skills/maria/` into your agent's `skills/` directory, restart/rescan the agent, then invoke tasks that match the skill names.

See [`docs/skills_only_usage.md`](docs/skills_only_usage.md).

### Option B — implement the full StructAgent system

Create two agents:

- **Maria** — domain reasoning, paper reading, literature/database synthesis, scientific critique.
- **Annika** — structural-biology execution, tool orchestration, run logging, metric capture, recovery.

Connect them with an A2A JSON-RPC gateway or equivalent message bus. Use the templates in `scripts/` and the protocol in `architecture/collaboration_protocol.md`.

See [`docs/full_system_implementation.md`](docs/full_system_implementation.md).

## Status

This is an initial private release archive. The software/protocol release is present, but paper-submission readiness still depends on completing the confidential reviewer evidence bundle and resolving manuscript blockers documented outside this public repo.
