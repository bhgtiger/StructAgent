# 03 — Program / GUI-job / stage / flags / outputs master inventory

## Scope
This is the index the skill consults *before* generating any RELION command: it maps every GUI job type label (`relion.xxx` in `job.star` → `_rlnJobTypeLabel`) to the underlying `relion_*` binary, the stage it belongs to, the handful of flags that actually matter, and the real output filenames it writes. All flags below are grounded in the live installed binaries (`relion_<prog> --help` on RELION 5.0.0-commit-3d6c20 at `<RELION_BIN>`), the captured help dumps, the pinned source `src/pipeline_jobs.cpp` (`getCommands*Job`) + `src/pipeline_jobs.h` (job-label `#define`s), and real output names observed in the read-only fixture `<RELION_PROJECT_FIXTURE>`. When a column is empty in the GUI the binary uses the help-listed default; this file lists the flag string, not the GUI label. Per-stage detail lives in the stage reference files cross-linked at the bottom of each section.

---

## How the GUI maps to a binary (read this first)

- Each GUI job writes `job.star` whose `data_job` block carries `_rlnJobTypeLabel` (e.g. `relion.refine3d`). These labels are `#define`d in `pipeline_jobs.h` as `PROC_*_LABELNEW` (e.g. `PROC_3DAUTO_LABELNEW "relion.refine3d"`, line 349).
- `getCommands*Job(...)` in `pipeline_jobs.cpp` builds the literal shell command, choosing the `_mpi` binary when `nr_mpi > 1` (pattern `command="`which relion_xxx_mpi`"` else `relion_xxx`). The exact executed string is saved verbatim in the job dir's `note.txt`.
- Exit is signalled by **sentinel files** in the job dir (not exit codes): `RELION_JOB_EXIT_SUCCESS`, `RELION_JOB_EXIT_FAILURE`, `RELION_JOB_EXIT_ABORTED`, `RELION_JOB_ABORT_NOW` (`src/pipeline_control.h:32-35`). See `02_project_job_tree.md` and `20_troubleshooting.md`.
- To enumerate labels in source: `grep -n PROC_.*LABELNEW pipeline_jobs.h`; to find the binary for a job: `grep -n getCommandsXxxJob pipeline_jobs.cpp` then read for `which relion_`.

---

## MASTER TABLE

Columns: **Job label** (`_rlnJobTypeLabel`) | **Stage** | **GUI name** | **Binary** (`_mpi` variant if any) | **Key flags** | **Key outputs** | **source anchor** (`pipeline_jobs.cpp`) | **installed?**

