# 00 — RELION 5 overview, project layout, version map

## Scope
Orientation file for the RELION 5.0 skill: what RELION 5 is, the three ways to drive it (GUI, raw `relion_*` CLI, Schemes/on-the-fly), the canonical single-particle (SPA) stage order, the on-disk project layout (per-job-type folders, `default_pipeline.star`, hidden `.gui_*job.star`, per-job `job.star`/`note.txt`, exit sentinels, `Trash/`), a version map (3.1→5.1), the source-precedence rule that governs every factual claim in this skill, and how to begin a diagnosis with the read-only `scripts/inspect_project.py`. Verified against the installed binary `RELION version: 5.0.0-commit-3d6c20` and the read-only 4.0-beta fixture `<RELION_PROJECT_FIXTURE>`.

---

## 1. What RELION 5 is

RELION (REgularised LIkelihood OptimisatioN) is an empirical-Bayesian cryo-EM structure-determination package from the Scheres group at MRC-LMB, distributed GPLv2 (`source/index.rst:4`). RELION 5.0 covers the entire SPA workflow plus a rewritten sub-tomogram-averaging (STA) pipeline. The installed build on this server is:

```
$ relion_refine --version
RELION version: 5.0.0-commit-3d6c20
Precision: BASE=double, CUDA-ACC=single
```

Note the GUI launcher binary (`relion`) on this host fails to start (`relion: error while loading shared libraries: libfltk.so.1.3`), so on this server RELION is effectively a **headless / CLI install** — drive it through the raw `relion_*` programs or Schemes, not the GUI. Version checks should use a worker binary (`relion_refine --version`), not `relion --version`.

Two precision facts worth keeping: the base build is double precision; the CUDA acceleration path is single precision (from the `--version` banner above). GPU acceleration is Nvidia-CUDA historically; RELION 5.0 adds AMD (HIP/ROCm) and Intel (SYCL) backends and a vectorised CPU path (`source/Whats-new.rst:23-25`). This host has 2× RTX 2080 Ti (11 GB each) — modest GPU memory, which is itself a common failure source (see §8).

---

## 2. Three ways to drive RELION

| Mode | How you invoke it | When to use | Grounding |
|---|---|---|---|
| **GUI pipeline** | `relion &` launched **from the project directory** | Interactive, exploratory; keeps the job graph for you | `source/Reference/Using-RELION.rst:15-21` |
| **Raw `relion_*` CLI** | `relion_refine_mpi --o ... --i ...` etc., usually via a queue script | Scripting, HPC submission, reproducing/patching a single job, this skill's diagnostics | `note.txt` in every job stores the literal command (fixture `Refine3D/job034/note.txt`) |
| **Schemes / on-the-fly** | `relion_schemer ...`; Schemes live under `Schemes/<name>/scheme.star` | Automated, decision-based pipelines; real-time data collection | `source/Onthefly.rst:6`, `Whats-new.rst:48-50` |

Key GUI mental model (`Using-RELION.rst:17-21`): one **project directory** per structure; always launch the GUI from it. Each job type writes to its own directory (e.g. `Class2D/`), and jobs inside get consecutive numbers (`Class2D/job010`). Output rootnames inside a job dir are **fixed** (e.g. `Class2D/job010/run`). Human-friendly job names are **aliases**, implemented as symlinks (e.g. `Select/side_view/` → `Select/job023/` in the fixture). The whole graph is stored in `default_pipeline.star`.

The `relion_*` programs are what the GUI/Schemes actually exec. The literal command for any past job is recorded verbatim in that job's `note.txt`. Example from the fixture (`Refine3D/job034/note.txt`, a 4.0-beta auto-refine):

```
`which relion_refine_mpi` --o Refine3D/job034/run --auto_refine --split_random_halves \
  --i JoinStar/job032/join_particles.star --ref Class3D/job033/run_it025_class002.mrc \
  --firstiter_cc --ini_high 20 --dont_combine_weights_via_disc --scratch_dir /processing \
  --pool 30 --pad 2 --skip_gridding --ctf --particle_diameter 180 --flatten_solvent \
  --zero_mask --oversampling 1 --healpix_order 2 --auto_local_healpix_order 4 \
  --offset_range 5 --offset_step 2 --sym C1 --low_resol_join_halves 40 --norm --scale \
  --j 3 --gpu "" --pipeline_control Refine3D/job034/
```

