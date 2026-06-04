# 02 — Project graph, job.star, logs, exit sentinels

## Scope
How a RELION project directory is wired together on disk: the `default_pipeline.star` directed graph (jobs = processes, files = nodes, edges = I/O), the anatomy of a single `Jobtype/jobNNN/` folder (`job.star`, `note.txt`, `run.out`/`run.err`, `job_pipeline.star`, continuation files), the `RELION_JOB_EXIT_*` / `RELION_JOB_ABORT_NOW` sentinel **files** that drive completion/abort signalling since RELION 3.1, legacy `run.job` and aliases, `Trash/` deletion and gentle/harsh clean, and how one job references another by node name. This is what `scripts/inspect_project.py` parses; read it after this file. Conventions here are version-stable from 3.1 through 5.0/5.1; the validation fixture is a 4.0-beta project read by a 5.0 install, which is normal.

---

## 1. `default_pipeline.star` — the project graph

One file lives at the **project root** (`default_pipeline.star`) and is the single source of truth for the whole pipeline. Run `relion` from the project directory; the GUI keeps this file in sync. It is a multi-table STAR file with four/five `data_*` blocks. (`source/Reference/Using-RELION.rst:21`; structure confirmed live on fixture head/tail.)

> If `default_pipeline.star` gets corrupted, restore the copy that each job snapshots as `Jobtype/jobNNN/job_pipeline.star` from the last-executed job (docs `Using-RELION.rst:22`, and see §3.4).

### 1.1 `data_pipeline_general`
A single counter:

```
data_pipeline_general
_rlnPipeLineJobCounter   90
```

