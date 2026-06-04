# 15 — Schemes, on-the-fly, relion_it.py

## Scope
How RELION 4+/5.0 automates pipelines via *Schemes* (directed graphs of jobs + operators stored under `Schemes/<name>/scheme.star`), how `$$variable` substitution turns a static `job.star` into a parameterised template, how to drive a scheme from the command line with `relion_schemer`, the standard on-the-fly preprocessing loop (`prep` + `proc` schemes), and how the rewritten `relion_it.py` GUI sits on top of all of this. Covers when to automate vs drive jobs by hand. Cross-links `02_project_job_tree.md` and `03_cli_inventory.md`.

---

## 1. Vocabulary and history

| Term | Meaning |
|---|---|
| *Scheme* | A directed graph of RELION jobs and *Operators*, stored in `Schemes/<name>/`. Renamed from *Schedule* (3.1) to *Scheme* in 4.0 to avoid clashing with GUI "scheduled jobs". |
| *Node* | Either a Job or an Operator. |
| *Edge* | A directed connection between two Nodes (defines execution order). |
| *Fork* | A special Edge with a boolean: routes to `outputNode` (bool False) or `outputNodeIfTrue` (bool True). The decision instrument. |
| *Variable* | Scheme-local value: float, boolean, or string. Has a current value and a reset value. |
| *Operator* | A Node that computes / acts on Variables or the filesystem (no RELION job). |

Version notes: Schemes are 4.0+; in 3.1 the same machinery existed as *Schedules*. The on-the-fly story (this file) is the 4.0+ rewrite. 5.0 adds Blush/DynaMight/ModelAngelo/tomo jobs that can also be placed in a scheme, but the scheme machinery itself is unchanged. (Grounded: `Reference/Schemes.rst:6`, `:1-12`.)

---

## 2. On-disk layout

```
ProjectDir/
  Schemes/
    prep/
      scheme.star            # variables, operators, jobs, edges
      importmovies/job.star  # one subdir per Job (subdir name = JobNameOriginal)
      motioncorr/job.star
      ctffind/job.star
    proc/
      scheme.star
      select_mics/job.star
      autopick/job.star
      ...
```

Each scheme directory holds exactly one `scheme.star` plus one subdirectory per job whose name is the job's `JobNameOriginal`, each containing a standard `job.star`. (Grounded: live install ships `<RELION_SOURCE_ROOT>/scripts/Schemes/prep` and `/proc` with this exact layout; `Reference/Schemes.rst:11-12,186,193`.)

### `scheme.star` data blocks

The shipped `Schemes/prep/scheme.star` and `Schemes/proc/scheme.star` use these blocks (all `# version 30001`). Label names are confirmed in `schemer.cpp` as `EMDL_SCHEME_*`:

| Block | Loop columns (label stems) | Holds |
|---|---|---|
| `data_scheme_general` | `_rlnSchemeName`, `_rlnSchemeCurrentNodeName` | scheme name + current node pointer |
| `data_scheme_floats` | `_rlnSchemeFloatVariableName / ...Value / ...ResetValue` | float variables |
| `data_scheme_bools` | `_rlnSchemeBooleanVariableName / ...Value / ...ResetValue` | boolean variables |
| `data_scheme_strings` | `_rlnSchemeStringVariableName / ...Value / ...ResetValue` | string variables |
| `data_scheme_operators` | `_rlnSchemeOperatorName / ...Type / ...Output / ...Input1 / ...Input2` | operators |
| `data_scheme_jobs` | `_rlnSchemeJobNameOriginal / ...JobName / ...JobMode / ...JobHasStarted` | jobs |
| `data_scheme_edges` | `_rlnSchemeEdgeInputNodeName / ...OutputNodeName / ...IsFork / ...OutputNodeNameIfTrue / ...BooleanVariable` | edges + forks |

(Grounded: read directly from `<RELION_SOURCE_ROOT>/scripts/Schemes/prep/scheme.star`, `/proc/scheme.star`; labels `EMDL_SCHEME_GENERAL_NAME`, `EMDL_SCHEME_JOB_MODE`, `EMDL_SCHEME_EDGE_IS_FORK`, etc. in `schemer.cpp`.)

