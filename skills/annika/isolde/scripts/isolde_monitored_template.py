"""
ISOLDE Monitored Batch Template
================================
Runs a whole-model or partial-model ISOLDE flexible fitting with:
  - Live convergence logging (flushes each line to disk)
  - CC-based early stop (plateau detection)
  - Emergency stop + revert on CC regression
  - Hard timeout safety net
  - Proper H stripping + explicit model save

Usage:
  Configure the PARAMETERS section below, then launch via the companion
  launch_monitored.sh script. Do NOT use --nogui (ISOLDE requires GUI).

Tested on: ChimeraX 1.11, ISOLDE, Apple M4 (OpenCL), cryo-EM maps.
"""

from chimerax.core.commands import run
from chimerax.atomic import AtomicStructure
from chimerax.map import Volume
from chimerax.clipper import get_map_mgr
import threading
import time
import numpy as np

# ╔══════════════════════════════════════════════════════════════════╗
# ║  PARAMETERS — edit these for each run                          ║
# ╚══════════════════════════════════════════════════════════════════╝

# Paths
BASE = "/path/to/working/directory"            # ← EDIT
MODEL = f"{BASE}/input_model.cif"              # ← EDIT
MAP   = f"{BASE}/map.mrc"                      # ← EDIT
OUTPUT = f"{BASE}/isolde_monitored_output.cif"  # ← EDIT
LOG    = f"{BASE}/convergence_log.txt"          # ← EDIT

# Mobile selection (ChimeraX specifier, applied to the ISOLDE submodel)
# Example: "D:176-862 E:7-756 F:15-37 G:4-28"
# Leave empty string to run on entire model.
MOBILE_SPEC = ""                               # ← EDIT

# Convergence parameters
CHECK_INTERVAL     = 60    # seconds between checks
HARD_TIMEOUT       = 600   # absolute max runtime (seconds)
MIN_SOAK           = 120   # minimum run before early stop allowed
CC_PLATEAU_THRESH  = 0.002 # ΔCC below this = "flat"
CC_DROP_THRESH     = 0.005 # CC drop from peak = emergency revert
CONSEC_FLAT_NEEDED = 2     # consecutive flat windows to trigger early stop

# Platform: 'OpenCL' for Mac (M-series), 'CUDA' for NVIDIA, 'CPU' for fallback
PLATFORM = 'OpenCL'

# Pre-flight: atoms to delete before sim (set False to skip)
DELETE_OP3 = True          # 5' DNA terminal OP3
DELETE_OXT = True          # C-terminal OXT

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ENGINE — do not edit below unless you know what you're doing   ║
# ╚══════════════════════════════════════════════════════════════════╝

# ─── state ───
cc_history = []
energy_history = []
rmsd_history = []
peak_cc = -999.0
flat_window_count = 0
prev_coords = None
stop_reason = None
log_lines = []
_last_molmap_id = None
sim_start_time = None

# Start a fresh live log.
with open(LOG, 'w') as f:
    f.write("")


def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    log_lines.append(line)
    try:
        with open(LOG, 'a') as f:
            f.write(line + '\n')
            f.flush()
    except Exception:
        pass


def write_log():
    with open(LOG, 'w') as f:
        f.write('\n'.join(log_lines) + '\n')
    print(f"Convergence log saved: {LOG}")


# ─── load model + maps ───
run(session, f"open {MODEL} format mmcif")
run(session, f"open {MAP}")  # vol: given to clipper for MDFF

model = None
vol = None
for m in session.models.list():
    if isinstance(m, AtomicStructure) and model is None:
        model = m
    elif isinstance(m, Volume) and vol is None:
        vol = m

assert model is not None, "No AtomicStructure found"
assert vol is not None, "No Volume found"

# Open a SECOND copy of the map for CC measurement.
# Clipper will NOT touch this one, so its id_string stays valid.
run(session, f"open {MAP}")
cc_ref_vol = None
for m in session.models.list():
    if isinstance(m, Volume) and m is not vol:
        cc_ref_vol = m
assert cc_ref_vol is not None, "Failed to open CC reference map"

log(f"Model #{model.id_string}, ISOLDE map #{vol.id_string}, CC ref map #{cc_ref_vol.id_string}")

# ─── pre-flight cleanup ───
if DELETE_OP3:
    try:
        run(session, f"delete #{model.id_string} @OP3")
        log("Deleted OP3 atoms")
    except Exception as e:
        log(f"OP3 delete note: {e}")

