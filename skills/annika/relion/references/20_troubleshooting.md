# 20 — Failure-triage methodology and common failure modes

## Scope
How to triage a failed or stalled RELION 5.0 job on the example RELION host server: read the exit sentinel, extract the *real* error from `run.err` past the X11/MPI noise, recover the exact command from `note.txt`, and map the symptom to a root cause and fix. Covers the common failure classes (missing input, MPI misuse, GPU out-of-memory, scratch/disk full, optics/pixel mismatch, bad STAR/label, version mismatch, queue/walltime kills) and the root-vs-symptom problem (one job's GPU OOM showing up as a downstream "file does not exist"). For the symptom→cause lookup table see `21_error_lookup.md`; for "what do I do next" branching see `22_decision_trees.md`. Most of this is version-stable, but RELION 4.0/5.0 changed file formats and added GPU back-ends — older projects read by a 5.0 install are normal here.

---

## The triage loop

Run these five steps in order. Steps 1–4 are pure reads; do not re-run or delete anything until you know the root cause. The fastest start is the bundled read-only diagnostic:

```
# RECOMMENDED FIRST STEP — read-only, never writes into the project
python3 scripts/inspect_project.py /path/to/PROJECT            # whole-project summary
python3 scripts/inspect_project.py /path/to/PROJECT --failed   # only FAILED/ABORTED jobs
python3 scripts/inspect_project.py /path/to/PROJECT Polish/job040   # deep-dive one job
```
`inspect_project.py` already does steps 1–3 for you: it reads each job's exit sentinel, extracts the real `ERROR:` line from `run.err` filtering the standard noise tokens, and pulls the executed command from `note.txt` (see "Noise filter" below). Use it first, then drill into anything it flags.

### Step 1 — Read the exit sentinel (FAILURE / ABORTED / none)
The sentinels are **files** written into the job directory. Exact names (from `src/pipeline_control.h:32-35`):

| File in job dir | Meaning | Written by |
|---|---|---|
| `RELION_JOB_EXIT_SUCCESS` | Job finished cleanly | `pipeline_control.cpp` on success |
| `RELION_JOB_EXIT_FAILURE` | Job hit a `REPORT_ERROR` / crashed | `pipeline_control.cpp:37` |
| `RELION_JOB_EXIT_ABORTED` | Job aborted on user request | `pipeline_control.cpp:42` |
| `RELION_JOB_ABORT_NOW` | *Request* to abort (you/GUI dropped it in to ask the job to stop) | checked at `pipeline_control.cpp:75` |

`RELION_EXIT_SUCCESS` / `RELION_EXIT_FAILURE` / `RELION_EXIT_ABORTED` (`pipeline_control.h:37-39`) are exit **macros** calling `pipeline_control_relion_exit(0|1|2)` — the function that *writes* the `RELION_JOB_EXIT_*` sentinel file **and** sets the exit code (`pipeline_control.cpp:24-56`). There is no file literally named `RELION_EXIT_SUCCESS` on disk; look for `RELION_JOB_EXIT_*`.

Interpretation:
- `RELION_JOB_EXIT_FAILURE` present → the binary itself threw. Go to step 2; `run.err` will have the cause.
- `RELION_JOB_EXIT_ABORTED` present → stopped on request; usually not a bug.
- **No sentinel at all** → the job was killed *before* it could write one: walltime/`scancel`, OOM-killer (host RAM), node death, or it never launched. This is the classic queue/walltime signature — check the scheduler log, not `run.err`.

### Step 2 — Extract the REAL error from `run.err`, filtering noise
RELION prints the real error as a line `ERROR:` followed by the message on the next non-empty line (the `RelionError` thrown by `REPORT_ERROR`, `src/error.h:65`). `run.err` is buried in noise that is **not** the cause. Skip these (this is exactly the `NOISE` set `inspect_project.py` filters):

- `No protocol specified` — X11/display, harmless (GUI couldn't open a window in batch).
- `MPI_ABORT was invoked on rank N in communicator MPI_COMM_WORLD` and the `NOTE: invoking MPI_ABORT…` block — a *consequence* of one rank dying, not the cause.
- `[host:PID] N more process has sent help message help-mpi-api.txt / mpi-abort` and `Set MCA parameter "orte_base_help_aggregate" to 0…` — Open MPI help-aggregation chatter.
- Long `------…------` dashed separators.
- `QStandardPaths`, `libGL error`, `Warning: Unable to load …` — Qt/GL noise.

The signal is the **first** `ERROR:`-then-message in the file (RELION often re-prints the same error once per rank and once at MPI teardown — read the earliest one). The `=== Backtrace ===` block under it is mangled C++ symbols; useful only to confirm *which* binary and function (e.g. `MetaDataTable::read`, `MlDeviceBundle::setupTunableSizedObjects`).

### Step 3 — Read `note.txt` for the exact command + which binary
`note.txt` contains the literal executed command(s) between `` ++++ with the following command(s): `` and the closing `` ++++ ``. This tells you:
- **Which binary** ran — `relion_refine` vs `relion_refine_mpi`, `relion_motion_refine` vs `relion_motion_refine_mpi`, `relion_flex_analyse`, etc. The `_mpi` suffix is decisive for the MPI-misuse class.
- The **exact flags** — `--gpu`, `--j`, `--pool`, `--scratch_dir`, `--params3`, input `--i`/`--continue` paths.
- That a job may run **several binaries in sequence** (e.g. a MultiBody job runs `relion_refine_mpi` then `relion_flex_analyse`). If the *first* binary crashed, the second one fails on a *missing* file — see Root vs symptom below.

`note.txt` accumulates one block per (re)run; the **last** block is the attempt that produced the current sentinel.

### Step 4 — Check inputs exist and optics/pixel sizes are sane
- Confirm every `--i`, `--continue`, `--ref`, `--mask`, `--f`, `--corr_mic`, `--multibody_masks` path in `note.txt` actually exists on disk. A missing one gives `MetaDataTable::read: File … does not exist` (`metadata_table.cpp:1353`).
- Check the optics block of the relevant particle STAR (`inspect_project.py` prints this). For the validation fixture `<RELION_PROJECT_FIXTURE>` (READ-ONLY): `opticsGroup1`, `_rlnMicrographOriginalPixelSize 0.53` (super-res K3) → `_rlnMicrographPixelSize 1.06` (2× binned), 300 kV, Cs 2.7, amplitude contrast 0.1. A box/pixel/voltage that disagrees between a reference and the data is a real failure class (see "optics/pixel mismatch").

### Step 5 — Check resources
- **GPU memory** — the two RTX 2080 Ti cards have **11 GB each** (modest). High-resolution refinement and multibody are the usual OOM victims (see GPU OOM class). Use `nvidia-smi` to see if something else is occupying a card.
- **Scratch** — `--scratch_dir /processing` (site convention) must have room for the copied particle stacks; a full `<SCRATCH_DIR>` makes the copy fail mid-run.
- **Walltime / host RAM** — no sentinel + truncated `run.out` usually means the scheduler killed it or the host OOM-killer fired.

---

## Common failure classes

The four fixtures below are the **real** failures captured in the validation project (RELION 4.0-beta, read here for triage practice; a 5.0 install reads them identically). All flag/error strings are grounded in the live 5.0 binaries and the pinned 5.0 source unless marked otherwise.

### A. Missing input file
**Recognise:** `ERROR: MetaDataTable::read: File <path> does not exist` (`metadata_table.cpp:1353`). Backtrace shows the reading binary (`relion_refine`, `relion_flex_analyse`, …).
**Causes:** the upstream job that should have produced `<path>` failed or was deleted/trashed; a hand-edited path is wrong; a continuation points at an `_optimiser.star` / `_data.star` that was never written because the run died first.
**Fix:** verify the producer job succeeded (its sentinel), re-run it, then re-launch the consumer. **Do not** create a stub file to satisfy the path — fix the producer.
> Fixture (MultiBody/job087, job089): `ERROR: MetaDataTable::read: File MultiBody/job087/run_ct2_data.star does not exist` (and `…/job089/run_data.star`). This is a *symptom*, not the root cause — see "Root vs symptom".

### B. MPI misuse — training/parameter-estimation under an `_mpi` binary
**Recognise:** `ERROR: Parameter estimation is not supported in MPI mode.` thrown by `relion_motion_refine_mpi`. In 5.0 source this guard is `motion_refiner_mpi.cpp:42` (and again at line 54): when `node->isLeader() && motionParamEstimator.anythingToDo()` it dies immediately.
**Root cause:** Polish/Bayesian-polishing **training** (parameter estimation, the `--params2` / `--params3` / `--params_file` mode of `relion_motion_refine`) is single-rank only. It was launched through the MPI binary with `Number of MPI procs > 1`, so the leader refused. The subsequent `MPI_ABORT … errorcode 1` lines are just teardown.
**Fix:** run the **training** step with the **non-MPI** binary `relion_motion_refine` (or set MPI procs = 1 so the GUI uses the serial binary). The later *polishing/recombination* step (no `--params*`) is the one that parallelises with `relion_motion_refine_mpi`. Flags `--params2`/`--params3`/`--params_file`, `--min_p`, `--eval_frac`, `--align_frac` are confirmed under "Parameter estimation" in `relion_motion_refine --help`.
> Fixture (Polish/job040, job041): `note.txt` ran ``relion_motion_refine_mpi … --params3 …`` → `ERROR: Parameter estimation is not supported in MPI mode.` `run.err` of job041 even opens with the harmless `No protocol specified` X11 line above the real error — exactly the noise to skip.

Example fix (NEW output rootname; serial binary for the training pass):
```
# EXAMPLE — training pass must be single-rank (no _mpi)
relion_motion_refine \
  --i Refine3D/job037/run_data.star --f PostProcess/job039/postprocess.star \
  --corr_mic MotionCorr/job002/corrected_micrographs.star \
  --first_frame 1 --last_frame -1 --params3 --min_p 10000 \
  --eval_frac 0.5 --align_frac 0.5 --o Polish/jobXXX/ --j 16
```

### C. GPU out-of-memory / "A GPU-function failed to execute"
**Recognise:** `ERROR: out of memory in …/custom_allocator.cuh at line 435 (error-code 2)` immediately followed by the long `A GPU-function failed to execute.` block (the `ERRGPUKERN` macro, `src/error.h:156`). On 5.0 this same block also names AMD/Intel back-ends and "NVIDIA GPUs with compute 5.0 / AMD MI gfx906". The dedicated OOM message `You ran out of memory on the GPU(s).` is `ERRGPUCAOOM` (`error.h:187`).
**Root cause on the 11 GB cards:** the per-rank GPU footprint exceeded 11 GB — too big a box, too many particles per GPU, GPU-sharing between MPI followers during a high-resolution final iteration (the `error.h:196` note), or multibody's per-body reconstructions. The fixtures here failed *mid/late run* (warnings about FSC and body resolution printed first), which the macro itself flags as the "data/parameters were unexpected … middle or end of a run" case.
**Fixes (all confirmed flags via `relion_refine --help`):**
- Reduce GPU pressure: fewer MPI ranks per card (avoid "device X is split between N followers"), smaller `--pool` (default 1), or fewer particles per GPU.
- `--free_gpu_memory <Mb>` — leave headroom (default 0); units are **Mb** per the help text.
- Re-extract to a smaller box / down-scale; the `error.h:199-203` rule of thumb is per-rank GB ≈ `1.1e-8 * (2N)^3` for an N-pixel box (≈8 GB at 450 px), so 11 GB caps you well below ~500 px at full single-precision.
- If `_rlnNrOfSignificantSamples` is huge (>10,000) the alignment is finding nothing — fix the reference/data or cap with `--maxsig <P>` (default -1).
- `--dont_combine_weights_via_disc` trades disc for MPI traffic, not GPU memory; it will not cure OOM.
- Last resort: run that step on CPU (omit `--gpu`) — slow but unbounded by VRAM.
> Fixture (MultiBody/job087, job089): the `relion_refine_mpi` multibody continuation ran `--gpu "" --pool 10` (empty `--gpu` = use all visible GPUs) and OOM'd on the 11 GB cards; `run.err` shows `out of memory … error-code 2` then `A GPU-function failed to execute.` repeated per rank.

### D. Scratch full / disk full
**Recognise:** copy/write errors mentioning `--scratch_dir`, `No space left on device`, or a job that dies right after "Copying particles to scratch…". No GPU/MPI error.
**Root cause:** `--scratch_dir /processing` filled up (stale copies from earlier runs accumulate there) or the project filesystem is full.
**Fix:** free `<SCRATCH_DIR>` (RELION normally cleans its own scratch on success, but a crashed job leaves it), or point `--scratch_dir` elsewhere, or drop it to read particles from the project. Check `df -h /processing` and the project mount.

### E. Optics / pixel-size mismatch
**Recognise:** `relion_refine` dying at startup complaining the reference pixel/box size differs from the data, or silently wrong scaling. The relevant 5.0 guard: by default the program *dies* if the reference pixel and box size differ from the first optics group — `--trust_ref_size` overrides it ("Trust the pixel and box size of the input reference", `relion_refine --help`).
**Root cause:** a reference map at a different pixel size than the particles (common after re-extracting at a new bin), an optics group with the wrong `_rlnMicrographPixelSize` / `_rlnImagePixelSize`, or mixing super-res (0.53 Å) and binned (1.06 Å) metadata.
**Fix:** rescale the reference (`relion_image_handler --rescale_angpix`/`--new_box` — confirm flags in `03_cli_inventory.md` / live `--help` before use) or fix the optics block; only use `--trust_ref_size` when you are sure the sizes are genuinely compatible.

### F. Bad STAR / label-not-found / wrong column count
**Recognise:** `ERROR: A line in the STAR file contains more columns than the number of labels.` or `… fewer columns than the number of labels. Expected = N Found = M` (`metadata_table.cpp:1107`, `:1124`); `Cannot sort this label: <label>` (`:681`); append errors `ERROR in appending metadata tables with not the same columns!` (`:856`).
**Root cause:** a hand-edited or externally generated STAR (e.g. an interop conversion) with a malformed loop, a missing/extra column, or a label the program needs that is absent.
**Fix:** validate the STAR with `scripts/star_min.py` / `relion_star_handler`, regenerate it from the source tool rather than patching by hand. For cryoSPARC→RELION conversions see `16_interop_cryosparc.md`; for coordinate STARs see `19_interop_coordinates.md`.

### G. Bad box / segfault
**Recognise:** the job dies with a raw segmentation fault / no clean `ERROR:` line, or a backtrace into FFT/box code. Sometimes only `run.out` truncates with no sentinel.
**Root cause:** a box size the FFT cannot handle, a corrupt `.mrcs` stack, or an out-of-range index. `ERRFFTMEMLIM` (`error.h:240`) is the GPU-FFT-too-large variant (autopicking with `--shrink 1` instead of the recommended `--shrink 0`).
**Fix:** re-extract with a sane (even, FFT-friendly) box; verify the stack opens (`relion_image_handler --stats`); for autopick FFT OOM set `--shrink 0`.

### H. Version mismatch (4.0/older project on a 5.0 install)
**Recognise:** older `relion_*` paths in backtraces (the fixtures show `<RELION4_INSTALL>/bin/…`), legacy `run.job` instead of `job.star`, or `_rlnPipeLineProcessType`/`…Status` (integer) instead of the 4.0+ `…TypeLabel`/`…StatusLabel` strings. `inspect_project.py` already falls back across both spellings and reports `legacy(run.job)`.
**Root cause:** the project was created by an older RELION. **This is normal and supported** — the fixture is a 4.0-beta project read by the 5.0 install. RELION 3.1 introduced optics groups; 4.0 introduced VDAM/Schemes/class-ranker and the tomo rewrite; 5.0 added Blush regularised reconstruction (`--blush`, confirmed in `relion_refine --help`), DynaMight, ModelAngelo, AMD/Intel GPU back-ends and full STA; 5.1 adds amyloid tooling.
**Fix:** usually nothing — just run the 5.0 binary. Only intervene if a label the 5.0 binary requires is genuinely absent (then it surfaces as class F). Do not "upgrade" a project by editing STARs blindly.

### I. Queue / walltime kill (no sentinel)
**Recognise:** **no** `RELION_JOB_EXIT_*` file in the job dir, `run.out`/`run.err` cut off mid-iteration, and the scheduler log shows a `CANCELLED`/`TIMEOUT`/`OOM` event. RELION never got to write a sentinel.
**Root cause:** SLURM walltime exceeded, manual `scancel`, node failure, or host-RAM OOM-killer (distinct from GPU OOM — this one leaves no RELION error).
**Fix:** raise the walltime / RAM request and resubmit as a continuation from the last `_optimiser.star`. Inspect `dmesg`/scheduler accounting to distinguish RAM-OOM from a plain timeout.

---

## Root vs symptom

The single most common triage mistake is fixing the *last* error instead of the *first*. RELION jobs often chain binaries, and a STAR that "does not exist" is usually the **footprint of an earlier crash**:

> **Fixture MultiBody/job087 / job089.** `note.txt` shows two binaries per block: `relion_refine_mpi` (the multibody refinement) **then** `relion_flex_analyse`. The refine step OOM'd on the 11 GB GPUs (`out of memory … error-code 2` → `A GPU-function failed to execute`), so it never wrote `run_ct2_data.star` / `run_data.star`. `relion_flex_analyse` then died with `MetaDataTable::read: File MultiBody/job087/run_ct2_data.star does not exist`. **Root cause = GPU OOM (class C). Symptom = missing file (class A).** Fixing the missing file is impossible; fixing the OOM (smaller box / fewer ranks per GPU / `--free_gpu_memory`) makes the file appear and the analyse step succeed.

Triage rule: when you see "file does not exist", check whether an **earlier binary in the same `note.txt` block** (or the upstream producer job) failed first, and fix *that*.

---

## Common failures / red flags (quick reference)

| Red flag in `run.err` | Likely class | First move |
|---|---|---|
| `Parameter estimation is not supported in MPI mode.` | B (MPI misuse) | Re-run training with serial `relion_motion_refine` |
| `out of memory … custom_allocator.cuh … error-code 2` | C (GPU OOM) | Smaller box / fewer ranks per GPU / `--free_gpu_memory` |
| `A GPU-function failed to execute.` *mid-run* | C (GPU OOM) | Same as above (read for the OOM line just above it) |
| `A GPU-function failed to execute.` *at start* | version/arch | Check `--gpu` index, CUDA/driver, card compute level |
| `MetaDataTable::read: File … does not exist` | A (missing input) — often a **symptom** | Find the producer that crashed first |
| `more/fewer columns than the number of labels` | F (bad STAR) | Regenerate STAR; don't hand-patch |
| `No space left on device` near scratch copy | D (disk full) | `df -h /processing`; free scratch |
| **No sentinel file at all** | I (walltime/RAM kill) | Check scheduler log; resubmit w/ more time/RAM |
| `No protocol specified`, `MPI_ABORT`, dashed lines | **noise** | Ignore — keep reading for the real `ERROR:` |

---

## Cross-links
- `21_error_lookup.md` — symptom→cause table keyed on the exact `ERROR:` strings and `error.h` macros (`ERRGPUKERN`, `ERRGPUCAOOM`, `ERRFFTMEMLIM`, `ERR_GPUID`).
- `22_decision_trees.md` — branch logic: sentinel → error class → next action / which job to re-run.
- `02_project_job_tree.md` — `default_pipeline.star`, `job.star`, `note.txt`, sentinel semantics in depth.
- `01_star_and_metadata.md` — optics groups, labels, validating STAR files.
- `03_cli_inventory.md` — full binary/flag inventory (`relion_image_handler`, `relion_star_handler`).
- `08_refine3d.md`, `10_ctfrefine_polish.md`, `11_subtract_multibody.md` — the steps behind the fixture failures (refine GPU memory, polishing train-vs-polish split, multibody).
- `16_interop_cryosparc.md`, `19_interop_coordinates.md` — STAR/label problems from conversions.

Where another **installed skill** owns execution or deeper diagnosis: `cryosparc` (its own error lookup for the cryoSPARC side of an interop chain), `cryolo` (picking), `cryo-flex-knowledge` (multibody/DynaMight/3DFlex conceptual background), `structural-strategy` (what-order/when-stuck decisions for downstream model building). RELION itself owns the binaries discussed here.

---

## Sources
- Live binaries on PATH at `<RELION_BIN>` (RELION 5.0.0-commit-3d6c20): `relion_refine --help` (`--free_gpu_memory`, `--pool`, `--maxsig`, `--j`, `--gpu`, `--scratch_dir`, `--dont_combine_weights_via_disc`, `--pad`, `--blush`, `--trust_ref_size`, `--grad`); `relion_motion_refine --help` ("Parameter estimation" section: `--params2`, `--params3`, `--params_file`, `--min_p`, `--eval_frac`, `--align_frac`, `--par_group`); `relion_flex_analyse --help` (`--data`, `--model`, `--bodies`, `--PCA_orient`, `--do_maps`, `--k`); `relion_refine --version`.
- `references/source/relion_ver5.0/src/pipeline_control.h` (sentinel macro names, lines 32-39).
- `references/source/relion_ver5.0/src/pipeline_control.cpp` (sentinel file writes/checks, lines 37/42/75/94-101).
- `references/source/relion_ver5.0/src/error.h` (`REPORT_ERROR` line 65; `ERRGPUKERN` 156; `ERRGPUCAOOM` 187; `ERRFFTMEMLIM` 240; `ERR_GPUID` 149).
- `references/source/relion_ver5.0/src/metadata_table.cpp` (`File … does not exist` line 1353; column-count errors 1107/1124; sort/append errors 681/856).
- `references/source/relion_ver5.0/src/jaz/single_particle/motion/motion_refiner_mpi.cpp` (MPI param-estimation guard, lines 40-44 and 52-54).
- Real fixture `run.err` + `note.txt` (READ-ONLY) under `<RELION_PROJECT_FIXTURE>`: `Polish/job040`, `Polish/job041`, `MultiBody/job087`, `MultiBody/job089`.
- `skill/relion/scripts/inspect_project.py` (noise-filter `NOISE` set; `SENTINELS` map; real-error extraction).