Real `prep/scheme.star` jobs block (verbatim):
```
data_scheme_jobs
loop_
_rlnSchemeJobNameOriginal #1
_rlnSchemeJobName #2
_rlnSchemeJobMode #3
_rlnSchemeJobHasStarted #4
importmovies importmovies   continue            0
motioncorr motioncorr   continue            0
   ctffind    ctffind   continue            0
```
`JobNameOriginal` (col 1) is the static template name = the subdirectory name; `JobName` (col 2) starts equal to it and gets rewritten to the real pipeline name (e.g. `CtfFind/job003/`) once the job actually runs. (Grounded: `prep/scheme.star`; `Reference/Schemes.rst:34-35,191`.)

---

## 3. Variables and `$$` substitution

Three variable types (Grounded: `Reference/Schemes.rst:18`, `schemer.h:30-70`):
- **float** — numbers (`SchemerFloatVariable`).
- **boolean** — True/False (`SchemerBooleanVariable`).
- **string** — text (`SchemerStringVariable`).

Each variable carries a current value and a **reset value** (the value it is re-initialised to on `--reset`). One special string variable named `email`: if set, the scheme emails it on completion or error via the Linux `mail` command. (Grounded: `Reference/Schemes.rst:19,21-22`.)

### `$$variable` inside a job.star
Any joboption value in a `job.star` can reference a scheme variable with a `$$` prefix; at execution time the schemer substitutes the variable's current value. This is what makes one `job.star` a reusable template. Real examples from the shipped `proc` scheme:

| File / joboption | Value | Replaced with |
|---|---|---|
| `proc/select_mics/job.star` `fn_mic` | `$$ctffind_mics` | current value of string var `ctffind_mics` |
| `proc/autopick/job.star` `do_log` | `$$do_log` | bool var `do_log` |
| `proc/autopick/job.star` `do_topaz` | `$$do_topaz` | bool var `do_topaz` |
| `proc/autopick/job.star` `topaz_model` | `$$topaz_model` | string var `topaz_model` |
| `proc/refine3d/job.star` `fn_ref` | `$$myref` | string var `myref` |
| `prep/motioncorr/job.star` `other_args` | `--do_at_most $$do_at_most` | float var `do_at_most` (note: `$$` works mid-string) |

(Grounded: `grep '\$\$'` over the shipped job.star files.)

### Jobname rewriting in string variables
Separately from `$$`, any string value that *contains a JobNameOriginal* of a job in any scheme in the project is rewritten to that job's current `JobName` when an operator runs. Example: a string `Schemes/prep/ctffind/micrographs_ctf.star` becomes `CtfFind/job003/micrographs_ctf.star` once the `ctffind` job has run. This is how downstream jobs find upstream outputs without hardcoding `jobNNN`. (Grounded: `Reference/Schemes.rst:190-191,195`; the `proc` strings block literally seeds `ctffind_mics` to `Schemes/prep/ctffind/micrographs_ctf.star`.)

---

## 4. Operators (the compute Nodes)

An operator has a `type`, `output` (a variable it writes), and up to two inputs `input1`/`input2`. Types are `defined` in `schemer.h:77-119` and documented in `Reference/Schemes.rst:59-166`. Most write `output`; the file/flow ones do not. Key ones (full list in source):

**Float** (`output` is a float): `float=set`, `float=plus`, `float=minus`, `float=mult`, `float=divide`, `float=round`, `float=count_images` (count `particles`/`micrographs`/`movies` in a STAR file given by input1, type by input2), `float=count_words`, `float=read_star` (read a number from `starfile,table,label`), `float=star_table_max` / `_min` / `_avg`, `float=star_table_sort_idx`.

**Boolean** (`output` is a bool): `bool=set`, `bool=and`, `bool=or`, `bool=not`, `bool=gt`, `bool=lt`, `bool=ge`, `bool=le`, `bool=eq`, `bool=file_exists` (input1 = filename), `bool=read_star`.

**String** (`output` is a string): `string=set`, `string=join`, `string=before_first` / `after_first` / `before_last` / `after_last`, `string=read_star`, `string=glob` (Linux wildcard → comma-separated list of matches), `string=nth_word`.

**No-output / side-effect**: `touch_file`, `copy_file`, `move_file`, `delete_file`, `email`, `wait` (waits `input1` seconds since last execution; first pass just starts the timer), `exit_maxtime` (terminates scheme after `input1` hours since start), `exit` (terminate now).

(Grounded: `schemer.h:77-119` macro names; `Reference/Schemes.rst:59-166` semantics.)

