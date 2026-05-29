# StructAgent

StructAgent is a two-agent structural-biology assistant system for cryo-EM model building, refinement, validation, ligand fitting, and ion-site audit workflows.

## Citation

If you use StructAgent in your research, please cite the accompanying preprint:

> Guo, X. *et al.* StructAgent: a two-agent system for cryo-EM structural biology. *bioRxiv* (2026). doi:[10.64898/2026.05.18.725842](https://doi.org/10.64898/2026.05.18.725842)

Preprint: https://www.biorxiv.org/content/10.64898/2026.05.18.725842v1

BibTeX:

```bibtex
@article{structagent2026,
  title   = {StructAgent: a two-agent system for cryo-EM structural biology},
  author  = {Guo, Xiaohu and others},
  journal = {bioRxiv},
  year    = {2026},
  doi     = {10.64898/2026.05.18.725842},
  url     = {https://www.biorxiv.org/content/10.64898/2026.05.18.725842v1}
}
```

This release contains two usable layers:

1. **Complete agent system** — an Annika/Maria/A2A architecture for separating scientific reasoning from execution control.
2. **Skills-only mode** — install the released skill protocols into any compatible OpenClaw-style agent and use them without running the full multi-agent system.

The public repository intentionally excludes private identities, tokens, chat routing configuration, raw session logs, and example structural datasets. Reviewer-only evidence bundles are tracked separately.

## Third-party software notice

StructAgent is independent and unofficial. It is not affiliated with, endorsed by, sponsored by, or approved by the developers or owners of the third-party scientific software it can help orchestrate. Product names and trademarks belong to their respective owners. Users must obtain and comply with all upstream software licenses, documentation terms, and citation requirements. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Repository layout

```text
architecture/                 System architecture and collaboration protocol
docs/                         Installation, implementation, privacy, versions, MCP setup, release scope
scripts/                      Sanitized helper templates for A2A messaging/setup
skills/annika/                Execution-side structural-biology skills/protocols
  ├── ccp4/                   Refmac5, AceDRG, CCP4 suite orchestration
  ├── chimerax/               UCSF ChimeraX model editing and map fitting
  ├── coot/                   Coot model building and local refinement
  ├── cryosparc/              AI agent skill for cryoSPARC workflows, masks, and cautious automation
  ├── emerald/                Rosetta EMERALD ligand docking into cryo-EM density (NEW)
  ├── isolde/                 ISOLDE interactive refinement in ChimeraX
  ├── phenix/                 Phenix real-space and reciprocal-space refinement
  ├── annika-log/             Auditable project/job logging for reproducibility (NEW)
  ├── structural-strategy/    Decision-making for fitting, refinement, validation
  └── structural_build/       End-to-end model building orchestration
skills/maria/                 Reading/reasoning/database/review skills
  ├── database/               Literature database query and cross-reference
  ├── discovery/              Gap-driven literature expansion via Semantic Scholar
  ├── distill/                Session distillation
  ├── paper-reader/           Primary paper reading and filing
  └── review-paper/           Review/tutorial paper reading
examples/                     Placeholder and reviewer-bundle notes only
reviewer_bundle_manifest.md   What belongs in the confidential reviewer bundle
LICENSE                       Apache-2.0 for original StructAgent material
THIRD_PARTY_NOTICES.md        Unofficial status, trademarks, upstream-license notice
```

## Quick start

### Option A — use only the skills

Copy selected folders under `skills/annika/` or `skills/maria/` into your agent's `skills/` directory, restart/rescan the agent, then invoke tasks that match the skill names.

See [`docs/skills_only_usage.md`](docs/skills_only_usage.md). For a worked Claude/Codex-style implementation example, see [`docs/cryosparc_skill_example/`](docs/cryosparc_skill_example/).

### Option B — implement the full StructAgent system

Create two agents:

- **Maria** — domain reasoning, paper reading, literature/database synthesis, scientific critique.
- **Annika** — structural-biology execution, tool orchestration, run logging, metric capture, recovery.

Connect them with an A2A JSON-RPC gateway or equivalent message bus. Use the templates in `scripts/` and the protocol in `architecture/collaboration_protocol.md`.

See [`docs/full_system_implementation.md`](docs/full_system_implementation.md). Optional public PDB/PDBe lookup tools can be exposed via [`docs/pdbe_mcp_setup.md`](docs/pdbe_mcp_setup.md).

## Changelog

### v4 (2026-05-29)
- **Updated** `skills/annika/cryosparc/` to the current v5.0.6-aware skill bundle, including expanded SPA playbooks, case-study/tutorial routing, integrated ChimeraX mask-generation guidance, small mask assets, and file-local mask helper scripts under `scripts/masks/`.
- **Added** `docs/pdbe_mcp_setup.md` — optional PDBe API/Search MCP configuration for StructAgent-style Maria/Annika deployments using `pdbe-mcp-server --transport stdio`; graph server remains out of scope unless a local PDBe-KB Neo4j deployment is provided.

### v3 (2026-05-22)
- **Added** `skills/annika/cryosparc/` — self-contained, unofficial cryoSPARC SPA advisor/automation skill covering import, preprocessing, picking, 2D/3D workflows, refinement, 3DVA/3DFlex, masks, helical processing, CryoSPARC Live, `cryosparc-tools`, `cryosparcm`, GPU lanes/queues, storage, RELION interop, troubleshooting, and error lookup. Includes synthesized workflow references and a dry-run-first `scripts/cryosparc_harness.py` helper for cautious local automation.
- **Added** `docs/cryosparc_skill_example/` — sanitized public usage page showing the unofficial AI agent skill for cryoSPARC as a Claude/Codex-style implementation pattern that can also be adapted to other agent runtimes.

### v2 (2026-05-18)
- **Added** `skills/annika/emerald/` — Rosetta EMERALD ligand docking into cryo-EM density maps (GALigandDock + density-weighted scoring). Includes wrapper scripts, presets, CLI reference, and installation guide.
- **Added** `skills/annika/annika-log/` — auditable project/job folder discipline. Provides canonical logging layout, error/lesson export for Supp. Table 3, integrity auditing, and paper-traceability mapping.
- Updated repository layout documentation.

### v1 (2025-05-18)
- Initial release with core structural-biology skills (ChimeraX, Coot, CCP4, ISOLDE, Phenix, structural-strategy, structural_build) and literature skills (database, discovery, distill, paper-reader, review-paper).

## Status

Active development. The software/protocol release is present and expanding as new tool integrations are validated. Paper-submission readiness depends on completing the confidential reviewer evidence bundle.
