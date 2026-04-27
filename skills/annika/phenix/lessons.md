# Phenix Lessons Learned

## Environment
- `source <PHENIX_INSTALL>/phenix_env.sh` before any command
- Phenix binaries at `~/phenix-2.0/bin/` — not auto-detected by `which`; use `export PATH=~/phenix-2.0/bin:$PATH`
- **Don't `pkill ChimeraX` while Phenix is running** — on Mac, process group signals can cascade and kill Phenix child processes

## SS Restraints
- phenix.secondary_structure_restraints outputs helix_type = *unknown → ZERO H-bond restraints
- Must sed to *alpha: `sed 's/helix_type = alpha pi 3_10 \*unknown/helix_type = *alpha pi 3_10 unknown/g'`
- DNA SS: auto-detected base pairs usually correct; verify C1'-C1' ~10.4Å for WC

## Metal Restraints (.edits)
- Use refinement.geometry_restraints.edits { bond { } angle { } }
- Sigma strategy: tight (0.05) for close bonds, loose (0.15-0.20) for distant → tighten between rounds
- Literature distances: Zn-SG 2.33, Zn-NE2/ND1 2.05, Zn-OE 1.95, Mg-O 2.05-2.10

## Ligands
- Standard CCD: `phenix.elbow --chemical_component ADP --opt`
- eLBOW generates WRONG restraints for nucleotide monomers (treats as isolated small molecules: P-OP1=1.648 instead of 1.497, C3'-C2'=1.221 instead of 1.523, protonates phosphate oxygens)
- eLBOW auto-generates CIF restraints for PS residues (PST/GS/AS/SC) during RSR — saved in working dir, must pass to subsequent runs

## Q/N/H Flips
- Always run: `phenix.reduce -BUILD -FLIP model.pdb`, strip H after, re-refine

## Reference Models
- Crystal reference_model restraints HURT at >2.5Å EM (tested 1H7S, 1VYM, 4P7A — CC dropped)
- Only use if resolution < 2.5Å and same complex

## Refinement Strategy
- Iterative: Round 1 conservative → check metals → tighten sigma → Round 2
- Gentle pass: minimization_global only, macro_cycles=3 (no local_grid_search)
- NCS: auto-detected but not constrained by default — fine for most cases

## Sub-agent limitations
- Sub-agents for Phenix timed out (10min limit too short for eLBOW + 5 macro cycles on full model)
- Either increase timeout to 20min+ or run directly from main session

## Rebuilding
- For residues in wrong position: delete + rebuild with ideal geometry toward density center → refine

## Validation
- `phenix.molprobity model.pdb` for full analysis + Q/N/H flip suggestions
- `phenix.rotalyze` for rotamer outlier classification

## Local DNA Refinement
- For very small local DNA-only boxes, auto-weighting can overfit badly (CC rises but geometry collapses; clashscore >600). Treat as INVALID even if CC improves
- Stable rescue for tiny local DNA windows: strip H first (`phenix.pdbtools remove='element H'`), use explicit `weight=1`, run `minimization_global` with 1 macro-cycle + reference model restraint
- `refinement.target_start_weight` is NOT recognized in this Phenix RSR build; use top-level `weight=` instead

## Phosphorothioate DNA
- **Phenix RSR does not treat PS residues (PST/SC/AS/GS) as polymer DNA:** no cross-residue backbone restraints (O3'-P-O5' angles scatter 82-153°)
- PS residues connected as polymer create huge inter-residue distances (>50Å) after ideal B-DNA grafting. Fix: `pdb_interpretation.max_reasonable_bond_distance = 100`
- **Working workaround: mutate → refine → mutate back**
  1. Convert PS→standard DNA (PST→DT etc; SP/S2P→OP2, element→O)
  2. Run Phenix RSR with DNA base-pair/stacking restraints (angles converge ~103°)
  3. Convert back to PS names/atoms
  4. Run Servalcat to fix P-S distances
- eLBOW auto-generates CIF restraints for PS residues during RSR. Pass these .cif files to subsequent runs

## Reference Model for DNA
- Use `reference_group` to fix protein chains (A-E,H) with tight sigma=0.05, let DNA chains refine freely

## Operational
- **Phenix env path:** `source ~/phenix-2.0/phenix_env.sh` (NOT `/Applications/phenix-*/build/setpaths.sh` — doesn't exist on this machine)
- **Don't pkill ChimeraX while Phenix is running** — process group signals cascade on Mac
- **Sub-agents for Phenix:** 10min timeout too short for eLBOW + 5 macro cycles on full model. Use 20min+ or run from main session
- `phenix.metal_coordination model.pdb` auto-generates metal bond restraint edits (output: elbow.edits). Needs curation — includes spurious bonds to C atoms (CG, ND2). Bug in `output_angles=True` (dict_keys deletion error)

## New Notes (pending merge)
<!-- Append new tool discoveries here. Cleared after weekly merge. -->