| Job label | Stage | GUI name | Binary | Key flags | Key outputs | source `getCommands*Job` | installed |
|---|---|---|---|---|---|---|---|
| `relion.import` | Import | Import | `relion_import` | `--do_movies/--do_micrographs/--do_other`, `--optics_group_mtf`, `--angpix --kV --Cs --Q0` | `movies.star` / `micrographs.star` | `getCommandsImportJob` (1270) | yes |
| `relion.motioncorr` | Preprocess | Motion correction | `relion_run_motioncorr[_mpi]` | `--use_own`/`--use_motioncor2`, `--bin_factor`, `--patch_x/y`, `--dose_per_frame`, `--gainref`, `--gpu <ids>` | `corrected_micrographs.star`, `*.eps`, `logfile.pdf` | `getCommandsMotioncorrJob` (1513) | yes |
| `relion.ctffind` | Preprocess | CTF estimation | `relion_run_ctffind[_mpi]` | `--i`, `--ctffind_exe --is_ctffind4`, `--Box --ResMin --ResMax --dFMin --dFMax --FStep`, `--do_phaseshift` | `micrographs_ctf.star`, `logfile.pdf` | `getCommandsCtffindJob` (1750) | yes |
| `relion.manualpick` | Picking | Manual picking | `relion_manualpick` (GUI) | `--i`, particle-diameter/lowpass display opts | `*_manualpick.star` per mic, `coords_suffix_manualpick.star` | `getCommandsManualpickJob` (1879) | yes |
| `relion.autopick` | Picking | Auto-picking | `relion_autopick[_mpi]` | `--ref`/`--LoG`/`--topaz_extract`, `--particle_diameter`, `--threshold`, `--min_distance`, `--lowpass`, `--gpu` | `*_autopick.star` per mic, `autopick.star`, `logfile.pdf` | `getCommandsAutopickJob` (2053) | yes |
| `relion.extract` | Extraction | Particle extraction | `relion_preprocess[_mpi]` | `--extract --extract_size`, `--scale`, `--norm --bg_radius`, `--invert_contrast`, `--reextract_data_star --recenter` | `particles.star`, `Particles/<mic>.mrcs` | `getCommandsExtractJob` (2471) | yes |
| `relion.select` | Class select | Subset selection | `relion_display` (interactive) / `relion_class_ranker` (auto-2D) / `relion_star_handler` (split/subset) / `relion_filament_selection` | display: `--gui --i --allow_save --fn_parts`; class_ranker: `--opt --auto_select --min_score`; star_handler: `--split --nr_split` | `particles.star`, `class_averages.star`, `run_optimiser.star`, `backup_selection.star` | `getCommandsSelectJob` (2705) | yes |
| `relion.class2d` | 2D classify | 2D classification | `relion_refine[_mpi]` | `--i --o`, `--iter --K`, `--tau2_fudge`, `--particle_diameter`, `--psi_step`, `--grad`(VDAM)/EM, `--gpu`, `--j` | `run_it###_classes.mrcs`, `run_it###_data.star`, `run_it###_model.star`, `run_it###_optimiser.star` | `getCommandsClass2DJob` (3149) | yes |
| `relion.initialmodel` | Initial model | 3D initial model | `relion_refine[_mpi]` | `--grad --denovo_3dref`, `--K`, `--sym`, `--iter`, `--gpu` | `initial_model.mrc`, `run_it###_*` | `getCommandsInimodelJob` (3428) | yes |
| `relion.class3d` | 3D classify | 3D classification | `relion_refine[_mpi]` | `--ref --i`, `--K --iter`, `--tau2_fudge`, `--sym`, `--healpix_order --offset_range`, `--solvent_mask`, `--gpu` | `run_it###_class00#.mrc`, `run_it###_data/model/optimiser.star` | `getCommandsClass3DJob` (3828) | yes |
| `relion.refine3d` | 3D refine | 3D auto-refine | `relion_refine[_mpi]` | `--auto_refine --split_random_halves`, `--ref`, `--ini_high`, `--sym`, `--particle_diameter`, `--solvent_mask`, `--blush`, `--gpu` | `run_class001.mrc`, `run_half1_class001_unfil.mrc`, `run_half2_class001_unfil.mrc`, `run_data.star`, `run_optimiser.star` | `getCommandsAutorefineJob` (4315) | yes |
| `relion.multibody` | Multibody | Multi-body refine | `relion_refine[_mpi]` then `relion_flex_analyse` | refine: `--multibody_masks`, `--solvent_mask`; analyse: `--PCA_orient --do_maps --select_eigenvalue` | `run_body###*.mrc`, `analyse_*` eigenmaps, `LogFile.pdf` | `getCommandsMultiBodyJob` (4694) | yes (binary present); flex_analyse fails on this GPU (see red flags) |
| `relion.maskcreate` | Mask | Mask creation | `relion_mask_create` | `--i --o`, `--ini_threshold`, `--extend_inimask`, `--width_soft_edge`, `--lowpass --angpix`, `--denovo`, `--helix` | `mask.mrc` | `getCommandsMaskcreateJob` (4923) | yes |
| `relion.joinstar` | Utility | Join star files | `relion_star_handler` | `--combine`/`--combine_picks`, `--i "f1 f2..."`, `--check_duplicates` | `join_*.star` | `getCommandsJoinstarJob` (5002) | yes |
| `relion.subtract` | Subtraction | Particle subtraction | `relion_particle_subtract[_mpi]` | `--i <optimiser.star> --mask`, `--recenter_on_mask`, `--new_box`, `--revert`, `--data` | `particles_subtracted.star`, `Particles/*` | `getCommandsSubtractJob` (5173) | yes |
| `relion.postprocess` | Postprocess | Post-processing | `relion_postprocess` | `--i <half1_unfil> --mask`, `--angpix`, `--mtf --mtf_angpix`, `--auto_bfac`/`--adhoc_bfac`, `--low_pass` | `postprocess.mrc`, `postprocess_masked.mrc`, `postprocess.star`, `postprocess_fsc.{dat,xml,eps}`, `logfile.pdf` | `getCommandsPostprocessJob` (5297) | yes |
| `relion.localres` | Local res | Local resolution | `relion_postprocess[_mpi]` (RELION mode) or ResMap | RELION: `--locres --locres_sampling --locres_maskrad --locres_randomize_at` | `relion_locres.mrc`, `relion_locres_filtered.mrc`, `logfile.pdf` | `getCommandsLocalresJob` (5417) | `relion_localres` NOT_FOUND — local-res runs via `relion_postprocess --locres` |
| `relion.ctfrefine` | CtfRefine | CTF refinement | `relion_ctf_refine[_mpi]` | `--i --f <postprocess.star> --o`, `--fit_defocus --fit_mode`, `--fit_beamtilt --fit_aberr`, `--fit_aniso`, `--m1 --m2 --mask` | `particles_ctf_refine.star`, `logfile.pdf`, aberration `*.eps/.mrc` | `getCommandsCtfrefineJob` (6042) | yes |
| `relion.polish` | Polish | Bayesian polishing | `relion_motion_refine[_mpi]` | train: `--params2/--params3 --min_p`; polish: `--combine_frames`, `--s_vel --s_div --s_acc`, `--bfac_minfreq`, `--first_frame --last_frame` | `shiny.star`, polished `*.mrcs`; train: `opt_params_all_groups.txt` | `getCommandsMotionrefineJob` (5840) | yes (training must be single-rank — see red flags) |
| `dynamight` | Flex het | DynaMight | `relion_python_dynamight` (conda wrapper) | (python wrapper; `--fn_dynamight_exe` default `relion_python_dynamight`) | half-maps `*.dynamight.*` | `getCommandsDynaMightJob` (5566) | wrapper (conda); see `cryo-flex-knowledge` |
| `modelangelo` | Model build | ModelAngelo | `relion_python_modelangelo` (conda wrapper) | (python wrapper; `--fn_modelangelo_exe` default `relion_python_modelangelo`) | built model `*.cif` | `getCommandsModelAngeloJob` (5709) | wrapper (conda) |
| `relion.external` | Utility | External | user binary | `--in_*` node passthrough | user-defined | `getCommandsExternalJob` (6209) | n/a |

