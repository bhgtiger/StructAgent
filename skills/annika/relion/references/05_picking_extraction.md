# 05 — Picking (LoG/template/Topaz/manual) and extraction

## Scope
Particle picking in RELION 5.0 — `relion_autopick` (Laplacian-of-Gaussian, 2D/3D reference template-matching, Topaz wrapper, helical) and `relion_manualpick` — and particle extraction with `relion_preprocess(_mpi)` (box size, rescale/downsample and the pixel-size bookkeeping it triggers, background normalisation, contrast inversion, re-extraction/recentering from a refined `_data.star`, helical tube extraction). Grounded in the live RELION 5.0.0-commit-3d6c20 binaries on the example RELION host server, the GUI command-builders in `pipeline_jobs.cpp`, the SPA tutorial, and the read-only NeCen/PRC1 fixture (a 4.0-beta project, picked via imported coordinates).

---

## 1. AutoPick — one job-type, three mutually-exclusive methods

The GUI Auto-picking job runs `relion_autopick` (or `relion_autopick_mpi` when nr_mpi>1). On the I/O tab you must select **exactly one** of: reference-based template-matching, Laplacian-of-Gaussian, or Topaz. The builder enforces this — `pipeline_jobs.cpp:2162` errors with `"ERROR: On the I/O tab specify (only) one of three methods: template-matching, LoG or topaz ..."` if zero or >1 are chosen.

Common I/O flags (all methods):

| Flag | Default | Meaning |
|---|---|---|
| `--i` | (required) | Micrograph STAR file (e.g. `CtfFind/job003/micrographs_ctf.star`) OR a wildcard like `"Micrographs/*.mrc"` |
| `--odir` | `AutoPick/` | Output directory for coordinate files |
| `--pickname` | `autopick` | Rootname for per-micrograph coordinate STARs; GUI always passes `autopick` |
| `--angpix` | `1` | Micrograph pixel size (A); GUI passes only when the I/O "pixel size" field is >0, otherwise read from the STAR optics block |
| `--gpu` | false | GPU acceleration (template-matching and Topaz only; **not** LoG — see below) |
| `--only_do_unfinished` | false | On Continue, skip micrographs whose coordinate file already exists |

**Output node:** the job writes `AutoPick/jobNNN/autopick.star` — a 2-column list of micrograph names and their coordinate files (node label `LABEL_AUTOPICK_COORDS`, `pipeline_jobs.cpp:2075,2183`). Per-micrograph picks go next to/under the micrographs as `<micrograph>_autopick.star`. Since 4.0 RELION no longer writes a `coords_suffix` node; the `autopick.star` 2-column list is what you feed to extraction. A `logfile.pdf` (eigenvalue/FOM histograms) is also produced for LoG and reference picking (`pipeline_jobs.cpp:2187`).

### 1a. Laplacian-of-Gaussian (LoG) — template-free, fast, CPU-only

Best first pass when you have no template. The GUI builds (`pipeline_jobs.cpp:2273-2294`):

```
relion_autopick --i Select/job005/micrographs_split1.star --odir AutoPick/jobNNN/ \
  --pickname autopick --LoG --LoG_diam_min 150 --LoG_diam_max 180 \
  --shrink 0 --lowpass 20 --LoG_adjust_threshold 0 --LoG_upper_threshold 5
```

| GUI field | Flag | Notes |
|---|---|---|
| Min diameter (A) | `--LoG_diam_min` | Smallest particle projection size; tutorial uses 150 |
| Max diameter (A) | `--LoG_diam_max` | Largest projection size; tutorial uses 180 |
| Maximum resolution | `--lowpass` | GUI also forces `--shrink 0`; tutorial 20 A |
| Adjust default threshold | `--LoG_adjust_threshold` | Default 0. Positive ⇒ fewer picks, negative ⇒ more (moves threshold this many σ). Useful range roughly [-1,1] |
| Upper threshold | `--LoG_upper_threshold` | Default 99999 (disabled). GUI passes it only when the field is < 999. Discards high-LoG ice/ethane contamination; for low-contrast micrographs ~1.5 may be reasonable, but that is too low for high-contrast data |
| Are particles white? | `--Log_invert` | Add when particles are white-on-black |

