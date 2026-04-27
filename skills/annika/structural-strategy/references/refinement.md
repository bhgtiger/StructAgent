# Refinement Strategies

Execution note: this file is for strategy only. When you choose Refmac5, Servalcat, refmacat, AceDRG, freerflag, mtzdump, or other CCP4 binaries, execute them via the `ccp4` skill.

## Phenix Real-Space Refinement

### Standard command
```bash
phenix.real_space_refine model.pdb map.mrc resolution=X.X \
  scattering_table=electron macro_cycles=5 \
  run=minimization_global+local_grid_search \
  secondary_structure.enabled=True \
  ss_restraints.eff metal_restraints.edits ligand.cif nproc=4
```

### Iterative approach (ALWAYS do this)
1. **Round 1:** Conservative — standard settings, check output
2. **Check:** Metal distances, Ramachandran, rotamer outliers, CC
3. **Adjust:** Tighten metal sigma if bonds improved, fix obvious problems
4. **Round 2:** With tightened restraints
5. **Repeat** until metrics plateau (usually 2-3 rounds)

### When to use which run modes
- `minimization_global+local_grid_search` — standard, most cases
- `minimization_global` only — gentle pass (after ISOLDE, when you don't want to undo ISOLDE's work)
- Add `adp` for B-factor refinement (helps at <3Å)

- For ligand-containing EM models, make ADP explicit (`refinement.run=minimization_global+local_grid_search+adp`) or ligand B-factors may remain frozen at ISOLDE defaults and create false LIG/shell B-factor artefacts.
- For ligands at EM resolution, include ADP explicitly: `refinement.run=minimization_global+local_grid_search+adp`. Without `+adp`, ligand B-factors can stay frozen at ISOLDE defaults and produce misleading ligand/shell B-factor ratios.

### Auto-generating metal restraints
- `phenix.metal_coordination model.pdb` auto-generates metal bond restraint edits (output: `elbow.edits`)
- **Needs curation** — includes spurious bonds to carbon atoms (CG, ND2); bug in `output_angles=True` (dict_keys deletion error)
- Use as starting point, then manually remove incorrect entries

### Restraint design
- **Metal restraints:** start loose (sigma 0.15-0.20) for distant ligands, tighten (0.05) as they converge. σ=0.02 forces ideal geometry (all 12 bonds converged to RMSD 0.012Å in test)
- **SS restraints:** always enable, but fix helix_type bug (sed *unknown → *alpha)
- **Reference model:** DON'T use crystal reference at >2.5Å EM — conformations too different
- **Reference model for DNA-only:** use `reference_group` to fix protein chains with tight sigma=0.05, let DNA chains refine freely
- **NCS:** auto-detected, usually fine without explicit constraints

- For planar ligand rings at EM resolution, tighten planarity via `.eff` edits (`geometry_restraints.edits.planarity`, sigma=0.02) rather than modifying CIF esds. This cleans deposition geometry (e.g. ring planarity RMSD ~0.13–0.15 → 0.005–0.008 Å) but usually does not improve local CC at ~3 Å.

### Phenix weight parameter
- `refinement.target_start_weight` is NOT recognized in current Phenix RSR build; use top-level `weight=` instead
- Tested values with tight metal restraints: w=0.5/1.0/2.0 — w=2.0 gave best CC_mask (0.728) and clashscore (29.58). Higher weight = more map fitting
- For very small local DNA-only boxes, auto-weighting can overfit badly (CC rises but geometry collapses, clashscore >600) — treat as invalid even if CC improves

### Stable rescue for tiny local DNA windows
- Strip H first (`phenix.pdbtools remove='element H'`)
- Use explicit `weight=1`, `minimization_global` with 1 macro-cycle + reference model restraint

## Post-Refinement

### Q/N/H flips
- Always check: `phenix.reduce -BUILD -FLIP model.pdb`
- Strip hydrogens after, re-refine
- Can change several residues per structure

### Rotamer outlier fix (3-phase protocol)
1. **Classify:** `phenix.rotalyze` → GOOD/WEAK/NO density per outlier
2. **Fix:** ChimeraX `swapaa criteria d` (good density) or `criteria c` (weak/no)
3. **Relax:** Targeted ISOLDE 5min on outlier residues + 5.5Å zone
4. **Polish:** Gentle Phenix (minimization_global only, macro_cycles=3)

- After an ADP-enabled RSR pass, expect rotamer outlier creep of ~1–2%. Do a short follow-up (`refinement.run=minimization_global+local_grid_search+adp`, `rotamers.tuneup=outliers`, `rotamers.fit=outliers`, `macro_cycles=3`) before finalizing; FTCD improved outliers 3.09→1.72% and clashscore 7.49→5.82 with per-ligand CC drift <0.005.

### Post-ADP rotamer tuneup
ADP refinement can loosen side-chain geometry by ~1–2% rotamer outliers. Before declaring final, run a short follow-up pass with ADP still enabled:

```bash
phenix.real_space_refine model.pdb map.mrc resolution=X.X \
  refinement.run=minimization_global+local_grid_search+adp \
  rotamers.tuneup=outliers rotamers.fit=outliers macro_cycles=3
```

