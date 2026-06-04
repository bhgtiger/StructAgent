# 13 — Helical / filament / amyloid processing

## Scope
Helical single-particle reconstruction in RELION 5.0: the He & Scheres (2017) workflow that adds helical tabs to Auto-picking, Particle extraction, 2D/3D classification, 3D auto-refine, Polish and Mask-create; start-end (tube) picking and Topaz filament picking; helical segment extraction (inter-box distance from rise × asu); 2D classification of segments; `relion_helix_inimodel2d` for a 2D-cross-over initial 3D; 3D helical auto-refine flags (`--helix`, twist/rise initial/min/max/inistep, local symmetry search, `--helical_z_percentage`, inner/outer diameter, `--helical_nr_asu`, symmetry on/off, tilt-prior, angular ranges); `relion_helix_toolbox` and `relion_helix_vote_classes` utilities; and the amyloid branch (single asymmetric rise, low/no point-group symmetry, cross-beta 4.75 Å rung, `--amyloid` picker, RELION 5.1 amyloid additions). The fixture `<RELION_PROJECT_FIXTURE>` is a globular nucleosome (not helical), so command lines below use NEW output rootnames and are illustrative, not fixture-replays.

---

## 1. The helical workflow at a glance

Shaoda He implemented helical processing as extra tabs inside the normal SPA job types — there is no separate "helical pipeline", only helical *options* added to existing jobs (`Reference/Helix.rst` lines 4-9). The job-type label gets a `.helical` suffix when helical options are on (e.g. `relion.refine3d.helical`; `pipeline_jobs.cpp` adds `label += ".helical"` in autopick/extract/class2d/class3d/refine3d).

| Stage | Job type | Helical toggle (joboption) | Sibling ref |
|---|---|---|---|
| Pick filaments (start-end or auto) | Auto-picking | `do_pick_helical_segments` (or Topaz `do_topaz_filaments`) | 05_picking_extraction.md |
| Extract segments | Particle extraction | `do_extract_helix` | 05_picking_extraction.md |
| 2D classify segments | 2D classification | `do_helix` | 06_class2d_select.md |
| Bi-hierarchical filament cleanup | Subset selection (FilamentTools) | "Filament" tab = Yes | 06_class2d_select.md |
| Initial 3D from 2D cross-over | command-line `relion_helix_inimodel2d` | (no GUI job) | 07_initialmodel_class3d.md |
| 3D classify segments | 3D classification | `do_helix` | 07_initialmodel_class3d.md |
| 3D auto-refine | 3D auto-refine | `do_helix` | 08_refine3d.md |
| Symmetry vote / class grouping | command-line `relion_helix_vote_classes` | (no GUI job) | — |
| Symmetry tools | command-line `relion_helix_toolbox` | (no GUI job) | 03_cli_inventory.md |

Version note: helical support has existed since RELION 2/3; `relion_helix_inimodel2d` is a 3.1 addition (`Whats-new.rst` line 122). FilamentTools (bi-hierarchical filament/2D classification) is a RELION-5 Subset-selection feature (`FilamentTools.rst` line 9). Amyloid-specific algorithm additions continue into 5.1 (see §7).

---

## 2. Picking filaments

### 2a. Start-end (manual tube) coordinates
Filaments are picked as two-point tube coordinates (start and end of each straight tube). The Particle-extraction job then cuts each tube into evenly spaced segment boxes. The "Coordinates are start-end only?" toggle is `do_extract_helical_tubes` (default Yes; `pipeline_jobs.cpp:2461`), which adds `--helical_tubes` to `relion_preprocess`.

### 2b. Reference-based auto-pick (He & Scheres 2017)
`do_pick_helical_segments` = Yes runs the classic reference-based segment picker (`pipeline_jobs.cpp:2038`), adding to `relion_autopick`:

```
--helix --helical_tube_outer_diameter <A> --helical_tube_kappa_max <k> --helical_tube_length_min <A>
```
(verified live: `relion_autopick --help` → `--helix`, `--helical_tube_outer_diameter`, `--helical_tube_kappa_max` (default 0.25), `--helical_tube_length_min`). `kappa_max` caps tube curvature relative to a circle; `tube_length_min` rejects short broken pieces.

