# Coot skill architecture

This skill targets the **practical Coot toolbox**, not a narrow wrapper around one API.

## Principle

Choose the execution lane per module, not by ideology.

Execution lanes:
1. **Headless / newer API** — use when a task is clearly supported and deterministic.
2. **Classic Coot scripting** — use for the broad documented scripting surface (`coot`, `coot_utils`, documented C/SWIG interfaces, `coot --no-graphics --script`).
3. **GUI/manual Coot** — use only when the task is genuinely interactive or the automation surface is weak/unclear.
4. **External helper / integration** — Refmac, SHELXL, findligand, libcheck/prodrg-style helpers, etc.

## Module families

### 1. Core I/O + model/map setup
- read model(s)
- read maps / MTZ / CIF-derived data where applicable
- set active refinement map
- save/export coordinates/maps
- deterministic batch job setup

### 2. Local editing + rebuild
- delete/copy fragments
- mutate / renumber / chain edits
- residue- and fragment-level local cleanup
- awkward local rebuild tasks
- loop/link/partial-residue style repair where scriptable

### 3. Refinement + fitting
- regularization / local real-space refinement
- rigid-body / simplex / residue-range fitting
- rotamers / peptide fixes / sidechain docking
- map-coupled local optimization

### 4. Ligands + monomers
- CIF dictionary loading
- monomer retrieval/import
- ligand-from-SMILES / SDF/mol helpers where practical
- ligand fitting / flipping / ligand-neighborhood cleanup
- ligand-focused validation and distortion reporting

### 5. Waters + peaks + ions
- water finding / pruning / refine-all-waters style tasks
- difference-map peak inspection
- blob finding / density candidate inspection
- ion-like local coordination workflows if Coot actually supports them well enough

### 6. Chemistry + restraints
- non-standard residue handling
- dictionaries / restraints / weird chemistry
- carbohydrate and ring-restraint features
- nomenclature / occupancy / chemistry-sensitive cleanup

### 7. Validation + diagnostics
- Ramachandran / geometry / rotamer / density-fit / clash-related reports
- local validation around edited regions
- compact summaries for agent use

### 8. External integrations
- Refmac / SHELXL / other helper-program workflows
- only include as first-class modules if they improve practical Coot usage rather than duplicating Phenix/other skills badly

## Module status labels

For each future module or script, classify it as:
- **documented + source-confirmed**
- **documented but source unclear**
- **source-present but weakly documented**
- **GUI-only / interactive**
- **not worth first-class skill support**

## Build order

Recommended priority:
1. Core I/O + map/model setup
2. Local editing + refinement basics
3. Validation summaries
4. Ligands + monomers
5. Waters + peaks / ions
6. Chemistry + restraints
7. Advanced local rebuild
8. Optional external integrations

This order keeps the skill usable early while still aiming at broad practical coverage.
