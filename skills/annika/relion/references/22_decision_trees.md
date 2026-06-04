# 22 — Decision trees: which branch / what next

## Scope
The router for the whole skill. Six skimmable decision trees that turn a one-line user question — "which pipeline is this?", "a job failed, now what?", "what is my next SPA step?", "which map do I hand to model building?", "should I round-trip to cryoSPARC / cryoDRGN?", "continue or restart this refinement?" — into a concrete next action and the **exact sibling reference file** that owns the detail. Every leaf points at a numbered reference (`04`–`21`) or a named installed skill. This file decides *where to go*; the target file holds the flags, commands, and grounding. All RELION facts here are inherited from the grounded sibling files and re-confirmed against the live `relion_refine --help` (5.0.0-commit-3d6c20), `pipeline_jobs.cpp`, and the read-only 4.0-beta fixture `<RELION_PROJECT_FIXTURE>`.

---

## How to use this file

1. Pick the tree whose question matches the user's intent (table below).
2. Walk the branches top-down; stop at the first leaf that matches what the user **already has on disk** (run `inspect_project.py` first if unsure — it reports job graph, sentinels, outputs, optics).
3. Open the reference file named at that leaf. Do not answer from this file alone — it is an index, not a manual.

| Tree | Question | Routes to |
|---|---|---|
| **A** | Is this SPA, helical/amyloid, or tomo/STA? | `04`–`11` / `13` / `14` |
| **B** | A job failed — what now? | `inspect_project.py` → `21` → `20` → the stage file |
| **C** | What is the next SPA step? | the stage map, keyed on what you have |
| **D** | Which map do I hand to model building / refinement? | `09` + `18` |
| **E** | Round-trip to cryoSPARC / export to cryoDRGN? | `16` / `17` + cost/benefit |
| **F** | Continue or restart a refinement? | `08` (continue from optimiser) vs fresh |

First command for almost any "my project / job is X" question:

```bash
python3 scripts/inspect_project.py /path/to/project            # whole-project triage
python3 scripts/inspect_project.py /path/to/project --failed   # only failed/aborted jobs
python3 scripts/inspect_project.py /path/to/project Refine3D/job034   # one job, deep
```

`inspect_project.py` is **read-only** (`scripts/inspect_project.py:10-12`) and reads `default_pipeline.star`, per-job exit sentinels, `run.err` tails, and optics/pixel summary. See `00_overview.md §8` and `02_project_job_tree.md`.

---

## Tree A — Is this SPA, helical/amyloid, or tomo/STA?

Decide the **pipeline family** before anything else. Two on-disk tells settle it immediately; the data shape settles the rest.

```
Open any job.star  →  _rlnJobIsTomo ?
├─ 1  → TOMO / STA  ────────────────────────────────────────────►  14_tomo_sta.md
│      (also: relion_refine command carries --ios / --tomograms / --trajectories;
│       launched via `relion --tomo`; tomogram_set / optimisation_set STARs present)
└─ 0  → SPA-family. Is the structure a filament/helix?
       Open the refine/class job.star or note.txt → does it carry --helix ?
       ├─ Yes, and the target is an amyloid fibril   ──────────►  13_helical_amyloid.md  (5.1 amyloid extras)
       ├─ Yes, helical (HIV CA tube, MT, F-actin…)   ──────────►  13_helical_amyloid.md
       └─ No  → globular / membrane / complex SPA   ──────────►  04–11 (the SPA stage files)
```

Grounding for the tells:
- `_rlnJobIsTomo` is a field in `data_job` of every `job.star` (0 = SPA, 1 = STA) — fixture `Refine3D/job034/job.star`; see `00_overview.md §4`, `02_project_job_tree.md`.
- `relion_refine` exposes tomo I/O: `--ios`, `--tomograms`, `--trajectories` (live help lines 13-15) and `--helix (false) : Perform 3D classification or refinement for helices?` (live help line 64). Presence of these in `note.txt` is a definitive classifier.
- STA is launched separately (`relion --tomo`, `source/Whats-new.rst:29`); its data model is `tomogram_set` / `particle_set` / `optimisation_set` STARs (`source/Reference/STA/Datatypes/*.rst`) — see `14_tomo_sta.md`.