The inter-box `--min_distance` for the picker is computed as `helical_nr_asu × helical_rise` (Angstroms), not the generic min-distance (`pipeline_jobs.cpp:2367-2368`).

### 2c. Topaz filament picking (RELION 4/5)
The modern default for many users is Topaz-based filament picking from the Topaz tab (the `do_pick_helical_segments` tooltip at `pipeline_jobs.cpp:2038` says "Often, we now run filament picking from the Topaz tab instead"). `do_topaz_filaments` = Yes adds to the Topaz extract command (`pipeline_jobs.cpp:2251-2258`):
```
--helix --topaz_threshold <t> [--helical_tube_length_min <A>]
```

### 2d. Amyloid picker
The `--amyloid` flag activates a dedicated amyloid picking algorithm in `relion_autopick` (verified live: `--amyloid (false) : Activate specific algorithm for amyloid picking?`). In the GUI it is the `do_amyloid` joboption, appended right after `--helix` (`pipeline_jobs.cpp:2380-2381`).

Helical metadata labels written by picking/extraction (from `metadata_label.h`): `rlnHelicalTubeID`, `rlnHelicalTrackLength` / `rlnHelicalTrackLengthAngst`, `rlnHelicalTubePitch` (cross-over distance, Å), plus the bimodal priors `rlnAnglePsiPrior` and `rlnAngleTiltPrior`. See 01_star_and_metadata.md.

---

## 3. Extracting helical segments

`do_extract_helix` = Yes (`pipeline_jobs.cpp:2456`) adds to `relion_preprocess` (verified live `relion_preprocess --help`, "Helix extraction" block):

```
--helix --helical_outer_diameter <A> [--helical_bimodal_angular_priors] \
        [--helical_tubes] [--helical_cut_into_segments --helical_nr_asu <N> --helical_rise <A>]
```

Key joboptions and conventions (`pipeline_jobs.cpp:2457-2467`, command at 2616-2630):
- **Tube diameter (`helical_tube_outer_diameter`, default 200 Å)** → `--helical_outer_diameter`. "Should be slightly larger than the actual width of the helical tubes." This also sets the soft 2D mask, so too-small a diameter clips real density (see Common failures).
- **Bimodal angular priors (`helical_bimodal_angular_priors`, default Yes)** → `--helical_bimodal_angular_priors`. Keep Yes unless the 3D helix looks identical when flipped upside-down.
- **Coordinates are start-end only (`do_extract_helical_tubes`, default Yes)** → `--helical_tubes`.
- **Cut tubes into segments (`do_cut_into_segments`, default Yes)** → `--helical_cut_into_segments`. If No, only the central box of each tube is extracted.
- **Inter-box distance** is NOT set directly; it is derived: `inter-box (pix) = helical_rise (Å) × helical_nr_asu / pixel_size (Å)` (`pipeline_jobs.cpp:2465-2466`). Aim for ~10% of the box size. When cutting is off the GUI writes literal `--helical_nr_asu 1 --helical_rise 1` (line 2630).

Extraction emits a `helix_segments.star` node when start-end tubes are used (`pipeline_jobs.cpp:2657`).

Illustrative command (NEW rootname; do not run against the read-only fixture):
```
relion_preprocess --i CtfFind/job014/micrographs_ctf.star \
  --coord_dir AutoPick/jobNNN/ --part_star Extract/jobNEW/particles.star \
  --extract --extract_size 256 --bg_radius 100 \
  --helix --helical_outer_diameter 200 --helical_bimodal_angular_priors \
  --helical_tubes --helical_cut_into_segments --helical_nr_asu 1 --helical_rise 4.75
```
(Flags `--extract`, `--extract_size`, `--bg_radius` are the generic extraction flags; confirm box/bg via 05_picking_extraction.md before use.)

---

## 4. 2D classification of helical segments

