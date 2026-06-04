---
name: relion
version: 0.1.0
description: >
  Diagnose, run, and interoperate with RELION cryo-EM workflows. Use when RELION context
  is explicit: project/job trees, default_pipeline.star, job.star, run.out/run.err,
  RELION_JOB_EXIT_* sentinels, data_optics/STAR metadata, failed Refine3D/Class2D/CtfRefine/
  Polish jobs, GUI-job to relion_* command mapping, guarded relion_*/sbatch generation or
  execution, and conversions with cryoSPARC/pyem, cryoDRGN, maps/half-maps/masks, or picker
  formats. Do not trigger on generic refine/classify/mask/particle requests without RELION
  context, or for native cryoSPARC processing.
---

# RELION

Execution, diagnosis, and file-conversion assistant for RELION **5.0** single-particle, helical, and tomography workflows. Built against a RELION 5.0.0 command-help capture and real project-tree fixture; configure each live host before execution.

This skill does three jobs:
1. **Interpret** a RELION project — walk the job tree, read STAR/log/sentinel files, explain job state and failures.
2. **Run** RELION — map GUI jobs to `relion_*` commands, generate exact command lines reconciled against the installed `--help`, and (when explicitly asked) launch them.
3. **Convert** RELION files for other programs — cryoSPARC, cryoDRGN, ChimeraX/Coot/Phenix, and picker formats.

---

## Execution & safety contract

This skill is allowed to **generate and launch commands**, including queue submissions. Power comes with a strict contract — follow it on every task.

**Tiers of action** (escalate only with the stated permission):

| Tier | Examples | Permission needed |
|---|---|---|
| **R — Read-only inspection** | `scripts/inspect_project.py`, reading STAR/log/sentinel files, `relion_star_handler --i x.star` *count/compare/hist*, `relion_image_handler --i map.mrc --stats`, `--print_metadata_labels` | None. Default. Never writes into a project. |
| **G — Generate** | Print an exact `relion_*` / `sbatch` command or a `job.star`, **without running it** | None. Always show the command and the inputs it reads before offering to run. |
| **W — Write/convert** | Produce new files *outside* the source project (a converted STAR, a mask, an exported map), `relion_star_handler` writes, conversions | Confirm the **output path** first. Never overwrite an input. |
| **X — Execute compute** | `relion_refine_mpi`, `relion_motion_refine`, `sbatch refine.sh`, anything that consumes GPU/queue time or writes into a job directory | **Explicit per-action approval.** Must have a valid `site_config.md`. Echo the full command and where it writes; wait for "yes". |

**Hard rules**
- **Never guess paths.** Missing input STAR, map, mask, or reference → *fail loudly and ask*. Do not auto-pick "the most recent file." (Same failure contract as the phenix skill.)
- **Treat any existing RELION project as read-only by default.** Do not edit `default_pipeline.star`, existing `job.star`, STAR outputs, or delete job folders / `Trash/` unless the user explicitly approves that exact write. Any user-provided validation fixture is **read-only** unless the user explicitly says otherwise.
- **Continue, don't clobber.** RELION continuation (`--continue ..._optimiser.star`) and new jobs write to *new* output rootnames. Never point `--o` at an existing job's rootname unless the user says so.
- **Use the project's own conventions.** If a job's `note.txt` / `job.star` shows the site's queue script, MPI/thread counts, and scratch dir, prefer those over invented defaults — see `site_config.md`.
- **Prefer `--dry-run`.** `scripts/run_relion.sh` defaults to printing, not executing. Drop the dry-run only after the user approves the printed command.
- **Reconcile before emitting flags.** Do not invent flags. Every command must trace to the installed `--help` — bundled under `references/cli/relion5_cli_capture_20260604/help/` (RELION 5.0.0) — or to `src/pipeline_jobs.cpp`. When unsure, or on a different RELION version, run `relion_<prog> --help` live and read it; the live binary is always the final authority.

---

## First response rule

Do **not** load the whole corpus. Pick the smallest relevant file(s) from `references/` and answer. Routing is below.

For a **project/job diagnosis**, the fastest start is almost always:
```bash
python3 scripts/inspect_project.py /path/to/relion/project        # read-only summary
python3 scripts/inspect_project.py /path/to/relion/project Class3D/job033   # one job, deep
```
Then read the relevant stage reference and `20_troubleshooting.md` / `21_error_lookup.md`.

For an **error string**, start with `21_error_lookup.md`, then `20_troubleshooting.md`.

## Site config rule

Before any environment-dependent action — generating a queue command, launching a job, recommending MPI/thread/GPU counts, or claiming a program is/n't installed — **read `site_config.md` at the skill root.** It records the RELION install path/version, MPI launcher, GPU backend, queue system + submit script, scratch dir, external-tool envs (pyem, cryoDRGN, Topaz), and the permission level the user has granted on this machine.

