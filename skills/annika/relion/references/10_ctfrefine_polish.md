# 10 — CTF/aberration refinement and Bayesian polishing

## Scope
Per-particle/per-optics-group CTF and aberration refinement (`relion_ctf_refine`, GUI "CTF refinement") and reference-based per-particle beam-induced-motion correction / "Bayesian polishing" (`relion_motion_refine`, GUI "Bayesian polishing"), including the mandatory two-pass polishing design (single-rank training/parameter-estimation vs MPI apply), the canonical refine→ctf-refine→refine→polish→refine loop, the real validation-fixture commands, and the failure modes (the Polish/job040 "Parameter estimation is not supported in MPI mode" MPI bug, missing movies, wrong frame dose, absent optics groups). Grounded against the installed RELION 5.0.0-commit-3d6c20 binaries, captured help, RELION-5.0 docs, and `src/pipeline_jobs.cpp`.

---

## 1. Where these jobs sit in the pipeline

Both jobs are post-Refine3D polishing steps that consume a refined particle set **plus** a PostProcess STAR file (for the gold-standard FSC/mask used as a frequency weighting). They are CPU-only on the worker side and are usually iterated:

```
Refine3D → PostProcess
   → CtfRefine  (per-particle defocus + aberrations)
        → Refine3D → PostProcess
            → Polish (train, then apply)
                 → Refine3D → PostProcess
                     → [optionally repeat CtfRefine]
```

Both directions work — you can polish before CTF-refining or vice versa; the docs say to "tackle the biggest problem first" and that an iterative procedure may be beneficial (`SPA_tutorial/Polish.rst`, "When and how to run CTF refinement and Bayesian polishing"). The fixture chose **Polish first, then CtfRefine** (see §6): `Polish/job043/shiny.star` → `CtfRefine/job044` (aniso) → `job045` (defocus) → `job046` (beamtilt).

| Job-type | Program (worker) | GUI label / `_rlnJobTypeLabel` | Key output |
|----------|------------------|--------------------------------|------------|
| CTF refinement (CTF/aberr) | `relion_ctf_refine` | `relion.ctfrefine` | `particles_ctf_refine.star`, `logfile.pdf` |
| CTF refinement (aniso-mag) | `relion_ctf_refine` | `relion.ctfrefine.anisomag` | `particles_ctf_refine.star`, `logfile.pdf` |
| Bayesian polishing (train) | `relion_motion_refine` | `relion.polish.train` | `opt_params_all_groups.txt` |
| Bayesian polishing (apply) | `relion_motion_refine` (`_mpi`) | `relion.polish` | `shiny.star`, `Micrographs/*.mrcs`, `logfile.pdf` |

Job-type labels confirmed from the fixture `job.star` files: `Polish/job040/job.star` → `relion.polish.train`; `Polish/job043/job.star` → `relion.polish` (with `_rlnJobIsContinue 1`); `CtfRefine/job044/job.star` → `relion.ctfrefine.anisomag`. Node labels from `src/pipeline_jobs.h:264-269` (`LABEL_CTFREFINE_REFINEPARTS`, `LABEL_CTFREFINE_LOG`, `LABEL_CTFREFINE_ANISOPARTS`, `LABEL_POLISH_PARTS`, `LABEL_POLISH_PARAMS`).

> Rationale: Zivanov, Nakane & Scheres (2019/2020) — reference-based per-particle motion (Bayesian polishing) and higher-order-aberration / per-particle defocus refinement were introduced as cheap resolution-recovery steps on top of a refined map. The optics-group machinery they depend on dates from RELION 3.1.

---

## 2. CTF refinement — `relion_ctf_refine`

### 2.1 Required inputs
- `--i` Input particle STAR (from a Refine3D `run_data.star`, or a prior `particles_ctf_refine.star`). Help line 12.
- `--f` PostProcess `postprocess.star` (the reference FSC). Help line 13/75.
- `--o` Output directory, e.g. `CtfRefine/job0NN/`. Help line 14/76.

