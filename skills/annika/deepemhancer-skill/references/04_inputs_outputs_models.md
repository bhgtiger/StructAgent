# 04 — Inputs, outputs, models & normalization

Grounded in pinned source help text + README + the paper (rationale only). The target's live help wins for exact flags.

## Inputs: what to feed DeepEMhancer

- **File type:** `.mrc` / `.map` 3D cryo-EM volume.
- **State of the map:** the input should be a **raw map directly from refinement — unmasked and not sharpened.** Per the `-i` help: *"This map should be unmasked and not sharpened (Do not use post-processed maps, only maps directly obtained from refinement)."*
  - **Inappropriate inputs:** already post-processed, masked, B-factor-sharpened, or otherwise enhanced maps. Feeding these defeats the method and can produce misleading output.
- **Half maps (preferred when available):** provide half map 1 as `-i` and half map 2 as `-i2`. If you pass a half map to `-i`, **do not forget `-i2`** (the help calls this out explicitly).
- **Sampling rate:** read from the MRC header by default; override with `-s/--samplingRate` (Å/voxel) only if the header is wrong/missing.

## Model choice (`-p/--processingType`)

| Model | When | Notes |
|---|---|---|
| `tightTarget` (default) | General use | Sharper result than `wideTarget`. |
| `wideTarget` | When tight/highRes appear to **over-mask** or clip density | Less sharp than tight. |
| `highRes` | **Only** when overall FSC resolution **< 4 Å** | May look noisier; not for lower-resolution maps. |

`-p` is described as **ignored** when normalization mode 2 (`-m/--binaryMask`) is used (that path forces the masked model) — but this is **not a silent ignore**: passing a non-default `-p` (`wideTarget`/`highRes`) together with `-m` raises an `AssertionError` and the run fails. In mask mode, omit `-p` or pass only `-p tightTarget`. A custom `.hd5` via `--deepLearningModelPath` likewise forces `tightTarget` (assertions in `references/03`).

## Model files (`.hd5`)

Expected inside the model directory (`DEFAULT_MODEL_DIR = ~/.local/share/deepEMhancerModels/production_checkpoints`, or a `--deepLearningModelPath` directory):

- `deepEMhancer_tightTarget.hd5` — used by default; **its absence triggers the "models not found" exit**.
- `deepEMhancer_wideTarget.hd5`
- `deepEMhancer_highRes.hd5`
- `deepEMhancer_masked.hd5` — used only by `-m/--binaryMask` (mode 2).

`--deepLearningModelPath` may instead point **directly at a single `.hd5` file** (which forces `-p tightTarget`). Models are obtained via the download action (Zenodo) or provided by the site — the skill downloads them only via `setup_deepemhancer_env.sh --download-models`, **with confirmation** (`references/09`). The config probe stats these files without downloading.

## Normalization (choose at most one mode; auto otherwise)

DeepEMhancer normalizes the input before the network; the help calls normalization "crucial."

1. **Auto (default):** no `--noiseStats`, no `-m`. Params estimated automatically; *"in some rare cases, estimation may fail or be less accurate."*
2. **Mode 1 — `--noiseStats NOISE_MEAN NOISE_STD`:** supply the noise mean and std (two floats). Use when auto-normalization looks wrong and you can estimate noise statistics from a solvent region. **Mutually exclusive with `-m/--binaryMask`** — see below.
3. **Mode 2 — `-m/--binaryMask <mask.mrc>`:** a binary mask (1 = protein, 0 = solvent) used to normalize. Forces the masked model and **requires `-p tightTarget`** (do not pass another `-p`).

**Choose exactly one mode.** The source help calls `--noiseStats` "ignored if `--binaryMask` is provided," but the runtime does **not** silently ignore it: passing both `--noiseStats` and `-m` raises `AssertionError: only one of the following options can be provided: noise_stats, binary_mask` and the run aborts (`processVol.py`). So there is no "binaryMask overrides noiseStats" precedence — supplying both crashes; supplying neither is auto. (This is the same help-says-ignored-but-code-asserts trap as `-p` with `-m`; see `references/03`/`06`.)

## Outputs

- A single post-processed `.mrc`/`.map` volume at `-o`. (Output name must end `.mrc` or `.map`.)
- The output is a **post-processed map for visualization and model building** — masking-like + sharpening-like in one step. It is **not** an independent resolution measurement or a guarantee of improvement. Validate it against your own map and the science (`references/08`).
- `--cleaningStrengh` (sic) optionally removes small disconnected components ("dust"); default `-1` (off). Use cautiously — it deletes density below a relative size threshold.

## GPU / batch interplay (planning)

- `-g/--gpuIds` default `"0"`; comma-separate for multiple (`-g 0,1`); `-1` = CPU only (very slow — README cautions ~a day for CPU runs; don't recommend casually).
- `-b/--batch_size` default `8`. Lower on CUDA OOM; raise for low GPU utilization.
- **Multi-GPU caution from source:** some inputs can crash when more than one GPU is used; in that case use a single GPU. See `references/06`.

## Decision summary (planning aid)

```text
Input/model/normalization decision
1. Is the input a raw, unmasked, unsharpened map from refinement?  No -> stop; wrong input.
2. Do you have both half maps?  Yes -> -i half1 -i2 half2.   No -> -i fullmap.
3. Resolution?  < 4 A and want detail -> consider -p highRes (may be noisier).
                Over-masking with tight/highRes -> try -p wideTarget.  Else default tightTarget.
4. Normalization?  Trust auto first. Auto looks wrong + can estimate noise -> --noiseStats MEAN STD.
                   Have a good binary mask -> -m mask.mrc (forces tightTarget).
5. Models present for the chosen mode?  No -> blocked (see references/02/06).
```
