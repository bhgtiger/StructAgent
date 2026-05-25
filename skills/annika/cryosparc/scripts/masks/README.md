# scripts/masks — Headless ChimeraX Mask-Base Helpers

File-local helpers for generating cryoSPARC mask bases off-instance. They are run **inside ChimeraX** via `--nogui --exit --script <path>` and do **not** touch any cryoSPARC instance — no credentials, no session, no network calls. See `../../references/20a_mask_generation_chimerax.md` for the full workflow, parameters, ChimeraX command caveats, and CryoSPARC handoff guidance.

## Binary discovery

The scripts do **not** hardcode a ChimeraX install path. The caller (user or wrapper) picks which ChimeraX to invoke. ChimeraX ≥ 1.8 is required.

On macOS, a reasonable default:

```bash
CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)
```

On Linux, use whatever `chimerax`/`ChimeraX` is on `$PATH`, or pass an explicit path.

## Scripts

| Script | Purpose |
|---|---|
| `make_mask_from_model.py` | Primary: `molmap` from a model selection → optional binarize/dilate → soft edge → resample onto target map's grid. |
| `make_mask_from_map.py` | No-model fallback: Gaussian blur + threshold + optional dilate + soft edge. Low confidence; flag in answers. |
| `make_complement_mask.py` | `full − region` → soft, clamped, resampled mask for cryoSPARC Particle Subtraction. |

## Output contract (sidecar JSON)

Every script writes `<out>.mrc` plus a sidecar `<out>.mrc.json` with the shape:

```json
{
  "ok": true,
  "params": { "<arg>": "<value>", "...": "..." },
  "stats":  { "apix": 1.06, "box": [380, 380, 380], "origin": [...], "selected_atoms": 1234, "molmap_max": 0.9, "threshold_used": 0.45, "soft_A": 17.0, "final_box": [380, 380, 380] }
}
```

On failure: `{"ok": false, "params": ..., "stats": ..., "error": "<msg>", "traceback": "<tb>"}`.

**Check the sidecar — not the exit code.** ChimeraX batch runs sometimes exit 0 on internal errors.

## Quick examples

```bash
# model → mask base (preferred when an atomic model is available)
"$CHIMERAX" --nogui --exit --script make_mask_from_model.py -- \
  --model model.cif --selection "/A:120-340" \
  --target-map refined_map.mrc --resolution 16 --out mask_base.mrc

# map → mask base (no model, low confidence)
"$CHIMERAX" --nogui --exit --script make_mask_from_map.py -- \
  --map refined_map.mrc --sdev 2.0 --threshold 0.05 --soft 4.0 \
  --out mask_base.mrc

# complement for particle subtraction
"$CHIMERAX" --nogui --exit --script make_complement_mask.py -- \
  --full mask_full.mrc --region mask_R.mrc \
  --target-map refined_map.mrc --out mask_subtraction.mrc
```

## Why not Segger / Volume Eraser?

Both require GUI interaction; they cannot be reliably scripted. Use `molmap` whenever a model exists; fall back to the map-only script otherwise. The GUI methods are documented in `../../references/20a_mask_generation_chimerax.md` for completeness.
