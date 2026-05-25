# Topic 00 — Overview and Orientation

## Scope
Entry point and router for the cryoSPARC AgentSkill. Read this first when a question is unclear, then jump to the right per-stage topic. This page deliberately does not teach mechanics — every section ends with a pointer to the topic that owns the detail.

## What cryoSPARC is
cryoSPARC is a GPU-accelerated scientific software platform for cryo-electron microscopy (cryo-EM), maintained by Structura Biotechnology. It covers the full single-particle analysis (SPA) workflow from raw movies through 3D maps, plus extensions for real-time on-the-microscope processing (CryoSPARC Live), helical reconstruction, and (via wrapper / external jobs) interoperation with third-party tools. The instance is web-based; a `cryosparcm` admin CLI and a `cryosparc-tools` Python library expose the same data model programmatically.

Major-version anchors:
- v5.0 first released 2026-01-27 (current stable line for this skill's bundled docs).
- v4.0 first released 2022-10-03; v4.7.1 is the last v4.x line before the v5.0 cut.
- Helical reconstruction is shipped as a beta job within the main job catalog.

## What this skill advises on (and what it does not)

| In scope | Out of scope |
|---|---|
| SPA workflow design and parameter tuning (import → export) | Specimen prep, grid freezing, microscope alignment |
| Picker choice, 2D/3D cleanup, ab-initio / refinement strategy | Atomic model building / refinement in Coot, Phenix, ChimeraX |
| Discrete (3D Classification, Heterogeneous Refinement) and continuous (3DVA, 3DFlex) heterogeneity | Validation against deposited PDB/EMDB chemistry |
| Local refinement, particle subtraction, masks, symmetry strategy | Re-deriving published results without project context |
| Postprocessing interpretation (FSC, sharpening, local resolution) | Manuscript figure prep / publication chemistry claims |
| CLI/API automation patterns, External Jobs, RELION interop bridge | Editing the MongoDB database directly |
| Operational triage: queue, lane, GPU, SSD cache, storage growth | Destructive cleanup or `rm`-based "compaction" |
| CryoSPARC Live session design and handoff to main projects | Tomography (SPA-focused skill; tomo coverage is not bundled) |

If a user asks for anything in the right column, say so plainly and route them to a domain-appropriate tool or person.

## Architecture mental model — master / worker / lane / queue
- **Master node** runs the web app, the core HTTP API, and a MongoDB metadata database. Lightweight (4+ CPUs, 16+ GB RAM, ~250 GB disk).
- **Worker node** runs the actual GPU computations. A single node can be both master and worker.
- All nodes must share a filesystem where project directories live, and master must reach each worker over passwordless SSH plus a small TCP port range.
- **Lane** is a scheduler bucket of one or more worker targets. A job is queued to a lane; the lane picks an idle target. A worker belongs to at most one lane.
- **Target** is the concrete machine (or cluster submission script). Per-target SSD cache paths control which jobs cache particles locally.
- **Queue** is the priority-ordered list of jobs waiting for a target. Priority is per-instance default, per-user override, per-job override; users can be restricted to specific lanes.

Operational ownership:
- Lane / queue / GPU / SSD-cache *scheduling behavior* → `21_gpu_lane_queue.md`.
- `cryosparcm` / `cryosparcw` admin surface, restart/update/log runbooks, version-sensitive CLI syntax → `14_cli_admin.md`.
- Hardware sizing, install topologies, single-workstation vs cluster setup → `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md` and `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure.md`.
- Storage lifecycle (project tree growth, SSD cache, archive/compact/restore) → `24_disk_and_storage.md`.

## Data model — projects, workspaces, jobs, results, datasets
- **Project** = on-disk directory plus a database record. Strict container: jobs in different projects cannot be connected. Deleting a project from the filesystem without first detaching via the GUI or `delete_project()` CLI corrupts the instance — always detach first.
- **Workspace** = logical label inside a project. No directory on disk. A job can live in multiple workspaces at once; moving between workspaces does not copy files.
- **Job** = atomic processing unit. Has typed inputs, parameters, a status (building / queued / running / completed / failed / killed), and one or more typed output groups. Jobs are connected by dragging outputs into a downstream job's inputs.
- **Output group / result** = a typed bundle of particles, exposures, volumes, masks, etc., backed by `.cs` metadata and per-iteration files in the job directory.
- **Dataset** (in `cryosparc-tools` parlance) = the in-memory representation of a `.cs` file; one row per particle/exposure with named columns.
- **Session** = a CryoSPARC Live container, scoped to a project, that streams exposures into preprocessing and picking jobs as data arrives.

Layout cues for the advisor:
- A path like `CS-<project>/J<job_id>/` is a job directory inside a project.
- `events.bson`, `job.log`, `job.json` and a results sidecar are always present per job.
- Symlinks under the project tree typically point to raw movie/micrograph storage outside the project — losing those symlink targets makes imports unreplayable.

Detail owners:
- Project / workspace / session semantics → `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`.
- Job building, the cart, quick actions, workflows (saved job graphs) → `docs/per_page/application-guide__creating-and-running-jobs.md` and `docs/per_page/application-guide__workflows.md`.
- Inspecting a job (dashboard, event log, outputs tab, downloads) → `docs/per_page/application-guide__inspecting-job-data.md` and `docs/per_page/application-guide__downloading-and-exporting-data.md`.
- Card / tree / table views of a project → `docs/per_page/application-guide__job-views-cards-tree-and-table.md`.

## Typical SPA workflow map

| Stage | Default jobs | Topic owner |
|---|---|---|
| 1. Import | Import Movies / Micrographs / Particle Stack / Volumes | `02_import.md` |
| 2. Preprocessing | Patch Motion Correction, Patch CTF Estimation, Exposure Curation, Micrograph Denoiser | `03_preprocessing.md` |
| 3. Picking | Blob Picker → Template Picker; Topaz / Deep Picker for hard cases; Filament Tracer for filaments | `04_picking.md` |
| 4. Extraction + first 2D | Extract from Micrographs, 2D Classification, Select 2D Classes | `05_extraction_2d.md` |
| 5. Ab initio | Ab-Initio Reconstruction (multi-class for junk sort) | `06_abinitio.md` |
| 6. Consensus refinement | Homogeneous / Non-Uniform Refinement; Heterogeneous Refinement for cleanup; Reconstruction Only for re-derivation | `07_refinement.md` |
| 7. Heterogeneity | Discrete: 3D Classification; Continuous: 3DVA / 3DFlex | `08_classification_3d.md`, `26_continuous_heterogeneity.md` |
| 8. Local / focused | Particle subtraction → Local Refinement around a masked region | `09_local_refinement.md` |
| 9. Postprocessing | Sharpening, Local Resolution, Orientation Diagnostics, optional DeepEMhancer | `10_postprocessing.md` |
| 10. Export / handoff | Job/project export, RELION bridge via pyem | `docs/per_page/application-guide__downloading-and-exporting-data.md`, `27_relion_interop.md` |

Loops are normal: 2D ↔ picking, ab initio ↔ heterogeneous refinement, refinement ↔ 3D classification, refinement ↔ CTF/RBMC refinement.

## Where specialized workflows fit

| Specialization | Goal | Where to look |
|---|---|---|
| **CryoSPARC Live** | Real-time triage during data collection; streaming preprocess / pick / 2D / ab initio; later handoff | `25_cryosparc_live.md` |
| **Masks** | Soft, generous, box/pixel/origin-matched masks for refinement, classification, subtraction | `20_masks.md` |
| **Symmetry strategy** | When to impose / stay C1 / expand / relax; handedness checks | `19_symmetry.md` |
| **Helical reconstruction (beta)** | Filaments and helical assemblies | Job is in the catalog; see `docs/per_page/processing-data__all-job-types-in-cryosparc.md` for the entry point. A dedicated topic page is not in this bundle. |
| **Tomography** | Sub-tomogram averaging / tomo workflows | Not covered by this skill bundle; route to domain-appropriate tooling. |
| **`cryosparc-tools` Python API** | Programmatic project/job orchestration, dataset I/O, external jobs | `13_cryosparc_tools_api.md`, `docs/per_page/processing-data__cryosparc-tools.md` |
| **CLI / admin** | Restart, update, worker registration, logs, diagnostics | `14_cli_admin.md`, `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0.md` |
| **Storage** | SSD cache, project growth, archive/compact/restore, raw-data symlink lifetime | `24_disk_and_storage.md` |
| **External jobs / wrappers** | CTFFIND4, MotionCor2, DeepEMhancer, ThreeDFSC, crYOLO via `cryosparc-tools` | `23_external_jobs.md` |
| **RELION interop** | Round-trip via `csparc2star.py` (pyem); optics groups, coordinates, paths | `27_relion_interop.md` |
| **Parameter cookbook** | "What knob next" by stage | `16_tuning_recipes.md` |
| **Decision trees** | "Which branch?" routing across the whole pipeline | `18_decision_trees.md` |
| **Troubleshooting mental model** | Five-bucket triage before deep debugging | `15_troubleshooting.md` |
| **Error / symptom lookup** | Exact strings → fastest checks | `17_error_lookup.md` |

## How to use this topic set — question router

Match the user's question to the right topic before quoting any specifics:

| User says… | Start at |
|---|---|
| "I just got my movies." / "How do I import?" / "Pixel size / gain / EER / TIFF" | `02_import.md` |
| "Motion correction looks weird." / "CTF fit ugly." / "Which exposures to keep?" | `03_preprocessing.md` |
| "Blob vs template vs Topaz?" / "Picks have junk." | `04_picking.md` |
| "What box size?" / "First 2D is messy." / "Templates from selection." | `05_extraction_2d.md` |
| "I have no reference / which volume is real?" | `06_abinitio.md` |
| "Homogeneous vs NU?" / "Resolution stuck." / "Should I run CTF refinement / RBMC?" | `07_refinement.md` |
| "Is this two states or one?" / "Class separation." | `08_classification_3d.md` |
| "There's continuous motion." / "3DVA vs 3DFlex?" | `26_continuous_heterogeneity.md` |
| "A region of my map is blurred but everything else is sharp." | `09_local_refinement.md` |
| "Mask question." / "What soft padding?" / "GSFSC inflated?" | `20_masks.md` |
| "Symmetry? Pseudo-symmetry? Wrong hand?" | `19_symmetry.md` |
| "FSC interpretation / sharpening / local resolution / preferred orientation" | `10_postprocessing.md` |
| "Setting up Live for an upcoming session." | `25_cryosparc_live.md` |
| "Write a Python script to do X." / "Drive jobs from a notebook." | `13_cryosparc_tools_api.md` |
| "Restart cryoSPARC." / "Connect a worker." / "Logs?" | `14_cli_admin.md` |
| "Job stuck in queue." / "Worker offline." / "GPU not visible." / "SSD cache full." | `21_gpu_lane_queue.md` |
| "Project too big." / "Archive a finished project." / "Recover a detached project." | `24_disk_and_storage.md` |
| "Call CTFFIND4 / MotionCor2 / DeepEMhancer / crYOLO from inside cryoSPARC." | `23_external_jobs.md` |
| "Export to RELION / import a RELION job here." | `27_relion_interop.md` |
| "Job failed with error X." / Exact traceback in hand | `17_error_lookup.md` then `15_troubleshooting.md` |
| "Which knob should I tune for this stage?" | `16_tuning_recipes.md` |
| "What's the right branch from here?" | `18_decision_trees.md` |

If the user's question does not match any row above, ask one clarifying question before routing — version, job type, and the exact error string (or the symptom) cover most ambiguity.

## Version awareness

CryoSPARC behavior is version-shaped, and the local docs span v4.0 through v5.0. Before quoting a parameter name, default, or fix:

1. Confirm the installed master version (the master version is the source of truth — workers should match).
2. Confirm the `cryosparc-tools` version when scripting; it tracks the connected CryoSPARC minor version.
3. Skim the relevant release-notes page (`reference/release_notes/markdown/v4.0.md` through `v5.0.md`) for the feature or bug under discussion.
4. Treat forum advice older than two minor versions as suggestive, not prescriptive — many recipes were superseded by jobs added in v4.3 (Data Cleanup Tools), v4.4 (volume viewer types, RBMC fixes), v4.5 (orientation diagnostics, 3D Classification fixes), v4.6 (transparent-hugepages handling, corrupt-particle checks), or v5.0 (job dashboard, instance tab redesign, intermediate-result handling).
5. `cryosparcm cli` flags can change between versions — verify with `cryosparcm <cmd> --help` on the live instance before scripting destructive operations.

## Safety defaults and red flags

These rules survive across stages. The advisor should refuse, pause, or downgrade an action when any of these fire:

1. **Never `rm` a project directory.** Detach via the GUI or `delete_project()` first; the on-disk and database state must be unwound together. Cleanup belongs to the Data Cleanup Tools (v4.3+) and to Project Compaction — not to the shell.
2. **Provenance is the deliverable.** Branch jobs (clone + change one thing) instead of mutating in place. Keep the raw-movie symlinks alive until export is signed off; once they go, RBMC and reimport are gone.
3. **Do not overinterpret maps.** Sharpening cannot fix wrong alignments; a tight mask can inflate GSFSC while the map gets worse; ResLog is not a resolution claim; angular plots are not a particle-count histogram. Cross-check upstream before "polishing" downstream.
4. **Verify paths from the worker shell as the cryoSPARC owner user**, not just from master. "Invalid path" / "file not found" / failed symlinks are usually mount or permission mismatches, not bugs.
5. **Capture diagnostics before destructive recovery.** Before restarting `cryosparcm`, killing a job, or repairing the database, grab `cryosparcm status`, the relevant `cryosparcm log` slice, and the failing job's `job.log` and event log.
6. **Ask before automating against a live instance.** For any `cryosparc-tools` or `cryosparcm` recipe, confirm: master version, host/port, license id ownership, target project/workspace, and whether the target project is currently being edited by a human user. Default to a dry-run / read-only pass first.
7. **Treat forum recipes as version-bound.** If a recipe is older than two minor versions, re-verify against the current release notes before applying.
8. **Respect the network model.** cryoSPARC is "trusted private network"-only by design and is not internet-hardened — do not propose exposing ports, weakening auth, or running it on a public IP.

## Advisor defaults and common first questions

Default reflexes when a request is ambiguous:
- **Default workflow**: import → patch motion → patch CTF → curate exposures → blob pick → 2D → select → re-pick (template) → 2D → ab initio (multi-class) → heterogeneous refinement cleanup → consensus (Homogeneous or NU) → postprocess. Branch out only when the data forces it.
- **Default symmetry**: C1 unless the point group is established and the consensus matches it.
- **Default refinement**: Non-Uniform when soft / disordered density is suspected (membrane, micelle, small target with flexible regions); Homogeneous as the conservative first pass otherwise.
- **Default heterogeneity branch**: discrete (3D Classification or Heterogeneous Refinement) before continuous (3DVA / 3DFlex). Continuous methods need a coherent consensus first.
- **Default cleanup**: prefer the GUI Data Cleanup Tools and Project Compaction over manual file deletion.
- **Default automation surface**: `cryosparc-tools` for orchestration, `cryosparcm` for admin, GUI for exploration and inspection.

Common first questions the advisor should ask before committing to a recommendation:

1. **Version**: cryoSPARC master version, worker version, `cryosparc-tools` version if scripting.
2. **Stage and goal**: where in the workflow, and what the user is trying to *decide*, not just *do*.
3. **Inputs in hand**: raw movies vs aligned micrographs vs imported particle stack vs imported volume; pixel size / voltage / Cs / dose confirmed against the collection sheet.
4. **Recent change**: new worker, new GPU/driver, moved storage, fresh upgrade, switched lanes.
5. **Failure evidence**: exact error string and which log it came from (`job.log`, `command_core`, `command_vis`, `database`, `supervisord`, cluster scheduler log).
6. **Constraints**: time budget, particle count, target resolution, single-class vs heterogeneity question, downstream consumer (RELION, ChimeraX, model building).

When the user is about to run something irreversible (delete project, force-restart, push a workflow to a cluster lane, run RBMC on the last copy of raw movies), name the action explicitly and confirm scope before executing.

## Source basis

The items below were local synthesis inputs used to build this self-contained reference. They are not required at runtime and are intentionally not bundled in this repository; use current public cryoSPARC documentation, release notes, and forum posts for fresh upstream verification.

- `topic_plan.md`
- `02_import.md`
- `03_preprocessing.md`
- `04_picking.md`
- `05_extraction_2d.md`
- `06_abinitio.md`
- `07_refinement.md`
- `08_classification_3d.md`
- `09_local_refinement.md`
- `10_postprocessing.md`
- `13_cryosparc_tools_api.md`
- `14_cli_admin.md`
- `15_troubleshooting.md`
- `16_tuning_recipes.md`
- `18_decision_trees.md`
- `19_symmetry.md`
- `20_masks.md`
- `21_gpu_lane_queue.md`
- `23_external_jobs.md`
- `24_disk_and_storage.md`
- `25_cryosparc_live.md`
- `26_continuous_heterogeneity.md`
- `27_relion_interop.md`
- `17_error_lookup.md`
- `docs/per_page/readme.md`
- `docs/per_page/application-guide__a-tour-of-the-cryosparc-interface.md`
- `docs/per_page/application-guide__projects-workspaces-and-live-sessions.md`
- `docs/per_page/application-guide__creating-and-running-jobs.md`
- `docs/per_page/application-guide__job-views-cards-tree-and-table.md`
- `docs/per_page/application-guide__inspecting-job-data.md`
- `docs/per_page/application-guide__workflows.md`
- `docs/per_page/application-guide__admin-panel.md`
- `docs/per_page/application-guide__instance-management.md`
- `docs/per_page/application-guide__downloading-and-exporting-data.md`
- `docs/per_page/setup-configuration-and-management__hardware-and-system-requirements.md`
- `docs/per_page/setup-configuration-and-management__how-to-download-install-and-configure.md`
- `docs/per_page/setup-configuration-and-management__management-and-monitoring-v5.0.md`
- `docs/per_page/processing-data__cryosparc-tools.md`
- `docs/per_page/processing-data__all-job-types-in-cryosparc.md`
- `docs/per_page/processing-data__get-started-with-cryosparc-introductory-tutorial.md`
- `reference/release_notes/markdown/v4.0.md`
- `reference/release_notes/markdown/v4.1.md`
- `reference/release_notes/markdown/v4.2.md`
- `reference/release_notes/markdown/v4.3.md`
- `reference/release_notes/markdown/v4.4.md`
- `reference/release_notes/markdown/v4.5.md`
- `reference/release_notes/markdown/v4.6.md`
- `reference/release_notes/markdown/v5.0.md`
- `videos/notes/01_introduction_and_cryoem_fundamentals.notes.md`
- `videos/notes/02_trpv1_and_a_standard_workflow.notes.md`
- `videos/notes/09_workflows_automated_pipelines.notes.md`
- `docs/forum_threads/digests/forum_troubleshooting.md`
