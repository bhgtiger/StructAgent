---
name: structural_build
description: "Orchestrator for macromolecular structure building pipelines. Routes tasks to sub-skills (chimerax, isolde, phenix, ccp4, emerald) and tools (Merizo). Use when the user asks to build/refine a structure, fit a model into a map, or run a multi-step structural biology workflow. NOT for single-tool tasks — use chimerax/isolde/phenix/ccp4/emerald directly."
---

# Structural Build — Orchestrator

Routes multi-step structure determination workflows to the right sub-skill.

## Sub-skills

| Skill | Mode | Use for |
|-------|------|---------|
| **chimerax** | `--nogui` batch | Rigid-body fitting, editing, measurements, format conversion |
| **isolde** | GUI + REST | Flexible fitting (MDFF), local geometry fixes, ligand sim |
| **phenix** | CLI | Final refinement, validation, ligand restraints |
| **ccp4** | CLI | Refmac5, Servalcat, AceDRG, MTZ preflight, explicit CCP4 binaries |
| **emerald** | CLI | Rosetta EMERALD ligand docking into cryo-EM density |

## External Tools

| Tool | Location | Notes |
|------|----------|-------|
| **Merizo** | `<MERIZO_INSTALL>/` | Domain segmentation (any structure, no PAE needed) |
| **AlphaFold DB** | via ChimeraX `alphafold match` | Template retrieval |

## Task → Skill Routing

| Task | Skill |
|------|-------|
| Delete/mutate/renumber/combine | **chimerax** |
| Rigid-body fitting (fitmap), superposition | **chimerax** |
| Domain-wise rigid-body fitting | **chimerax** (standalone Python script) |
| Flexible fitting into map (MDFF) | **isolde** |
| Fix Ramachandran/rotamer outliers, pepflips | **isolde** |
| MDFF with ligands | **isolde** (see ligand pre-flight checklist) |
| Domain decomposition | **Merizo** |
| Final refinement (real-space, Phenix route) | **phenix** |
| Reciprocal-space refinement with Refmac5 | **ccp4** |
| Cryo-EM final refinement with Servalcat | **ccp4** |
| Cryo-EM ligand docking with Rosetta EMERALD | **emerald** |
| Ligand restraint generation (eLBOW) | **phenix** |
| Ligand restraint generation (AceDRG) | **ccp4** |
| Metal coordination restraints | **phenix** (.edits file) |
| SS restraints | **phenix** (with helix_type fix) |
| Q/N/H flip correction | **phenix** (reduce) |
| Validation (MolProbity) | **phenix** |

## Cryo-EM Pipeline (AlphaFold → Map)

