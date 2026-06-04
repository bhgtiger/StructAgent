# 07 — Initial model (VDAM SGD) and 3D classification

## Scope
How RELION 5.0 builds a *de novo* 3D reference (gradient/VDAM-SGD via `relion_refine --grad --denovo_3dref`, then `relion_align_symmetry`) and runs unsupervised 3D classification (`relion_refine --K …`), including every flag, the run_it*\_{class,data,model,optimiser}.star outputs, how to read class distribution / per-class resolution, and the validation-fixture chain where `Class3D/job033/run_it025_class002.mrc` became the `Refine3D/job034` reference. All flags below are confirmed against the live `relion_refine --help` on the example RELION host install (RELION 5.0.0-commit-3d6c20) unless marked `(unverified)`.

---

## 1. Initial model — VDAM / SGD (`relion.initialmodel`)

Both initial-model generation and 3D classification are the **same binary** (`relion_refine` / `relion_refine_mpi`). The initial-model job is just `relion_refine` driven in gradient mode with `--denovo_3dref`. Two commands run back-to-back: the gradient refinement, then `relion_align_symmetry` to detect/apply point-group symmetry. (Grounded: fixture `InitialModel/job027/note.txt`.)

### Algorithm
- RELION 4.0 replaced the older SGD with a **VDAM** (Variable-metric Decoupled Adaptive Mini-batch Descent) gradient algorithm; it is *different* from cryoSPARC's ab-initio SGD. (Grounded: `InitialModel.rst` lines 6-7.)
- It loops over **mini-batches** (hundreds–thousands of particles each); the GUI "Number of VDAM mini-batches" maps to `--iter`. (Grounded: `InitialModel.rst` lines 18-20; fixture used `--iter 200`.)
- **Gradient mode cannot use multiple MPI ranks** — run with `--j` threads only, MPI = 1. (Grounded: `InitialModel.rst` lines 65-67; fixture `nr_mpi 1`.)

### Real fixture command (`InitialModel/job027`, RELION 4.0-beta project)
```
relion_refine --o InitialModel/job027/run --iter 200 --grad --denovo_3dref \
  --i Select/job025/particles.star --ctf --K 4 --sym C1 \
  --flatten_solvent --zero_mask --dont_combine_weights_via_disc \
  --scratch_dir /processing --pool 30 --pad 1 --skip_gridding \
  --particle_diameter 160 --oversampling 1 --healpix_order 1 \
  --offset_range 6 --offset_step 2 --auto_sampling --tau2_fudge 4 --j 4 --gpu ""
# then, automatically:
relion_align_symmetry --i InitialModel/job027/run_it200_model.star \
  --o InitialModel/job027/initial_model.mrc --sym C1 --apply_sym --select_largest_class
```
(Grounded verbatim: `InitialModel/job027/note.txt`.)

### Key initial-model flags (live `relion_refine --help`)

| Flag | Default | Meaning / use |
|---|---|---|
| `--grad` | false | Gradient-based optimisation instead of expectation-maximisation. Mandatory for VDAM ab-initio. |
| `--denovo_3dref` | false | Make an initial 3D model from randomly oriented 2D particles. |
| `--iter` | -1 | Max iterations = number of VDAM mini-batches (GUI default 100; fixture used 200). |
| `--K` | 1 | Number of classes/references. Tutorial uses 1; >1 gives a "sink" for bad particles. (Grounded: `InitialModel.rst` 26-29.) |
| `--sym` | c1 | Build in **C1**; symmetrise later (see below). |
| `--tau2_fudge` | -1 | Regularisation T (default 4 for 3D). |
| `--particle_diameter` | — | Mask diameter in Å (fixture 160; tutorial 200). |
| `--flatten_solvent` | false | Mask the references too (GUI "Flatten and enforce non-negative solvent"). |
| `--zero_mask` | false | Fill solvent with zeros instead of random noise. |
| `--healpix_order` | 2 | Angular sampling (hp1=30°, hp2=15°, hp3=7.5°). Fixture hp1 + `--auto_sampling`. |
| `--auto_sampling` | false | Auto-refine the angular/offset sampling during the run. |
| `--grad_write_iter` | 10 | Write model every N iters in SGD (default writes all). |