`--scratch_dir /processing` and queue submission via `sbatch` + a site `queue.sh` are **site conventions** (this server), not RELION universals — treat them as illustration. STA mode is launched separately: `relion --tomo` (`source/Whats-new.rst:29`, `STA_tutorial/Introduction.rst:31`). CCP-EM's python pipeliner can be launched with `relion --ccpem &` (`Whats-new.rst:54`).

---

## 3. Canonical SPA stage order

RELION 5's SPA workflow, in pipeline order (`SPA_tutorial/Introduction.rst:5`, `relion5_docs_source_map_2026-06-04.md:48-49`):

```
import → motioncorr → ctf → pick → extract → 2D class → select →
initialmodel → 3D class → refine3d → mask/postprocess →
ctfrefine → polish → localres → modelbuilding(ModelAngelo) → flexibility(DynaMight)
```

| Stage | Job type label (`_rlnJobTypeLabel`) | Primary program | Reference file |
|---|---|---|---|
| Import movies/mics/particles | `relion.import` | `relion_import` | `04_preprocessing.md` |
| Motion correction | `relion.motioncorr` | `relion_run_motioncorr[_mpi]` | `04_preprocessing.md` |
| CTF estimation | `relion.ctffind` | `relion_run_ctffind[_mpi]` | `04_preprocessing.md` |
| Auto-picking | `relion.autopick` / `relion.manualpick` | `relion_autopick[_mpi]` | `05_picking_extraction.md` |
| Particle extraction | `relion.extract` | `relion_preprocess[_mpi]` | `05_picking_extraction.md` |
| 2D classification | `relion.class2d` | `relion_refine[_mpi]` | `06_class2d_select.md` |
| Subset selection / class ranking | `relion.select` | `relion_class_ranker`, GUI select | `06_class2d_select.md` |
| Initial model (VDAM) | `relion.initialmodel` | `relion_refine[_mpi]` | `07_initialmodel_class3d.md` |
| 3D classification | `relion.class3d` | `relion_refine[_mpi]` | `07_initialmodel_class3d.md` |
| 3D auto-refine | `relion.refine3d` | `relion_refine[_mpi]` | `08_refine3d.md` |
| Mask creation | `relion.maskcreate` | `relion_mask_create` | `09_mask_postprocess_localres.md` |
| Post-processing | `relion.postprocess` | `relion_postprocess` | `09_mask_postprocess_localres.md` |
| Local resolution | `relion.localres` | `relion_localres` | `09_mask_postprocess_localres.md` |
| CTF refinement | `relion.ctfrefine` | `relion_ctf_refine[_mpi]` | `10_ctfrefine_polish.md` |
| Bayesian polishing | `relion.polish` / `relion.polish.train` | `relion_motion_refine[_mpi]` | `10_ctfrefine_polish.md` |
| Particle subtraction | `relion.subtract` | `relion_particle_subtract[_mpi]` | `11_subtract_multibody.md` |
| Multi-body refinement | `relion.multibody` | `relion_refine[_mpi]` + `relion_flex_analyse` | `11_subtract_multibody.md` |
| Join STAR | `relion.joinstar` | `relion_star_handler` | `01_star_and_metadata.md`, `02_project_job_tree.md` |
| Model building | `relion.modelangelo` | `relion_python_modelangelo` | `18_interop_chimerax_coot_phenix.md` (cross-link `phenix`, `coot`) |
| Flexibility | `relion.dynamight` | `relion_python_dynamight` | (cross-link `cryo-flex-knowledge`) |