### Helical family (SPA helical processing)
| Job label | Stage | Binary | Key flags | source |
|---|---|---|---|---|
| `relion.manualpick.helixstartend` / `relion.autopick` (helix) | Picking | `relion_manualpick` / `relion_autopick` `--helix` | `--helical_tube_outer_diameter`, `--helical_tube_kappa_max`, `--helical_tube_length_min`, `--amyloid` | `getCommandsManualpickJob`/`AutopickJob` |
| `relion.extract` (helix) | Extraction | `relion_preprocess --helix` | `--helical_tubes`, `--helical_nr_asu`, `--helical_rise`, `--helical_cut_into_segments`, `--helical_outer_diameter` | `getCommandsExtractJob` (2471) |
| `relion.class2d.helicalsegments` / `relion.class3d.helicalsegments` / `relion.refine3d.helicalsegments` | 2D/3D | `relion_refine --helix` | `--helical_twist_initial`, `--helical_rise_initial`, `--helical_twist_min/max`, `--helical_rise_min/max`, `--helical_symmetry_search`, `--helical_z_percentage`, `--helical_outer_diameter`, `--ignore_helical_symmetry` | class/refine getCommands |
| (toolbox, command-line only) | Helix utils | `relion_helix_toolbox` | `--impose --cyl_outer_diameter --rise --twist`, `--check`, `--simulate_helix`, `--pdb_helix` | invoked as `relion_helix_toolbox --impose` (7538) |
| (2D inimodel) | Helix init | `relion_helix_inimodel2d` | (initial 2D model for helices) | — |

Real-space helical symmetry imposition is command-line `relion_helix_toolbox --impose` only; the refine GUI imposes it in Fourier space (`do_helix` note, line 7451). See `13_helical_amyloid.md`.