Real `proc/scheme.star` operators (verbatim subset):
```
HAS_ctffind        bool=file_exists  has_ctffind        ctffind_mics      undefined
COUNT_mics         float=count_images current_nr_mics    selected_mics     micrographs
COUNT_parts        float=count_images current_nr_parts   selected_parts    particles
CHECK_do_3d        bool=ge           do_3d              current_nr_parts  min_nr_parts_3d
HAS_mics_increased bool=gt           has_larger_nr_mics current_nr_mics   prev_nr_mics
EXIT_maxtime       exit_maxtime      undefined          maxtime_hr        undefined
WAIT               wait              undefined          wait_sec          undefined
```
(Grounded: `proc/scheme.star:64-82`.)

---

## 5. Edges and Forks (the control flow)

A normal edge connects `inputNode → outputNode`. A fork additionally has `OutputNodeNameIfTrue` and an associated boolean: bool False → `outputNode`, bool True → `outputNodeIfTrue` (`_rlnSchemeEdgeIsFork = 1`). (Grounded: `Reference/Schemes.rst:171-179`; `schemer.h:178-205` `SchemerEdge`.)

The scheme is initialised/reset to the **left-hand node of the first edge**. End infinite loops with the `wait` operator at the tail; end finite schemes with an `exit` operator. (Grounded: `Reference/Schemes.rst:204-205`.)

Real `proc/scheme.star` edges showing the fork pattern (verbatim subset):
```
_rlnSchemeEdgeInputNodeName  _rlnSchemeEdgeOutputNodeName  _rlnSchemeEdgeIsFork  _rlnSchemeEdgeOutputNodeNameIfTrue  _rlnSchemeEdgeBooleanVariable
HAS_ctffind         WAIT          1   select_mics      has_ctffind
HAS_mics_increased  WAIT          1   SET_prev_nr_mics has_larger_nr_mics
CHECK_do_3d         WAIT          1   CHECK_iniref     do_3d
CHECK_iniref        inimodel3d    1   SET_myref_user   has_iniref
refine3d            WAIT          0   undefined        undefined
```
Read: "if `has_ctffind` is True go to `select_mics`, else go back to `WAIT`"; "if enough particles (`do_3d`) and a reference exists (`has_iniref`) skip initial model and use the user ref, else build one." (Grounded: `proc/scheme.star:104-130`.)

---

## 6. The standard on-the-fly pattern: `prep` then `proc`

On-the-fly = two cooperating schemes that loop over movies as they land on disk. (Grounded: `Onthefly.rst:6,28,38-39`.)

### `prep` scheme — import → motioncorr → ctf
Linear loop, all three jobs in `continue` mode (so each pass re-uses the same job dir and only processes new movies). Default cap `do_at_most = 50` movies/cycle. Control flow:
```
WAIT → EXIT_maxtime → importmovies → motioncorr → ctffind → WAIT (loop)
```
The `--do_at_most $$do_at_most` flag is injected into motioncorr's `other_args`. (Grounded: `prep/scheme.star:46-65` (jobs + edges); `prep/motioncorr/job.star:41`; `Onthefly.rst:28-29`.)

### `proc` scheme — select → pick → extract → 2D → select → (3D)
Loops while the particle count keeps rising; forks decide LoG-vs-Topaz picking, whether to retrain Topaz, whether to do 3D, and whether to build an initial model. Skeleton (Grounded: `proc/scheme.star:104-130`):
```
WAIT → EXIT_maxtime → HAS_ctffind ──(True)── select_mics → COUNT_mics → HAS_mics_increased
   │(False, loop)                                                            │(True)
   └────────────────────────── back to WAIT ←─────────────────────────────  SET_prev_nr_mics → SET_do_topaz
                                                                                    │
   autopick → extract → class2d → select_parts → COUNT_parts → CHECK_do_3d
                                                                    │(do_3d True)
                                                       CHECK_iniref ─(has_iniref)→ inimodel3d → refine3d → WAIT
```
`continue`-mode jobs: `select_mics, autopick, extract`. `new`-mode jobs: `class2d, select_parts, inimodel3d, refine3d` (a fresh job dir each cycle). This matches the doc guidance that import/motioncorr/ctf/pick/extract are `continue` and "most other jobs" are `new`. (Grounded: `proc/scheme.star:86-99`; `Reference/Schemes.rst:200`.)

