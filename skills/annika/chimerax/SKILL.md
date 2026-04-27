---
name: chimerax
description: "Automate UCSF ChimeraX on macOS for structural biology: fitting, superposition, measurements, and model editing (delete, mutate, renumber, combine, dockprep, etc.). Runs one-shot batch jobs via --nogui --script with structured JSON results. Use when the user asks to fit a model into a map, superpose structures, edit PDB/mmCIF models, or run ChimeraX commands from the terminal."
---

# ChimeraX Skill

Automate ChimeraX (≥1.8) on macOS. Analysis + model editing only — no rendering in v1.

## Binary Discovery

```bash
CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)
```

## Invocation

**Always one-shot. Never interactive, never REST (use isolde skill for REST).**

```bash
JOBDIR=$(mktemp -d /tmp/chimerax_job_XXXX)
cat > "$JOBDIR/job.json" << 'EOF'
{ "resultFile": "$JOBDIR/result.json", "commands": [...] }
EOF
"$CHIMERAX" --nogui --exit --script scripts/wrapper.py "$JOBDIR/job.json"
cat "$JOBDIR/result.json"
```

Flags (always all three): `--nogui` (no graphics), `--exit` (prevent zombies), `--script` (run wrapper).

For tasks needing loops/branching, write a standalone `.py` script instead of using the wrapper.

## Job File Schema

```json
{
  "resultFile": "/tmp/chimerax_job_abc/result.json",
  "commands": [
    "open /path/to/model.cif",
    {"cmd": "matchmaker #1 to #2", "capture": true},
    {"cmd": "delete /C", "abort": false},
    "save /path/to/output.cif"
  ]
}
```

Each command entry: **string** (abort on failure) or **object** with `cmd`, optional `capture` (extract return value), optional `abort` (default `true`).

## Result File

```json
{ "ok": true, "n": 4, "results": [{"i": 0, "cmd": "...", "ok": true, "return": {...}}, ...] }
```

**Result file is the ONLY reliable success signal.** Exit code 0 doesn't guarantee success. If no result file → treat as crash.

## Critical Rules

1. **Start every job with `close all`** to reset model numbering
2. **Never hardcode model numbers across open/delete** — IDs don't renumber after delete
3. **Use explicit format**: `open file.cif format mmcif` (avoid guessing bugs)
4. **Prefer `.cif` over `.pdb`** for saves
5. **URL-encode `#` as `%23`** when sending via curl/REST
6. **Always save to a NEW filename** — ChimeraX caches files; reopening an overwritten file may return old data
7. **Never parse stdout** — polluted with banners, warnings, OpenGL noise
8. **Find models by type or explicit ID, not list index** — `session.models` may include PseudobondGroups and child models.

## Fitting: The Position Trap (Critical)

**`fitmap` changes `model.position` (scene transform), NOT `atom.coord`.**

After `fitmap`, atom coordinates in the model are unchanged. You must capture the position delta:

```python
pre_pos = model.position
run(session, "fitmap #1 inMap #2")
post_pos = model.position
delta = post_pos * pre_pos.inverse()
# Apply to atoms explicitly:
atoms.coords = delta.transform_points(atoms.coords)
```

This matters for domain-wise fitting where you need to apply transforms to specific residues in a complete model.

## Domain-Wise Fitting Pattern

For per-domain rigid-body fitting:
1. Open fresh copy of complete model for each domain
2. Delete non-domain residues
3. `fitmap search 100 radius 5` + local `fitmap`
4. Capture `model.position` delta
5. Apply delta to domain residues in the original complete model
6. **Linker residues:** interpolate transforms (SLERP rotation + LERP translation) from flanking domains
7. **DNA:** local `fitmap` only (no search — DNA jumps to wrong density)
8. **Discontinuous domains** (e.g., `E:487-570+669-756`): fit as single unit
9. **Sanity check:** reject any domain fit with shift > 30 Å

**Key principle:** Never extract + reassemble domains. Fit copies to get transforms, apply to complete model. This preserves linkers and unassigned residues.

## Pitfalls

- **Model numbering drift**: After `open A` → `open B` → `delete #1`, B is still `#2`
- **Closed model IDs are not reused**: after `close #N`, the next `open` gets `N+1` or the next available ID. Do not assume closed IDs become free.
- **Chain IDs are case-sensitive**: `/A` ≠ `/a`
- **macOS --nogui cannot save images/movies**
- **Centering matters**: Always center model on map before global rotation search

## Coordinate Frames

- `atom.coord` is model-local coordinates.
- `atom.scene_coord` is coordinates after scene transforms (e.g. `matchmaker`, `fitmap`, manual placement).
- When extracting coordinates from a superposed or fitted reference, write `scene_coord`; using `coord` will silently export the unfitted local frame.

## Ligand / Local Density Fitting Notes

## Extraction / Saving Caveats

- `save path #N/A:901` selects chain A residue 901 but may still write source-model context such as headers/full chain context. For extracting only specific HETATM records, write the records directly via Python instead of relying on `save` selection semantics.

- `fitmap #lig inMap #vol metric correlation` requires `resolution R` for atomic-model fitting.
- For local ligand refinement, prefer `fitmap ... metric correlation resolution R maxSteps 120` **without** `search`; reject fits whose centroid drifts >10 Å from the expected site midpoint.
- Global `search` on isolated ligands at ≥3 Å can jump to stronger off-target density. If a reference structure exists, place the ligand by `matchmaker` transfer and let real-space refinement optimize it.
- For per-chain ligand transfer, open fresh copies of the reference structure up front, match each copy to a different target chain, and extract ligand `scene_coord` from each copy. Avoid close/reopen loops because model IDs drift.

## Custom Density Metrics

- Phenix does not provide reliable EM per-atom CC in this workflow. ChimeraX can sample a map directly with `vol.interpolated_values(pts)` on a cubic grid around each atom, then correlate observed values against a Gaussian atom model.
- `vol.full_matrix()` returns the map numpy array; `float(m.mean()), float(m.std())` are useful for global z-score normalization.

## Command Reference & Examples

Load [references/commands.md](references/commands.md) for:
- Full atom specifier syntax
- All command tables (I/O, fitting, measurement, editing, transforms)
- Timeout guidance per command
- Job JSON examples

## What's NOT in v1

Rendering (images/movies), REST mode (use isolde skill), missing loop building, ligand docking (use `emerald` for cryo-EM density-guided docking), solvation.