This usually recovers rotamer statistics without moving ligands materially (per-ligand CC drift should stay <0.005).

### Planarity restraint tightening
For aromatic/heterocyclic ligand rings at EM resolution, use reproducible `.eff` planarity edits instead of modifying CIF distances. `geometry_restraints.edits.planarity { action=add ... sigma=0.02 }` blocks can reduce ring planarity RMSD from ~0.13–0.15 Å to ~0.005–0.008 Å in one RSR pass. This cleans deposition geometry metrics; it usually does not improve local CC when the map resolution is the limiting factor.

### Refmac / Servalcat external restraints caveat
Refmac5 `EXTE ANGL` is incompatible with Servalcat nonpolymer chain renaming in tested builds (Refmac 5.8.0431 / Servalcat 0.4.126). Servalcat can rename nonpolymer chains to underscore forms (e.g. `3_p`, `3_1`), which Refmac's user-injected `EXTE ANGL` parser cannot reference. `EXTE DIST` can still work because Servalcat generates those in its internal format. `EXTE FAIL OFF` was also not recognized in this build despite documentation, so do not rely on it.

For structures with many nonpolymer chains, prefer `--prepare_only` plus manual Refmac inspection/editing. Directly injecting curated `EXTE DIST` lines into the `.inp` can work after stripping `resi >= 10000`, but user-injected `EXTE ANGL` lines remain unreliable.

### HOLE channel analysis
HOLE 2.3.2 is installed at `~/tools/hole2/hole2-2.3.2/` with radii file `rad/simple.rad`. For channeling/intermediate claims, two independent seedings (e.g. midpoint and site-centroid) converging on the same waist residues support a real constriction rather than a sampling artefact.

### Expected results by resolution
| Resolution | CC_mask | MolProbity | Rama favored | Clashscore |
|---|---|---|---|---|
| <2.5Å | >0.75 | <1.5 | >98% | <5 |
| 2.5-3.5Å | >0.55 | <2.0 | >97% | <10 |
| 3.5-4.5Å | >0.40 | <2.5 | >95% | <15 |
| >4.5Å | >0.30 | variable | >93% | variable |

## Servalcat (CCP4, cryo-EM preferred; run via `ccp4` skill)

### When to use
- **Cryo-EM final refinement** — Servalcat `refine_spa` is preferred over raw Refmac for SPA because it handles half-map input, FSC-based weighting, B-factor estimation, and sharpened map output automatically
- **Geometry-only cleanup** — `refine_geom` runs Refmac without a map to fix clashes/outliers; good as a quick post-Coot pass
- **Map calculation** — `fofc` for Fo-Fc difference maps from half-maps; `fsc` for map-model FSC; `localcc` for local correlation

### Standard cryo-EM command
```bash
source ~/ccp4-9/bin/ccp4.setup-sh
servalcat refine_spa \
  --model model.cif \
  --halfmaps half1.mrc half2.mrc \
  --resolution X.X \
  --ncycle 10
```

### Servalcat vs Phenix RSR — complementary, not competing
| Situation | Better choice |
|-----------|--------------|
| Final refinement for deposition | **Servalcat** — better statistics, FSC curves |
| Intermediate cleanup after Coot/ISOLDE | **Phenix RSR** — better at local geometry fixes, rotamer fitting |
| Rotamer/sidechain correction | **Phenix RSR** — built-in rotamer fitting |
| B-factor refinement | **Servalcat** — more robust |
| X-ray crystallography | **Raw Refmac** or **Phenix refine** |

### External helper hierarchy (for Coot workflows)
| Tool | Use case |
|------|----------|
| **Servalcat `refine_spa`** | Cryo-EM final refinement (preferred over raw Refmac for SPA) |
| **Phenix RSR** | Intermediate cleanup rounds between Coot edits |
| **Raw Refmac** | X-ray or fine-grained control |
| **Servalcat `refine_geom`** | Geometry-only cleanup (no map) |

### Recommended cryo-EM pipeline
```
Coot edit → Phenix RSR (intermediate cleanup) → iterate
   ...when happy...
→ Servalcat refine_spa (final) → validate → deposit
```

### Utility subcommands
- `servalcat fofc` — Fo-Fc difference maps from half-maps
- `servalcat fsc` — map-model FSC calculation
- `servalcat localcc` — local correlation maps
- `servalcat trim` — map trimming/boxing
- `servalcat shiftback` — origin shift correction (common cryo-EM issue)
- `servalcat refine_geom` — geometry-only refinement (no map)

## When to Stop Refining

1. CC_mask has plateaued (not improving between rounds)
2. MolProbity score < 2.0
3. Ramachandran favored > 97%
4. No more obvious density mismatches visible
5. Remaining outliers are likely real (verified by density inspection)
6. You've done 3+ rounds and gains are <0.5% per round

**Diminishing returns are real.** A perfect MolProbity score at 3.3Å resolution is suspicious, not impressive.

## Job Pipeline Convention
- Use `job_N_tool_action/` folders with `Run_setting_log.md` + `bug_fix.md`
- Project-level `PIPELINE.md` tracks overall progress
- See `conventions/job_pipeline.md` for full spec