Additional gradient knobs (rarely touched; defaults from `--help`): `--grad_ini_frac 0.3`, `--grad_fin_frac 0.2`, `--grad_min_resol 20`, `--grad_ini_subset`/`--grad_fin_subset` (mini-batch sizes), `--mu 0.9` (momentum), `--grad_stepsize`, `--grad_em_iters 0` (EM iters appended at the end of a gradient run), `--som_neighbour_pull 0.2` and `--class_inactivity_threshold 0` (self-organising-map / class-pruning during gradient classification). (All grounded: live `relion_refine --help`.)

### Build in C1, then symmetrise — `relion_align_symmetry`
The GUI option "Run in C1 and apply symmetry later" runs VDAM in C1 (observed to converge better than higher symmetry) and then calls `relion_align_symmetry` to detect the symmetry axes and apply the chosen point group. (Grounded: `InitialModel.rst` 39-42.)

`relion_align_symmetry` flags actually used and available (live `relion_align_symmetry --help`):

| Flag | Meaning |
|---|---|
| `--i` | Input map **or** `*_model.star` (selects map from it). |
| `--sym` | Target point-group symmetry. |
| `--apply_sym` | Also apply (impose) the symmetry to the map, not just align axes. |
| `--select_largest_class` | Pick the largest class from `model.star` (default: best symmetry). |
| `--select_highest_resol` | Pick the highest-resolution class instead. |
| `--o aligned.mrc` | Output map; the initial-model job names it `initial_model.mrc`. |

**Output of the initial-model job:** `initial_model.mrc` (the symmetrised map) plus the underlying `run_it200_{class00N,model,data,optimiser,sampling}.star/.mrc`. (Grounded: `InitialModel.rst` 77 for `initial_model.mrc`; fixture `note.txt` for `--o …/initial_model.mrc`.)

### Common failures / red flags (initial model)
- **Forcing symmetry too early.** Running VDAM directly in D2/C4/etc. converges worse than C1-then-symmetrise. Build C1, symmetrise with `relion_align_symmetry`. (Grounded: `InitialModel.rst` 41-42.)
- **Bad handedness.** A *de novo* map can come out mirror-flipped (wrong hand). If a subsequent Refine3D stalls or the map looks "inside-out", invert the hand before refining (hand flip is a downstream postprocess step; see cross-links). The Class3D/Refine3D reference must have the correct hand. (Convention; hand-flip mechanics covered in `09_mask_postprocess_localres.md`.)
- **Trying to use MPI** with `--grad` → run single-rank, threads only. (Grounded: `InitialModel.rst` 65-67.)
- **High-res starting model** carried into Class3D/Refine3D → reference bias; always low-pass the reference (`--ini_high`, see §2).

---

## 2. Unsupervised 3D classification (`relion.class3d`)

Same `relion_refine_mpi` binary, **expectation-maximisation mode** (no `--grad`), with `--K` references and full angular search.

### Real fixture command (`Class3D/job033`, NeCen/PRC1 dataset)
```
relion_refine_mpi --o Class3D/job033/run --i JoinStar/job032/join_particles.star \
  --ref InitialModel/job027/run_it200_class001.mrc --firstiter_cc --ini_high 20 \
  --dont_combine_weights_via_disc --scratch_dir /processing --pool 30 --pad 2 \
  --skip_gridding --ctf --iter 25 --tau2_fudge 4 --particle_diameter 200 \
  --fast_subsets --K 4 --flatten_solvent --zero_mask --strict_highres_exp 12 \
  --oversampling 1 --healpix_order 2 --offset_range 5 --offset_step 2 --sym C1 \
  --norm --scale --j 2 --gpu ""
```
(Grounded verbatim: `Class3D/job033/note.txt`. Note: this 4.0-beta job predates Blush, so `--blush` is absent — that is normal for an older project.)

