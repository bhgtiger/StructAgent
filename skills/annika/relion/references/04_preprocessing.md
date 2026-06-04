# 04 — Import, motion correction, CTF estimation

## Scope
The three jobs that turn raw movies/micrographs into CTF-corrected micrographs ready for picking: `Import` (`relion_import`), `Motion correction` (`relion_run_motioncorr`), and `CTF estimation` (`relion_run_ctffind`). Covers optics-group/metadata setup, EER/TIFF/MRC + gain handling, RELION-own vs MotionCor2 motion correction, the CTFFIND-4.1/5 wrapper (and why Gctf is gone in 5.0), the STAR files and per-micrograph logfiles each job emits, and the gain-orientation / EER-fraction / pixel-size mistakes that bite people. Grounded against the live RELION 5.0.0-commit-3d6c20 binaries on example RELION host and the 4.0-beta validation fixture at `<RELION_PROJECT_FIXTURE>` (READ-ONLY).

---

## 1. Import (`relion_import`)

Import is the entry point: it copies/links raw data into the pipeline and writes a STAR file with the **optics group** block that carries pixel size, voltage, Cs, amplitude contrast and the MTF reference. From RELION 3.1 onward all CTF/microscope metadata lives in a `data_optics` block keyed by `_rlnOpticsGroup`; this is the per-dataset "optics group" concept (3.1 feature). Everything downstream (motion-corr, CTF, refinement) reads it.

### What you can import
Two mutually-exclusive modes (`getCommandsImportJob`, pipeline_jobs.cpp:1283 — you cannot import raw AND "other" in one job):

| GUI node type | `relion_import` flag | output |
|---|---|---|
| Raw movies (multi-frame) | `--do_movies` | `movies.star` |
| Raw micrographs (single-frame) | `--do_micrographs` | `micrographs.star` |
| Particle coordinates (`*.box`, `*_pick.star`) | `--do_coordinates` | `coords_suffix*` |
| Particles STAR file | `--do_particles` (+ optional `--particles_optics_group_name`) | copied `.star` |
| Multiple 2D/3D references (`.star`/`.mrcs`) | `--do_other` | copied file |
| 3D reference (`.mrc`) | `--do_other` | copied file |
| 3D mask (`.mrc`) | `--do_other` | copied file |
| Micrographs STAR file | `--do_other` | copied file |
| Unfiltered half-map (`*unfil.mrc`) | `--do_halfmaps` | both half-maps copied |

(node-type menu strings and flag dispatch: pipeline_jobs.cpp:1353–1435; half-map auto-find of the `half1`↔`half2` partner: lines 1396–1414.)

### Optics-group flags (raw movies/micrographs only)
From `relion_import --help` (live binary): `--optics_group_name` (default `opticsGroup1`), `--optics_group_mtf`, `--angpix` (Å, default 1.0), `--kV` (default 300), `--Cs` (mm, default 2.7), `--Q0` (amplitude contrast, default 0.1), `--beamtilt_x`, `--beamtilt_y`. To split a dataset into multiple optics groups, import each group separately with its own `--optics_group_name`, then merge with a `Join star files` job (Preprocessing.rst:48).

### Real fixture command (4.0-beta, K3 super-res)
From `Import/job001/note.txt`:
```
relion_import  --do_movies  --optics_group_name "opticsGroup1" \
  --optics_group_mtf ../../other/MTF/mtf_k3_standard_300kV_FL2.star \
  --angpix 0.53 --kV 300 --Cs 2.7 --Q0 0.1 --beamtilt_x 0 --beamtilt_y 0 \
  --i "Micrographs/*.tiff" --odir Import/job001/ --ofile movies.star
```
This writes `movies.star` with `data_optics` columns `_rlnOpticsGroupName / _rlnOpticsGroup / _rlnMtfFileName / _rlnMicrographOriginalPixelSize (0.53) / _rlnVoltage (300) / _rlnSphericalAberration (2.7) / _rlnAmplitudeContrast (0.1)` and a `data_movies` block of `_rlnMicrographMovieName / _rlnOpticsGroup`. Note: `--angpix` here is the **physical/super-res pixel** of the recorded movie (0.53 Å); binning to 1.06 Å happens later in motion correction, which then adds `_rlnMicrographPixelSize`.