LoG flags not exposed by the simple GUI workflow but available on the binary: `--LoG_neighbour` (100; avoid neighbours within (detected+min diameter)×this%), `--LoG_use_ctf`, `--Log_max_search` (5; multi-scale span). **GPU is not supported for LoG** — the builder errors with `"ERROR: The Laplacian-of-Gaussian picker does not support GPU."` (`pipeline_jobs.cpp:2277`).

### 1b. Reference-based template matching (2D class averages or a 3D map)

Use 2D class averages (from a 2D classification of the LoG/Topaz set) or a 3D reference. The builder (`pipeline_jobs.cpp:2295-2394`):

| GUI field | Flag | Default | Notes |
|---|---|---|---|
| 2D references (MRC stack/STAR) | `--ref <refs.star or .mrcs>` | — | `.ref2d` job label |
| 3D reference (map) | `--ref <map.mrc> --sym <pg> --healpix_order N` | — | `.ref3d` label. Sampling: hp0=60°, hp1=30°, hp2=15° (`--healpix_order` from `--help`) |
| References on inverted contrast | `--invert` | false | Density in micrograph inverted w.r.t. template |
| Pixel size of references | `--angpix_ref` | -1 (=micrograph angpix) | Passed only when >0 |
| Angular sampling (in-plane) | `--ang` | 10 | Degrees; 360 = no in-plane rotation search |
| CTF-correct references | `--ctf` (+`--ctf_intact_first_peak`) | false | |
| Lowpass references (A) | `--lowpass` | -1 | **Set this** to prevent Einstein-from-noise (e.g. 20 A) |
| Highpass micrographs (A) | `--highpass` | -1 | |
| Picking threshold | `--threshold` | 0.25 | Fraction of expected probability ratio to keep a peak |
| Min inter-particle distance (A) | `--min_distance` | -1 (= half box) | For helical it is set to `nr_asu × rise` instead |
| Max stddev noise | `--max_stddev_noise` | -1 (none) | Reject peaks in too-noisy areas |
| Min avg noise | `--min_avg_noise` | -999 (none) | Passed only when > -900 |
| Shrink factor | `--shrink` | 1.0 | Reduce micrograph to this fraction during correlation (saves memory/time). Note: a source comment (`pipeline_jobs.cpp:2392`) says GPU runs "always use `--shrink 0`", but the command builder does **not** force it — the `--shrink` value comes from this job-option whether or not `--gpu` is set; set Shrink=0 yourself for GPU runs if you want that behavior |

3D-reference picking projects the map at `--healpix_order` over the point group `--sym`. Blob-picking with a Gaussian (`--ref gauss --gauss_max 0.1`) also exists on the binary.

**FOM maps for tuning:** `--write_fom_maps` then `--read_fom_maps` lets you re-pick at different thresholds without recomputing cross-correlations (capped at 30 maps unless `--no_fom_limit`). Reference and LoG picking both honour these (`pipeline_jobs.cpp:2402-2406`).

### 1c. Topaz wrapper (neural-net picking; integrated since RELION 4.0)

The Auto-picking job wraps Topaz via `relion_python_topaz` (default `--fn_topaz_exe relion_python_topaz`, a conda install). On the Topaz tab choose exactly one of train / pick (`pipeline_jobs.cpp:2204` errors otherwise). Topaz requires a GPU for training (builder errors at `pipeline_jobs.cpp:2219` if no GPU is selected); picking GPU is optional.

**Train** (single MPI process only — training is not parallelised across ranks):
```
relion_autopick --fn_topaz_exe relion_python_topaz --i Select/job005/micrographs_split1.star \
  --odir AutoPick/jobNNN/ --pickname autopick --particle_diameter 180 \
  --topaz_train --topaz_nr_particles 300 --topaz_train_parts Select/job009/particles.star --gpu "0"
```
Train on coordinates (`--topaz_train_picks <name>`) or on a particle STAR (`--topaz_train_parts <particles.star>`); the GUI uses one or the other. Training writes a model under the job dir, e.g. `AutoPick/jobNNN/model_epoch10.sav`. When training, RELION does **not** register an `autopick.star` output (`pipeline_jobs.cpp:2179`) — that node only appears for picking.

