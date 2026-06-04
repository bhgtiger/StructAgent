# 21 — Exact error-string → cause/fix lookup

## Scope
A grep-target lookup table mapping the exact (or distinctively fragmentary) RELION error string to the program that throws it, the likely root cause, a concrete fix, and the sibling reference that explains it. Every row is grounded in the pinned RELION-5.0 source (`src/error.h`, `src/metadata_table.cpp`, `src/jaz/single_particle/...`, `src/symmetries.cpp`, `src/image.h`), the live installed binaries (`relion_refine --help`, `relion_motion_refine --help`), and/or the read-only NeCen/PRC1 4.0-beta fixture (`<RELION_PROJECT_FIXTURE>`). Strings not found in source are explicitly tagged `(unverified)`. Use this file when you have a literal error line and want the shortest path to a cause; use `20_troubleshooting.md` for the general "the job failed, where do I start" workflow and `22_decision_trees.md` for branchier diagnosis.

---

## 0. How RELION reports errors (so you know what to grep)

RELION raises a `RelionError` via the `REPORT_ERROR(msg)` / `REPORT_ERROR_STR(<<...)` macros (`src/error.h:65,77`). The printed block in `run.err` looks like:

```
in: <RELION_SOURCE_ROOT>/src/<file>.cpp, line <N>
ERROR:
<the message>
=== Backtrace  ===
...mangled symbol names...
==================
ERROR:
<the message>
```

So the **message line** is what you match in this table, and the `in: ...src/<file>.cpp, line <N>` line tells you the throw site (file + line), which is the most reliable disambiguator when the message text is generic. MPI jobs additionally print an `MPI_ABORT was invoked on rank N ... with errorcode 1` block — that is OpenMPI tearing down the other ranks, **not** a second independent error; ignore it and look for the real `ERROR:` above it. The job is marked failed by writing a `RELION_JOB_EXIT_FAILURE` file in the job dir (`src/pipeline_control.h:32-35`); a clean job writes `RELION_JOB_EXIT_SUCCESS`. See `02_project_job_tree.md` for the sentinel-file semantics.

> Many of the GPU strings below are long multi-line help blocks (defined as macros in `src/error.h`). Grep only the first distinctive line (e.g. `A GPU-function failed to execute`), not the whole paragraph.

---

## 1. The four verified fixture errors (gold-standard rows)

These four are reproduced **verbatim** from the read-only fixture's `run.err`/`run.out` files and matched to their throw sites in `src/`.