A runnable 5.0 example (new output rootname):
```
relion_import --do_movies --optics_group_name opticsGroup1 \
  --optics_group_mtf mtf_k3_300kV.star \
  --angpix 0.53 --kV 300 --Cs 2.7 --Q0 0.1 \
  --i "Movies/*.tiff" --odir Import/job901/ --ofile movies.star
```

### Path rules (enforced by the GUI job builder)
- **No `../` anywhere** in the input wildcard, and **no leading `/`** — import must be by a relative path inside the project (pipeline_jobs.cpp:1300–1310). If data live elsewhere, make an **absolute-path symbolic link** into the project and import the link by a relative path. Relative-path symlinks (e.g. `../../storage`) cause problems downstream (Preprocessing.rst:16).
- Optics-group names may contain only numbers, letters and hyphens (validated at pipeline_jobs.cpp:1334).
- The MTF file is optional; skipping it does not change final resolution, only the B-factor — it can also be applied later in PostProcessing (Preprocessing.rst:67–68).

### EER / TIFF / MRC at import
Movies may be `.mrc`, `.mrcs`, `.tif`, `.tiff`, or `.eer`; single micrographs use `.mrc` (Preprocessing.rst:18). RELION 5.0 can read MRC movies compressed by bzip2/xz/zstd/gzip (needs `pbzip2`/`xz`/`zstd` on PATH; MovieCompression.rst:344–347 — note that compressed MRC is supported only in motion correction and Bayesian Polish, not tomo/`relion_image_handler`). **For EER you import the `.eer` files using the physical pixel size for 4K rendering** (half the physical size for 8K; MovieCompression.rst:73) — the fractionation and rendering are set in the *next* (motion-corr) job, not at import.

---

## 2. Motion correction (`relion_run_motioncorr`)

Whole-frame (+patch) movie alignment. The job-type wraps two engines (motioncorr_runner.cpp:141 hard-requires exactly one):

| Engine | flag | notes |
|---|---|---|
| RELION's own (CPU, multithreaded) | `--use_own` | favoured; required if you want **Bayesian Polish** later (Polish reads local tracks only from RELION-own); can write summed power spectra for CTFFIND; supports `--float16` |
| UCSF MotionCor2 (GPU) | `--use_motioncor2 --motioncor2_exe <path>` | does on-the-fly outlier-pixel rejection not passed to Polish; **cannot write float16** |

(engine trade-offs: Preprocessing.rst:94–101.) RELION-own does **not** use the GPU (Preprocessing.rst:193); it is multithreaded via `--j`, and it is optimal to pick a thread count that divides the number of frames evenly.

### Flags (from live `relion_run_motioncorr --use_own --help`)
General / dose / own-implementation flags:

| Concern | flag (default) | meaning |
|---|---|---|
| Input | `--i` | movies STAR (e.g. `Import/job001/movies.star`) |
| Output dir | `--o (MotionCorr)` | |
| Threads/movie | `--j (1)` | one thread per movie frame is efficient |
| Frame range for sum | `--first_frame_sum (1)` / `--last_frame_sum (-1)` | -1/0 = use all |
| Power spectra for CTFFIND | `--grouping_for_ps (-1)` | group N frames → write summed PS; `-1` = don't. GUI "Sum of power spectra every e/A2" maps here. `--ps_size (512)` |
| EER fractionation | `--eer_grouping (40)` | raw hardware frames per fraction |
| EER rendering | `--eer_upsampling (1)` | 1 = 4K physical, 2 = 8K super-res |
| Dose weighting | `--dose_weighting` + `--angpix`, `--voltage`, `--dose_per_frame (1)`, `--preexposure (0)` | |
| B-factor | `--bfactor (150)` | larger for super-res movies (Preprocessing.rst:145) |
| Binning | `--bin_factor (1)` | Fourier-crop; 2 for super-res / 8K-EER |
| Patches | `--patch_x (1)` `--patch_y (1)` | local motion; e.g. 5 5 |
| Group frames | `--group_frames (1)` | **must stay 1 for EER** (MovieCompression.rst:81) |
| Gain | `--gainref <mrc>` `--gain_rot (0)` `--gain_flip (0)` | see §4 |
| Defects | `--defect_file` | MotionCor2-style `x y w h` text OR defect map (MRC/TIFF, 1=bad) |
| float16 | `--float16` | half-precision MRC mode 12; **own-impl only**, and you **must** also write power spectra (`--grouping_for_ps`) — enforced at pipeline_jobs.cpp:1565–1573 |
| Save non-DW | `--save_noDW` | extra `_noDW.mrc` (sometimes better Thon rings for CTF) |
| even/odd split | `--even_odd_split` | for tomo denoising |
| Skip hot-pixel | `--skip_defect` | |

