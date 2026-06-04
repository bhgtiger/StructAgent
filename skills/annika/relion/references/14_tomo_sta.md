# 14 — Tomography / subtomogram averaging (RELION 5)

## Scope
The RELION 5.0 native cryo-ET / subtomogram-averaging (STA) pipeline: its four-part data model (tomogram set, particle set, trajectory set, manifold set) bound by an **optimisation set**, the end-to-end job chain from tilt-series import through ModelAngelo, the `relion_tomo_*` C++ program family and the `relion_python_tomo_*` external wrappers, and how this differs from the legacy RELION 1.4/2.0 subtomo path. STA is first-class in RELION 5 but newer and less battle-tested than the SPA path; cross-link `16_interop_cryosparc.md` for the SPA/tilted-SPA boundary.

---

## 1. Data model: optimisation set bundles everything

RELION 5 tomography is built around small STAR "set" files that point at each other. The **optimisation set** (`optimisation_set.star`) is the central object: it contains *only paths* to other files (tomogram set, particle set, trajectory set, manifold set) and most tomo programs both read and write one, so you don't have to track which program updated which file (optimisation_set.rst lines 6-22).

| Set | Typical filename | Key labels / contents | Grounding |
|-----|------------------|------------------------|-----------|
| **Tomogram set** | `tomograms.star` | single `global` table, one row per tilt-series. `rlnTomoName` (unique id), `rlnTomoTiltSeriesStarFile`, `rlnTomoSize<X/Y/Z>`, `rlnTomoHand` (+1/-1 handedness), `rlnMicrographOriginalPixelSize`, `rlnTomoTiltSeriesPixelSize`, `rlnTomoTomogramBinning`, `rlnTomoReconstructedTomogram`, `rlnVoltage`, `rlnSphericalAberration`, `rlnAmplitudeContrast` | tomogram_set.rst 6-23 |
| **Particle set** | `particles.star` | optics table + particles table. 3D coords in `rlnCenteredCoordinate<X/Y/Z>Angst` (RELION 5: replaces the old `rlnCoordinate<X/Y/Z>`) plus `rlnOrigin<X/Y/Z>Angst`; each particle carries `rlnTomoName`. Optional two-orientation scheme: `rlnTomoSubtomogram<Rot/Tilt/Psi>` (geometry-derived) vs `rlnAngle<Rot/Tilt/Psi>` (the angles `relion_refine` actually optimises, usually with a tilt prior) | particle_set.rst 9-19 |
| **Trajectory set** | `motion.star` | P+1 tables; per-particle beam-induced-motion trajectories in Å relative to the lowest-dose tilt image; keyed by `rlnTomoParticleName`. Produced by `relion_tomo_align` (Bayesian polishing) | trajectory_set.rst |
| **Manifold set** | `manifolds.star` | one table per tomogram; rows are manifolds with `rlnTomoManifoldIndex`, `rlnTomoManifoldType` (sphere / spheroid), `rlnTomoManifoldParams`. Used for geometry-constrained picking (membranes/vesicles) | manifold_set.rst |

Each per-tilt-series STAR file (pointed to by `rlnTomoTiltSeriesStarFile`) holds one row per tilt image with `rlnTomo<X/Y>Tilt`, `rlnTomoZRot`, `rlnTomo<X/Y>ShiftAngst`, `rlnDefocus<U/V>`, `rlnDefocusAngle`, `rlnCtfScalefactor` (ice-thickness intensity scaling), `rlnMicrographPreExposure` (cumulative dose), `rlnTomoTiltMovieFrameCount` (tomogram_set.rst 24-30).

**Pseudo-subtomograms are transient.** The particle set is an abstract definition; the on-disk pixel data (2D stacks or 3D volumes) are produced by `relion_tomo_subtomo` and become *invalid* whenever a tomogram property changes — so you re-extract after every CTF-refine or polishing cycle (particle_set.rst 12-14, ExtractSubtomos.rst).

