---
name: phenix
description: "Run Phenix crystallography and cryo-EM refinement workflows via CLI. Two separate lanes: (1) phenix.refine for X-ray reciprocal-space refinement, (2) phenix.real_space_refine for cryo-EM real-space refinement. Also covers ligand restraint generation (eLBOW), model prep (ready_set/reduce), metal coordination restraints, SS restraints, Q/N/H flip correction, and post-refinement validation (MolProbity). Use when the user asks to refine a structure, run Phenix, validate geometry, or automate crystallographic/cryo-EM structure determination workflows."
---

# Phenix Refinement Skill

Two strictly separate lanes. Never mix them.

## Prerequisites

```bash
PHENIX_ENV_SH=$(ls -1d /Applications/phenix-*/build/setpaths.sh 2>/dev/null | sort -V | tail -1)
# or: source <PHENIX_INSTALL>/phenix_env.sh
source "$PHENIX_ENV_SH"
```

## Lane A: X-ray Refinement

**Input:** model (PDB/mmCIF) + diffraction data (MTZ)

```bash
phenix.refine model.pdb data.mtz strategy=individual_sites+individual_adp \
  main.number_of_macro_cycles=3 nproc=4
```

Key params: `--strategy`, `--macro-cycles`, `--nproc`, `--ordered-solvent`, `--labels` + `--rfree-label` (always specify), `--ligands`.

Outputs: `_refine_001.pdb/.mtz/.log`. Key metrics: **Rwork / Rfree**.

---

## Lane B: Cryo-EM Real-Space Refinement

**Input:** model (PDB/mmCIF) + map (MRC/CCP4) + resolution

```bash
phenix.real_space_refine model.pdb map.mrc resolution=3.3 \
  scattering_table=electron macro_cycles=5 \
  run=minimization_global+local_grid_search \
  secondary_structure.enabled=True \
  ss.eff metal.edits ligand.cif nproc=4
```

`--resolution` is **required** for MRC/CCP4 maps. `scattering_table=electron` always enforced.

Outputs: `.pdb/.log/.geo/.eff`. Key metrics: Ramachandran, rotamer outliers, bond/angle RMSD, CC_mask.

## Critical Lessons (from experience)

### SS Restraints: helix_type Bug

`phenix.secondary_structure_restraints` outputs `helix_type = *unknown` → generates **ZERO** H-bond restraints for helices.

**Must fix:**
```bash
phenix.secondary_structure_restraints model.pdb format=phenix | \
  sed 's/helix_type = alpha pi 3_10 \*unknown/helix_type = *alpha pi 3_10 unknown/g' > ss.eff
```

### Metal Coordination Restraints (.edits)

```
refinement.geometry_restraints.edits {
  bond {
    atom_selection_1 = chain D and resname HIS and resid 701 and name NE2
    atom_selection_2 = chain H and resname ZN and resid 5 and name ZN
    distance_ideal = 2.05
    sigma = 0.05
  }
  angle {
    atom_selection_1 = ...
    atom_selection_2 = ... (central metal)
    atom_selection_3 = ...
    angle_ideal = 109.5
    sigma = 5.0
  }
}
```

**Sigma strategy:** Start loose (0.15–0.20) for distant bonds, tight (0.05) for close ones. Tighten between rounds as ligands move closer.

**Literature distances:**
| Bond | Distance (Å) |
|------|--------------|
| Zn–SG (CYS) | 2.33 |
| Zn–NE2/ND1 (HIS) | 2.05 |
| Zn–OE (GLU) | 1.95 |
| Mg–O | 2.05–2.10 |

### Crystal Reference Models — Don't Use at Low Resolution

Using crystal structures as `reference_model` restraints for ≥3 Å EM maps makes things WORSE. Crystal conformations too different from EM complex. CC dropped from 0.604 to 0.593.

**Rule:** Only use reference_model for same complex at better resolution, or resolution < 2.5 Å.

### Q/N/H Flips — Always Run

```bash
phenix.reduce -BUILD -FLIP model.pdb > flipped.pdb 2> flips.log
# Strip H (Phenix adds its own during refinement)
phenix.pdbtools flipped.pdb remove="element H" output.file_name=noH.pdb
```

Flips are almost always correct. Apply after first refinement round.

### DNA SS Restraints

Auto-detected base pairs and stacking are usually correct. Verify C1'–C1' distances (~10.4 Å for WC). Stacking gaps = kink points — don't force stacking there.

### Iterative Approach (recommended)

1. **Round 1:** Conservative — SS + metal + ligand restraints, loose sigma
2. **Check:** Metal distances, density fit, geometry
3. **Tighten:** Sigma where bonds improved
4. **Round 2:** Tightened restraints
5. **Q/N/H flips:** reduce → strip H → re-refine
6. Don't try to do everything in one shot

### Rebuilding Residues

For residues in completely wrong positions: delete, rebuild with ideal geometry pointing toward density center, let Phenix refine. Works well for terminal residues.

## Ligand Workflow

```bash
phenix.elbow --chemical_component ADP --opt  # Standard CCD ligand
phenix.elbow ligand.sdf --residue=LIG --output=lig  # Custom ligand
phenix.ready_set model.pdb  # Add H + ligand CIFs + metal edits
```

Supply CIFs to refinement as positional arguments: `phenix.real_space_refine model.pdb map.mrc lig.cif resolution=3.3`

### Cryo-EM ligand fitting caveat