### Key 3D-classification flags (live `relion_refine --help`)

| Flag | Default | Meaning / when to change |
|---|---|---|
| `--K` | 1 | Number of classes. Tutorial/fixture = 4. Cost scales ~linearly with K (CPU + RAM). (Grounded: `Class3D.rst` 56-59.) |
| `--tau2_fudge` | -1 | Regularisation T. 2D: T=1-2; **3D classification: T=2-4** (fixture 4). Noisy classes → lower T; stuck-low-res → raise T. (Grounded: `Class3D.rst` 61-67.) |
| `--iter` | -1 | Number of EM iterations; tutorial/fixture = 25, "we typically do not change this". (Grounded: `Class3D.rst` 69-71.) |
| `--ref` | — | Reference map (the `initial_model.mrc` or a class from a previous job). |
| `--ini_high` | -1 | Initial low-pass (Å) applied to the reference in iteration 1. Tutorial 50 (40-60 for small, ~70 for ribosome); fixture 20. **Always set this** to limit reference bias. (Grounded: `Class3D.rst` 34-38.) |
| `--firstiter_cc` | false | CC in first iteration — use when reference is **not** on absolute greyscale (GUI "Ref. map is on absolute greyscale? = No"). Fixture used it (`ref_correct_greyscale No`). (Grounded: `Class3D.rst` 29-32; live help.) |
| `--ctf` | false | Do CTF correction. (Grounded: `Class3D.rst` 47.) |
| `--ctf_intact_first_peak` | false | Ignore CTF until first peak — only if you did so in the 2D job that made the reference. (Grounded: `Class3D.rst` 49-51.) |
| `--flatten_solvent` | false | Mask the references. |
| `--zero_mask` | false | Mask particle background to zero (vs random noise). GUI "Mask individual particles with zeros = Yes". |
| `--solvent_mask` | None | User reference mask. **Default (empty) = spherical mask of `--particle_diameter`**, which adds the least bias; supply a real mask only for focused classification. (Grounded: `Class3D.rst` 19-24; live help.) |
| `--solvent_mask2` | None | Secondary mask with its own average density. |
| `--strict_highres_exp` | -1 | Limit resolution of the E-step (Å). Fixture 12; "Limit resolution E-step to" in GUI. Useful to prevent overfitting. (Grounded: `Class3D.rst` 85-89; live help.) |
| `--particle_diameter` | — | Mask diameter Å (fixture 200). |
| `--sym` | c1 | **Classify in C1 first** even if you expect symmetry — lets bad/asymmetric particles separate out and verifies the symmetry. (Grounded: `Class3D.rst` 40-42.) |
| `--fast_subsets` | false | "Use fast subsets" — speeds up large datasets; can hurt quality on small ones (tutorial says No, fixture used it). (Grounded: `Class3D.rst` 73-77.) |
| `--blush` | false | **RELION 5.0** Blush regularisation — CNN denoiser prior trained on EMDB half-maps; helps low-SNR / small complexes against overfitting. Needs the RELION-5 conda env + CUDA GPU (pytorch). (Grounded: `Class3D.rst` 91-93; live help.) |

### Angular / offset search (global vs local)

| Flag | Default | Meaning |
|---|---|---|
| `--healpix_order` | 2 | Global angular sampling: hp2=15°, hp3=7.5°. Fixture hp2. (Grounded: live help string.) |
| `--oversampling` | 1 | Adaptive oversampling (1 = 2×). |
| `--offset_range` | 6 | Translation search range (px). Fixture 5. |
| `--offset_step` | 2 | Translation sampling step (px). |
| `--psi_step` | -1 | In-plane angle step (default hp sampling for 3D). |
| `--skip_align` | false | "Skip orientational assignment (only classify)" — fixed-pose classification using priors from a prior refinement. |
| `--sigma_ang` | -1 | **Local angular search**: stddev on all three Euler angles (search ±3σ). Set this (or the GUI "local searches") to do *local* instead of *global* angular search; otherwise the search is global at `--healpix_order`. (Grounded: live help.) |