### How `--ios` / `--i` auto-wires inputs

`relion_refine` exposes the optimisation set via **`--ios`** (not `--i`, which is the SPA particle star):
```
--ios () : Input tomo optimisation set file. It is used to set --i, --tomograms,
           --ref or --solvent_mask if they are not provided. Updated output
           optimiser set is created.
--tomograms ()    : Star file with the tomograms, in case subtomos are handled as 2D stacks
--trajectories () : Star file with the tomogram motion trajectories
```
(verified live: `relion_refine --help | grep -iE "ios|tomogram|trajector"`). So one `--ios optimisation_set.star` populates `--i`, `--tomograms`, `--ref`, and `--solvent_mask`. The standalone `relion_tomo_*` programs instead use **`--i`** for the optimisation set and override components with `--p` (particles), `--t` (tomograms), `--mot` (trajectories), `--man` (manifolds), `--ref1`/`--ref2` (half-maps), `--mask`, `--fsc` (verified live across `relion_tomo_subtomo`, `relion_tomo_align`, `relion_tomo_refine_ctf`, `relion_tomo_make_optimisation_set --help`).

> **Pitfall:** the meaning of `--i` flips between worlds. In `relion_refine` `--i` = SPA particle star and the optimisation set is `--ios`. In every `relion_tomo_*` program `--i` = the optimisation set itself. Do not cross them.

---

## 2. Legacy (pre-5) subtomo path — for contrast only

RELION ≤2.x subtomo averaging is a different, IMOD-dependent route built around `relion_prepare_subtomo` (a Tanmay Bharat python script reimplemented by Shaoda He, "supports RELION 2.0 only"; relion_prepare_subtomo.txt 11-21). It expects a per-tomogram `Tomogram/tomo???/` directory with `tomo.mrc`, `tomo.mrcs`, `tomo.star`/`tomo.coords`, `tomo.order`, optional `tomo.tlt`, and calls IMOD `extracttilts`/`newstack` plus CTFFIND/Gctf to emit `do_all_reconstruct_ctfs.sh` (relion_prepare_subtomo.txt 24-36). On this example RELION host install it fails immediately because it hard-codes an IMOD path: `Cannot find IMOD 'extractilts' executable /public/EM/imod/imod-4.5.8/IMOD/bin/extracttilts` (relion_prepare_subtomo.txt 86-96). The doc index still links a "RELION 1.4 subtomogram averaging pipeline" as the *previous* pipeline (STA index.rst 76-79). **Do not use this for new RELION 5 projects** — it predates optics groups, the optimisation-set model, and 2D-stack pseudo-subtomograms. The RELION 4.0 tomo rewrite (Jasenko/Zivanov) introduced the modern `relion_tomo_*` family; RELION 5.0 added 2D-stack pseudo-subtomos, the Napari picker, cryoCARE denoising and the Blush/ModelAngelo integrations.

---

## 3. The pipeline (RELION 5 GUI: `relion --tomo &`)

Launch the tomo GUI from the project dir with `relion --tomo&` and confirm setting up a new project (Introduction.rst). GUI job-type → directory → `_rlnJobTypeLabel` mapping (from `pipeline_jobs.h` lines 327-371):