**Configuring a host (portable — do this once per machine):**
- If `site_config.md` is the unconfigured template (its title says "UNCONFIGURED TEMPLATE"), or its `Host:` does not match the current `hostname`, it is not valid for this machine. Configure it:
  ```bash
  bash scripts/check_env.sh                                              # read-only: what's installed
  bash scripts/configure_site.sh --apply --save                         # generate site_config.md for THIS host
  bash scripts/configure_site.sh --apply --save --project /path/to/proj # also scrape queue/scratch from a job.star
  ```
- `configure_site.sh` auto-detects RELION/MPI/GPU/Python/scheduler/interop tools and, with `--project`, scrapes `qsub`/`qsubscript`/`queuename`/`scratch_dir` from a real `job.star`. `--save` keeps a per-host copy under the `configs/` directory using the hostname. Fill any remaining `TODO` fields by hand, then confirm with the user.

## Version awareness

The skill targets **RELION 5.0**. Real projects are often older: the validation fixture was processed with **RELION 4.0-beta** and its `default_pipeline.star` is STAR `version 30001`. RELION 3.1+ STAR files use `data_optics`; pre-3.1 files are auto-upgraded on read (manual: `relion_convert_star`). Flag for the user when behavior is version-specific (Blush/DynaMight/ModelAngelo and the modern tomo pipeline are 5.0; VDAM/Schemes/class-ranker are 4.0+; optics groups are 3.1+). Anchor behavior claims to the installed binary, not a release name.

---

## Reference routing

**Data model & literacy (highest-leverage, read these first for any "what is this file" question):**
- STAR syntax, `rln*` label vocabulary, `data_optics`/optics groups, parser/writer behavior → `references/01_star_and_metadata.md`
- Project graph: `default_pipeline.star`, `job.star`/`run.job`/`note.txt`, `run.out`/`run.err`, `RELION_JOB_EXIT_*` sentinels, aliases, `Trash/` → `references/02_project_job_tree.md`
- Program ↔ GUI-job ↔ stage ↔ flags ↔ outputs map (the CLI inventory) → `references/03_cli_inventory.md`
- Euler angles, origins/shifts, symmetry (C/D/I1↔I2), pixel-size issues, interop conventions → `references/12_conventions_symmetry.md`

**SPA workflow stages:**
- Overview / project structure / version map → `references/00_overview.md`
- Import, motion correction, CTF estimation (EER, dose) → `references/04_preprocessing.md`
- Auto/manual picking, extraction → `references/05_picking_extraction.md`
- 2D classification, class ranker, Select → `references/06_class2d_select.md`
- Initial model (VDAM), 3D classification → `references/07_initialmodel_class3d.md`
- 3D auto-refine, Blush, continuation from optimiser → `references/08_refine3d.md`
- Mask create, postprocess (FSC/sharpening), local resolution → `references/09_mask_postprocess_localres.md`
- CTF/aberration refinement, Bayesian polishing → `references/10_ctfrefine_polish.md`
- Particle subtraction, multi-body, flex_analyse → `references/11_subtract_multibody.md`

**Other workflows (first-class):**
- Helical / filament / amyloid → `references/13_helical_amyloid.md`
- Tomography / subtomogram averaging (RELION 5) → `references/14_tomo_sta.md`
- Schemes / on-the-fly automation / `relion_it.py` → `references/15_schemes_automation.md`

**File conversion / interop:**
- RELION ↔ cryoSPARC (csparc2star/pyem, conventions) → `references/16_interop_cryosparc.md`
- RELION → cryoDRGN (parse_pose_star/parse_ctf_star, downsample) → `references/17_interop_cryodrgn.md`
- RELION → ChimeraX / Coot / Phenix (maps, half-maps, masks, pixel size/origin) → `references/18_interop_chimerax_coot_phenix.md`
- Picker / coordinate formats (crYOLO, Topaz, EMAN, manual/auto-pick STAR) → `references/19_interop_coordinates.md`

**Diagnosis:**
- Failure-triage methodology + common failure modes → `references/20_troubleshooting.md`
- Exact error-string → cause/fix lookup → `references/21_error_lookup.md`
- "What next?" / "which branch?" decision trees → `references/22_decision_trees.md`

## Scripts

- `scripts/configure_site.sh` — **the portable "configure this machine" step.** Probes the host and writes a per-host `site_config.md` (and a hostname-specific config with `--save`); `--project <dir>` scrapes queue/scratch from a real `job.star`. Run once per machine.
- `scripts/check_env.sh` — read-only environment probe; reports RELION path/version, MPI, GPU, queue, and what to write into `site_config.md`.
- `scripts/inspect_project.py` — **read-only** RELION project-tree diagnostic. Walks jobs, reads `default_pipeline.star`, sentinels, tails `run.err`, parses `data_optics`, summarizes job state. The first tool to reach for on any diagnosis.
- `scripts/run_relion.sh` — execution wrapper. `--dry-run` by default; prints the resolved env and exact command; only executes after the flag is dropped. Sources the RELION env from `site_config.md`.
- `scripts/star_min.py` — dependency-free STAR reader used by `inspect_project.py`; also handy for quick field extraction.

## Lessons

See `lessons.md` for accumulated, version-stamped gotchas. Append new ones under "Pending Merge" (the `distill-session` skill manages promotion).
