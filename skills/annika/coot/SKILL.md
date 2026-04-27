---
name: coot
description: Practical Coot 1 workflows for macromolecular model building, local rebuilding, ligand/monomer handling, density-guided cleanup, waters/peaks inspection, validation, dictionaries/restraints, and Coot-specific scripting. Use when the task should be done with Coot rather than ChimeraX/ISOLDE/Phenix, especially for ligand fitting, local residue/fragment cleanup, water finding/pruning, awkward rebuild jobs, weird chemistry, or source-backed Coot automation. Prefer modular lane selection: headless/newer API when clearly supported, classic `coot --no-graphics --script` for the broad documented scripting surface, and GUI/manual Coot only when the task is genuinely interactive or underdocumented for automation.
---

# Coot

Treat this skill as the **practical Coot toolbox**, not a thin wrapper around one API.

## Core rule

Choose the execution lane **per module**, not by ideology.

Execution lanes:
1. **Headless / newer API** — use when support is clear and the task is deterministic.
2. **Classic Coot scripting** — use for the broad documented scripting surface and batch jobs such as `coot --no-graphics --script`.
3. **GUI/manual Coot** — use only for genuinely interactive work or features with weak/unclear automation support.
4. **External helper / integration** — use when the real Coot workflow depends on Refmac, SHELXL, findligand, dictionary generators, or related helpers.

## What this skill should cover

Aim for broad practical Coot coverage across these module families:

1. **Core I/O + model/map setup**
   - load coordinates, maps, MTZ/CIF-derived data as appropriate
   - choose/set active refinement map
   - write/export updated coordinates and maps

2. **Local editing + rebuild**
   - delete/copy fragments
   - mutate / renumber / chain edits
   - awkward local cleanup and fragment-level repair

3. **Refinement + fitting**
   - regularization / local real-space refinement
   - residue- and fragment-level fitting
   - rotamers / peptide fixes / sidechain docking

4. **Ligands + monomers**
   - CIF dictionary loading
   - monomer retrieval/import
   - ligand fitting / flipping / ligand-neighborhood cleanup
   - ligand-focused validation/reporting

5. **Waters + peaks + ions**
   - water finding / pruning / refine-all-waters style work
   - difference-map peaks / blobs / candidate-site inspection
   - ion-like local density work only when support is real enough

6. **Chemistry + restraints**
   - non-standard residues
   - weird chemistry and dictionary/restraint handling
   - carbohydrate / ring / nomenclature / occupancy-sensitive tasks

7. **Validation + diagnostics**
   - Ramachandran / geometry / rotamer / density-fit / clash-style summaries
   - local validation around edited regions

8. **External integrations**
   - only when they improve real Coot use rather than duplicating other skills badly

## Routing

### Prefer headless / newer API for
- narrow, deterministic batch tasks with clearly confirmed support
- clean read/edit/write/report jobs
- workflows already validated against source or runtime tests

### Prefer classic Coot scripting for
- the broadest documented automation surface
- legacy/upstream helper-driven workflows
- tasks described in manual + documented scripting interface but not clearly proven in newer/headless API
- practical batch jobs via `coot --no-graphics --script`

### Prefer GUI/manual Coot for
- highly interactive rebuilds
- tasks centered on visual judgment, picking, or iterative manual placement
- features that are documented mainly as GUI workflows and not yet source-confirmed as good automation targets

### Prefer external helpers when
- the real Coot workflow explicitly depends on them
- they provide chemistry/dictionary/fitting support that Coot expects upstream
- a helper can make the Coot-facing step cleaner or safer than forcing everything through Coot itself
- you want refinement/acceptance behavior that is more trusted than the current local classic Coot scripting path

Typical helper choices:

**Refinement engines (choose by context):**
- **Servalcat `refine_spa`** — preferred for cryo-EM refinement (wraps Refmac5 with proper half-map handling, FSC weighting, B-factor estimation). Use for final refinement rounds and deposition-quality runs.
- **Phenix `real_space_refine`** — preferred for intermediate cleanup (rotamer fitting, Ramachandran restraints, morphing, local geometry fixes). Use between manual building rounds.
- **Raw Refmac** — preferred for X-ray crystallography, or when fine-grained Refmac keyword control is needed (TLS, twin refinement, NCS).
- **Servalcat `refine_geom`** — geometry-only cleanup without a map. Good as a quick post-Coot sanity pass.