| Step | GUI job-type | Dir | `_rlnJobTypeLabel` | Underlying executable |
|------|--------------|-----|--------------------|------------------------|
| Import tilt-series | Import | `Import/` (`ImportTomo/` link) | `relion.importtomo` | `relion_python_tomo_import SerialEM` |
| Motion correction | Motion correction | `MotionCorr/` | (shared SPA label) | RELION own impl / MotionCor2 |
| CTF (tomo) | CTF estimation | `CtfFind/` | (shared SPA label) | CTFFIND-4.1 |
| Exclude tilt images | Exclude tilt-images | `ExcludeTiltImages/` | `relion.excludetilts` | `relion_python_tomo_exclude_tilt_images` |
| Align tilt-series | Align tilt-series | `AlignTiltSeries/` | `relion.aligntiltseries` | `relion_align_tiltseries` (IMOD/AreTomo wrapper) |
| Reconstruct tomograms | Reconstruct tomograms | `Tomograms/` | `relion.reconstructtomograms` | `relion_tomo_reconstruct_tomogram` |
| Denoise | Denoise tomograms | `Denoise/` | `relion.denoisetomo` | `relion_python_tomo_denoise` (cryoCARE) |
| Pick | Pick tomograms | `Picks/` | `relion.picktomo` | `relion_python_tomo_pick` (Napari) |
| Extract pseudo-subtomos | Extract subtomos | `Extract/` | `relion.pseudosubtomo` | `relion_tomo_subtomo` |
| Reconstruct particle | Reconstruct particle | `Reconstruct/` | `relion.reconstructparticletomo` | `relion_tomo_reconstruct_particle` |
| CTF refine (tomo) | CTF refinement | `CtfRefine/` | `relion.ctfrefinetomo` | `relion_tomo_refine_ctf` |
| Bayesian polishing | Bayesian polishing | `Polish/` | `relion.framealigntomo` | `relion_tomo_align` |

3D refinement / classification / initial model reuse the **standard SPA jobs** (`relion.refine3d`, `relion.class3d`, `relion.initialmodel`) but fed an optimisation set via `--ios`; they are not separate tomo job types. Tutorial step order: Import → MotionCorr → CTF → ExcludeTiltImages → AlignTiltSeries → ReconstructTomo → Denoise → Pick → ExtractSubtomos (→ ImportCoords if external picks) → InitialModel → ReconstructPart → Refine3D (bin) → DuplicateParticles → Class3D → Refine3D (high-res) → TomoRefinement(CtfRefine+Polish) → ModelAngelo (STA_tutorial/index.rst 7-27).

### 3a. Import (`relion.importtomo`)
The importer is a typer CLI: `relion_python_tomo_import` exposes one sub-command `SerialEM` ("Import tilt-series data using SerialEM metadata"; verified live). GUI inputs: tilt-image frames (`frames/*.mrc`), `mdoc/*.mdoc`, optics group name, pixel size, kV, Cs, amplitude contrast, dose-rate, tilt-axis angle, and **Invert defocus handedness?** (Yes → `rlnTomoHand = -1`, correct for the EMPIAR-10164 tutorial) (ImportTomo.rst). Output: `ImportTomo/job001/tilt_series.star` (table of tilt-series) plus a per-series star `tilt_series/TS_01.star`.

### 3b. Motion correction & CTF
MotionCorr input = `ImportTomo/job001/tilt_series.star`; output `MotionCorr/job002/corrected_tilt_series.star`. Set **Save images for denoising? Yes** and **Save sum of power spectra? Yes** (mandatory with float16 output, since CTFFIND4 cannot read float16) (MotionCorrection.rst). CTF uses CTFFIND-4.1 on the saved power spectra; output `CtfFind/job003/tilt_series_ctf.star` with per-image `rlnDefocusU`/`rlnDefocusV` (CtfEstimation.rst). Inspect with `relion_display --gui --i CtfFind/job003/tilt_series/TS_01.star`.

### 3c. Align tilt-series (`relion_align_tiltseries`)
Wraps three external aligners; choose exactly one (verified live `relion_align_tiltseries --help`):
- `--imod_fiducials` (IMOD fiducial; `--fiducial_diameter` nm),
- `--imod_patchtrack` (IMOD patch-tracking; `--patch_size`, `--patch_overlap`),
- `--aretomo2` (AreTomo2; `--aretomo_exe`, `--aretomo_tiltcorrect`, `--aretomo_ctf`, `--gpu 0:1:2:3`).