| Error string (match this fragment) | Program (binary) | Throw site | Likely cause | Concrete fix | See-also |
|---|---|---|---|---|---|
| `Parameter estimation is not supported in MPI mode.` | `relion_motion_refine_mpi` (Bayesian polishing **training**) | `src/jaz/single_particle/motion/motion_refiner_mpi.cpp:42` and `:54` | The polishing **train / parameter-estimation** pass (`--params2` or `--params3`) was launched through the MPI binary `relion_motion_refine_mpi` with ≥2 ranks. Param estimation is single-rank-only by design; only the **apply** pass parallelises over MPI. In the fixture this is `Polish/job040` and `job041`. | Run the training step with **one rank, no `mpirun`**: use `relion_motion_refine` (non-MPI binary) directly, or in the GUI set MPI procs = 1 for the "Train optimal parameters" job. The flags that trigger estimation are `--params2`/`--params3` (live `relion_motion_refine --help`); keep those only on the single-rank job. The subsequent **apply** job (with `--params_file`) is the one you may run under MPI. | `10_ctfrefine_polish.md` |
| `MetaDataTable::read: File <X> does not exist` | any program that reads a STAR (here `relion_flex_analyse`) | `src/metadata_table.cpp:1353` (`REPORT_ERROR("MetaDataTable::read: File " + fn_read + " does not exist")`) | The file `<X>` was never produced — almost always because the **upstream step in the same job (or an upstream job) failed** and the expected `run_*.star` was never written, or the rootname/path is wrong. In the fixture, `relion_refine`/multibody crashed on GPU first, so `relion_flex_analyse` then hit `File MultiBody/job087/run_ct2_data.star does not exist` (job087) and `File MultiBody/job089/run_data.star does not exist` (job089). | Do **not** debug the missing-file message; it is a symptom. Read the **earlier** `ERROR:` in the same `run.err` (here the GPU failure, next row), fix that, and the file will be produced. Independently: confirm the rootname (`--o` prefix) and that the producing job wrote `RELION_JOB_EXIT_SUCCESS`. | `20_troubleshooting.md` |
| `A GPU-function failed to execute.` | `relion_refine` / `relion_refine_mpi` (incl. `--multibody_masks`) | `src/error.h:156` macro `ERRGPUKERN`, raised from the CUDA-acceleration path | A CUDA kernel returned an error. On these 11 GB RTX 2080 Ti cards the overwhelmingly common cause is **GPU out-of-memory** during a high-resolution / large-box iteration, or GPU-sharing between MPI followers ("device X is split between N followers"). Less common: an architecture/build mismatch (only relevant if you rebuilt RELION). In the fixture this is the **root cause** of the `MultiBody/job087,089` failures (the missing-file error above is downstream). | Reduce GPU memory pressure: fewer particles/box per GPU, lower `--pool`, add `--free_gpu_memory <Mb>` to leave headroom, give each rank its own GPU instead of sharing (one MPI follower per physical GPU), and check `nvidia-smi` for other processes. If the box is simply too big for 11 GB, downscale/re-extract smaller or run fewer bodies. The companion OOM macro `ERRGPUCAOOM` (`src/error.h:187`, "You ran out of memory on the GPU(s)") gives the box-size rule of thumb `~1.1e-8*(2N)^3 GB` per rank. | `08_refine3d.md`, `11_subtract_multibody.md` |
| `ObservationModel::getBoxSize: box sizes not available. Make sure particle images are available before converting/importing STAR files from earlier versions of RELION.` | any program loading particles via `ObservationModel` (refine/ctf_refine/polish/flex_analyse on a converted STAR) | `src/jaz/single_particle/obs_model.cpp:742` (and `:752` for `getBoxSizes`) | The `data_optics` table has **no `_rlnImageSize`** column, so the per-optics-group box size is unknown. This is typical of STAR files **converted/imported from cryoSPARC or an older RELION** where the optics block was reconstructed without the image size. `hasBoxSizes` is set only if `EMDL_IMAGE_SIZE` is present (`obs_model.cpp:94`). | Re-add the optics info so `_rlnImageSize` is present. With pyem: `csparc2star.py --boxsize <N> in.cs out.star` (live `csparc2star.py --help` shows `--boxsize BOXSIZE`). Or run an `--o` of a fresh extraction so particle images exist and the optics block is rebuilt, or hand-edit `data_optics` to add `_rlnImageSize <box>`. The error itself tells you images must be available before converting. | `16_interop_cryosparc.md`, `01_star_and_metadata.md` |

> Fixture provenance: the `Parameter estimation...` and `...does not exist` strings were read directly from `Polish/job040/run.err`, `MultiBody/job087/run.err`, `MultiBody/job089/run.err`. The fixture ran a 4.0-beta build (`run.out`: "RELION version: 4.0-beta-2-commit-e3afcf"); the throw-site line numbers above are from the pinned **5.0** source, so the absolute line number in your `run.err` may differ by version even though the message text matches.

---

## 2. Other grounded errors (from `src/`)

All rows below are quoted from the pinned 5.0 source; the throw-site column is the disambiguator.

### 2.1 STAR / metadata I/O (`src/metadata_table.cpp`)