**Recommended cryo-EM pipeline:**
```
Coot edit → Phenix RSR (intermediate cleanup) → iterate
   ...when happy...
→ Servalcat refine_spa (final refinement) → validate → deposit
```

**Prep / conversion / inspection:**
- **gemmi** — mmCIF/PDB conversion, header/cell repair, map slicing, residue queries. Fast, clean, scriptable (CLI + Python). Use freely for prep tasks; no skill needed.

**Validation:**
- **Servalcat `fofc`** — Fo-Fc / difference map calculation from half-maps
- **Servalcat `fsc`** — map-model FSC calculation
- **Servalcat `localcc`** — local correlation maps
- **Phenix MolProbity** — geometry validation (clashes, rotamers, Ramachandran)

**Chemistry / ligands:**
- **AceDRG** (CCP4) — ligand restraint CIF generation, Refmac-native format
- **eLBOW** (Phenix) — ligand restraint generation, Phenix-native format

Default fallback policy when classic local refinement is uncertain:
- use **Coot** for triage, local edits, focused validation, and local refinement probes
- use **Phenix RSR** for intermediate refinement/cleanup after Coot edits
- use **Servalcat** for final cryo-EM refinement when you need deposition-quality statistics
- use **raw Refmac** for X-ray work or when you need explicit Refmac keyword control

Use helpers to support the Coot workflow, not to duplicate other skills unnecessarily.

## Build/implementation policy

When implementing or extending this skill:
1. Find the capability family first.
2. Check the documented callable surface.
3. Reconcile with source before claiming robust support.
4. Use runtime smoke tests for high-value workflows.
5. Tag each module mentally as one of:
   - documented + source-confirmed
   - documented but source unclear
   - source-present but weakly documented
   - GUI-only / interactive
   - not worth first-class skill support

Do **not** claim broad headless coverage from online docs alone.

## Script design guidance

When adding scripts, organize them by lane and keep them narrow:
- `scripts/headless_*.py` → newer/headless API jobs
- `scripts/classic_*.py` → classic embedded Coot/batch scripting jobs
- `scripts/gui_*.md` or reference notes → manual/interactive procedures only when needed
- `scripts/*.sh` → thin wrappers only if environment setup is repetitive

Prefer scripts that:
- take explicit input files/arguments
- write explicit output files
- emit compact text or JSON summaries
- avoid hidden startup state

For classic runs, prefer explicit batch invocation like:
- `coot --no-graphics --script script.py`
- add `--no-state-script` when cleaner runs matter

## Current classic script surface

Use these first before inventing new one-off Coot snippets.
Treat them as the current operational baseline for classic-lane automation.

### Shared CLI/report convention
Use these conventions across current Phase A scripts:
- `--model` → input coordinate model
- `--map` / `--diff-map` → direct map inputs
- `--mtz` plus explicit columns when needed → MTZ-backed map generation
- residue syntax: `CHAIN:RESNO[:INSCODE]`
- residue-range syntax: `CHAIN:START-END`
- `--output-model` → output coordinates when the script edits the model
- `--report-json` → optional machine-readable report path
- `--refinement-map {primary,diff,none}` → choose the active refinement map

### `scripts/classic_load_and_export.py`
Use for:
- loading a model plus optional map(s) or MTZ
- selecting the active refinement map
- writing a clean output model
- producing a compact JSON summary of loaded molecules/maps

Example pattern:
```bash
python3 skills/coot/scripts/classic_load_and_export.py \
  --model input.pdb \
  --map map.ccp4 \
  --output-model output.pdb \
  --report-json load_report.json
```

### `scripts/classic_edit_primitives.py`
Use for simple local model edits:
- `delete-residue`
- `delete-range`
- `copy-range`
- `change-chain`
- `renumber-range`