Common args: `--i` (tomogram star or wildcard), `--o (AlignTiltSeries/)`, `--tomogram_thickness (300)` nm, `--batchtomo_exe` (or `$RELION_BATCHTOMO_EXECUTABLE`), `--aretomo_exe` (or `$RELION_ARETOMO_EXECUTABLE`). The python-side equivalent `relion_python_tomo_align_tilt_series` exposes sub-commands `AreTomo`, `IMOD:fiducials`, `IMOD:patch-tracking` (verified live). Output: `AlignTiltSeries/job005/aligned_tilt_series.star` (ReconstructTomo.rst input). The job-type's underlying `relion_tomo_align` (the C++ binary) is the **polishing** engine, not this wrapper — note the name collision: `relion_align_tiltseries` (tilt-series geometry) ≠ `relion_tomo_align` (particle/frame polishing).

### 3d. Reconstruct tomograms (`relion_tomo_reconstruct_tomogram`)
Makes a low-mag tomogram for picking/denoising. GUI: unbinned X/Y/Z dims (4000/4000/2000 for tutorial), binned pixel size (10 Å), **Generate tomograms for denoising? Yes** → even/odd halves. Live flags include `--w/--h/--d`, `--bin` or `--binned_angpix`, `--generate_split_tomograms`, `--fourier`, `--ctf`, `--tn` (single tomogram by `rlnTomoName`), `--tiltangle_offset`, `--do_proj` (verified live). Output: `Tomograms/job006/tomograms/rec_TS_01.mrc` (or `rec_TS_01_half<1/2>.mrc` when split) and a `tomograms.star` (ReconstructTomo.rst).

### 3e. Denoise (`relion_python_tomo_denoise`, cryoCARE)
Wrapper for cryoCARE ≥0.2.1 with sub-commands `cryoCARE:train` and `cryoCARE:predict` (verified live). Requires both **Save images for denoising? Yes** (MotionCorr) and **Generate tomograms for denoising? Yes** (Reconstruct tomograms). Two separate Denoise jobs: train then predict. Output `tomograms.star` lives at e.g. `Denoise/job008/tomograms.star` (Denoise.rst).

### 3f. Pick (`relion_python_tomo_pick`, Napari)
Alister Burt's Napari plug-in; sub-commands `particles`, `spheres`, `filaments` (and a non-functional `surfaces`) (verified live + ParticlePicking.rst). `spheres`/`filaments` modes set geometry-derived tilt priors (Z normal to surface / along helical axis). **Run Napari on the local console — it performs poorly over remote/X-forwarded connections** (ParticlePicking.rst). Output optimisation set e.g. `Picks/job009/optimisation_set.star`. External picks (crYOLO etc.) come in via the **Import → Coordinates** tab → `relion_tomo_import_coordinates`, using `rlnTomoName`/`rlnTomoImportParticleFile` columns and a multiply-coords factor equal to the `rlnTomoTomogramBinning` (ImportCoords.rst).

### 3g. Extract pseudo-subtomos as 2D stacks (`relion_tomo_subtomo`)
Strongly prefer **2D stacks** (`--stack2d`) over 3D volumes: less disk, no extra interpolation, slightly better refinements (ExtractSubtomos.rst). Live flags: `--b` (binned projection box), `--crop` (output box), `--bin`, `--stack2d`, `--max_dose`, `--min_frames`, `--float16`, `--j` OMP threads (verified live). GUI bin-6 tutorial: box 192, cropped 96, max dose 50, 2D stacks Yes, float16 Yes. Output: `Extract/job010/Subtomograms/TS_01/1_stack2d.mrcs`, updated `Extract/job010/particles.star`, new `Extract/job010/optimisation_set.star` (ExtractSubtomos.rst).

> MPI versions of Extract / Reconstruct particle / CTF refine / Bayesian polishing parallelise **per tomogram**, so `--j`/MPI procs should not exceed the number of tomograms (ExtractSubtomos.rst).

