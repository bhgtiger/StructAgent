# 11 — Particle subtraction and multi-body refinement

## Scope
Two RELION tools for focusing on part of a complex and for modelling continuous inter-domain motion: `relion_particle_subtract` (Subtract job — removes signal of unwanted density so the remaining part can be classified/refined or analysed in isolation) and `relion_refine --multibody_masks` (MultiBody job — refines several rigid bodies independently against the same particle, with `relion_flex_analyse` for PCA/eigen-motion analysis). Both consume a *consensus* `Refine3D` optimiser. This file is grounded in the live RELION 5.0.0-commit-3d6c20 binaries, the pinned `pipeline_jobs.cpp`, the RELION-5.0 docs source, and the read-only NeCen/PRC1 fixture (`Subtract/job083,085`, `MultiBody/job087,089`).

---

## 1. Particle subtraction (`relion_particle_subtract`)

### 1.1 What it does
Given a consensus 3D refinement and a 3D mask, it projects the *masked-out* density of the consensus map into each experimental particle (using that particle's known orientation) and subtracts it, leaving images that contain only the density you wanted to keep. The mask semantics are: **the mask covers the density you KEEP; everything outside the mask is subtracted away**. From the live help: `--mask : Name of the 3D mask with all density that should be kept, i.e. not subtracted`. Use it to remove a rigid scaffold (e.g. mask out a nucleosome / membrane / large domain from a complex) before focused classification or local refinement of the remaining part.

> Mask convention warning: the GUI label is *"Mask of the signal to keep"* and the help says the mask = density kept (white=1) and subtracted region = black=0 (`pipeline_jobs.cpp` `initialiseSubtractJob`, joboption `fn_mask`). This is the OPPOSITE polarity of what people often assume from the word "subtract". If you build the mask around the part you want to delete, you will keep the wrong half. Build masks with the `mask` skill or a `MaskCreate` job; see `09_mask_postprocess_localres.md`.

### 1.2 Inputs / outputs
| Item | Value | Grounding |
|---|---|---|
| `--i` | consensus `*_optimiser.star` from Refine3D/Class3D | live help `relion_particle_subtract --help` |
| `--mask` | 3D mask of density to KEEP | live help |
| `--data` | (optional) particle STAR if not all optimiser particles are used | live help |
| `--o` | output dir (default `Subtract/`) | live help |
| Output STAR | `<odir>/particles_subtracted.star` | `pipeline_jobs.cpp:5236` (`LABEL_SUBTRACT_SUBTRACTED`); fixture `Subtract/job083/particles_subtracted.star` |
| Output stacks | `<odir>/Particles/*.mrcs` | fixture: `Subtract/job083/Particles/` subdir exists |
| Node label | `LABEL_SUBTRACT_SUBTRACTED` | `pipeline_jobs.cpp:5236` |

### 1.3 Key flags (all from live `relion_particle_subtract --help`)
| Flag | Default | Meaning |
|---|---|---|
| `--recenter_on_mask` | false | Re-centre subtracted particles on the projected centre-of-mass of `--mask`. GUI "Do center subtracted images on mask?" defaults Yes (`pipeline_jobs.cpp:5164`). |
| `--center_x/--center_y/--center_z` | 9999 | Explicit 3D coordinate to re-centre on (pixels; origin = box centre, `pipeline_jobs.cpp:5165`). Mutually exclusive with `--recenter_on_mask` in the GUI logic (`:5239-5248`). |
| `--new_box` | -1 | Re-window subtracted particles to a smaller box. |
| `--float16` | false | Write half-precision (MRC mode 12); GUI defaults this to Yes (`do_float16`, `:5159`). RELION/CCPEM read float16; some external tools do not. |
| `--ignore_class` | false | Ignore `rlnClassNumber` in the input STAR. |
| `--ssnr` | false | Don't subtract; only compute average spectral SNR of the images. |
| `--revert <star>` | — | Undo subtraction: flips `rlnImageName`/`rlnImageOriginalName` so the STAR points back at the original images. **When given, all other options are ignored** (live help). Output is `<odir>/original.star`, label `LABEL_SUBTRACT_REVERTED` (`pipeline_jobs.cpp:5191`). MPI is rejected for revert (`:5184`). |

### 1.4 MPI
The GUI emits `relion_particle_subtract_mpi` when MPI > 1, else the serial `relion_particle_subtract` (`pipeline_jobs.cpp:5202-5204`). Subtraction is CPU-only (no `--gpu`); both binaries are present in `<RELION_BIN>`.

### 1.5 Runnable example (point `--o` at a NEW rootname)
```bash
# Focused subtraction: keep only the density inside MaskCreate/jobNNN/mask.mrc, subtract the rest
relion_particle_subtract \
  --i   Refine3D/job079/run_optimiser.star \
  --mask MaskCreate/job081/mask.mrc \
  --o   Subtract/job200/ \
  --recenter_on_mask \
  --float16
# -> Subtract/job200/particles_subtracted.star (+ Subtract/job200/Particles/*.mrcs)
```
This mirrors the real fixture command (`Subtract/job083/note.txt`), which produced 241363 subtracted particles and reported `+ The subtracted particles will be re-centred on projections of 3D-coordinate: (-20.1702 , 16.0278 , 30.5501)` in `run.out`. `Subtract/job085` ran the identical command **without** `--recenter_on_mask` — i.e. keep vs re-centre is the one real difference between the two fixture jobs.

```bash
# Revert subtracted particles back to the originals
relion_particle_subtract \
  --revert Subtract/job200/particles_subtracted.star \
  --o      Subtract/job201/
# -> Subtract/job201/original.star
```

### 1.6 Downstream
The `particles_subtracted.star` feeds a `Class3D` (focused/masked classification, often with `--skip_align` if you trust the consensus poses), a `Refine3D` local refinement, or `cryoDRGN`/`3DVA` heterogeneity (see `17_interop_cryodrgn.md`, `16_interop_cryosparc.md`). Subtraction is also the standard preconditioning step before importing into cryoSPARC local refinement.

---

## 2. Multi-body refinement (`relion_refine --multibody_masks`)

### 2.1 Concept
Multi-body refinement treats a complex as several rigid bodies that move relative to one another. Each body is refined against the part of every experimental particle that remains after subtracting the *other* bodies (internally), with Gaussian priors keeping each body near its consensus pose. It is the RELION route for **continuous inter-domain motion**; for the underlying heterogeneity science (when multi-body vs cryoDRGN/3DFlex/3DVA/DynaMight, validation, overfitting) defer to the **cryo-flex-knowledge** skill.

### 2.2 The bodies STAR file
Provided via `--multibody_masks <bodies.star>`. Format (verbatim from `pipeline_jobs.cpp:4625-4644`, `initialiseMultiBodyJob`):
```
data_
loop_
_rlnBodyMaskName
_rlnBodyRotateRelativeTo
_rlnBodySigmaAngles
_rlnBodySigmaOffset
large_body_mask.mrc 2 10 2
small_body_mask.mrc 1 10 2
head_body_mask.mrc  2 10 2
```
| Column | Meaning (source: `pipeline_jobs.cpp:4639-4643`) |
|---|---|
| `_rlnBodyMaskName` | soft-edged mask, values in [0,1], defining the body. |
| `_rlnBodyRotateRelativeTo` | which other body this one rotates relative to (bodies numbered from 1). |
| `_rlnBodySigmaAngles` | std-dev (width) of the Gaussian prior on rotations away from the consensus. |
| `_rlnBodySigmaOffset` | std-dev (width) of the Gaussian prior on translations. |
| `_rlnBodyReferenceName` | OPTIONAL 5th column. `None` = take initial reference from consensus density; or an MRC map for that body. |

Rules: **larger bodies should be listed above smaller bodies** in the STAR file (`pipeline_jobs.cpp:4644`). The fixture used a 2-body refinement (`run_body001_mask.mrc`, `run_body002_mask.mrc` written into `MultiBody/job087`), masks supplied via `multi/multi.star`.

### 2.3 How the job is built (GUI → command)
The MultiBody job emits up to **two** commands: a `relion_refine(_mpi)` continuation from the consensus optimiser, then a `relion_flex_analyse` analysis (`getCommandsMultiBodyJob`, `pipeline_jobs.cpp:4694-4902`). On a fresh run it appends:
| Flag | Source |
|---|---|
| `--continue <consensus_optimiser.star>` | `:4743` (continuation from consensus, NOT a brand-new refine) |
| `--solvent_correct_fsc` | `:4746`; live `relion_refine --help`: *"Correct FSC curve for the effects of the solvent mask?"* |
| `--multibody_masks <bodies.star>` | `:4746` |
| `--oversampling 1`, `--healpix_order N`, `--auto_local_healpix_order N` | `:4753-4763` (always local searches) |
| `--offset_range`, `--offset_step` | `:4766-4768` |
| `--reconstruct_subtracted_bodies` | `:4776`, when "Reconstruct subtracted bodies?" = Yes (default Yes, `:4646`) |
| `--blush` | `:4773`, RELION-5.0 Blush regularisation (default No here) |
| `--pad 2` / `--pad 1` | `:4789-4791` |
| `--gpu "<ids>"` | `:4799`, only if GPU acceleration enabled |

Note `--reconstruct_subtracted_bodies` does **not** appear in the standard `relion_refine --help` listing (it is a multi-body-specific flag); it is grounded in `pipeline_jobs.cpp:4776` and in the executed fixture command in `MultiBody/job087/note.txt`.

### 2.4 Per-body outputs
Refinement writes one set of maps **per body per half-set**, named `run[_ctX]_it<NNN>_half<H>_body<BBB>[_unfil].mrc`, plus per-body angular-distribution `.bild`, per-half `_model.star`, and the usual `_data.star` / `_optimiser.star` / `_sampling.star`. Confirmed in the fixture, e.g.:
```
MultiBody/job087/run_it000_half1_body001.mrc
MultiBody/job087/run_it002_half1_body002_unfil.mrc
MultiBody/job087/run_body001_mask.mrc      # copied-in body masks
MultiBody/job087/run_bodies.bild           # body-axis visualisation for Chimera(X)
```
Output node labels: `LABEL_MULTIBODY_HALFMAP`, `LABEL_MULTIBODY_OPTSET` (`pipeline_jobs.cpp:49,87,116`). Continuation runs get a `_ctX` rootname where X is the iteration continued from (`:4734`); the fixture shows `run_ct2_it002_*` after a continuation from `run_it002`.

### 2.5 Flexibility analysis (`relion_flex_analyse`)
Second command of the job (`pipeline_jobs.cpp:4810-4852`). Live help (`relion_flex_analyse --help`):
| Flag | Meaning |
|---|---|
| `--data <run_data.star>` | orientations to analyse |
| `--model <run_model.star>` | refined model |
| `--bodies <bodies.star>` | same bodies STAR used for refinement |
| `--o analyse` | output rootname (`<odir>/analyse`) |
| `--PCA_orient` | PCA on the multi-body orientations |
| `--do_maps` | generate maps along the principal components |
| `--k <N>` | number of principal components to make maps for |
| `--v <0..1>` | OR: use as many PCs as explain this fraction of variance (default 0.75) |
| `--maps_per_movie` | maps per PC movie (default 10) |
| `--select_eigenvalue[_min/_max]` | write a `particles.star` subset selected on an eigenvalue range |
| `--3dmodels` | one 3D model per experimental particle |

Outputs include `analyse_logfile.pdf` (eigenvalue histograms, label `LABEL_MULTIBODY_FLEXLOG`, `:4895`) and, when maps are requested, series of maps along each eigenvector that open as a **Volume Series** in UCSF Chimera/ChimeraX to play as an eigen-motion movie (`:4665`). Selected-particle output is `analyse_eval<NNN>_select...star` (`LABEL_MULTIBODY_SEL_PARTS`, `:4875-4889`). The fixture flex_analyse command: `relion_flex_analyse --PCA_orient --model ...run_model.star --data ...run_data.star --bodies multi/multi.star --o .../analyse --do_maps --k 3`.

### 2.6 Runnable example (NEW output rootname)
```bash
# Multi-body refine, continuing from a converged consensus Refine3D; 2 bodies, GPU
relion_refine --continue Refine3D/job079/run_it017_optimiser.star \
  --o MultiBody/job200/run \
  --solvent_correct_fsc --multibody_masks multi/multi.star \
  --oversampling 1 --healpix_order 4 --auto_local_healpix_order 4 \
  --offset_range 3 --offset_step 1.5 \
  --reconstruct_subtracted_bodies \
  --dont_combine_weights_via_disc --scratch_dir /processing --pad 2 \
  --j 6 --gpu "0"

relion_flex_analyse --PCA_orient \
  --model MultiBody/job200/run_model.star \
  --data  MultiBody/job200/run_data.star \
  --bodies multi/multi.star \
  --o MultiBody/job200/analyse --do_maps --k 3
```
(`--scratch_dir /processing` is the site convention here; queue submission via `qsub=sbatch`, `qsubscript=<RELION_QUEUE_SCRIPT>` — illustration only, not universal.)

### 2.7 GPU / memory notes
- Multi-body refinement is **memory-hungry**: it holds maps and accumulators for every body × half-set. On the example RELION host node's 2× RTX 2080 Ti (11 GB each), a 2-body refinement of a ~384-box particle set can exhaust GPU RAM — exactly the fixture failure (Section 3).
- DynaMight (RELION-5.0, the ML motion approach, `Flexibility.rst`) uses **one GPU at a time** and is even more memory-bound (>30,000 Gaussians "difficult... unless you have a very large GPU"; inverse-deformation "store deformations in RAM" was infeasible on the authors' small 1080s). Treat single-GPU, modest-VRAM as the binding constraint for both.
- Mitigations: drop to `--gpu ""` (CPU; slow but no VRAM ceiling — used in two of the fixture retries), reduce MPI ranks sharing a GPU, lower `--pool`, use `--pad 1` (`Skip padding?`), shrink box / mask, or move to a larger-VRAM machine.

---

## 3. Teaching example — root vs symptom (fixture `MultiBody/job087`, `job089`)

Both MultiBody jobs ended in `RELION_JOB_EXIT_FAILURE` (the exit-sentinel FILE; see `02_project_job_tree.md`). `run.err` shows **two distinct errors** — and getting the diagnosis right means reading them in order:

1. **ROOT CAUSE — the refine step ran out of GPU memory.**
   ```
   ERROR: out of memory in .../custom_allocator.cuh at line 435 (error-code 2)
   ... A GPU-function failed to execute.
   MPI_ABORT was invoked on rank 2 ... with errorcode 1
   ```
   The backtrace is in `relion_refine_mpi` (`MlDeviceBundle::setupTunableSizedObjects` → `expectation`). So `relion_refine` died mid-iteration; it never wrote the final `run_data.star` / `run_model.star`.

2. **SYMPTOM — flex_analyse then can't find the refine output.**
   ```
   in: .../metadata_table.cpp, line 1276
   ERROR: MetaDataTable::read: File MultiBody/job089/run_data.star does not exist
   ```
   (In `job087` the same message names `run_ct2_data.star`, because retries used the `_ct2` continuation rootname.) This is the **second** command of the job firing after the first already crashed; the missing file is a *consequence*, not the disease.

**Diagnostic rule.** When a MultiBody job reports `run_data.star does not exist` from `relion_flex_analyse`, do NOT chase the missing STAR. Scroll **up** in `run.err` to the first error: here `out of memory` / `A GPU-function failed to execute` from `relion_refine_mpi`. Fix the refine (less VRAM pressure — see 2.7), and the flex_analyse step has its inputs again. The `_it000/_it001/_it002` body maps present in the fixture dirs confirm refine got several iterations in before the allocator failed — classic "crashed mid/late run", which matches the help text's "If this occurred at the middle or end of a run... YOUR DATA OR PARAMETERS WERE UNEXPECTED" branch (here: simply too big for 11 GB).

Note the fixture was processed with **RELION 4.0-beta** (paths say `<RELION4_INSTALL>/...`) and is being read by the 5.0 install — that mismatch is expected; older projects open fine in 5.0. The note.txt retries (CPU `--gpu ""`, swapping `relion_refine` ↔ `relion_refine_mpi`) are the user iterating on exactly this memory problem.

### Common failures / red flags
- `A GPU-function failed to execute` + `out of memory` in `relion_refine(_mpi)` → VRAM exhausted; lower memory footprint or use CPU/`--gpu ""`. NOT a CUDA-arch incompatibility despite the help text's "GPUs incompatible" wording (that branch is for *start*-of-run failures).
- `run_data.star does not exist` from `relion_flex_analyse` → upstream refine failed; this is downstream noise.
- Subtraction kept the wrong half → mask polarity inverted (mask = density to KEEP, white=1).
- `FSC dipped below 0.5 and rose again ... Using higher resolution` WARNINGs (seen in the fixture) → usually too-tight body masks; per the message "not necessarily a bad thing". Soften body masks if bodies are too small.
- Body STAR with smaller bodies above larger ones, or too-small `_rlnBodySigmaAngles/Offset` → poor/over-constrained refinement (`pipeline_jobs.cpp:4644`).

---

## Cross-links
- `09_mask_postprocess_localres.md` — building the keep/body masks (MaskCreate); the `mask` skill (ChimeraX) for model-based masks.
- `08_refine3d.md` — the consensus Refine3D that supplies the optimiser for both Subtract and MultiBody.
- `07_initialmodel_class3d.md` — focused 3D classification on subtracted particles.
- `02_project_job_tree.md` — exit sentinels, `note.txt`, `job.star`, `default_pipeline.star`.
- `16_interop_cryosparc.md`, `17_interop_cryodrgn.md` — subtracted particles into cryoSPARC local refine / cryoDRGN.
- `20_troubleshooting.md`, `21_error_lookup.md` — GPU out-of-memory and "file does not exist" root-vs-symptom patterns.
- Sibling skills: **cryo-flex-knowledge** (multi-body vs cryoDRGN/3DFlex/3DVA/DynaMight, heterogeneity science, validation), **mask** (mask generation), **chimerax** (Volume Series eigen-motion movies, body-axis `.bild`), **cryosparc** (interop).

---

## Sources
- Live binary help (RELION 5.0.0-commit-3d6c20, `<RELION_BIN>`): `relion_particle_subtract --help`, `relion_flex_analyse --help`, `relion_refine --help` (greps for `multibody`, `solvent_correct_fsc`, `reconstruct_subtracted_bodies`, `blush`, `auto_local_healpix`).
- Captured help: `references/cli/relion5_cli_capture_20260604/help/relion_particle_subtract.txt`.
- Pinned source: `references/source/relion_ver5.0/src/pipeline_jobs.cpp` — `initialiseMultiBodyJob`/`getCommandsMultiBodyJob` (lines 4610-4902), `initialiseSubtractJob`/`getCommandsSubtractJob` (lines 5150-5269), node-label helpers (lines 49-116).
- Docs source: `references/source/relion-documents_release-5.0/source/SPA_tutorial/Flexibility.rst` (DynaMight, single-GPU/memory), `.../SPA_tutorial/WrappingUp.rst` (multi-body protocol pointer), `.../SPA_tutorial/Class3D.rst` (Blush context).
- Read-only fixture `<RELION_PROJECT_FIXTURE>`: `Subtract/job083,085/note.txt` + `run.out`, `MultiBody/job087,089/note.txt` + `run.err`, and directory listings of all four jobs.