### Tomography / STA family (RELION 4.0 rewrite, full in 5.0)
| Job label | Binary | source |
|---|---|---|
| `relion.importtomo` | `relion_tomo_import_coordinates` / `relion_python_tomo_import SerialEM` | `getCommandsTomoImportJob` (6466) |
| `relion.aligntiltseries` | `relion_python_*` tilt-series align wrappers | `getCommandsTomoAlignTiltSeriesJob` (6573) |
| `relion.reconstructtomograms` | `relion_tomo_reconstruct_tomogram[_mpi]` | `getCommandsTomoReconstructTomogramsJob` (6701) |
| `relion.denoisetomo` | `relion_python_tomo_denoise` | `getCommandsTomoDenoiseTomogramsJob` (6810) |
| `relion.picktomo` | `relion_python_tomo_pick` / `relion_python_tomo_get_particle_poses` | `getCommandsTomoPickTomogramsJob` (6930) |
| `relion.excludetilts` | `relion_python_tomo_exclude_tilt_images` | `getCommandsTomoExcludeTiltImagesJob` (7017) |
| `relion.pseudosubtomo` | `relion_tomo_subtomo[_mpi]` | `getCommandsTomoSubtomoJob` (7070) |
| `relion.ctfrefinetomo` | `relion_tomo_refine_ctf[_mpi]` | `getCommandsTomoCtfRefineJob` (7172) |
| `relion.framealigntomo` | `relion_tomo_align[_mpi]` | `getCommandsTomoAlignJob` (7310) |
| `relion.reconstructparticletomo` | `relion_tomo_reconstruct_particle[_mpi]` | `getCommandsTomoReconPartJob` (7466) |

Note: `relion_prepare_subtomo` and `relion_tomo_test` are also installed. Tomo refine/class share the same `relion_refine[_mpi]` binary via the optimisation-set (`--ios`). See `14_tomo_sta.md`.

### Standalone utilities (no dedicated GUI job; used inside jobs or by hand)
| Binary | Purpose | Key flags |
|---|---|---|
| `relion_star_handler` | star surgery | `--compare`, `--select --minval/--maxval`, `--select_by_str --select_include/--exclude`, `--combine`, `--split --nr_split/--size_split`, `--operate --multiply_by/--add_to/--set_to`, `--remove_column/--add_column`, `--hist_column`, `--remove_duplicates` |
| `relion_image_handler` | per-image/map ops | `--multiply_constant`, `--lowpass/--highpass`, `--bfactor`, `--rescale_angpix/--new_box`, `--sym`, `--fsc`, `--stats`, `--shift_com`, `--invert_hand`, `--remove_nan` |
| `relion_reconstruct[_mpi]` | backprojection from a `_data.star` | `--i --o --sym --ctf --maxres --subset --class --subtract` |
| `relion_display` | interactive 2D/3D viewer + class picker | `--gui --i`, `--allow_save --fn_parts/--fn_imgs`, `--recenter`, `--scale`, `--sigma_contrast`, `--display` |
| `relion_particle_symmetry_expand` | symmetry-expand a `_data.star` | (expand poses by point group) |
| `relion_particle_reposition` | place class avgs / refs back onto micrographs | — |
| `relion_stack_create` | build/flatten particle `.mrcs` stack from star | — |
| `relion_external_reconstruct` | hook for `relion_refine --external_reconstruct` (Blush/learned priors) | (called automatically; not run by hand) |
| `relion_pipeliner` | command-line driver of the pipeline/scheduler | runs jobs, schedules |
| `relion_schemer` | run/edit Schemes (RELION 4.0+ automation) | `--scheme`, `--run`, `--add variable/operator/job/edge/fork`, `--set_var`, `--set_job_mode`, `--abort` |
| `relion` | the GUI launcher | (also `relion --version`, `relion --tomo`) |

> `convert_star` / `csparc2star.py` are **not** RELION binaries: cryoSPARC↔RELION conversion uses pyem's `csparc2star.py` (installed at `csparc2star.py`). See `16_interop_cryosparc.md` and `19_interop_coordinates.md`.

> `relion_localres` and `relion_split_stack` are **NOT_FOUND** in this install (`env/program_availability.txt`). Local-resolution is done by `relion_postprocess --locres`; stack splitting is done by `relion_star_handler --split` / `relion_stack_create`.

---

## Per-program notes (what it does / flags that matter / what it writes)