### 3h. Initial model & Reconstruct particle
Two routes to a starting reference:
1. **De novo** via the standard `3D initial reference` (VDAM/gradient) job fed `Extract/job010/optimisation_set.star`; VDAM "does not scale well with MPI" so use 1 MPI proc (InitialModel.rst). VDAM sometimes prefers 3D pseudo-subtomos — re-extract with **2D stacks? No** to try.
2. **Geometry-primed** via `Reconstruct particle` (`relion_tomo_reconstruct_particle`) when sphere/filament picking already gave good priors. Live flags: `--b`, `--crop`, `--bin`, `--sym`, `--SNR`, `--mem` (GB cap), and **three** thread args `--j`/`--j_in`/`--j_out` (verified live). The GUI "Number of threads" sets both `--j` and `--j_out`, so also pass `--mem` (~80-90% of node RAM) to avoid OOM (ReconstructPart.rst). Output: `Reconstruct/job011/merged.mrc`, plus `half1.mrc`/`half2.mrc` when `rlnRandomSubset` is present.

### 3i. 3D refine (`relion_refine --ios`)
Standard `3D auto-refine`, but on the I/O tab give the **optimisation set** (it auto-fills particle/tomogram/trajectory). Strategy: refine in stages from high binning down to bin 1 because pseudo-subtomos are RAM-heavy (Refine3DIni.rst). Tutorial bin-6 refine: ref `Reconstruct/job011/merged.mrc`, initial low-pass 60 Å, C6, mask diameter 500 Å. Between refines, run **Subset selection → remove duplicates** (`--remove duplicates`, min inter-particle distance e.g. 30 Å) so the same physical particle does not land in both half-sets and inflate the FSC (DuplicateParticles.rst). RELION 5 Blush regularisation (deep-learning prior, shared with SPA) is available in these refine jobs.

### 3j. Tomo refinement cycle: CTF refine + Bayesian polishing
Both operate **at the original (bin-1) pixel size regardless of the refinement binning**, and require: bin-1 reference half-maps from `Reconstruct particle`, a `postprocess.star` from Post-processing (for SNR; without it SNR is slightly optimistic), a bin-1 alignment mask, and the optimisation set (TomoRefinement.rst).

- **CTF refinement** (`relion_tomo_refine_ctf`): live flags `--do_defocus`, `--do_reg_defocus`/`--lambda`, `--d0/--d1/--ds` (defocus search), `--do_scale`/`--per_frame_scale`/`--per_tomogram_scale`, `--do_even_aberrations`/`--do_odd_aberrations` with `--ne`/`--no` (verified live). It writes the estimated defocus + ice-thickness into the **tomogram set** and the higher-order aberrations into the **particle set** — both replace the input sets in the output optimisation set (`Reference/STA/Programs/refine_ctf.rst:23`). Output `CtfRefine/job027/optimisation_set.star`.
- **Bayesian polishing** (`relion_tomo_align`): live flags `--motion` (per-particle beam-induced motion; `--s_vel`, `--s_div`), `--shift_only`, `--r` (max shift px), `--deformation`/`--def_model` (linear/spline/Fourier), `--const_p/--const_a/--const_s`, `--aniso` (verified live). It updates the tomogram set, particle set **and** trajectory set (optimisation_set.rst 22). Output `Polish/job030/{tomograms.star, particles.star, motion.star, optimisation_set.star}` (BayesianPolishing.rst).

Order is interchangeable as long as you carry the optimisation set forward (TomoRefinement.rst). After each cycle: **re-extract** pseudo-subtomos → `Reconstruct particle` → `Post-processing` → new `3D auto-refine` (low-pass 4 Å, sampling 0.9°). Tutorial: 3.6 Å after cycle 1, 3.3 Å after ~4 more cycles (TomoRefinement.rst).