**Optics groups are mandatory.** All aberration, beam-tilt, anisotropic-magnification and per-micrograph parameters are stored *per optics group* in the `data_optics` table (3.1+ convention). A 3.0-era STAR without a `data_optics` block cannot be CTF-refined — see §7. The fixture's real `data_optics` has a single `opticsGroup1` (0.53 super-res → 1.06 binned, 300 kV, Cs 2.7, AmpC 0.1).

### 2.2 What it fits (all default `false`, opt-in flags)
From `relion_ctf_refine --help` (captured 2026-06-04, lines 25-62):

| Concern | Flag | Notes |
|---------|------|-------|
| Per-particle defocus + astigmatism | `--fit_defocus` (+ `--fit_mode`) | per-particle/per-micrograph/fixed, see §2.3 |
| Inner-freq cutoff for defocus | `--kmin_defocus` (30.0 Å) | "Minimum resolution for fits" in GUI |
| Brute-force defocus search | `--bf0` / `--bf1` / `--bf_only` (range `--bf_range`, 2000 Å) | RELION-3.0-style; rarely needed |
| Legacy per-particle astig | `--legacy_astig` | RELION-3.0 behaviour |
| CTF B-factors | `--fit_bfacs` (`--bfac_per_mg`, `--bfac_min_B -30`, `--bfac_max_B 300`) | |
| Beam tilt (asymmetric, odd Zernike) | `--fit_beamtilt` (`--kmin_tilt` 20.0) | |
| Trefoil + higher odd aberrations | `--odd_aberr_max_n` (0; set to 3 for trefoil) | GUI "Also estimate trefoil?" sets `--odd_aberr_max_n 3` (`pipeline_jobs.cpp:6143`) |
| Symmetric (even) aberrations: 4th-order / tetrafoil / Cs error | `--fit_aberr` (`--even_aberr_max_n` 4, `--kmin_aberr` 20.0) | GUI "estimate 4th order aberrations?" |
| Anisotropic magnification | `--fit_aniso` (`--kmin_mag` 20.0) | mutually exclusive with aberration fits |
| Threads | `--j` | CPU-only; **no MPI** for `relion_ctf_refine` (no `_mpi` binary used by this job) |

The GUI enforces one important rule: anisotropic magnification is done **alone**, never simultaneously with CTF/tilt/aberration fitting ("simultaneous magnification and aberration refinement is unstable", `CtfRefine.rst`; `pipeline_jobs.cpp` puts `--fit_aniso` in its own branch). That is why the fixture splits aniso, defocus, and beam-tilt into three separate jobs.

### 2.3 The `--fit_mode` string (the part people get wrong)
`--fit_mode` is **5 characters** describing how to fit, in order:

1. phase shift, 2. defocus, 3. astigmatism, 4. spherical aberration, 5. B-factors

Each character is `p` (per-particle), `m` (per-micrograph), or `f` (fixed). Default `fpmfm` (help line 27-29). The GUI builds it as phase / defocus / astigmatism / **always `f` for Cs** / B-factor (`pipeline_jobs.cpp:6121-6125`; `getCtfFitString` maps the GUI dropdowns `f`/`m`/`p` at `pipeline_jobs.cpp:243-249`). So the GUI never lets you refine Cs per-particle via `--fit_mode`.

Fixture defocus job (`CtfRefine/job045/note.txt`) used `--fit_mode fpmff`:

| pos | char | meaning |
|-----|------|---------|
| 1 phase | `f` | phase shift fixed (not phase-plate data) |
| 2 defocus | `p` | **per-particle** defocus |
| 3 astig | `m` | **per-micrograph** astigmatism |
| 4 Cs | `f` | spherical aberration fixed (GUI always forces this) |
| 5 B-factor | `f` | CTF B-factor fixed |

That matches the docs' recommended setting (per-particle defocus, per-micrograph astigmatism) for a reference resolved well beyond 4 Å (`CtfRefine.rst`).

### 2.4 Outputs
- `particles_ctf_refine.star` — updated particles (per-particle `rlnDefocusU/V`, per-optics-group aberration/`rlnMagMat??`/beam-tilt fields). The anisotropic-mag branch and the CTF/aberr branch both write this name (`pipeline_jobs.cpp:6105,6113`).
- `logfile.pdf` — accumulated aberration/defocus diagnostic plots (asymmetric image = beam-tilt/trefoil; symmetric image = Cs error/tetrafoil; per-micrograph defocus colour plots).

