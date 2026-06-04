# 09 — Mask create, PostProcess (FSC/sharpen), LocalRes

## Scope
The trio of jobs that turn a converged 3D auto-refine into a publishable, sharpened map plus a defensible resolution number: `relion_mask_create` builds a soft solvent mask; `relion_postprocess` applies that mask, does the phase-randomised masked-FSC correction (Chen 2013), fits a Rosenthal-Henderson B-factor, and writes the sharpened map; and the LocalRes job (a `relion_postprocess --locres` wrapper, or ResMap) produces a per-voxel resolution map and a locally-filtered map. This file covers flags, outputs, how to read the four FSC curves, the 0.143 criterion, and the mask-overfitting smell. Pipeline labels and command construction are grounded in `pipeline_jobs.cpp`; all flags are confirmed against the live 5.0.0-commit-3d6c20 binaries.

---

## 1. Mask creation — `relion_mask_create`

Job type label: `relion.maskcreate` (from fixture `MaskCreate/job038/job.star`). Output node: `MaskCreate/jobNNN/mask.mrc`. The program is single-binary (no MPI); it is multi-threaded via `--j`.

### 1.1 Flags (live `relion_mask_create --help`)

| Flag | Default | Meaning |
|---|---|---|
| `--i` | (none) | Input map to threshold for the initial binary mask (usually `Refine3D/jobNNN/run_class001.mrc`) |
| `--o` | `mask.mrc` | Output mask |
| `--ini_threshold` | `0.01` | Density at which to binarise. Often 0.002–0.02; tune so the lowpassed map shows no noise blobs outside the protein |
| `--extend_inimask` | `0` | Grow the white binary volume this many pixels in all directions (makes the mask less tight) |
| `--width_soft_edge` | `0` | Width (pixels) of the raised-cosine soft edge added to the binary mask |
| `--lowpass` | `-1` (none) | Lowpass filter (Å) applied to `--i` **before** binarisation. ~15 Å gives smooth solvent masks for many proteins |
| `--angpix` | `-1` | Pixel size (Å) for the lowpass filter; `-1` reads it from the map header |
| `--invert` | false | Invert the final mask |
| `--helix` | false | Generate a mask for a 3D helix spanning Z |
| `--z_percentage` | `0.3` | Fraction (NOT percent) of the box Z length, centred, that holds good helical info |
| `--j` | `1` | Threads |

De-novo / boolean-combine options also exist (`--denovo`, `--box_size`, `--inner_radius`, `--outer_radius`, `--center_x/y/z`, `--and/--or/--and_not/--or_not`) for building masks without thresholding a map or for combining two maps; rarely needed for a standard solvent mask.

### 1.2 GUI → command mapping (grounded in `pipeline_jobs.cpp:4923-4965`)

The Mask Creation GUI builds the command as:
```
relion_mask_create --i <fn_in> --o <out>/mask.mrc --lowpass <lowpass_filter> --angpix <angpix> \
  --ini_threshold <inimask_threshold> --extend_inimask <extend_inimask> \
  --width_soft_edge <width_mask_edge> --j <nr_threads>
```
GUI joboption names (left) vs CLI flags (right): `inimask_threshold`→`--ini_threshold`, `extend_inimask`→`--extend_inimask`, `width_mask_edge`→`--width_soft_edge`, `lowpass_filter`→`--lowpass`, `nr_threads`→`--j`. If "Mask a 3D helix?" is Yes, the GUI appends `--helix --z_percentage <helical_z_percentage/100>` (i.e. the GUI takes a percent like 30 and divides by 100; the CLI flag itself wants the fraction 0.3) — `pipeline_jobs.cpp:4962-4964`.

### 1.3 Real fixture command (NeCen/PRC1, `MaskCreate/job038/note.txt`)

This job was run three times (you can re-run the same Mask job with new settings until happy — the GUI shows multiple commands in one `note.txt`). The last one:
```
relion_mask_create --i Refine3D/job037/run_class001.mrc --o MaskCreate/job038/mask.mrc \
  --lowpass 20 --ini_threshold 0.005 --extend_inimask 5 --width_soft_edge 3 --j 1
```
Note `--angpix` is absent here, so the header value (1.06 Å for this 2x-binned dataset) was used.

### 1.4 Runnable example (NEW output rootname)
```
relion_mask_create \
  --i Refine3D/job037/run_class001.mrc \
  --o MaskCreate/job_mymask/mask.mrc \
  --lowpass 15 --ini_threshold 0.006 --extend_inimask 3 --width_soft_edge 6 --j 12
```

