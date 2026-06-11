# 11 · crYOLO → cryoSPARC general-model picking (the crYOLO side)

This page is the **crYOLO half** of a "crYOLO general-model picking → cryoSPARC
extract/2D" workflow: pick particles with a SPHIRE-crYOLO general model on
motion-corrected micrographs that already live in a cryoSPARC project, then hand the
picks back to cryoSPARC for extraction and 2D classification — without ever leaving
the cryoSPARC metadata model. Everything crYOLO-side below — filter-matched general
models, box sizing into `model.anchors`, the config + predict commands, the CBOX
corner→centre math, and running in the conda env — is **VALIDATED against crYOLO
1.9.9** (the captured `--help` set, ref 03, plus a live run of this exact workflow on a
Linux + NVIDIA RTX 4090 host). The cryoSPARC-side wiring (external job, extract, 2D) is
**not** part of the crYOLO captures and is owned by the cryosparc skill — this page
points at it explicitly (see "Hand-off to cryoSPARC" below) rather than restating it.

## When this path is the right pick (decision surface)

crYOLO general-model picking is a strong **template-free** alternative to Blob Picker
when you have no 2D templates yet and the particle is reasonably well-defined: it is
often cleaner than blob picking on heterogeneous / low-contrast fields and needs no
training. Prefer Topaz once you have a clean labeled seed; prefer cryoSPARC's Template
Picker once you have good 2D classes. The general model runs out of the box with a
supplied `.h5` — **never download the weights as part of the skill** (model usage terms
are separate from the package license; ref 07). The user supplies the model file.

## Source micrographs come from cryoSPARC, fed to crYOLO as a folder

The micrographs are any cryoSPARC **exposures** output that is motion-corrected **and**
CTF-estimated (e.g. patch-motion / patch-CTF / curated / an exposure-set split). The
dose-weighted motion-corrected `.mrc` is what crYOLO reads. `cryolo_predict.py -i` takes
a **folder** (ref 03), so the standard move is to symlink the chosen micrographs into one
input dir and point `-i` at it. The cryoSPARC-side per-micrograph metadata (uid, blob
path, shape `[NY, NX]`, pixel size, exposure-group id) is read by the cryosparc-tools
side, not by crYOLO; crYOLO only ever sees the image files.

## Filter-matched general models (CRITICAL)

The 2020 PhosaurusNet general models ship as **filter-specific variants**. The filter set
in the config JSON (`-f/--filter`, ref 03) **must match the model file you pass to `-w`**:

| Model file (example name) | Config filter | Notes |
|---|---|---|
| `LOWPASS_gmodel_phosnet_*.h5` | `--filter LOWPASS` (default; `--low_pass_cutoff 0.1`) | The robust default for ordinary cryo-EM picking. |
| `JANNI_gmodel_phosnet_*.h5` | `--filter JANNI` (+ a JANNI denoise model `.h5`) | Neural-network denoising; needs `--janni_model` (ref 03). |
| `*negstain*` general model | (negative-stain) | **Negative stain only** — do not use on cryo-EM. |

**Why matching matters:** the general model was trained on micrographs pre-processed by a
specific filter, so its learned features assume that filtered input. Feeding a LOWPASS
model JANNI-denoised images (or vice versa) gives the network out-of-distribution input
and degrades picking — the box-size and threshold tuning below cannot recover a
filter mismatch. The VALIDATED run used `LOWPASS_gmodel_phosnet_202005_N63_c17.h5` with a
`--filter LOWPASS` config. (Model download URL / provenance is a soft gap; ref 05/07 — do
not advise a download without the official source.)

> `--otf` (on-the-fly filtering, filtered images not written to disk) only matters when a
> `LOWPASS`/`JANNI` filter is configured; it is **silently ignored** under `--filter NONE`
> (ref 03). Since this workflow always uses a filter-matched model, `--otf` is meaningful.

## Box sizing: particle longest dimension → `model.anchors`

The `cryolo_gui.py config` trailing positional is the **box size in pixels**, and it lands
in `model.anchors = [box, box]` (ref 03/04). Size it from the physics, not by guessing:

