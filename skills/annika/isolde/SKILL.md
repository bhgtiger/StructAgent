---
name: isolde
description: "Interactive model building with ISOLDE inside ChimeraX. Covers: flexible fitting (MDFF) of AlphaFold/homology models into cryo-EM or crystallographic maps, simulation management, restraints, ligand handling, validation, and Phenix export. Uses ChimeraX REST for automation. Requires GUI mode. Use when the user asks to run ISOLDE, do flexible fitting, MDFF, fix geometry, or refine interactively."
---

# ISOLDE Skill

Automate ISOLDE (ChimeraX plugin) via REST API for flexible fitting with OpenMM molecular dynamics. Upstream checked **2026-09-07**: Toolshed lists **1.12.1 for macOS (2026-09-04)** and **1.12.0 for Linux/Windows (2026-06-26)**, requiring ChimeraX 1.12.x. These are documentation checks; historical local lessons and scripts are not newly validated. Read [current preflight and tutorial guidance](references/commands.md#current-release-preflight-and-tutorials) for this release family.

**Key difference from chimerax skill:** ISOLDE requires GUI mode — `--nogui` does NOT work.

## Architecture

```
Agent → curl (HTTP POST) → ChimeraX REST (localhost:PORT) → ISOLDE
       ↘ Python script injection via REST for timers/monitors
```

## Bootstrap

```bash
CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)
"$CHIMERAX" --cmd 'remotecontrol rest start port 9876' &
for i in $(seq 1 30); do curl -s http://localhost:9876/run?command=version && break; sleep 2; done
curl -s 'http://localhost:9876/run?command=isolde+start'
```

If port 9876 gives "Address already in use" after a crash, use 9877.

## Sending Commands

```bash
curl -s 'http://localhost:9876/run?command=isolde+sim+start'
curl -s 'http://localhost:9876/run?command=fitmap+%231+inMap+%232'
```

**Always URL-encode `#` as `%23`.** Do NOT interact with ChimeraX GUI while agent is running.

## ISOLDE Handler

```python
ih = session.isolde  # CORRECT
# WRONG: session_extensions.get_isolde_handler() — doesn't exist
```

## Critical Rules (from debugging)

### 1. REST Hangs During Active Simulation
REST commands queue behind the Qt event loop when sim is running. **All timers and stops must be Python code injected into ChimeraX:**

```python
import threading
def stop_and_save():
    session.ui.thread_safe(lambda: run(session, "isolde sim stop"))
    session.ui.thread_safe(lambda: run(session, "save /path/out.cif"))
threading.Timer(600, stop_and_save).start()
```

### 2. Map Association is MANDATORY
Loading a map does NOT enable MDFF. Without explicit association, ISOLDE runs pure MD and the model drifts away from density.

```python
from chimerax.clipper import get_map_mgr
mmgr = get_map_mgr(model)
nxmapset = mmgr.nxmapset
nxmapset.add_nxmap_handler_from_volume(vol)
```

**Verify before sim:**
- `ih.selected_model_has_maps == True`
- `ih.selected_model_has_mdff_enabled == True`
- If EITHER is False → ABORT. Do not start sim.

### 2b. Find Volume by TYPE, Not Index
**Bug:** `session.models[1]` is NOT always the map volume. Loading a model can create child PseudobondGroups (metal coordination bonds, missing structure, etc.) that appear in the models list before the Volume.

**Fix:** Always find model and volume by class type:
```python
from chimerax.atomic import AtomicStructure
from chimerax.map import Volume

model = None
vol = None
for m in session.models.list():
    if isinstance(m, AtomicStructure) and model is None:
        model = m
    elif isinstance(m, Volume) and vol is None:
        vol = m
```
**Never** use `session.models[0]` / `session.models[1]` — always type-check.

### 3. Unexpected simulation termination
Treat an immediate stop as failure, but do not infer its cause from "Sim termination reason: None" alone. On 1.12 use `isolde status` and `isolde preflight parameters #N` before private API patches; see [references/debugging.md](references/debugging.md).

### 4. Don't `close all` During Workflow
Closing + reloading disrupts MDFF setup. Keep the session alive.

### 5. Monitor Simulation Status
Check `ih.simulation_running` every 30s to catch silent failures.

### 6. OpenMM Platform (Mac)
```python
ih.sim_params.platform = 'OpenCL'  # Mac mini — no HIP
```
Available: Reference, CPU, OpenCL.

## Pre-Flight Checklist (before every sim start)

1. Confirm compatible ChimeraX/ISOLDE versions; on macOS the 1.12.1 build restores preflight/validation commands missing from 1.12.0.
2. Run the current [preflight sequence](references/commands.md#current-release-preflight-and-tutorials) for hydrogen, parameter, disulfide, and alternate-conformer readiness. Resolve reported chemistry issues and repeat the checks.
3. Preserve OP3/OXT and existing chemistry unless the actual residue fails template matching and a justified repair is needed. Historical terminal/ADP/HIS fixes below are conditional, not blanket preparation steps.
4. Rigid-fit before selecting the ISOLDE model; associate the map and verify both MDFF flags. The public `clipper associate #map to #model` route is documented in the command reference.
5. Select an available OpenMM platform. OpenCL and the M4 precision workaround are historical Mac observations, not guarantees for every installation.
6. Set the internal stop/save timer and monitor before starting. Current disulfide/altloc preflights acknowledge their dialogs without changing atoms; use corresponding fixes only as required by the model-building task.

## Ligand Handling

ISOLDE uses OpenMM amber14 forcefield templates, NOT Phenix `.edits` restraints.

### Ligand Import
A historical local mmCIF export lost non-polymer entities. Verify ligand atom/residue counts in each actual export; if affected, save the ligand separately as PDB and combine in ChimeraX. This is not a blanket claim about current gemmi.

### ADP Template (MC_ADP)
Template expects 39 atoms (27 heavy + 12 H), 41 bonds. After `addh`:
- Rename `H5'` → `H5'1`, `H5''` → `H5'2`
- Delete spurious `H2B` on O2B
- Delete spurious `O3A–O5'` bond
- Verify: 39 atoms, 41 bonds

### Metal Ions
MG, ZN are in ISOLDE's `metal_name_map` — just need correct residue names. **Do NOT create covalent bonds to metals** — this changes atom bond counts and breaks template matching for coordinating residues.

### CYS Near Metals
ISOLDE's `cys_type()` checks SG bond count: 1 bond (only CB) → CYM. Works correctly if you don't add manual bonds.

### C-Terminal OXT
Do not delete all OXT atoms by default. ISOLDE 1.12 release notes include a C-terminal OXT construction fix; use `isolde preflight parameters` to identify actual unmatched residues. The legacy deletion workaround is scoped in [debugging](references/debugging.md).

### Template Verification
Templates are in `moriarty_and_case.zip` inside the ISOLDE package. Parse with `ZipFile` + `ElementTree`.

**Full debugging and template matching details:** [references/debugging.md](references/debugging.md)

## Popup Handling (macOS)

For 1.12, prefer the disulfide/altloc preflight commands and explicit model-specific fixes in [commands](references/commands.md#current-release-preflight-and-tutorials). They avoid those one-time dialogs. Historical launchers contain an indiscriminate OK/Yes click loop; review and disable it when using the current preflight route. Other modal warnings still need inspection before continuing.

## Domain Segmentation (Merizo)

```bash
cd <MERIZO_INSTALL> && source .venv/bin/activate
python predict.py -d cpu -i /path/to/model.pdb --iterate --save_domains
```

**Parsing:** comma = domains, underscore = discontinuous segments, dash = range.
To ChimeraX: `6-18_296-459` on chain A → `/A:6-18,296-459`

## Flexible Fitting Pipeline

### 1. Load model + map
### 2. Run pre-flight checklist
### 3. Start sim with internal timer (10 min minimum for CPU)
### 4. Monitor every 30s
### 5. Timer stops + saves
### 6. Remove H (Python API — see below)
### 7. Validate: `rama report`, `rota report`, `measure correlation`
### 8. Export for Phenix: `isolde write phenixRsrInput` (cryo-EM) or `phenixRefineInput` (X-ray)

**Convergence:** CC improvement < 0.02 between rounds → done. Max 3 rounds.

## Apple M4 OpenCL Precision

On Apple M4, OpenMM/OpenCL is reliable in **single precision**. Code that forces mixed precision can falsely report no compatible OpenCL platform and fall back to CPU. Prefer a precision fallback chain (mixed → single) or a short smoke-test confirming the selected platform/precision actually runs.

## Monitored Batch Run (historical template)

For automated runs with live convergence monitoring, adapt the monitored batch template after reading its [current-version caveats](references/monitored_batch.md#current-version-caveats). Its chemistry cleanup, private APIs, and popup handling remain historical and have not been tested with 1.12.

**Template:** `scripts/isolde_monitored_template.py`
**Launcher:** `scripts/launch_monitored.sh`
**Docs:** `references/monitored_batch.md`

**Features:**
- Live CC measurement every 60s (flushes to `convergence_log.txt`)
- Early stop on CC plateau (ΔCC < 0.002 for 2 consecutive windows)
- Emergency revert if CC drops > 0.005 from peak
- Hard timeout safety net (default 10 min)
- Proper H stripping via Python API + explicit model save
- Single-instance launcher lock (no duplicate ChimeraX)

**Quick start:**
1. Copy `scripts/isolde_monitored_template.py` to working dir
2. Edit PARAMETERS section (paths, mobile selection, timing)
3. `bash scripts/launch_monitored.sh /path/to/your_script.py`
4. Monitor: `tail -f convergence_log.txt`

**Key design decisions:**
- **Two map copies:** One for clipper/MDFF, one for CC measurement (clipper invalidates vol IDs)
- **Delete H via Python API:** `model.atoms.elements.numbers == 1` — the `element.H` specifier is broken
- **Explicit save:** `save OUTPUT models #id format mmcif` — prevents saving extra objects
- **thread_safe:** All timer callbacks wrapped in `session.ui.thread_safe()` — required because ChimeraX Qt event loop blocks during sim

## Command Reference

### Custom Ligand Templates (GAFF2/OpenMM XML)

ISOLDE can handle custom ligands with matching OpenMM force-field templates loaded before simulation. First consider documented `isolde parameterise` and the GUI parameter loader in [commands](references/commands.md#ligand-parameterization). The following custom-ligand pattern is a historical locally validated CHEBI:57456 precedent, not a requirement to install packages or bypass the public workflow:

1. Install prerequisites into ChimeraX Python once: `openmmforcefields` and `rdkit` (OpenMM/parmed are already present in current setup).
2. Ensure Phenix AmberTools wrappers exist, e.g. `~/phenix-2.0/bin/wrapped_progs/{antechamber,parmchk2,...}` symlinked to `../x/<tool>`; otherwise `antechamber` can fail with `wrapped_progs not found`.
3. Use RDKit to make a protonated 3D ligand with canonical heavy-atom names and sequential H names.
4. Write SDF with explicit bond orders (`Chem.MolToMolFile(..., kekulize=True)`); PDB-derived input can make antechamber assign `DU` dummy atom types.
5. Run antechamber with GAFF2, usually using fast Gasteiger charges for MDFF: `antechamber -i LIG.sdf -fi mdl -o LIG.mol2 -fo mol2 -c gas -nc <charge> -at gaff2 -rn LIG -pf y`.
6. Run `parmchk2`, then `tleap`, then convert with parmed `OpenMMParameterSet.from_structure(struct).write('LIG_params.xml')`.
7. Inject a `<Residues><Residue name="USER_LIG">...` block manually; parmed writes atom types/forces but not the residue template.
8. Load before sim: `ff = ih.forcefield_mgr[ih.sim_params.forcefield]; ff.loadFile('LIG_user.xml')`.

Critical gotchas:
- Template name must use the `USER_` prefix (ISOLDE checks `USER_{resname}` first).
- Pre-protonate the ligand before loading the model; H names and bonds must match the template.
- Include ligand `CONECT` records in PDB input. Without them, ChimeraX `addh` can guess wrong ligand H bonds.
- `addh #1 & ~:LIG` does not reliably exclude the ligand; run `addh`, then prune non-template ligand H atoms and verify atom count/bonds.
- Keep all atoms of each residue contiguous, keep residues per chain contiguous, and renumber PDB serials consecutively before loading.
- `assignTemplates()` returns `(dict, list, list)`; debug monkey-patches must handle list-like ambiguous/unassigned outputs.
- AM1-BCC charges can hang for large/drug-like ligands; Gasteiger (`-c gas`) is usually adequate for map-restrained MDFF.

Load [references/commands.md](references/commands.md) for full command tables and timeout guidance.

## What's NOT in v1

Interactive mouse tugging, image rendering, auto loop building.

## Update this skill

For release, tutorial, or instruction refreshes, follow [references/maintenance.md](references/maintenance.md): verify the tool-specific sources, correct owning references, preserve historical/local evidence, validate, and synchronize authorized copies. Software upgrades and live jobs are separate tasks.