SPA-family stage routing (the `04`–`11` leaves):

| You are working on | Reference file |
|---|---|
| Import, motion correction, CTF estimation | `04_preprocessing.md` |
| Picking (LoG / template / Topaz), extraction | `05_picking_extraction.md` (cross-link **cryolo**) |
| 2D classification + class selection / ranking | `06_class2d_select.md` |
| Initial model (VDAM), 3D classification | `07_initialmodel_class3d.md` |
| 3D auto-refine | `08_refine3d.md` |
| Mask, PostProcess, LocalRes | `09_mask_postprocess_localres.md` |
| CTF refine, Bayesian polishing | `10_ctfrefine_polish.md` |
| Subtraction, multi-body | `11_subtract_multibody.md` |

> Mixed projects are normal: a tomo project can still run SPA-style 2D/3D classification on its pseudo-subtomograms. Trust `_rlnJobIsTomo` of the *specific* job, not the project name.

---

## Tree B — A job failed — what now?

A strict four-step funnel. Do them **in order**; do not skip to the stage file before reading the real error string.

```
1. inspect_project.py PROJECT --failed
   → lists every job with RELION_JOB_EXIT_FAILURE / _ABORTED + the filtered run.err tail
   │
2. Read the SENTINEL (file in the job dir), not a guess:
   ├─ RELION_JOB_EXIT_FAILURE   → it errored. Get the real error line (step 3).
   ├─ RELION_JOB_EXIT_ABORTED   → user/GUI aborted (RELION_JOB_ABORT_NOW was placed).
   ├─ RELION_JOB_ABORT_NOW only → abort REQUESTED, job may still be exiting.
   └─ NO sentinel + stale state  → killed by queue / OOM-killer / node death (no clean exit).
   │   (sentinels are FILES: src/pipeline_control.h:32-35. RELION_EXIT_* (lines 37-39) are
   │    exit MACROS that WRITE the RELION_JOB_EXIT_* file — there is no RELION_EXIT_SUCCESS file;
   │    grep for RELION_JOB_EXIT_*.)
   │
3. Extract the REAL error from run.err (ignore the noise):
   → MPI noise to ignore: "MPI_ABORT was invoked", "errorcode 1",
     "----" rule lines, X11 "No protocol specified". inspect_project.py already filters these.
   → The real cause is usually ONE line above the MPI_ABORT block.
   │
4. Look the exact error string up → fix → re-run:
   ├─ Known exact string?  ───────────────────────────────►  21_error_lookup.md  (string → cause → fix)
   ├─ Symptom/class, not an exact string?  ───────────────►  20_troubleshooting.md  (diagnostic playbook)
   └─ Cause is stage-specific (a flag, an input STAR)  ───►  the stage file (04–11) for that job type
```

Worked examples from the fixture (canonical patterns):

| `run.err` real line (after filtering noise) | Sentinel | Root cause | Route | Fix in |
|---|---|---|---|---|
| `Parameter estimation is not supported in MPI mode.` | FAILURE | Polish **training** run under `relion_motion_refine_mpi` (`Polish/job040,041`) | `21` → | `10_ctfrefine_polish.md` — run training **single-rank**, no `_mpi` |
| `ERROR: out of memory in …custom_allocator.cuh … A GPU-function failed to execute.` | FAILURE | GPU OOM on 11 GB RTX 2080 Ti (`MultiBody/job087,089`, `relion_flex_analyse`) | `20` → | `11_subtract_multibody.md` — fewer bodies / smaller pool / box |
| `MetaDataTable::read: File …run_data.star does not exist` | FAILURE | **Secondary** symptom — upstream GPU job never wrote its output | `20` → | fix the upstream OOM first, then re-run |