### Job mode semantics
| Mode | Behaviour each time the schemer reaches the node |
|---|---|
| `new` | always create a brand-new job dir (`JobName`), regardless of `jobHasStarted`. |
| `continue` | if `jobHasStarted` is False → new job dir; if True → run as a *continue* job inside the existing `JobName`. |

Executing any job sets `jobHasStarted = True`; `--reset` sets it back to False for all jobs. (Grounded: `Reference/Schemes.rst:40-48`; `schemer.h:146-147` `SCHEME_NODE_JOB_MODE_NEW/CONTINUE`.)

---

## 7. Running a scheme from the command line: `relion_schemer`

Binary: `<RELION_BIN>/relion_schemer` (5.0.0-commit-3d6c20). All flags below are from the live `--help`.

| Action | Command |
|---|---|
| **Run** a scheme | `relion_schemer --scheme Schemes/proc --run --verb 1` |
| Run in a named pipeline | `relion_schemer --scheme Schemes/proc --run --run_pipeline default` |
| **Abort** a running scheme | `relion_schemer --scheme Schemes/proc --abort` |
| **Reset** all variables to reset-values (and `jobHasStarted=False`) | `relion_schemer --scheme Schemes/proc --reset` |
| Set a variable | `relion_schemer --scheme Schemes/proc --set_var do_3d --value True` |
| Set a job's mode | `relion_schemer --scheme Schemes/proc --set_job_mode class2d --value new` |
| Set a job's has-started flag | `relion_schemer --scheme Schemes/proc --set_has_started autopick --value False` |
| Move the current-node pointer | `relion_schemer --scheme Schemes/proc --set_current_node WAIT` |
| Copy a scheme to a new dir | `relion_schemer --scheme Schemes/proc --copy Schemes/proc2` |