The label strings above are confirmed from real fixture `job.star` files and `default_pipeline.star` (e.g. `relion.refine3d`, `relion.class3d`, `relion.import`, `relion.motioncorr`, `relion.ctffind`, `relion.extract`, `relion.class2d`, `relion.select`, `relion.initialmodel`, `relion.joinstar` all appear in `<RELION_PROJECT_FIXTURE>/default_pipeline.star`). `relion.polish.train` / `relion.multibody` are per the verified environment notes; `relion.autopick`/`relion.manualpick`/`relion.modelangelo`/`relion.dynamight` are standard but not present in this older fixture — confirm exact strings against `pipeline_jobs.cpp` or the live `job.star` of such a job before quoting (see `03_cli_inventory.md`).

Not every stage is mandatory or strictly linear: CTF-refine ↔ polish ↔ refine3d iterate; multi-body and subtraction branch off a finished consensus refinement; helical/amyloid and STA are parallel tracks (`13_helical_amyloid.md`, `14_tomo_sta.md`).

---

## 4. Project directory layout

A RELION project directory contains one folder per job type, a pipeline-graph file, hidden GUI state, and a Trash. Real top level of the fixture (RELION job-type dirs in **bold**; the rest are user/third-party):

```
Import/  MotionCorr/  CtfFind/  Extract/  Class2D/  Select/  InitialModel/
Class3D/  Refine3D/  MaskCreate/  PostProcess/  CtfRefine/  Polish/
Subtract/  MultiBody/  JoinStar/
default_pipeline.star
.gui_importjob.star  .gui_motioncorrjob.star  .gui_ctffindjob.star  ... .gui_projectdir
Trash/
ccp4/  phenix/  cryosparc/  cryodrgn/  locspiral/  multi/   (user/interop scratch — NOT RELION)
```

(Job-type dirs and hidden files above are all present in `<RELION_PROJECT_FIXTURE>/`.)

### Key files and folders

| Path | What it is | Grounding |
|---|---|---|
| `default_pipeline.star` | The project graph: jobs, aliases, status, nodes, edges | `Using-RELION.rst:21`; fixture header below |
| `<JobType>/jobNNN/` | One job; output rootnames are fixed inside it | `Using-RELION.rst:18-19` |
| `<JobType>/jobNNN/job.star` | Modern per-job settings: `data_job` + `data_joboptions_values` | fixture `Refine3D/job034/job.star` |
| `<JobType>/jobNNN/note.txt` | Literal executed command(s) + timestamps | fixture `Refine3D/job034/note.txt` |
| `<JobType>/jobNNN/run.out`, `run.err` | stdout / stderr of the job | `relion5_docs_source_map_2026-06-04.md:108` |
| `RELION_JOB_EXIT_SUCCESS` etc. | Exit sentinels (files) — see §6 | `src/pipeline_control.h:32-35` |
| `.gui_<jobtype>job.star` | Hidden GUI defaults: the **last-used** parameters per job type (NOT per job) | fixture hidden files |
| `<alias>/` (symlink) | Human-friendly alias → `jobNNN/` | `Using-RELION.rst:20`; fixture `Select/side_view → job023` |
| `Trash/` | Deleted jobs (recoverable until emptied) | `Using-RELION.rst:70-72` |
| `.Nodes/`, `.TMP_runfiles/`, `.gui_projectdir` | Hidden pipeliner bookkeeping | fixture |

`.gui_*job.star` are the **GUI's per-job-type memory** of the last parameters you entered, distinct from each job's own `job.star`. Do not confuse them: edit a job's behaviour via its `job.star`, not the dotfile.

### `default_pipeline.star` structure (fixture header)

```
data_pipeline_general
_rlnPipeLineJobCounter   90

data_pipeline_processes
loop_
_rlnPipeLineProcessName #1
_rlnPipeLineProcessAlias #2
_rlnPipeLineProcessTypeLabel #3
_rlnPipeLineProcessStatusLabel #4
Import/job001/        None  relion.import      Succeeded
MotionCorr/job002/    None  relion.motioncorr  Succeeded
...
Select/job023/  Select/side_view/  relion.select  Succeeded
```

It also carries node and edge tables (`data_pipeline_nodes` / `data_pipeline_input_edges` / `data_pipeline_output_edges`) that wire job outputs to downstream inputs. Status strings seen: `Succeeded`. Other possible values (`Running`, `Failed`, `Aborted`) follow the sentinel semantics in §6. Note this fixture's header carries `# version 30001` — RELION writes a version tag into pipeline/job STARs; a 4.0-beta project read by a 5.0 install is normal and expected.