### 2.5 Real fixture commands (read-only, illustrative)
From the fixture (`*/note.txt`); the `which relion_ctf_refine` wrapper means single-process CPU runs with `--j 16`:

```bash
# 1) anisotropic magnification (alone)  — CtfRefine/job044
relion_ctf_refine --i Polish/job043/shiny.star \
  --f PostProcess/job039/postprocess.star \
  --o CtfRefine/job044/ --fit_aniso --kmin_mag 30 --j 16

# 2) per-particle defocus + per-mic astig  — CtfRefine/job045
relion_ctf_refine --i CtfRefine/job044/particles_ctf_refine.star \
  --f PostProcess/job039/postprocess.star \
  --o CtfRefine/job045/ --fit_defocus --kmin_defocus 30 --fit_mode fpmff --j 16

# 3) beam tilt  — CtfRefine/job046
relion_ctf_refine --i CtfRefine/job045/particles_ctf_refine.star \
  --f PostProcess/job039/postprocess.star \
  --o CtfRefine/job046/ --fit_beamtilt --kmin_tilt 30 --j 16
```

To reproduce against new outputs, keep `--o` pointing at a NEW rootname (e.g. `--o CtfRefine/job100/`) and chain `particles_ctf_refine.star` as the next `--i`.

---

## 3. Bayesian polishing — `relion_motion_refine` — TWO distinct runs

`relion_motion_refine` operates in two completely different modes from the same binary. Confusing them is the #1 polishing failure.

### 3.1 Shared inputs (both modes)
From `relion_motion_refine --help` (lines 11-25, 89) and `pipeline_jobs.cpp:5890-5905`:
- `--i` particle STAR (a Refine3D `run_data.star`).
- `--f` PostProcess `postprocess.star`.
- `--corr_mic` the **uncorrected/motion-corrected micrographs** list, i.e. `MotionCorr/jobNNN/corrected_micrographs.star` — this is how it finds the original **movies**. Without it (or if the movie paths are stale) polishing cannot read frames. Help line 89; GUI "Micrographs (from MotionCorr)".
- `--first_frame 1 --last_frame -1` — frame window. Docs **strongly recommend keeping all frames** ("throwing away first/last frames is *not recommended*"; B-factor weighting handles SNR), `Polish.rst`.
- `--float16` — write half-precision MRCS (recommended, used by fixture).

The per-frame dose is **not** passed on the polishing command line by the GUI — it is read from the optics/movie metadata; the manual `relion_motion_refine` flag for it is `--fdose` (e^-/Å²/frame, default −1 = read from metadata, help line 27/120). A wrong dose here corrupts the radiation-damage weighting — see §7.

### 3.2 Mode A — TRAINING / parameter estimation (`relion.polish.train`)
Estimates the three motion priors (σ_vel, σ_div, σ_acc) on a particle subset. Triggered by the parameter-estimation flags:

| Flag | Help | Meaning |
|------|------|---------|
| `--params3` | line 53 | estimate 3 parameters (σ_vel, σ_div, σ_acc) |
| `--params2` | line 52 | estimate 2 parameters (used when σ_acc < 0; `pipeline_jobs.cpp:5918-5923`) |
| `--min_p` | line 56 (default 1000) | min particles for estimation; GUI "Use this many particles" |
| `--eval_frac` | line 55 (0.5) | fraction of Fourier pixels for evaluation; GUI "Fraction for testing" |
| `--align_frac` | line 54 (0.5) | fraction for alignment; GUI sets `align_frac = 1 − eval_frac` (`pipeline_jobs.cpp:5910`) |

Output: a text file **`opt_params_all_groups.txt`** (node label `LABEL_POLISH_PARAMS`, `pipeline_jobs.cpp:5929`). In the fixture `Polish/job042/opt_params_all_groups.txt` contains the three sigmas on one line: `0.9735 7920 5.79`.

