# Monitored Batch ISOLDE Runs

## Overview

Run ISOLDE flexible fitting with live convergence monitoring, automatic early stop on plateau, emergency revert on CC regression, and hard timeout safety net.

**Template:** `scripts/isolde_monitored_template.py`
**Launcher:** `scripts/launch_monitored.sh`

## Architecture

```
launch_monitored.sh
  ├── single-instance lock file
  ├── popup auto-clicker (osascript background loop)
  └── ChimeraX --cmd "runscript script.py"
        ├── load model + ISOLDE map (for MDFF via clipper)
        ├── load CC reference map (second copy, clipper-free)
        ├── pre-flight: delete OP3/OXT, addh
        ├── ISOLDE init + map associate + MDFF verify
        ├── start sim (full or selection)
        ├── threading.Timer loop (every CHECK_INTERVAL):
        │     ├── compute CC (molmap + measure correlation vs cc_ref_vol)
        │     ├── read map energy (OpenMM force group 5)
        │     ├── compute Cα RMSD vs previous snapshot
        │     └── check stop conditions
        ├── hard timeout (threading.Timer at HARD_TIMEOUT)
        └── do_save: stop sim → strip H → close cc_ref → save → write log
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CHECK_INTERVAL` | 60s | Time between convergence checks |
| `HARD_TIMEOUT` | 600s | Absolute max runtime |
| `MIN_SOAK` | 120s | Minimum run before early stop allowed |
| `CC_PLATEAU_THRESH` | 0.002 | ΔCC below this = "flat" |
| `CC_DROP_THRESH` | 0.005 | CC drop from peak → emergency revert |
| `CONSEC_FLAT_NEEDED` | 2 | Consecutive flat windows to trigger early stop |
| `PLATFORM` | OpenCL | OpenMM platform (OpenCL for Mac M-series) |

## CC Measurement Pattern

**Problem:** Clipper takes ownership of the map volume given to `nxmapset.add_nxmap_handler_from_volume(vol)`. After association, the volume's `id_string` may change or become invalid, breaking `measure correlation`.

**Solution:** Open the map file **twice**:
1. First copy → given to clipper for MDFF
2. Second copy (`cc_ref_vol`) → never touched by clipper, used only for CC measurement

At each check:
1. `molmap #model 3.5` → creates a simulated density from current coordinates
2. `measure correlation #molmap inMap #cc_ref_vol` → CC against untouched map copy
3. Clean up molmap volume immediately

Track molmap volumes by Python `id()` to avoid dangerous `close #N-M` range commands.

## Stop Conditions

| Condition | When | Action |
|-----------|------|--------|
| CC plateau | ΔCC < 0.002 for 2 consecutive 60s windows (after 2 min soak) | `isolde sim stop` → save |
| CC regression | CC drops > 0.005 from peak CC seen so far | `isolde sim revert` → save checkpoint state |
| Hard timeout | Elapsed > HARD_TIMEOUT | `isolde sim stop` → save |
| Sim crash | `ih.simulation_running == False` unexpectedly | Save whatever we have |

## Live Logging

Every `log()` call flushes to `convergence_log.txt` immediately. Monitor during the run:
```bash
tail -f convergence_log.txt
```

Log format:
```
[HH:MM:SS] CHECK @ 60s | CC=0.7832 | map_E=-278162.5 | Cα_RMSD=1.3495Å | flat_windows=0/2
```

## Hydrogen Handling

**Delete H via Python API, not ChimeraX specifier:**
```python
h_mask = model.atoms.elements.numbers == 1
h_atoms = model.atoms[h_mask]
h_atoms.delete()
```

The ChimeraX specifier `delete element.H` is unreliable and throws "invalid atoms specifier" errors.

## Save Pattern

**Always explicit:**
```python
run(session, f"save {OUTPUT} models #{model.id_string} format mmcif")
```

Without `models #id`, ChimeraX may save extra objects (cc_ref_vol, molmap leftovers). Without `format mmcif`, it may default to a different format.

## Usage

1. Copy `scripts/isolde_monitored_template.py` to your working directory
2. Edit the PARAMETERS section (paths, mobile selection, timing)
3. Run:
   ```bash
   bash /path/to/launch_monitored.sh /path/to/your_script.py
   ```
4. Monitor: `tail -f convergence_log.txt`
5. Output: model CIF + convergence_log.txt

## Known Limitations

- ISOLDE requires GUI mode — `--nogui` will fail
- CC computation adds ~4s per check (molmap creation + correlation)
- Map energy (OpenMM force group 5) is a cheap proxy but not a substitute for CC
- Cα RMSD is vs previous snapshot (not vs start), so it shows per-interval movement
- The monkey-patch for template debugging won't survive if ISOLDE reloads the module
- Duplicate launch protection requires the lock file cleanup trap to fire (kill -9 can leave stale locks)

## Tuning Guide

| Scenario | Adjustment |
|----------|------------|
| Large model (>50k atoms) | Increase HARD_TIMEOUT to 1200-1800s |
| Very flexible regions | Increase MIN_SOAK to 180-300s |
| High-resolution map (<2.5 Å) | Tighten CC_PLATEAU_THRESH to 0.001 |
| Low-resolution map (>4 Å) | Relax CC_PLATEAU_THRESH to 0.003-0.005 |
| Quick test run | Set HARD_TIMEOUT=120, MIN_SOAK=60 |