### 1.5 What makes a good solvent mask
- Encapsulate the entire ordered density but leave little solvent inside. Inspect slices (RELION Display) or load mask + refined map together in ChimeraX.
- The soft edge matters: the masked-FSC correction is sensitive to too-sharp masks, so a wider/softer edge (and a stronger lowpass) is the cure for mask overfitting (see §2.5).
- Mask iteration is cheap — make several and let PostProcess tell you which gives the best honest resolution.

### 1.6 Model-based masks vs solvent masks
`relion_mask_create` thresholds a **map**. If you need a mask derived from an **atomic model** (e.g. a tight focus/subtraction mask for one chain/domain), that is the job of the installed **mask** skill (ChimeraX `molmap` → binarize/dilate → soft edge → resample onto the target box). Use the **mask** skill for model-reference masks; use this job for the solvent mask consumed by PostProcess and for box-thresholded masks. Multi-body masks are covered in `11_subtract_multibody.md`.

---

## 2. Post-processing — `relion_postprocess`

Job type label: `relion.postprocess` (fixture `PostProcess/job039/job.star`). Single-binary by default; an MPI variant `relion_postprocess_mpi` exists (it is used by the LocalRes job, not by ordinary post-processing). PostProcess takes one unfiltered half-map, auto-pairs the other, applies the mask, runs the phase-randomised masked-FSC correction, sharpens, and reports the gold-standard FSC=0.143 resolution.

### 2.1 Flags (live `relion_postprocess --help`)

| Flag | Default | Meaning |
|---|---|---|
| `--i` | (none) | Half1, e.g. `run_half1_class001_unfil.mrc` |
| `--i2` | (auto) | Half2; default replaces `half1`→`half2` in `--i` automatically |
| `--ios` | (none) | Input tomo optimiser-set file (used to set `--i`; tomo only) |
| `--o` | `postprocess` | Output **rootname** (the GUI passes `<out>/postprocess`) |
| `--angpix` | `-1` | Calibrated pixel size (Å); `-1` reads the half-map header |
| `--half_maps` | false | Also write post-processed half-maps for validation |
| `--mtf` | (none) | STAR file with the detector MTF curve |
| `--mtf_angpix` | `-1.` | Pixel size of the **original raw** micrographs/movies (super-res-aware); needed to read the MTF at the right frequency |
| `--molweight` | `-1` | Molecular weight (kDa) of ordered mass (alternative path to the solvent fraction) |
| `--mask` | (none) | User solvent mask (1=protein, 0=solvent, values in [0,1]) |
| `--auto_mask` | false | Auto-mask by density threshold instead of supplying `--mask` |
| `--inimask_threshold` | `0.02` | Seed-mask density threshold (auto-mask path) |
| `--extend_inimask` | `3.` | Pixels to grow the seed mask (auto-mask path) |
| `--width_mask_edge` | `6.` | Soft-edge width in pixels (auto-mask path) |
| `--force_mask` | false | Keep the mask even if masked resolution is **worse** than unmasked (red flag if you need this — see §2.5) |
| `--auto_bfac` | false | Automated B-factor (Rosenthal & Henderson 2003) |
| `--autob_lowres` | `10.` | Lowest resolution (Å) included in the B-factor fit |
| `--autob_highres` | `0.` | Highest resolution (Å) in the fit (0 = use up to estimated resolution) |
| `--adhoc_bfac` | `0.` | User B-factor (Å²), e.g. `-400`; use when the map does not reach <10 Å so auto-B is unreliable |
| `--skip_fsc_weighting` | false | Disable FSC weighting in sharpening (only to inspect regions beyond overall resolution) |
| `--low_pass` | `0` | Lowpass the final map (Å); 0=off, negative=lowpass at FSC=0.143 (only honoured when `--skip_fsc_weighting`) |
| `--randomize_at_fsc` | `0.8` | Randomise phases from the resolution where FSC first drops below this |
| `--randomize_at_A` | `-1` | Randomise phases from this fixed resolution (Å) instead, if positive |
| `--ampl_corr` | false | Amplitude correlation + DPR, and re-normalise amplitudes for non-uniform angular distributions |
| `--locres ...` | — | Local-resolution mode — see §3 |

### 2.2 GUI → command mapping (grounded in `pipeline_jobs.cpp:5304-5379`)