| Error string (fragment) | Program | Throw site | Cause | Fix | See-also |
|---|---|---|---|---|---|
| `A line in the STAR file contains more columns than the number of labels.` | any STAR reader | `metadata_table.cpp:1107` | A data row has more whitespace-separated fields than there are `_rln...` labels in the `loop_` header — usually a hand-edit, a stray value, or a label line that got deleted. | Re-export the STAR cleanly, or fix the offending row/header so column count matches the label count. | `01_star_and_metadata.md` |
| `A line in the STAR file contains fewer columns than the number of labels. Expected = <a> Found = <b>` | any STAR reader | `metadata_table.cpp:1124` | A data row has fewer fields than labels (truncated line, missing value, a path with an unescaped space). | Inspect the row; pad/repair the missing field or remove the broken line. The "Expected/Found" counts point at the malformed row. | `01_star_and_metadata.md` |
| `RELION does not support CR+LF as a new line code. Didn't you edit a STAR file in Windows? ... run dos2unix` | any STAR reader | `metadata_table.cpp:1224` | The STAR has Windows CRLF line endings (often from editing on Windows / copying through a Windows share). | `dos2unix file.star` (the message says so explicitly). | `01_star_and_metadata.md` |
| `MetaDataTable::write: cannot write to file: <X>` | any writer | `metadata_table.cpp:1527` | Output path is not writable: missing parent dir, no permission, or read-only filesystem (e.g. trying to write into the read-only fixture `<PROJECT_ROOT>/...`). | Point `--o` at a writable dir; create the parent; never write into a read-only project. | `02_project_job_tree.md` |
| `STAR file does not contain <label>` / `You need rlnOriginXAngst and rlnOriginYAngst ...` | `relion_star_handler` (duplicate removal) etc. | `metadata_table.cpp:2104,2107,2113` | A requested label (offsets, coordinates, micrograph name) is absent for the operation you asked. | Use a STAR that has the required columns, or pick an operation appropriate to the columns present. | `01_star_and_metadata.md` |

### 2.2 Optics / box-size / observation model (`src/jaz/single_particle/obs_model.cpp`)

| Error string (fragment) | Program | Throw site | Cause | Fix | See-also |
|---|---|---|---|---|---|
| `ObservationModel::getBoxSizes: box sizes not available. Make sure particle images are available before converting/importing STAR files from earlier versions of RELION.` | refine/ctf_refine/polish/flex_analyse | `obs_model.cpp:752` | Same `_rlnImageSize`-missing cause as the §1 `getBoxSize` row, hit via the plural getter. | Add `_rlnImageSize` to `data_optics` (`csparc2star.py --boxsize`, or re-extract). | `16_interop_cryosparc.md` |
| `ObservationModel::predictObservation: Unable to make a prediction without knowing the box size.` | ctf_refine / polish (prediction) | `obs_model.cpp:234,354` | Same missing-box-size condition reached during reference prediction. | Same fix: restore `_rlnImageSize`. | `16_interop_cryosparc.md` |

### 2.3 Motion / polishing (`src/jaz/single_particle/motion/`)

| Error string (fragment) | Program | Throw site | Cause | Fix | See-also |
|---|---|---|---|---|---|
| `Parameter estimation is not supported in MPI mode.` | `relion_motion_refine_mpi` | `motion_refiner_mpi.cpp:42,54` | (Gold row — see §1.) Train pass launched under MPI. | Single-rank train, MPI only for apply. | `10_ctfrefine_polish.md` |
| `ERROR: this program needs to be run with at least two MPI processes!` | `relion_motion_refine_mpi` (and other `*_mpi`) | `motion_refiner_mpi.cpp:37` | The MPI binary was started with a single rank (`nr_mpi=1` / no `mpirun`). MPI binaries need a leader + ≥1 follower. | Either run with ≥2 ranks (`mpirun -n 2 relion_motion_refine_mpi ...`) for the apply pass, or use the non-MPI binary `relion_motion_refine` for single-rank work. | `10_ctfrefine_polish.md` |
| `ERROR: No electron dose available. Please provide one ...` | `relion_motion_refine` | `motion_estimator.cpp:856` | The movie/optics metadata lacks per-frame dose, which the dose-weighting needs. | Provide the dose (per-frame dose / total dose) in the import/optics so `_rlnMicrographDoseRate`/dose columns exist. | `04_preprocessing.md`, `10_ctfrefine_polish.md` |
| `<starFn> does not contain all of the required columns (...)` | `relion_motion_refine` | `motion_refiner.cpp:132` | The input particle STAR is missing columns the motion fit needs (e.g. the polish corr-mic/optics linkage). | Feed the optimiser/particles STAR from a completed Refine3D+PostProcess, not a hand-trimmed file. | `10_ctfrefine_polish.md` |
| `The window size (--window) has to be an even number.` / `--scale must be an even number` / `--crop must be an even number` | `relion_motion_refine` (frame recombiner) | `frame_recombiner.cpp:73,93,98` | An odd value was passed to `--window`/`--scale`/`--crop`. | Use an even integer. | `10_ctfrefine_polish.md` |

### 2.4 GPU / accelerator (`src/error.h` macros, CUDA path)