Prefer this script for deterministic low-level edits before attempting broader rebuild logic.

Example patterns:
```bash
python3 skills/coot/scripts/classic_edit_primitives.py \
  --model input.pdb \
  --output-model output.pdb \
  delete-residue --residue A:42

python3 skills/coot/scripts/classic_edit_primitives.py \
  --model input.pdb \
  --output-model output.pdb \
  renumber-range --range A:100-120 --offset 5
```

### `scripts/classic_validate_summary.py`
Use for compact validation/triage:
- model summary
- Ramachandran summary
- rotamer summary
- density-fit summary when a map is loaded
- optional focused validation on one chain or residue range

Prefer this script to find weak regions before deciding whether to edit/refine in Coot or escalate to another tool/lane.

Example patterns:
```bash
python3 skills/coot/scripts/classic_validate_summary.py \
  --model input.pdb \
  --map map.ccp4 \
  --chain A \
  --worst-n 10

python3 skills/coot/scripts/classic_validate_summary.py \
  --model input.pdb \
  --map map.ccp4 \
  --range A:120-130 \
  --report-json validate_report.json
```

### `scripts/classic_refine_local.py`
Use experimentally for local classic-lane refinement / rigid-body range refinement.

Current status:
- the refinement call itself is usable enough to probe behavior
- a safer scripted acceptance path exists: enable immediate replacement, then use `accept_moving_atoms_py()`
- direct `c_accept_moving_atoms()` / `accept_regularizement()` calls are still not the preferred path on the current local headless runtime
- treat this script as **experimental**, and always validate the output instead of assuming refinement improved the model

Example pattern:
```bash
python3 skills/coot/scripts/classic_refine_local.py \
  --model input.pdb \
  --map map.ccp4 \
  --range A:120-123 \
  --mode refine \
  --output-model refined_out.pdb \
  --report-json refine_report.json
```

Use this script for local refinement probes and small classic-lane edits, but prefer a helper-lane decision when you need a more trusted refinement/acceptance workflow.

### `scripts/classic_mutate.py`
Use for the first narrow Phase B mutation / sequence / chain-repair surface:
- `mutate-residue` for one explicit protein or nucleotide residue
- `mutate-range` for a contiguous range from a one-letter sequence string
- `assign-sequence` for sequence annotation without coordinate mutation
- `align-and-mutate` for Coot-driven chain alignment plus mutation
- `apply-pir` for PIR alignment association + application

Current status:
- classic Python-callable mutation/alignment functions are present in the local runtime
- local smoke tests succeeded for `mutate-residue`, `mutate-range`, `align-and-mutate`, and `apply-pir`
- range mutation currently uses explicit per-residue mutation calls rather than pretending a broader helper lane is already proven
- `assign-sequence` is **quirky on this runtime**: a chain-targeted call appeared to assign annotations onto other chains, so the script now keeps it behind `--unsafe-allow-ambiguous-chain-assignment` until it is re-tested on a cleaner dataset

Example patterns:
```bash
python3 skills/coot/scripts/classic_mutate.py \
  --model input.pdb \
  --output-model mutated_out.pdb \
  mutate-residue --residue A:42 --target TYR

python3 skills/coot/scripts/classic_mutate.py \
  --model input.pdb \
  --output-model mutated_out.pdb \
  mutate-range --range A:100-102 --sequence AGS

python3 skills/coot/scripts/classic_mutate.py \
  --model input.pdb \
  --output-model aligned_out.pdb \
  align-and-mutate --chain A --sequence MSEQUENCE --renumber
```

### `scripts/classic_sidechain_fix.py`
Use for the first narrow rotamer / pep-flip / sidechain-fix surface:
- `score-rotamer` and `auto-fit-rotamer` when a map-backed rotamer choice is wanted
- `set-rotamer-number` / `set-rotamer-name` for deterministic explicit rotamer selection
- `pepflip` for peptide flips
- `backrub` / `crankshaft` as initial wrappers around sidechain/backbone cleanup helpers