> The third row is the classic trap: a "missing file" error is often *downstream* of the real crash. Always check whether the file's **producer** job actually succeeded (its `RELION_JOB_EXIT_SUCCESS` file) before chasing the consumer. See `20_troubleshooting.md` (cascade failures) and `00_overview.md §"Common failures"`.

> "Job failed but there's no `RELION_JOB_EXIT_FAILURE`": a queue-killed or OOM-killed process can leave **no** sentinel. Treat a job in a running-but-stale state with a truncated `run.out` as crashed, and confirm against the queue logs (`sacct` / scheduler). This is the one case where the absence of a sentinel is itself the diagnosis.

---

## Tree C — What is the next SPA step?

Key the decision on **what you already have on disk**, not on where you "should" be. Walk down until your most-advanced existing output matches a row, then take the "next" action.

```
What is the most advanced thing you have?
├─ Raw movies only ───────────────────────────────► IMPORT → MOTIONCORR → CTF     →  04_preprocessing.md
├─ Aligned micrographs + CTF (micrographs_ctf.star)► PICK (LoG/template/Topaz)     →  05_picking_extraction.md (cryolo)
├─ Coordinates (*_autopick.star / manualpick) ────► EXTRACT particles             →  05_picking_extraction.md
├─ Extracted particles (particles.star) ──────────► 2D CLASSIFY → SELECT good     →  06_class2d_select.md
├─ Clean particle subset (selected 2D) ───────────► INITIAL MODEL (VDAM)          →  07_initialmodel_class3d.md
├─ An initial 3D map ─────────────────────────────► 3D CLASSIFY (sort hetero)     →  07_initialmodel_class3d.md
├─ One clean 3D class + its particles ────────────► 3D AUTO-REFINE                 →  08_refine3d.md
├─ A converged refine (run_half1/2…_unfil.mrc) ───► MASK + POSTPROCESS            →  09_mask_postprocess_localres.md
├─ A PostProcess map + resolution number ─────────► two parallel branches ↓
│     ├─ push resolution?  → CTF-REFINE → POLISH → re-REFINE (iterate)            →  10_ctfrefine_polish.md
│     └─ per-voxel res?    → LOCALRES                                              →  09_mask_postprocess_localres.md
├─ A high-res consensus map you trust ────────────► is there residual heterogeneity?
│     ├─ discrete (compositional)  → focused 3D-classify w/ SUBTRACT             →  11_subtract_multibody.md
│     ├─ rigid-body motion         → MULTI-BODY                                   →  11_subtract_multibody.md
│     └─ continuous deformation    → DynaMight                                     →  cryo-flex-knowledge (skill)
└─ A finished, sharpened, validated map ──────────► MODEL BUILDING                 →  Tree D
```

The canonical linear order (for reference) is `import → motioncorr → ctf → pick → extract → 2D → select → initialmodel → 3D class → refine3d → mask/postprocess → ctfrefine → polish → localres → modelbuilding → flexibility` (`source/SPA_tutorial/Introduction.rst:5`; `00_overview.md §3`).

Loops and branches that break the straight line:
- **CtfRefine ↔ Polish ↔ Refine3D iterate.** After CtfRefine or Polish the particle STAR changed, so you re-refine; resolution usually improves over 1-2 rounds, then plateaus. Each pass is a *fresh* Refine3D (Tree F). See `10_ctfrefine_polish.md`.
- **Subtraction / multi-body branch off a finished consensus refine** — they consume its `*_optimiser.star` / `run_data.star`, they are not a linear "next step." See `11_subtract_multibody.md`.
- **Re-extraction** (bigger box, different pixel, recentred) sends you back to 2D/3D with a *new* particle set — that is a fresh refinement, never a continue.

What "next step" each output enables (quick lookup):

