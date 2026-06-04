# 08 — 3D auto-refine, Blush, continuation

## Scope
The RELION `3D auto-refine` job (`relion_refine[_mpi] --auto_refine`): gold-standard half-set refinement mechanics and every flag in the real fixture command (`Refine3D/job034`), the output file set that feeds postprocess, continuation/extension via `--continue`, Blush regularisation (5.0), memory tactics for the site's 11 GB RTX 2080 Ti cards, and the common failure modes (greyscale/handedness, stuck sampling, tight mask, scratch full, GPU OOM). All flags are grounded in the live `relion_refine --help` from the installed 5.0.0-commit-3d6c20 binary and in `src/pipeline_jobs.cpp::getCommandsAutorefineJob`.

---

## 1. What auto-refine does

`3D auto-refine` runs a single program, `relion_refine` (single rank) or `relion_refine_mpi` (>1 MPI), with `--auto_refine --split_random_halves`. It splits particles into two random halves that are refined **completely independently** and computes the gold-standard FSC between the two half-maps each iteration. Resolution is only ever derived from data the two halves do not share, which avoids self-enhancing overfitting. The algorithm raises the angular/translational sampling automatically (signal-to-noise-driven) and stops when orientations and resolution stop changing — so it needs almost no parameter tuning and is normally run once (`Refine3D.rst:6-10`).

Job-type label in `job.star`: `_rlnJobTypeLabel relion.refine3d` (confirmed in the fixture `job.star`). The pipeline process type is `PROC_3DAUTO` (`pipeline_jobs.cpp:4128`).

MPI layout: one leader (does no expectation work) plus two worker groups (one per half), so use an **odd** number of MPI ranks; the minimum is 3 (`Refine3D.rst:140`).

---

## 2. The real fixture command (job034), verbatim

From `<RELION_PROJECT_FIXTURE>/Refine3D/job034/note.txt` (NeCen/PRC1, RELION 4.0-beta project, read here by a 5.0 install — older projects are normal):

```text
`which relion_refine_mpi` --o Refine3D/job034/run \
  --auto_refine --split_random_halves \
  --i JoinStar/job032/join_particles.star \
  --ref Class3D/job033/run_it025_class002.mrc \
  --firstiter_cc --ini_high 20 \
  --dont_combine_weights_via_disc --scratch_dir /processing --pool 30 \
  --pad 2  --skip_gridding \
  --ctf --particle_diameter 180 --flatten_solvent --zero_mask \
  --oversampling 1 --healpix_order 2 --auto_local_healpix_order 4 \
  --offset_range 5 --offset_step 2 \
  --sym C1 --low_resol_join_halves 40 --norm --scale \
  --j 3 --gpu "" --pipeline_control Refine3D/job034/
```

Flag-by-flag (each grounded in `relion_refine --help` lines or `pipeline_jobs.cpp`):

