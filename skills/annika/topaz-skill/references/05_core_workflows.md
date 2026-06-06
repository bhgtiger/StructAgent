# 05 — Core workflows

These are **validated workflows** for Topaz 0.3.20, confirmed against captured live
`--help` and a GPU smoke run (a Linux + NVIDIA GPU host, 2026-06-06). On a machine where
`scripts/topaz_env_probe.py` reports `validation_status = valid` / `ready`, fill in the
user's **real paths** and — **after explicit user confirmation** — run them. Every flag,
default, and format below matches the captured help (`topaz.<cmd>.help.txt`);
each command is labeled with its source file. Keep private data local and never run on the
user's real data without confirming first (see ref 00).

**Device note (probe-driven):** Topaz dispatches to CUDA when available. If the probe
reports Apple Silicon / no NVIDIA GPU, Topaz runs **CPU-only** (it has no MPS code path —
`topaz_mps_supported = False` [sourced 0.3.20 @ 58fe5237]); in that case pass `-d -1` to
ML commands. Defaults differ per command: `train`/`extract`/`denoise` default `-d 0`
(first GPU); `preprocess`/`normalize` default `-d -1` (CPU). See ref 02.

## A. Particle picking (the main pipeline)
```
# 1. Preprocess: downsample + normalize micrographs (default -s 1, -d -1)
topaz preprocess -s <SCALE> -d <DEVICE> -o <PROC_DIR> <MICROGRAPHS...>
#    [validated topaz 0.3.20 — captured: topaz.preprocess.help.txt]

# 2. (Train) a picking model from a few labeled particles
#    Inputs: image list (image_name<TAB>path) and coords (image_name<TAB>x_coord<TAB>y_coord)
#    -n / --num-particles = expected particles per micrograph (either -n OR --pi is required).
topaz train --train-images <IMAGE_LIST> --train-targets <COORDS> \
            -m resnet8 -n <EXPECTED_PARTICLES_PER_MIC> -r <RADIUS> -d <DEVICE> \
            --num-epochs <N> --save-prefix <MODEL_PREFIX>
#    Defaults: -m resnet8, -r 3, --num-epochs 10, --method GE-binomial, -d 0.
#    [validated topaz 0.3.20 — captured: topaz.train.help.txt]
#    GOTCHA: --save-prefix's parent DIR must already exist; topaz does NOT create it. [smoke]
#    OR skip training and use the bundled resnet16 model directly in step 3.

# 3. Extract particles (scores micrographs with the model, then picks coordinates)
#    -m default is resnet16; set -m none if inputs are already segmented
#    (log-likelihood maps). -r/--radius has NO default — supply it (or tune via --targets).
topaz extract -m <MODEL.sav|resnet16> -r <RADIUS> -d <DEVICE> \
              -o <PARTICLES.txt> <PROC_DIR>/*.mrc
#    [validated topaz 0.3.20 — captured: topaz.extract.help.txt]
#    Output columns: image_name  x_coord  y_coord  score [smoke]

# 4. (Optional) scale coords back to original pixels + export to STAR
#    -x/--up-scale UP-scales, -s/--down-scale DOWN-scales (DIFFERENT flags; both default 1).
#    --image-ext (default .mrc) is REQUIRED when converting TO star/box.
topaz convert --to star -x <UPSCALE_FACTOR> --image-ext <.mrc> -o <PARTICLES.star> <PARTICLES.txt>
#    [validated topaz 0.3.20 — captured: topaz.convert.help.txt]
```
Notes: `extract` can run directly on **segmented** maps (`-m none`) or score+pick with a
model. `extract -t/--threshold` is a **log-likelihood** termination score, **default -6**
("-6 is p>=0.0025") — it is NOT 0.5 and NOT a "score quantile"; raise it (toward 0 and
above) to be more selective. `extract -r/--radius` has **no default**; supply it directly
or let topaz tune it by passing `--targets` (search bounded by `--min-radius 5`,
`--max-radius 100`, `--step-radius 5`). `convert -t/--threshold` filters by score.
**`convert -s` = DOWN-scale, `convert -x` = UP-scale** — picking on downsampled images then
exporting needs `-x <factor>`. [validated topaz 0.3.20 — captured: topaz.extract.help.txt,
topaz.convert.help.txt]

### Validated end-to-end example (mirrors the GPU smoke run) [smoke]
This exact sequence ran on a Linux + NVIDIA GPU host (NVIDIA GPU, `-d 0`) against 3 train + 1 test
synthetic micrographs. On a CPU-only host replace `-d 0` with `-d -1`.
```
# Preprocess (downsample x4 + GMM-normalize) all micrographs into proc/
topaz preprocess -s 4 -d 0 -o proc/ mics/*.mrc

# Train one epoch with explicit train/test splits (PN objective) and save checkpoints
#    NOTE: the model/ directory must EXIST before this runs (see GOTCHA above).
mkdir -p model
topaz train -d 0 \
    --train-images train_mics/ --train-targets train_coords.txt \
    --test-images  test_mics/  --test-targets  test_coords.txt \
    -n 30 -r 8 --num-epochs 1 --method PN \
    --save-prefix model/topaz_smoke -o train.log.txt
#    -> writes checkpoint model/topaz_smoke_epoch1.sav (naming: <save-prefix>_epoch{N}.sav)

# Extract picks with the trained checkpoint
topaz extract -m model/topaz_smoke_epoch1.sav -r 8 -d 0 -o extracted.txt proc/*.mrc
#    -> extracted.txt columns: image_name  x_coord  y_coord  score
```
`--train-images`/`--test-images` accept either an image-list file or a directory (all images
loaded). `-n`/`--num-particles` (or `--pi`) is required. [validated topaz 0.3.20 — captured:
topaz.train.help.txt, topaz.extract.help.txt; behavior: smoke]