| You have (file) | Producer | Enables |
|---|---|---|
| `corrected_micrographs.star` | MotionCorr | CTF estimation, picking |
| `micrographs_ctf.star` | CtfFind | picking, extraction |
| `particles.star` | Extract | 2D classify |
| `run_it025_class00N.mrc` + `run_it025_data.star` | Class3D | refine3d (pick best class) |
| `run_data.star` | Refine3D (final) | CtfRefine, Polish, re-extraction, subtraction/multibody input |
| `run_half1/2_class001_unfil.mrc` | Refine3D (final) | PostProcess, LocalRes |
| `postprocess.star` + `postprocess.mrc` | PostProcess | model building (Tree D), reporting resolution |

(Output names per `08_refine3d.md §6`, `09_mask_postprocess_localres.md`, fixture job dirs.)

---

## Tree D — Which map do I hand to model building / refinement?

The single most common interop mistake is handing the **wrong** map to a model-builder or to real-space refinement. Pick by **what the downstream tool expects**, not by "the prettiest map."

```
Downstream consumer?
├─ ModelAngelo / Coot / manual tracing (build INTO density)
│     → use the SHARPENED, masked PostProcess map:  PostProcess/jobNNN/postprocess.mrc
│       (B-factor sharpened + masked; this is the "display" map)              →  09_mask_postprocess_localres.md
│       RELION 5 ModelAngelo job is relion.modelangelo / relion_python_modelangelo →  18_interop_chimerax_coot_phenix.md
│
├─ Phenix real_space_refine / validation (needs HALF-MAPS for FSC-validation)
│     → hand the TWO UNFILTERED half-maps + a mask + pixel size:
│       run_half1_class001_unfil.mrc, run_half2_class001_unfil.mrc, mask.mrc
│       (so Phenix computes its own FSC_model-vs-half and avoids over-sharpening)  →  18 (cross-link phenix skill)
│
├─ Local / heterogeneous resolution colouring or trimming
│     → locally-filtered map from LocalRes (relion_postprocess --locres)      →  09_mask_postprocess_localres.md
│
└─ Rigid-body docking / figure / fit-check in ChimeraX
      → postprocess.mrc for figures; raw run_class001.mrc to judge handedness  →  chimerax skill, 18
```

Rules of thumb (grounded in `09_mask_postprocess_localres.md`):
- **`postprocess.mrc`** = masked + B-factor-sharpened → for *building/visualising*. Not for FSC validation against a model (it is already sharpened and masked).
- **`run_half1/2…_unfil.mrc`** = the two *unfiltered* half-maps → for any tool that must do its **own** FSC / resolution estimate (Phenix, EMReady, independent validation). These are the auto-refine deliverable (`08_refine3d.md §6`).
- **Always send the pixel size and the mask alongside the map** — RELION sharpening uses a specific mask; downstream tools need it to reproduce the resolution. Build/inspect masks via the **mask** skill or a `MaskCreate` job (`09_mask_postprocess_localres.md §1`).
- Execution of the building/refinement step itself is owned by the **phenix**, **coot**, **chimerax**, and **mask** skills, and strategy by **structural-strategy**. This skill hands off; it does not run them. See `18_interop_chimerax_coot_phenix.md`.

> Handedness gate before model building: if the model refuses to fit / fits as a mirror, the map may be the wrong hand. RELION refinement does not fix global handedness; check it in ChimeraX and flip (z-mirror) the map if needed before building (`08_refine3d.md §9`, `12_conventions_symmetry.md`).

---

## Tree E — Round-trip to cryoSPARC / export to cryoDRGN?

These are *optional* detours. Only take them for a concrete reason; each crossing risks a convention bug (Euler-angle direction, shift sign, pixel size) — see `12_conventions_symmetry.md` and the interop files.