`_rlnPipeLineJobCounter` is the **next** job number the pipeliner will hand out (here next job = `job090`; the fixture's highest existing job is `job089`). It is `PipeLine::job_counter` in source (`src/pipeliner.h:81`, init `=1` at line 91). When a job overwrites an existing slot the counter is decremented (`setJobCounter`, `pipeliner.h:149`).

### 1.2 `data_pipeline_processes` — one row per job
A `loop_` with exactly four columns (live, fixture `default_pipeline.star`):

| Column | Meaning | Example value |
|---|---|---|
| `_rlnPipeLineProcessName` | job directory (with trailing `/`) | `Refine3D/job034/` |
| `_rlnPipeLineProcessAlias` | symlink alias or `None` | `Select/side_view/` |
| `_rlnPipeLineProcessTypeLabel` | job-type label | `relion.refine3d` |
| `_rlnPipeLineProcessStatusLabel` | current status | `Succeeded` / `Failed` / `Running` / `Aborted` / `Scheduled` |

These map to the `Process` C++ struct (`src/pipeliner.h:34-69`: `name`, `alias`, `typeLabel`, `status`). The job number is parsed from the name after `/job` (`pipeliner.h:63-67`).

**Status labels** are a fixed enumeration (`src/pipeline_jobs.h:601-617`):

| StatusLabel string | Constant | Code |
|---|---|---|
| `Running` | `PROC_RUNNING` | running now |
| `Scheduled` | `PROC_SCHEDULED` | queued/schemed, not yet executed |
| `Succeeded` | `PROC_FINISHED_SUCCESS` (`=2`) | finished, reported success |
| `Failed` | `PROC_FINISHED_FAILURE` (`=3`) | reported an error |
| `Aborted` | `PROC_FINISHED_ABORTED` (`=4`) | aborted by the user |

> Older projects on disk may carry the integer status in a `_rlnPipeLineProcessStatus` column instead of/with the `*Label` string; a 5.0 install reads both and re-emits the label form. The fixture (4.0-beta) already uses the label form shown above.

Real fixture excerpt (note alias column and two `Failed` Polish jobs + two `Failed` MultiBody jobs):

```
Refine3D/job034/        None relion.refine3d  Succeeded
Select/job023/  Select/side_view/  relion.select  Succeeded
Polish/job040/          None relion.polish     Failed
MultiBody/job087/       None relion.multibody  Failed
```

`_rlnPipeLineProcessTypeLabel` values seen on the fixture: `relion.import`, `relion.motioncorr`, `relion.ctffind`, `relion.extract`, `relion.class2d`, `relion.select`, `relion.initialmodel`, `relion.joinstar`, `relion.class3d`, `relion.refine3d`, `relion.maskcreate`, `relion.postprocess`, `relion.polish`, `relion.ctfrefine`, `relion.subtract`, `relion.multibody`. These are the same strings used for `_rlnJobTypeLabel` in `job.star` (§2.1) and are the canonical job-type IDs across the inventory — see `03_cli_inventory.md`.

### 1.3 `data_pipeline_nodes` — one row per file in the graph
A `loop_` of every file that participates as input/output of any job:

```
_rlnPipeLineNodeName        Refine3D/job034/run_data.star
_rlnPipeLineNodeTypeLabel   ParticlesData.star.relion.refine3d
```

The node type label is a dotted type string, e.g. `MicrographMoviesData.star.relion`, `MicrographsData.star.relion.motioncorr`, `DensityMap.mrc`, `DensityMap.mrc.relion.halfmap.refine3d`, `ProcessData.star.relion.optimiser.refine3d`, `LogFile.pdf.relion.ctffind` (all live from fixture). RELION 5.0 uses these v50001-style label strings; the pipeliner converts old v30001 numeric node types on read (`PipeLine::convertOldNodeTypeLabel`, `src/pipeliner.h:237`). Node naming/types are detailed in `01_star_and_metadata.md`.

### 1.4 Edges — the directed graph
Two `loop_` tables encode the DAG (live, fixture `job_pipeline.star` and `default_pipeline.star` tails):

```
data_pipeline_input_edges
_rlnPipeLineEdgeFromNode   _rlnPipeLineEdgeProcess
JoinStar/job032/join_particles.star   Refine3D/job034/

data_pipeline_output_edges
_rlnPipeLineEdgeProcess   _rlnPipeLineEdgeToNode
Refine3D/job034/   Refine3D/job034/run_data.star
```

- **Input edge** = `fromNode -> process`: a file produced elsewhere is consumed by this job.
- **Output edge** = `process -> toNode`: this job produces this file.

So `JoinStar/job032/join_particles.star -> Refine3D/job034/` (input) and `Refine3D/job034/ -> Refine3D/job034/run_class001.mrc` (output) together let the GUI's *Input to this job* / *Output from this job* lists walk the history both directions (docs `Using-RELION.rst:44`). `inputNodeList`/`outputNodeList` are the in-memory form (`src/pipeliner.h:43-44`).

---

## 2. The job folder: `Jobtype/jobNNN/`

Output names inside a job dir are fixed, e.g. `Class2D/job010/run`, `Refine3D/job034/run` (docs `Using-RELION.rst:18-19`). Live listing of `Refine3D/job034/` shows the standard set: `job.star`, `note.txt`, `job_pipeline.star`, `run.out`, `run.err`, `run_submit.script`, `RELION_JOB_EXIT_SUCCESS`, plus the program's own `run_*` outputs and `run_itNNN_*` iteration files.

### 2.1 `job.star` — the parameters that were run
Two `data_*` blocks (live, `Refine3D/job034/job.star`):

```
data_job
_rlnJobTypeLabel   relion.refine3d
_rlnJobIsContinue  0
_rlnJobIsTomo      0

data_joboptions_values
loop_
_rlnJobOptionVariable  _rlnJobOptionValue
fn_img   JoinStar/job032/join_particles.star
fn_ref   Class3D/job033/run_it025_class002.mrc
sym_name C1
use_gpu  Yes
qsub     sbatch
qsubscript <RELION_QUEUE_SCRIPT>
scratch_dir /processing
...
```

- `data_job`: `_rlnJobTypeLabel` (the job-type ID, e.g. `relion.refine3d`, `relion.polish.train`, `relion.multibody`, `relion.class2d`), `_rlnJobIsContinue` (`0`/`1` — was this a continuation run), `_rlnJobIsTomo` (`0`/`1` — RELION 4.0+/5.0 tomography flag; `0` for this SPA project). EMDL labels `EMDL_JOB_IS_CONTINUE` etc. are read/written in `RelionJob::read`/`write` (`src/pipeline_jobs.cpp:437,530`).
- `data_joboptions_values`: a `loop_` of every GUI field as `variable value` pairs. These are the **GUI parameters**, not the command line — RELION translates them into the actual `relion_*` flags in `pipeline_jobs.cpp` (the `getCommands*Job` functions). The fixture queue fields (`qsub=sbatch`, `qsubscript=<RELION_QUEUE_SCRIPT>`, `scratch_dir=/processing`) are **site-specific** illustration, not universal — see `site_config.md`.

> To recover the literal flags from a `job.star`, do not re-derive them — read `note.txt` (§2.2), which records exactly what ran.

### 2.2 `note.txt` — the literal executed command + timestamp
The pipeliner appends to `note.txt` on every execution (`src/pipeliner.cpp:707-715`: `ofs << " ++++ Executing new job on " << ctime(&now)` then `" ++++ with the following command(s): "`). Live `Refine3D/job034/note.txt`:

```
 ++++ Executing new job on Wed Mar 16 20:59:28 2022
 ++++ with the following command(s):
`which relion_refine_mpi` --o Refine3D/job034/run --auto_refine --split_random_halves \
  --i JoinStar/job032/join_particles.star --ref Class3D/job033/run_it025_class002.mrc \
  --firstiter_cc --ini_high 20 --dont_combine_weights_via_disc --scratch_dir /processing \
  --pool 30 --pad 2 --skip_gridding --ctf --particle_diameter 180 --flatten_solvent \
  --zero_mask --oversampling 1 --healpix_order 2 --auto_local_healpix_order 4 \
  --offset_range 5 --offset_step 2 --sym C1 --low_resol_join_halves 40 --norm --scale \
  --j 3 --gpu "" --pipeline_control Refine3D/job034/
```

This is the **best forensic artifact** in the whole project: the exact binary, every flag, the timestamp. Note `--pipeline_control Refine3D/job034/` — that argument is what tells the binary to write its exit sentinels into this dir (§4). `note.txt` is append-only across continuations, so it accumulates one block per run. (Users may also add free-text comments here via the GUI *Job actions* menu, docs `Using-RELION.rst:64`.)

### 2.3 `run.out` / `run.err` — stdout / stderr
The GUI redirects each command to `outputname + "run.out"` and `outputname + "run.err"` via `>> run.out 2>> run.err` (`src/pipeline_jobs.cpp:760`, template tokens `XXXoutfileXXX`/`XXXerrfileXXX` at lines 601-602). `run.err` **should ideally be empty**; any text is worth inspection (docs `Using-RELION.rst:47`). On the fixture, `Refine3D/job034/run.err` contains only `No protocol specified` — that is **X11/display noise, not a real error** (the job Succeeded). `inspect_project.py` filters exactly this class of noise (its `NOISE` tuple: `No protocol specified`, `MPI_ABORT was invoked`, `libGL error`, `QStandardPaths`, etc.) so the real error line surfaces. The hidden `.run.out.tail`/`.run.err.tail` files are the GUI's rolling tail caches.

### 2.4 `run_submit.script`
Present when a job was submitted to a queue (`do_queue Yes`). It is the rendered queue script (here from `qsubscript <RELION_QUEUE_SCRIPT>`). Absent for jobs run locally. Queue submission and the `qsub`/`qsubscript`/`min_dedicated` fields are covered in `15_schemes_automation.md` and `site_config.md`.

---

## 3. Per-job snapshots and continuation

### 3.4 `job_pipeline.star` — the mini-pipeline snapshot
Every job writes a `job_pipeline.star` containing **only that job's** slice of the graph: its one process row, its nodes, and its input/output edges (live `Refine3D/job034/job_pipeline.star`). Same four/five `data_pipeline_*` blocks as the master, scoped to one job. The pipeliner copies `run.job`, `note.txt`, and `job_pipeline.star` together when importing/exporting scheduled jobs (`src/pipeliner.cpp:1744`, `replaceFilesForImportExportOfScheduledJobs`). This is your backup if the root `default_pipeline.star` is corrupted.

### 3.5 Continuation files
When you *continue* a job (GUI turns *Run!* into *Continue now!*), no new job dir is made; the same dir is reused and `_rlnJobIsContinue` is set to `1`. For iterative refiners (`relion_refine`: Class2D/Class3D/Refine3D), a continuation needs an `_optimiser.star` to resume from, and new files carry the continued iteration in the name, e.g. `run_ct23_*` / `run_ctNN_*` (docs `Using-RELION.rst:42`; the command gets `--continue <fn_cont>`, `src/pipeline_jobs.cpp:3180`). On the fixture, `Refine3D/job079` output edges include `run_it017_optimiser.star`, and MultiBody `job087` produced `run_ct2_half1_body001_unfil.mrc` — the `_ctN_` infix is the continuation marker. Other job types (MotionCorr, CtfFind, AutoPick, Extract) "continue" by simply processing only micrographs not done before (docs `Using-RELION.rst:43`).

`fn_cont` in `job.star` (empty `""` on job034 since it was a fresh auto-refine) holds the optimiser path when continuing.

---

## 4. Exit sentinels — completion/abort signalling (since 3.1)

**Since RELION 3.1 the pipeliner determines job outcome from sentinel FILES in the job dir, not from the presence of output files.** Each is an (empty) file whose name is the literal macro string (`src/pipeline_control.h:32-35`):

| File (exact name, in job dir) | Meaning | Written by |
|---|---|---|
| `RELION_JOB_EXIT_SUCCESS` | job finished cleanly | binary on success |
| `RELION_JOB_EXIT_FAILURE` | binary hit an error | binary on failure |
| `RELION_JOB_EXIT_ABORTED` | binary aborted on request | binary on abort |
| `RELION_JOB_ABORT_NOW` | **request** to abort (created by GUI *Job actions*) | GUI / user |

Mechanism (`src/pipeline_control.cpp`): the binary is told the job dir via `--pipeline_control Jobtype/jobNNN/` (see job034's `note.txt`), stored in `pipeline_control_outputname` (`pipeline_control.cpp:22`). `pipeline_control_relion_exit()` writes `<dir>RELION_JOB_EXIT_SUCCESS`/`_FAILURE`/`_ABORTED` (lines 27-42). `pipeline_control_check_abort_job()` polls for `<dir>RELION_JOB_ABORT_NOW` (line 75); the running binary checks this periodically and, if found, aborts and writes `RELION_JOB_EXIT_ABORTED`. Before each run, `pipeline_control_delete_exit_files()` removes stale exit files (lines 86-101), and `runJob` clears any leftover exit/abort files first (`src/pipeliner.cpp:649`). The GUI then maps the sentinel to the StatusLabel (§1.2).

**Do not confuse** the on-disk filenames with the exit **macros** `RELION_EXIT_SUCCESS`/`_FAILURE`/`_ABORTED` (`pipeline_control.h:37-39`). Those macros simply call `pipeline_control_relion_exit(0|1|2)` — the very function described above that *writes* the `RELION_JOB_EXIT_*` file **and** returns shell exit code `0`/`1`/`2`. So there is no file literally named `RELION_EXIT_SUCCESS`; the file on disk is `RELION_JOB_EXIT_SUCCESS`.

**External jobs** must honour the same contract by hand: on completion create an empty `RELION_JOB_EXIT_SUCCESS`; optionally `RELION_JOB_EXIT_ABORTED`/`RELION_JOB_EXIT_FAILURE`; and if `RELION_JOB_ABORT_NOW` appears, abort, write `RELION_JOB_EXIT_ABORTED`, remove `RELION_JOB_ABORT_NOW`, exit (docs `Using-RELION.rst:234-243`). They also emit `RELION_OUTPUT_NODES.star` (a `data_output_nodes` table of `_rlnPipeLineNodeName`/`_rlnPipeLineNodeType`) to register output edges (`Using-RELION.rst:237-240`, `getOutputNodesFromStarFile`, `src/pipeliner.h:206`).

---

## 5. Legacy `run.job` and aliases

### 5.1 Legacy `run.job`
Projects from RELION ≤ 3.0 have `run.job` (a flat key/value file) instead of `job.star`. The reader falls back to it only when `job.star` is **absent**: `if (!exists(job.star) && exists(run.job))` it parses `run.job` and reads `is_continue` from a line `is_continue == true` (`src/pipeline_jobs.cpp:368-393`). The fixture has `job.star` (4.0-beta), so `run.job` is not present; expect `run.job` only in much older projects. Hidden GUI defaults files use the same pattern: `.gui_<jobtype>job.star` or `.gui_<jobtype>run.job` (e.g. `.gui_manualpick`, `src/pipeline_jobs.cpp:2085-2086`).

### 5.2 Aliases
An alias is a **symbolic link** to the job dir with a human-readable name, stored in `_rlnPipeLineProcessAlias` (`None` if unset) and set via the GUI *Job actions* menu (`PipeLine::setAliasJob`, `src/pipeliner.h:212`; docs `Using-RELION.rst:20,64`). Fixture examples: `Select/job023/ -> Select/side_view/`, `Select/job025/ -> Select/top_view/`, `JoinStar/job032/ -> JoinStar/combined/`, `Class3D/job055/ -> Class3D/RF047_E12/`, `MaskCreate/job081/ -> MaskCreate/segger_079_0045_PRC1_E2/`. Aliases never change the canonical `jobNNN` path; node names and edges always use the canonical `Jobtype/jobNNN/` form, so resolve aliases to job numbers when tracing the graph.

---

## 6. Deletion, `Trash/`, and gentle/harsh clean

**Delete** moves the entire job dir into `Trash/` (recoverable until you empty Trash). The command is literally `rm -rf Trash/<alldirs>; mv -f <alldirs> Trash/<firstdirs>/. ; rm -rf <alldirs>` — three operations, including the final cleanup of the original path (`src/pipeliner.cpp:1136`); `undeleteJob` moves it back (`pipeliner.cpp:1384-1410`). Emptying Trash (GUI *File* menu) frees the space for good (docs `Using-RELION.rst:70-72`).

**Clean** moves only **intermediate** files to Trash, keeping the job in the graph (`PipeLine::cleanupJob(this_job, do_harsh, ...)`, `src/pipeliner.cpp:1424`):
- **Gentle clean** (`do_harsh=false`): removes intermediate iterations but **keeps everything that could be input to another job**, and keeps the last iteration so you could still e.g. run multibody after cleaning (`pipeliner.cpp:1554`). For the fixture's `Refine3D/job034`, gentle clean would trash the `run_itNNN_*` iteration stacks (`run_it000_*` … `run_it018_*`) but keep `run_data.star`, `run_class001.mrc`, `run_half{1,2}_class001_unfil.mrc`, `run_optimiser.star`.
- **Harsh clean** (`do_harsh=true`): also removes files that *could* be input downstream (`pipeliner.cpp:1481,1525,1623,1634`), freeing far more space — heaviest for MotionCorr, Extract, movie-refine, and Polish dirs holding particle/micrograph stacks (docs `Using-RELION.rst:74-77`). MultiBody dirs get extra harsh handling (`pipeliner.cpp:1577`).
- **Protect a dir from harsh clean** by `touch Jobtype/jobNNN/NO_HARSH_CLEAN`; `cleanupAllJobs` skips any dir containing that file (`src/pipeliner.cpp:1668`; docs `Using-RELION.rst:78-82`, e.g. `touch Polish/job098/NO_HARSH_CLEAN`).

`cleanupAllJobs(do_harsh, ...)` runs the above over every job (`pipeliner.cpp:1661`).

---

## 7. How jobs reference each other (worked example)

Refine3D/job034 consumed `JoinStar/job032/join_particles.star` as its particle set:

1. `job.star` records the GUI field: `fn_img  JoinStar/job032/join_particles.star` (and `fn_ref Class3D/job033/run_it025_class002.mrc`).
2. `note.txt` shows the resolved flag: `--i JoinStar/job032/join_particles.star --ref Class3D/job033/run_it025_class002.mrc`.
3. `default_pipeline.star` records the input edges: `JoinStar/job032/join_particles.star -> Refine3D/job034/` and `Class3D/job033/run_it025_class002.mrc -> Refine3D/job034/`.
4. `JoinStar/job032` itself (alias `JoinStar/combined/`, type `relion.joinstar`) merged several Select outputs into `join_particles.star` — so the chain is `Select/* -> JoinStar/job032 -> Refine3D/job034`.

To trace any job's lineage: read its input edges in `default_pipeline.star` (backwards) or its output edges (forwards); cross-check against `note.txt` `--i`/`--ref`/`--o`. Aliases (§5.2) must be resolved to `jobNNN` because edges store canonical names only.

---

## 8. Use `scripts/inspect_project.py`

`scripts/inspect_project.py` (READ-ONLY) parses everything above so you don't have to grep by hand. It reads `default_pipeline.star`, the per-job exit sentinels, tails `run.err` with X11/MPI noise filtered, summarises optics/pixel-size, and reports which standard outputs each job did/didn't produce. Usage:

```
python3 scripts/inspect_project.py PROJECT_DIR              # whole-project summary
python3 scripts/inspect_project.py PROJECT_DIR Refine3D/job034   # one job, deep
python3 scripts/inspect_project.py PROJECT_DIR --failed     # only Failed/Aborted jobs
python3 scripts/inspect_project.py PROJECT_DIR --json       # machine-readable
```

It maps the four sentinel files to `SUCCEEDED`/`FAILED`/`ABORTED`/`ABORT-REQUESTED` and exits `0` on any readable project (it is a report, not a test). Run it first when triaging an unfamiliar or broken project.

---

## Common failures / red flags
- **`Failed` status but no obvious error in run.out** — read `run.err`, but filter X11/MPI noise (`No protocol specified` is benign). On the fixture, `Polish/job040`/`job041` (`relion.polish`) Failed with `relion_motion_refine_mpi`: *"Parameter estimation is not supported in MPI mode"* — Polish **training/parameter-estimation must run single-rank** (`nr_mpi 1`); only the per-frame polishing step is MPI-safe. See `10_ctfrefine_polish.md`.
- **MultiBody `Failed`** — fixture `MultiBody/job087`/`job089` (`relion.multibody`, `relion_flex_analyse`) failed with *"A GPU-function failed to execute"*, then downstream *"MetaDataTable::read: File run_data.star does not exist"* (the missing output is a *symptom*, not the cause). See `11_subtract_multibody.md` and `21_error_lookup.md`.
- **A `RELION_JOB_EXIT_FAILURE` file present** in a job dir = the binary reported failure; trust the sentinel over guessing from output-file presence. A lone `RELION_JOB_ABORT_NOW` left behind = an abort was requested but the binary may not have cleaned it up.
- **Status says `Running` but no process exists** (e.g. fixture's `job_pipeline.star` snapshot shows `Running` because it was captured mid-run) — a stale `Running` in the *root* `default_pipeline.star` with no live PID means the job died without writing a sentinel; mark finished via the GUI or re-run.
- **Editing `default_pipeline.star` by hand** — avoid; let the GUI/pipeliner manage it. If corrupted, restore `Jobtype/jobNNN/job_pipeline.star` from the last good job (§3.4).
- **Aliases mistaken for separate jobs** — `Select/side_view/` and `Select/job023/` are the same job; always resolve to the `jobNNN`.

## Cross-links
- `00_overview.md` — project layout big picture and triage entry point.
- `01_star_and_metadata.md` — STAR multi-table format, node type labels, optics groups.
- `03_cli_inventory.md` — `relion_*` binaries and the `relion.<jobtype>` ID list.
- `10_ctfrefine_polish.md`, `11_subtract_multibody.md` — the fixture's failing Polish/MultiBody jobs.
- `15_schemes_automation.md` — Schemes, scheduled jobs, queue submission, `run_submit.script`.
- `20_troubleshooting.md`, `21_error_lookup.md` — error triage and exact-string lookup.
- `site_config.md` — site queue convention (`qsub`/`qsubscript`/`scratch_dir`) is illustration only.

## Sources
- `relion_ver5.0/src/pipeline_control.h` (lines 31-49: sentinel macro strings + exit functions).
- `relion_ver5.0/src/pipeline_control.cpp` (lines 22-101: exit/abort file write/check/delete logic).
- `relion_ver5.0/src/pipeliner.h` (Process/PipeLine structs, job_counter, alias/cleanup/undelete/node API).
- `relion_ver5.0/src/pipeliner.cpp` (lines 649, 707-715: note.txt + clear exit files; 1136 Trash mv (3-op); 1384-1410 undelete; 1424-1670 cleanupJob/All + NO_HARSH_CLEAN; 1744 export-copy run.job/note.txt/job_pipeline).
- `relion_ver5.0/src/pipeline_jobs.h` (lines 601-617: PROC_* status constants ↔ StatusLabel strings).
- `relion_ver5.0/src/pipeline_jobs.cpp` (lines 361-393 run.job fallback; 437/530 EMDL_JOB_IS_CONTINUE; 601-602/760 run.out/run.err redirect; 1684-1687 --only_do_unfinished; 3180 --continue).
- `relion-documents_release-5.0/source/Reference/Using-RELION.rst` (lines 18-22 job dirs/aliases/default_pipeline; 42-47 continue/run.err; 64-82 note.txt/Trash/gentle-harsh clean/NO_HARSH_CLEAN; 234-243 External sentinel contract).
- Live fixture (READ-ONLY): `<RELION_PROJECT_FIXTURE>/default_pipeline.star`, and `Refine3D/job034/{job.star,note.txt,job_pipeline.star,run.err}` + directory listing.
- `skill/relion/scripts/inspect_project.py` (SENTINELS map, NOISE filter, usage header).