`do_helix` = Yes in 2D classification (`pipeline_jobs.cpp:3111`) adds the tube diameter mask and a bimodal psi-prior restriction. Relevant joboptions:
- `helical_tube_outer_diameter` → `--helical_outer_diameter` (sets the rectangular/elliptical mask instead of a circle; `pipeline_jobs.cpp:3112-3313`). A negative value falls back to an ordinary circular mask.
- `do_bimodal_psi` (default Yes) restricts in-plane psi search around the bimodal prior from picking.
- `do_restrict_xoff` (default Yes) + `helical_rise` (default 4.75 Å, line 3123) → restricts translational offsets along the helix to ±rise/2 with a flat prior, so neighbouring segments are not aligned on top of each other.

After 2D, select straight, untangled classes that show clear cross-beta striations (amyloid) or recognisable subunit repeats. Then optionally clean up with **FilamentTools** (Subset-selection, Filament tab = Yes): it runs a bi-hierarchical classification (filaments × 2D class), writes `logfile.pdf` plus `run_optimiser.star`, and lets you select *whole filaments* belonging to clean class blocks rather than individual 2D classes — yielding cleaner homogeneous subsets than 2D-class selection alone (`FilamentTools.rst` lines 9-15). For millions of particles split the dataset; combine output subset star files with `relion_star_handler`. See 06_class2d_select.md.

---

## 5. Initial 3D model from 2D classes — `relion_helix_inimodel2d`

`relion_helix_inimodel2d` builds an initial 3D reference (especially for amyloids) from a selection of 2D class averages that together span a full cross-over. It performs an iterative tomographic 2D reconstruction over 1D pixel columns of the cross-over, then lofts that to 3D (`Reference/Helix.rst` lines 16-36). Run from the command line — there is no GUI job.

Flags (verified live `relion_helix_inimodel2d --help`):

| Flag | Meaning |
|---|---|
| `--i` | STAR file of input class averages (+ orientation params) |
| `--o` | output rootname |
| `--crossover_distance` | distance (Å) between two cross-overs — **the key helical input** |
| `--angpix` | pixel size (Å; default from STAR) |
| `--maxres` | resolution limit (Å) |
| `--search_shift` | translation search ⊥ to helical axis (Å) |
| `--search_angle` / `--step_angle` | in-plane rotation search range / step (deg) |
| `--mask_diameter` | mask diameter (Å) on the 2D reconstruction |
| `--iter`, `--K`, `--smear`, `--search_size`, `--iniref`, `--sym`, `--j` | iterations / classes / X-smear / crossover fit window / seed reference / in-plane symmetry order / threads |
| `--only_make_3d` | take `--iniref` and build a 3D model with no alignment of the inputs |

Two-stage recipe straight from the docs (`Reference/Helix.rst` lines 29-36), with NEW rootnames:
```
# stage 1: align the 2D classes across a cross-over
relion_helix_inimodel2d --i Select/jobNNN/class_averages.star \
  --crossover_distance 800 --angpix 1.15 --maxres 9 --search_shift 3 \
  --mask_diameter 250 --j 6 --iter 5 --o IniModel/runNEW1

# stage 2: refine with finer angular sampling, seeded from stage-1 reconstruction
relion_helix_inimodel2d --i IniModel/runNEW1_it005.star \
  --iniref 1@IniModel/runNEW1_it005_reconstructed.mrcs --angpix 1.15 \
  --maxres 6 --search_angle 2 --step_angle 0.5 --mask_diameter 250 \
  --j 6 --iter 5 --o IniModel/runNEW2
```
Output naming: `<rootname>_it<NNN>.star` and `<rootname>_it<NNN>_reconstructed.mrcs` (grounded in the `--iniref 1@...it005_reconstructed.mrcs` usage above). The reconstructed `.mrcs` becomes the 3D reference for `relion_refine` helical auto-refine. Live monitoring with xmipp is suggested but optional (`Reference/Helix.rst` lines 39-43). See 07_initialmodel_class3d.md.

---

## 6. 3D auto-refine (and 3D classification) for helices

