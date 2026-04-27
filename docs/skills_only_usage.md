# Skills-only usage

You can use StructAgent without running the two-agent Maria/Annika system.

## Install

Copy one or more skill folders into your agent's skill directory.

```bash
# Example
cp -R skills/annika/chimerax ~/.openclaw/workspace/skills/
cp -R skills/annika/phenix ~/.openclaw/workspace/skills/
cp -R skills/maria/paper-reader ~/.openclaw/workspace/skills/
```

Restart or rescan your agent so it indexes the skills.

## Recommended bundles

### Cryo-EM model building / refinement

- `skills/annika/chimerax`
- `skills/annika/isolde`
- `skills/annika/phenix`
- `skills/annika/coot`
- `skills/annika/ccp4`
- `skills/annika/structural_build`
- `skills/annika/structural-strategy`

### Ligand fitting and geometry review

- `skills/annika/chimerax`
- `skills/annika/isolde`
- `skills/annika/phenix`
- `skills/annika/coot`
- `skills/annika/structural_build`

### Ion audit / validation

- `skills/annika/phenix`
- `skills/annika/ccp4`
- `skills/annika/structural-strategy`

### Paper reading / knowledge base

- `skills/maria/paper-reader`
- `skills/maria/database`
- `skills/maria/discovery`
- `skills/maria/review-paper`
- `skills/maria/distill`

## Usage pattern

Ask your agent in plain language. Example:

```text
Use the PHENIX and ChimeraX skills to validate this model against this cryo-EM map. Report command lines, versions, CC, geometry outliers, and whether the result is publishable.
```

For paper reading:

```text
Use the paper-reader and database skills to digest this PDF, file it under my ligand-fitting project, and list methods relevant to pterin-like ligands.
```

## Limits

Skills-only mode gives you protocols and tool-use habits. It does not provide the full StructAgent division of labor, A2A routing, cross-agent review, or automatic provenance enforcement unless your host agent implements those behaviors.
