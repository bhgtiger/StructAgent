# Coot skill v1 scope

## Purpose

This skill is for **batch Coot 1 automation**, not full interactive Coot usage.

Default priority:
1. `coot_headless_api`
2. classic `coot --no-graphics --script`
3. GUI/manual work only if explicitly requested

## Why headless first

Upstream Coot 1 includes a newer API in `api/` exposed to Python as `coot_headless_api`.
This is the best fit for agent work because it is headless, scriptable, and focused on deterministic model/map operations.

Upstream examples indicate support for:
- `read_pdb()`
- `read_mtz()`
- `set_imol_refinement_map()`
- `refine_residue_range()`
- `mutate()`
- `delete_using_cid()`
- `copy_fragment_using_cid()`
- `write_coordinates()`
- Ramachandran / rotamer / density-correlation analysis
- hydrogen add/remove

## When to fall back to classic Coot Python

Use classic batch mode when the needed function exists only in the older embedded Python environment.

Batch invocation pattern:

```bash
coot --no-graphics --script script.py
```

Useful flags:
- `--no-state-script` for cleaner, less stateful runs
- `--python` only for specific command-line Python-mode needs; it is not the main batch path

Classic Python environment layers:
- `coot` = core bound module
- `coot_utils` = Python helper layer on top of `coot`
- `coot_gui_api` = GUI-facing module, usually not relevant for v1

## V1 in-scope tasks

### Headless lane
- load model/map
- mutate residues
- delete/copy by CID
- local residue refinement
- rotamer fitting
- validation summaries
- export updated coordinates

### Classic fallback lane
- legacy helper-driven scripts that depend on `coot_utils`
- missing headless operations discovered during implementation

## V1 out of scope

- GUI automation
- menu/widget scripting as a first-class feature
- Scheme/Guile coverage
- startup file management
- trying to replace ChimeraX, ISOLDE, or Phenix broadly

## Practical rule

If the task is a **local edit/validate/export** operation and the headless API can do it, use headless.
If the task needs an older Coot helper or embedded behavior, use classic batch mode.
If the task is highly interactive, do not pretend it is a good batch-Coot v1 task.