The PostProcess GUI builds:
```
relion_postprocess --mask <fn_mask> --i <fn_in> --o <out>/postprocess --angpix <angpix> \
  [ --mtf <fn_mtf> --mtf_angpix <mtf_angpix> ] \
  [ --auto_bfac --autob_lowres <autob_lowres> ] | [ --adhoc_bfac <adhoc_bfac> ] \
  [ --skip_fsc_weighting --low_pass <low_pass> ]
```
The mask is **mandatory** in the GUI path (empty `fn_mask` → "ERROR: empty field for input mask"). The half2 name is derived from half1 by `getTheOtherHalf()` — if the filename has no `half` substring the job errors ("cannot find 'half' substring"). MTF flags are only added when an MTF STAR file is given. Auto-B and ad-hoc-B are mutually exclusive in the GUI (two checkboxes), though the binary would accept both.

### 2.3 Real fixture command + run.out (`PostProcess/job039`)
```
relion_postprocess --mask MaskCreate/job038/mask.mrc \
  --i Refine3D/job037/run_half1_class001_unfil.mrc \
  --o PostProcess/job039/postprocess --angpix -1 --auto_bfac --autob_lowres 10
```
Key lines from `run.out` (these are the numbers you read back):
```
+ half2-map: Refine3D/job037/run_half2_class001_unfil.mrc      <- auto-paired
+ --mtf_angpix was not provided, assuming ... 1.06 A/px         <- no MTF given here
+ fraction f (solvent mask based): 9.24822
+ molecular weight inside protein mask: 528713
+ randomize phases beyond: 6.66286 Angstroms                    <- phase-randomisation cutoff
+ Applying sqrt(2*FSC/(FSC+1)) weighting (Rosenthal & Henderson, 2003)
+ slope of fit: -59.2358 ... correlation of fit: 0.922201
+ apply b-factor of: -236.943
+ FINAL RESOLUTION: 4.09123
```
The B-factor RELION applies is roughly `4 x slope` of the Guinier fit (here −59.24 → −236.94 Å²); a fit correlation ~0.92 is healthy. Note this is a 4.0-beta project read by a 5.0 install — that is expected and fine.

### 2.4 Outputs (node labels from `pipeline_jobs.cpp:5342-5351`; files confirmed in fixture)

| File | Pipeline label | Content |
|---|---|---|
| `postprocess.mrc` | `LABEL_POST_MAP` | Sharpened, FSC-weighted, lowpass-to-resolution map (the map you build into) |
| `postprocess_masked.mrc` | `LABEL_POST_MASKED` | The masked version (solvent-flattened) |
| `postprocess.star` | `LABEL_POST_POST` | Metadata + the FSC and Guinier data tables (see §2.6) |
| `logfile.pdf` | `LABEL_POST_LOG` | FSC curves + Guinier plot, one PDF |
| `postprocess_fsc.xml` | — | FSC in XML (EMDB-style; not a pipeline node but always written) |
| `postprocess_fsc.dat`, `postprocess_fsc.eps`, `postprocess_guinier.eps` | — | Gnuplot data/EPS used to assemble the PDF |

Top of `postprocess.star` (fixture) carries the scalar summary: `_rlnFinalResolution` (4.091229), `_rlnBfactorUsedForSharpening` (−236.94), `_rlnUnfilteredMapHalf1/Half2`, `_rlnPostprocessedMap`, `_rlnPostprocessedMapMasked`, `_rlnMaskName`, `_rlnParticleBoxFractionSolventMask` (9.248), `_rlnRandomiseFrom` (6.663), and the Guinier fit: `_rlnFittedSlopeGuinierPlot`, `_rlnFittedInterceptGuinierPlot`, `_rlnCorrelationFitGuinierPlot`.

### 2.5 Reading the four FSC curves (the whole point of phase-randomisation)

The FSC table in `postprocess.star` has columns (exact labels from fixture):

| Column label | The curve |
|---|---|
| `_rlnFourierShellCorrelationUnmaskedMaps` | **Unmasked** FSC — pessimistic; solvent noise drags it down |
| `_rlnFourierShellCorrelationMaskedMaps` | **Masked** FSC — optimistic; can be inflated by mask overfitting |
| `_rlnCorrectedFourierShellCorrelationPhaseRandomizedMaskedMaps` | **Phase-randomised** masked FSC — the spurious correlation the mask alone introduces |
| `_rlnFourierShellCorrelationCorrected` | **Corrected** FSC = the masked FSC with the phase-randomised contribution removed. **This is the curve the 0.143 number comes from.** |

Also present: `_rlnSpectralIndex`, `_rlnResolution` (1/Å), `_rlnAngstromResolution`, and `_rlnFourierShellCorrelationParticleMaskFraction`.

