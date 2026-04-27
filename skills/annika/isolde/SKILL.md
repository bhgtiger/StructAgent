---
name: isolde
description: "Interactive model building with ISOLDE inside ChimeraX. Covers: flexible fitting (MDFF) of AlphaFold/homology models into cryo-EM or crystallographic maps, simulation management, restraints, ligand handling, validation, and Phenix export. Uses ChimeraX REST for automation. Requires GUI mode. Use when the user asks to run ISOLDE, do flexible fitting, MDFF, fix geometry, or refine interactively."
---

# ISOLDE Skill

Automate ISOLDE (ChimeraX plugin) via REST API for flexible fitting with OpenMM molecular dynamics.

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

### 3. "Sim termination reason: None" = Silent Crash
OpenMM couldn't assign a forcefield template. Debug with monkey-patch — see [references/debugging.md](references/debugging.md).

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

1. Delete OP3 from 5' DNA terminals
2. Delete OXT from C-terminal residues (especially near metals)
3. Run `addh`
4. **Check HIS/residues after PRO** — `addh` may skip backbone H. Missing backbone H → template mismatch → silent crash. Fix: manually add H along N-CA/N-C bisector at 1.01 Å
5. If ligands present: fix H-naming (see Ligand Handling below)
6. Associate map (step 2 above)
7. Verify MDFF flags
8. Set platform to OpenCL
9. Handle popups via osascript background loop

## Ligand Handling

ISOLDE uses OpenMM amber14 forcefield templates, NOT Phenix `.edits` restraints.

### Ligand Import
gemmi's mmCIF export drops non-polymer entities. Fix: save ligands as PDB, load separately, `combine` in ChimeraX.

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
ISOLDE has no template for residues with OXT. `delete @OXT` before sim.

### Template Verification
Templates are in `moriarty_and_case.zip` inside the ISOLDE package. Parse with `ZipFile` + `ElementTree`.

**Full debugging and template matching details:** [references/debugging.md](references/debugging.md)

## Popup Handling (macOS)

ISOLDE shows popups during sim init (disulfide Yes, unparameterised OK, map warning OK). Handle front-window-first with osascript background loop:
```bash
while true; do
    osascript -e 'tell app "ChimeraX" to click button "OK" of front window' 2>/dev/null
    osascript -e 'tell app "ChimeraX" to click button "Yes" of front window' 2>/dev/null
    sleep 2
done &
```

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

## Monitored Batch Run (recommended)

For automated runs with live convergence monitoring, use the monitored batch template.

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

ISOLDE can handle custom ligands if they are supplied as OpenMM force-field templates before simulation start. Validated pattern for a custom ligand (CHEBI:57456 precedent):

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