> **CRITICAL — training is single-MPI-rank only.** "Note that the training step of this program has not been MPI-parallelised. Therefore, make sure you use only a single MPI process" (`Polish.rst`). Use threads (`--j`) for speed, not MPI ranks. This is exactly the Polish/job040 fixture failure (§5).

### 3.3 Mode B — APPLY / polishing (`relion.polish`)
Fits per-particle motion tracks for all particles and writes weighted-average "shiny" particles. Triggered by `--combine_frames` (`pipeline_jobs.cpp:5951`):

| Flag | Help | Meaning |
|------|------|---------|
| `--combine_frames` | line 67 | "Combine movie frames into polished particles" — the APPLY switch |
| `--params_file FILE` | line 31 | read σ_vel/σ_div/σ_acc from `opt_params_all_groups.txt`; GUI "Optimised parameter file" (`pipeline_jobs.cpp:5948`) |
| `--s_vel / --s_div / --s_acc` | lines 28-30 | OR supply the three sigmas directly ("use own parameters?"; `pipeline_jobs.cpp:5938-5940`) |
| `--bfac_minfreq 20 / --bfac_maxfreq -1` | lines 73-74 | B-factor fit range (min/max res); GUI defaults |
| `--scale / --window / --crop` | lines 69-71 | optional re-extraction box / rescale (GUI "Extraction size" / "Re-scaled size") |
| `--j` | line 83 | OMP threads |

`relion_motion_refine` (apply) **is MPI-parallelised** — the fixture runs `relion_motion_refine_mpi ... --combine_frames`. Outputs: `shiny.star` (node `LABEL_POLISH_PARTS`), polished `Micrographs/*.mrcs`, `bfactors.star`/`scalefactors.eps`, and `logfile.pdf` (scale/B-factor + per-particle track plots). `shiny.star` is the input for the next Refine3D.

> If you *skip* training, the **installed-binary** default sigmas are σ_vel=0.5, σ_div=5000, σ_acc=2 (`relion_motion_refine --help`: `--s_vel (0.5) --s_div (5000.0) --s_acc (2.0)`; initial-guess variants `--s_vel_0 (0.6)`, `--s_div_0 (10000)`, `--s_acc_0 (3)`). Older docs/tutorials quote σ_vel=0.2 — trust the installed `--help`, not the prose. These often work as well as a trained set.

### 3.4 Real fixture commands (read-only)
```bash
# TRAIN — Polish/job042 (single-rank: NO _mpi)  — SUCCEEDED
relion_motion_refine \
  --i Refine3D/job037/run_data.star \
  --f PostProcess/job039/postprocess.star \
  --corr_mic MotionCorr/job002/corrected_micrographs.star \
  --first_frame 1 --last_frame -1 --o Polish/job042/ --float16 \
  --min_p 10000 --eval_frac 0.5 --align_frac 0.5 --params3 --j 16

# APPLY — Polish/job043 (MPI OK)  — SUCCEEDED, writes shiny.star + Micrographs/*.mrcs
relion_motion_refine_mpi \
  --i Refine3D/job037/run_data.star \
  --f PostProcess/job039/postprocess.star \
  --corr_mic MotionCorr/job002/corrected_micrographs.star \
  --first_frame 1 --last_frame -1 --o Polish/job043/ --float16 \
  --params_file Polish/job042/opt_params_all_groups.txt \
  --combine_frames --bfac_minfreq 20 --bfac_maxfreq -1 --j 16
```

Note the APPLY job reads `--i Refine3D/job037/run_data.star` (the *refined* particles, full set) and the **trained params from job042**, not job040/041. The fixture re-ran job043 several times with `--only_do_unfinished` (checkpointed continue, `_rlnJobIsContinue 1`) — normal for a long apply step. The second polishing cycle mirrors this: `Polish/job070` (train) → `Polish/job071` (apply, `--params_file Polish/job070/opt_params_all_groups.txt`).

---