`phenix.ligandfit` is primarily an X-ray tool and expects MTZ reflection data, not CCP4/MRC maps. Converting large cryo-EM maps with `phenix.map_to_structure_factors` can create huge MTZs and stall; boxed MTZ workflows can still place ligands in the wrong density and require origin-shift correction. For cryo-EM ligand refitting, prefer reference transfer by structural superposition followed by Phenix RSR when a homologous ligand structure exists.

### Ligand refinement / validation details

- `phenix.real_space_refine run=all` is invalid in this build. Omit `run=` for defaults, or specify valid components explicitly.
- For ligand B-factors, include ADP explicitly: `refinement.run=minimization_global+local_grid_search+adp`.
- For ring planarity cleanup, pass `.eff` planarity edits (`geometry_restraints.edits.planarity`) instead of modifying the ligand CIF.
- `phenix.pdb_interpretation model.pdb restraints.cif write_geo=True` writes a `.geo` file; grep ligand names to inspect ligand-specific bond/angle deviations.
- `phenix.map_correlations model.pdb map.map resolution=X` reports per-residue CC including ligands. `phenix.map_model_cc` is deprecated and requires `--force`.

## Validation

```bash
phenix.molprobity model.pdb                              # Geometry
phenix.validation_cryoem model.pdb map.mrc resolution=3.3  # Cryo-EM comprehensive
phenix.mtriage map.mrc model.pdb                         # Map quality
```

Notes:
- `phenix.validation_cryoem` can fail on custom ligands unless the ligand CIF is passed as a positional argument.
- `phenix.mtriage` half-map jobs are most robust via an `.eff` file with fully qualified `map_model.full_map`, two `map_model.half_map` entries, `map_model.model`, `resolution`, and `scattering_table=electron`. Bare `half_map_1=` / `half_map_2=` CLI flags are rejected in this build.
- `phenix.real_space_diff_map model.pdb map.mrc resolution=X` works for cryo-EM omit-style difference maps and is a useful gate before speculative local restraint tests.
- `phenix.real_space_correlation` is broken for real-map jobs in this Phenix 2.0 build (`miller_fn` error); use `phenix.map_correlations` for overall/per-residue CC and a custom ChimeraX sampler for ligand/per-atom density.

**Target metrics:**
| Metric | Target |
|--------|--------|
| Rama outliers | < 0.5% |
| Rama favored | > 96% |
| Rotamer outliers | < 2% |
| Clashscore | < 10 |
| CC_mask | > 0.6 |

## Presets
- `xray_default`: individual_sites+individual_adp, 3 cycles
- `em_default`: electron scattering, minimization+grid_search, 5 cycles

## Troubleshooting

## Additional Cryo-EM / Ligand CLI Lessons

- `phenix.ligandfit` is fundamentally an X-ray/MTZ workflow. Feeding CCP4/MRC maps directly can crash; converting large cryo-EM cells with `phenix.map_to_structure_factors` may create enormous MTZs and stall. Boxed MTZ ligandfit can place ligands in wrong density and uses shifted-box coordinates that need origin correction. Prefer reference-transfer + RSR when a homologous ligand structure exists.
- `phenix.real_space_refine run=all` is invalid in this Phenix 2.0 build. Omit `run=` for defaults, or specify explicit terms such as `refinement.run=minimization_global+local_grid_search+adp`.
- For ligand-containing EM models, make ADP refinement explicit (`...+adp`) before interpreting ligand B-factors; otherwise ligand B values can remain frozen from ISOLDE defaults.
- `phenix.map_correlations model.pdb map.map resolution=X` gives per-residue CC including ligands and replaces deprecated `phenix.map_model_cc` (old name requires `--force`).
- `phenix.pdb_interpretation model.pdb restraints.cif write_geo=True` writes a `.geo` file useful for ligand-specific bond/angle deviations.
- `phenix.real_space_diff_map model.pdb map.mrc resolution=X` works for cryo-EM omit-style difference maps and is a good gate before speculative local restraint tests.
- `phenix.real_space_correlation` is broken for real-map jobs in this build (`UnboundLocalError: miller_fn`) and also rejects `scattering_table=electron`; use `phenix.map_correlations` for residue CC and a custom ChimeraX map-sampling script for ligand/per-atom local density.
- For half-map FSC with `phenix.mtriage`, use an `.eff` block with fully qualified keys, e.g. `map_model.full_map`, repeated `map_model.half_map = ...`, `map_model.model`, plus resolution/scattering table. Bare `half_map_1=` / `half_map_2=` CLI flags are rejected.
- `phenix.validation_cryoem` on custom ligands can fail with unknown nonbonded energy types unless the ligand CIF is supplied as a positional argument.

| Problem | Fix |
|---------|-----|
| `phenix.refine: command not found` | Source `phenix_env.sh` |
| MTZ label errors | Specify `--labels` + `--rfree-label` |
| EM resolution missing | Always pass `--resolution` |
| Ligand not recognized | Generate CIF via `phenix.elbow` |
| Zero helix H-bonds | Fix `helix_type = *unknown` → `*alpha` |
| CC drops with reference_model | Remove reference model at >3Å EM |

## CLI Reference

Load [references/phenix_cli_reference.md](references/phenix_cli_reference.md) for full command syntax.

## Neighbour skills

- **CCP4 binaries** (`refmac5`, `acedrg`, `phaser`, `freerflag`, `mtzdump`, `servalcat`, `refmacat`, …) → use the `ccp4` skill, not Phenix wrappers, even when a Phenix workflow could solve the same problem.
- **Strategic choice** between Phenix vs Refmac/Servalcat → `structural-strategy/references/refinement.md`.