**Pick / extract** (parallelisable over MPI):
```
relion_autopick --fn_topaz_exe relion_python_topaz --i CtfFind/job003/micrographs_ctf.star \
  --odir AutoPick/jobNNN/ --pickname autopick --particle_diameter 180 \
  --topaz_extract --topaz_model AutoPick/job010/model_epoch10.sav --gpu "0"
```
Leave `--topaz_model` empty to use Topaz's general pretrained network. Default Topaz picking applies no FOM threshold, so it returns many picks; the per-pick figure of merit lands in `rlnAutopickFigureOfMerit`, and a minimum of ~ -3 is reasonable to apply later at extraction (tutorial). Other Topaz knobs from `--help`: `--topaz_nr_particles` (200), `--topaz_threshold` (-6), `--topaz_downscale` (-1), `--topaz_radius`, `--topaz_test_ratio` (0.2), `--topaz_workers`, `--topaz_args "..."` (passed through verbatim). Version note: Topaz integration is **4.0+**; pre-4.0 used reference-based picking from 2D templates.

### 1d. Helical picking

Reference-based picking gains `--helix` (and `--amyloid` for amyloid; amyloid-specific algorithm matured in **5.1**) plus `--helical_tube_outer_diameter`, `--helical_tube_kappa_max` (0.25; max curvature relative to a circle), `--helical_tube_length_min` (`pipeline_jobs.cpp:2379-2387`). For helical, `--min_distance` is set to `nr_asu × rise`, not the box-based default. See `13_helical_amyloid.md`.

---

## 2. Manual picking

`relion_manualpick` is a GUI/FLTK tool (needs `libfltk.so.1.3` — note the captured `relion_manualpick --help` on example RELION host fails to load that shared library, so confirm flags from source rather than `--help` on this box). The builder (`pipeline_jobs.cpp:1879-1971`):

```
relion_manualpick --i CtfFind/job003/micrographs_ctf.star --odir ManualPick/jobNNN/ \
  --pickname manualpick --allow_save --fast_save --selection ManualPick/jobNNN/micrographs_selected.star \
  --scale <micscale> --sigma_contrast <s> --black <b> --white <w> --particle_diameter <d>
```

- Per-micrograph picks are saved as `<micrograph>_manualpick.star`; the 2-column list output is `ManualPick/jobNNN/manualpick.star` (node `LABEL_MANPICK_COORDS`; `LABEL_MANPICK_COORDS_HELIX` when `--pick_start_end` is used for helical start/end coordinates).
- `--selection micrographs_selected.star` doubles as a micrograph-subset selector — you can use the Manual picking GUI just to tick which micrographs to keep (the tutorial mentions saving `micrographs_selected.star` for Topaz training subsets).
- Display/colour options: `--color_label rlnAutopickFigureOfMerit --blue 5 --red -3 [--color_star ...]` colour existing picks by any metadata label (blue=high FOM, red=low), which is the standard way to choose a Topaz FOM cutoff visually. `--lowpass`/`--highpass`/`--angpix` filter the displayed micrograph; `--topaz_denoise` denoises the display.
- Re-launching an Auto-pick job in "continue/manual" mode runs `relion_manualpick` on the autopicked coords with `--pickname autopick` to add/delete picks (`pipeline_jobs.cpp:2060-2146`).

---

## 3. Coordinate STAR file format

A bare picked-coordinates STAR (one per micrograph, or the imported coords in the fixture) is a single `data_` block with at minimum:

```
data_
loop_
_rlnMicrographName #1
_rlnCoordinateX #2
_rlnCoordinateY #3
FoilHole_..._fractions.mrc 3196 3924
FoilHole_..._fractions.mrc 4024 1644
```

