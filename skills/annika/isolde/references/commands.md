# ISOLDE Command Reference

## Table of Contents
1. [Session Management](#session-management)
2. [Simulation Control](#simulation-control)
3. [Restraints — Adaptive Distances](#restraints--adaptive-distances)
4. [Restraints — Adaptive Torsions](#restraints--adaptive-torsions)
5. [Release & Adjust Restraints](#release--adjust-restraints)
6. [Peptide Manipulation](#peptide-manipulation)
7. [Residue & Chain Management](#residue--chain-management)
8. [Navigation](#navigation)
9. [Ligand Parameterization](#ligand-parameterization)
10. [NCS Restraints](#ncs-restraints)
11. [Export for Refinement](#export-for-refinement)
12. [Assessment Commands](#assessment-commands)
13. [Timeout Guidance](#timeout-guidance)

---

## Session Management

| Command | Description |
|---------|-------------|
| `isolde start` | Launch ISOLDE GUI (required before any ISOLDE command) |
| `isolde select #N` | Set model #N as the working model |
| `isolde set temperature T` | Set simulation temperature (default 100K) |
| `isolde set timeStepsPerGuiUpdate N` | Simulation speed vs responsiveness |
| `isolde shorthand` | Enable short aliases (ss, pf, cf, etc.) |

---

## Simulation Control

| Command | Description |
|---------|-------------|
| `isolde sim start` | Start sim on entire selected model |
| `isolde sim start sel` | Start sim on current selection only |
| `isolde sim start #1/A:50-150` | Start sim on specific residues |
| `isolde sim stop` | Stop sim, keep current coordinates |
| `isolde sim stop discardTo checkpoint` | Stop and revert to last checkpoint |
| `isolde sim stop discardTo start` | Stop and revert to starting state |
| `isolde sim pause` / `resume` | Pause/resume simulation |
| `isolde sim checkpoint` | Save checkpoint (for revert) |

**Default simulation timeout: 600s (10 min).** CPU-only OpenMM on Apple Silicon needs this minimum.

**Auto-checkpoint rule:** Always `isolde sim checkpoint` before major operations.

---

## Restraints — Adaptive Distances

```bash
# Self-restraint (own geometry)
isolde restrain distances #1/A

# AlphaFold template with PAE confidence
isolde restrain distances #1 templateAtoms #2 adjustForConfidence true

# Domain-specific
isolde restrain distances #1/A:19-156 templateAtoms #2/A:19-156 adjustForConfidence true
```

Key parameters: `distanceCutoff 8.0`, `kappa 10.0`, `wellHalfWidth 0.1`, `tolerance 0.025`, `fallOff 2.0`, `perChain true`.

**Domain workflow guidance:**
- Well-fit domains (displacement < 1× resolution): full PAE-adjusted restraints
- Displaced domains: PAE-adjusted (weaker inter-domain handled by PAE)
- NDR/linker regions: **no distance restraints** — let MDFF pull into density

---

## Restraints — Adaptive Torsions

```bash
isolde restrain torsions #1/A templateResidues #2/A adjustForConfidence true
# Backbone only:
isolde restrain torsions #1/A templateResidues #2/A sidechains false
```

Parameters: `angleRange 60.0`, `springConstant 250.0`, `identicalSidechainsOnly true`.

---

## Release & Adjust Restraints

```bash
isolde release distances #1/A:100-200
isolde release torsions #1/A:100-200
isolde release distances #1 strainedOnly true stretchLimit 1.5
isolde release distances #1 longerThan 6.0
isolde adjust distances #1/A kappa 5.0
isolde adjust torsions #1/A springConstant 100
isolde adjust distances #1/A displayThreshold 0.1
```

---

## Peptide Manipulation

```bash
isolde pepflip #1/A:42     # Flip peptide bond N-terminal to residue 42
isolde cisflip #1/A:42     # Toggle cis↔trans
```

Auto-starts local sim if none running.

---

## Residue & Chain Management

```bash
isolde ignore #1/B          # Exclude chain B from simulations
isolde ~ignore #1/B         # Re-include
isolde modify his #1/A:57 ND  # His protonation (ND/NE/both)
isolde adjust bfactors 5.0 #1/A
isolde add water             # At centre of rotation
isolde add ligand ATP
isolde add aa ALA sel        # Add to selected terminal
```

---

## Navigation

```bash
isolde stepto #1/A:42   # Focus on residue
isolde stepto next/prev  # Step through residues
isolde jumpto next       # Jump to next chain
```

---

## Ligand Parameterization

```bash
isolde parameterise #1/A:501   # GAFF2/ANTECHAMBER
```

Time scales roughly as (atoms)^3; large ligands may take over an hour. Only C, N, O, S, P, H, F, Cl, Br, I are supported, and hydrogens must be correct. The documented route excludes ligands covalently bonded to other residues. It writes `{resname}.xml`, loads it for the current session, and requires reloading in later sessions via the GUI residue-parameter loader. Use `netCharge` when the inferred charge is demonstrably wrong; `override true` replaces existing parameterization. The 1.12 release notes also announce `isolde load parameters`; inspect installed help before generating its arguments because the fetched command page does not document its full syntax.

---

## NCS Restraints

For homo-multimers: NCS ON by default (prevents identical chains from diverging).

NCS is managed through ISOLDE's GUI Restraints tab or building module.

**Relax NCS when:** different ligand binding states across chains, known asymmetry at interfaces.

---

## Export for Refinement

```bash
# Cryo-EM → Phenix real-space
isolde write phenixRsrInput #1 3.5 #2
# Args: model_id, resolution, map_id
# Optional: modelFileName, paramFileName, restrainPositions true, includeHydrogens true

# X-ray → Phenix reciprocal-space
isolde write phenixRefineInput #1
# Optional: numProcessors N, numMacrocycles 6, nqhFlips true

# Refmac
isolde write refmacRestraints #1
```

ISOLDE export uses model as its own reference for torsion restraints, disables rotamer/rama/SS restraints in Phenix. Goal: subtle tightening of bonds/angles while maintaining overall geometry.

---

## Assessment Commands

```bash
# Map-model correlation
measure correlation #1 inMap #2

# Per-atom density
measure mapvalues #2 atoms #1 attribute density_value

# Ramachandran validation
rama #1 report true
# → Clustered outliers in one region = that region needs work

# Rotamer validation
rota #1 report true

# Check simulation status
python3 -c "print(session.isolde.simulation_running)"
```

---

## Timeout Guidance

| Operation | Default timeout | Notes |
|-----------|----------------|-------|
| ChimeraX launch + REST | 60s | Poll every 2s |
| `isolde start` | 30s | First-time init slow |
| `isolde sim start` (local) | 30s start, 600s run | 10 min min for CPU convergence |
| `isolde sim start` (full model) | 60s start, 600-1800s run | Large = 15-30 min |
| `fitmap` (local) | 30s | |
| `fitmap search 50` | 120s | Per domain |
| `isolde parameterise` | 60-3600s | Scales as (atoms)^3 |
| Merizo | 1-10s | Fast on CPU |
| `isolde write` | 30s | |

## Current release preflight and tutorials

Official [Toolshed release history](https://cxtoolshed.rbvi.ucsf.edu/apps/chimeraxisolde), checked 2026-09-07: **1.12.1 macOS (4 September)** fixes missing preflight/validation commands in the macOS 1.12.0 wheel. **1.12.0 Linux/Windows (26 June)** and 1.12.1 macOS require **ChimeraX 1.12.x**. The online manual still labels itself 1.12.0. Check the installed platform-specific bundle; a GitHub Releases list is empty and cannot substitute for Toolshed history.

Before simulation, the [documented command interface](https://tristanic.github.io/isolde/static/isolde/doc/commands/isolde.html) supports:

```chimerax
isolde status
isolde preflight hydrogens #1
isolde preflight parameters #1
isolde preflight disulfides #1
isolde preflight altlocs #1
```

Use hydrogen recommendations and unmatched/ambiguous residue details to target repairs, then repeat preflight. Parameter checks do not create an OpenMM Context; readiness does not test the GPU or map forces. Disulfide/altloc checks change acknowledgment flags to suppress their dialogs but do not edit atoms. Resolve the reported choices before simulation; avoid automatically accepting all GUI warnings.

For geometry reports use `isolde validate peptidebonds #1`, `isolde validate rama #1`, `isolde validate rotamers #1`, and `isolde validate clashes #1`. Each supports `saveFile /path/report.json`; inline `limit` does not truncate the saved report. Compare before/after geometry alongside map fit, and preserve unexpected-stop outcomes as failures even if coordinates could be saved.

For **map association**, follow [Getting Started](https://tristanic.github.io/isolde/static/isolde/doc/tools/gui/getting_started.html): rigid-fit before ISOLDE model initialization, then `clipper associate #2 to #1` for map #2 and model #1. If fitting after initialization is necessary, local `fitmap ... moveWholeMolecules false` updates atoms without adding a model transform. Verify both existing MDFF flags before sim start. The older private Clipper API is a fallback requiring installed-version inspection.

For **AlphaFold multimer models with domain disagreement**, use the official [multimer cryo-EM tutorial](https://tristanic.github.io/isolde/static/isolde/doc/tutorials/alphafold/multimer/alphafold_multimer_cryoem.html): inspect inter-domain confidence, place domains, and tune restraints to allow justified movement. The [tutorial index](https://tristanic.github.io/isolde/static/isolde/doc/tools/ISOLDE.html#tutorials) marks Bulk Flexible Fitting superseded; use its current AlphaFold routes for new modelling work. Tutorials were read, not executed in this refresh.