### 3k. ModelAngelo
Built identically to SPA: `ModelAngelo building` job-type, input the postprocessed sharpened map and a FASTA, `Perform HMMer search? No` for the tutorial (ModelAngelo.rst). See `18_interop_chimerax_coot_phenix.md` for downstream rebuild/refine.

---

## 4. `relion_tomo_*` family and `relion_python_tomo_*` wrappers (live inventory)

C++ binaries on PATH (`ls <RELION_BIN> | grep relion_tomo`, verified live): `relion_tomo_subtomo(_mpi)`, `relion_tomo_reconstruct_particle(_mpi)`, `relion_tomo_reconstruct_tomogram(_mpi)`, `relion_tomo_align(_mpi)`, `relion_tomo_refine_ctf(_mpi)`, `relion_tomo_local_particle_refine`, `relion_tomo_fit_blobs_3d`, `relion_tomo_add_spheres`, `relion_tomo_sample_manifold`, `relion_tomo_find_fiducials`, `relion_tomo_find_lattice`, `relion_tomo_import_coordinates`, `relion_tomo_make_optimisation_set`, `relion_tomo_split_optics`, `relion_tomo_predict_tilt_series`, `relion_tomo_bin_stack`, `relion_tomo_dark_erase`, `relion_tomo_delete_blobs`, `relion_tomo_taper`, `relion_tomo_refine_mag`, `relion_tomo_fit_bfactors`, `relion_tomo_compute_FCC`, `relion_tomo_template_pick`, `relion_tomo_Wiener_divide`, `relion_tomo_catalogue_tomos`, `relion_tomo_tomo_ctf`, `relion_tomo_powspec`, `relion_tomo_convert_projections`, `relion_tomo_discover_motif`, `relion_tomo_test`.

Python (typer) wrappers, each a thin bridge to an external tool — **first-class but newer, less battle-tested than SPA**: `relion_python_tomo_import` (SerialEM), `relion_python_tomo_align_tilt_series` (AreTomo / IMOD fiducials / IMOD patch-tracking), `relion_python_tomo_exclude_tilt_images`, `relion_python_tomo_denoise` (cryoCARE train/predict), `relion_python_tomo_pick` (Napari particles/spheres/filaments), `relion_python_tomo_get_particle_poses`, `relion_python_tomo_view` (verified live). These need their wrapped tools installed and on PATH/env (IMOD `$RELION_BATCHTOMO_EXECUTABLE`, AreTomo `$RELION_ARETOMO_EXECUTABLE`, cryoCARE conda env, Napari). The doc index also lists `relion_tomo_make_reference` (runs `relion_postprocess` on a half-map pair) (STA index.rst 69) — *(unverified: not present as a standalone binary in the live PATH listing; likely the `make reference`/Post-process GUI action rather than a separate executable.)*

---

## 5. Runnable examples (illustrative — point `--o` at NEW rootnames)

Site queue convention shown only as illustration (qsub=sbatch, qsubscript=`<RELION_QUEUE_SCRIPT>`, scratch=`<SCRATCH_DIR>`); do not treat as universal.

