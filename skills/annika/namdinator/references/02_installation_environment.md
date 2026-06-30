# 02 — Installation & Environment (local CLI)

Evidence: `Namdinator_Generic.sh` (baseline @ 5814c947), README, web manual,
Kidmose et al. 2019. **No live install was validated by this project** — treat
versions as the documented/tested set, not as a guaranteed-working modern stack.

## Required local stack

| Component | Version / note | Evidence |
|---|---|---|
| Linux shell environment | Bash + GNU/Linux utilities (e.g. `lscpu`). | Source |
| VMD | 1.93. | README, paper |
| VMD plugins | MDFF 0.5, ssrestraints 1.1, cispeptides 1.3, chirality 1.3, AutoPSF 1.6, multiplot 1.7. | Paper |
| NAMD2 | 2.12, CUDA build. | README, paper |
| CUDA | 6.0 or later GPU support recommended. | Paper |
| Phenix | README: 1.13rc1 (2954); source comments mention `phenix-1.13-2998`. Script calls many `phenix.*` tools. **Hard-required — the script exits without it, even without `-x`.** | README, source |
| Rosetta | 2016.32.58837. **Optional** — used only if `ROSETTA_BIN` is set; otherwise Rosetta score columns become `n/a`. | README, source |
| CHARMM36 | Topology/parameters used through VMD for all-atom MDFF. | Source, paper |
| gnuplot | Clashscore-vs-frame plots. | Source |
| bc | Resolution-dependent Rosetta scoring branch logic. | Source |

Phenix tools invoked by the script include: `phenix.show_map_info`,
`phenix.reduce`, `phenix.pdbtools`, `phenix.real_space_refine`,
`phenix.map_model_cc`, `phenix.ramalyze`, `phenix.rotalyze`, `phenix.cbetadev`,
`phenix.clashscore`. The baseline script runs ADP-only
`phenix.real_space_refine` on the input and last frame even when `-x` is not
set; `-x` adds a coordinate real-space-refinement pass that writes
`last_frame_rsr.pdb`. VMD usage includes MDFF, AutoPSF, ssrestraints,
cispeptides, chirality, multiplot.

## Environment variables / paths

The generic script can use: `VMDMASTER`, `NAMDMASTER`, `ROSETTA_BIN`, `PHENIX`,
`PHENIXMASTER`. If `PHENIXMASTERDIR` is set it sources `phenix_env.sh`.

**Hard requirements:** the generic script **exits** if VMD, NAMD2, **or Phenix**
are missing — the `which phenix` → `exit 1` check is *unconditional* (source
lines 479–489), alongside the VMD (63–72) and NAMD2 (75–94) exits. So **Phenix
is required even without `-x`**: it is used for map info, ADP/B-factor
processing including `phenix.real_space_refine refinement.run=adp`, model-map
CC, and validation on every run. Setting `-x` adds a
*further* `PHENIXMASTERDIR` check. Rosetta is genuinely optional (used only if
`ROSETTA_BIN` is set; otherwise its score columns read `n/a`). `gnuplot` (clash
plot) and `bc` (Rosetta-scoring branch) are used but do **not** gate startup;
`lscpu` only supplies the `-n` default on Linux and is substitutable with an
explicit `-n`.

## Hardware guidance (2019-era context — label it as such)

- Default local execution uses GPU-accelerated NAMD2; a CUDA GPU is recommended.
- NAMD2 does **not** offload all work to GPU, so a strong multicore CPU helps.
- 16 GB RAM handled models up to ~20,000 residues with their maps.
- Web-server timing claim: ~1 minute per 15 kDa of model, generally < 1 hour on
  a normal workstation. This is 2019 context; do not quote as a current SLA.

## Compatibility risks (state these when advising installation)

- The repo is old and untagged; exact compatibility with current
  VMD/NAMD/Phenix/Rosetta is unknown.
- `lscpu` makes the processor default **Linux-specific**. macOS needs patching
  or an explicit `-n`. Do not recommend running the unmodified script on macOS.
- Phenix output formats have shifted across versions; the baseline already moved
  CC parsing from older `CC_volume`/`masked` patterns to `CC_mask`. A newer
  Phenix could break parsing again.
- Web UI defaults differ from CLI: web temperature fields default to **298 K**;
  Bash defaults are **300 K**.

## The read-only probe

`scripts/preflight_namdinator_env.py` inventories whether `vmd`, `namd2`,
`phenix` and the required `phenix.*` tools, Rosetta, `gnuplot`, `bc`, `lscpu`
are on PATH and reports versions where safe.
It is **read-only** (no installs, downloads, network, or jobs) and is safe to
run on any host to answer "could this machine, in principle, run Namdinator?".
It does **not** prove a working run — only a live fixture run does that.

## Licensing for install advice

Namdinator is GPL-3.0, but its dependencies are not freely redistributable:
Rosetta needs a RosettaCommons license, Phenix has its own download/license
terms, VMD/NAMD have theirs. Advise the user to obtain each through its official
channel; never bundle binaries or assume redistribution rights. See ref 09.
