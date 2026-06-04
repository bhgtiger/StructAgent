# RELION skill — lessons

Version-stamped gotchas learned while building and using this skill. New entries go under **Pending Merge**; the `distill-session` skill promotes them into the body.

## Verified (RELION 5.0.0-commit-3d6c20 on example RELION host; fixture processed with RELION 4.0-beta)

- **Bayesian polishing has two runs; the training run must be single-rank.** `relion_motion_refine` parameter-estimation/training (`--params3` + `--min_p` + `--eval_frac`) aborts with `ERROR: Parameter estimation is not supported in MPI mode` if launched as `relion_motion_refine_mpi` with >1 rank. The fixture's `Polish/job040` and `job041` both died this way. The *apply* run (with `--params <opt_params_all_groups.txt>`) can use MPI. In the GUI this is the "Train optimal parameters" vs "Polish" distinction.
- **Read the real error, not the MPI noise.** A failed `run.err` is dominated by `No protocol specified` (X11/DISPLAY, harmless), `MPI_ABORT was invoked...`, dashed separators, and `... has sent help message`. The actual cause is the `ERROR:` line. `scripts/inspect_project.py` filters the noise; do the same by eye.
- **Distinguish root cause from downstream symptom.** `MultiBody/job087` and `job089` show `relion_flex_analyse ... run_data.star does not exist` — but the *root* cause earlier in `run.err` is `A GPU-function failed to execute` (the multi-body refine itself failed on GPU, so the data STAR was never written; flex_analyse then can't find it). Fix the GPU failure (OOM on the 11 GB RTX 2080 Ti cards), not the missing file.
- **Exit state lives in sentinel FILES, not run.err.** `RELION_JOB_EXIT_SUCCESS` / `RELION_JOB_EXIT_FAILURE` / `RELION_JOB_EXIT_ABORTED` / `RELION_JOB_ABORT_NOW` are empty marker files in the job dir (`src/pipeline_control.h:32-35`). The `RELION_EXIT_SUCCESS/FAILURE/ABORTED` macros (lines 37-39) are what *write* those files — they call `pipeline_control_relion_exit()` (`pipeline_control.cpp:24-56`), which writes the `RELION_JOB_EXIT_*` file and sets the process exit code. There is no file literally named `RELION_EXIT_SUCCESS`. A job killed by the queue (walltime) often has **no** sentinel at all — "no sentinel" ≠ success.
- **Super-resolution vs binned pixel size both live in `data_optics`.** The fixture: `rlnMicrographOriginalPixelSize 0.53` (super-res detector) and `rlnMicrographPixelSize 1.06` (2× binned, the working pixel size). Particle work uses the image/binned pixel size; motion correction and re-extraction care about the original. Mixing them up is a classic resolution-killer and the #1 interop bug.
- **Old projects on a new binary are normal.** The fixture's `default_pipeline.star` is STAR `version 30001` and was processed with `4.0-beta-2-commit-e3afcf` while the install is 5.0. RELION 5 reads it fine (3.1+ STAR auto-upgrades). Don't assume the project version equals the binary version; anchor behavior to the installed binary.
- **`<RELION_GUI_LAUNCHER>` is a GUI launcher, not a headless env.** It rewrites `relion-4.0`→`relion-5.0` in PATH and runs `relion --idle`. For scripted/headless use the `relion_*` binaries are already on PATH; don't source it.
- **`csparc2star.py` (pyem) is installed** at `csparc2star.py`; cryoDRGN is in a conda env, not base PATH. Always `--help` pyem before scripting — its flags churn between versions.

## Pending Merge

- **The fixture is its own answer key for the polishing-MPI bug.** `Polish/job040` and `job041` failed (training under MPI); `Polish/job042` is the **succeeded** single-rank re-run (non-MPI `relion_motion_refine`, produced `opt_params_all_groups.txt`). When diagnosing job040, cite job042 as proof the fix works. (Found via live eval E2.)
- **Not every failed `run.err` has an X11 line.** `Polish/job040`'s log opens straight at the real `ERROR:`; the `No protocol specified` X11 noise is in the sister job `job041`. Don't assume the X11 line is always present — filter MPI_ABORT noise regardless.
- **For a Refine3D `--ref`, use `initial_model.mrc`**, not the InitialModel job's `run_itNNN_class001.mrc` (raw last iteration). `initial_model.mrc` is the symmetrised canonical output. (Found via live eval E7.)
- **`--particle_diameter` has no single source of truth** — the fixture used 160/180/200 Å for the same complex across InitialModel/Refine3D/Class3D. Derive it from the particle's longest dimension + margin (must stay < box×pixel); confirm per target, don't copy another job's value. (Found via live eval E7.)

_(append new session learnings here)_