### relion_import — Import (`relion.import`)
Copies/symlinks raw movies, micrographs, or other nodes into the project and writes the optics-group metadata that everything downstream reads. The `--optics_group_mtf`, `--angpix --kV --Cs --Q0` flags seed `data_optics`. RELION 3.1+ stores acquisition params in `data_optics`, not per-particle (see `01_star_and_metadata.md`). Writes `movies.star` or `micrographs.star`. → `04_preprocessing.md`.

### relion_run_motioncorr — Motion correction (`relion.motioncorr`)
Drives RELION's own implementation or UCSF MotionCor2. **The bare `--help` aborts** (`motioncorr_runner.cpp:141 "You have to choose either UCSF MotionCor2 or RELION's own implementation"`) — you must pass `--use_own` or `--use_motioncor2`. Key flags: `--bin_factor` (e.g. 1 for K3 super-res → physical), `--patch_x/--patch_y` (anisotropic), `--dose_per_frame`, `--gainref`, `--gpu <device-ids, e.g. 0:1>` (the GPU device list; MotionCor2 path). Writes `corrected_micrographs.star`, `_rlnAccumMotion*.eps` plots, `logfile.pdf`. The fixture (`MotionCorr/job002`) wrote exactly these plus `gain.mrc`. → `04_preprocessing.md`.

### relion_run_ctffind — CTF estimation (`relion.ctffind`)
Wraps CTFFIND4/4.1 (`--ctffind_exe --is_ctffind4`) or Gctf. Core search box: `--Box 512 --ResMin 100 --ResMax 7 --dFMin --dFMax --FStep --dAst`; `--do_phaseshift` for phase plates; tomo-only `--localsearch_nominal_defocus`. Writes `micrographs_ctf.star` (joined) + per-mic diagnostics + `logfile.pdf`. → `04_preprocessing.md`.

### relion_autopick — Auto-picking (`relion.autopick`)
Three modes: template (`--ref` star/stack), Laplacian-of-Gaussian (`--LoG --LoG_diam_min --LoG_diam_max`), or Topaz wrapper (`--topaz_train`/`--topaz_extract`, exe `relion_python_topaz`). Tuning: `--threshold 0.25`, `--min_distance`, `--lowpass` (prevent Einstein-from-noise), `--particle_diameter`, `--gpu`. Helical: `--helix --helical_tube_outer_diameter`. Writes `<pickname>_autopick.star` per mic. → `05_picking_extraction.md`.

### relion_preprocess — Particle extraction (`relion.extract`)
Windows particles from micrographs. `--extract --extract_size`, `--scale` (downscale box), `--norm --bg_radius`, `--invert_contrast`. Re-extraction/recentring after refinement: `--reextract_data_star <run_data.star> --recenter`. Helical: `--helical_tubes --helical_nr_asu --helical_rise`. Also operates on a stack with `--operate_on/--operate_out`. Writes `particles.star` + `Particles/<mic>.mrcs`. → `05_picking_extraction.md`.

### relion_refine — the workhorse (class2d / inimodel / class3d / refine3d / multibody / helix / tomo)
**One binary, six job labels** — the job label is determined by flag combinations, not by a different executable:
- 2D classify: `--K N --iter --psi_step` (no `--ref`).
- Initial model: `--grad --denovo_3dref --K`.
- 3D classify: `--ref --K --healpix_order --offset_range/--offset_step --solvent_mask`.
- 3D auto-refine: `--auto_refine --split_random_halves` (no `--iter`; auto-stops at `--auto_iter_max`).
- RELION 4.0 introduced VDAM gradient optimisation (`--grad`, replaces SGD for 2D/inimodel). RELION 5.0 added Blush regularisation `--blush` (uses `relion_external_reconstruct` internally) and `--tau2_fudge_scheme`.
- Tomo/STA: `--ios <optimiser_set.star>` sets `--i/--tomograms/--ref/--solvent_mask`; subtomo flags `--normalised_subtomo --skip_subtomo_multi --ctf3d_not_squared`.
Outputs (auto-refine, confirmed in fixture `Refine3D/job034`): `run_class001.mrc`, `run_half1_class001_unfil.mrc`, `run_half2_class001_unfil.mrc`, `run_data.star`, `run_optimiser.star`, plus per-iteration `run_it###_*`. Classification writes `run_it###_class00#.mrc`/`run_it###_classes.mrcs` + `_data/_model/_optimiser.star`. → `06_class2d_select.md`, `07_initialmodel_class3d.md`, `08_refine3d.md`, `11_subtract_multibody.md`.