| Flag (value in fixture) | Meaning (help line) | GUI option / code origin |
|---|---|---|
| `--o Refine3D/job034/run` | Output rootname | `--o ()`; `outputname + "run"` (`:4351`) |
| `--auto_refine` | Perform the 3D auto-refine procedure | `--auto_refine (false)`; added when not continue (`:4359`) |
| `--split_random_halves` | Refine two random halves completely separately | `--split_random_halves (false)`; added with `--auto_refine` (`:4359`) |
| `--i …join_particles.star` | Input particles STAR | `--i ()`; `fn_img` (`:4387`) |
| `--ref …class002.mrc` | Reference map (compulsory for 3D refine) | `--ref (None)`; `fn_ref` (`:4400`) |
| `--firstiter_cc` | CC in iter 1 (reference not on absolute scale) | `--firstiter_cc (false)`; emitted because `ref_correct_greyscale=No` (`:4406-4407`) |
| `--ini_high 20` | Low-pass the reference to 20 Å in iter 1 | `--ini_high (-1)`; from `ini_high` if >0 (`:4413-4417`) |
| `--dont_combine_weights_via_disc` | Send weight arrays over MPI net, not via disc files | `--dont_combine_weights_via_disc (false)`; emitted when `do_combine_thru_disc=No` (`:4427-4428`) |
| `--scratch_dir /processing` | Copy particle stacks to local scratch first | `--scratch_dir ()`; emitted when `do_preread_images=No` and `scratch_dir` set (`:4433-4434`) |
| `--pool 30` | Images pooled per thread task | `--pool (1)`; `nr_pool` (`:4435`) |
| `--pad 2` | Fourier oversampling factor (2 = default) | `--pad (2)`; `do_pad1=No` → `--pad 2` (`:4436-4439`) |
| `--skip_gridding` | (see note below) | from `skip_gridding=Yes` GUI option |
| `--ctf` | CTF correction inside MAP refinement | `--ctf (false)`; `do_ctf_correction=Yes` (`:4448-4450`) |
| `--particle_diameter 180` | Soft circular mask diameter (Å) on particles | `--particle_diameter (-1)` (`:4457`) |
| `--flatten_solvent` | Also mask the references | `--flatten_solvent (false)`; always added when not continue (`:4461`) |
| `--zero_mask` | Fill background with zeros (not random noise) | `--zero_mask (false)`; `do_zero_mask=Yes` (`:4462-4463`) |
| `--oversampling 1` | Adaptive oversampling order (1 = 2×) | `--oversampling (1)`; hard-set `iover=1` (`:4479-4480`) |
| `--healpix_order 2` | Initial angular sampling hp2 = 15° (GUI "7.5°" minus 1 oversampling level) | `--healpix_order (2)`; `sampling-iover` (`:4482-4489`) |
| `--auto_local_healpix_order 4` | Switch to local searches from hp4 (GUI "1.8°") | `--auto_local_healpix_order (4)`; `auto_local_sampling-iover` (`:4492-4499`) |
| `--offset_range 5` | Translation search radius (pix) | `--offset_range (6)`; `offset_range` (`:4502`) |
| `--offset_step 2` | Offset step (pix); GUI value 1 × 2^iover = 2 | `--offset_step (2)`; `offset_step * pow(2,iover)` (`:4504`) |
| `--sym C1` | Symmetry group | `--sym (c1)`; `sym_name` (`:4507`) |
| `--low_resol_join_halves 40` | Keep halves coupled below 40 Å to stop them diverging into different hands | `--low_resol_join_halves (-1)`; **hard-coded to 40** (`:4509`) |
| `--norm --scale` | Normalisation-error + intensity-scale corrections | `--norm`, `--scale`; always added when not continue (`:4510`) |
| `--j 3` | Threads per rank | `--j (1)`; `nr_threads` |
| `--gpu ""` | Use GPU, auto-assign devices (empty list) | `--gpu (false)`; `use_gpu=Yes` |
| `--pipeline_control Refine3D/job034/` | Where to drop `RELION_JOB_EXIT_*` sentinels | pipeline harness, not a refine algorithm flag |

