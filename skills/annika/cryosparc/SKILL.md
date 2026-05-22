---
name: cryosparc
description: Guide and automate cryoSPARC SPA processing: import/preprocessing, picking, extraction/2D, ab initio, homogeneous/heterogeneous/non-uniform refinement, 3D classification, 3DVA/3DFlex, local/focused refinement, masks, symmetry, helical, CryoSPARC Live, cryosparc-tools, cryosparcm admin, GPU lanes/queues, storage, RELION interop, troubleshooting, and error lookup. Covers tomography/cryo-ET only at the SPA boundary (e.g. tilted-SPA vs tilt-series, importing tomo-derived particles); it is not a native tomo/cryo-ET pipeline.
---

# cryoSPARC

Use this skill for cryoSPARC advice, troubleshooting, parameter recommendations, workflow planning, and cautious automation via `cryosparc-tools` / `cryosparcm` when the user explicitly wants commands run.

**Scope.** SPA-focused. Tomography/cryo-ET is in-scope only where it touches SPA (tilted-SPA collection, importing tomo-derived particle stacks, boundary disambiguation) — see `12_tomography.md`. Native tilt-series alignment and subtomogram averaging pipelines are out of scope.

## First response rule

For user questions, do **not** load the whole corpus. Pick the smallest relevant reference file(s) from `references/` and answer with version-aware caveats. The bundled corpus covers cryoSPARC **v4.0 through v5.0**; flag uncertainty when the user is on an earlier or later release than that window. If the user gives an exact error string, start with `17_error_lookup.md` and `15_troubleshooting.md`.

The `Source basis` sections inside reference files are provenance notes from skill construction, not runtime dependencies. Do not try to load those raw source paths unless the user explicitly provides the original source corpus; the actionable guidance is contained in the bundled reference file itself.

If acting on a live cryoSPARC instance, first identify:
- cryoSPARC version;
- whether the task is advisor-only or automation;
- project/workspace/job IDs;
- compute context: lane, GPUs, storage constraints;
- whether destructive actions are involved. Ask before deleting jobs/data, changing cluster config, or restarting services.

## Reference routing

Core workflow:
- Overview/project structure → `00_overview.md`
- Installation/admin → `01_installation_admin.md`, `14_cli_admin.md`
- Import → `02_import.md`
- Motion/CTF/exposure curation → `03_preprocessing.md`
- Picking: Blob/Template/Topaz/Filament Tracer → `04_picking.md` (Deep Picker is legacy and was removed in v5.0+; do not propose it for current installs)
- Extraction, 2D classification, box/Fourier crop/Nyquist → `05_extraction_2d.md`
- Ab initio → `06_abinitio.md`
- Homogeneous/Heterogeneous/NU refinement → `07_refinement.md`
- Discrete heterogeneity / 3D classification → `08_classification_3d.md`
- Local/focused refinement, particle subtraction, symmetry expansion → `09_local_refinement.md`
- Postprocessing/FSC/sharpening/local resolution → `10_postprocessing.md`
- Helical → `11_helical.md`
- Tomography/cryo-ET boundaries → `12_tomography.md`
- CryoSPARC Live → `25_cryosparc_live.md`

Decision and troubleshooting:
- Common failures → `15_troubleshooting.md`
- Error string lookup → `17_error_lookup.md`
- Parameter cookbook → `16_tuning_recipes.md`
- “What next?” branch logic → `18_decision_trees.md`
- Version-specific behavior/bugs → `version_caveats.md`

Specialized references:
- Masks → `20_masks.md`
- Symmetry → `19_symmetry.md`
- CTF refinement / RBMC → `ctf_refinement_and_rbmc.md`
- Orientation diagnostics / preferred views → `orientation_and_preferred_views.md`
- Particle set operations → `particle_set_operations.md`
- Continuous heterogeneity: 3DVA/3DFlex → `26_continuous_heterogeneity.md`
- External jobs: DeepEMhancer/ModelAngelo/custom wrappers → `23_external_jobs.md`
- RELION interop / STAR import-export → `27_relion_interop.md`
- Disk/storage/cleanup/export → `24_disk_and_storage.md`