```bash
# Extract pseudo-subtomos as 2D stacks from a picks optimisation set (bin 6)
relion_tomo_subtomo --i Picks/job009/optimisation_set.star \
  --o Extract/jobNEW/ --b 192 --crop 96 --bin 6 --stack2d --max_dose 50 \
  --min_frames 1 --float16 --j 12

# Reconstruct a bin-6 reference (cap memory; 3 thread args via --j/--j_out)
relion_tomo_reconstruct_particle --i Extract/jobNEW/optimisation_set.star \
  --o Reconstruct/jobNEW/ --b 192 --crop 96 --bin 6 --sym C6 --mem 50 --j 12

# 3D auto-refine driven by the optimisation set (note --ios, not --i)
relion_refine --ios Extract/jobNEW/optimisation_set.star \
  --o Refine3D/jobNEW/run --ini_high 60 --sym C6 --particle_diameter 500 \
  --auto_refine --split_random_halves --gpu 0,1

# Tilt-series alignment via AreTomo2
relion_align_tiltseries --i CtfFind/job003/tilt_series_ctf.star \
  --o AlignTiltSeries/jobNEW/ --aretomo2 --gpu 0:1 --tomogram_thickness 300

# CTF refinement (defocus + per-frame scale), bin-1 reference
relion_tomo_refine_ctf --p Select/job024/particles.star \
  --t Denoise/job008/tomograms.star --ref1 Reconstruct/job025/half1.mrc \
  --ref2 Reconstruct/job025/half2.mrc --mask mask_align.mrc \
  --fsc PostProcess/job026/postprocess.star --b 512 \
  --do_defocus --do_reg_defocus --lambda 0.1 --do_scale --per_frame_scale \
  --o CtfRefine/jobNEW/

# Bayesian polishing with per-particle motion
relion_tomo_align --i CtfRefine/jobNEW/optimisation_set.star \
  --ref1 Reconstruct/job028/half1.mrc --ref2 Reconstruct/job028/half2.mrc \
  --mask mask_align.mrc --fsc PostProcess/job029/postprocess.star \
  --b 512 --r 5 --motion --s_vel 0.2 --s_div 5000 --o Polish/jobNEW/
```
(All flags above verified against live `--help`; defocus regularisation `--lambda 0.1`, scale per-frame, motion sigmas 0.2/5000 follow CtfRefine.rst / BayesianPolishing.rst tutorial values.)

---

## 6. Common failures / red flags

