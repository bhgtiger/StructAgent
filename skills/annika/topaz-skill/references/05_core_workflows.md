# 05 — Core workflows (templates only in v0)

All commands below are **placeholder templates [sourced v0.3.20]**. Do not fill in real
paths (v1) or execute (v2+) until the config session passes and the user confirms.
On a CPU-only / Apple-Silicon machine add `-d -1` to ML commands (see ref 02).

## A. Particle picking (the main pipeline)
```
# 1. Preprocess: downsample + normalize micrographs
topaz preprocess -s <SCALE> -o <PROC_DIR> <MICROGRAPHS_GLOB>

# 2. (Train) a picking model from a few labeled particles
#    Inputs: image list (image_name<TAB>path) and coords (image_name<TAB>x_coord<TAB>y_coord)
topaz train --train-images <IMAGE_LIST> --train-targets <COORDS> \
            -m resnet8 -n <EXPECTED_PARTICLES_PER_MIC> -d <DEVICE> \
            --save-prefix <MODEL_PREFIX>
#    OR skip training and use a bundled model (resnet16) directly in step 3.

# 3. Extract particles (segments + picks in one step when a model is given)
topaz extract -m <MODEL.sav|resnet16> -r <RADIUS> -t <THRESHOLD> \
              -o <PARTICLES.txt> -d <DEVICE> <PROC_DIR>/*.mrc

# 4. (Optional) scale coords back to original pixels + export to STAR
#    -x/--up-scale UP-scales, -s/--down-scale DOWN-scales (they are DIFFERENT flags).
#    --image-ext (default .mrc) is required when converting TO star/box.
topaz convert --to star -x <UPSCALE_FACTOR> --image-ext <.mrc> -o <PARTICLES.star> <PARTICLES.txt>
```
Notes: `extract` can run directly on **segmented** maps (`-m none`) or do
segment+extract with a model. `extract -t/--threshold` default 0.5 (score quantile).
`convert -t/--threshold` filters by score. **`convert -s` = DOWN-scale, `convert -x` =
UP-scale** — picking on downsampled images then exporting needs `-x <factor>`. [sourced]

## B. Evaluate a picking model
```
topaz precision_recall_curve --predicted <PARTICLES.txt> --targets <LABELS.txt> -r <RADIUS>
```

## C. 2D micrograph denoising (CPU-feasible)
```
topaz denoise -m unet -d <DEVICE> -o <DENOISED_DIR> <MICROGRAPHS_GLOB>
# average multiple pretrained models: -m unet unet-small
```

## D. 3D tomogram denoising
```
topaz denoise3d -m unet-3d -d <DEVICE> -o <DENOISED_DIR> <TOMOGRAM.mrc>
```

## E. Format conversion / cleanup
```
topaz convert --to star --image-ext <.mrc> -o <OUT.star> <IN.txt>   # --from auto-detects
topaz split -o <OUTDIR> <ALL_PARTICLES.txt>   # one file per micrograph
topaz particle_stack <COORDS> <MICROGRAPHS> -o <STACK.mrc>
topaz train_test_split --test-split <FRAC> <IMAGE_LIST>
```

## Workflow decisions to surface to the user
- **Train vs. use bundled `resnet16`:** bundled is a fast start; train when your particle
  differs from the pretrained distribution or pretrained recall is poor.
- **Downsample factor (`-s`):** trades resolution for speed/recall; affects coordinate
  scaling later (ref 04). State the assumed factor.
- **Radius / threshold:** dataset-specific; `extract` can tune radius against `--targets`.
- **Device:** GPU (CUDA) for training-heavy work; CPU OK for denoise/extract/convert.

Grounding: README usage blocks, `docs/source/tutorial.md`, `docs/source/commands/*`,
and `tutorial/01_quick_start_guide.ipynb` / `02_walkthrough.ipynb`.