```
Why are you leaving RELION?
├─ "RELION refine stalls / I want NU-refine or a second opinion on the map"
│     → ROUND-TRIP to cryoSPARC                                               →  16_interop_cryosparc.md (cryosparc skill)
│       Cost: convention conversion both ways. Benefit: NU-refine,
│       cryoSPARC ab-initio/hetero-refine often crack preferred-orientation
│       or junk-heavy sets faster. Bring particles back via csparc2star.py.
│
├─ "I have continuous conformational heterogeneity (a flexible machine)"
│     ├─ want to STAY in RELION  → DynaMight (5.0, single-GPU)                →  cryo-flex-knowledge (skill)
│     └─ want a latent landscape / cryoDRGN  → EXPORT to cryoDRGN            →  17_interop_cryodrgn.md
│           Cost: env switch (cryoDRGN in a conda env, not base PATH).
│           Benefit: continuous latent space, particle filtering, motion movies.
│
└─ "I just want a better mask / picker / quick 2D"
      → consider the picker (cryolo) or mask (mask) skills, or just iterate in RELION
        before committing to a full package round-trip.
```

Conversion mechanics and cost/benefit:

| Crossing | Tool | Direction | Watch out for |
|---|---|---|---|
| RELION → cryoSPARC | cryoSPARC's own `Import Particle Stack` (reads RELION STAR) | particles + poses out | optics-group → exposure-group mapping; pixel size |
| cryoSPARC → RELION | `csparc2star.py` (pyem) at `csparc2star.py` | `.cs` → RELION `.star` | Euler-angle direction & shift sign conversion (the classic interop bug) |
| RELION → cryoDRGN | cryoDRGN's `parse_pose_star` / `parse_ctf_star` on a RELION `*_data.star` | particles + ctf + poses | cryoDRGN lives in a **conda env**, not base PATH; box/pixel must match the stack |

Cost/benefit summary (when it is worth it):
- **Worth a cryoSPARC round-trip** when: preferred orientation or a stubborn junk fraction is defeating RELION refinement; you want NU-refinement, a faster ab-initio, or an orthogonal validation of the map/resolution. The **cryosparc** skill owns that side end-to-end (import/picking/refine/3DVA/3DFlex). See `16_interop_cryosparc.md`.
- **Worth a cryoDRGN export** when: the heterogeneity is *continuous* and you want a latent landscape / per-particle filtering / motion movies that RELION's discrete 3D-class cannot give. If you would rather not leave RELION, **DynaMight** (5.0) does deformation modelling in-pipeline (cross-link **cryo-flex-knowledge**). See `17_interop_cryodrgn.md`.
- **Not worth it** when a RELION-native fix exists (Blush for low-SNR/preferred-orientation refinement; focused 3D-class with subtraction for discrete heterogeneity). Don't cross packages to dodge a one-flag fix. See `08_refine3d.md §5` (Blush), `11_subtract_multibody.md`.

> `csparc2star.py` and cryoDRGN env paths are this host's install (verified-environment brief); treat them as site facts, not RELION universals. The convention conversions themselves are the load-bearing risk — read `12_conventions_symmetry.md` before trusting any cross-package poses.

---

## Tree F — Continue or restart a refinement?

For Refine3D / Class2D / Class3D / InitialModel, "continue" resumes from a saved `*_optimiser.star`; it does **not** re-emit the algorithm/initialisation flags. Restart ("fresh") whenever any of those frozen settings must change.

```
Do you need to change particles, box/pixel, symmetry, mask, CTF mode, or greyscale?
├─ YES  → START FRESH (new job).  A continue CANNOT change those — they are guarded
│         by if(!is_continue) in the command builder.                          →  08_refine3d.md §7
│         Always fresh after: re-extraction, CtfRefine, Polish (the STAR changed),
│         a symmetry change, a new/different mask, or switching greyscale mode.
│
└─ NO (same particles, same sym, same CTF) → why did it stop?
      ├─ hit wall-clock / queue limit, or killed cleanly  → CONTINUE
      ├─ want a few more iters at finer sampling           → CONTINUE
      └─ converged but you want to push resolution         → usually NOT a continue;
            do CtfRefine/Polish then a FRESH refine instead (Tree C loop).
```