Current status:
- local smoke tests succeeded for `set-rotamer-number` and `pepflip`
- `backrub` appears to need a valid active map on this runtime and the script now enforces that requirement explicitly
- map-backed `score-rotamer` / `auto-fit-rotamer` are wired but still need dedicated map-backed smoke tests before they are treated as routine-safe

### `scripts/classic_ligand_tools.py`
Use for the first narrow ligand / monomer surface:
- `list-hets` to inventory non-water HET groups and non-standard residue types
- `fetch-monomer` to retrieve/build a monomer from the available dictionary surface
- `flip-ligand` for simple ligand orientation cycling
- `read-dictionary` for loading an external CIF dictionary
- `ligand-distortion` as a thin wrapper around Coot's ligand distortion summary

Current status:
- local smoke tests succeeded for `list-hets` and `flip-ligand`
- `fetch-monomer --for-model` returned a valid comp-name/surface for `ANP`, but the returned molecule id should be interpreted cautiously because it can alias existing state
- `ligand-distortion` is **unsafe on this local mixed-chemistry benchmark**: Coot aborted while resolving linked residue types like `SC`, so the script now guards it by default on risky linked-chemistry models and only allows it with `--unsafe-allow-linked-chemistry`

### `scripts/classic_density_candidates.py`
Use for the first waters / peaks / blobs / coordination-triage surface:
- `find-blobs` to report blob-like density clusters around the model
- `map-peaks` to report map peaks around the model from the active map
- `peaks-near-point` to triage local peak candidates around one xyz point
- `find-waters` to run classic Coot water finding and report the created/updated waters molecule
- `check-waters` to flag suspicious waters by heuristic B-factor / map-score / distance criteria
- `prune-waters` to delete suspicious waters with the same heuristic criteria
- `highly-coordinated-waters` to triage suspiciously coordinated waters/metals when the loaded model already contains waters
- `ion-site-report` to do local ion-site triage around one xyz point using peaks + blobs + nearby high-coordination sites

Current status:
- local smoke tests succeeded for `find-blobs`, `map-peaks`, `find-waters`, `check-waters`, `prune-waters`, and `ion-site-report` on the local AQuaRef-style benchmark path
- `find-blobs` is currently the best reportable blob lane because `find_blobs_py()` returns structured candidates, while `execute_find_blobs()` is more GUI/side-effect oriented on this runtime
- `map-peaks` is currently the best reportable peak lane because `map_peaks_around_molecule_py()` returns structured candidates directly
- `find-waters` can create a clean new waters molecule in batch mode, optionally move those waters around the protein, renumber them, and save the affected molecule explicitly
- `check-waters` / `prune-waters` are usable, but they require a model that already contains waters and an active map; mapless or waters-only heuristic runs are not safe to assume on this runtime
- `ion-site-report` is intentionally triage-only: it reports local density/coordination context, not autonomous ion identity assignment
- `highly-coordinated-waters` is wired, but still best treated as a supporting signal rather than a standalone decision engine

### `scripts/classic_chemistry_restraints.py`
Use for the first narrow chemistry / restraints surface:
- `monomer-restraints` to inspect Coot's current restraint dictionary for one comp-id
- `write-restraints-cif` to export a CIF restraint dictionary
- `generate-local-self-restraints` for local chain self-restraint generation
- `add-extra-bond` / `clear-extra-restraints` for explicit extra-restraint management

Current status:
- local smoke tests succeeded for `monomer-restraints`, `write-restraints-cif`, and `add-extra-bond`
- the script is intentionally narrow and does not yet claim broad restraint editing coverage

### `scripts/classic_refmac_probe.py`
Use for the first narrow Coot ↔ Refmac integration check:
- verify that the local Coot build exposes Refmac-facing functions such as `execute_refmac_real()`
- verify whether `refmac5` is actually discoverable from the Coot runtime via `PATH` / `CBIN` / `CCP4_BIN`
- optionally load a model and report the per-molecule `refmac_name()` stub that Coot uses for Refmac output naming

