# 08 — Troubleshooting (symptom → cause → fix)

Map the user's error text or description to a **source-backed** cause. For
anything not covered here, say so and route to: inspect the log / capture `-h` /
run on a validated host — do **not** invent a fix.

| Symptom / message | Likely cause | What to advise |
|---|---|---|
| Run exits immediately saying VMD, NAMD2, or Phenix not found | The generic script hard-exits when `vmd`, `namd2`, **or `phenix`** isn't on PATH — Phenix is required even without `-x`. | Preflight the environment (`scripts/preflight_namdinator_env.py`); fix PATH / `VMDMASTER` / `NAMDMASTER` / Phenix before anything else. |
| `-x` requested but Phenix path not set | On top of the unconditional Phenix check, `-x` additionally requires `PHENIXMASTERDIR` (so `phenix_env.sh` is sourced). | Set the Phenix path / source `phenix_env.sh`; or drop `-x` (but you still need Phenix on PATH for the rest of the run). |
| AutoPSF fails on the input | Non-standard atoms / HETATM / unusual chemistry. AutoPSF can't build a topology. | Remember HETATMs are dropped by default; inspect the input in VMD/AutoPSF; remove or fix problem residues; if it's a ligand/metal/water, plan manual reinsertion later (ref 04). |
| `Bad global bond / angle / dihedral count` | Topology/geometry mismatch after record removal — broken/duplicate atoms, bad connectivity, leftover odd records. | Inspect the model **after** HETATM removal in VMD/AutoPSF; remove problematic residues or repair geometry; re-run. |
| "Atoms moving too fast" / unstable simulation | Map pull too strong for the starting geometry. | Lower `-g`, raise `-e` (minimization); verify the atom count/PSF mapping; confirm the model is actually docked in the map. |
| Output barely changed | Model already close, or G-scale too low, or steps too few. | If more motion is wanted, raise `-g` and/or `-s` gradually (ref 06). If the model was already good (high-res full-atom), low benefit is expected — don't force it. |
| Big rigid rotation didn't fit | MDFF struggles with rotations beyond ~40–45°. | Split into domains, manually rotate into density (ChimeraX/Coot), run domain-wise or on the recombined model. |
| Crystallographic map gives symmetry artifacts | No symmetry handling; map must be P1. | Expand the map to P1 first (ref 04 commands); prefer the full P1 asymmetric unit. |
| Ligands / glycans / metals gone from output | Non-ATOM records removed by default; `-l` is unreliable. | Expected behavior — reinsert manually and validate separately, or reconsider the tool. Don't rely on `-l`. |
| Two runs give different results | MDFF is stochastic. | Expected. Repeat important cases; inspect; don't treat one run as definitive. |
| Web upload rejected | Upload JS rejects filenames with spaces or `( ) # &`. | Rename to a simple ASCII filename and retry. |
| Web upload of sensitive data | Terms: data stored 14 days server-side. | Stop — apply the privacy gate (ref 09); recommend local instead for non-public data. |
| Rosetta columns show `n/a` | `ROSETTA_BIN` not set; Rosetta is optional. | Expected if Rosetta isn't configured. Set `ROSETTA_BIN` to enable Rosetta scoring, or ignore those columns. |
| Modern Phenix/VMD breaks parsing or a step | Old, untagged code vs. newer dependency output formats. | This is a known compatibility risk (ref 02). Try the documented pinned versions; treat the modern stack as unvalidated; capture the failing log. |

## When you don't know

There is little public support discussion (0 GitHub issues across both repos).
If a symptom isn't in the source/manual/paper, say it's **unverified**, ask for
the relevant log lines, and suggest reproducing on a validated host with `-h`
captured. A clear "I don't know — here's how to find out" beats a confident
guess for a 2019-era pipeline.