- **0.143 criterion**: reported resolution = the spatial frequency where the *corrected* FSC crosses 0.143 (gold-standard, half-maps were never compared during refinement). FINAL RESOLUTION in `run.out` is exactly this crossing.
- **How to sanity-check the mask**: the phase-randomised (red) curve must be ~0 at the reported resolution. RELION randomises phases from `_rlnRandomiseFrom` (here 6.66 Å) — chosen automatically as the resolution where the unmasked FSC drops below `--randomize_at_fsc` (default 0.8). If the red curve is still rising near your resolution, the corrected curve has subtracted real signal away from a too-aggressive mask.

### 2.6 Common failures / red flags
- **Mask-overfitting smell**: the masked FSC is dramatically better than unmasked AND the phase-randomised curve is non-zero at the claimed resolution. Tutorial fix: stronger lowpass and/or a wider, softer mask in Mask Creation, then redo PostProcess (`Mask.rst` lines 102-105). Iterate the mask — it is cheap.
- **Needing `--force_mask`**: if RELION refuses the mask because the masked resolution is *worse* than unmasked, that means the mask is hurting; forcing it papers over the problem instead of fixing the mask.
- **No `--mtf` / wrong `--mtf_angpix`**: amplitudes will not be MTF-corrected; for the NeCen fixture the standard curve is `mtf_k3_standard_300kV_FL2.star` with the original (super-res) pixel `--mtf_angpix 0.53`, not the 1.06 binned value (see `12_conventions_symmetry.md`). When omitted, `run.out` warns and assumes raw pixel == particle pixel.
- **Auto-B on a low-res map**: `--auto_bfac` needs the map to extend well beyond 10 Å for a meaningful Guinier slope; below that, use `--adhoc_bfac` (a negative value) instead. A low fit correlation (`_rlnCorrelationFitGuinierPlot` well under ~0.9) is a warning.
- **Wrong pixel size found late**: you do not need to re-refine — just set the corrected value via `--angpix` here for the final resolution/scaling (consistent up to ~2 Å, per `Mask.rst:70-72`).

---

## 3. Local resolution

Two engines behind one Local-resolution job (`relion.localres`; ResMap subtype `.resmap`, RELION subtype `.own`):
1. **RELION's own** — `relion_postprocess --locres` (or `relion_postprocess_mpi` with >1 MPI). A series of PostProcess-style corrections under a small soft sphere swept across the map. **MPI-capable.** This is the recommended path here.
2. **ResMap wrapper** — Kucukelbir & Tagare's external program. **Cannot use MPI**, cannot be queued (needs interaction), needs a mask.

### 3.1 Local-resolution flags on `relion_postprocess` (live `--help`)

| Flag | Default | Meaning |
|---|---|---|
| `--locres` | false | Enter local-resolution mode |
| `--locres_sampling` | `25.` | Grid spacing (Å) at which the local-res map is sampled. Very fine (<~15 Å) is slow and can give spurious values |
| `--locres_maskrad` | `-1` | Spherical mask radius (Å); default = 0.5 × sampling |
| `--locres_edgwidth` | `-1` | Soft-edge width (Å) on the moving mask; default = sampling |
| `--locres_randomize_at` | `25.` | Resolution (Å) from which to randomise phases for the local correction |
| `--locres_minres` | `50.` | Lowest local resolution (Å) allowed |
| `--adhoc_bfac` | `0.` | B-factor (Å²) for the locally sharpened/filtered output map (use ~the PostProcess auto-B value) |
| `--mtf` | (none) | Detector MTF STAR, same as PostProcess |

### 3.2 GUI → command (grounded in `pipeline_jobs.cpp:5498-5528`)

The RELION-locres branch builds:
```
relion_postprocess[_mpi] --locres --i <fn_in> --o <out>/relion --angpix <angpix> \
  --adhoc_bfac <adhoc_bfac> [ --mtf <fn_mtf> ] [ --mask <fn_mask> ]
```
Important: the GUI does **not** expose `--locres_sampling` or `--locres_randomize_at` — both joboption lines are commented out in 5.0 source (`pipeline_jobs.cpp:5410-5413`), so the GUI job uses the binary defaults (sampling 25 Å). To change sampling you must run the binary directly or add it via the job's "Additional arguments" (`other_args`, appended verbatim at line 5532). The `--mask` here is only used to make a histogram of local resolution, not for the calculation itself (`pipeline_jobs.cpp:5400`).

### 3.3 Outputs (node labels from source; names from `Validation.rst`)