Current status:
- on this machine, the Coot-side Refmac hooks are present in the embedded runtime
- `refmac5` is now discoverable from plain Coot via the wrapper placed on normal `PATH`
- use this probe before claiming that the external-helper lane is actually live

### `scripts/classic_refmac_run.py`
Use for the first safe real Coot → Refmac helper lane:
- run Refmac from within Coot via `coot_utils.popen_command()`
- pass one or more ligand/dictionary CIFs via repeatable `--libin`
- keep cycle count explicit with `--ncycle` (default `0` for smoke tests)
- optionally repair a broken mmCIF header before Refmac using `--ensure-cell-from` to copy cell/spacegroup from a known-good reference model
- emit a structured JSON report with prepared-input details, Refmac status, output existence, and log tail

Current status:
- local test succeeded on the older PCNA ligand-heavy benchmark (`model_10_isolde_5min.cif`) when the script repaired its placeholder cell header from a later reference model
- current wrapper is intentionally conservative: good for proving the handoff path and running narrow jobs with explicit ligand CIFs
- **not yet a metal-restraint wrapper**: do not pretend Phenix `.edits` files are directly valid Refmac extra restraints without a real translation/format check

## Feedback holding area

Use this section as a lightweight temporary place to append small runtime learnings while using the skill.
Keep entries short and operational.
When enough notes accumulate, use `skill_creator` to fold them properly back into the skill.

### New Notes (pending merge)
- Prefer generic runtime notes here; do not record dataset-specific observations unless they change the reusable workflow.
- Keep examples abstract unless a concrete example is required to explain a bug or workaround.
- If a script works only partially, say exactly which step is reliable and which step is not.
- `get_residues_in_chain_py()` is not reliable enough to trust blindly for residue enumeration on the current local runtime; prefer a more robust residue-list path when scripting selections.
- Coordinate write return codes are not fully trustworthy on the current local runtime; verify success by checking that the output file was actually created and is non-empty.
- `coot --no-graphics` can still emit GTK/GI noise on the current local runtime; treat runtime behavior as ground truth instead of assuming the headless path is clean.
- Moving-atom acceptance after refinement is no longer a pure dead end locally: the safer pattern is immediate replacement + `accept_moving_atoms_py()`.
- Do not treat successful acceptance as proof that refinement improved the model; validate the edited region afterward.
- Prefer `accept_moving_atoms_py()` over direct `c_accept_moving_atoms()` / `accept_regularizement()` calls on the current local runtime.
- When local Coot automation is awkward, prefer an explicit helper-lane decision rather than hidden improvisation; Refmac/CCP4-style helpers and Phenix are both valid depending on what the Coot workflow actually needs.
- `assign_sequence` behaved suspiciously in a chain-targeted smoke test on the current runtime; do not assume chain-local sequence assignment is trustworthy until re-checked on a cleaner dataset.
- `backrub_rotamer` appears to require a valid active map on the current runtime; treat mapless calls as expected to fail.
- `get_ligand_distortion_summary_info_py()` can hard-abort the process on mixed linked-chemistry models when dictionary coverage is incomplete (observed around linked residue types like `SC`); do not call it casually on complex ligand/cofactor assemblies.
- Some direct local `python3` + `coot` crash paths can leave a macOS “Python quit unexpectedly” dialog behind; do not treat those as acceptable routine test paths.

## References

Read these before planning or extending major coverage:
- `references/architecture.md` — module families, lane philosophy, build order
- `references/docs-and-source.md` — how to use the mirrored docs corpus and source together
- `references/v1-scope.md` — historical narrow v1 scope; useful only as a minimal baseline, not the final target

## Neighbour skills

- **Standalone CCP4 CLI binaries** (`refmac5`, `acedrg`, `freerflag`, `mtzdump`, `phaser`, `cbuccaneer`, …) → `ccp4` skill. "Run Refmac from inside Coot" recipes stay here; bare-CLI Refmac runs go to `ccp4`.
- **Phenix CLI** (`phenix.refine`, `phenix.real_space_refine`, `phenix.elbow`, …) → `phenix` skill.
