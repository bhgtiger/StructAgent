# 06 — 2D classification, class ranker, Select

## Scope
How RELION 5.0 builds and runs reference-free 2D classification (`relion_refine` with `--K`, VDAM `--grad` or EM, `--tau2_fudge`, mask/CTF/zero-mask options), what the `Class2D/jobNNN/run_it*_{data,model,optimiser,sampling}.star` + `run_it*_classes.mrcs` outputs mean, how the automated `relion_class_ranker` scores good/bad classes (`rlnClassScore`/`rlnPredictedClassScore`), and how the Subset selection job (`relion.select.*`) and `relion_star_handler` produce, combine, split, deduplicate, and alias view-subsets that feed JoinStar → InitialModel. All flags below are grounded against the installed `5.0.0-commit-3d6c20` binaries, the captured help, `pipeline_jobs.cpp`, and the read-only 4.0-beta fixture `<RELION_PROJECT_FIXTURE>`.

---

## 1. 2D classification (`relion_refine`)

2D classification (job type `relion.class2d`) and 3D classification/refinement all run through the **single binary `relion_refine`** (MPI variant `relion_refine_mpi`). There is no separate `relion_class2d` program. The GUI builds the command in `RelionJob::getCommandsClass2DJob` / `initialiseClass2DJob` (`pipeline_jobs.cpp`).

### 1.1 Real fixture command (the canonical shape)

From `Class2D/job017/note.txt` (4.0-beta project, VDAM run):

```
`which relion_refine` --o Class2D/job017/run --grad --class_inactivity_threshold 0.1 \
  --grad_write_iter 10 --iter 200 --i Extract/job016/particles.star \
  --dont_combine_weights_via_disc --scratch_dir /processing --pool 30 --pad 2 \
  --ctf --tau2_fudge 2 --particle_diameter 180 --K 200 --flatten_solvent --zero_mask \
  --strict_highres_exp 12 --center_classes --oversampling 1 --psi_step 12 \
  --offset_range 5 --offset_step 2 --norm --scale --j 4 --gpu "" --pipeline_control Class2D/job017/
```

Note `--grad --class_inactivity_threshold 0.1 --grad_write_iter 10` is **hard-coded by the GUI** when VDAM is selected (`pipeline_jobs.cpp:3211`), not user-tunable from the basic tabs. `--gpu ""` means "use GPUs, auto-assign device IDs". The literal executed command is always recoverable from `note.txt` and from the first comment line of any `run_it*_optimiser.star`.

### 1.2 Key `relion_refine` flags for 2D (verified: `relion_refine --help`)

| Flag | Default | Meaning / 2D usage |
|---|---|---|
| `--i` | — | Input particles STAR file (e.g. `Extract/jobNNN/particles.star`) |
| `--o` | — | **Output rootname** — point at a NEW path (`Class2D/jobNNN/run`) |
| `--K` | 1 | Number of classes (GUI option `nr_classes`). Tutorial uses 100; fixture used 200 |
| `--tau2_fudge` | -1 | Regularisation parameter **T** (GUI `tau_fudge`). >1 = more weight to data. 2D typically T=2–3 |
| `--particle_diameter` | -1 | Mask diameter in **Å** (circular mask applied to particles and class averages). Must exceed longest particle dimension |
| `--zero_mask` | false | Fill solvent area with zeros (GUI `do_zero_mask=Yes`); default otherwise fills with random noise |
| `--flatten_solvent` | false | Also mask the references (added automatically with zero_mask in the 2D job) |
| `--ctf` | false | Perform CTF correction (GUI `do_ctf_correction=Yes`) |
| `--ctf_intact_first_peak` | false | Ignore CTFs until first peak (GUI `ctf_intact_first_peak`) |
| `--psi_step` | -1 | In-plane angle sampling (deg, before oversampling). Default 10° for 2D; fixture used 12 |
| `--offset_range` | 6 | Translational search range (**pixels**) |
| `--offset_step` | 2 | Translational sampling (**pixels**) |
| `--strict_highres_exp` | -1 | "Limit resolution E-step to (Å)" (GUI `highres_limit`); positive value caps alignment frequencies to fight overfitting |
| `--center_classes` | false | Re-center class averages on centre-of-mass each iteration (GUI `do_center`); recommended before class-ranker and template picking |
| `--bimodal_psi` | false | Bimodal psi search (GUI `do_bimodal_psi`); used for helical 2D segments |
| `--oversampling` | 1 | Adaptive oversampling order (1 = 2×) |
| `--norm` / `--scale` | false | Normalisation-error and per-group intensity-scale corrections (added by GUI) |