## 4. After polishing / CTF refinement — re-refine
Always submit a fresh Refine3D + PostProcess on the new particle set:
- after CtfRefine: input `CtfRefine/jobNNN/particles_ctf_refine.star`;
- after Polish: input `Polish/jobNNN/shiny.star`, and supply a half-map as the reference (`run_half1_class001_unfil.mrc`) so both half-maps are read for gold-standard refinement and you can start from higher initial resolution (`Polish.rst`). See `08_refine3d.md` and `09_mask_postprocess_localres.md`.

---

## 5. The fixture MPI failure (Polish/job040 & job041) — read this

`Polish/job040/note.txt` shows the GUI submitted the **training** parameters (`--min_p 10000 --eval_frac 0.5 --align_frac 0.5 --params3`) but via the **MPI** binary:

```
`which relion_motion_refine_mpi` --i Refine3D/job037/run_data.star ... --params3 --j 16 ...
```

`Polish/job040/run.err`:
```
in: <RELION4_INSTALL>/source/src/jaz/single_particle/motion/motion_refiner_mpi.cpp, line 42
ERROR:
Parameter estimation is not supported in MPI mode.
... MPI_ABORT was invoked on rank 0 ... errorcode 1.
```
The job dir gets a `RELION_JOB_EXIT_FAILURE` sentinel file (one of `RELION_JOB_EXIT_SUCCESS/FAILURE/ABORTED/RELION_JOB_ABORT_NOW`, `src/pipeline_control.h:32-35`). Same error in `job041`. The fix is in `job042`: identical flags, but the **non-MPI** `relion_motion_refine` (single rank) → success → `opt_params_all_groups.txt`. (The fixture was a RELION-4.0-beta project; the bug and fix are identical in 5.0.)

**Cause:** a training job was launched with nr_mpi > 1. **Fix:** set MPI procs = 1 for any polishing job whose Train tab has "Train optimal parameters? = Yes" (i.e. any `relion.polish.train` job). Threads (`--j`) are fine and recommended.

---

## 6. Canonical run order (with the fixture as a worked example)

```
Refine3D/job037 → PostProcess/job039
  → Polish/job040 (TRAIN, MPI)   ✗ FAIL  "Parameter estimation is not supported in MPI mode"
  → Polish/job041 (TRAIN, MPI)   ✗ FAIL  (same)
  → Polish/job042 (TRAIN, 1-rank) ✓      → opt_params_all_groups.txt = "0.9735 7920 5.79"
  → Polish/job043 (APPLY, MPI)    ✓      → shiny.star
     → CtfRefine/job044 (aniso-mag) → job045 (per-part defocus) → job046 (beamtilt)
        → Refine3D/job065 → PostProcess/job068
           → Polish/job070 (TRAIN) → Polish/job071 (APPLY) → shiny.star
              → CtfRefine/job072 (aniso) → job073 (defocus) → job074 (beamtilt)
```

The generic recommended loop is **refine → ctf refine → refine → polish → refine** (`Polish.rst` §"When and how…"); the fixture interleaves polish-before-ctf, which is equally valid.

---