| Error string (first line) | Macro / site | Cause | Fix | See-also |
|---|---|---|---|---|
| `A GPU-function failed to execute.` | `ERRGPUKERN` (`error.h:156`) | (Gold row — see §1.) CUDA kernel error; usually OOM on 11 GB cards, sometimes arch/build mismatch. | Reduce memory pressure / one GPU per follower / `--free_gpu_memory`; check `nvidia-smi`. | `08_refine3d.md`, `11_subtract_multibody.md` |
| `You ran out of memory on the GPU(s).` | `ERRGPUCAOOM` (`error.h:187`) | Explicit GPU OOM. Macro gives the rule `~1.1e-8*(2N)^3 GB` per rank for an N-pixel box at final refinement iteration, and flags `device X is split between N followers` as a multiplier. | Smaller box / fewer ranks sharing a GPU / `--maxsig <P>` if `_rlnNrOfSignificantSamples` is huge (>10000). `--maxsig` is a live `relion_refine` flag. | `08_refine3d.md` |
| `There was an issue with the GPU-ids.` | `ERR_GPUID` (`error.h:149`) | A `--gpu` index is too high, or RELION sees a different GPU count than expected on a node. | Run with bare `--gpu` (let RELION choose) or supply valid 0-based indices; GPUs are numbered from 0. | `00_overview.md` |
| `When trying to plan one or more Fourier transforms, ... available GPU memory was insufficient` | `ERRFFTMEMLIM` (`error.h:240`) | Not even one FFT plan fits in GPU memory — e.g. autopicking with `--shrink 1` (huge transforms), or multiple processes contending for the same GPU. | Use `--shrink 0` for autopick (the macro recommends it); reduce contention; `--free_gpu_memory <Mb>` to escape RELION's all-space reservation. | `05_picking_extraction.md` |
| `Relion had to use extra-precision fallbacks too many times.` | `ERRNUMFAILSAFE` (`error.h:285`) | Alignment is numerically unstable — strong preferred orientation, very noisy data, or very small particles — exceeding `--failsafe_threshold`. | Re-extract with re-centering and restart refinement (the macro says so); inspect data quality; as a last resort raise `--failsafe_threshold`. | `08_refine3d.md`, `07_initialmodel_class3d.md` |
| `rlnMicrographScaleCorrection is very high. Did you normalize your data?` | `ERRHIGHSCALE` (`error.h:302`); also thrown in `ml_optimiser.cpp:8498` | Per-micrograph scale correction blew up — particles were not normalised at extraction. | Re-extract with normalisation enabled (default). | `05_picking_extraction.md` |
| `You tried to use gaussian blobs but did not specify a blob-size.` | `ERR_GAUSSBLOBSIZE` (`error.h:304`) | A Gaussian-blob initial reference was requested without a particle diameter. | Set Mask diameter [Å] in the GUI, or `--particle_diameter <d>` on the CLI (the macro names both). | `07_initialmodel_class3d.md` |

### 2.5 Symmetry & image headers

| Error string (fragment) | Program | Throw site | Cause | Fix | See-also |
|---|---|---|---|---|---|
| `... or do not recognize symmetry group <fn_sym>` | symmetry reader (`SymList::read_sym_file`) | `symmetries.cpp:75-76` | The symmetry-group string/file can't be opened or parsed — a typo'd point group, or a missing custom symmetry file. | Use a valid point group (e.g. `C1`, `C2`, `D7`, `I1`/`I2`...) or supply a readable `.sym` file. | `12_conventions_symmetry.md` |
| `ERROR: Symmetry <X>is not known` (printed to stderr, then `exit(0)`) | symmetry-file generator (`symmetry2Quaternions` path) | `symmetries.cpp:756` | The requested point group is not implemented / mistyped. Note this path prints to `cerr` and calls `exit(0)` rather than throwing a `RelionError`, so there is **no** `=== Backtrace ===` block. | Correct the point-group string; check `12_conventions_symmetry.md` for the exact accepted tokens. | `12_conventions_symmetry.md` |
| `Cannot read file <X> It does not exist` | any image reader | `image.h:276` | An MRC/MRCS path in a STAR (or `--i`) points at a missing file — wrong relative path (run from wrong CWD), moved stacks, or a broken symlink. | Run from the project root so relative paths resolve; restore/relink the stack; check the `data_optics`/particle paths. | `02_project_job_tree.md`, `19_interop_coordinates.md` |
| `ERROR: One cannot use helical symmetry with multi-body refinement!` | `relion_refine` (multibody) | `ml_optimiser.cpp:2133` | A multi-body refinement was configured with helical symmetry on — unsupported combination. | Drop helical symmetry for the multibody job, or do helical refinement separately. | `11_subtract_multibody.md`, `13_helical_amyloid.md` |
| `ERROR: 2D classification: Helical tube diameter should be smaller than particle diameter!` | `relion_refine` (helical 2D) | `ml_optimiser.cpp:2289` | The helical tube diameter exceeds the particle/mask diameter. | Reduce the tube diameter or increase the mask diameter so tube < particle. | `13_helical_amyloid.md` |