> Global vs local: an empty/negative `--sigma_ang` + a `--healpix_order` sampling = **global** search (default Class3D). Providing `--sigma_ang` (e.g. 5) restricts to **local** searches around existing angles from the input STAR — used for refinement-like classification where poses are already roughly known.

### Masks for focused classification
Supply `--solvent_mask <mask.mrc>` (a soft-edged mask around the region of interest, optionally with `--solvent_mask2`) to focus the classification on density differences inside the mask while the rest is treated as solvent. Mask creation and signal subtraction are owned by **`11_subtract_multibody.md`** and the `mask` skill. (Grounded: `Class3D.rst` 19-24; live help `--solvent_mask`/`--solvent_mask2`.)

---

## 3. Outputs and how to read them

Per-iteration outputs (same scheme as 2D, except each 3D class is a separate MRC map). For iteration *it* of job NNN:

| File | Content |
|---|---|
| `run_it025_class00N.mrc` | One reconstructed 3D map per class (N = 1…K), separate MRC files (not a stack). (Grounded: `Class3D.rst` 162-163; fixture lists `run_it000_class001.mrc` … `class004.mrc`.) |
| `run_it025_data.star` | Per-particle table: assigned class, angles, offsets, optics. |
| `run_it025_model.star` | Class distributions, per-class resolution, SSNR tables. |
| `run_it025_optimiser.star` | Optimiser state; this is the file you give to **Subset selection** and to `--continue`. (Grounded: `Class3D.rst` 131, 144.) |
| `run_it025_sampling.star` | Angular/offset sampling state. |
| `run_it000_class00N_angdist.bild` | Chimera/ChimeraX angular-distribution glyph per class. (Grounded: fixture file listing.) |

### Reading class distribution / per-class resolution
The `data_model_classes` loop in `run_it025_model.star` holds, per class: `_rlnReferenceImage`, `_rlnClassDistribution`, `_rlnEstimatedResolution`. Real values from the fixture `Class3D/job033/run_it025_model.star`:

| Class map | rlnClassDistribution | rlnEstimatedResolution (Å) |
|---|---|---|
| run_it025_class001.mrc | 0.315 | 8.04 |
| **run_it025_class002.mrc** | **0.349** | **7.77** |
| run_it025_class003.mrc | 0.223 | 9.72 |
| run_it025_class004.mrc | 0.113 | 12.96 |

(Grounded: extracted live from `Class3D/job033/run_it025_model.star`. The `data_model_general` table also carries `_rlnCurrentResolution` = 8.041380 for this job.)

`class002` has both the largest population and best resolution — and indeed it was selected as the reference for the next refinement: `Refine3D/job034` ran `relion_refine_mpi … --ref Class3D/job033/run_it025_class002.mrc --auto_refine …`. (Grounded: `Refine3D/job034/note.txt`.) This is the canonical Class3D → Refine3D handoff.

Useful one-liners (grounded: `Class3D.rst` 167-190):
```
relion_star_printtable Class3D/job033/run_it025_model.star \
  data_model_class_1 rlnResolution rlnSsnrMap      # SSNR vs resolution per class
relion_star_plottable  Class3D/job033/run_it025_model.star \
  data_model_class_1 rlnResolution rlnSsnrMap      # same, gnuplot
grep _rlnChangesOptimalClasses Class3D/job033/run_it???_optimiser.star   # convergence
```
The smaller classes are low-pass filtered more strongly; per-class SSNR lives in the `data_model_class_N` tables. (Grounded: `Class3D.rst` 165.)