| File | Label | Content |
|---|---|---|
| `<out>/relion_locres.mrc` | `LABEL_LOCRES_RESMAP` | Per-voxel local-resolution map (Å). Colour a surface by this in ChimeraX |
| `<out>/relion_locres_filtered.mrc` | `LABEL_LOCRES_FILTMAP` | Composite map, each region filtered to its local resolution and sharpened — unique to RELION |
| `<out>/histogram.pdf` | `LABEL_LOCRES_LOG` | Local-resolution histogram within the mask (only when `--mask` given) |

ResMap branch instead symlinks `half1.mrc`/`half2.mrc` and writes `half1_resmap.mrc`.

### 3.4 Runnable example (RELION engine, MPI, NEW rootname)
```
mpirun -n 8 relion_postprocess_mpi --locres \
  --i Refine3D/job037/run_half1_class001_unfil.mrc \
  --o LocalRes/job_mylocres/relion \
  --angpix 1.06 --adhoc_bfac -237 --mtf mtf_k3_standard_300kV_FL2.star --mask MaskCreate/job038/mask.mrc
```
Single-rank variant: drop `mpirun` and use `relion_postprocess --locres ...`. Pick `--adhoc_bfac` near the PostProcess auto-B (~−237 here). The tutorial used `-30` for a different (β-gal) dataset (`Validation.rst:35`); match your own PostProcess B-factor.

### 3.5 Validation: handedness and over-sharpening
- **Handedness**: SGD in 3D-initial-model has a 50% chance of the wrong hand; absolute hand cannot be set without a tilt experiment. If α-helices coil the wrong way, flip with `relion_image_handler --i PostProcess/jobNNN/postprocess.mrc --o ...postprocess_invert.mrc --invert_hand` (`Validation.rst:63-68`). RELION itself is hand-agnostic; flip whenever you notice, then re-do downstream model building. Atomic-model fit (ChimeraX, the **chimerax** skill) is the practical handedness check.
- **Over-sharpening**: a too-negative `--adhoc_bfac` (or aggressive auto-B) amplifies noise; you can end up "interpreting noise for signal" (`pipeline_jobs.cpp:5412`). Cross-check local-res-filtered map detail against the corrected FSC resolution.
- ChimeraX colour-by-local-resolution: open `postprocess.mrc`, Surface Color → by volume data value → browse `relion_locres.mrc` (`Validation.rst:49-53`). Use the **chimerax** skill for scripted/headless coloring and model fitting.

---

## Cross-links
- `08_refine3d.md` — produces the `run_half1/2_class001_unfil.mrc` and `run_class001.mrc` inputs; "solvent-flattened FSCs" option inside refine vs post-hoc masking here.
- `10_ctfrefine_polish.md` — PostProcess resolution is the convergence metric driving CtfRefine/Polish iterations; PostProcess STAR is fed back via `--fsc` (`in_post`, `pipeline_jobs.cpp:7146`).
- `11_subtract_multibody.md` — multi-body and subtraction masks (model/region masks, not solvent masks).
- `12_conventions_symmetry.md` — MTF files, super-res vs binned pixel sizes, `--mtf_angpix` convention.
- `13_helical_amyloid.md` — `--helix`/`--z_percentage` masks for helical reconstructions.
- `18_interop_chimerax_coot_phenix.md` — using `postprocess.mrc` / `relion_locres.mrc` downstream; handedness check by model fit.
- Sibling installed skills: **mask** (model-reference masks via ChimeraX), **chimerax** (fitting, colour-by-local-res, handedness), **phenix** / **coot** (model building into the sharpened map).

## Sources
- Live binaries (5.0.0-commit-3d6c20): `relion_mask_create --help`, `relion_postprocess --help` / `--version`, `which relion_postprocess_mpi`.
- Captured help: `cli/relion5_cli_capture_20260604/help/relion_mask_create.txt`, `.../relion_postprocess.txt`.
- Docs source: `source/SPA_tutorial/Mask.rst`, `source/SPA_tutorial/Validation.rst`.
- Pinned source: `relion_ver5.0/src/pipeline_jobs.cpp` — `getCommandsMaskcreateJob` (4923-4965), `getCommandsPostprocessJob` (5297-5381), `initialiseLocalresJob`/`getCommandsLocalresJob` (5383-5536).
- Read-only fixture `<RELION_PROJECT_FIXTURE>`: `MaskCreate/job038/{note.txt,job.star}`, `PostProcess/job039/{note.txt,job.star,run.out,postprocess.star,dir listing}`. No LocalRes job exists in this fixture.