Continue mechanics (grounded in `08_refine3d.md §7`, `pipeline_jobs.cpp`):

```text
relion_refine_mpi --continue Refine3D/job034/run_it018_optimiser.star \
  --o Refine3D/job050/run  --pool 30 --dont_combine_weights_via_disc \
  --scratch_dir /processing --j 6 --gpu ""
```

- The continue target **must** be an `*_optimiser.star` whose name contains both `_it` and `_optimiser`, or the GUI rejects it (`pipeline_jobs.cpp:4336-4342`; construction `:4347`).
- On continue, only the output name, compute flags (`--pool`, disc-IO, `--scratch_dir`, `--pad`, `--auto_ignore_angles`/`--auto_resol_angles`), `--particle_diameter`, and `--blush` are re-applied; `--auto_refine/--split_random_halves`, `--i`, `--ref`, `--firstiter_cc`, `--ini_high`, `--ctf`, `--flatten_solvent/--zero_mask`, all sampling flags, `--sym`, `--norm/--scale` are **not** re-emitted (`08_refine3d.md §7`). So you literally cannot change symmetry or CTF mode mid-continue.
- The continued job needs a **new output rootname / job dir** (different from the previous run); the same `--continue` pattern applies to Class2D (`pipeline_jobs.cpp:3180`), InitialModel (`:3856`), and Class3D (`:3462`).
- Multi-body is itself a *continuation from the consensus optimiser*: `--continue <consensus_optimiser.star> … --solvent_correct_fsc --multibody_masks <bodies.star>` (`pipeline_jobs.cpp:4743-4746`) — see `11_subtract_multibody.md`. That is a continue in the code sense but conceptually a new analysis.

Quick verdict table:

| Situation | Continue or fresh |
|---|---|
| Queue wall-clock killed a refine mid-run | **Continue** from last `_it???_optimiser.star` |
| Want finer sampling for a few more iters | **Continue** (compute flags + sampling-faster flags re-applied) |
| Re-extracted to a different box/pixel | **Fresh** |
| After CtfRefine or Polish | **Fresh** (the particle STAR changed) |
| Changing symmetry (C1→D2, etc.) | **Fresh** (sym is frozen on continue) |
| New / looser / tighter reference mask | **Fresh** |
| Reference greyscale assumption changed | **Fresh** (`--firstiter_cc` is frozen on continue) |

---

## Common failures / red flags (router-level)

- **Routing on project name, not job metadata.** A "tomo" project may run SPA-style 2D/3D on pseudo-subtomograms; trust `_rlnJobIsTomo` of the specific `job.star` (Tree A), not the folder name.
- **Chasing a "missing file" error.** A `…does not exist` error is frequently *downstream* of the real crash (fixture `MultiBody` → missing `run_data.star`). Tree B step-2/3: confirm the producer job's `RELION_JOB_EXIT_SUCCESS` before treating the consumer as the problem.
- **Grepping for the wrong sentinel.** Looking for a `RELION_EXIT_SUCCESS` *file* always fails — the file is `RELION_JOB_EXIT_SUCCESS` (`src/pipeline_control.h:32-35`); `RELION_EXIT_*` (`:37-39`) are the exit *macros* that write that file and set the exit code (`pipeline_control.cpp:24-56`).
- **"Continue" to fix a changed input.** If the particle STAR, box, symmetry, mask, CTF, or greyscale changed, a continue silently keeps the *old* frozen settings — you must start fresh (Tree F).
- **Crossing packages to avoid a one-flag fix.** Blush (low-SNR/preferred orientation) or focused-class-with-subtraction (discrete heterogeneity) often beat a full cryoSPARC/cryoDRGN round-trip (Tree E).
- **Handing `postprocess.mrc` to a tool that needs half-maps.** Sharpened+masked map for *building*; the two `*_unfil.mrc` half-maps for any *own-FSC* validation (Tree D).