`do_helix` = Yes in 3D auto-refine / 3D classification (`pipeline_jobs.cpp:3741`) appends the full helical block to `relion_refine`. All flags below are **verified live** in `relion_refine --help` under "Helical reconstruction (in development...)". The GUI→CLI translation is in `pipeline_jobs.cpp:4031-4099`.

### 6a. Core flags
| GUI joboption | CLI flag (relion_refine) | Notes / default |
|---|---|---|
| `do_helix` | `--helix` | turn on helical refinement |
| `helical_tube_inner_diameter` | `--helical_inner_diameter <A>` | only added if inner > 0 (`pipeline_jobs.cpp:4037-4040`); negative = solid core |
| `helical_tube_outer_diameter` | `--helical_outer_diameter <A>` | slightly larger than tube width; also masks 2D refs |
| `do_apply_helical_symmetry` (default Yes) | (omit → applies sym) / else `--ignore_helical_symmetry` | **set No when symmetry is unknown** (`pipeline_jobs.cpp:3769`, 4043/4071) |
| `helical_nr_asu` (default 1) | `--helical_nr_asu <N>` | new asu per box = inter-box ÷ rise (nearest int); 1 = no symmetry imposed |
| `helical_twist_initial` (deg) | `--helical_twist_initial <t>` | + for right-handed (`pipeline_jobs.cpp:3773`) |
| `helical_rise_initial` (Å) | `--helical_rise_initial <r>` | always positive Å |
| `helical_z_percentage` (default 30%) | `--helical_z_percentage <0..1>` | GUI value/100; central Z fraction used to search/impose symmetry (`pipeline_jobs.cpp:4049-4051`) |
| `keep_tilt_prior_fixed` (default Yes) | `--helical_keep_tilt_prior_fixed` | keeps tilt prior at 90° during global search (`pipeline_jobs.cpp:3802`, 4074-4075) |

### 6b. Local symmetry search
`do_local_search_helical_symmetry` = Yes (`pipeline_jobs.cpp:3781`) adds `--helical_symmetry_search` plus the ranges (`pipeline_jobs.cpp:4053-4070`). `inistep` flags are only emitted when their value > 0:
```
--helical_symmetry_search \
--helical_twist_min <t0> --helical_twist_max <t1> [--helical_twist_inistep <ts>] \
--helical_rise_min  <r0> --helical_rise_max  <r1> [--helical_rise_inistep  <rs>]
```
The true twist/rise must lie inside the given ranges or the search fails to find a sensible symmetry (`pipeline_jobs.cpp:3784`). Default sampling is 5–1000 samples; only set `inistep` if convergence is poor.

### 6c. Angular ranges → sigma conversion
The GUI exposes angular search *ranges* (deg); RELION converts each to a sigma = range/3 before passing it to `relion_refine` (`pipeline_jobs.cpp:4079-4099`). These are only applied when doing global (non-local) alignment:
| GUI range joboption | CLI flag | default range |
|---|---|---|
| `range_rot` | `--sigma_rot (range/3)` | — |
| `range_tilt` | `--sigma_tilt (range/3)` | 15 → sigma 5 |
| `range_psi` | `--sigma_psi (range/3)` | 10 |
| `helical_range_distance` | `--helical_sigma_distance (val/3)` | only if > 0; local averaging of orientations/translations along the tube; ~2.0 recommended for flexible filaments (MAVS-CARD, ParM, MamK) (`pipeline_jobs.cpp:3800`) |

(verified live: `--sigma_rot`, `--sigma_tilt`, `--sigma_psi`, `--helical_sigma_distance` all present.)

### 6d. Other live helical flags worth knowing
From `relion_refine --help` (not all surfaced in the GUI block above): `--helical_nstart` (N-start number for rotational priors, default 1), `--helical_offset_step` (offset sampling along the helical axis, Å), `--helical_exclude_resols` (comma-separated resolution pairs along the helical axis to exclude, e.g. `50,5` to drop a dominant layer-line). Use `--helical_exclude_resols` to suppress an over-dominant cross-beta layer line if it biases alignment.