### Selecting the good class
Run a **Subset selection** job on `run_it025_optimiser.star`. Automatic class selection is **not** implemented for 3D classes (only for 2D), so set "Automatically select 2D classes? = No" and pick the good class(es) manually. (Grounded: `Class3D.rst` 140-150.) Class-ranker auto-selection details are in `06_class2d_select.md`.

---

## Common failures / red flags (3D classification)
- **Skipping `--ini_high`** (or using a sharp reference) → reference bias / template overfitting. Always low-pass the reference. (Grounded: `Class3D.rst` 36-38.)
- **Classifying in the expected symmetry from the start** — classify in C1, verify symmetry in the maps, impose it only in the subsequent refinement. (Grounded: `Class3D.rst` 40-42.)
- **`--firstiter_cc` mismatch**: if the reference is not on absolute greyscale (any non-RELION map, or a cryoSPARC import) you *must* use `--firstiter_cc` / "greyscale = No", else intensities are wrong. (Grounded: `Class3D.rst` 29-32.)
- **`--fast_subsets` on small datasets** can degrade class quality even though it is faster. (Grounded: `Class3D.rst` 73-77.)
- **GPU memory on this site**: 2× RTX 2080 Ti = 11 GB each (modest). Large K, large box, or Blush can exceed memory — reduce `--K`, drop `--pool`, downscale the box, or move particles to `--scratch_dir`. (Environment fact.) Blush additionally needs the RELION-5 conda env + a CUDA GPU for pytorch. (Grounded: `Class3D.rst` 91-93.)
- **Older project, no Blush**: a 4.0-beta Class3D job (like job033) has no `--blush` — that is expected, not an error.
- **Continuing a run**: use `--continue run_it0NN_optimiser.star`; do not point `--continue` at a `.mrc` or `data.star`.

---

## Cross-links
- `06_class2d_select.md` — 2D classification, Subset selection, class-ranker (auto-select is 2D-only).
- `08_refine3d.md` — 3D auto-refine (`--auto_refine --split_random_halves`); consumes the selected Class3D map as `--ref` (e.g. job033 class002 → job034).
- `09_mask_postprocess_localres.md` — solvent masks, postprocess, hand flip, local resolution.
- `11_subtract_multibody.md` — focused/masked classification, signal subtraction, multibody.
- `12_conventions_symmetry.md` — point-group conventions, C1-then-symmetrise rationale, handedness.
- `01_star_and_metadata.md` — `*_model.star` / `*_data.star` / `*_optimiser.star` table and label reference.
- `02_project_job_tree.md` — job.star / note.txt / default_pipeline.star and exit-sentinel files.
- `16_interop_cryosparc.md` — importing a cryoSPARC ab-initio map as a Class3D/Refine3D reference (remember `--firstiter_cc`).
- `20_troubleshooting.md`, `21_error_lookup.md` — GPU-memory and run failures.

Sibling installed skills: **mask** (build focused-classification masks), **cryosparc** (cryoSPARC ab-initio/hetero-refine equivalents and interop), **cryo-flex-knowledge** (3D classification vs continuous-heterogeneity methods), **chimerax** (view class maps / fit-in-map).

---

## Sources
- Live binaries (RELION 5.0.0-commit-3d6c20, `<RELION_BIN>`): `relion_refine --help`, `relion_align_symmetry --help` (run during authoring).
- Captured help: `<RELION_SKILL_BUILD_ROOT>/references/cli/relion5_cli_capture_20260604/help/relion_refine.txt`.
- Docs source (pinned 5.0): `…/relion-documents_release-5.0/source/SPA_tutorial/InitialModel.rst`, `…/SPA_tutorial/Class3D.rst`.
- Validation fixture (READ-ONLY, RELION 4.0-beta project) `<RELION_PROJECT_FIXTURE>`: `InitialModel/job027/{note.txt,job.star}`, `Class3D/job033/{note.txt,job.star}`, `Class3D/job033/run_it025_model.star` (class distribution/resolution extracted live), `Refine3D/job034/note.txt`.
