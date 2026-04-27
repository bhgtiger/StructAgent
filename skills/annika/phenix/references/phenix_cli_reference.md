# Phenix CLI Quick Reference

## Environment Setup
```bash
source /path/to/phenix-<version>/phenix_env.sh
# Verify: echo $PHENIX; command -v phenix.refine
```

## X-ray Refinement (phenix.refine)
Ref: https://phenix-online.org/documentation/reference/refinement.html

```bash
# Minimal
phenix.refine model.pdb data.mtz

# With params
phenix.refine model.pdb data.mtz \
  strategy=individual_sites+individual_adp \
  main.number_of_macro_cycles=3 nproc=4

# With explicit labels
phenix.refine model.pdb data.mtz \
  xray_data.labels="F,SIGF" \
  xray_data.r_free_flags.label="FreeR_flag"

# With ligand CIFs
phenix.refine model.pdb data.mtz lig1.cif lig2.cif

# With PHIL file
phenix.refine model.pdb data.mtz run.eff
```

Key params: strategy=, main.number_of_macro_cycles=, nproc=, ordered_solvent=,
xray_data.labels=, xray_data.r_free_flags.label=, xray_data.twin_law=,
tls.find_automatically=, output.prefix=

Outputs: <prefix>_refine_001.pdb/.mtz/.log/.eff/.geo
Metrics: grep -Ei "R-work|R-free" *.log

## Cryo-EM Refinement (phenix.real_space_refine)
Ref: https://phenix-online.org/documentation/reference/real_space_refine.html

```bash
# Minimal (resolution= required for MRC/CCP4)
phenix.real_space_refine model.pdb map.mrc resolution=3.2

# Automation-friendly
phenix.real_space_refine model.pdb map.mrc \
  resolution=3.2 scattering_table=electron \
  macro_cycles=5 nproc=8

# With run steps
phenix.real_space_refine model.pdb map.mrc resolution=3.2 \
  run=minimization_global+local_grid_search+morphing

# With ligand CIFs
phenix.real_space_refine model.pdb map.mrc lig.cif resolution=3.2
```

Key params: resolution=, macro_cycles=, nproc=, scattering_table=electron,
run= (minimization_global|rigid_body|local_grid_search|morphing|simulated_annealing|nqh_flips),
rotamer_restraints=, ramachandran_restraints=, c_beta_restraints=, ncs_constraints=

Outputs: <prefix>.pdb/.log/.geo/.eff
Metrics: Ramachandran/rotamer outliers, bond/angle RMSD

## Validation Tools
| Tool | Use | Ref |
|------|-----|-----|
| phenix.model_vs_data | X-ray Rwork/Rfree/stats | model_vs_data.html |
| phenix.molprobity | Geometry validation (both) | molprobity.html |
| phenix.validation_cryoem | Cryo-EM comprehensive | validation_cryo_em.html |
| phenix.mtriage | Map quality/FSC | mtriage.html |
| phenix.map_correlations | Map-model CC | map_correlations.html |

## Ligand/Restraints
```bash
# Generate ligand CIF from SMILES/SDF
phenix.elbow ligand.sdf --residue=LIG --output=lig

# Model prep (add H, ligand CIFs, metal edits)
phenix.ready_set model.pdb

# Supply CIFs to refinement (positional args)
phenix.refine model.pdb data.mtz lig.cif link.cif

# Covalent links via PHIL
refinement.pdb_interpretation.apply_cif_link {
  data_link = LINK_ID
  residue_selection_1 = chain A and resname LIG and resid 501
  residue_selection_2 = chain A and resname CYS and resid 145
}
```

Refs: elbow.html, ready_set.html, ligandfit.html, dock_in_map.html