## B. Evaluate a picking model
```
topaz precision_recall_curve --predicted <PARTICLES.txt> --targets <LABELS.txt> -r <RADIUS>
#    -r/--assignment-radius is REQUIRED (max prediction-to-target match distance).
#    Optional --images {target,predicted,union} chooses which micrographs to count
#    (default target = only micrographs labeled in the targets file).
#    [validated topaz 0.3.20 — captured: topaz.precision_recall_curve.help.txt]
```

## C. 2D micrograph denoising (CPU-feasible)
```
topaz denoise -d <DEVICE> -o <DENOISED_DIR> <MICROGRAPHS...>
# -m/--model accepts MULTIPLE pretrained names (unet, unet-small, fcnn, affine; default unet);
# averaging several: -m unet unet-small. -o is a DIRECTORY; default -d 0.
# Omitting -m auto-loads the bundled pretrained model. [smoke: loaded unet_L2_v0.2.2.sav on GPU]
#    [validated topaz 0.3.20 — captured: topaz.denoise.help.txt]
```

## D. 3D tomogram denoising
```
topaz denoise3d -m unet-3d -d <DEVICE> -o <DENOISED_DIR> <TOMOGRAM.mrc>
# -m default unet-3d (also unet-3d-10a, unet-3d-20a, or a path). -o is a DIRECTORY.
# -d default -2 (multi-GPU); >=0 single GPU, -1 CPU.
#    [validated topaz 0.3.20 — captured: topaz.denoise3d.help.txt]
```

## E. Format conversion / cleanup
```
# Convert coordinates between formats. --from auto-detects; --to {coord,csv,star,json,box}.
# --image-ext (default .mrc) REQUIRED for star/box; --boxsize REQUIRED for box.
# For JSON/BOX, OUTPUT must be a DIRECTORY.
topaz convert --to star --image-ext <.mrc> -o <OUT.star> <IN.txt>
#    [validated topaz 0.3.20 — captured: topaz.convert.help.txt; smoke confirmed --to star]

# Split one particle file into per-micrograph files. positional is a SINGLE file;
# -o is a DIRECTORY; --format is {auto,coord,star} ONLY (no csv/box).
topaz split -o <OUTDIR> <ALL_PARTICLES.txt>
#    [validated topaz 0.3.20 — captured: topaz.split.help.txt]

# Cut a particle stack. positional is a SINGLE coordinates file (NOT a micrographs arg);
# point at the micrograph dir with --image-root and give the box --size.
# Optional: --image-ext (default .mrc), --resize (downsample), --metadata (.star CTF),
#           --threshold (default -inf).
topaz particle_stack <COORDS> --image-root <MICDIR> --size <BOX> -o <STACK.mrc>
#    [validated topaz 0.3.20 — captured: topaz.particle_stack.help.txt]

# Split a particle file into train/test by holding out N images. positional is the
# particle file; point at images with --image-dir. -n/--number = number of images into
# the TEST set (there is NO --test-split FRAC flag). --seed default 0.
topaz train_test_split -n <NUM_TEST_IMAGES> --image-dir <MICDIR> <PARTICLES.txt>
#    [validated topaz 0.3.20 — captured: topaz.train_test_split.help.txt]
```

## Workflow decisions to surface to the user
- **Train vs. use bundled `resnet16`:** bundled is a fast start; train when your particle
  differs from the pretrained distribution or pretrained recall is poor.
- **Downsample factor (`-s`):** trades resolution for speed/recall; affects coordinate
  scaling later (ref 04). State the assumed factor.
- **Radius / threshold:** dataset-specific. `extract -r` has no default — supply it, or let
  `extract` tune radius against `--targets`. `extract -t` defaults to -6 (log-likelihood),
  raise to be more selective.
- **Device:** GPU (CUDA) for training-heavy work; CPU OK for denoise/extract/convert. If the
  probe reports no NVIDIA GPU (e.g. Apple Silicon), pass `-d -1` (CPU-only).

Grounding: primary CLI ground truth is the captured live help
(`topaz.<cmd>.help.txt`, cited inline as `[validated topaz 0.3.20 — captured:
topaz.<cmd>.help.txt]`) plus the GPU smoke run
(cited as `[smoke]`). Conceptual/usage context: README usage blocks,
`docs/source/tutorial.md`, `docs/source/commands/*`, and
`tutorial/01_quick_start_guide.ipynb` / `02_walkthrough.ipynb`.