```
1. Global rigid-body fitting          (ChimeraX --nogui)
   Center model on map → fitmap search 500 → local refine
   Quality gate: ≥60% atoms in density

2. Domain segmentation                (Merizo)
   --iterate → domain boundaries + NDR regions

3. Conservative trim                  (ChimeraX --nogui)
   Remove residues: unassigned by Merizo AND no density (0.5σ)

4. Domain-wise rigid-body fitting     (ChimeraX --nogui, Python script)
   Per-domain fitmap, capture model.position delta (NOT atom.coord!)
   Linker interpolation (SLERP + LERP), DNA local-only
   Never extract+reassemble — fit copies, apply transforms to complete model

5. ISOLDE flexible fitting (10 min)   (ChimeraX GUI + REST)
   Pre-flight: OP3/OXT delete, addh, map association, MDFF verify
   Internal Python timer (REST hangs during sim)
   Monitor ih.simulation_running every 30s

6. Post-ISOLDE cleanup block
   6a. Aggressive trim (chain ends + internal gaps ≥5)
   6b. Check for breaks → fill gaps from pre-trim model
   6c. ISOLDE touch-up (2-5 min) to relax filled regions

7. Ligand building (if applicable)
   7a. Place ligands from reference structures (superpose + extract)
   7b. ISOLDE with ligands (5 min) — full pre-flight checklist
       Fix ADP H-naming, delete OXT, check post-PRO HIS, set OpenCL
   7c. For cryo-EM small-molecule docking into density, run Rosetta EMERALD
       when no trustworthy transferred pose exists or multiple orientations remain plausible
   7d. Prepare restraint files: metal .edits, ligand .cif, SS .eff

8. Phenix real-space refinement       (Phenix CLI)
   Iterative: R1 conservative → check → tighten → R2
   Fix helix_type *unknown → *alpha
   Apply Q/N/H flips (reduce) between rounds
   Don't use crystal reference_model at >3Å

9. Validation                         (Phenix MolProbity)
   Targets: Rama <0.5%, favored >96%, rotamer <2%, clashscore <10

10. Rotamer outlier fix (if rotamer >2%)  (ChimeraX + ISOLDE + Phenix)
    Three-phase protocol — see "Rotamer Fix Protocol" section below.

11. Iterate or deposit
    Max 3 ISOLDE↔Phenix cycles before flagging

## Rotamer Fix Protocol

When rotamer outliers exceed ~2% after Phenix refinement, use this three-phase approach:

### Phase 1: Triage + Fix (ChimeraX --nogui or GUI, swapaa)

1. Run `phenix.rotalyze model.pdb` → list all OUTLIER residues
2. For each outlier, sample map density at side-chain atoms (skip N/CA/C/O):
   - `avg > 0.15` → **GOOD_DENSITY** (real conformation in density)
   - `0.05 < avg < 0.15` → **WEAK_DENSITY**
   - `avg < 0.05` → **NO_DENSITY**
3. Fix each outlier in ChimeraX with `swapaa`:
   - **GOOD_DENSITY:** `swapaa /<chain>:<res> <resname> criteria d` (density-fit best rotamer)
   - **WEAK_DENSITY:** `swapaa /<chain>:<res> <resname> criteria c` (chi-angle nearest allowed)
   - **NO_DENSITY:** `swapaa /<chain>:<res> <resname> criteria c` (common rotamer)
4. Save intermediate model

### Phase 2: Targeted ISOLDE (5 min, selection only)

1. Load rotamer-fixed model + map in ChimeraX GUI
2. Run full ISOLDE pre-flight (OP3, OXT, addh, map association, MDFF verify)
3. **Find Volume by type, not index** (see isolde skill rule 2b)
4. Select all outlier residues: `select #1 & (/<chain>:<res> ...)`
5. Expand selection: `select zone sel 5.5 #1 & protein`
6. Start sim on selection: `isolde sim start sel`
7. 5 min timer → stop + save (strip H first)

### Phase 3: Gentle Phenix cleanup

1. Run `phenix.real_space_refine` with:
   - `macro_cycles=3`
   - `run=minimization_global` only (NO `local_grid_search` — preserves ISOLDE improvements)
   - Keep SS, metal, ligand restraints active
2. This fixes Rama/Cβ regressions from ISOLDE dynamics without disturbing rotamers

### Expected results (at 3.3 Å)
- Rotamer outliers: 2.5% → ~1.0%
- Clashscore: improved
- Rama favored: maintained or improved
- MolProbity: significant improvement
```

## X-ray Pipeline

```
ChimeraX: open model + MTZ
  → ISOLDE: interactive refinement with live maps
  → Export to chosen refinement engine
  → Phenix: phenix.refine + validation
    OR
  → CCP4: MTZ preflight → Refmac5 + validation
```

## Quick Model Editing (no simulation)

```
ChimeraX only: delete, mutate, renumber, combine, addh, dockprep
```

## Data Flow

```
Input:
  model.cif          — AlphaFold/predicted model
  map.mrc            — CryoSPARC/RELION map

Intermediate (sequential numbering, NEVER overwrite):
  model_2_fitted.cif       → model_3_trimmed.cif
  → model_4_domainfit.cif  → model_5_isolde.cif
  → model_6_trimmed.cif    → model_7_gapfilled.cif
  → model_8_isolde.cif     → model_9_ligands.cif
  → model_10_isolde.cif    → model_N_phenix.pdb

Restraint files:
  ss.eff                   — SS restraints (helix_type fixed)
  metal_restraints.edits   — metal coordination
  ligand.cif               — from eLBOW

Key rule: Always save to NEW filename. ChimeraX caches files.
```

## Integration Notes

- ChimeraX ↔ ISOLDE share session via REST — model IDs consistent
- ISOLDE → Phenix: export `.eff` with self-reference torsions, disabled rotamer/rama/SS
- Refmac5, Servalcat, AceDRG, and MTZ preflight/inspection run through the `ccp4` skill
- Rosetta EMERALD density-guided ligand docking runs through the `emerald` skill
- Merizo runs in separate Python venv — output parsed by agent
- ISOLDE uses OpenMM templates (NOT Phenix .edits) — different restraint systems
- Metal restraints: ISOLDE handles via `metal_name_map`, Phenix via `.edits` file