(Real example from the fixture's imported coordinates — `Import/job015/Micrographs/*.star`.) Autopick coordinate files additionally carry `_rlnAutopickFigureOfMerit` (and class/psi for templates). Coordinates are in **micrograph pixels** at the micrograph's own pixel size — not Angstroms, not the extracted-particle pixel size. The 2-column dispatch file (`autopick.star` / `manualpick.star` / `extractpick.star`) lists `_rlnMicrographName` + `_rlnMicrographCoordinates` so extraction knows which coord file pairs with which micrograph.

---

## 4. Particle extraction — `relion_preprocess(_mpi)`

The Extract job (`relion.extract` / `relion.extract.reextract` / `relion.extract.helical`) runs `relion_preprocess_mpi` (or `relion_preprocess` for nr_mpi=1). Two input modes, mutually exclusive in the builder:

**(A) Fresh extraction from coordinates** — `--coord_suffix`/`--coord_dir` (or `--coord_list`). Real fixture command (`Extract/job016/note.txt`):
```
relion_preprocess_mpi --i CtfFind/job003/micrographs_ctf.star \
  --coord_dir Import/job015/ --coord_suffix .star \
  --part_star Extract/job016/particles.star --part_dir Extract/job016/ \
  --extract --extract_size 220 --float16 --scale 60 \
  --norm --bg_radius 22 --white_dust -1 --black_dust -1 --invert_contrast
```

**(B) Re-extraction from a refined `_data.star`** — `--reextract_data_star`. Real fixture command (`Extract/job036/note.txt`):
```
relion_preprocess_mpi --i CtfFind/job003/micrographs_ctf.star \
  --reextract_data_star Select/job035/particles.star \
  --part_star Extract/job036/particles.star --pick_star Extract/job036/extractpick.star \
  --part_dir Extract/job036/ --extract --extract_size 220 --float16 \
  --norm --bg_radius 82 --white_dust -1 --black_dust -1 --invert_contrast
```

Core extraction flags:

| GUI field | Flag | Default | Notes |
|---|---|---|---|
| micrograph STAR | `--i` | (required) | Must be the **same** micrograph set the coordinates were picked on (see failures) |
| Input coordinates | `--coord_suffix` + `--coord_dir` | — | Or `--coord_list <2-col.star>`. Builder splits a `coords_suffix*.star` path into dir+suffix (`pipeline_jobs.cpp:2533-2536`) |
| Particle box size (pix) | `--extract_size` | -1 | **Must be even.** In original (pre-rescale) micrograph pixels |
| Output particle STAR | `--part_star` | — | e.g. `Extract/jobNNN/particles.star` |
| Output stack dir | `--part_dir` | `Particles/` | `.mrcs` stacks written under here, mirroring micrograph subdirs |
| Write float16? | `--float16` | false | MRC mode 12, half the disk of mode-0 float32. RELION/CCPEM read it; some external tools may not |
| Use FOM threshold | `--minimum_pick_fom` | -999 | Only extract picks with `rlnAutopickFigureOfMerit` ≥ this (e.g. -3 for Topaz) |

Particle operations:

| GUI field | Flag | Notes |
|---|---|---|
| Rescale particles | `--scale <pix>` | Down/up-scale the box to this many pixels (Fourier crop/pad). Speeds up early classification |
| Re-window | `--window <pix>` | Real-space re-window to this size (distinct from rescale) |
| Normalize | `--norm` | Background → mean 0, stddev 1 |
| (subtract mean only) | `--no_ramp` | Subtract background mean instead of a fitted ramp |
| Background diameter (pix) | `--bg_radius <pix>` | Radius (pixels) of the circle outside which is "background". GUI input is a *diameter*; see bookkeeping below |
| White / black dust | `--white_dust` / `--black_dust` | σ cutoff for outlier-pixel removal; -1 = off. Use ~5 only if you actually see hot/dead pixels |
| Invert contrast | `--invert_contrast` | Makes particles white-on-black, RELION's convention |

**Output:** `particles.star` (a 3.1+ optics-grouped STAR: `data_optics` + `data_particles`) plus `.mrcs` stacks. Each particle's `_rlnImageName` is `NNNNNN@Extract/jobNNN/.../mic.mrcs`, with `_rlnMicrographName`, `_rlnCoordinateX/Y`, `_rlnOpticsGroup` and the CTF columns copied from the micrograph STAR.

### 4a. The rescale → pixel-size bookkeeping (do not get this wrong)

When you `--scale`, RELION updates the optics block so the recorded image pixel size matches the new box, and adjusts the background radius automatically. From the fixture:

- **job016**: `--extract_size 220`, `--scale 60`. Original micrograph pixel size is **1.06 A/pix** (2× binned super-res; `rlnMicrographOriginalPixelSize 0.53`). After scaling 220→60, the run log states *"The pixel size of the extracted particles in optics group 1 is 3.88667 Angstrom/pixel"* and `particles.star` records `_rlnImagePixelSize 3.886667`, `_rlnImageSize 60`. Check: 1.06 × 220/60 = 3.8867 A/pix. ✓
- **job036**: re-extraction at `--extract_size 220`, **no** `--scale` → `_rlnImagePixelSize 1.060000`, `_rlnImageSize 220`. ✓

So the bookkeeping is `new_angpix = orig_angpix × extract_size / scale`. The optics block (`_rlnImagePixelSize`, `_rlnImageSize`) is the single source of truth downstream; `_rlnMicrographOriginalPixelSize` (0.53) and `_rlnMicrographPixelSize` are unchanged.

**Background radius auto-scaling:** the GUI takes the *diameter* you type (or 0.75×box when you leave it at -1), halves it to a radius, and **rescales it by `scale/extract_size`** so the background circle stays in the same physical place after downscaling (`pipeline_jobs.cpp:2584-2601`). Worked from job016: default diameter = 0.75×220 = 165 → radius 82.5 → ×60/220 = 22.5 → int → **`--bg_radius 22`** (matches note.txt). job036 (no rescale): 0.75×220=165 → 82.5 → int → **`--bg_radius 82`** (matches). If you call `relion_preprocess` by hand you must do this halving+scaling yourself; the GUI does it for you.

### 4b. Re-extraction, recentering, and resetting offsets (after 2D/3D)

`--reextract_data_star <run_data.star>` re-extracts exactly the particles surviving in a refinement, e.g. to go from a downscaled box back to full scale, or to recenter after a 3D refinement:

| GUI field | Flag | Effect |
|---|---|---|
| Re-extract refined particles | `--reextract_data_star` | Source of coordinates + (optionally) offsets |
| Reset offsets to zero | `--reset_offsets` | Zero the `rlnOrigin*` from the input; do **not** apply alignment shifts |
| Re-center refined coordinates | `--recenter` (+`--recenter_x/y/z`) | Shift each particle's X/Y by its refined origin so a new reconstruction is centered on the given (x,y,z) reference voxel. Useful for focused/local refinement |
| Reference pixel size | `--ref_angpix` | Pixel size of the reference used for recentering (-1 = particle pixel size) |

`--reset_offsets` and `--recenter` are mutually exclusive (builder errors at `pipeline_jobs.cpp:2503`). Re-extraction writes both `particles.star` and an `extractpick.star` (`--pick_star`, node `LABEL_EXTRACT_COORDS_REEX`). When you re-extract at full scale, remember to **drop `--scale`** (and let `--extract_size` set the new, larger box) — the pixel-size bookkeeping above then resolves to the original micrograph pixel size.

### 4c. Helical extraction

`relion.extract.helical` adds `--helix --helical_outer_diameter <A>`, and for tube coordinates `--helical_tubes` + `--helical_cut_into_segments --helical_nr_asu <N> --helical_rise <A>` to cut tubes into overlapping segments; `--helical_bimodal_angular_priors` adds bimodal psi priors (`pipeline_jobs.cpp:2608-2632`). Note the fixture's Extract job.star carries helical defaults (`do_extract_helix No`, `helical_tube_outer_diameter 200`) even though this is a single-particle nucleosome project — those joboptions exist in every Extract job and are simply inactive when `do_extract_helix=No`. See `13_helical_amyloid.md`.

---

## 5. Common failures / red flags

- **Box too small ⇒ delocalised CTF clipped.** At high defocus the CTF delocalises signal far from the particle centre; if `--extract_size` is too tight you crop that signal and cap attainable resolution. Rule of thumb: box ≳ particle diameter + a generous margin (often 1.5–2× the particle), even larger at high defocus. You can re-extract larger later (4b) without re-picking.
- **Wrong rescale pixel-size bookkeeping.** Calling `relion_preprocess` by hand with `--scale` but forgetting that the GUI also rescales `--bg_radius` (4a) gives a background circle in the wrong place and skewed normalisation. Always verify `_rlnImagePixelSize`/`_rlnImageSize` in the output `particles.star` equal `orig_angpix × extract_size / scale` and the new box. A particle pixel size that doesn't match this product is the tell-tale of a bookkeeping mistake (and breaks every downstream `--angpix`-sensitive step and any cryoSPARC/cryoDRGN import).
- **Coordinates from a different micrograph set.** Extraction silently warns, e.g. `Warning: coordinate file Import/job015/Micrographs/<mic>.star does not exist...` (real fixture `.run.err.tail`) — that means the micrograph STAR (`--i`) and the coordinates were not produced from the same micrographs (renamed, re-imported, or a different MotionCorr/CtfFind job). Particles silently go missing. Pixel-size mismatch between picking micrographs and extraction micrographs is the same class of bug and shifts every coordinate. Pick and extract from the **same** CtfFind output.
- **`Warning: There are only N particles in micrograph ... Consider joining multiple micrographs into one group.`** (real fixture) — sparse micrographs make per-micrograph noise/scale estimation unstable in later classification/refinement; use Subset selection "Regroup the particles" rather than ignoring it.
- **`WARNING: no particles on micrograph: ...`** during re-extraction (real fixture job036) is expected when refinement/2D selection removed all of a micrograph's particles — not an error.
- **Einstein-from-noise with templates.** Skipping `--lowpass` on references (or using a too-high threshold with self-generated 2D classes) can pick noise that matches the template. Always lowpass references (~20 A) and sanity-check 2D classes of the picks.
- **LoG + GPU.** Selecting GPU with the LoG picker aborts before running (`"...does not support GPU."`). Only template-matching and Topaz use the GPU. With 2× RTX 2080 Ti (11 GB) on example RELION host, template/Topaz picking fits comfortably; LoG is CPU and fast regardless.
- **Topaz training under MPI.** Topaz training is not rank-parallelised — run training with a single MPI process (picking can use multiple). This mirrors the fixture's Polish/job040–041 failure pattern (`"Parameter estimation is not supported in MPI mode"`) for other train/estimate steps: training/estimation steps in RELION generally want a single rank.

---

## Cross-links

- `04_preprocessing.md` — MotionCorr + CtfFind that produce `micrographs_ctf.star` (the `--i` for picking/extraction) and the optics/pixel-size provenance.
- `01_star_and_metadata.md` — optics-group STAR layout, `_rlnImagePixelSize`/`_rlnImageSize`, `rlnCoordinateX/Y`, `rlnAutopickFigureOfMerit` columns.
- `06_class2d_select.md` — 2D classification to make templates and Subset selection (auto class-ranker, regrouping) used between LoG/Topaz picking and Topaz re-training.
- `13_helical_amyloid.md` — helical tube/segment picking and extraction, amyloid (5.1).
- `02_project_job_tree.md` — job-type labels (`relion.autopick.*`, `relion.extract.*`, `relion.manualpick.*`), node labels, `note.txt`/`job.star` conventions.
- `19_interop_coordinates.md` and `16_interop_cryosparc.md` — importing/exporting coordinates between RELION and cryoSPARC; pixel-size matching at extraction is the critical handoff.
- `cryolo` skill — crYOLO picking (external picker; coordinates imported back into RELION). `cryosparc` skill owns cryoSPARC-side picking/extraction.

---

## Sources

Read for this file:
- Live binaries (run on example RELION host, RELION 5.0.0-commit-3d6c20): `relion_autopick --help`, `relion_preprocess --help`.
- Captured help: `references/cli/relion5_cli_capture_20260604/help/relion_autopick.txt`, `relion_preprocess.txt`, `relion_manualpick.txt` (the latter records the live `libfltk.so.1.3` load failure on example RELION host).
- Source: `references/source/relion_ver5.0/src/pipeline_jobs.cpp` — `getCommandsManualpickJob` (1879–1971), `getCommandsAutopickJob` (2053–2424), `getCommandsExtractJob` (2471–2650), and node-label/coords-suffix lines (1363, 2075, 2183, 2533–2564).
- Docs: `references/source/relion-documents_release-5.0/source/SPA_tutorial/Autopicking.rst` (LoG/Topaz workflow, extraction defaults, box 256/rescale 64, FOM threshold).
- Read-only fixture `<RELION_PROJECT_FIXTURE>`: `Extract/job016` and `Extract/job036` (`note.txt`, `job.star`, `particles.star` optics blocks, `.run.err.tail`, `.run.out.tail`), `Import/job015` (`note.txt`, `coords_suffix.star`, imported coordinate STAR sample).
