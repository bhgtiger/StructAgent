---
name: cryosparc
description: Guide and automate CryoSPARC single-particle processing, troubleshooting, Live, workflows, cryosparc-tools/CLI administration, masks, and external-tool interoperability. Use for CryoSPARC workflow or parameter questions and to refresh this skill's release notes, tutorials, and sources. Native tomography pipelines are outside scope.
---

# CryoSPARC

## Start here

Latest verified release: **v5.0.7 (2026-08-14)**; sources checked **2026-09-07**. Historical guidance covers v4.0–v5.0.7, with selective patch notes; this is documentation coverage, not live-instance validation. Check [version caveats](references/version_caveats.md) for release-dependent advice; browse official sources when asked for the latest information.

Load only the relevant reference below, normally one or two files. For long references, search headings or the exact symptom with `rg -n` and read the matching section. Specific requests take precedence over broad workflow routing. Historical `Source basis` paths identify the construction archive, not runtime dependencies; consult [maintenance](references/maintenance.md) only for provenance or updates.

## Choose a reference

Reference filenames are relative to `references/`; `scripts/` paths are relative to the skill root.

| Request | Read |
|---|---|
| Whole dataset / protocol | `28_spa_playbook.md` |
| Case study, EMPIAR ID, dataset phenotype | `case_studies_and_tutorials.md` |
| Repeat-target automation, CAK, GPCR Workflows v1/v2, workflow JSON examples | `automated_workflow_tutorials.md` |
| Stage-specific “what next?” / parameter recipes | `18_decision_trees.md` / `16_tuning_recipes.md` |
| Exact error / general failure | `17_error_lookup.md` / `15_troubleshooting.md` |
| Overview / import | `00_overview.md` / `02_import.md` |
| Motion, CTF, exposure curation | `03_preprocessing.md` |
| Native picking / extraction and 2D | `04_picking.md` / `05_extraction_2d.md` |
| crYOLO general-model picks → extraction → 2D | `29_cryolo_picking_to_2d.md`; `scripts/cryolo_pick/` |
| Ab initio, including Homogeneous Ab-Initio Refinement | `06_abinitio.md` |
| Homogeneous, heterogeneous, NU refinement | `07_refinement.md` |
| Discrete / continuous heterogeneity | `08_classification_3d.md` / `26_continuous_heterogeneity.md` |
| Local refinement / subtraction | `09_local_refinement.md`, `20_masks.md` |
| Masks / dynamic masking | `20_masks.md` |
| Generate model/map/complement mask with ChimeraX | `20a_mask_generation_chimerax.md`; `scripts/masks/` |
| FSC, sharpening, local resolution | `10_postprocessing.md` |
| Preferred orientation, cFAR/tFAR | `orientation_and_preferred_views.md` |
| Symmetry / helical / tomography boundary | `19_symmetry.md` / `11_helical.md` / `12_tomography.md` |
| CTF refinement / RBMC | `ctf_refinement_and_rbmc.md` |
| Particle union, intersection, deduplication, scale subsets | `particle_set_operations.md` |
| Live | `25_cryosparc_live.md` |
| Python API / GUI-to-API parameters | `13_cryosparc_tools_api.md`, `ui_to_api_crosswalk.md` |
| Installation / CLI / GPU lanes / storage | `01_installation_admin.md` / `14_cli_admin.md` / `21_gpu_lane_queue.md` / `24_disk_and_storage.md` |
| External jobs / adapter formats | `23_external_jobs.md` / `29_external_tool_bridge_format.md` |
| RELION STAR import/export | `27_relion_interop.md` |
| RELION focused classification → CryoSPARC refinement | `28_relion_class3d_roundtrip.md`; `scripts/roundtrip/` |

## Working rules

- Diagnose from the processing stage and evidence. Give the first inspection, a justified next step, and its validation. Tutorial parameters are dataset-specific examples.
- For errors, obtain the exact traceback, master/worker/tools versions, and worker-side path visibility. Historical CLI commands require version checks.
- Deep Picker was removed in v5; use supported picking routes. For v5 scripting, check the migration section in the API reference before adapting old examples.
- Before live work, establish installed version, project/workspace/job IDs, lane, resources, and whether the user wants advice, job creation, or queueing. Reuse authorization already given. Obtain missing authorization before queue/start, deletion, service restart, configuration changes, shared GPU computation, or private-data export.
- `scripts/cryosparc_harness.py` defaults to a local plan. `--commit` creates jobs; queueing additionally requires `--queue --queue-confirm QUEUE`, project, workspace, and lane. Inspect actual job schemas; do not infer API names from GUI labels.
- Mask scripts read/write local files without a CryoSPARC connection. Importing their outputs and running downstream jobs follows the live-work rules. Use the native tool skill for external CLI details.
- Consult `lessons.md` only for relevant site-specific history; keep credentials outside the skill.

## Update this skill

For “update/refresh the CryoSPARC skill,” follow [references/maintenance.md](references/maintenance.md): inspect sources, review release/tutorial changes, edit affected references, validate, and synchronize the authorized local copies. This maintains the knowledge bundle; a CryoSPARC installation upgrade is a separate task.
