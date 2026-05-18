# EMERALD XML — annotated

The template lives at `presets/emerald.xml`. This document explains what each
block does and what to change for your system.

## SCOREFXNS

```xml
<ScoreFunction name="dockscore" weights="beta_genpot">
    <Reweight scoretype="gen_bonded" weight="1.0"/>
    <Reweight scoretype="elec_dens_fast" weight="100.0"/>
</ScoreFunction>
```

- `beta_genpot` — the generic-potential scorefunction (enables GenFF ligand energies). Required for EMERALD.
- `gen_bonded` reweight — needed so the new bonded terms contribute. If you see large strain in the ligand, lower this to 0.5.
- `elec_dens_fast` weight 100 — density agreement term. Paper default. For noisier maps (≥5 Å local resolution) try 50–80. For cleaner maps (<3 Å) 120–150 is fine.

```xml
<ScoreFunction name="relaxscore" weights="beta_genpot_cart"> ... </ScoreFunction>
```

Cartesian scorefunction used for the post-dock refinement (only if
`final_exact_minimize` is set to an `sc`/`bbsc*` value on GALigandDock).

## MOVERS

```xml
<SetupForDensityScoring name="setupdens"/>
<LoadDensityMap name="loaddens" mapfile="%%map%%"/>
```

Standard density-scoring preamble. `%%map%%` is a Rosetta variable — set it
from the CLI with `-parser:script_vars map=/path/to/map.mrc`, or hardcode the
path inside the XML if you prefer.

```xml
<GALigandDock name="dock"
              scorefxn="dockscore"
              scorefxn_relax="relaxscore"
              runmode="dockflex"
              ...>
```

- `runmode="dockflex"` — flexible side chains around the ligand. Use `"dockrigid"` if your receptor is trusted and you only want to place the ligand (faster).
- `sidechains="aniso"` — Ile/Leu/Val/Thr use anisotropic sampling. Alternative: `"auto"` (Rosetta picks) or an explicit residue list `"22A,25A,29A"`.
- `final_exact_minimize="bbsc1"` — one round of bb+sc cartesian minimization on the top 20 poses.
- `favor_native="2"` — keep starting side-chain rotamers unless there's a strong reason to move.
- `optimize_input_H="true"` — re-place polar hydrogens before docking.
- `estimate_dG="true"` — compute the per-pose dH / dG summary for ranking.

### Stage

```xml
<Stage repeats="100" npool="50" pmut="0.2" smoothing="0.375"
       rmsdthreshold="1.5" maxiter="50" pack_cycles="100"
       ramp_schedule="0.1,1.0"/>
```

GA parameters from the paper. Changes:
- `npool=50, repeats=100` → ~5000 ligand evaluations. Drop to 25/50 for a smoke test; go to 100/150 for difficult pockets.
- `rmsdthreshold=1.5` — poses closer than this collapse into the same cluster.

## Binding site (optional)

For a known approximate site, add an `initial_pool` pointing at a seed PDB:

```xml
<GALigandDock ... initial_pool="seed.pdb" reference_pool="seed.pdb" reference_frac="0.5">
```

The `run_emerald.sh --seed <pdb>` flag wires this up automatically (it
substitutes `-s seed.pdb`, but the XML attribute you'd want is `initial_pool`).

## Running with `-parser:script_vars`

```bash
rosetta_scripts.* -parser:protocol emerald.xml \
  -parser:script_vars map=/abs/path/to/map.mrc \
  -s receptor.pdb -in:file:extra_res_fa LIG.params ...
```

## Verifying against the paper

This template covers the core protocol; for production benchmarking pull the
reference XML from **Supplementary Data 2** of Muenks et al. 2023. Commit that
to your project alongside this template so future-you can tell them apart.