**Algorithm selection (mutually exclusive):**

| GUI option | Flag emitted | Notes |
|---|---|---|
| `do_grad=Yes` (VDAM) | `--grad --class_inactivity_threshold 0.1 --grad_write_iter 10 --iter <nr_iter_grad>` | RELION-4.0+ default; `--iter` is the number of **mini-batches** (200 good, 100 faster). **VDAM cannot run under MPI** (`pipeline_jobs.cpp:3207`) — use `--nr_mpi 1` and threads/GPUs only |
| `do_em=Yes` (EM) | `--iter <nr_iter_em>` (no `--grad`) | Classic Expectation-Maximization; default ~25 iters, no convergence criterion (stop manually). MPI-parallelisable |

Specifying both raises `"You cannot specify to use both the EM and the VDAM algorithm!"`; specifying neither raises `"You need to specify to use either the EM or the VDAM algorithm"`.

**Fast subsets** (`--fast_subsets`, GUI `do_fast_subsets`): "Use faster optimisation by using subsets of the data in the first 15 iterations" (help text); the GUI tooltip describes K×1500 → K×4500 → 30% → all-data ramp. Primarily an EM-path accelerator (the VDAM algorithm already mini-batches). Not used in the fixture.

### 1.3 Compute flags (GPU memory is modest here: 2× RTX 2080 Ti, 11 GB)

| Flag | Use |
|---|---|
| `--gpu ""` | Use all GPUs, auto-assign. `--gpu 0:1` to pin specific devices |
| `--j` | Threads per process (fixture: 4). With VDAM, increase threads rather than MPI ranks |
| `--pool` | Images pooled per thread task (fixture: 30) |
| `--scratch_dir /processing` | Copy particle stack to local scratch (here `<SCRATCH_DIR>`) — big I/O win on NFS |
| `--dont_combine_weights_via_disc` | Send summed weights over MPI instead of disc |
| `--preread_images` | Leader reads all particles into RAM (only if RAM is ample) |
| `--blush` | 5.0 regularised reconstruction (Blush, a denoiser-prior); mainly for 3D refine/InitialModel, available here but **not** a 2D default |

### 1.4 Outputs (per iteration `it<NNN>`)

For each written iteration RELION emits a fixed set (tutorial `Class2D.rst`; confirmed in `Class2D/job017/`):

| File | Contents |
|---|---|
| `run_it<NNN>_classes.mrcs` | MRC stack of the K class-average images (full CTF-corrected → white-on-black) |
| `run_it<NNN>_model.star` | Model params: `data_model_general` (`rlnNrClasses`, `rlnPixelSize`, `rlnTau2FudgeFactor`, `rlnCurrentResolution`…), `data_model_classes` (per-class table), `data_model_groups`, `data_model_class_N` SSNR spectra, `data_model_optics_group_N` noise spectra |
| `run_it<NNN>_data.star` | Per-particle metadata incl. assigned `rlnClassNumber`, orientations, offsets; reusable as input to a new job |
| `run_it<NNN>_optimiser.star` | Restart/continue state; first line carries the literal command; **is the input node for Subset selection and class-ranker in 4.0+** |
| `run_it<NNN>_sampling.star` | Sampling rates (needed for restart) |
| `run_it<NNN>_1moment.mrcs`, `run_it<NNN>_2moment.mrcs` | VDAM gradient moment stacks (present only for `--grad` runs; fixture has them) |

The `data_model_classes` table header in the fixture (`Class2D/job021/run_it200_model.star`) is exactly:
`_rlnReferenceImage _rlnGradMoment1 _rlnGradMoment2 _rlnClassDistribution _rlnAccuracyRotations _rlnAccuracyTranslationsAngst _rlnEstimatedResolution _rlnOverallFourierCompleteness _rlnClassPriorOffsetX _rlnClassPriorOffsetY`. `rlnClassDistribution` = fraction of particles in that class; `rlnEstimatedResolution` = its estimated resolution in Å.

