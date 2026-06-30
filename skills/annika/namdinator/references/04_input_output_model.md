# 04 — Input / Output Model

## Inputs (minimum)

- **Atomic model.** Source help path = standard **PDB**. Web UI also accepts
  `.cif` and `.pdb.gz`. Local CIF/GZ support is **unverified** — confirm before
  promising it.
- **Density map.** Source help lists `.mrc`, `.ccp4`, `.map`, `.situs`; web UI
  accepts `.ccp4`, `.map`, `.mrc`, `.map.gz`.
- **Map resolution (Å).** Required.

### Preparation requirements

- The model must already be **roughly docked** into the density. Namdinator is
  flexible fitting, not blind placement. If it is not docked, rigid-body fit
  first (ChimeraX / Coot / PyMOL / COLORES) — see the chimerax skill.
- EM maps are expected in **P1**. Crystallographic maps must be expanded to P1.
  The manual's suggested route:

  ```bash
  iotbx.reflection_file_editor PDBID.mtz --expand_to_p1 output_file=PDBID_p1.mtz
  phenix.mtz2map PDBID.pdb PDBID_p1.mtz labels=FWT,PHWT --remove extension=ccp4
  ```

- For web upload, use simple ASCII filenames (no spaces or `( ) # &`).

## Internal transformations (what Namdinator does to your model)

From paper + source:

- **Non-ATOM records are removed by default** — metals, waters, ligands,
  glycans, and other HETATMs do **not** enter the default simulation and are
  **absent from the default output**. (`-l` tries to keep HETATM but per help
  often fails and conflicts with `-x`.)
- `UNK` residues are converted to **alanine**.
- AutoPSF adds hydrogens and missing atoms and applies standard MD patches.
- CHARMM36 parameters are used for all-atom MDFF.
- The map is converted by MDFF into a steering potential.
- The last DCD frame is written to PDB; **hydrogens are removed**.
- Nucleotide/residue names are normalized back toward PDB-compatible naming.
- The baseline (org) repo applies ADP/B-factor processing via Phenix tools
  (`phenix.pdbtools modify.adp.set_b_iso`, ADP-only `phenix.real_space_refine`).

## Outputs (user-facing)

- `last_frame.pdb` — last MD frame, hydrogens removed, names normalized.
- `last_frame_rsr.pdb` — Phenix real-space-refined last frame, **only with `-x`**.
- `simulation-step1.dcd` — MD trajectory.
- `visualize_trj.tcl` — VMD visualization script.
- `data_files/`, `log_files/`, `scripts/`, `namdinator_stdout.log`.
- Validation logs: model-map CC / `CC_mask`, clashscore, Ramachandran, rotamer,
  Cβ-deviation, cis-peptide, and Rosetta logs (Rosetta only if `ROSETTA_BIN`
  set). See ref 07 for how to read them.
- `clash_all_frames.png` / gnuplot clashscore-vs-frame plot.

(Exact output *layout* is from source; it has **not** been confirmed against a
captured fixture run — flag this if a user needs the precise tree.)

## Output interpretation cautions

- **Better CC can accompany worse geometry, and vice-versa.** Look at all
  metrics, not one.
- The output may be **full-atom even if the input was pruned / polyalanine** —
  so a "worse" clashscore can simply reflect added atoms. Compare fairly.
- Ligands / metals / waters are likely **absent** and need manual reinsertion +
  separate validation.
- For high-resolution, already-well-built full-atom models, Namdinator may add
  little and can degrade a metric. Don't oversell.