if DELETE_OXT:
    try:
        run(session, f"delete #{model.id_string} @OXT")
        log("Deleted OXT atoms")
    except Exception as e:
        log(f"OXT delete note: {e}")

run(session, f"addh #{model.id_string}")
log("Hydrogens added")

# ─── ISOLDE init ───
run(session, "isolde start")
run(session, f"isolde select #{model.id_string}")
ih = session.isolde

# ─── debug monkey-patch (prints unassigned residues on template failure) ───
try:
    from chimerax.isolde.openmm.openmm_interface import SimHandler
    _original_create = SimHandler._create_openmm_system

    def _patched_create(self, *args, **kwargs):
        try:
            return _original_create(self, *args, **kwargs)
        except Exception as e:
            print("=== OPENMM TEMPLATE FAILURE ===")
            print(repr(e))
            try:
                ff = self._forcefield
                top = self._topology
                assigned, ambiguous, unassigned = ff.assignTemplates(top)
                print(f"Assigned: {len(assigned)}")
                if ambiguous:
                    print(f"Ambiguous: {len(ambiguous)}")
                    for res, templates in ambiguous.items():
                        print(f"  AMBIG {res.name} {res.id}: {[t.name for t in templates]}")
                if unassigned:
                    print(f"Unassigned: {len(unassigned)}")
                    for res, templates in unassigned.items():
                        print(f"  UNASSIGNED {res.name} {res.id}: {[t.name for t in templates]}")
            except Exception as e2:
                print(f"assignTemplates failed too: {e2!r}")
            raise
    SimHandler._create_openmm_system = _patched_create
    log("Installed OpenMM debug monkey-patch")
except Exception as e:
    log(f"Monkey-patch note: {e!r}")

# ─── map association (only vol, NOT cc_ref_vol) ───
mmgr = get_map_mgr(model)
nxmapset = mmgr.nxmapset
nxmapset.add_nxmap_handler_from_volume(vol)
log(f"Map associated. has_maps={ih.selected_model_has_maps} mdff={ih.selected_model_has_mdff_enabled}")
assert ih.selected_model_has_maps, "ABORT: model has no associated maps"
assert ih.selected_model_has_mdff_enabled, "ABORT: MDFF not enabled"

# Verify cc_ref_vol survived clipper setup
try:
    test_id = cc_ref_vol.id_string
    log(f"CC ref map still valid: #{test_id}")
except Exception:
    log("WARNING: CC ref map invalidated after clipper setup — CC monitoring will be disabled")

# ─── platform ───
ih.sim_params.platform = PLATFORM
log(f"Platform: {ih.sim_params.platform}")

# ─── select mobile region + start sim ───
if MOBILE_SPEC:
    # Build specifiers relative to the ISOLDE submodel
    parts = MOBILE_SPEC.split()
    sim_sel = " ".join(f"#{model.id_string}/{p}" if '/' not in p else f"#{model.id_string}/{p.split('/', 1)[1]}" for p in parts)
    # Simpler: let the user provide chain:range specs, prefix with model id
    sim_sel = " ".join(f"#{model.id_string}/{p.strip()}" for p in MOBILE_SPEC.split())
    run(session, f"sel {sim_sel}")
    log(f"Mobile: {sim_sel}")
    run(session, "isolde sim checkpoint")
    run(session, "isolde sim start sel")
else:
    run(session, "isolde sim checkpoint")
    run(session, "isolde sim start")
    log("Mobile: entire model")

log(f"ISOLDE sim started — monitored run (hard cap {HARD_TIMEOUT}s)")
sim_start_time = time.time()

# Capture initial Cα coordinates for RMSD tracking
try:
    ca_atoms = model.atoms[model.atoms.names == 'CA']
    prev_coords = ca_atoms.coords.copy()
    log(f"Captured initial Cα coords ({len(ca_atoms)} atoms)")
except Exception as e:
    log(f"Initial coords capture failed: {e}")