Illustrative refine3d command (NEW rootname; ~9 Å twist guess, 4.75 Å rise, amyloid-like):
```
relion_refine --o Refine3D/jobNEW/run --auto_refine --split_random_halves \
  --i Select/jobNNN/particles.star --ref IniModel/runNEW2_it005_reconstructed.mrcs \
  --ini_high 10 --particle_diameter 200 --flatten_solvent --zero_mask \
  --oversampling 1 --healpix_order 2 --auto_local_healpix_order 4 \
  --sym C1 --pad 2 \
  --helix --helical_outer_diameter 200 --ignore_helical_symmetry \
  --helical_z_percentage 0.3 --helical_keep_tilt_prior_fixed \
  --sigma_tilt 5 --sigma_psi 3.333 --sigma_rot 0 \
  --j 6 --gpu "0:1"
```
Notes: `--ignore_helical_symmetry` is the safe first pass (symmetry unknown). Generic auto-refine flags (`--auto_refine`, `--split_random_halves`, `--ini_high`, `--healpix_order`, `--zero_mask`, `--pad`, `--gpu`) belong to 08_refine3d.md; the fixture's 2×RTX 2080 Ti (11 GB) limits box size — drop `--pad 2` to `--pad 1` (skip-padding joboption `do_pad1`) if you hit GPU OOM. Blush regularisation (5.0, `--blush`) and the class-ranker (4.0) also apply to helical jobs; see 08_refine3d.md / 06_class2d_select.md.

---

## 7. Amyloid branch specifics

Amyloid filaments are the limiting helical case: a stack of β-strands related by a **single asymmetric rise of ~4.75 Å** (the cross-β rung spacing) and a small twist, frequently with **C1 or pseudo-2₁** symmetry only (protofilaments can be related by an approximate 2-fold). Practical consequences:

- **Picking**: use the `--amyloid` algorithm (§2d). Topaz filament picking also works well for thin amyloid fibrils.
- **Rise**: start with `--helical_rise_initial 4.75`; the 2D classes (`do_helix`, default `helical_rise` = 4.75 Å, `pipeline_jobs.cpp:3123`) already default to this rung.
- **Symmetry**: keep `--ignore_helical_symmetry` until 2D/3D shows a clean cross-over; impose only the genuine helical twist + 4.75 Å rise once measured. Do NOT impose a point group across protofilaments unless the 2-fold is real.
- **Initial model**: `relion_helix_inimodel2d` (§5) was built primarily for amyloids — the `--crossover_distance` is the single most important number, read off the 2D classes (cross-over = half the helical pitch).
- **Per-protofilament**: signal subtraction / focused refinement of one protofilament is common; see 11_subtract_multibody.md.

Version note: the **amyloid-specific additions are extended in RELION 5.1** (e.g. refined amyloid picking and processing tools). In this 5.0.0-commit-3d6c20 install the `--amyloid` picker and `relion_helix_inimodel2d` are present, but any 5.1-only amyloid feature is **(unverified: not in this 5.0 build — confirm against a 5.1 install before relying on it)**.

Project paper crosswalk digests tracked for this branch: **He & Scheres 2017** (J Struct Biol — the core helical algorithm, cited in `Reference/Helix.rst:9` via `he_helical_2017`), **Scheres 2020** (amyloid-specific processing), and **Lövstam 2022** (high-throughput amyloid). These digests live in the project paper crosswalk; consult cryo-em-knowledge / structural-strategy skills for the methodological reasoning, not this file.

---

## 8. `relion_helix_toolbox` — symmetry & geometry utilities

`relion_helix_toolbox` is a multi-function tool selected by one boolean function flag (verified live `relion_helix_toolbox --help`). The most useful functions:

| Function flag | Purpose |
|---|---|
| `--check` | Check parameters for 3D helical reconstruction (sanity-check rise/twist/asu/diameters/z%) |
| `--search` / `--search_sym` | Local search of helical symmetry on a reconstruction |
| `--impose` | Impose helical symmetry in real space on a map |
| `--impose_fourier` | Impose symmetry the way 3D reconstruction does (Fourier space) |
| `--cylinder` / `--simulate_helix` / `--pdb_helix` | Build a cylinder / sphere-helix / PDB-derived initial reference |
| `--spherical_mask` / `--central_mask` / `--cut_out` | Masking / cropping a helical map |
| `--norm` | Normalise 2D/3D helical segments in a STAR file |
| `--average_au_2d` | Average asymmetrical units in 2D along the helical axis |
| `--remove_bad_tilt` / `--remove_bad_psi` / `--remove_bad_ctf` | Clean segments by tilt/psi deviation or bad CTF |
| `--coords_emn2rln` / `--coords_xim2rln` | Convert EMAN2 / XIMDISP helical coords to RELION STAR |
| `--sort_tube_id` / `--divide` / `--merge` | STAR housekeeping by tube ID / split / merge |

Shared parameters (all verified live): `--twist`/`--rise` (+ `_min`/`_max`/`_inistep`), `--nr_asu`, `--z_percentage` (default 0.3), `--cyl_inner_diameter`/`--cyl_outer_diameter`, `--sphere_percentage` (default 0.9), `--sym_Cn`, `--sigma_tilt`/`--sigma_psi`/`--sigma_offset`, `--tilt_max_dev`/`--psi_max_dev` (default 15°), `--angpix`, `--boxdim`. **Twist sign convention from the help text: `--twist` is "in degrees, + for right-handedness"; `--rise` is positive Å.**

Example — check helical parameters before a refine (NEW output, illustrative):
```
relion_helix_toolbox --check --angpix 1.15 --boxdim 256 \
  --twist -1.0 --rise 4.75 --nr_asu 1 --z_percentage 0.3 \
  --cyl_outer_diameter 200 --cyl_inner_diameter -1 --sphere_percentage 0.9
```

---

## 9. `relion_helix_vote_classes` — group filaments by polymorph

`relion_helix_vote_classes` assigns whole filaments to user-defined groups (polymorphs, e.g. PHF vs SF) by majority vote of their segments' 2D/3D class assignments, then selects consistent subsets (verified live `relion_helix_vote_classes --help`):

| Flag | Meaning |
|---|---|
| `--i` | `_data.star` with the classified segments |
| `--nr_classes` | number of classes in the input |
| `--coord_suffix` | suffix of start-end coordinate files (e.g. `_picked.star`, `.box`) |
| `--pick` | alternative 2-column STAR (micrographs + coordinate files) |
| `--o` | output dir (default `HelixAnalyseClasses/`) |
| `--groups` | comma-separated class numbers, `:`-separated groups, e.g. `1,4,5:6,2` |
| `--group_names` | `:`-separated names, e.g. `phf:sf` |
| `--voting_threshold` | min fraction to assign a helix to a group (default 0.0) |
| `--consistency_check` | fraction of particles checked to lie on the start-end line (default 0.05) |
| `--min_nr_picks` / `--min_picks_group` | select filaments with ≥ N picks in a given group |
| `--norm` | normalise before voting |

Example (NEW output dir, illustrative):
```
relion_helix_vote_classes --i Class2D/jobNNN/run_it025_data.star --nr_classes 50 \
  --coord_suffix _picked.star --groups 1,4,5:2,6,7 --group_names phf:sf \
  --voting_threshold 0.5 --o HelixVoteNEW/
```
This is the programmatic counterpart of FilamentTools' visual polymorph separation (§4) and the standard way to split tau PHF/SF-type polymorphs before per-polymorph refinement.

---

## Common failures / red flags