`--gain_rot`: 0/1/2/3 = number of clockwise 90° rotations (== MotionCor2 RotGain). `--gain_flip`: 0/1 (flip Y, upside-down) / 2 (flip X, left-right) (== MotionCor2 FlipGain). These come straight from the live help.

### Real fixture command (RELION-own, K3 super-res → 2× binned)
From `MotionCorr/job002/note.txt`:
```
relion_run_motioncorr --i Import/job001/movies.star --o MotionCorr/job002/ \
  --first_frame_sum 1 --last_frame_sum -1 --use_own --j 50 \
  --bin_factor 2 --bfactor 350 --dose_per_frame 1 --preexposure 0 \
  --patch_x 5 --patch_y 5 --eer_grouping 32 \
  --gainref 20220301_K3-20050033GainRef.x1.m1.mrc --gain_rot 2 --gain_flip 2 \
  --dose_weighting
```
`--bin_factor 2` takes the 0.53 Å super-res movie to 1.06 Å, which is why the output `corrected_micrographs.star` optics block adds `_rlnMicrographPixelSize = 1.060000` next to `_rlnMicrographOriginalPixelSize = 0.530000`. `--eer_grouping 32` is present but **ignored for TIFF input** (Preprocessing.rst:121) — harmless leftover. `--gain_rot 2 --gain_flip 2` is the orientation this K3 gain needs.

### Outputs
- `corrected_micrographs.star` — `data_optics` (now incl. `_rlnMicrographPixelSize`) + `data_micrographs` with `_rlnMicrographName` (summed `.mrc`), `_rlnMicrographMetadata` (per-mic `.star` trajectory), `_rlnOpticsGroup`, `_rlnAccumMotionTotal / _rlnAccumMotionEarly / _rlnAccumMotionLate` (verified in fixture header).
- Per-micrograph aligned sums and trajectory STARs under `MotionCorr/jobNNN/Micrographs/`.
- `logfile.pdf` (+ `.eps` plots and histograms of `rlnAccumMotion*`) — view via `Display: out: logfile.pdf`.
- If `--grouping_for_ps` set: summed power-spectrum images for CTFFIND.
- `early/late` split in motion statistics is controlled by `--dose_motionstats_cutoff (4.)` e/Å².

### EER recipe (Falcon4), the bits people get wrong
From MovieCompression.rst:57–102:
1. Choose `--eer_grouping` = raw frames per fraction (e.g. 1000 raw / 30 → 33 usable fractions, last 10 dropped). Aim ~0.5–1.25 e/Å² per fraction.
2. Import EER with the **physical** pixel size for 4K (half-physical for 8K).
3. In motion-corr: set the dose **per fraction** (all GUI "frame" fields mean fractions, not raw frames; pipeline_jobs.cpp:1465), `--group_frames 1` **always**, and `--bin_factor 2` + `--eer_upsampling 2` if working in an 8K grid (Fourier-crop back to 4K). Default 4K = `--eer_upsampling 1`.
4. 8K rendering can create artefacts around defect lines (RELION 3.1.1 note, MovieCompression.rst:53) — 4K is the safe default.
- To change fractionation/rendering *before Polish*, post-process the trajectory STARs with `scripts/eer_trajectory_handler.py` (`--resample`, `--regroup`); it writes `corrected_micrographs_<tag>.star` to feed Polish (MovieCompression.rst:88–95).

---

## 3. CTF estimation (`relion_run_ctffind`)

Wraps Alexis Rohou & Niko Grigorieff's **CTFFIND-4.1** (and CTFFIND-5; see below). **Gctf support was dropped in RELION 5.0** (Preprocessing.rst:209) — the GUI CTF job now unconditionally emits `--is_ctffind4` and labels itself `.ctffind4` with no Gctf branch (pipeline_jobs.cpp:1822–1826). The CTFFIND4.1 path is preferred because it is open-source and can read the movie-averaged power spectra from RELION-own motion correction (Preprocessing.rst:207–208).