```
box_px  ≈  particle_longest_dimension_Å  /  pixel_size_Å·px⁻¹
```

VALIDATED example from the live run: a ~110 Å particle at 0.656 Å·px⁻¹ → ~168 px, and the
config crYOLO wrote contained `"anchors": [168, 168]`. This crYOLO box size is the
**detection** anchor; it is independent of the cryoSPARC **extraction** box (which is
larger — ~1.5–2× the particle longest dimension, FFT-friendly — and set on the cryoSPARC
side). Do not confuse the two: the crYOLO anchor sizes the detector; the cryoSPARC box
sizes the extracted particle stack.

## Configure (`cryolo_gui.py config`) — VALIDATED crYOLO 1.9.9

```bash
# Low-pass-filtered general-model config (matches a LOWPASS_* model)
cryolo_gui.py config config_cryolo.json 168 --filter LOWPASS --low_pass_cutoff 0.1
```

Positionals are exactly `config_out_path boxsize` (ref 03). Defaults that this workflow
relies on (captured `cryolo_gui.config.help.txt`): `-a/--architecture PhosaurusNet`,
`--input_size 1024` (downsizes the shorter edge; rarely changed), `-nm/--norm STANDARD`,
`max_box_per_image 700`. The VALIDATED config crYOLO actually wrote for this workflow was:

```jsonc
{
  "model": {
    "architecture": "PhosaurusNet",
    "input_size": 1024,
    "anchors": [168, 168],            // = [box, box], from the trailing positional
    "max_box_per_image": 700,
    "norm": "STANDARD",
    "filter": [0.1, "filtered_tmp/"]  // LOWPASS: [low_pass_cutoff, filtered_output_dir]
  },
  "other": { "log_path": "logs/" }
}
```

Build filter configs via the `cryolo_gui.py config -f ...` command rather than
hand-editing (ref 04). The serialized JANNI filter sub-schema is a remaining GAP (the
validated config here was LOWPASS) — for JANNI, generate it with the command.

## Predict (`cryolo_predict.py`) — VALIDATED crYOLO 1.9.9

```bash
cryolo_predict.py \
  -c config_cryolo.json \
  -w <LOWPASS_gmodel_phosnet_*.h5> \
  -i input_mics/ \
  -o out/ \
  -g 0 -t 0.3 --otf
```

Required: `-c/--conf`, `-w/--weights` (the general-model `.h5`), `-i/--input` (the symlink
folder), `-o/--output`. `-t/--threshold` default `0.3` (0–1, higher = more conservative);
`-g/--gpu` selects the GPU id (ref 03). This is the exact command shape that ran on GPU for
this workflow: ~67 s to pick 500 micrographs on an RTX 4090. Output subfolders crYOLO
writes under `-o` (ref 03/04): `EMAN/*.box`, `STAR/*.star`, `CBOX/*.cbox`,
`CRYOSPARC/`, `DISTR/`.

- **`STAR/*.star`** — thresholded particle **centres** (RELION `_rlnCoordinateX/Y`).
- **`CBOX/*.cbox`** — **ALL** detections (including below-threshold) with confidence and
  estimated size: the re-thresholdable master. **This is the file this workflow consumes.**

## CBOX is the re-thresholdable master (corner → centre math)

The `.cbox` (v1.0) columns are:

```
CoordinateX CoordinateY CoordinateZ Width Height Depth EstWidth EstHeight Confidence NumBoxes Angle
```

- `CoordinateX`/`CoordinateY` = the box **lower-left corner** (not the centre).
- `Width` = `Height` = the box size (= the `model.anchors` value).
- **Confidence is column 9** (0-indexed 8) — the field you re-threshold on.
- **Particle centre = corner + box/2** for each axis:
  `center_x = CoordinateX + Width/2`, `center_y = CoordinateY + Height/2`.
  (VALIDATED: corner `3471.9 + 84 = 3555.9` equals the matching `STAR` centre.)