Automation/admin:
- `cryosparc-tools` API → `13_cryosparc_tools_api.md`
- `cryosparcm` CLI/admin → `14_cli_admin.md`
- UI label → API parameter crosswalk → `ui_to_api_crosswalk.md`
- GPU lanes/queues/workers → `21_gpu_lane_queue.md`

## Operating guidance

### Advisor mode

1. Identify the processing stage and symptom.
2. Load the relevant reference(s), then answer with:
   - likely cause;
   - what to inspect first;
   - safest next job/parameter change;
   - what not to overinterpret.
3. Prefer upstream fixes over cosmetic postprocessing when the issue is alignment, heterogeneity, masks, preferred orientation, or bad particles.
4. Include version caveats when behavior changed across v4.4–v5.0.

### Automation mode

Do not assume connection details. Use `cryosparc-tools` for job orchestration and `cryosparcm` for admin/status only when appropriate. Before queueing **any** `cryosparc-tools`-created job, explicitly confirm with the user: `project_uid`, `workspace_uid`, target lane, and whether they want a dry run (build the job but do not queue) vs. an actual `queue()` call. Do not run `.queue()` / `.start()` on the user's behalf without that confirmation, even if the surrounding script already shows it.

The bundled helper `scripts/cryosparc_harness.py` is a safe starting point for local automation: read-only commands plus dry-run-first job creation by default; actual queueing requires `--commit --queue --queue-confirm QUEUE`, explicit `project_uid`, `workspace_uid`, and lane. It contains no credentials and expects `cryosparc-tools` login/session state or standard `CRYOSPARC_*` environment variables.

For code examples, favor minimal, inspectable snippets. Use `ui_to_api_crosswalk.md` before translating GUI labels to API parameters. For lanes/GPUs, check `21_gpu_lane_queue.md`.

### Safety boundaries

Ask before:
- queueing or starting any `cryosparc-tools`-created job (confirm `project_uid`, `workspace_uid`, lane, dry-run vs. queue);
- deleting jobs, projects, workspaces, cache, or raw data;
- restarting/stopping cryoSPARC services;
- modifying cluster/worker/lane configuration;
- running long GPU jobs that consume shared resources;
- exporting private datasets outside the project.

## Common answer shapes

- **Error message:** before prescribing fixes, collect (a) the **exact error text** as it appears in the job log, (b) cryoSPARC **master / worker / cryosparc-tools versions**, and (c) whether the offending **path is visible from the worker** (not just the master/UI host) — many "file not found" / permission errors are worker-side path or mount issues. Then load `17_error_lookup.md` + `15_troubleshooting.md` and give cause/fix/inspection commands.
- **Bad 2D classes:** load `05_extraction_2d.md` + maybe `04_picking.md`.
- **Bad/refinement streaky map:** load `07_refinement.md`, `10_postprocessing.md`, and if angular bias suspected `orientation_and_preferred_views.md`.
- **Mask/local refinement question:** load `20_masks.md` + `09_local_refinement.md`.
- **Continuous heterogeneity (3DVA / 3DFlex):** load `26_continuous_heterogeneity.md` (+ `09_local_refinement.md` if the user is mixing in particle subtraction or masked analysis).
- **RELION ↔ cryoSPARC interop / STAR import-export:** load `27_relion_interop.md` (+ `02_import.md` for import-side specifics, `particle_set_operations.md` if combining/diffing particle sets across packages).
- **Particle set operations (union / intersect / difference / dedup across jobs):** load `particle_set_operations.md`.
- **UI label → API parameter name lookup:** load `ui_to_api_crosswalk.md` (+ `13_cryosparc_tools_api.md` if the user is about to script it).
- **Automation script/API:** load `13_cryosparc_tools_api.md` + `ui_to_api_crosswalk.md`.
- **Queue/GPU problem:** load `21_gpu_lane_queue.md` + `14_cli_admin.md`.

## Prior-session notes

`lessons.md` (at the skill root) holds running notes from earlier sessions about this user's cryoSPARC environment, recurring pitfalls, and confirmed-working recipes. Consult it as a **last-resort** context source after the relevant reference file, and only when current question hints at site-specific behavior. It may be empty — that is expected and not a problem.
