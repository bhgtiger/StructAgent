# 04 — Inputs, outputs, models & normalization

Grounded in pinned source help text + README + the paper (rationale only). The target's live help wins for exact flags.

## Inputs: what to feed DeepEMhancer

- **File type:** `.mrc` / `.map` 3D cryo-EM volume.
- **State of the map:** the input should be a **raw map directly from refinement — unmasked and not sharpened.** Per the `-i` help: *"This map should be unmasked and not sharpened (Do not use post-processed maps, only maps directly obtained from refinement)."*
  - **Inappropriate for default normalization:** masked maps; sharpened or previously enhanced maps remain unsuitable. The README documents a special mask-normalization mode for masked input when raw maps cannot be recovered; see the limited fallback below.
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
1. Prefer raw, unmasked, unsharpened refinement maps. Sharpened/enhanced -> stop.
   Only masked input available -> assess the documented mode-2 fallback below.
2. Do you have both half maps?  Yes -> -i half1 -i2 half2.   No -> -i fullmap.
3. Resolution?  < 4 A and want detail -> consider -p highRes (may be noisier).
                Over-masking with tight/highRes -> try -p wideTarget.  Else default tightTarget.
4. Normalization?  Trust auto first. Auto looks wrong + can estimate noise -> --noiseStats MEAN STD.
                   Have a good binary mask -> -m mask.mrc (forces tightTarget).
5. Models present for the chosen mode?  No -> blocked (see references/02/06).
```

## Normalization tutorial caveat (checked 2026-09-07)

The [upstream usage guide](https://github.com/rsanchezgarc/deepEMhancer/blob/961f028ca609017990de4473ab368cf1787e8282/README.md#about-the-normaliztion) warns that automatic solvent-shell estimation can fail for hollow or fibrous specimens. Prefer raw half maps; if shell statistics are unreliable, measure a genuinely solvent-only region and supply its mean/SD. Do not copy the README's example statistics to another map.

A **masked but unsharpened** input has a documented fallback through mode 2 (`-m`) and `deepEMhancer_masked.hd5`, when the preferred raw input is unavailable. Upstream discourages it when mode 1 is possible. This exception does not endorse feeding sharpened/enhanced maps into the network. Confirm the binary mask's grid and protein/solvent labels, omit a non-default `-p`, and do not combine with `--noiseStats`. Compare recovered and missing density against the input; ligands and post-translational modifications were absent from training and require particular scrutiny. This is source-backed guidance, not new local validation.