# ─── helper: compute whole-model CC ───
def compute_cc():
    """Compute whole-model CC via molmap + measure correlation.

    Uses cc_ref_vol (a second copy of the map, never given to clipper)
    as the reference. Tracks molmap volumes by Python id() to clean up.
    """
    global _last_molmap_id
    try:
        # Clean up previous molmap if it still exists
        if _last_molmap_id is not None:
            for m in session.models.list():
                if id(m) == _last_molmap_id:
                    try:
                        run(session, f"close #{m.id_string}")
                    except Exception:
                        pass
                    break
            _last_molmap_id = None

        # Snapshot existing volumes before molmap
        existing_vol_ids = set(id(m) for m in session.models.list() if isinstance(m, Volume))

        # Create molmap from current atom positions
        run(session, f"molmap #{model.id_string} 3.5")

        # Find the newly created molmap volume
        molmap_vol = None
        for m in session.models.list():
            if isinstance(m, Volume) and id(m) not in existing_vol_ids:
                molmap_vol = m
                break
        if molmap_vol is None:
            log("CC error: molmap volume not found after creation")
            return None

        _last_molmap_id = id(molmap_vol)

        # Measure correlation against CC reference map
        result = run(session,
                     f"measure correlation #{molmap_vol.id_string} inMap #{cc_ref_vol.id_string}")

        # Clean up molmap immediately
        try:
            run(session, f"close #{molmap_vol.id_string}")
            _last_molmap_id = None
        except Exception:
            pass

        # Parse result
        if isinstance(result, (list, tuple)) and len(result) >= 1:
            return float(result[0])
        elif isinstance(result, (int, float)):
            return float(result)
        log(f"CC parse warning: unexpected return type {type(result).__name__}: {result}")
        return None
    except Exception as e:
        log(f"CC computation error: {e}")
        return None


# ─── helper: get map potential energy ───
def get_map_energy():
    """Get MDFF map potential energy from OpenMM (cheap proxy for fit quality)."""
    try:
        sh = ih.sim_handler
        if sh is None or not sh.sim_running:
            return None
        from openmm import unit as omm_unit
        state = sh._context.getState(getEnergy=True, groups={5})
        return state.getPotentialEnergy().value_in_unit(omm_unit.kilojoule_per_mole)
    except Exception as e:
        log(f"Map energy error: {e}")
        return None


# ─── helper: Cα RMSD vs previous snapshot ───
def get_ca_rmsd():
    """Compute Cα RMSD between current and previous checkpoint."""
    global prev_coords
    try:
        ca_atoms = model.atoms[model.atoms.names == 'CA']
        coords_now = ca_atoms.coords.copy()
        if prev_coords is None:
            prev_coords = coords_now
            return 0.0
        rmsd = float(np.sqrt(np.mean(np.sum((coords_now - prev_coords)**2, axis=1))))
        prev_coords = coords_now
        return rmsd
    except Exception as e:
        log(f"RMSD error: {e}")
        return None


# ─── convergence monitor ───
def convergence_check():
    global peak_cc, flat_window_count, stop_reason

    elapsed = time.time() - sim_start_time

    if not ih.simulation_running:
        reason = getattr(ih, 'sim_termination_reason', 'unknown')
        log(f"SIM NOT RUNNING at {elapsed:.0f}s — reason: {reason}")
        stop_reason = f"sim_died:{reason}"
        do_save()
        return

    # Collect metrics
    map_e = get_map_energy()
    rmsd = get_ca_rmsd()
    cc = compute_cc()

    energy_history.append(map_e)
    rmsd_history.append(rmsd)
    cc_history.append(cc)

    cc_str = f"{cc:.4f}" if cc is not None else "None"
    e_str = f"{map_e:.1f}" if map_e is not None else "None"
    r_str = f"{rmsd:.4f}" if rmsd is not None else "None"
    log(f"CHECK @ {elapsed:.0f}s | CC={cc_str} | map_E={e_str} | Cα_RMSD={r_str}Å | flat_windows={flat_window_count}/{CONSEC_FLAT_NEEDED}")

    # ─── early stop logic (only after MIN_SOAK) ───
    if elapsed >= MIN_SOAK and cc is not None:
        # Update peak
        if cc > peak_cc:
            peak_cc = cc

        # Emergency stop: CC dropped from peak
        if peak_cc - cc > CC_DROP_THRESH:
            log(f"⚠️ EMERGENCY STOP: CC dropped {peak_cc - cc:.4f} from peak {peak_cc:.4f}")
            stop_reason = f"cc_drop:peak={peak_cc:.4f},now={cc}"
            try:
                run(session, "isolde sim revert")
                log("Reverted to checkpoint (pre-drop state)")
            except Exception as e:
                log(f"Revert failed: {e}, stopping normally")
                run(session, "isolde sim stop")
            do_save()
            return

        # Plateau check: ΔCC < threshold
        if len(cc_history) >= 2 and cc_history[-2] is not None:
            delta_cc = abs(cc - cc_history[-2])
            if delta_cc < CC_PLATEAU_THRESH:
                flat_window_count += 1
                log(f"  Flat window #{flat_window_count}: ΔCC={delta_cc:.5f}")
            else:
                flat_window_count = 0
                log(f"  CC still moving: ΔCC={delta_cc:.5f}")

            if flat_window_count >= CONSEC_FLAT_NEEDED:
                log(f"✅ EARLY STOP: CC plateau ({CONSEC_FLAT_NEEDED} consecutive flat windows)")
                stop_reason = f"cc_plateau:{CONSEC_FLAT_NEEDED}_flat_windows"
                try:
                    run(session, "isolde sim stop")
                except Exception:
                    pass
                do_save()
                return

    # Schedule next check (unless we'll hit hard timeout)
    next_check = elapsed + CHECK_INTERVAL
    if next_check < HARD_TIMEOUT:
        threading.Timer(CHECK_INTERVAL, lambda: session.ui.thread_safe(convergence_check)).start()


