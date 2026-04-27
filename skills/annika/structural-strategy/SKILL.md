---
name: structural-strategy
description: Decision strategies for macromolecular structure building into cryo-EM maps. Use when deciding WHAT to do, in WHAT ORDER, and WHY — not how to run specific tools (that's chimerax/isolde/phenix/ccp4/emerald skills). Covers fitting, model building, refinement, validation, and special cases. Load when planning a structure-building task, choosing between approaches, or troubleshooting a stuck pipeline step.
---

# Structural Biology Strategy

Distilled decision-making knowledge for cryo-EM model building. This skill answers "what should I do next?" and "which approach works here?" — not "how do I run this command."

## How to use this skill

1. Read this file first — it has the decision trees and quick rules
2. Load a references/ file only when you need detailed strategy for a specific topic
3. After completing a project step, distill new strategies back into the appropriate references/ file

## Quick Decision Trees

### "I have a predicted model and a cryo-EM map. Now what?"

```
1. What resolution?
   ├─ <2.5Å → aggressive: full pipeline, expect near-atomic features
   ├─ 2.5-3.5Å → standard: pipeline works well, cautious with small features  
   └─ >3.5Å → conservative: ISOLDE essential, skip small-feature modeling

2. How many chains/domains?
   ├─ Single domain → rigid-body fit, skip domain segmentation
   ├─ Multi-domain, single chain → Merizo segmentation, per-domain fitting
   └─ Multi-chain complex → Merizo on each chain, careful with interfaces

3. Is it an AlphaFold/predicted model?
   ├─ Yes → expect register errors, domain orientations wrong, loops unreliable
   │        Trim low-pLDDT regions BEFORE fitting
   └─ No (experimental) → less trimming needed, but check for crystal packing artifacts
```

### "The fit looks wrong / metrics aren't improving"

```
1. Check map-model agreement first
   ├─ Global CC < 0.3 → fitting failed. Re-run with more rotation samples or manual placement
   ├─ CC 0.3-0.5 → partial fit. Some domains may be misplaced → per-domain fitting
   └─ CC > 0.5 → reasonable. Issues are local, not global

2. Identify the problem region
   ├─ Backbone register error → ISOLDE (physics-based correction)
   ├─ Sidechain wrong → rotamer fix protocol (swapaa → ISOLDE → gentle Phenix)
   ├─ Loop in wrong place → trim + rebuild, or ISOLDE with restraints released
   ├─ Domain orientation wrong → re-fit that domain specifically
   └─ Density is just bad → accept it, lower expectations for that region

3. Resolution-dependent expectations
   ├─ Rotamer outliers at >3Å → many are real, don't over-fix
   ├─ Waters at >2.5Å → don't model them
   ├─ Metal coordination at >3Å → geometry restraints essential (can't rely on density alone)
   └─ DNA/RNA at >3.5Å → backbone trace only, don't trust base orientations
```

### "Should I use ISOLDE or Coot for this fix?"

```
ISOLDE when:
  - Large backbone movements needed (>2Å shift)
  - Register errors (entire segment shifted)
  - Flexible regions that need physics-based relaxation
  - Low resolution (<3.5Å) where manual building is unreliable
  - Multiple simultaneous problems in one region

Coot when:
  - Single residue fixes (flip, rotamer change)
  - High resolution (<2.5Å) where density is unambiguous
  - Quick checks (real-space correlation per residue)
  - Experienced user who prefers manual control

Neither — just Phenix when:
  - Small geometry fixes (bond lengths, angles)
  - B-factor refinement needed
  - Final polishing after ISOLDE
```

### "Which refinement engine should I use?"

```
Cryo-EM workflow:
  ├─ Intermediate cleanup (between Coot/ISOLDE rounds)
  │   → Phenix real_space_refine
  │     (rotamer fitting, Ramachandran restraints, local geometry)
  │
  ├─ Final refinement for deposition
  │   → Servalcat refine_spa
  │     (half-map input, FSC weighting, B-factors, better statistics)
  │
  ├─ Geometry-only cleanup (no map needed)
  │   → Servalcat refine_geom
  │
  └─ B-factor refinement
      → Servalcat refine_spa (more robust than Phenix for this)

X-ray workflow:
  ├─ Standard refinement → Refmac5 or Phenix refine
  └─ Fine-grained control (TLS, twins, NCS) → Refmac5

Recommended cryo-EM pipeline:
  Coot edit → Phenix RSR (iterate) → Servalcat refine_spa (final) → validate → deposit
```

Execution note: this skill chooses the engine. When the chosen command is Refmac5, Servalcat, refmacat, AceDRG, or another CCP4 binary, load the `ccp4` skill to run it. When the chosen command is Rosetta EMERALD / GALigandDock with density, load the `emerald` skill to run it.

### "Do I need gemmi for this?"

```
gemmi is a general-purpose prep/inspection tool. Use it when:
  - Converting between mmCIF ↔ PDB formats
  - Inspecting/repairing cell/symmetry/header info
  - Slicing or querying maps
  - Quick residue-level queries on a structure
  - Any prep step that doesn't need a full refinement engine

No skill needed — CLI (gemmi --help) and Python API (import gemmi) are self-explanatory.
Available at: /opt/homebrew/bin/gemmi (Homebrew) + ~/ccp4-9/bin/gemmi (CCP4)
```

## Core Principles

1. **Always start with the best possible rigid-body fit.** Everything downstream depends on it. More rotation samples = better. Center model on map first.

2. **Work from large to small.** Global fit → domain fit → ISOLDE → sidechain → waters/ions. Never start fixing sidechains when the backbone is wrong.

3. **Preserve completeness.** Never extract domains and reassemble — you'll lose linkers. Fit copies, get transforms, apply back to the complete model.

4. **Resolution sets expectations.** At 3.3Å you won't get perfect rotamers. At 4Å you're doing backbone trace. Don't fight the data.

5. **Iterate, don't optimize in one shot.** Phenix round 1 → check → adjust restraints → round 2. ISOLDE 5min → check → ISOLDE 5min. Small steps.

6. **Validate continuously.** Don't wait until the end. Check CC, MolProbity, Ramachandran after every major step. Catch problems early.

7. **Know when to stop.** MolProbity < 2.0, Rama favored > 97%, clashscore < 10, CC_mask reasonable for resolution. Diminishing returns are real.

8. **Trust physics over statistics at low resolution.** ISOLDE's forcefield prevents impossible geometry. Phenix can over-fit at low resolution.

9. **Metals need explicit restraints.** Phenix won't get coordination geometry right without .edits files. Literature distances are your friend.

10. **Save everything, overwrite nothing.** model_N_description.cif. You will want to go back.

## Reference Files

| File | When to load | Content |
|---|---|---|
| references/fitting.md | Planning fitting strategy | Rigid-body, domain fitting, flexible fitting, convergence criteria |
| references/model-building.md | Building/modifying model components | DNA/RNA, ligands, metals, gap filling, loop building |
| references/refinement.md | Planning refinement rounds | Phenix strategy, restraint design, iterative approaches |
| references/validation.md | Assessing/improving quality | Metrics interpretation, fix protocols, when to stop |
| references/special-cases.md | Non-standard situations | Membrane proteins, glycans, heterogeneity, low resolution |