**Re-threshold trick (no GPU re-run):** because CBOX holds *every* detection with its
confidence, filtering CBOX at a new confidence is **mathematically identical** to
re-running `cryolo_predict.py -t <new>`. Use it to hit a target particles/image without
touching the GPU. (VALIDATED per-image medians on the live dataset: thr 0.30 → ~9/img
(18,020 total), 0.20 → ~19/img (34,464), 0.18 → ~22/img (39,417).) Read CBOX once, then
re-filter in memory at whatever confidence the downstream 2D wants.

> **Coordinate-frame caution (verify on import).** The captures do not byte-assert
> crYOLO's absolute origin / y-axis orientation relative to a specific cryoSPARC version —
> the classic silent particle-mislocation point (ref 06). The cryosparc-side bundle does
> the mandatory one-batch Y-FLIP check (average-blob test) on first use; the crYOLO-side
> fix if it is flipped is to set `center_y_frac = 1 − (center_y / NY)` before injection.

## Run crYOLO in its conda env (CUDA / TF)

crYOLO needs its conda environment active for the CUDA / TensorFlow libraries (crYOLO
1.9.9 runs TF 1.15.5 / Keras 2.3.1, ref 03). Activate it, then run — credentials are never
involved on the crYOLO side:

```bash
source <conda>/etc/profile.d/conda.sh
conda activate <cryolo_env>
cryolo_predict.py -c config_cryolo.json -w <model.h5> -i input_mics/ -o out/ -g 0 -t 0.3 --otf
```

(The validated run loaded `libcudart` 11 and used GPU 0 on an NVIDIA RTX 4090; crYOLO is
GPU-only and has no macOS path — a probe-driven per-platform fact, ref 02. Confirm the
machine probes `supported`/`partial` and confirm with the user before running on real
data, ref 07.) The crYOLO env also carries `matplotlib` (3.4.3), which the cryosparc-tools
env does **not** — that is why the cryosparc-side verify/2D-montage rendering is run in the
crYOLO env (the cryosparc bundle dumps a `.npy`, a montage script in the crYOLO env renders
the PNG).

## Hand-off to cryoSPARC (cryosparc-side, not crYOLO)

Once you have the CBOX-derived centres in fractional micrograph coordinates, everything
downstream — injecting the picks as a cryosparc-tools **external job**, **Extract from
Micrographs**, **2D Classification**, and the verify / Y-FLIP / 2D-optimization steps — is
**cryoSPARC-side** and is owned by the cryosparc skill. Do not restate or invent those API
calls here (the cryosparc-tools external-job code, cryoSPARC parameter names, and job-type
strings are not part of the crYOLO captures). Go to:

- **`cryosparc` skill → `references/29_cryolo_picking_to_2d.md`** — the workflow brain:
  exposures → external-job inject → extract → verify → 2D (+ optimization), with the
  verified cryoSPARC parameter and job-type names.
- **`cryosparc` skill → `scripts/cryolo_pick/`** — the ready-to-run bundle
  (`cryolo_pick.py` CLI with `inspect|config|predict|threshold|inject|extract|verify|class2d|dumpclasses`,
  `cp_common.py`, `make_montage.py`, the example JSON config, and its README). Real GPU
  jobs there are gated behind an explicit `--confirm` flag **and** a lane; everything
  site/dataset-specific comes from one JSON config; credentials are environment-only.

Apply the one-batch Y-FLIP / average-blob verification (above) on first use of any new
micrograph source or model — that is the only crYOLO-side fact the cryoSPARC side depends
on for correctness.

## Remaining gaps (genuine, not deferral)

- Coordinate **origin / y-flip** convention vs. a specific cryoSPARC version — not in any
  crYOLO capture; resolved by the one-batch verification, not asserted.
- Serialized **JANNI** filter sub-schema — the validated config here was LOWPASS
  (`"filter": [0.1, "filtered_tmp/"]`); build JANNI configs with `cryolo_gui.py config -f
  JANNI ...` rather than hand-editing (ref 04).
- The cryoSPARC-tools external-job / extract / 2D API — cryoSPARC-side, see the cryosparc
  skill references above; do not reconstruct it from this page.