Notes on a few flags:
- **`--skip_gridding`**: the fixture (4.0-beta GUI) emitted `--skip_gridding`. In the **5.0** binary the live help only exposes the *opposite* switch `--dont_skip_gridding (false) : Perform gridding in the reconstruction step (obsolete?)` (help line 167) — i.e. skipping gridding is now the default and `--skip_gridding` is no longer in the 5.0 help list. Treat `--skip_gridding` as a legacy/no-op token on the 5.0 binary; do not add it to new 5.0 commands. (Grounded: present in fixture note.txt; absent from live 5.0 `--help`.)
- **`--firstiter_cc` vs greyscale**: there is no `--ref_correct_greyscale` *flag*. The GUI option `ref_correct_greyscale` (`job.star`) inverts to the CLI: `ref_correct_greyscale=No` ⇒ emit `--firstiter_cc` (`:4406-4407`). If your reference came out of RELION/XMIPP and *is* on absolute greyscale, set it Yes and `--firstiter_cc` is omitted.
- **`--low_resol_join_halves`**: the GUI always hard-codes 40 (`:4508-4509`); it is not user-exposed in the auto-refine GUI. You only override it on the command line for special cases.
- **Choosing `--ref` from an InitialModel job**: an `InitialModel/jobNNN/` directory emits both `initial_model.mrc` (the final, symmetrised model) and `run_itNNN_class001.mrc` (the raw last-iteration class). For a Refine3D `--ref`, **prefer `initial_model.mrc`** — it is the canonical, symmetry-applied output. (Class3D references are instead `run_itNNN_classMMM.mrc`, e.g. the fixture's `Class3D/job033/run_it025_class002.mrc`.) Lowpass the reference with `--ini_high` (e.g. 20–60 Å) so the refine does not start biased to reference detail.
- **Setting `--particle_diameter` (Å)**: this is the soft circular mask diameter, **not** the box. Rule of thumb: the particle's **longest dimension + ~10–20 Å** margin, and it must stay **smaller than `box × pixel_size`** or the mask clips the box. It is not auto-derived; pick it from the known particle size. The fixture used 160 (initial model), 180 (refine), and 200 (Class3D) for the same complex at different stages — there is no single "right" value, so confirm it per target rather than copying another job's number.

---

## 3. Auto-sampling: the GUI "degrees" vs the `--healpix_order` integer

The GUI shows angular sampling in degrees; the program receives a HealPix order = (degrees-choice index) − `iover`, where `iover=1` (`:4482-4499`). Live help: `--healpix_order (2) : hp2=15deg, hp3=7.5deg, etc` (help line 41/202).

| GUI "Initial angular sampling" | passed as | local-search GUI "Local searches from" | passed as |
|---|---|---|---|
| 7.5° (default, ≤ octahedral sym) | `--healpix_order 2` | 1.8° (default) | `--auto_local_healpix_order 4` |
| 3.7° (high sym, e.g. I/O) | `--healpix_order 3` | 0.9° | `--auto_local_healpix_order 5` |

Tutorial guidance: for sub-octahedral symmetry use 7.5° initial / local from 1.8°; for higher symmetry use 3.7° / 0.9° (`Refine3D.rst:107-108`). The initial sampling only matters for the first few iterations — auto-refine raises it as SNR allows (`Refine3D.rst:106`).

"Use finer angular sampling faster?" (`auto_faster=Yes`) adds **two** flags: `--auto_ignore_angles --auto_resol_angles` (`:4440-4443`; help lines 162-163). Faster, but may cost final resolution — watch the late iterations (`Refine3D.rst:111-115`).

---

## 4. Masks, solvent, FSC

- **No mask** (fixture): a soft spherical mask of `--particle_diameter` Å is used; refinement FSC is unmasked-gold-standard.
- **`--solvent_mask <mask.mrc>`** (help line 24/185): user mask for the references; emitted from the GUI "Reference mask" `fn_mask` (`:4465-4467`). Values 0..1, same box/pixel as the reference (`:4148-4153`).
- **`--solvent_correct_fsc`** (help line 155): "Use solvent-flattened FSCs?" `do_solvent_fsc=Yes` (`:4469-4470`). Only valid *with* a reference mask; uses phase-randomised masked half-maps each iteration. Can raise resolution when the mask volume is small, but a **too-tight** mask inflates FSC artificially (see failures).
- `--solvent_mask2` (help line 25/186) is not in the GUI; pass it as Additional argument for e.g. non-empty icosahedral viruses (`:4154-4159`).

---

## 5. Blush regularisation (RELION 5.0)

`--blush (false) : Perform the reconstruction with the Blush algorithm.` (live help line 158). GUI: "Use Blush regularisation?" `do_blush`; emits `--blush` for both classify and auto-refine jobs (`:4203`, `:4421-4424`). Blush replaces the standard smoothness prior with a neural-network regularisation-by-denoising at every iteration (`:4203` help text). It is most useful for small / low-SNR / preferred-orientation data and for pushing past where standard refinement stalls.

- Companion flag: `--blush_skip_spectral_trailing (false)` — *"WARNING: This may inflate resolution estimates"* (help line 159). Leave it off unless you know why you need it.
- Blush is **5.0-only**; 4.0/3.1 have no Blush. The fixture (4.0-beta) command has no `--blush`. The 5.0 tutorial explicitly *skips* Blush for this high-SNR dataset (`Refine3D.rst:103`). For low-SNR/small particles, turn it on.
- Blush adds GPU memory pressure (the denoiser runs on GPU). On 11 GB cards combine with smaller `--pool` and scratch (see §8).

---

## 6. Outputs (verbatim from the fixture job dir)

Per-iteration files (`run_itNNN_*`), confirmed present in `Refine3D/job034/` for iters 000–018:

| File | Content |
|---|---|
| `run_itNNN_data.star` | Particle metadata + assigned orientations/offsets for that iter |
| `run_itNNN_optimiser.star` | Optimiser state (resume point; `--continue` target) |
| `run_itNNN_sampling.star` | Current angular/translational sampling |
| `run_itNNN_half1_model.star`, `run_itNNN_half2_model.star` | Per-half model (FSC, tau2, resolution, accuracies) — two files, one per half (`Refine3D.rst:150`) |
| `run_itNNN_half1_class001.mrc`, `run_itNNN_half2_class001.mrc` | The two independent half-maps for that iter |
| `run_itNNN_half1_class001_angdist.bild`, `…half2…` | Angular-distribution plots (ChimeraX `.bild`) per half |

Final (no `_itNNN`, written only on convergence — `Refine3D.rst:151`):

| File | Content / downstream use |
|---|---|
| `run_data.star` | Final particle alignments — input to CtfRefine/Polish (refs `10_ctfrefine_polish.md`) and to re-extraction |
| `run_optimiser.star` | Final optimiser state |
| `run_model.star` | Final joined model (final FSC/resolution) |
| `run_sampling.star` | Final sampling |
| `run_class001.mrc` | Final **joined** map (both halves combined at the last iter; resolution jumps here because all data to Nyquist is used — `Refine3D.rst:151-153`) |
| `run_half1_class001_unfil.mrc`, `run_half2_class001_unfil.mrc` | **Unfiltered** half-maps — the two inputs to **PostProcess** (refs `09_mask_postprocess_localres.md`). Pipeline node label `LABEL_REFINE3D_HALFMAP` (`pipeline_jobs.cpp:82`). |
| `run_class001_angdist.bild` | Final angular distribution (open over the map in ChimeraX) |
| `RELION_JOB_EXIT_SUCCESS` | Success sentinel **file** in the job dir (see `src/pipeline_control.h:32-35`) |
| `run.out`, `run.err` | stdout/stderr; `grep Auto run.out` shows sampling/resolution progression (`Refine3D.rst:163`) |

The two `*_unfil.mrc` half-maps are the entire reason auto-refine exists: PostProcess takes them, applies a mask, does phase-randomised FSC correction, sharpens, and reports the masked gold-standard resolution.

---

## 7. Continuation vs fresh job

`--continue run_itNNN_optimiser.star` resumes/extends an existing refinement from that iteration (help text on `--continue` is in the optimiser, exposed via GUI "Continue from here"). Construction (`:4329-4349`):

```text
relion_refine_mpi --continue Refine3D/job034/run_it018_optimiser.star \
  --o Refine3D/job050/run  --pool 30 --dont_combine_weights_via_disc \
  --scratch_dir /processing --j 6 --gpu ""
```

Mechanics and constraints:
- The filename **must** contain both `_it` and `_optimiser` or the GUI errors out (`:4336-4342`).
- On continue, the algorithm/initialisation flags are **not** re-emitted: `--auto_refine/--split_random_halves`, `--i`, `--ref`, `--firstiter_cc`, `--ini_high`, `--ctf`, `--flatten_solvent/--zero_mask`, all sampling flags, `--sym`, `--low_resol_join_halves`, `--norm/--scale` are guarded by `if (!is_continue)` (`:4357`, `:4446`, `:4458`, `:4476`). Only the output name, compute flags (`--pool`, disc-IO, scratch, `--pad`, `--auto_ignore/_resol_angles`), `--particle_diameter`, and `--blush` are re-applied. So you cannot change symmetry or CTF mode mid-continue — start fresh for those.
- Output rootname of the continued run **must differ** from the previous run; if identical the program auto-appends `_ctX` (X = iter) (`:4143-4145`). In 5.0 the `_ctXX` rootname auto-bump for *output filenames* was switched off to keep Schemes stable (`:4344-4347`), but the GUI still requires a new job dir.

**When to continue vs start fresh:**
- *Continue*: job hit a wall-clock/queue limit; you want a few more iterations at finer sampling; the run was killed cleanly. Same particles, same symmetry, same CTF.
- *Fresh*: changed particle set, box/pixel size, symmetry, mask, greyscale assumption, CTF correction, or you re-extracted. Also fresh after CtfRefine/Polish (the STAR changed).

---

## 8. Memory on 11 GB RTX 2080 Ti (2× on example RELION host)

Auto-refine's last iteration uses all frequencies to Nyquist and is the memory peak (`Refine3D.rst:141, 152-153`). On modest 11 GB cards:

- **`--pool`**: lower it. The fixture uses 30; pool batches images per thread and trades RAM/VRAM for throughput. Drop to ~5–10 if you OOM late.
- **Fewer particles/box per GPU**: assign explicit devices and run more MPI ranks so fewer particles land on each GPU, e.g. `--gpu 0:1` to use both cards; or re-extract to a smaller box (a 360 px box rescaled to 256 px is exactly what the tutorial does to cap resolution and memory, `Refine3D.rst:47-57`).
- **`--scratch_dir /processing`** (site convention; **not universal**) copies stacks to local SSD so disc I/O is not the bottleneck and the leader can stream particles; alternative is `--preread_images` (all particles into leader RAM — only for small sets, `Refine3D.rst:127-129`; help line 128/289). `do_preread_images=Yes` and a non-empty `scratch_dir` are mutually exclusive in the GUI (`:4431-4434`).
- **`--pad 1`** (GUI "Skip padding? Yes") cuts reconstruction RAM ~8× at the risk of aliasing for very tight boxes (`Refine3D.rst:124-125`). The fixture used `--pad 2`.
- **`--free_gpu_memory <Mb>`** (help line 135) leaves headroom after allocation — useful if the desktop/X server shares the card.
- **`--j`** scales CPU threads (CPU RAM), not VRAM; raise it for big final-iteration boxes (`Refine3D.rst:141`).

Site queue convention seen in the fixture `job.star` (illustration only, do not hardcode): `qsub=sbatch`, `qsubscript=<RELION_QUEUE_SCRIPT>`, `scratch_dir=/processing`, `nr_mpi=3`, `nr_threads=3`.

---

## 9. Common failures / red flags

| Symptom | Likely cause | Fix |
|---|---|---|
| Map refines to a blob / never improves; or comes out **inside-out** | Wrong greyscale, or **wrong handedness** of the reference | Set "Ref. map on absolute greyscale? = No" so `--firstiter_cc` corrects the scale (`:4161-4170`); if handedness is flipped, mirror the reference (z-flip) before refining. `--low_resol_join_halves 40` exists precisely because D/I point groups can fall into different hands (`:4508`). |
| Resolution stuck; "Auto" lines in `run.out` show sampling not advancing | Too-coarse initial sampling for the SNR, or symmetry mis-set, or particles misaligned | Confirm `--sym`; check `grep Auto run.out` (`Refine3D.rst:163`); try Blush (`--blush`) on low-SNR data; verify the input particles are actually a clean subset. |
| Reported resolution suspiciously high; FSC has a sharp artificial step | **Mask too tight** with `--solvent_correct_fsc` | Loosen the mask (more soft edge / extend), re-run PostProcess; only use solvent-flattened FSCs with a generous mask (`:4200-4202`). |
| Job dies copying to scratch; `run.err` shows write/space error | **Scratch full** (`<SCRATCH_DIR>` out of space) | Free scratch or point `--scratch_dir` elsewhere; `--keep_free_scratch <Gb>` reserves space (help line 130); or use `--preread_images` for small sets. |
| Crash in expectation with "out of memory" on GPU, usually the **final** iteration | **GPU OOM** at Nyquist | Lower `--pool`, raise MPI ranks so fewer particles/GPU, `--pad 1`, smaller box, `--free_gpu_memory`; on these 11 GB cards the last iteration is the danger point (`Refine3D.rst:141`). |
| `failsafe` error: too many zero-weight particles | bad normalisation / corrupt particles (GPU fail-safe) | `--failsafe_threshold (40)` caps allowed fail-safe particles before exit (help line 157); fix the input STAR / re-extract. |
| Job has no `RELION_JOB_EXIT_SUCCESS` file | crashed or aborted | Check for `RELION_JOB_EXIT_FAILURE` / `RELION_JOB_EXIT_ABORTED` files and read `run.err` (sentinels are files: `src/pipeline_control.h:32-35`). |

Project-context note: in this fixture, downstream MultiBody (`MultiBody/job087,089`) failed with "A GPU-function failed to execute" then a missing `run_data.star` — a reminder that a clean auto-refine `run_data.star` is the prerequisite input for multibody/flex jobs (refs `11_subtract_multibody.md`).

---

## Cross-links

- `07_initialmodel_class3d.md` — produces the reference map (`--ref`) that seeds auto-refine.
- `09_mask_postprocess_localres.md` — consumes `run_half1/2_class001_unfil.mrc` (PostProcess, LocalRes, masking).
- `10_ctfrefine_polish.md` — consumes `run_data.star`; re-refine after.
- `11_subtract_multibody.md` — multibody continues from a refine optimiser; needs `run_data.star`.
- `12_conventions_symmetry.md` — `--sym` point groups, handedness, `--print_symmetry_ops`.
- `13_helical_amyloid.md` — helical auto-refine flags (`--helix`, twist/rise).
- `14_tomo_sta.md` — tomo auto-refine (`--ios`, `--tomograms`, `--trajectories`).
- `20_troubleshooting.md`, `21_error_lookup.md` — broader failure catalog and exact error strings.
- Sibling skills (execution owned elsewhere): **mask** (build the soft mask for `--solvent_mask`/PostProcess), **chimerax** (open `*_angdist.bild`, check handedness/fit), **cryosparc** (compare to NU-refine; import poses), **cryo-flex-knowledge** (when continuous heterogeneity is blocking convergence).

---

## Sources

- Live: `relion_refine --help` (RELION 5.0.0-commit-3d6c20, `<RELION_BIN>/relion_refine`) — confirmed all `--*` flags and defaults.
- `<RELION_SKILL_BUILD_ROOT>/references/cli/relion5_cli_capture_20260604/help/relion_refine.txt`
- `<RELION_SKILL_BUILD_ROOT>/references/source/relion-documents_release-5.0/source/SPA_tutorial/Refine3D.rst`
- `<RELION_SKILL_BUILD_ROOT>/references/source/relion_ver5.0/src/pipeline_jobs.cpp` — `getCommandsAutorefineJob` (`:4315-4544`), `initialiseAutorefineJob` (`:4126-4224`), `getOutputNodesRefine` (`:48-115`).
- `<RELION_SKILL_BUILD_ROOT>/references/source/relion_ver5.0/src/ml_optimiser.h` (metadata-label and write-mode definitions, `:48-93`).
- Fixture (READ-ONLY): `<RELION_PROJECT_FIXTURE>/Refine3D/job034/` — `note.txt` (executed command), `job.star` (job options), directory listing (output filenames).
- Sentinel file names: `src/pipeline_control.h:32-35` (per environment brief).