---

## Cross-links

- `00_overview.md` — pipeline mental model, exit sentinels, `inspect_project.py` usage.
- `02_project_job_tree.md` — `default_pipeline.star`, `job.star`, status labels, nodes/edges.
- `04_preprocessing.md`, `05_picking_extraction.md`, `06_class2d_select.md`, `07_initialmodel_class3d.md`, `08_refine3d.md`, `09_mask_postprocess_localres.md`, `10_ctfrefine_polish.md`, `11_subtract_multibody.md` — SPA stage detail (Trees A/C/D/F leaves).
- `12_conventions_symmetry.md` — Euler-angle direction, shift sign, symmetry/handedness (Tree E risk).
- `13_helical_amyloid.md` — helical/amyloid track (Tree A).
- `14_tomo_sta.md` — `relion --tomo` STA pipeline (Tree A).
- `16_interop_cryosparc.md`, `17_interop_cryodrgn.md`, `18_interop_chimerax_coot_phenix.md`, `19_interop_coordinates.md` — interop (Trees D/E).
- `20_troubleshooting.md`, `21_error_lookup.md` — diagnostic playbook and exact error-string lookup (Tree B).
- Installed sibling skills handed execution: **cryosparc** (Tree E round-trip), **cryolo** (picking), **mask** (mask building, Tree D), **phenix** / **coot** / **chimerax** (model building/refinement, Tree D), **cryo-flex-knowledge** (DynaMight / continuous heterogeneity, Trees C/E), **structural-strategy** (what-order/why decisions for model building).

---

## Sources

Files read:
- `references/skill/relion/references/00_overview.md` — pipeline order, exit sentinels, `inspect_project.py` workflow, version map.
- `references/skill/relion/references/08_refine3d.md` — continuation vs fresh (§7), Blush (§5), output file set (§6), GPU-memory tactics, failure table.
- `references/skill/relion/references/09_mask_postprocess_localres.md` — mask/PostProcess/LocalRes outputs (`postprocess.mrc` vs `*_unfil.mrc`).
- `references/skill/relion/references/11_subtract_multibody.md` — subtraction/multibody consume consensus optimiser; multibody continue construction.
- `references/official_docs/relion5_docs_source_map_2026-06-04.md` — SPA stage order, source-precedence rule, program→source map.
- `scripts/inspect_project.py` — read-only guarantee (L10-12), sentinel map (L29-34), `run.err` noise filter (L37-50), usage (L13-18).

Live binary / source re-confirmed on this host:
- `relion_refine --help` (RELION 5.0.0-commit-3d6c20, `<RELION_BIN>/relion_refine`) — `--helix` (help L64), `--ios`/`--tomograms`/`--trajectories` (L13-15), `--solvent_correct_fsc`.
- `references/cli/relion5_cli_capture_20260604/help/relion_refine.txt` — same flag lines (L13-15, L64).
- `references/source/relion_ver5.0/src/pipeline_jobs.cpp` — `--continue` construction for Class2D (`:3180`), Class3D (`:3462`), InitialModel (`:3856`), AutoRefine (`:4347`); multibody `--solvent_correct_fsc --multibody_masks` (`:4746`); optimiser-name guard (`:4336-4342`).
- Sentinel file names: `src/pipeline_control.h:32-35` (files) vs `:37-39` (exit-code functions) — per environment brief.
- Fixture (READ-ONLY) `<RELION_PROJECT_FIXTURE>/` — `_rlnJobIsTomo` field in `job.star`; failure patterns `Polish/job040,041` (MPI param-estimation), `MultiBody/job087,089` (GPU OOM → missing `run_data.star`).
- Site/host facts (verified-environment brief, not RELION universals): `csparc2star.py` at `csparc2star.py`; cryoDRGN in a conda env (not base PATH); 2× RTX 2080 Ti 11 GB.
