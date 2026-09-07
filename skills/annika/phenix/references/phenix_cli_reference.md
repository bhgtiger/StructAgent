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

## Current release and tutorial decisions (checked 2026-09-07)

The [official build table](https://www.phenix-online.org/download/nightly_builds.cgi) identifies **2.2.1-6174, 2026-09-03**, as an official release. The [versioned changelog](https://phenix-online.org/version_docs/2.2.1-6174/CHANGES) labels its changes August 2026: distinguish this development heading from the installer release date. No new local Phenix runtime was tested; entrypoint observations labeled Phenix 2.0 retain that historical scope.

- **Cryo-EM ligand placement:** the [LigandFit manual](https://phenix-online.org/documentation/reference/ligandfit.html) documents `map_in` for MRC/CCP4/MAP input and requires resolution. A command template is:

  ```bash
  phenix.ligandfit map_in=boxed_map.mrc resolution=3.2 \
    model=receptor.pdb ligand=ligand.pdb
  ```

  This uses internal map-coefficient conversion. Keep receptor and boxed map in one frame, inspect conversion cost and verify the ligand sits in the intended density. This is a documented template, not a validated local fixture. Supply ligand restraints for subsequent refinement.

- **Ligand validation:** Phenix 2.2 adds `phenix.validate_ligands`, covering local fit, geometry and environment; check installed help before selecting its arguments. In 2.2.1, cryo-EM validation summary tables and Table 1 export receive fixes, and GUI transfers to Coot use mmCIF. For an export failure or changed atom identifiers, record the exact build and re-read the exported model before attempting coordinate repair. These changes are documented in the [release changelog](https://phenix-online.org/version_docs/2.2.1-6174/CHANGES).
- **Real-space refinement tutorial:** use the examples and linked video in the [RSR manual](https://phenix-online.org/documentation/reference/real_space_refine.html). Start with defaults, inspect the resulting `.eff` and geometry report, and change one justified strategy at a time. ADP refinement is documented as enabled by default; a custom `run=` selection can omit it. Preserve `adp` when needed. The manual supports reference-model restraints with selected chain/range mappings, so reference suitability is not determined by a universal resolution threshold. Inspect actual restraint counts when SS outlier filtering removes long hydrogen bonds.

The runner's `--resolution`, `--labels` and other dashed options belong to `scripts/runner.py`; native Phenix uses PHIL `name=value` syntax. The online manual is not the installed PHIL schema. Retest old failure-specific workarounds against an authorized small fixture before declaring them fixed in 2.2.1.
