---
name: emerald
description: Run Rosetta EMERALD (EM Maps ERoded for Automatic Ligand Docking) to
  place small-molecule ligands into cryo-EM density maps. Trigger on explicit
  intents like "emerald", "run emerald", "rosetta emerald", "dock ligand into
  cryo-EM map with rosetta", "GALigandDock with density", or when the user names
  an emerald.xml / GALigandDock XML file and a cryo-EM map + ligand params. Do
  NOT trigger on generic "ligand docking" (use RosettaLigand / AutoDock / Vina
  skills for non-density docking) or on "rosetta" alone.
---

# EMERALD (execution-only)

Rosetta EMERALD automatically docks a ligand into a cryo-EM map using
GALigandDock + density-weighted scoring (`beta_genpot`). See Muenks et al.,
*Nat. Commun.* 2023 (PMC9976687). Requires Rosetta ≥ 2023.06.

## Failure contract
Skills never guess. Missing Rosetta install, map, apo/holo PDB, or ligand
`.params` → **fail loudly and ask**. Do not auto-pick files in CWD. Do not
fabricate a resolution — EMERALD is sensitive to `edensity::mapreso`.

## Prerequisites
```bash
ROSETTA3="${ROSETTA3:-$HOME/rosetta/main}"       # path to rosetta/main
# Build suffix is auto-detected: macosclangrelease | linuxgccrelease | default.*
```

Run `scripts/check_env.sh` before any real run. It verifies:
1. `ROSETTA3/source/bin/rosetta_scripts.*` exists
2. `generic_potential/generic_bonded.round6p.txt` is present in the database
3. Rosetta version ≥ 2023.06 (EMERALD not available before that)

If Rosetta is not installed, read `references/install.md` — covers the
non-commercial license, download, build, and env-var setup.

## Inputs EMERALD needs

| File | Purpose |
|---|---|
| `receptor.pdb` | Apo or holo receptor. Binding-site residues should be correctly placed. |
| `map.mrc` (or `.map`) | Cryo-EM map, same frame of reference as the PDB. |
| `resolution` | Numeric Å value (e.g. `3.3`). Sets `edensity::mapreso`. |
| `LIG.params` | Rosetta ligand params file with **GenFF / AM1-BCC** charges. See `scripts/make_params.sh`. |
| *(optional)* `site.pdb` | Pre-placed seed for the ligand (if known). Can be omitted — EMERALD will search. |

## Core recipes

### 1. Generate ligand params (if not already)
```bash
bash scripts/make_params.sh --dry-run ligand.sdf LIG
# With antechamber (AmberTools) installed: produces LIG.params + LIG.pdb
# Without antechamber: falls back to $ROSETTA3/source/scripts/python/public/generic_potential/mol2genparams.py
# If neither is available → fails and tells you how to supply your own .params
```

### 2. Dock a ligand with EMERALD
```bash
bash scripts/run_emerald.sh --dry-run \
  --receptor receptor.pdb \
  --map map.mrc \
  --reso 3.3 \
  --params LIG.params \
  --xml presets/emerald.xml \
  --nstruct 20
```
Drop `--dry-run` to execute. The wrapper prints the full command first so you
can sanity-check it.

### 3. Pre-placed seed (known approximate site)
Pass `--seed site.pdb` — the wrapper adds `-s seed.pdb` and wires
`initial_pool` in the XML.

## What the XML does (conceptually)

`presets/emerald.xml` wires up:
- `ScoreFunction beta_genpot` + `elec_dens_fast` weight 100
- `GALigandDock runmode="dockflex"` with the stage schedule from the paper
- Post-dock Cartesian refinement of the top 20 poses

Full annotated template in `references/xml_template.md`. The `flags` file at
`presets/emerald_flags.txt` holds the `-edensity::*`, `-gen_potential`, and
`-score::gen_bonded_params_file` options.

## Known failure modes
- **Build suffix missing** — `rosetta_scripts.default.linuxgccrelease` may not exist; the wrapper probes `macosclangrelease`, `linuxgccrelease`, `default.*`, `static.*` in that order.
- **`-gen_potential` omitted** — scoring silently falls back to the regular beta scorefunction; you get plausible but wrong results. The flags file forces it on.
- **Wrong `edensity::mapreso`** — don't use the global/nominal reso; use the local resolution in the binding site. ±0.5 Å matters.
- **PDB & map frame mismatch** — Rosetta expects the map origin to match the PDB coordinates. Re-grid with `phenix.map_box` or ChimeraX `vop resample` before running.
- **Non-AM1-BCC charges** — params generated with default Rosetta charges give poor density agreement. Always use GenFF/AM1-BCC.
- **Version too old** — pre-2023.06 Rosetta has no EMERALD demo; `check_env.sh` rejects these.

## Deep dives
- `references/install.md` — license, download, build options for Rosetta
- `references/cli_reference.md` — every flag EMERALD uses, with meaning
- `references/xml_template.md` — annotated GALigandDock XML
- `presets/emerald.xml` — drop-in XML, edit ligand 3-letter code to match your params
- `presets/emerald_flags.txt` — command-line flags file (`@flags`)

## Lessons
See `lessons.md`.