### Flags (from live `relion_run_ctffind --help`)

| Concern | flag (default) | meaning |
|---|---|---|
| Input | `--i` | `corrected_micrographs.star` (or wildcard `mics/*.mrc`) |
| Output dir | `--o (CtfEstimate/)` | |
| Use non-DW mics | `--use_noDW` | estimate from `rlnMicrographNameNoDW` (needs `--save_noDW` earlier) |
| Executable | `--ctffind_exe` (or `$RELION_CTFFIND_EXECUTABLE`) | path to `ctffind` |
| CTFFIND4 mode | `--is_ctffind4` | required for 4.1+; set automatically by GUI |
| FFT box | `--Box (512)` | |
| Resolution range | `--ResMin (100)` / `--ResMax (7)` | GUI defaults are 30 / 5 Å (pipeline_jobs.cpp:1734–1735) |
| Defocus search | `--dFMin (10000)` / `--dFMax (50000)` / `--FStep (250)` | GUI defaults 5000 / 50000 / 500 |
| Astigmatism | `--dAst (0)` | GUI default 100 Å |
| Pre-calc power spectra | `--use_given_ps` | use the PS written by motion-corr (required if you used float16) |
| Phase plate | `--do_phaseshift` + `--phase_min (0.)` / `--phase_max (180.)` / `--phase_step (10.)` | for example RELION host phase-plate data |
| Exhaustive search | (GUI "Use exhaustive search?" No) → `--fast_search` | `--fast_search` = disable slow exhaustive; omit it for difficult astig/phase fits |
| Window | `--ctfWin (-1)` | square window at centre; -1 = whole micrograph |
| Thon rings from movie | `--do_movie_thon_rings`, `--avg_movie_frames (1)`, `--movie_rootname (_movie.mrcs)` | legacy alternative to `--use_given_ps` |
| Threads (CTFFIND4) | `--j (1)` | |
| Microscope override | `--CS / --HT / --AmpCnst / --angpix` (all `-1` = take from STAR) | |
| Only join logs | `--only_make_star` | re-collect Final values without recomputing |
| Resume | `--only_do_unfinished` | only mics lacking a Final-values `.log` |

### CTFFIND-5

CTFFIND-5 (Gyobu/Rohou) adds tilt-aware fitting and ice-ring handling; in RELION 5.0 it is run through the **same wrapper** — you point `--ctffind_exe` at the CTFFIND-5 binary and keep `--is_ctffind4` (the "4" flag means "4.1-or-later command syntax", which CTFFIND-5 honours). (unverified: a dedicated `--is_ctffind5` flag — none exists in the live `relion_run_ctffind --help` on this install, and pipeline_jobs.cpp:1826 hard-codes `--is_ctffind4`; treat CTFFIND-5 as a drop-in executable.)

### Real-world command and the GUI 5.0 form
Fixture (`CtfFind/job003/note.txt`) used the **legacy Gctf path** (4.0-beta): `relion_run_ctffind ... --Box 512 --ResMin 30 --ResMax 5 --dFMin 5000 --dFMax 50000 --FStep 500 --dAst 100 --use_gctf --gctf_exe <GCTF_BIN> --ignore_ctffind_params`. **`--use_gctf` / `--gctf_exe` / `--ignore_ctffind_params` no longer exist in the 5.0 `relion_run_ctffind --help`** — this is exactly the kind of flag an old project carries that a 5.0 install will reject. The 5.0 CTFFIND equivalent (new output rootname):
```
relion_run_ctffind --i MotionCorr/job002/corrected_micrographs.star \
  --o CtfFind/job903/ --ctffind_exe /path/to/ctffind --is_ctffind4 \
  --Box 512 --ResMin 30 --ResMax 5 --dFMin 5000 --dFMax 50000 \
  --FStep 500 --dAst 100 --fast_search --use_given_ps
```
Run several MPI ranks (`relion_run_ctffind_mpi`, chosen automatically when MPI>1, pipeline_jobs.cpp:1773–1776) to process micrographs in parallel.

