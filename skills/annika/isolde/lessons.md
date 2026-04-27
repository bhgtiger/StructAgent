# ISOLDE Lessons Learned

## Core Rules
- ISOLDE requires GUI mode — `--nogui` does NOT work
- Handler: `ih = session.isolde` (NOT `session_extensions.get_isolde_handler`)
- "Sim termination reason: None" = silent crash — monkey-patch `_create_openmm_system`
- REST hangs during active sim (Qt event loop blocked) — use Python `threading.Timer` inside ChimeraX via `session.ui.thread_safe()`
- Don't `close all` + reload during workflow — disrupts MDFF setup

## Map Association (CRITICAL)
- `from chimerax.clipper import get_map_mgr; mmgr = get_map_mgr(model); nxmapset = mmgr.nxmapset; nxmapset.add_nxmap_handler_from_volume(vol)`
- Verify: `ih.selected_model_has_maps == True` AND `ih.selected_model_has_mdff_enabled == True`
- Without map association → pure MD, model drifts AWAY from density

## Pre-flight Checklist
- All residues have correct H atoms (especially metal-coordinating CYS/HIS)
- OP3 removed from 5' DNA terminals
- C-terminal OXT deleted from CYS residues
- Platform set: `ih.sim_params.platform = 'OpenCL'` (Mac mini: Reference, CPU, OpenCL available; HIP wrong)
- Monitor sim status every 30s with `ih.simulation_running`

## Ligand Handling
- ISOLDE uses OpenMM forcefield templates, NOT Phenix `.edits`
- Gemmi mmCIF drops non-polymer entities — save ligands as PDB, load separately, combine
- ADP template (MC_ADP): expects 39 atoms, 41 bonds
  - `addh` names C5' H wrong: H5'/H5'' → must be H5'1/H5'2
  - `addh` may create spurious atoms/bonds → verify against template
- Metal ions (MG, ZN): already in ISOLDE's `metal_name_map`
- Don't create explicit covalent bonds to metals — breaks template matching
- CYS near metals: `cys_type()` checks SG bond count (1=CYM, SG-SG=CYX, SG-H=CYS)
- HIS backbone H after addh: may skip H on residues after PRO/chain breaks → add manually

## Selection API
- `session.selection.atoms()` is INVALID (`Selection` has no `atoms` attr) — use atom-collection APIs on models instead

## Local Fragment Runs
- Local-fragment ISOLDE runs can fail target-chain selections after clipper map association (ID/chain remapping)
- Robust fallback: run on full model+map, then select local zone (e.g., chain T window + 5 Å neighborhood) before `isolde sim start sel`

## Sub-agent Limitations
- Spawning ISOLDE via sub-agents fails — REST + GUI + timer + popup handling is too complex for limited-context sub-agents
- Always run ISOLDE from the main session

## Debugging
- Unparameterised residue: patch `_create_openmm_system` → `forcefield.assignTemplates()` → print unassigned
- Monkey-patch import path: `from chimerax.isolde.openmm.openmm_interface import SimHandler` (NOT `isolde.openmm.sim_handler`)
- REST port stuck after crash → use different port (9877)
- Template verification: ISOLDE templates in `moriarty_and_case.zip` (parse with `ZipFile` + `ElementTree`)
- Popup handling: osascript background loop, front window first

## Post-ISOLDE
- Remove hydrogens via Python API: `model.atoms[model.atoms.elements.numbers == 1].delete()`
  - Do NOT use `delete element.H` — throws "invalid atoms specifier"
- Always report output filename to user
- Explicit save: `save OUTPUT models #model.id_string format mmcif` — prevents saving extra objects

## Phosphorothioate DNA
- **ISOLDE CANNOT RUN on PST/SC/AS/GS.** OpenMM has no forcefield templates. Even renaming to standard DNA + S→O doesn't work (sulfur positions/bond geometry still break template matching). "Sim termination reason: None" = instant crash. Only workaround: custom OpenMM XML templates
- Use mutate-refine-mutate-back strategy with Phenix instead (see structural-strategy special-cases)

## Monitored Batch Runs
- **CC measurement requires a second map copy.** Clipper takes ownership of the vol given to `add_nxmap_handler_from_volume()`. After association, the original vol's `id_string` becomes invalid for `measure correlation`. Open the map twice: one for clipper, one untouched for CC.
- **Live log flushing:** Write each line to disk immediately with `open(LOG, 'a')` + `flush()`. Without this, log only appears when the run completes — useless for monitoring.
- **Single-instance launcher lock:** Use a PID lock file + `trap cleanup EXIT INT TERM`. Without this, re-running the launcher while an old shell is hanging spawns a duplicate ChimeraX with two competing scripts.
- **ISOLDE submodel:** After `isolde select`, ISOLDE creates a submodel (e.g., `#1.2`). Save `#model.id_string` which resolves to the parent including submodels. Saving only `#1.2` loses non-simulated atoms.
- **Convergence timing:** On M4 OpenCL, whole-complex sims (~32k atoms including H) typically converge within 2-5 min. 10-min hard cap is generous; 5 min usually sufficient.
- **molmap cleanup:** Track molmap volumes by Python `id()` to find and close them. Avoid `close #N-M` range commands — they can close unrelated models.

## Apple M4 OpenCL Precision
- OpenMM/OpenCL can appear "unavailable" if code forces **mixed precision**. On M4, OpenCL is reliable in **single precision**; forcing mixed causes false CPU fallback ("No compatible OpenCL platform").
- **Workaround:** Don't hard-code mixed; implement a precision fallback chain (mixed → single) and/or a short smoke-test to confirm the chosen platform/precision actually runs.

## Distilled 2026-04-03

### Monitored batch early-stop guardrails (parameter choices)
- **Check cadence:** 60 s between CC checks (keeps overhead low, still responsive).
- **Plateau stop:** trigger when **ΔCC < 0.002** for **2 consecutive windows**.
- **Minimum soak:** enforce **≥120 s** runtime before any early-stop logic can fire (avoids stopping during startup/transient settling).
- **Emergency stop:** abort if CC drops **> 0.005** from the peak (catches divergence/regressions quickly).

## New Notes (pending merge)
<!-- Append new tool discoveries here. Cleared after weekly merge. -->
