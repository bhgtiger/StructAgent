# 07 — Validation Outputs & How to Read Them

Namdinator compares **input**, **last-frame output**, and (with `-x`) the
**real-space-refined** output across a battery of metrics. Use them together;
no single number decides quality.

## What gets computed (from source + paper)

| Metric | Tool | Reads as |
|---|---|---|
| Model–map correlation (local CC / `CC_mask`) | `phenix.map_model_cc` | Higher = better agreement with the map. Baseline repo parses `CC_mask`. |
| Trajectory & model–map correlation | VMD/MDFF `mdff check -ccc` | Cross-check of CC during/after the run. |
| Clashscore | `phenix.clashscore` | Lower = fewer steric clashes. Can rise when a pruned/polyalanine input becomes full-atom. |
| Ramachandran outliers | `phenix.ramalyze` | Fewer outliers = better backbone geometry. |
| Rotamer outliers | `phenix.rotalyze` | Fewer = better side-chain geometry. |
| Cβ deviations | `phenix.cbetadev` | Fewer = better backbone/side-chain consistency. |
| Cis-peptides | VMD cispeptides | Flags unexpected cis peptide bonds. |
| Whole-model Rosetta score | `score_jd2.*` | Only if `ROSETTA_BIN` is set; else `n/a`. |
| Per-residue Rosetta energies | `per_residue_energies.*` | Top-hit table of worst residues; only if `ROSETTA_BIN` set. |
| Clashscore across trajectory | gnuplot → `clash_all_frames.png` | Trend of clashes over frames. |

## Reading the results honestly

- **CC up, geometry down (or the reverse) is common.** A model can fit the map
  better while gaining clashes, or clean up geometry without moving CC. Judge the
  *balance*, against the question being asked.
- **Full-atom conversion skews comparisons.** If the input was pruned or
  polyalanine and the output is full-atom, more atoms can mean more clashes —
  that is not necessarily a regression. Example: 6eny/EMDB-3906 — Ramachandran
  outliers dropped strongly and CC rose, but clashscore worsened after full-atom
  conversion. Compare like with like.
- **The benchmark headline is permissive.** "34/39 improved" (of 39 cryo-EM
  pairs) counts a case as improved if **any one** of CC / clashscore /
  Ramachandran improved. Per-metric: CC 22 up / 11 same / 6 down; clashscore
  17 up / 18 similar / 4 down; Ramachandran outliers 23 down / 12 same / 4 up.
  So "often helpful," not "always improves the whole model."
- **Stochastic.** Re-running gives different trajectories/numbers; for important
  cases, repeat and inspect.
- **Visualize before trusting.** Load `last_frame.pdb` (or `_rsr`) with
  `visualize_trj.tcl` / in ChimeraX/Coot and look — especially at ligand sites
  (now empty), chain breaks, and any region that moved a lot.

## What to tell the user after a run

1. Which output to take: `last_frame_rsr.pdb` if `-x` was used and its metrics
   are better; otherwise `last_frame.pdb`. Always inspect, don't auto-accept.
2. The before/after on each metric, with the "balance not single-number" framing.
3. Reminder that ligands/metals/waters need manual reinsertion and separate
   validation (ref 04), and that this output is a **draft**, not a finished,
   publication-ready model.

> Output filenames/log formats here are from source, not a captured fixture run.
> If a user needs an exact parser, flag that a real fixture output tree must be
> captured first (ref 00, ref 10). Do not invent log line formats.
