# RELION skill — evaluation cases

Grounded in the read-only example RELION host fixture `<RELION_PROJECT_FIXTURE>` (NeCen/PRC1 nucleosome complex, processed with RELION 4.0-beta) and the installed RELION 5.0.0 binary. Each case has a question, the tool/reference the skill should use, and a reference answer with the key facts a correct response must contain. Score = fraction of **must-include** facts present, with **must-not** as hard fails.

Re-derive the ground truth at any time with `scripts/inspect_project.py`.

---

## E1 — Summarize the project state

**Q:** "What's the state of this RELION project?" (project dir given)

**Skill should:** run `python3 scripts/inspect_project.py <RELION_PROJECT_FIXTURE>`; read `02_project_job_tree.md`.

**Must include:**
- It's a full SPA pipeline; `default_pipeline.star` lists ~71 processes; ~67 succeeded, **4 failed**.
- The 4 failures are `Polish/job040`, `Polish/job041`, `MultiBody/job087`, `MultiBody/job089`.
- One optics group; working pixel size **1.06 Å** (super-res original **0.53 Å**), 300 kV, Cs 2.7.
- Processed with RELION 4.0-beta, read by the 5.0 install (older project is fine).

**Must not:** claim everything succeeded; invent extra optics groups; hardcode that the fixture is editable.

---

## E2 — Diagnose the Polish failure

**Q:** "Why did Polish/job040 fail?"

**Skill should:** `inspect_project.py <proj> Polish/job040`; read `10_ctfrefine_polish.md` + `21_error_lookup.md`.

**Must include:**
- Real error: **"Parameter estimation is not supported in MPI mode"** (`relion_motion_refine_mpi`).
- Cause: the Bayesian-polishing **training / "train optimal parameters"** run (`--params3 --min_p --eval_frac`) was launched with MPI (>1 rank); training must be **single-rank**.
- Fix: run the train step without `mpirun` / with `nr_mpi = 1` (the non-MPI `relion_motion_refine` binary); the later *apply/polish* step can use MPI.
- The `MPI_ABORT` / errorcode-1 block is noise, not the cause. (Note: job040's log starts straight at the real error; the X11 `No protocol specified` noise line appears in **job041**, the sister job — don't assume every failed run.err has an X11 line.)

**Strong bonus:** the fixture's own `Polish/job042` is the **succeeded** single-rank version of the same training job (ran non-MPI `relion_motion_refine`, produced `opt_params_all_groups.txt`) — cite it as proof the fix works.

**Must not:** blame the input files, GPU, or scratch; recommend re-running with the same MPI training settings.

---

## E3 — Root cause vs symptom (MultiBody)

**Q:** "MultiBody/job087 says a STAR file doesn't exist — what's wrong?"

**Skill should:** `inspect_project.py <proj> MultiBody/job087`; read `11_subtract_multibody.md` + `20_troubleshooting.md`.

**Must include:**
- The visible `relion_flex_analyse ... run_data.star does not exist` is a **downstream symptom**.
- The **root cause** earlier in `run.err` is **"A GPU-function failed to execute"** — the multi-body refine failed on GPU, so the data STAR was never written.
- Likely GPU OOM on the 11 GB RTX 2080 Ti cards; fix by reducing particles/box per GPU, `--pool`, `--free_gpu_memory`, checking `nvidia-smi`.

**Must not:** tell the user to just recreate the missing STAR; stop at "file not found".

---

## E4 — Optics / pixel size

**Q:** "What does the data_optics block tell me, and which pixel size do I use?"

**Skill should:** read `01_star_and_metadata.md` + `12_conventions_symmetry.md`; show the real optics line.

**Must include:**
- `rlnMicrographOriginalPixelSize 0.53` = super-resolution detector sampling; `rlnMicrographPixelSize 1.06` = working (2× binned) pixel size.
- Particle/refinement work uses the **image/binned** pixel size (1.06 Å); original matters for motion correction / re-extraction.
- 300 kV, Cs 2.7 mm, amplitude contrast 0.1, MTF `mtf_k3_standard_300kV_FL2.star`.
- Mixing the two pixel sizes is a common resolution/interop bug.

---

## E5 — Expected outputs and continuation

**Q:** "Refine3D/job034 — what should it have produced, and can I continue it?"

**Skill should:** `inspect_project.py <proj> Refine3D/job034`; read `08_refine3d.md`.

**Must include:**
- Auto-refine outputs: `run_data.star`, `run_optimiser.star`, `run_model.star`, `run_half1_class001_unfil.mrc` + `run_half2_...`, `run_class001.mrc`, per-iteration `run_it0NN_*`, angdist `.bild`.
- The job succeeded (RELION_JOB_EXIT_SUCCESS present); command used `--auto_refine --split_random_halves --sym C1 --ini_high 20`, ref = `Class3D/job033/run_it025_class002.mrc`.
- Continuation: `--continue run_itNNN_optimiser.star` resumes/extends — to a **new** output rootname, never overwriting job034.

**Must not:** suggest pointing `--o` at the existing job034 rootname; claim half-maps are missing.

---

## E6 — Export to cryoDRGN (interop)

**Q:** "How was this exported to cryoDRGN, and how would I redo it?"

**Skill should:** read `17_interop_cryodrgn.md`; inspect `cryodrgn/RL_rf075_box110/`.

**Must include:**
- Folder name decodes as ReLion refine job **075**, box **110**; contents `pose.pkl`, `ctf.pkl`, `particles_110.mrcs`, and a `z10_n50` train_vae run (zdim 10).
- Pattern: re-extract/downsample to box 110 → `cryodrgn parse_pose_star run_data.star -D 110 --Apix <A>` → `cryodrgn parse_ctf_star ... -D 110 --Apix <A> --kV 300 --cs 2.7 -w 0.1` → `cryodrgn train_vae particles_110.mrcs --poses pose.pkl --ctf ctf.pkl --zdim 10`.
- Use a **clean consensus** refinement; pose/ctf `.pkl` must match the exact stack/box/Apix; cryoDRGN is in a conda env (not base PATH).

---

## E7 — Generate an auto-refine command (execution, tier G→X)

**Q:** "Give me a 3D auto-refine command for these particles."

**Skill should:** read `08_refine3d.md` + `site_config.md`; reconcile flags against `relion_refine --help`.

**Must include:**
- Required, real flags only: `--o <NEW/path/run> --i <particles.star> --ref <ref.mrc> --auto_refine --split_random_halves --ini_high <A> --particle_diameter <A> --sym <C1...> --flatten_solvent --zero_mask --ctf --pool 30 --j <threads> --gpu ""`.
- Output rootname is **new**; never the fixture.
- Default to **dry-run** (`scripts/run_relion.sh -- ...`); ask the missing inputs rather than guessing; state MPI/thread/GPU from `site_config.md` (e.g. 3 MPI × 3 threads here) but ask to confirm.

**Must not:** invent flags; auto-launch without explicit approval; write into the fixture.

---

## Scoring notes

A passing skill response cites the right reference file(s), runs `inspect_project.py` for diagnosis cases, gets every **must-include** fact, hits no **must-not**, and respects the read-only/execution tiers from `SKILL.md`.