## 7. Common failures / red flags

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Parameter estimation is not supported in MPI mode` (job aborts at rank 0) | Training job launched with MPI > 1 | Run the **train** job with 1 MPI rank; use `--j` threads for speed (fixture job040/041 vs job042) |
| `ERROR: ... corrected_micrographs.star does not exist` / cannot find movies / "could not read movie" | `--corr_mic` missing/stale, or movie files moved relative to `MotionCorr/.../corrected_micrographs.star` | Point `--corr_mic` at the live `MotionCorr/jobNNN/corrected_micrographs.star`; ensure movie paths resolve. See `04_preprocessing.md` |
| Polished map worse / wrong radiation-damage weighting | Wrong per-frame dose, or first/last frames discarded | Keep `--first_frame 1 --last_frame -1`; verify dose in metadata (`--fdose` only if metadata dose is wrong) |
| CtfRefine errors / no aberration fields written; "no optics group" | Input STAR has no `data_optics` block (pre-3.1 / 3.0-era file) | Re-import or upgrade the STAR so each particle has an optics group; see `01_star_and_metadata.md`, `12_conventions_symmetry.md` |
| `ERROR: you did not select any CTF parameter to fit` | `do_ctf=Yes` but all `--fit_mode` slots `f` | Set at least one of phase/defocus/astig to `p`/`m` (`pipeline_jobs.cpp:6080-6084`) |
| Aniso-mag job silently disables CTF/aberration options | By design: `--fit_aniso` is mutually exclusive with `--fit_defocus`/`--fit_beamtilt`/`--fit_aberr` | Run aniso-mag in its own job, then CTF/aberr in another (fixture job044 vs job045/046) |
| Apply job restarts from scratch on every resubmit | not using continue | The GUI "Continue" sets `--only_do_unfinished` (`_rlnJobIsContinue 1`); long apply jobs are checkpointed per-micrograph (fixture job043) |

Memory note: this site has 2× RTX 2080 Ti (11 GB). It does not matter for CtfRefine/Polish themselves (CPU workers), but the **re-refinement** afterward is GPU and box-size sensitive — see `08_refine3d.md`. If training runs out of RAM, lower `--min_p` (docs: "if you run out of memory, try training with fewer particles", `Polish.rst`).

---

## 8. Version notes
- Optics groups (the carrier for all aberration/beam-tilt/mag fields) are a **RELION-3.1** feature; older 3.0 STARs must be upgraded before CtfRefine. The fixture is a 4.0-beta project read by a 5.0 install — normal and supported.
- Higher-order aberration / per-particle defocus refinement and Bayesian polishing came in **RELION 3.1** (Zivanov et al.); the algorithms are unchanged through 5.0. The two-binary CtfRefine vs MotionRefine split and the train/apply duality of `relion_motion_refine` are identical in 4.0 and 5.0.
- RELION 5.0 adds Blush regularisation in Refine3D (relevant for the re-refinement step, not CtfRefine/Polish) and full DynaMight/ModelAngelo/AMD-Intel-GPU support — none change the CtfRefine/Polish CLI. The subtomogram analogue of polishing ("Fit per-particle motion?", `pipeline_jobs.cpp:7303`) belongs to the tomo path — see `14_tomo_sta.md`.

---

## Cross-links
- `08_refine3d.md` — the Refine3D jobs that bracket CtfRefine/Polish (and the half-map-reference trick).
- `09_mask_postprocess_localres.md` — the PostProcess `postprocess.star` consumed via `--f`.
- `04_preprocessing.md` — MotionCorr `corrected_micrographs.star` and movie handling for `--corr_mic`.
- `01_star_and_metadata.md`, `12_conventions_symmetry.md` — optics-group / `data_optics` requirements and aberration metadata labels.
- `11_subtract_multibody.md` — the other post-refinement consumers; MultiBody fixture GPU failures.
- `02_project_job_tree.md` — job.star / default_pipeline.star / exit-sentinel mechanics.
- `20_troubleshooting.md`, `21_error_lookup.md` — error-string lookup.
- Sibling skills: `cryosparc` (CryoSPARC's Global/Local CTF refinement equivalents), `cryo-flex-knowledge` (multi-body / heterogeneity context).

## Sources
- Live/captured help: `relion_ctf_refine --help` and `relion_motion_refine --help` from `references/cli/relion5_cli_capture_20260604/help/relion_ctf_refine.txt`, `.../relion_motion_refine.txt` (RELION 5.0.0-commit-3d6c20).
- Docs: `relion-documents_release-5.0/source/SPA_tutorial/CtfRefine.rst`, `.../SPA_tutorial/Polish.rst`.
- Source: `relion_ver5.0/src/pipeline_jobs.cpp` (Polish builder ~5828-5970; CtfRefine builder ~6080-6155; `getCtfFitString` 243-249) and `pipeline_jobs.h:264-269` (node labels).
- Fixture (READ-ONLY) `<RELION_PROJECT_FIXTURE>`: `Polish/job040/note.txt`+`run.err` (MPI train failure), `Polish/job041,042,043,070,071/note.txt`, `Polish/job042/opt_params_all_groups.txt`, `CtfRefine/job044,045,046,072,073,074/note.txt`, and the `job.star` `_rlnJobTypeLabel` values.