### relion_class_ranker — automated 2D class selection (inside `relion.select`)
Invoked by the Select job when "Automatically select 2D classes?" is on (`pipeline_jobs.cpp:2918`, `command="`which relion_class_ranker`"`). Flags as built by the GUI: `--opt <optimiser.star> --o <dir> --auto_select --fn_sel_parts particles.star --fn_sel_classavgs class_averages.star`, with `--select_min_nr_particles`/`--select_min_nr_classes` and `--min_score 0.5`. Introduced RELION 4.0. The `--train`/`--extract_subimages` options are development-only. → `06_class2d_select.md`.

### relion_mask_create — Mask creation (`relion.maskcreate`)
Binarize a map and grow a soft edge: `--i --o --ini_threshold 0.01 --extend_inimask --width_soft_edge`, optional `--lowpass --angpix` pre-filter, `--denovo --box_size --outer_radius` for a spherical/cylinder mask de novo, `--helix --z_percentage` for helical masks. Writes `mask.mrc`. The dedicated `mask` skill builds masks from atomic models via ChimeraX — prefer it when a model exists. → `09_mask_postprocess_localres.md`.

### relion_postprocess — Post-processing + local resolution (`relion.postprocess`, `relion.localres`)
Two roles. (1) Global sharpen/FSC: `--i run_half1_class001_unfil.mrc --mask --angpix --mtf --mtf_angpix --auto_bfac`(Rosenthal–Henderson) or `--adhoc_bfac -400`, `--low_pass`. (2) Local-res (since there is no `relion_localres` binary here): `--locres --locres_sampling 25 --locres_maskrad --locres_randomize_at`. Writes `postprocess.mrc`, `postprocess_masked.mrc`, `postprocess.star`, `postprocess_fsc.{dat,xml,eps}`, `logfile.pdf` (all confirmed in fixture `PostProcess/job039`). The `postprocess.star` (`--f`/`--fsc` argument) is the FSC reference consumed by CtfRefine and Polish. → `09_mask_postprocess_localres.md`.

### relion_ctf_refine — CTF refinement (`relion.ctfrefine`)
Per-particle / per-micrograph defocus and higher-order aberration fitting against a reference. Inputs: `--i <particles.star> --f <postprocess.star> --m1/--m2 <half maps> --mask`. Fit controls: `--fit_defocus --fit_mode <5-char p/m/f string, default fpmfm>`, `--fit_beamtilt`, `--fit_aberr --even_aberr_max_n`, `--odd_aberr_max_n` (trefoil), `--fit_aniso` (anisotropic mag). Single-binary OMP threading via `--j`; the `_mpi` variant parallelises over micrographs. Writes `particles_ctf_refine.star` (confirmed in fixture `CtfRefine/job044`) + aberration plots + `logfile.pdf`. → `10_ctfrefine_polish.md`.

### relion_motion_refine — Bayesian polishing (`relion.polish`)
Two-phase: **train** optimal sigma params (`--params2`/`--params3 --min_p 1000`) then **polish** (`--combine_frames --s_vel --s_div --s_acc --bfac_minfreq --first_frame/--last_frame`). Inputs `--i <particles.star> --f <postprocess.star> --m1/--m2 --mask --corr_mic <corrected_micrographs.star>`. Training writes `opt_params_all_groups.txt` (fixture `Polish/job042`); polishing writes `shiny.star` + polished `*.mrcs` (`SPA_tutorial/Polish.rst:129`). → `10_ctfrefine_polish.md`.

### relion_particle_subtract — Particle subtraction (`relion.subtract`)
Subtracts projections of everything *outside* a keep-mask from the experimental images, for focused/multibody work. `--i <optimiser.star> --mask <keep.mrc>`, optional `--recenter_on_mask --new_box`, `--data <subset.star>`, and `--revert <star>` to undo (all other options ignored when reverting). Writes `particles_subtracted.star` + `Particles/*` (fixture `Subtract/job083`). → `11_subtract_multibody.md`.