def do_save():
    """Stop sim if running, strip H, save model + write final log."""
    time.sleep(3)
    try:
        if ih.simulation_running:
            run(session, "isolde sim stop")
            log("Simulation stopped")
            time.sleep(3)
    except Exception as e:
        log(f"Stop note: {e}")

    # Delete hydrogens using Python API
    # (ChimeraX specifier 'element.H' is unreliable — use atomic number)
    try:
        h_mask = model.atoms.elements.numbers == 1
        h_atoms = model.atoms[h_mask]
        n_h = len(h_atoms)
        if n_h > 0:
            h_atoms.delete()
            log(f"Deleted {n_h} hydrogen atoms")
        else:
            log("No hydrogen atoms found to delete")
    except Exception as e:
        log(f"Delete H note: {e}")
    time.sleep(2)

    # Close the CC reference map before saving
    try:
        run(session, f"close #{cc_ref_vol.id_string}")
        log("Closed CC reference map")
    except Exception as e:
        log(f"Close CC ref note: {e}")

    # Explicit save: specify model ID + format to avoid saving extra objects
    run(session, f"save {OUTPUT} models #{model.id_string} format mmcif")
    log(f"Saved: {OUTPUT} (models #{model.id_string})")

    # Summary
    log("")
    log("=== CONVERGENCE SUMMARY ===")
    log(f"Stop reason: {stop_reason}")
    log(f"Total time: {time.time() - sim_start_time:.0f}s")
    log(f"CC history: {[f'{c:.4f}' if c is not None else 'None' for c in cc_history]}")
    log(f"Map energy history: {[f'{e:.1f}' if e is not None else 'None' for e in energy_history]}")
    log(f"RMSD history: {[f'{r:.4f}' if r is not None else 'None' for r in rmsd_history]}")
    if cc_history and any(c is not None for c in cc_history):
        valid_cc = [c for c in cc_history if c is not None]
        log(f"Final CC: {valid_cc[-1]:.4f}")
        log(f"Peak CC: {max(valid_cc):.4f}")
    else:
        log("Final CC: None (all measurements failed)")
    write_log()


# ─── hard timeout ───
def hard_timeout():
    def _do():
        global stop_reason
        if stop_reason is not None:
            return  # already stopped by convergence check
        elapsed = time.time() - sim_start_time
        log(f"⏱️ HARD STOP at {elapsed:.0f}s ({HARD_TIMEOUT}s limit)")
        stop_reason = f"hard_timeout_{HARD_TIMEOUT}s"
        try:
            if ih.simulation_running:
                run(session, "isolde sim stop")
        except Exception as e:
            log(f"Hard stop note: {e}")
        do_save()
    session.ui.thread_safe(_do)


threading.Timer(HARD_TIMEOUT, hard_timeout).start()
log(f"Hard timeout armed: {HARD_TIMEOUT}s")

# ─── first convergence check ───
threading.Timer(CHECK_INTERVAL, lambda: session.ui.thread_safe(convergence_check)).start()
log(f"Convergence monitor armed: check every {CHECK_INTERVAL}s")
log(f"Early stop: ΔCC < {CC_PLATEAU_THRESH} for {CONSEC_FLAT_NEEDED} consecutive windows")
log(f"Emergency stop: CC drop > {CC_DROP_THRESH} from peak")
log(f"Min soak: {MIN_SOAK}s before early stop allowed")