### 2.6 Continuation / optimiser plumbing (`src/ml_optimiser.cpp`)

| Error string (fragment) | Program | Throw site | Cause | Fix | See-also |
|---|---|---|---|---|---|
| `MlOptimiser::readStar: ... rlnModelStarFile2 not found in optimiser_general table` | `relion_refine` continue | `ml_optimiser.cpp:1268` | Tried to continue a gold-standard (split-halves) run from an optimiser that doesn't record the second half-model — wrong/old/partial optimiser file. | Continue from a complete `*_optimiser.star` written by a gold-standard auto-refine, not a hand-made one. | `08_refine3d.md` |
| `ERROR: cannot change padding factor in a continuation of a multi-body refinement...` | `relion_refine` continue (multibody) | `ml_optimiser.cpp:180` | `--pad` differs from the original run when continuing a multibody refinement. | Keep `--pad` identical to the original job when continuing (the fixture used `--pad 2` consistently). | `11_subtract_multibody.md` |
| `Invalid free_gpu_memory value.` | `relion_refine` | `ml_optimiser.cpp:548` | `--free_gpu_memory` got a nonsensical (e.g. negative) value. | Pass a non-negative integer in **Mb** (live help: `--free_gpu_memory (0)`). | `08_refine3d.md` |
| `Invalid value for --grad_ini_frac.` / `--grad_fin_frac.` | `relion_refine` (VDAM/gradient) | `ml_optimiser.cpp:270,272` | Out-of-range gradient-schedule fraction. | Use a fraction in the documented range (0–1). | `07_initialmodel_class3d.md` |

---

## 3. Common failures / red flags

- **Two errors in one `run.err`, only the first matters.** The fixture's MultiBody jobs show the pattern: a real `A GPU-function failed to execute` from `relion_refine`, then a cascade `MetaDataTable::read: File ...run(_ct2)_data.star does not exist` from `relion_flex_analyse`. Always scroll **up** past the `MPI_ABORT` block to the earliest `ERROR:`.
- **`MPI_ABORT ... errorcode 1` is noise.** It is OpenMPI killing siblings after one rank threw. Don't treat it as the cause.
- **`...is not known` symmetry vs `RelionError`.** The `symmetries.cpp:756` path uses `exit(0)` with no backtrace; if you see a bare `ERROR: Symmetry ... is not known` and no `=== Backtrace ===`, it's that one.
- **Box-size / `_rlnImageSize` errors almost always mean "imported from cryoSPARC / old RELION".** The fixture itself is a 4.0-beta project read by a 5.0 install — older projects are normal — but a *converted* STAR that never carried `_rlnImageSize` is the classic trigger. See `16_interop_cryosparc.md`.
- **Single-rank vs MPI for polishing is a hard rule, not a tuning knob.** Train = `relion_motion_refine` single rank (`--params2`/`--params3`); apply = may use `relion_motion_refine_mpi`. Getting this backwards gives exactly the §1 row-1 error.
- **GPU OOM on 11 GB cards is the default explanation for `A GPU-function failed to execute`** on this host (2× RTX 2080 Ti). Confirm with `nvidia-smi` and the box-size estimate in `ERRGPUCAOOM`.

---

## 4. Errors people expect but I could not ground in this source tree

Listed so you don't assert them. If you hit one, capture the verbatim string and the `in: ...src/<file>.cpp, line N` and add a grounded row.

