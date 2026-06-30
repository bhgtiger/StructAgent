# 05 — Core Workflow & Suitability

## What the pipeline actually does (end to end)

1. Take a roughly pre-fitted model + target map + map resolution.
2. Convert the map to an MDFF steering potential.
3. Prepare the model with VMD AutoPSF/MDFF — **remove non-ATOM records**,
   convert `UNK`→ALA, add hydrogens/missing atoms, apply CHARMM36.
4. Run NAMD2/MDFF (CHARMM36, vacuum by default; GBIS optional via `-i`),
   steered by the map potential.
5. Export the last trajectory frame as PDB; remove hydrogens.
6. Run Phenix ADP/B-factor processing on the input and last frame; optionally
   (`-x`) add coordinate real-space refinement to produce `last_frame_rsr.pdb`.
7. Validate input vs. output(s) with Phenix metrics, model-map CC, and Rosetta
   scoring (if available). Plot clashscore across frames.

It is a **codified, automated MDFF workflow** — its value is convenience and
consistency, not a correctness guarantee.

## Suitability decision (run this before any command talk)

Namdinator is appropriate when **all** hold; name any that fail and steer
accordingly:

- **One model, one map, already roughly docked.** Not docked → rigid-body fit
  first (chimerax/Coot/PyMOL). Multiple very different conformations → handle
  per-conformer.
- **Resolution is low-to-medium** (roughly > ~3 Å) *or* the model has clear
  fit/geometry problems MDFF can relax. Already-good high-res full-atom models
  are low-benefit (paper non-improvers: 6b44, 5ni1, 5sy1, 5n9y, 3j9c).
- **Required motion is modest.** Rotations beyond ~40–45° are poor MDFF targets
  without manual domain splitting (ref 06, ref 08).
- **Map is/can be P1.** Crystallographic maps must be expanded to P1 (ref 04).
- **Chemistry tolerance:** the user understands ligands/metals/waters are
  dropped by default (SKILL §6) and is OK reinserting them, or those groups are
  not central to the question.

If those hold, proceed to mode choice (local vs. web) → input preflight →
environment preflight (local) / privacy gate (web) → parameters → command plan →
output interpretation → troubleshooting.

## When another tool is the better answer

- Interactive, guided fixing with live restraints → **isolde** (interactive
  MDFF in ChimeraX) or **coot** (local rebuilding, ligands, waters).
- Reciprocal-space refinement, ligand restraints, final validation → **phenix**
  / **ccp4**.
- Rigid-body docking / superposition / model editing → **chimerax**.
- "Which approach, in what order, and why" across the whole build → consult
  **structural-strategy**.

Namdinator competes most directly with ISOLDE and Phenix real-space refinement.
Its niche: a fast, hands-off batch pass that needs almost no setup and produces
a validated before/after — useful for triage and for visibly problematic models,
less so for fine final-stage work.

## Honest framing

The paper frames Namdinator as *assistance, not a replacement* for model
building, and its "34/39 improved" benchmark counts improvement in **any one**
of three global metrics. Present recommendations as triage / improvement
support, never as automatic correctness. The final model still needs visual
inspection, independent validation, and domain judgment.
