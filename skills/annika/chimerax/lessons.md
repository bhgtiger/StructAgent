# ChimeraX Lessons Learned

## Batch mode (--nogui)
- Result JSON is the ONLY reliable success signal (not exit code)
- URL-encode # as %23 in all REST curl commands

## Fitting
- fitmap changes model.position (scene placement), NOT atom.coord — capture position delta
- Always center model on map before rotation search
- More rotation samples = better (500 > 100)
- Local refine after rotation search is essential

## Domain fitting
- Preserve ALL residues from previous step
- Fit domains in copies → get transforms → apply to complete original
- Discontinuous domains fitted as single unit
- Linker residues: SLERP rotation + LERP translation
- Reject fits with shift > 30Å

## File management
- Always save to NEW filename (ChimeraX caching issue)
- Use model_N_description.cif convention

## Model access
- session.models[1] is NOT always the Volume — PseudobondGroups appear as child models
- Always find Volume by isinstance check, never index-based

## Selection quirks
- `select add zone sel 5 #model` is invalid in batch mode (parser error). For union behavior in scripted runs, use Python atom-distance selection merge instead
- `session.selection.atoms()` is invalid (`Selection` has no `atoms` attr). Don't inspect selection that way; use atom-collection APIs on models

## New Notes (pending merge)
<!-- Append new tool discoveries here. Cleared after weekly merge. -->