### Outputs
- `micrographs_ctf.star` — `data_micrographs` adds `_rlnCtfImage` (`...ctf:mrc`, the PS + fitted-model image), `_rlnDefocusU`, `_rlnDefocusV`, `_rlnCtfAstigmatism`, `_rlnDefocusAngle`, `_rlnCtfFigureOfMerit`, `_rlnCtfMaxResolution` (verified in fixture header). `_rlnPhaseShift` is added when `--do_phaseshift`.
- Per-micrograph `.ctf` (MRC PS+model), `.log` (CTFFIND stdout, holds the Final values), `.com` (launch script) under the output `Micrographs/` (or `Movies/`) subdir (Preprocessing.rst:264).
- `logfile.pdf` + `.eps` plots/histograms of `rlnDefocusU`, `rlnCtfAstigmatism`, `rlnCtfMaxResolution`, `rlnCtfFigureOfMerit`, `rlnDefocusAngle` (verified: fixture has `micrographs_ctf_all_*.eps` and `micrographs_ctf_hist_*.eps` for each).

### Reading a good vs bad CTF fit
- **Good:** the zeros (dark rings) between experimental Thon rings coincide with the model's rings out to a high spatial frequency; `rlnCtfMaxResolution` is low (≈ your target resolution or better — the fixture sits ~2.85–3.6 Å), `rlnCtfFigureOfMerit` is high. Sort the `Display: out: micrographs_ctf.star` montage by max-res / FoM / defocus to triage (Preprocessing.rst:266–268).
- **Bad:** Thon rings fade quickly (high `rlnCtfMaxResolution`, e.g. > ~6–8 Å), model rings drift out of register, FoM low, or astigmatism implausibly large. Delete that micrograph's `.log`, adjust parameters, and **Continue!** — only mics without a `.log` are re-processed (`--only_do_unfinished`; Preprocessing.rst:272–273). Persistent failures → cull with a `Subset selection` job.

---

## 4. Gain reference handling (the single biggest preprocessing footgun)

- **Orientation:** K2/K3 gains routinely need rotation/flip to match the movie. The fixture K3 gain needed `--gain_rot 2 --gain_flip 2`. Wrong orientation does **not** error — it produces micrographs with streaks/lattice artefacts and dead motion correction. If your aligned sums look striped or motion is absurd, sweep `--gain_rot {0,1,2,3}` × `--gain_flip {0,1,2}` on a few movies.
- **Multiply vs divide (EER is special):** for MRC/TIFF gains from K2/K3 (`.gain` TIFF), RELION **multiplies** raw pixels by the gain. **For EER movies with an MRC gain, RELION divides** raw values by the gain (historical convention); a `.gain`-extension TIFF gain with EER multiplies like K2/K3 (MovieCompression.rst:97–99). If you convert EER→TIFF with `relion_convert_to_tiff`, you must invert the EER gain first — the tool does this when you pass it via `--gain` (MovieCompression.rst:109–110). A zero-valued gain pixel is treated as defective.
- **Gain size for EER:** 8K or 4K gains are auto up/down-sampled to match `--eer_upsampling` (MovieCompression.rst:101–102).
- **Defects:** SerialEM-format defect *text* files are NOT supported directly; convert to a defect map with IMOD `clip defect` (pipeline_jobs.cpp:1495; Preprocessing.rst:168).

---

## 5. Common failures / red flags