- "pixel size not set" / "Angpix not set" as a single canonical RELION string — **(unverified)**: not found as a literal `REPORT_ERROR` in the files searched. Pixel-size problems usually surface instead as the box-size / `_rlnImageSize` errors above, or as wrong-resolution output rather than a crash.
- "NaN in FSC" / "FSC contains NaN" as a literal RELION error — **(unverified)**: no such `REPORT_ERROR` found in `ml_optimiser.cpp`. NaNs typically manifest as the numerical-fallback error `ERRNUMFAILSAFE` or as silently bad maps, not a dedicated FSC-NaN abort.
- A literal "cannot read image / corrupt MRC header" with that exact wording — the closest grounded strings are `Cannot read file <X> It does not exist` (`image.h:276`) and `CompressedMRCReader: error in reading header of image <X>` (`image.h:1682`). Treat any other "cannot read image" wording as **(unverified)** until you see its throw site.
- Generic "symmetry not recognised" wording — the grounded forms are `do not recognize symmetry group <fn>` (`symmetries.cpp:76`) and `Symmetry <X>is not known` (`symmetries.cpp:756`). Other phrasings are **(unverified)**.

---

## Cross-links

- `20_troubleshooting.md` — general failure-triage workflow (start here when you don't yet have a string).
- `22_decision_trees.md` — branching "which job/flag" diagnosis.
- `10_ctfrefine_polish.md` — the single-rank-train vs MPI-apply polishing design (row-1 error).
- `08_refine3d.md`, `11_subtract_multibody.md` — GPU OOM, multibody continuation, `--pad`/`--free_gpu_memory`.
- `16_interop_cryosparc.md`, `01_star_and_metadata.md` — `_rlnImageSize`/optics restoration after conversion (`csparc2star.py --boxsize`).
- `12_conventions_symmetry.md` — accepted point-group tokens.
- `02_project_job_tree.md` — exit sentinels, job dirs, relative-path resolution.
- Sibling installed skills owning execution elsewhere: `cryosparc` (the converted-STAR source), `mask` (mask polarity for subtraction/multibody), `cryo-flex-knowledge` (multibody/flex-analyse interpretation).

---

## Sources

Files read for this reference:
- `src/error.h` (macros `ERRGPUKERN`, `ERRGPUCAOOM`, `ERR_GPUID`, `ERRFFTMEMLIM`, `ERRNUMFAILSAFE`, `ERRHIGHSCALE`, `ERR_GAUSSBLOBSIZE`; `REPORT_ERROR`/`REPORT_ERROR_STR` macros)
- `src/metadata_table.cpp` (lines 1107, 1124, 1224, 1353, 1527, 2104–2113)
- `src/jaz/single_particle/obs_model.cpp` (lines 94, 234, 354, 742, 752)
- `src/jaz/single_particle/motion/motion_refiner_mpi.cpp` (lines 37, 42, 54)
- `src/jaz/single_particle/motion/motion_refiner.cpp` (line 132), `motion_estimator.cpp` (line 856), `frame_recombiner.cpp` (lines 73, 93, 98)
- `src/symmetries.cpp` (lines 75–76, 756)
- `src/image.h` (lines 276, 1682)
- `src/ml_optimiser.cpp` (lines 180, 270, 272, 548, 1268, 2133, 2289, 8498)
- `src/pipeline_control.h` (exit-sentinel filenames, lines 32–35)

Live binaries run (`<RELION_BIN>`, RELION 5.0.0-commit-3d6c20):
- `relion_refine --help` (confirmed `--maxsig`, `--pool`, `--j`, `--scratch_dir`, `--gpu`, `--free_gpu_memory`)
- `relion_motion_refine --help` (confirmed `--i`, `--o`, `--params_file`, `--params2`, `--params3`)
- `csparc2star.py --help` (`csparc2star.py`; confirmed `--boxsize BOXSIZE`)

Read-only fixture (`<RELION_PROJECT_FIXTURE>`):
- `Polish/job040/run.err`, `Polish/job040/run.out` (verbatim "Parameter estimation is not supported in MPI mode.")
- `MultiBody/job087/run.err`, `MultiBody/job087/note.txt`, `MultiBody/job089/run.err` (verbatim "A GPU-function failed to execute." and "MetaDataTable::read: File ... does not exist")
