# crYOLO general-model picking → cryoSPARC extract / 2D (portable automation)

Config-driven tools to **pick particles with SPHIRE-crYOLO's general model** on
motion-corrected micrographs that already live in a cryoSPARC project, inject the
picks back via a **cryosparc-tools external job**, **Extract from Micrographs**, run
**2D Classification**, and **optimize the 2D** when classes are weak — all **without
leaving the cryoSPARC metadata model** (native micrograph↔particle linkage,
per-particle CTF). No training, no 2D templates required.

This is the executable companion to the cryoSPARC skill reference
`references/29_cryolo_picking_to_2d.md` (the workflow narrative, parameter rationale,
and validation). The crYOLO-side details (filter-matched general models, box sizing,
the CBOX re-threshold trick, config generation) live in the **crYOLO** skill reference
`11_cryosparc_picking_workflow.md`. The cryoSPARC picking/extraction/external-job
semantics live in `references/{04_picking.md,05_extraction_2d.md,23_external_jobs.md}`.

These scripts ship UNCONFIGURED. Nothing is hard-coded to a host, project, dataset,
or model — you supply all of that in one JSON config.

## Install / prerequisites — TWO environments

This bundle straddles two environments. Keep them separate; the scripts shell out
between them.

1. **cryosparc-tools interpreter** — version matched to your master (record it in the
   cryoSPARC skill's `site_config.md`). Runs the steps that talk to the master:
   `inspect`, `threshold`, `inject`, `extract`, `verify`, `class2d`. Has `numpy` and
   `cryosparc` but **not** matplotlib.
2. **crYOLO conda env** (SPHIRE-crYOLO 1.9.9, CUDA/TF, GPU) — runs the picking
   (`config`, `predict`) and the montage renderer (`make_montage.py`, which uses the
   crYOLO env's matplotlib). Activated via `source <conda>/etc/profile.d/conda.sh &&
   conda activate <env>`; the scripts do this for you from `cryolo.{conda_sh,env}`.

You also supply the **crYOLO general model `.h5`** yourself — never download weights
(licensing). Use a **filter-matched** model: `LOWPASS_gmodel_phosnet_*.h5` with
`filter: "LOWPASS"`, `JANNI_gmodel_phosnet_*.h5` with `filter: "JANNI"` (+ a JANNI
denoise model). A `negstain` model is for negative stain only.

## Credentials (mandatory)

Account email + password come **only** from the environment and are never written to
any file or echoed back:

```bash
export CRYOSPARC_EMAIL='you@lab.org'
export CRYOSPARC_PASSWORD='...'      # typed at the shell, never committed
```

The **instance license id** is not a personal secret — it goes in the config
`instance.license` (copy it from your `site_config.md`). If your tools build no longer
needs `license=`, set it to `null`.

## Configure

```bash
cp cryolo_pick.example.json cryolo_pick.json
$EDITOR cryolo_pick.json     # fill instance/project/workspace/source_job/box sizes/cryolo env
```

| Config key | Meaning |
|---|---|
| `instance.{license,host,port}` | from your cryoSPARC `site_config.md` (the example's `port: 39000` is cryoSPARC's default base port — confirm against your own `site_config.md`) |
| `project` / `workspace` | `P###` / `W###` the new jobs go in |
| `source_job` / `source_output` | the cryoSPARC exposures job + output group that is **motion-corrected AND CTF-estimated** (e.g. a Patch CTF, Curate Exposures, or an `exposure_sets` `split_0`) |
| `particle_diameter_A` | particle longest dimension (Å) — drives box-size suggestions |
| `cryolo_box_pix` | crYOLO **detection/anchor** box (~particle longest / psize, e.g. 168 px) — what `config` writes to `model.anchors`. Distinct from (and smaller than) the cryoSPARC extraction box; never reuse `box_extract_pix` here. `config` defaults to this, else derives it from `particle_diameter_A` / psize |
| `box_extract_pix` / `box_crop_pix` | cryoSPARC Extract box (~1.5–2× particle longest, FFT-friendly) / Fourier-crop output box (→ ~1.5–2 Å/px). `inspect` suggests both |
| `output_f16` | 16-bit float extract output (recommended) |
| `threshold` | crYOLO `-t` confidence at predict time |
| `target_per_image` | desired picks/image — `threshold` recommends a confidence to hit it (CBOX re-threshold, no GPU re-run) |
| `class2D_K` | number of 2D classes |
| `class2D_window_outer_A` / `class2D_min_res_align` | optional 2D optimization pair (tight circular mask + alignment high-pass) for small/low-contrast particles with a background ring; applied only with `class2d --optimize` |
| `work_dir` | scratch dir (symlinked mics, crYOLO outputs, `.npy` dumps, PNGs) |
| `cryolo.{conda_sh,env,general_model,filter,low_pass_cutoff}` | crYOLO conda activation + the filter-matched general model `.h5` |
| `montage_python` | the crYOLO env's python (used to run `make_montage.py`) |
| `lane` | default queue lane for GPU jobs (or leave null and export `CS_LANE`) |

## Workflow

```
cryoSPARC source exposures (motion-corrected + CTF)   [source_job/source_output]
  └─ inspect   ──────────►  n / pixel / shape; box-size suggestions
       └─ config  ────────►  crYOLO config JSON                      (crYOLO env)
            └─ predict ────►  symlink mics + cryolo_predict.py (GPU) (crYOLO env)
                 └─ threshold ─►  CBOX per-image distribution -> recommend a confidence
                      └─ inject ──►  external picks job (NO passthrough; location/* slots)
                           └─ extract ──►  Extract From Micrographs (GPU)
                                └─ verify ──►  Y-flip check (avg blob) + .npy dump
                                     └─ class2d ──►  2D Classification (+ optional --optimize)
                                          └─ dumpclasses ──►  cls_*.npy for the class montage
```

```bash
# 1. read-only: confirm the source + get box-size suggestions
python cryolo_pick.py inspect   --config cryolo_pick.json

# 2. crYOLO config + GPU picking (crYOLO env activation is automatic)
python cryolo_pick.py config    --config cryolo_pick.json            # writes config_cryolo.json
python cryolo_pick.py predict   --config cryolo_pick.json --confirm  # symlinks mics, runs cryolo_predict.py

# 3. choose a confidence to hit target_per_image (no GPU re-run), then inject
python cryolo_pick.py threshold --config cryolo_pick.json
python cryolo_pick.py inject    --config cryolo_pick.json --conf 0.20   # -> PICKS_JOB_UID=J###

# 4. extract (GPU), then verify localization BEFORE trusting the batch
python cryolo_pick.py extract   --config cryolo_pick.json --picks J### --confirm   # -> EXTRACT_JOB_UID=J###
python cryolo_pick.py verify    --config cryolo_pick.json --extract J###           # dumps verif_*.npy
$CRYOLO_PY make_montage.py verify --work-dir <work_dir>                            # render in the crYOLO env

#    -> AVERAGE shows a centred blob = OK. Flat/flipped? re-run inject --flip-y, then re-extract.

# 5. 2D classification (GPU); add --optimize for the tight-mask + high-pass pair
python cryolo_pick.py class2d   --config cryolo_pick.json --extract J### --confirm
python cryolo_pick.py class2d   --config cryolo_pick.json --extract J### --optimize --confirm

# 6. when the 2D job finishes: dump class averages + counts, then render the montage
python cryolo_pick.py dumpclasses --config cryolo_pick.json --class2d J###   # -> cls_imgs.npy / cls_counts.npy
$CRYOLO_PY make_montage.py class2d --work-dir <work_dir> --label J###         # render in the crYOLO env
```

## Safety

- `inspect`, `threshold`, `verify`, `dumpclasses` are read-only (no jobs queued).
- `inject` creates an external picks job (cheap; no GPU compute).
- `predict`, `extract`, `class2d` only run/queue GPU compute when you pass `--confirm`
  **and** (for extract/class2d) a lane is resolvable (`lane` in config or `CS_LANE`
  env). Without `--confirm` they print exactly what they would do (dry-run).
- Multi-user instance: only ever name a `project`/`workspace` that is yours, and
  symlink only your own micrographs into `work_dir/input_mics/`.

## Files

| File | Role |
|---|---|
| `cp_common.py` | shared config/connect/exposure/CBOX/inject helpers (env-only credentials) |
| `cryolo_pick.py` | `inspect` / `config` / `predict` / `threshold` / `inject` / `extract` / `verify` / `class2d` / `dumpclasses` |
| `make_montage.py` | crYOLO-env (matplotlib) renderer: verify avg/std/montage + 2D class-average montage |
| `cryolo_pick.example.json` | config template (copy to `cryolo_pick.json`, edit) |