### 1.5 Continue a run

Select the job's `run_it<NNN>_optimiser.star` as "Continue from here" (GUI `fn_cont`) and set a higher `--iter`. The continued run's `--o` rootname must differ from the original, or RELION appends `_ctX`. See `08_refine3d.md` for the analogous 3D restart mechanics.

---

## 2. Class ranker (`relion_class_ranker`)

`relion_class_ranker` (RELION-4.0+) is a trained CNN that scores each 2D class average for "good vs junk" so selection can be **automated and non-interactive** (critical on this headless server — see §3.1). It reads a 2D `optimiser.star` and the associated class images + model.

### 2.1 How the Subset-selection job invokes it (`pipeline_jobs.cpp:2918-2956`)

When the Select job has `do_class_ranker=Yes`, the job label becomes `relion.select.class2dauto` and the command is:

```
`which relion_class_ranker` --opt Class2D/jobNNN/run_it200_optimiser.star \
  --o Select/jobMMM/ --fn_sel_parts particles.star --fn_sel_classavgs class_averages.star \
  --fn_root rank --do_granularity_features --auto_select --min_score <rank_threshold>
```

`--select_min_nr_particles <n>` OR `--select_min_nr_classes <n>` are appended when the GUI `select_nr_parts`/`select_nr_classes` are positive (safety net so you never select zero classes). **Regrouping and recentering are not implemented in class_ranker** — requesting either raises `"ERROR: regrouping and recentering have not been implemented in class_ranker."`.

### 2.2 `relion_class_ranker` flags (verified: `relion_class_ranker --help`)

| Flag | Default | Meaning |
|---|---|---|
| `--opt` | — | Input `optimiser.star` from the Class2D job |
| `--o` | `./` | Output **directory** (note: a directory, not a rootname) |
| `--auto_select` | false | Actually perform the threshold-based selection |
| `--min_score` | 0.5 | Minimum class score to keep (GUI `rank_threshold`) |
| `--max_score` | 999. | Maximum class score to keep |
| `--select_min_nr_particles` | -1 | Keep at least this many particles regardless of score |
| `--select_min_nr_classes` | -1 | OR keep at least this many classes regardless of score |
| `--relative_thresholds` | false | Interpret min/max as fractions of the max predicted score |
| `--fn_sel_parts` | `particles.star` | Output selected-particles STAR filename |
| `--fn_sel_classavgs` | `class_averages.star` | Output selected class-averages STAR filename |
| `--fn_root` | `rank` | Rootname for output `rank_model.star` / `rank_optimiser.star` |
| `--do_granularity_features` | false | Compute granularity features (the GUI always passes this) |
| `--ext` | `ranked` | Extension for output optimiser/model rootnames |

### 2.3 Scores and labels (verified live: `relion_refine --print_metadata_labels`)

- `rlnClassScore` — "Class score calculated based on estimated resolution and selection label"
- `rlnPredictedClassScore` — "2D class merit scores predicted by RELION model" (the CNN output)
- The score combines estimated resolution and learned image features; higher = better. Default keep threshold is **0.5**; the fixture/tutorial use lower thresholds (tutorial recommends 0.1, fixture default `rank_threshold=0.5`).

### 2.4 What it needs to run

The model + class images: a valid `run_it*_optimiser.star` pointing at its `_model.star` and `_classes.mrcs`. It only works on classes from a `relion_refine` job (the GUI tooltip: *"This option only works when selecting classes from a relion_refine job"*). It runs on CPU and does **not** require the GUI/FLTK, so it is the headless-safe path on example RELION host.

---

## 3. Subset selection (job type `relion.select.*`)

The Subset selection job (`PROC_CLASSSELECT_LABELNEW = "relion.select"`, `pipeline_jobs.h:346`) is multi-purpose; the GUI appends a sub-label depending on which mutually-exclusive mode is chosen. Verified sub-labels and the program each one actually runs:

| Mode (GUI option) | Sub-label | Program run | Output |
|---|---|---|---|
| Interactive class/particle picking (default) | `.interactive` | `relion_display --gui --allow_save` | `particles.star` (+ `class_averages.star` for Class2D) |
| Automatic 2D class selection (`do_class_ranker`) | `.class2dauto` | `relion_class_ranker` | `particles.star`, `class_averages.star`, `rank_optimiser.star` |
| Select on metadata values (`do_select_values`) | `.onvalues` | `relion_star_handler --select …` | `particles.star` / `micrographs.star` |
| Discard on image statistics (`do_discard`) | `.discard` | `relion_star_handler --discard_on_stats` | filtered STAR |
| Split into subsets (`do_split`) | `.split` | `relion_star_handler --split` | `particles_split*.star` |
| Remove duplicates (`do_remove_duplicates`) | `.removeduplicates` | `relion_star_handler --remove_duplicates` | `particles.star` |

(Sub-label strings `.interactive`, `.class2dauto`, `.onvalues`, `.discard`, `.split`, `.removeduplicates` are from `pipeline_jobs.cpp` `getCommandsSelectJob`. The fixture's `job.star` files all carry `_rlnJobTypeLabel relion.select.interactive`.)

### 3.1 Interactive mode needs the GUI — and `relion_display` is broken headless here

The fixture's Select jobs (`Select/job023`, `job025`, `job035`) all ran:

```
`which relion_display` --gui --i Class2D/job021/run_it200_optimiser.star --allow_save \
  --fn_parts Select/job023/particles.star --fn_imgs Select/job023/class_averages.star --recenter
```

On **this example RELION host install** `relion_display` fails to even print `--help`:

```
relion_display: error while loading shared libraries: libfltk.so.1.3: cannot open shared object file
```

**Red flag / consequence:** interactive class selection cannot be reproduced headless here. To select classes non-interactively, use **`relion_class_ranker --auto_select`** (§2) or **`relion_star_handler --select`** on a model/data STAR (§3.3). `--recenter` (GUI `do_recenter`) and `--regroup N` (GUI `do_regroup`, "Approximate nr of groups") are only available on the interactive/`relion_display` path; class_ranker rejects them.

A manual interactive selection is recorded as `backup_selection.star` in the job dir — a single-column `_rlnSelected` table (one 0/1 per class, in class order). The fixture's `Select/job023/backup_selection.star` shows `_rlnSelected` = 0/1 flags; re-running the job replays that backup. The kept classes (and their `rlnClassScore`/`rlnEstimatedResolution`/`rlnClassDistribution`) land in `class_averages.star`, and the per-particle subset in `particles.star`.

### 3.2 Select-job option reference (from fixture `job.star` + `pipeline_jobs.cpp`)

| `job.star` option | CLI effect |
|---|---|
| `fn_model` | Input `optimiser.star` (Class2D/Class3D) — drives interactive or class_ranker mode |
| `fn_data` | Input particle `data.star` — drives value/discard/split/dedup modes |
| `fn_mic` | Input micrographs STAR — drives value/discard modes for micrographs |
| `do_class_ranker` + `rank_threshold` | `--auto_select --min_score <rank_threshold>` |
| `do_recenter` | `--recenter` (interactive Class2D only) |
| `do_regroup` + `nr_groups` | `--regroup <nr_groups>` (interactive only) |
| `do_select_values` + `select_label`/`select_minval`/`select_maxval` | `relion_star_handler --select <label> --minval --maxval` |
| `do_discard` + `discard_label`/`discard_sigma` | `--discard_on_stats --discard_label --discard_sigma` |
| `do_split` + `nr_split`/`split_size`/`do_random` | `--split [--nr_split N] [--size_split M] [--random_order]` |
| `do_remove_duplicates` + `duplicate_threshold`/`image_angpix` | `--remove_duplicates <Å> [--image_angpix]` |

### 3.3 `relion_star_handler` — the non-GUI Swiss-army knife (verified: `--help`)

Used by Select for value/discard/split/dedup and by JoinStar for combine. Key options:

| Operation | Command |
|---|---|
| **Combine** STAR files (+ dedup) | `relion_star_handler --combine --i "a.star b.star" --check_duplicates rlnImageName --o out.star` |
| **Select** by numeric label | `relion_star_handler --i in.star --select rlnCtfMaxResolution --minval -9999 --maxval 6 --o out.star` |
| **Select** by string label | `relion_star_handler --i in.star --select_by_str rlnMicrographName --select_include foo --o out.star` |
| **Split** into N equal files | `relion_star_handler --i in.star --split --nr_split 5 --o out.star` |
| **Split** by subset size | `relion_star_handler --i in.star --split --size_split 50 [--random_order] --o out.star` |
| **Remove duplicates** | `relion_star_handler --i in.star --remove_duplicates 30 [--image_angpix <orig Å>] --o out.star` |
| **Discard** on image stats | `relion_star_handler --i in.star --discard_on_stats --discard_sigma 4 --o out.star` |
| **Histogram** a column | `relion_star_handler --i in.star --hist_column rlnCtfMaxResolution` |

`--combine` requires all input filenames inside one double-quoted `--i` argument. `--check_duplicates rlnImageName` drops particles that appear in more than one input — essential when combining view-subset selections that overlap (see §4). `--remove_duplicates` is distance-based (Å) and removes particles that drifted onto the same spot during alignment (they inflate FSC).

---

## 4. View-subsets → JoinStar → InitialModel (the fixture pattern)

The fixture demonstrates the standard "split by view, then recombine" workflow. The `Select/` directory carries **aliases** that re-point process names to their job dirs (`default_pipeline.star` `_rlnPipeLineProcessAlias`):

```
Select/side_view   -> Select/job023/    Select/top_view   -> Select/job025/
Select/side_view_1 -> Select/job028/    Select/top_view_2 -> Select/job031/
Select/side_view_2 -> Select/job030/    Select/J055_C1_C5 -> Select/job058/   Select/J62_cls_01 -> Select/job064/
```

Each `side_view*/top_view*` is an interactive Class2D selection keeping only the classes of one viewing direction. They then feed JoinStar:

```
# JoinStar/job032 (type relion.joinstar.particles), note.txt:
`which relion_star_handler` --combine --i " Select/job030/particles.star Select/job031/particles.star " \
  --check_duplicates rlnImageName --o JoinStar/job032/join_particles.star
```

i.e. JoinStar's "Join particle STAR files" mode is just `relion_star_handler --combine --check_duplicates rlnImageName` over `fn_part1..fn_part4`. The combined STAR then becomes the input particles for `InitialModel/job027` (`relion_refine --denovo_3dref --grad --K 4`). See `07_initialmodel_class3d.md` for the InitialModel step itself (it chains `relion_refine` then `relion_align_symmetry --select_largest_class`).

**Why split by view first:** balancing/curating preferred vs minority views before building the first 3D model reduces preferred-view bias in the de-novo model. The tutorial explicitly warns: *"be careful not to throw away your minority views!"* (`Class2D.rst`).

---

## 5. Reading 2D classes — junk vs signal, preferred-view detection

Grounded in `Class2D.rst` and the model.star labels:

- **Good signal:** internal structure visible within domains; flat solvent around the particle; class average resembles a projection of a low-pass-filtered atomic model. High `rlnClassDistribution` classes are higher-resolution (more particles → higher SNR) — this is intrinsic to the Bayesian approach.
- **Junk:** small classes (`rlnClassDistribution` near zero), blobby/edge/streaky averages, ice/carbon edges, aggregates. Bad particles "do not average well together" and collect into small ugly classes — discarding them cleans the dataset.
- **Overfitting:** radially extending streaks in the solvent region. Remedy: lower T (`--tau2_fudge`) and/or set `--strict_highres_exp` (Limit E-step) to ~10–15 Å.
- **Quantitative sort:** in the GUI, sort class averages on `rlnClassDistribution` (population) or `rlnEstimatedResolution` (resolution); class-ranker's `rlnClassScore`/`rlnPredictedClassScore` combine both into one number. The class-average quality is the best early predictor of final 3D map quality.
- **Preferred-view detection:** if a few high-population classes all show the same projection (e.g. only top views), the dataset has a preferred orientation. Count distinct view directions across the high-`rlnClassDistribution` classes; if narrow, expect anisotropic 3D resolution. The fixture's response was to make separate `side_view`/`top_view` Selects and recombine balanced subsets (§4). Tilt-collection and view-rebalancing are downstream remedies — see `08_refine3d.md` / `12_conventions_symmetry.md`.

---

## Common failures / red flags

- **`relion_display` cannot run headless here** (`libfltk.so.1.3` missing) → interactive Subset selection is impossible on example RELION host. Use `relion_class_ranker --auto_select` or `relion_star_handler --select`. (Verified: captured `relion_display.txt`.)
- **VDAM + MPI** → `"Gradient refinement (running the VDAM algorithm) is not supported together with MPI."` Run VDAM with `--nr_mpi 1`; scale via threads/GPUs. (`pipeline_jobs.cpp:3207`; help: `--grad`.)
- **Both `--grad` and EM iters set** → `"You cannot specify to use both the EM and the VDAM algorithm!"`.
- **class_ranker + regroup/recenter** → `"ERROR: regrouping and recentering have not been implemented in class_ranker."` Do regrouping in a separate interactive/value Select. (`pipeline_jobs.cpp:2914`.)
- **GPU OOM on 2080 Ti (11 GB):** large box × many classes can exceed memory. Reduce `--K`, lower `--pool`, set `--free_gpu_memory`, or drop to fewer GPUs/CPU. (`--free_gpu_memory`, `--pool` verified in `relion_refine --help`.)
- **Mask diameter too small** clips particle signal from class averages; too large lets neighbouring particles/solvent interfere with alignment. Set `--particle_diameter` just larger than the longest particle dimension (`Class2D.rst`).
- **`--combine` without `--check_duplicates`** can double-count particles shared between view-subsets → inflated/invalid gold-standard FSC later. Always pass `--check_duplicates rlnImageName`.
- **Class averages black-on-white instead of white-on-black** usually means CTF correction was off or references weren't intensity-corrected; with `--ctf` they should be white on black (`Class2D.rst`).

---

## Cross-links

- `01_star_and_metadata.md` — STAR/optics-group structure, `rlnClassNumber`, `data_model_*` tables.
- `02_project_job_tree.md` — `job.star`, `note.txt`, `default_pipeline.star`, aliases, exit sentinels.
- `03_cli_inventory.md` — full `relion_refine` / `relion_star_handler` / `relion_class_ranker` flag inventory.
- `05_picking_extraction.md` — Extract job that produces `particles.star` input here.
- `07_initialmodel_class3d.md` — de-novo 3D model and 3D classification fed by the combined view-subsets.
- `08_refine3d.md` — Refine3D, continue mechanics, preferred-view consequences.
- `12_conventions_symmetry.md` — symmetry, view geometry, angular conventions.
- `13_helical_amyloid.md` — 2D classification of helical segments (`--bimodal_psi`, `--helix`).
- `16_interop_cryosparc.md` — importing cryoSPARC 2D-cleaned particles (csparc2star.py).
- `20_troubleshooting.md` / `21_error_lookup.md` — error-string lookup incl. the messages above.
- Sibling skills: **cryosparc** (2D classification / Select 2D equivalents), **vesicle-processing** (when 2D classes align to membrane/vesicle instead of protein).

---

## Sources

Read/grounded for this file:
- Live binary help: `relion_refine --help`, `relion_class_ranker --help`, `relion_particle_select --help`, `relion_star_handler --help` (captured + re-confirmed against `<RELION_BIN>`, version `5.0.0-commit-3d6c20`).
- Live label dump: `relion_refine --print_metadata_labels` (for `rlnClassScore`, `rlnPredictedClassScore`, `rlnClassDistribution`, `rlnEstimatedResolution`).
- Captured help: `.../relion5_cli_capture_20260604/help/relion_refine.txt`, `relion_class_ranker.txt`, `relion_particle_select.txt`, `relion_star_handler.txt`, `relion_display.txt`.
- Source: `.../source/relion_ver5.0/src/pipeline_jobs.cpp` (getCommands/initialise for Class2D and Select; lines ~2682–3036, 3038–3320) and `pipeline_jobs.h:234-346` (label macros).
- Docs: `.../source/relion-documents_release-5.0/source/SPA_tutorial/Class2D.rst`.
- Read-only fixture: `Class2D/job017/{job.star,note.txt}`, `Class2D/job021/run_it200_model.star`, `Select/job023/{job.star,note.txt,backup_selection.star,class_averages.star}`, `Select/job035/{job.star,note.txt}`, `Select/job058`, `JoinStar/job032/{job.star,note.txt}`, `InitialModel/job027/note.txt`, and the `Select/{side_view*,top_view*,J055_C1_C5,J62_cls_01}` aliases.