| Symptom | Likely cause | Fix |
|---|---|---|
| `relion_run_motioncorr` exits "You have to choose either UCSF MotionCor2 or RELION's own implementation" | neither `--use_own` nor `--use_motioncor2` given (also what you hit if you run `--help` bare; motioncorr_runner.cpp:141) | add `--use_own` (or `--use_motioncor2 --motioncor2_exe`) |
| Striped / lattice-artefact micrographs, wild motion tracks | **wrong gain orientation** | sweep `--gain_rot` / `--gain_flip` on a few movies; confirm gain matches detector |
| EER job too slow / OOM, or wrong dose-weighting | EER **fraction count vs raw-frame** confusion | `--eer_grouping` = *raw frames per fraction* (e.g. 30, not the resulting 33); aim 0.5–1.25 e/Å²/fraction; dose is **per fraction**; `--group_frames 1` |
| float16 motion-corr refuses to run | `--float16` without power spectra | also pass `--grouping_for_ps` (GUI "Save sum of power spectra") — enforced at pipeline_jobs.cpp:1565–1573 |
| Old project: CTF job dies on unknown flag | `--use_gctf`/`--gctf_exe`/`--ignore_ctffind_params` from a ≤4.0 project | Gctf removed in 5.0; rebuild the job as CTFFIND-4.1/5 (re-run the CTF GUI job) |
| Particles wrong scale / box, CTF off by 2× | **pixel-size mismatch**: imported `--angpix` is super-res but you treated motion-corr output as super-res (or vice-versa) | the optics block carries BOTH `_rlnMicrographOriginalPixelSize` (0.53) and post-bin `_rlnMicrographPixelSize` (1.06); always read the binned value downstream |
| Float16 mics unreadable by Gctf/other tools | float16 (MRC mode 12) | RELION/CCPEM read it; for CTF use CTFFIND-4.1 with `--use_given_ps` (Preprocessing.rst:125) |
| Compressed MRC movie won't read | missing decompressor | put `pbzip2`/`xz`/`zstd` on PATH (MovieCompression.rst:347); note tomo + image_handler don't support compressed MRC |
| EPU reports ~1/7 the real EER frame count | old EPU bug | verify true frame count via `relion_convert_to_tiff` ("Found X raw frames"; MovieCompression.rst:113–115) |

---

## 6. Version notes
- **3.1** introduced optics groups (`data_optics`, `_rlnOpticsGroup`) and EER reading (≥3.1.1) — older `.star` files without an optics block are auto-upgraded on read.
- **4.0** added VDAM, Schemes, the class-ranker, and the tomo rewrite; compressed-MRC movie reading is 4.0.1+.
- **5.0** dropped Gctf (CTFFIND only), introduced Blush regularisation, DynaMight, ModelAngelo, AMD/Intel-GPU acceleration, and ships Topaz in the relion-5 conda env. The validation fixture is a **4.0-beta project read by this 5.0 install** — its `--use_gctf` CTF job and missing `_rlnMicrographPixelSize`-only quirks are normal for an older project; re-running any preprocessing job through the 5.0 GUI regenerates 5.0-correct commands.

---

## Cross-links
- `01_star_and_metadata.md` — `data_optics` block, `_rlnMicrograph*` / `_rlnCtf*` label definitions.
- `02_project_job_tree.md` — job.star / note.txt / `RELION_JOB_EXIT_*` sentinels, default_pipeline.star.
- `03_cli_inventory.md` — full `relion_*` binary list and which GUI job calls which binary.
- `05_picking_extraction.md` — consumes `micrographs_ctf.star`; gain/box conventions for extraction.
- `10_ctfrefine_polish.md` — per-particle CTF refinement and Bayesian Polish (needs RELION-own motion tracks + trajectory STARs).
- `12_conventions_symmetry.md` — pixel size, dose, optics-group conventions.
- `20_troubleshooting.md` / `21_error_lookup.md` — broader failure catalogue.
- Sibling skill `cryosparc` owns the equivalent CryoSPARC import/patch-motion/CTF jobs; `16_interop_cryosparc.md` covers handoff.

---

## Sources
Read:
- `cli/.../help/relion_import.txt`
- `cli/.../help/relion_run_motioncorr.txt`, `cli/.../help/relion_run_ctffind.txt`
- `source/relion-documents_release-5.0/source/SPA_tutorial/Preprocessing.rst`
- `source/relion-documents_release-5.0/source/Reference/MovieCompression.rst`
- `source/relion_ver5.0/src/pipeline_jobs.cpp` (getCommandsImportJob 1270–1449; initialise/getCommandsMotioncorrJob 1451–1605; initialise/getCommandsCtffindJob 1696–1844)
- Fixture (READ-ONLY): `Import/job001/{note.txt,movies.star}`, `MotionCorr/job002/{note.txt,corrected_micrographs.star}`, `CtfFind/job003/{note.txt,micrographs_ctf.star}` at `<RELION_PROJECT_FIXTURE>`

Ran live on example RELION host (RELION 5.0.0-commit-3d6c20):
- `relion_import --help`
- `relion_run_motioncorr --use_own --help`
- `relion_run_ctffind --help`