Building a scheme programmatically (add elements) uses `--add variable|operator|job|edge|fork` with `--type`, `--name`, `--value`, `--i`, `--i2`, `--o`, `--o2`, `--bool`, `--mode {new|continue}`. The `--bool` arg names the boolean for a fork. (Grounded: `relion_schemer --help` — captured at `cli/.../help/relion_schemer.txt:12-37`; flag set re-confirmed against the live binary's identical `-h` output.)

Notes:
- `--scheme` takes the **directory name** (e.g. `Schemes/proc`), per the help text "Directory name of the scheme".
- Default `--run_pipeline` is `default` (i.e. `default_pipeline.star`). The scheme adds its executed jobs and their edges into that pipeline. (Grounded: help line `--run_pipeline (default)`; `Reference/Schemes.rst:196`.)
- `--verb` accepts 0/1/2/3.

### Locking
While a scheme runs it holds a lock directory `.relion_lock_scheme_<name>` containing a `lock_scheme` file (the GUI looks for this to know if the scheme is running). If a scheme dies on an error (not a clean abort/exit), this lock dir must be removed before re-running. (Grounded: `schemer.cpp:675-687`; `Onthefly.rst:190,198`.)

---

## 8. The GUIs: `relion_schemegui.py` and `relion_it.py`

Both are installed on PATH (`<RELION_BIN>/relion_schemegui.py`, `relion_it.py`; sources are `scripts/schemegui.py`, `scripts/it.py` in the install).

- **`relion_schemegui.py <name>`** — a small Tkinter GUI for one running scheme; Start/Abort/Restart/Reset/Unlock buttons; shows the `Current` node; lets you change job options or scheme variables while aborted. It just emits `relion_schemer` calls under the hood — inspect it to see them. After you change any option for a job, that job (and only downstream consequences) reverts to `has not started`. (Grounded: `Reference/Schemes.rst:229-237`; `Onthefly.rst:184-198`.)
- **`relion_it.py [opts.py ...] &`** — the rewritten on-the-fly driver GUI. It depends on the pre-configured `Schemes/prep` and `Schemes/proc` shipped in the install's `scripts/` dir; point `RELION_SCRIPT_DIRECTORY` at that dir (or your own modified copy) so it can find them. Save options to `relion_it_options.py`; **Save & run** launches both schemes and the normal RELION GUI. (Grounded: `Onthefly.rst:8-18,173-178`.)

`RELION_SCRIPT_DIRECTORY` is **empty** in this environment (`echo $RELION_SCRIPT_DIRECTORY` returned nothing). To use `relion_it.py` here you would set it to `<RELION_SOURCE_ROOT>/scripts` (which contains `Schemes/prep` and `Schemes/proc`). (Grounded: live `echo`; live `ls` of that scripts/Schemes dir.)

### Deep option override syntax (relion_it.py)
In `relion_it_options.py` you address any job option or scheme variable with double underscores:
- `'SCHEMENAME__JOBNAME__JOBOPTION', 'value'` — e.g. `'proc__class2d_ini__nr_classes', '200'`.
- `'SCHEMENAME__VARIABLENAME', 'value'` — e.g. `'prep__do_at_most', '100'`.

Multiple options files are read left-to-right; last value wins. Use this to pin site executables (CTFFIND/Topaz paths) and thread/MPI counts. (Grounded: `Onthefly.rst:204-258`.)

---

## 9. Creating / modifying a scheme by hand (recommended path)

The docs explicitly recommend hand-editing over `--add`: copy the shipped `prep`/`proc` as a starting point, draw a flowchart, then edit `Schemes/<name>/scheme.star` and each `Schemes/<name>/<job>/job.star` in a text editor. Use the normal GUI to fill a job, then *Jobs → Save job.star* into the scheme's job subdir, and replace concrete values with `$$variable` where you want scheme control. (Grounded: `Reference/Schemes.rst:185-202`.)

Package a finished scheme for reuse across projects:
```
tar -zcvf preprocess_scheme.tar.gz Schemes/preprocess     # author project
tar -zxvf preprocess_scheme.tar.gz                          # new project
```
(Grounded: `Reference/Schemes.rst:208-219`.)

A minimal hand-built linear scheme (illustrative, real flags/labels):
```bash
# Build a 2-job scheme: import -> motioncorr, then exit
relion_schemer --scheme Schemes/mini --add variable --type float --name do_at_most --value 50 --original_value 50
relion_schemer --scheme Schemes/mini --add job  --name importmovies --mode continue   # after placing importmovies/job.star
relion_schemer --scheme Schemes/mini --add job  --name motioncorr   --mode continue
relion_schemer --scheme Schemes/mini --add edge --i importmovies --o motioncorr
# run it
relion_schemer --scheme Schemes/mini --run --verb 1
```
(`--add`/`--type`/`--name`/`--mode`/`--i`/`--o` are all in the live help. The exact required ordering of element creation is best learned by mirroring the shipped `scheme.star` files; if unsure, hand-edit the STAR instead.)

---

## 10. Legacy `relion_it.py` — what it was, what it is now

`relion_it.py` first shipped with RELION 3.0/3.1 as a standalone Python preprocessing pipeline. In 4.0 it was **rewritten to drive the Schemes machinery** (the Tkinter GUI by Colin Palmer, CCPEM) — same name, different engine. There is no separate "old" relion_it engine in the 5.0 install; `scripts/it.py` is the schemes-based version. Treat any 3.x `relion_it.py` documentation that talks about its own internal job loop as superseded. (Grounded: `Onthefly.rst:6-8`; `Reference/Schemes.rst:6`; `scripts/it.py` present in install.)

---

## 11. When to automate vs drive jobs by hand

| Situation | Recommendation |
|---|---|
| Live data collection / on-the-fly QC during a session | Automate with `prep`+`proc` (via `relion_it.py` or `relion_schemer --run`). The loop + forks are exactly what you want. |
| Standardised, repeated pipeline across many datasets | Build/tar a custom scheme once, reuse. |
| Novel sample, unknown ideal box/mask/threshold, tricky classification | Drive jobs by hand from the GUI/CLI (`02_project_job_tree.md`, `03_cli_inventory.md`). Schemes shine when the decisions are already known. |
| A single re-run or continuation | Hand-run; a scheme is overkill. |
| GPU-memory-constrained box (here: 2× RTX 2080 Ti, 11 GB each) | Hand-tune `--pool`, downsampled box (`proc` downsamples to 64 px by default), and MPI/thread split before automating; a runaway scheme can OOM repeatedly. |

The shipped `proc` is tuned for throughput (downsample to 64 px, LoG/Topaz picking, automated 2D class selection via the class-ranker `do_class_ranker`/`rank_threshold` in `select_mics`/`select_parts` job.star). It is a *starting template*, not a one-size-fits-all. (Grounded: `Onthefly.rst:115-117`; `proc/select_mics/job.star` shows `do_class_ranker`, `rank_threshold 0.35`.)

---

## Common failures / red flags

- **Stale lock dir.** A scheme that crashed leaves `.relion_lock_scheme_<name>/` behind; the next `--run` refuses to start. Remove the lock dir (the `Unlock` button prints instructions). (Grounded: `schemer.cpp:675-687`; `Onthefly.rst:198`.)
- **`$$variable` not substituted.** The name after `$$` must exactly match a variable declared in `scheme.star` (case-sensitive). A typo passes the literal `$$foo` string into the job command. (Grounded: `Reference/Schemes.rst:30-32,197`.)
- **`continue` job not re-running after you changed options.** For a `continue` job, a new job only launches if that job's options changed *or* an upstream job's options changed; otherwise it just continues. If you expected a fresh run, set its mode to `new` or `--set_has_started <job> --value False`. (Grounded: `Onthefly.rst:194`.)
- **`relion_it.py` can't find prep/proc.** `RELION_SCRIPT_DIRECTORY` unset (it is unset in this env). Set it to `<RELION_SOURCE_ROOT>/scripts`. (Grounded: live `echo`; `Onthefly.rst:18`.)
- **Single-rank-only jobs inside an automated loop.** Jobs that must run single-rank (e.g. Polish *training/parameter estimation*: `relion_motion_refine_mpi` errors "Parameter estimation is not supported in MPI mode", seen on fixture Polish/job040,041) will fail if a scheme template hands them an MPI command. Keep such steps out of MPI-parallel scheme nodes. (Grounded: fixture failure record; see `10_ctfrefine_polish.md`.)
- **`count_images` reads the wrong table.** `float=count_images` needs `input2 = particles|micrographs|movies`; the wrong keyword silently miscounts and breaks the increase/`min_nr_parts_3d` forks. (Grounded: `Reference/Schemes.rst:73-74`; `proc/scheme.star:71-72`.)
- **Old-project `# version 30001` blocks.** Scheme/job STAR files carry `# version 30001` even under 5.0; this is normal and not a corruption sign (the 4.0-beta fixture project reads fine under the 5.0 install). (Grounded: shipped `scheme.star` headers.)

---

## Cross-links
- `02_project_job_tree.md` — `default_pipeline.star`, job dirs, `job.star`/`note.txt`, exit sentinels; a scheme writes its executed jobs and edges into this pipeline.
- `03_cli_inventory.md` — `relion_schemer` alongside the other CLI binaries; how to find flags.
- `04_preprocessing.md` / `05_picking_extraction.md` / `06_class2d_select.md` / `07_initialmodel_class3d.md` / `08_refine3d.md` — the per-job detail behind each `prep`/`proc` node.
- `10_ctfrefine_polish.md` — why Polish param-estimation must stay single-rank (relevant if scripting it).
- `20_troubleshooting.md` / `21_error_lookup.md` — lock-dir and substitution errors.

For execution of downstream model-building steps that a scheme might feed into, the dedicated skills own those: **chimerax**, **coot**, **phenix**, **mask**; for cross-package SPA automation see the **cryosparc** skill and `16_interop_cryosparc.md`.

---

## Sources
Files read:
- `cli/relion5_cli_capture_20260604/help/relion_schemer.txt` (and re-confirmed against live `relion_schemer --help` / `-h`)
- `source/relion-documents_release-5.0/source/Reference/Schemes.rst`
- `source/relion-documents_release-5.0/source/Onthefly.rst`
- `source/relion_ver5.0/src/schemer.h`
- `source/relion_ver5.0/src/schemer.cpp` (grep for `data_scheme_*`, `EMDL_SCHEME_*`, lock-dir convention)
- Live install: `<RELION_SOURCE_ROOT>/scripts/Schemes/prep/scheme.star`, `/proc/scheme.star`, `prep/importmovies/job.star`, `proc/select_mics/job.star`; `grep '\$\$'` over all shipped `Schemes/*/*/job.star`
- Live: `ls` of `<RELION_BIN>` (binaries `relion_schemer`, `relion_it.py`, `relion_schemegui.py`); `echo $RELION_SCRIPT_DIRECTORY` (empty)

Commands run: `relion_schemer --help`, `relion_schemer -h` (live binary, 5.0.0-commit-3d6c20).