### relion_reconstruct — manual backprojection (utility)
Rebuild a map from any `_data.star` with poses: `--i --o --sym --ctf --maxres --subset 1|2 --class N`, `--subtract <map>` to subtract a model first. Useful for half-map reconstruction outside refine, sanity maps, or symmetry checks. Writes one `.mrc`. → `08_refine3d.md`, `12_conventions_symmetry.md`.

### relion_star_handler / relion_image_handler — metadata & image utilities
`relion_star_handler` is the safe way to filter/split/combine/edit star files (`--select`, `--select_by_str`, `--split --nr_split`, `--combine`, `--remove_duplicates`, `--operate --multiply_by`, `--hist_column`); pass `--ignore_optics --angpix` only for legacy 3.0-style files. `relion_image_handler` does map/image math (`--lowpass`, `--bfactor`, `--rescale_angpix --new_box`, `--sym`, `--fsc`, `--invert_hand`, `--shift_com`, `--remove_nan`). Both are non-MPI, single-process. → `01_star_and_metadata.md`, `12_conventions_symmetry.md`, `19_interop_coordinates.md`.

### relion_schemer — automation (`relion.scheme`, RELION 4.0+)
Builds and runs Schemes (the successor to RELION 3.x "scheduling"): `--scheme <dir>`, `--add variable|operator|job|edge|fork`, `--set_var`, `--set_job_mode new|continue`, `--run --run_pipeline default`, `--abort`. Replaces the brittle `relion_pipeliner --schedule` flow for on-the-fly / unattended processing. → `15_schemes_automation.md`.

---

## MPI variants — which parallelise, which must NOT

`_mpi` binaries exist for: `relion_refine`, `relion_preprocess`, `relion_run_motioncorr`, `relion_run_ctffind`, `relion_autopick`, `relion_ctf_refine`, `relion_motion_refine`, `relion_postprocess`, `relion_particle_subtract`, `relion_reconstruct`, and the tomo `relion_tomo_*` family (all confirmed in `env/program_availability.txt`). The GUI selects them when `nr_mpi > 1` (`command="`which relion_xxx_mpi`"` in each `getCommands*Job`).

Rules and gotchas:
- **relion_refine_mpi**: in 3D auto-refine, rank 0 is a leader that does no expectation work, so use **`nr_mpi = (2k)+1`** (e.g. 3, 5) to keep the two half-sets balanced; combine with `--j` threads and `--gpu`. With 2× RTX 2080 Ti (11 GB each) keep `--K`/box modest and consider `--scratch_dir /processing`, `--dont_combine_weights_via_disc`, `--pool`.
- **relion_motion_refine — training/param-estimation MUST be single-rank.** `relion_motion_refine_mpi` aborts with **"Parameter estimation is not supported in MPI mode."** (`src/jaz/single_particle/motion/motion_refiner_mpi.cpp:42,54`). This is the exact failure recorded in the fixture `Polish/job040` and `job041`. Run the **train** phase with `relion_motion_refine` (no `_mpi`, `nr_mpi=1`); only the *polishing* (`--combine_frames`) phase may use MPI.
- **relion_class_ranker, relion_mask_create, relion_star_handler, relion_image_handler, relion_import, relion_display, relion_schemer, relion_helix_toolbox** have **no MPI variant** — always single process (thread with `--j` where supported, e.g. mask_create, ctf_refine, motion_refine).
- `relion_ctf_refine` and `relion_motion_refine` use OpenMP threads (`--j`) for the heavy per-micrograph math; the `_mpi` layer only distributes micrographs.
- This site runs Open MPI 4.1.6; launch under the queue's `mpirun`/`srun`, not bare.

---

## Common failures / red flags