- **`--i` vs `--ios` mix-up:** giving `relion_refine --i optimisation_set.star` treats it as an SPA particle star and fails to find image columns. Use `--ios` for refine; `--i` for `relion_tomo_*`.
- **Stale pseudo-subtomos:** running refine on an old `Extract/` after a CTF-refine/polish silently uses outdated CTF/geometry. Always re-extract after CtfRefine or Polish (particle_set.rst 12-14).
- **Tomo CTF-refine/polish at wrong binning:** these run at bin 1 internally; feeding a binned reference or binned mask gives wrong scaling. Reference half-maps and `mask_align.mrc` must be bin-1 (TomoRefinement.rst).
- **Missing denoising prerequisites:** Denoise train fails unless MotionCorr saved denoise images *and* Reconstruct-tomograms generated even/odd splits (Denoise.rst).
- **float16 + CTFFIND4:** writing motion-corrected tilt images in float16 without "Save sum of power spectra? Yes" breaks CTF estimation (CTFFIND4 can't read float16) (MotionCorrection.rst).
- **MPI > #tomograms:** Extract / Reconstruct particle / CtfRefine / Polish MPI is per-tomogram; excess ranks idle or error (ExtractSubtomos.rst).
- **`relion_tomo_reconstruct_particle` OOM on 11 GB cards:** the two 2080 Ti here are modest. The 3 thread args (`--j`/`--j_in`/`--j_out`) and missing `--mem` cap are the usual cause; set `--mem` to ~80-90% of RAM (ReconstructPart.rst). See `20_troubleshooting.md`.
- **Name collision:** `relion_align_tiltseries` (tilt-series geometry alignment) is *not* `relion_tomo_align` (particle frame-alignment / polishing). The GUI "Bayesian polishing" job calls the latter.
- **MPI param-estimation rule (shared with SPA polishing):** in the SPA fixture, `relion_motion_refine_mpi` aborts with *"Parameter estimation is not supported in MPI mode"* (Polish/job040,041). The tomo polishing engine is a different binary, but the same principle — training/estimation runs single-rank — applies; don't blindly throw MPI at estimation steps. See `10_ctfrefine_polish.md`, `21_error_lookup.md`.
- **Legacy `relion_prepare_subtomo`:** errors with a hard-coded `/public/EM/imod/.../extracttilts` path; it's the RELION 2.0 route and not part of the RELION 5 pipeline (relion_prepare_subtomo.txt 86-96).

---

## 7. Version notes
- **3.1:** optics groups (the tomo particle set carries an optics table).
- **4.0:** full tomo rewrite (`relion_tomo_*` family, optimisation-set model, 3D pseudo-subtomos), VDAM, Schemes. The validation fixture `<RELION_PROJECT_FIXTURE>` is a 4.0-beta *SPA* project read by this 5.0 install (READ-ONLY) — older projects opening fine is normal.
- **5.0:** 2D-stack pseudo-subtomos (preferred), `rlnCenteredCoordinate<X/Y/Z>Angst` replacing pixel coords, Napari picker, cryoCARE denoise wrapper, AreTomo2 tilt-series alignment, Blush regularisation in refine, ModelAngelo, AMD/Intel GPU support, `relion --tomo` GUI.
- **5.1:** amyloid-specific features (out of scope here; see `13_helical_amyloid.md`).

---

## Cross-links
- `00_overview.md`, `02_project_job_tree.md` — pipeline/job-tree model (`default_pipeline.star`, `job.star`, exit sentinels).
- `01_star_and_metadata.md` — STAR `rln*` label conventions.
- `03_cli_inventory.md` — full `relion_*` binary inventory.
- `08_refine3d.md`, `09_mask_postprocess_localres.md` — 3D auto-refine, masking, Post-process (FSC for tomo refine).
- `10_ctfrefine_polish.md` — SPA CTF-refine/polish (analogues; MPI param-estimation rule).
- `12_conventions_symmetry.md` — symmetry / handedness conventions (`rlnTomoHand`).
- `13_helical_amyloid.md` — helical refinement (filament tomo picking shares priors).
- `16_interop_cryosparc.md` — SPA/tilted-SPA vs tilt-series boundary (cryosparc skill is SPA-only for tomo).
- `19_interop_coordinates.md` — crYOLO/external coordinate import (`relion_tomo_import_coordinates`).
- `20_troubleshooting.md`, `21_error_lookup.md`, `22_decision_trees.md`.
- Sibling installed skills: **cryosparc** (SPA boundary), **cryolo** (external picking), **chimerax**/**coot**/**phenix** (post-ModelAngelo model building), **mask** (alignment/FSC masks), **structural-strategy** (what-to-do-next).

---

## Sources
- Docs (release-5.0): `source/Reference/STA/index.rst`; `Datatypes/{tomogram_set,particle_set,trajectory_set,manifold_set,optimisation_set}.rst`; `STA_tutorial/{index,Introduction,ImportTomo,MotionCorrection,CtfEstimation,ExcludeTiltImages,AlignTiltSeries,ReconstructTomo,Denoise,ParticlePicking,ImportCoords,ExtractSubtomos,ReconstructPart,InitialModel,Refine3DIni,DuplicateParticles,TomoRefinement,CtfRefine,BayesianPolishing,ModelAngelo}.rst`.
- Source (relion_ver5.0): `src/pipeline_jobs.h` lines 327-371, 398-441 (tomo PROC_/LABELNEW/DIRNAME); `src/jaz/tomography/` + `.../programs/` listing.
- Captured CLI: `references/cli/.../help/relion_prepare_subtomo.txt`.
- Live `--help` (RELION 5.0.0-commit-3d6c20, <RELION_BIN>): `relion_refine` (grep ios/tomogram/trajector), `relion_tomo_reconstruct_particle`, `relion_tomo_subtomo`, `relion_tomo_reconstruct_tomogram`, `relion_tomo_align`, `relion_tomo_refine_ctf`, `relion_tomo_make_optimisation_set`, `relion_align_tiltseries`, `relion_python_tomo_{import,align_tilt_series,exclude_tilt_images,denoise,pick}`; binary inventory `ls <RELION_BIN> | grep -E "relion_(tomo|python_tomo)"`.