| Symptom | Likely cause | Fix |
|---|---|---|
| Refinement diverges / symmetry "not found" | **Twist sign or units wrong** — twist must be `+` for right-handed (deg), rise positive (Å). A left-handed map fed a `+` twist, or twist given in radians, breaks the search. | Re-measure handedness; `--twist` deg, `--rise` Å, both per the `relion_helix_toolbox`/`relion_refine` help conventions. Run `relion_helix_toolbox --check` first. |
| Density clipped / streaky 2D masks | **Tube diameter too small** — `--helical_outer_diameter` smaller than the real fibril width masks away real signal. | Set outer diameter slightly *larger* than the visible tube width (`pipeline_jobs.cpp:2458`). |
| Map collapses to a featureless rod / wrong repeat | **Helical symmetry imposed before it is known**, or wrong `--helical_nr_asu`. | Start with `--ignore_helical_symmetry` (set `do_apply_helical_symmetry` = No, `pipeline_jobs.cpp:3769`); impose only the measured twist/rise once 2D/3D is clean. |
| Neighbouring segments align on top of each other | Offsets along the helix not restricted. | Keep `do_restrict_xoff` = Yes (2D) / use `--helical_sigma_distance`; consider resetting offsets (`do_reset_offsets`, `pipeline_jobs.cpp:2435`) before refine. |
| Inter-box distance wrong → too few/too many segments | inter-box = `rise × nr_asu / angpix`; people often set asu or rise inconsistently between extract and refine. | Keep `helical_rise` × `helical_nr_asu` consistent; target inter-box ~10% of box (`pipeline_jobs.cpp:2466`). |
| Local symmetry search returns nonsense | True twist/rise outside `--helical_twist_min/max` or `--helical_rise_min/max`. | Widen the ranges; remember the final reconstruction can still converge with wrong symmetry, so a "good" map does not prove the symmetry (`pipeline_jobs.cpp:3784`). |
| GPU OOM on the 11 GB 2080 Ti | large helical box + `--pad 2`. | Reduce box, set "Skip padding" (`do_pad1` → `--pad 1`), or refine on one card. |
| `relion_motion_refine_mpi` "Parameter estimation is not supported in MPI mode" on a helical Polish job | Same constraint as globular Polish — training/estimation must be single-rank (real fixture failure Polish/job040,041). | Run Polish train / estimate single-rank; see 10_ctfrefine_polish.md. |

---

## Cross-links

- 05_picking_extraction.md — autopick/Topaz flags, generic extraction (`relion_preprocess`) parameters.
- 06_class2d_select.md — 2D classification, FilamentTools bi-hierarchical selection, class-ranker.
- 07_initialmodel_class3d.md — initial model, `relion_helix_inimodel2d` placement, 3D classification.
- 08_refine3d.md — 3D auto-refine generic flags, Blush, GPU/memory, `--pad`.
- 09_mask_postprocess_localres.md — helical masks (z-length aware), post-processing.
- 11_subtract_multibody.md — per-protofilament signal subtraction / focused refinement.
- 12_conventions_symmetry.md — handedness, twist sign, Euler/prior conventions.
- 01_star_and_metadata.md — `rlnHelicalTubeID`, `rlnHelicalRise/Twist`, psi/tilt priors.
- 03_cli_inventory.md — full `relion_helix_*` program list.
- 20_troubleshooting.md / 21_error_lookup.md / 22_decision_trees.md — failure routing.
- Installed sibling skills: **cryosparc** (owns cryoSPARC helical refine execution), **chimerax** (rigid-body / visual handedness checks), **cryo-em-knowledge** & **structural-strategy** (He & Scheres / Scheres 2020 / Lövstam 2022 method reasoning), **mask** (helical mask base generation).

---

## Sources

Live `--help` runs on RELION 5.0.0-commit-3d6c20 (`<RELION_BIN>`): `relion_refine --help`, `relion_autopick --help`, `relion_preprocess --help`, `relion_helix_toolbox --help`, `relion_helix_inimodel2d --help`, `relion_helix_vote_classes --help`.

Captured help (read): `.../cli/relion5_cli_capture_20260604/help/relion_helix_toolbox.txt`, `relion_helix_inimodel2d.txt`, `relion_helix_vote_classes.txt`.

Pinned source (read): `.../relion_ver5.0/src/pipeline_jobs.cpp` (autopick helical 2025-2050/2253-2386; extract helical 2456-2657; class2d helical 3111-3329; class3d/refine3d helical joboptions 3741-3802 and command build 4031-4099); `.../relion_ver5.0/src/metadata_label.h` (helical labels).

Docs source (read): `.../relion-documents_release-5.0/source/Reference/Helix.rst`, `.../source/FilamentTools.rst`, `.../source/Whats-new.rst` (lines 122, 46).