### `job.star` structure (fixture `Refine3D/job034/job.star`)

```
data_job
_rlnJobTypeLabel    relion.refine3d
_rlnJobIsContinue   0
_rlnJobIsTomo       0

data_joboptions_values
loop_
_rlnJobOptionVariable #1
_rlnJobOptionValue #2
fn_img  JoinStar/job032/join_particles.star
fn_ref  Class3D/job033/run_it025_class002.mrc
do_ctf_correction  Yes
...
```

`_rlnJobIsContinue` flags a continued job; `_rlnJobIsTomo` flags an STA job (0 here = SPA). The `data_joboptions_values` loop is the full GUI parameter set. See `02_project_job_tree.md` for the complete field walk.

---

## 5. Version map

| Release | Headline additions (what changes behaviour/metadata) | Grounding |
|---|---|---|
| **3.1** | **Optics groups**: `data_optics` block + `rlnOpticsGroup`; higher-order aberration correction (trefoil/tetrafoil, Cs deviation), anisotropic magnification; auto-upgrade of older STARs (one-way — 3.1 STARs can't be read by older RELION); `External` job type; first `Schedules` framework | `Whats-new.rst:57-94` |
| **4.0** | **VDAM** gradient refinement (replaces SAGD for initial model; faster 2D/3D class); **Schemes** (renamed from Schedules) for on-the-fly; **class-ranker** (`relion_class_ranker`, automated 2D class selection); **tomo rewrite** (pseudo-subtomograms, CTF-refine + polish for tomo); CCP-EM pipeliner integration | `Whats-new.rst:31-54` |
| **5.0** | **Blush** regularisation (denoising CNN inside Class3D/Refine3D/MultiBody; GUI `do_blush` → `--blush`); **DynaMight** (continuous heterogeneity, VAE deformations); **ModelAngelo** (automated atomic model building); **AMD/Intel GPU** (HIP/ROCm, SYCL); **full STA** pipeline (`relion --tomo`, mdoc→model); filament dendrogram selection | `Whats-new.rst:7-29` |
| **5.1** | Amyloid-focused additions (e.g. enhanced helical/amyloid utilities) | (unverified: not in this docs snapshot, which is release-5.0; confirm against a 5.1 source/docs before quoting specifics) — `13_helical_amyloid.md` |

Practical consequence: **older projects are normal.** This skill runs a 5.0 binary on a 4.0-beta fixture; 5.0 will read 3.1/4.0 STARs and `default_pipeline.star` fine. Going *backwards* (5.0 STAR → older RELION) is the unsupported direction. When a feature flag (`--blush`, VDAM behaviour) is absent from an old job's `note.txt`, that's the project's era, not a bug.

---

## 6. Exit sentinels (critical — files vs functions)

Job completion is signalled by **files written into the job directory** (`src/pipeline_control.h:32-35`):

| File (in job dir) | Meaning |
|---|---|
| `RELION_JOB_EXIT_SUCCESS` | job finished cleanly |
| `RELION_JOB_EXIT_FAILURE` | job errored |
| `RELION_JOB_EXIT_ABORTED` | job was aborted |
| `RELION_JOB_ABORT_NOW` | abort **request** placed by GUI/user; job exits when it sees this |

Do **not** confuse these filenames with the exit **macros** `RELION_EXIT_SUCCESS` / `RELION_EXIT_FAILURE` / `RELION_EXIT_ABORTED` (`src/pipeline_control.h:37-39`): those expand to `pipeline_control_relion_exit(0|1|2)`, the function that *writes* the `RELION_JOB_EXIT_*` sentinel file (when a pipeline output name is set) **and** sets the process exit code (`src/pipeline_control.cpp:24-56`). There is no on-disk file literally named `RELION_EXIT_SUCCESS` — when diagnosing, look for the `RELION_JOB_EXIT_*` files. External jobs must themselves write `RELION_JOB_EXIT_SUCCESS` (and may write `_FAILURE`/`_ABORTED`) plus `RELION_OUTPUT_NODES.star` (`Using-RELION.rst:234-243`).

---

## 7. Source-precedence rule (applies to every claim in this skill)

When sources disagree, trust them in this order (`relion5_docs_source_map_2026-06-04.md:15-21`):

1. **Installed binary** on the target server — `relion_<prog> --help`, `relion_refine --print_metadata_labels`, `relion_refine --version`. This is ground truth for flags and labels on *this* build.
2. **RELION 5.0 source** (`references/source/relion_ver5.0/src`, esp. `pipeline_jobs.cpp` `getCommands*Job` / `initialise*Job`) and **docs source** (`references/source/relion-documents_release-5.0/source`).
3. Rendered official docs (readthedocs release-5.0).
4. RELION method/release papers and first-party talks.
5. Third-party tutorials, forums, HPC notes.

Corollary for authoring: **never invent a flag or filename.** If you cannot ground a claim from (1)–(2), either run the live `--help` to confirm, or mark it `(unverified: ...)`. The captured CLI help on this host lives under `references/cli/relion5_cli_capture_20260604/help` and is a valid stand-in for (1).

---

## 8. How to start a diagnosis

Begin every "my RELION job/project is broken" question with the read-only inspector:

```bash
# whole-project summary (graph, per-job sentinels, real error excerpts, optics/pixel)
python3 scripts/inspect_project.py /path/to/project

# one job, deep
python3 scripts/inspect_project.py /path/to/project Refine3D/job034

# only failed/aborted jobs
python3 scripts/inspect_project.py /path/to/project --failed

# machine-readable
python3 scripts/inspect_project.py /path/to/project --json
```

`inspect_project.py` **never writes** inside the project (header docstring, lines 11–12): it reads `default_pipeline.star`, per-job exit sentinels, tails `run.err` (filtering X11/MPI noise), summarises optics-group / pixel size, and lists which standard outputs each job did/didn't produce. The companion `scripts/check_env.sh` reports the installed RELION/MPI/CUDA/GPU/python state, and `scripts/run_relion.sh` wraps queue submission. `scripts/star_min.py` is the dependency-free STAR reader used by the inspector.

Workflow: run `inspect_project.py` → identify the failed/aborted job → open its `note.txt` (literal command) and `run.out`/`run.err` → match the program and error to the relevant reference file below and to `21_error_lookup.md`.

---

## Common failures / red flags

These are real failures from the fixture (a 4.0-beta project), useful as canonical patterns:

- **Polishing in MPI mode** — `Polish/job040`, `job041` (`relion_motion_refine_mpi`): `run.err` says `Parameter estimation is not supported in MPI mode.` Training / parameter-estimation polish must run **single-rank** (no `_mpi` / no `mpirun`). The surrounding `MPI_ABORT was invoked ... errorcode 1` lines are noise; the real cause is the one quoted line. See `10_ctfrefine_polish.md`.
- **GPU out-of-memory in multi-body / flex analysis** — `MultiBody/job087`, `job089` (`relion_flex_analyse`): the root cause in `run.err` is `ERROR: out of memory in .../custom_allocator.cuh ... A GPU-function failed to execute.` On these 11 GB RTX 2080 Ti cards this is a memory limit; the downstream `MetaDataTable::read: File run_data.star does not exist` is a **secondary** symptom (the upstream GPU job never produced its output). Fix the OOM (fewer parallel bodies / smaller pool / box) before chasing the missing-file error. See `11_subtract_multibody.md`.
- **GUI won't launch** — on this host `relion` fails with `libfltk.so.1.3: cannot open shared object file`. Use the worker binaries (`relion_refine --version`) for version checks and drive jobs via CLI/Schemes.
- **"Job failed" but no `RELION_JOB_EXIT_FAILURE`** — a killed-by-queue or OOM-killed process may leave no sentinel; treat a job with a running-but-stale state and a truncated `run.out` as crashed. Confirm with the queue logs.
- **Misreading exit semantics** — looking for a `RELION_EXIT_SUCCESS` *file* will always fail; the file is `RELION_JOB_EXIT_SUCCESS` (§6).

---

## Cross-links

- `01_star_and_metadata.md` — STAR syntax, `data_optics`, metadata labels, `relion_refine --print_metadata_labels`.
- `02_project_job_tree.md` — `default_pipeline.star`, `job.star`, nodes/edges, aliases, status in depth.
- `03_cli_inventory.md` — the full `relion_*` program list and where each flag is grounded.
- `04_preprocessing.md` / `05_picking_extraction.md` / `06_class2d_select.md` / `07_initialmodel_class3d.md` / `08_refine3d.md` / `09_mask_postprocess_localres.md` / `10_ctfrefine_polish.md` / `11_subtract_multibody.md` — per-stage detail.
- `12_conventions_symmetry.md` — Euler-angle direction, shifts, symmetry names.
- `13_helical_amyloid.md` — helical/amyloid track (3.1 priors, 5.1 amyloid).
- `14_tomo_sta.md` — `relion --tomo` STA pipeline.
- `15_schemes_automation.md` — Schemes / on-the-fly (`relion_schemer`).
- `16_interop_cryosparc.md` / `17_interop_cryodrgn.md` / `18_interop_chimerax_coot_phenix.md` / `19_interop_coordinates.md` — interop.
- `20_troubleshooting.md` / `21_error_lookup.md` / `22_decision_trees.md` — diagnosis.
- Sibling installed skills to hand off execution: **chimerax**, **coot**, **phenix**, **mask**, **cryosparc**, **cryolo**, **cryo-flex-knowledge** (DynaMight/heterogeneity), **structural-strategy**.

---

## Sources

Files read:
- `references/source/relion-documents_release-5.0/source/Whats-new.rst` (version map: 3.1 optics groups L57-94; 4.0 VDAM/Schemes/class-ranker/tomo L31-54; 5.0 Blush/DynaMight/ModelAngelo/AMD-Intel-GPU/STA L7-29; `relion --tomo` L29; `relion --ccpem` L54)
- `references/source/relion-documents_release-5.0/source/index.rst` (what RELION is, L4; ToC)
- `references/source/relion-documents_release-5.0/source/SPA_tutorial/Introduction.rst` (canonical SPA stage order, L5)
- `references/source/relion-documents_release-5.0/source/Reference/Using-RELION.rst` (GUI pipeline model L15-21, aliases L20, Trash/clean L70-82, External job + sentinels L234-243)
- `references/source/relion-documents_release-5.0/source/Onthefly.rst` (Schemes-based on-the-fly, L6, L18, L28)
- `references/official_docs/relion5_docs_source_map_2026-06-04.md` (source-precedence rule L15-21; SPA flow L48-49; run.out/run.err L108)
- `scripts/inspect_project.py` (header/usage L1-34), and directory listing of `scripts/`

Live binary / fixture inspected on this host:
- `relion_refine --version` → `RELION version: 5.0.0-commit-3d6c20`, `Precision: BASE=double, CUDA-ACC=single`
- `relion --version` → fails: `libfltk.so.1.3: cannot open shared object file` (GUI unusable on this host)
- `which relion_refine relion_import relion` → `<RELION_BIN>/...`
- `<RELION_PROJECT_FIXTURE>/` (READ-ONLY): top-level listing; `default_pipeline.star` header (`_rlnPipeLineJobCounter 90`, process loop, labels, aliases); `Refine3D/job034/job.star` (`_rlnJobTypeLabel relion.refine3d`, `_rlnJobIsContinue`, `_rlnJobIsTomo`, `data_joboptions_values`); `Refine3D/job034/note.txt` (literal `relion_refine_mpi` command, `--scratch_dir /processing`); `Polish/job040/run.err` (`Parameter estimation is not supported in MPI mode.`); `MultiBody/job087/run.err` (`out of memory ... custom_allocator.cuh ... A GPU-function failed to execute`)

Source anchors cited from verified-environment notes (not re-read here): `src/pipeline_control.h:32-35` (exit-sentinel files) and `:37-39` (exit-code functions).
