# EMERALD CLI reference

Every flag `run_emerald.sh` assembles, and why it matters. Sourced from
Muenks et al. 2023 (PMC9976687) Methods + Rosetta GALigandDock docs.

## Rosetta framework flags

| Flag | Purpose |
|---|---|
| `-parser:protocol <emerald.xml>` | RosettaScripts XML that defines the dock. |
| `-s <receptor.pdb>` | Starting receptor structure. |
| `-nstruct <N>` | Number of output poses. Paper uses 20. |
| `-out:prefix <str>` | Prefix on all output PDB/silent files. |
| `-overwrite` | Overwrite existing outputs (avoid "output exists" bail). |

## Ligand / scoring flags

| Flag | Purpose |
|---|---|
| `-in:file:extra_res_fa <LIG.params>` | Tells Rosetta about the custom ligand residue. |
| `-gen_potential` | **Required.** Switches to the generic (beta_genpot) force field. Without this, GALigandDock falls back to a typical beta scorefunction that doesn't know your ligand properly. |
| `-score::gen_bonded_params_file scoring/score_functions/generic_potential/generic_bonded.round6p.txt` | Path (relative to `$ROSETTA3/database`) to GenFF's bonded params. |

## Density flags

| Flag | Purpose |
|---|---|
| `-edensity::mapfile <map.mrc>` | CCP4/MRC-format cryo-EM map. |
| `-edensity::mapreso <Å>` | **Local** resolution in the binding pocket (not global). ±0.5 Å matters. |
| `-edensity::grid_spacing 1.0` | Internal sampling grid. Paper uses 1.0 Å. |
| `-edensity::sliding_window 1` | Enables the per-residue sliding-window density score. |
| `-edensity::score_sliding_window_context` | Score each residue in context of its neighbors — essential for density-guided dock. |
| `-edensity::atom_mask 2` | Atom mask radius (Å). |

The XML separately sets the density *weight* via the `elec_dens_fast` reweight
(100 in the paper template).

## Optional / tuning

| Flag | Purpose |
|---|---|
| `-in:file:extra_res_fa` (repeat) | Multiple params if you have co-factors. |
| `-restore_talaris_behavior` | **Do not set.** Breaks GenFF. |
| `-ignore_zero_occupancy false` | Keep zero-occupancy atoms in the receptor. |
| `-out:file:scorefile emerald.sc` | Score summary file (see presets/emerald_flags.txt). |

## After the run — picking a pose

Poses are written as `<prefix>_NNNN.pdb`. Rank by:

1. `elec_dens_fast` — primary density-agreement term (lower = better fit)
2. `total_score` — overall Rosetta energy
3. `if` (interface energy) — protein–ligand complementarity

The paper's metric for "confident solution" combines density score with a
cluster-size criterion (top-20 poses clustering to ≤2 Å RMSD). See
Methods §"Pose selection" of the paper.