- **`relion_run_motioncorr --help` "aborts"** — expected: it needs `--use_own` or `--use_motioncor2` before it will print/run anything. Not a bug.
- **`relion_display` won't start (`libfltk.so.1.3: cannot open shared object file`)** in a bare/headless shell — it is an FLTK GUI binary; it needs an X/FLTK environment. Use it only for interactive class picking, or substitute `relion_class_ranker`/`relion_star_handler` for headless selection.
- **MultiBody flex analysis fails here.** Fixture `MultiBody/job087,089` died in `relion_flex_analyse` with "A GPU-function failed to execute", then the downstream job reported `MetaDataTable::read: File ...run_data.star does not exist` (the real root cause is upstream — the absent file is a *symptom*). On the 2× 2080 Ti, GPU multibody/flex steps are fragile; consider CPU or smaller boxes. See `11_subtract_multibody.md`, `20_troubleshooting.md`, `21_error_lookup.md`.
- **Polishing job shows two binaries in one run** — that is normal: train (single-rank `relion_motion_refine`) then polish (`relion_motion_refine[_mpi] --combine_frames`). If you see "Parameter estimation is not supported in MPI mode", the train phase was launched with `nr_mpi>1`.
- **No `relion_localres`** — anyone asking to "run relion_localres" should be routed to `relion_postprocess --locres`.
- **GPU memory** — 11 GB cards are modest; large `--K`, big boxes, or `--preread_images` will OOM. Use `--scratch_dir`, `--free_gpu_memory`, fewer pooled images.
- **Old project, new binary** — the fixture is a RELION 4.0-beta project read by a 5.0 install. That is supported and normal; job labels and star schemas are forward-compatible. Don't "upgrade" the user's existing job dirs.

---

## Cross-links
- Stage detail: `04_preprocessing.md`, `05_picking_extraction.md`, `06_class2d_select.md`, `07_initialmodel_class3d.md`, `08_refine3d.md`, `09_mask_postprocess_localres.md`, `10_ctfrefine_polish.md`, `11_subtract_multibody.md`, `13_helical_amyloid.md`, `14_tomo_sta.md`, `15_schemes_automation.md`.
- Metadata/labels: `01_star_and_metadata.md`; project/job tree + sentinels: `02_project_job_tree.md`; conventions/symmetry: `12_conventions_symmetry.md`.
- Interop: `16_interop_cryosparc.md`, `17_interop_cryodrgn.md`, `18_interop_chimerax_coot_phenix.md`, `19_interop_coordinates.md`.
- Triage: `20_troubleshooting.md`, `21_error_lookup.md`, `22_decision_trees.md`, overview `00_overview.md`.
- Sibling installed skills (execution owners): **mask** (model-based masks), **chimerax** / **coot** / **phenix** (model building & refinement), **cryosparc** (cryoSPARC SPA + RELION interop), **cryolo** (crYOLO picking), **cryo-flex-knowledge** (DynaMight / multibody / 3DVA heterogeneity), **structural-strategy** (what-to-do-next).

---

## Sources
- Live binaries (run during authoring): `relion_refine --version`, `relion_refine --help`, `relion_run_motioncorr --help` (aborts as documented), `relion_display --help` (FLTK load error captured), `which relion_refine relion_preprocess relion_import`.
- Captured help dumps under `references/cli/relion5_cli_capture_20260604/help/`: `relion_import.txt`, `relion_run_ctffind.txt`, `relion_autopick.txt`, `relion_preprocess.txt`, `relion_postprocess.txt`, `relion_mask_create.txt`, `relion_refine.txt`, `relion_ctf_refine.txt`, `relion_motion_refine_mpi.txt`, `relion_particle_subtract.txt`, `relion_class_ranker.txt`, `relion_star_handler.txt`, `relion_image_handler.txt`, `relion_reconstruct.txt`, `relion_helix_toolbox.txt`, `relion_schemer.txt`.
- `references/cli/relion5_cli_capture_20260604/env/program_availability.txt` (installed/NOT_FOUND list).
- Pinned source `references/source/relion_ver5.0/src/pipeline_jobs.cpp` (`getCommands*Job` line anchors quoted above) and `pipeline_jobs.h` (`PROC_*_LABELNEW` and `LABEL_*` `#define`s, lines 185–371); `src/jaz/single_particle/motion/motion_refiner_mpi.cpp:42,54` (MPI param-estimation guard); `src/pipeline_control.h:32-39` (sentinels).
- Docs source `references/source/relion-documents_release-5.0/source/SPA_tutorial/Polish.rst:129` (`shiny.star`).
- Read-only fixture `<RELION_PROJECT_FIXTURE>` — real output filenames per job type (Import/job001, MotionCorr/job002, CtfFind/job003, Extract/job016, Class2D/job017, Select/job018, InitialModel/job027, Class3D/job033, Refine3D/job034, MaskCreate/job038, PostProcess/job039, Polish/job040-042, CtfRefine/job044, Subtract/job083).
