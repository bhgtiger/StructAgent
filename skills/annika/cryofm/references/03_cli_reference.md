# 03 — CLI reference (live `--help` captured 2026-10-08 in the validated site's image, commit 6448681)

Evidence labels: **[live]** = printed by the installed container on 2026-10-08; **[code]** = read at the pinned
commit (`src/cryofm/cli.py`, `src/cryofm/projects/cryofm2/{uncond_sampling,cond_sampling,sampling_helper}.py`);
**[derived]** = consequence reasoned from code, not observed. Flags not listed here do not exist.

## 1. `cfm` is a thin launcher [code + live]

- Console script `cfm = cryofm.cli:main` (`pyproject.toml`). Subcommands: `denoise` → `python -m
  cryofm.projects.cryofm2.uncond_sampling …`; `enhance` → `python -m cryofm.projects.cryofm2.cond_sampling …`.
- `parse_known_args()`: every token after the subcommand is forwarded unchanged, except `-h/--help` (and prefixes
  `--h`, `--he`, `--hel`, consumed by the stub) and the two accelerate knobs below.
- `--num_processes N` / `--num_processes=N` / `--main_process_port P` (underscores, **after** the subcommand) are
  intercepted and turn the run into `accelerate launch [--num_processes N] [--main_process_port P] -m <module>
  <rest>`. Hyphenated `--num-processes` is *not* intercepted and makes the module exit 2 (`unrecognized arguments`).
  A knob placed before the subcommand fails: `cfm: error: argument command: invalid choice: '4'`.
- Exit code = the child's. argparse errors 2; uncaught Python exceptions 1. Under `accelerate launch` the code is
  accelerate's (observed as `subprocess.CalledProcessError … returned non-zero exit status 1`).
- No `--version`, no `--device`/`--gpu` flag (device from accelerate; select GPUs with `CUDA_VISIBLE_DEVICES`), no
  pixel-size or box-size flag (pixel size comes from the MRC header of `-i1`, or `-i` for enhance).

### 1.1 `cfm --help` [live]

```text
usage: cfm [-h] {denoise,enhance} ...

CryoFM Command Line Interface

positional arguments:
  {denoise,enhance}  Available commands
    denoise          Apply denoising to cryo-EM density maps
    enhance          Apply style enhancement to cryo-EM density maps

options:
  -h, --help         show this help message and exit

Examples:
  # Denoise with single GPU
  cfm denoise -i1 half1.mrc -i2 half2.mrc -o ./output --model-dir ./model
  # Denoise with multiple GPUs
  cfm denoise --num_processes 4 -i1 half1.mrc -i2 half2.mrc -o ./output --model-dir ./model
  # Enhance with single GPU
  cfm enhance -i input.mrc -o ./output --model-dir ./model --output-tag 1
  # Enhance with multiple GPUs
  cfm enhance --num_processes 2 -i input.mrc -o ./output --model-dir ./model --output-tag 1
```

The two denoise examples **omit `--norm-grad`** and would fail with the assertion in §4 — do not copy them.

### 1.2 `cfm denoise --help` / `cfm enhance --help` [live] print only the stub

```text
usage: cfm denoise [-h]

Denoise cryo-EM density maps using CryoFM2 unconditional model. This command
wraps python -m cryofm.projects.cryofm2.uncond_sampling
```

Real flags: `python -m cryofm.projects.cryofm2.uncond_sampling --help` (§2) and `…cond_sampling --help` (§3). In a
container: `apptainer exec [--no-mount hostfs] /abs/cryofm2.sif python -m … --help` (CPU node is fine;
imports torch, takes ~10 s, prints a harmless `CUDA is not available … Disabling autocast` warning on CPU).

## 2. `cfm denoise` = `uncond_sampling.py` [live help, verbatim]

```text
usage: uncond_sampling.py [-h] [-i INPUT_PATH] [-i1 INPUT_PATH1]
                          [-i2 INPUT_PATH2] [-o OUTPUT_DIR]
                          [--mask-path MASK_PATH]
                          [--data-starfile-path DATA_STARFILE_PATH]
                          --model-dir MODEL_DIR [--no-ema] [--bf16]
                          [--patch-size PATCH_SIZE] [--batch-size BATCH_SIZE]
                          [--patch-overlap PATCH_OVERLAP] [--odeint ODEINT]
                          [--num-timesteps NUM_TIMESTEPS] [--op OP [OP ...]]
                          [--lamb-base LAMB_BASE] [--use-lamb-w]
                          [--lamb-w-max LAMB_W_MAX] [--norm-grad]
                          [--fmask-threshold FMASK_THRESHOLD]
                          [--threshold-res THRESHOLD_RES] [--nbands NBANDS]
                          [--bbox] [--spectral-mixing] [--fsc-weighting]
                          [--skip-spectral-trailing] [--debug]
                          [--log-file-path LOG_FILE_PATH] [--seed SEED]

data options:
  -i INPUT_PATH, --input-path INPUT_PATH
                        If this arg is not None, only do posterior sampling on
                        this map. (default: None)
  -i1 INPUT_PATH1, --input-path1 INPUT_PATH1
                        Input half map 1 path (default: None)
  -i2 INPUT_PATH2, --input-path2 INPUT_PATH2
                        Input half map 2 path (default: None)
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory (default: None)
  --mask-path MASK_PATH
                        Mask to control inference region (default: None)
  --data-starfile-path DATA_STARFILE_PATH
                        Particle dataset starfile path, used for compute
                        Fourier mask (default: None)

model options:
  --model-dir MODEL_DIR
                        Model directory (default: None)
  --no-ema              Disable EMA weights (default: False)
  --bf16                Use bf16 precision for fast inference (default: False)
  --patch-size PATCH_SIZE
                        Model input patch size (default: 64)
  --batch-size BATCH_SIZE
                        Batch size (default: 4)
  --patch-overlap PATCH_OVERLAP
  --odeint ODEINT
  --num-timesteps NUM_TIMESTEPS
                        Number of sampling timesteps (default: 200)
  --op OP [OP ...]      Forward operator type, can be set as [denoise, denoise
                        inpaint, non-uniform] (default: ['denoise'])
  --lamb-base LAMB_BASE
                        Likelihood gradient base step size (default: 1000.0)
  --use-lamb-w          Use decayed lamb scheduler (default: False)
  --lamb-w-max LAMB_W_MAX
                        Max weight for decayed lamb scheduler (default: 5.0)
  --norm-grad           Use normalized gradient (default: False)
  --fmask-threshold FMASK_THRESHOLD
                        Threshold for inpaint fourier mask (default: 10.0)
  --threshold-res THRESHOLD_RES
  --nbands NBANDS
  --bbox

extra options:
  --spectral-mixing
  --fsc-weighting
  --skip-spectral-trailing
  --debug
  --log-file-path LOG_FILE_PATH
  --seed SEED
```

Help-less flags have these code defaults: `--patch-overlap 32`, `--odeint euler`, `--threshold-res 10.0`,
`--nbands 64`, `--seed None`; the `store_true` flags default to False. `--model-dir` is the only required flag;
`-o` is de-facto required (missing → `TypeError … NoneType` at the first `os.path.join`). `--cfg-weight` and
`--output-tag` do **not** exist here (rejected with `unrecognized arguments`). argparse abbreviations work
(`--model` = `--model-dir`), but `--input` is ambiguous and rejected.

## 3. `cfm enhance` = `cond_sampling.py` [live help]

Identical flag set, order and defaults as §2 plus two flags (in `model options`), and `--fsc-weighting` listed before
`--spectral-mixing`:

```text
  --output-tag OUTPUT_TAG
                        Conditional model output tag, to be removed (default:
                        1)
  --cfg-weight CFG_WEIGHT
                        Classifier-free-guidance weight (default: 2.0)
```

## 4. Semantics that matter (by path) [code]

Paths: **den** = `cfm denoise` (any input); **enh-pure** = `cfm enhance -i` only; **enh-post** = `cfm enhance` with
`-i1/-i2` (± `-i`); **RELION** = `relion_wrapper.py` (re-uses the `uncond_sampling` parser).

| Flag | den | enh-pure | enh-post | RELION | Notes |
|---|---|---|---|---|---|
| `--model-dir` | ✓ | ✓ | ✓ | ✓ or `CRYOFM_MODEL_DIR` | opens exactly `<dir>/config.yaml` and `<dir>/model.safetensors`; strict load; no download |
| `-o` | ✓ | ✓ | ✓ | – (paths from STAR) | created with `exist_ok`; same-name files overwritten |
| `--norm-grad` | **required** | – | **required** | **required** | `assert cli_args.norm_grad is True, "Now we only support norm=True for flow"`, raised on the first batch after all preprocessing |
| `--use-lamb-w`, `--lamb-w-max`, `--lamb-base` | ✓ | – | ✓ | ✓ | λ_w = min(t/(1000−t), max) with `--use-lamb-w`, else 1.0; step = λ_base·λ_w·h/1000 along the unit-norm gradient |
| `--op`, `--fmask-threshold`, `--nbands`, `--data-starfile-path` | ✓ | – | ✓ | ✓ | membership tests on the list; **repeating `--op` keeps only the last list**; unknown tokens → `UnboundLocalError` |
| `--output-tag`, `--cfg-weight` | rejected | ✓ | ✓ | n/a | tag → class embedding (5 rows; ≥ 5 → index error); CFG = (1+w)·v_cond − w·v_uncond; in enh-post CFG wraps the likelihood-guided velocity |
| `--seed` | ✓ | – (ignored) | – (ignored) | ✓ | den: re-seeds torch at **every batch** with the same seed; None → fresh random seed per batch |
| `--odeint` | – (fixed Euler) | ✓ | – | – | enh-pure accepts `euler`, `rk4`, `midpoint`, `heun`, `ralston`, `midpoint_no_bar` |
| `--no-ema` | – | ✓ (no-op) | – | – | EMA shadow is rebuilt from the loaded weights, so it cannot change results |
| `--bf16` | ✓ | ✓ | ✓ | ✓ | `torch.autocast(bfloat16)` around model calls and loss; FFTs stay float32; weights stay float32 |
| `--batch-size` | ✓ | ✓ | ✓ | ✓ | patches per forward **per process**; also changes posterior results (one unit-norm gradient per batch) |
| `--patch-size`, `--patch-overlap` | ✓ | ✓ (size must stay 64) | ✓ | ✓ | model trained on 64³; enh-pure noise is hard-coded 64³ so other sizes break; overlap ≥ size → empty range |
| `--num-timesteps` | ✓ | ✓ | ✓ | ✓ | > 1000 → `ValueError`; posterior paths use integer step h = 1000 // N, so N ∤ 1000 integrates only part of the path (300 → 0.9, 400 → 0.8); use 50, 100, 125, 200, 250, 500, 1000 |
| `--mask-path` (+ `--bbox`) | ✓ | ✓ | ✓ | ✓ | mask resampled with the **input's** pixel size, binarised > 0.5; **without `--bbox` it changes nothing**; with it sampling runs only inside the bbox (+5 voxels, ≥ 64) and the rest keeps the unprocessed input; mask is never multiplied into the output |
| `--spectral-mixing`, `--skip-spectral-trailing` | ✓ | ✓ | ✓ | ✓ | MRC: paste the raw input above ≈3 Å; STAR: Blush-style trailing at FSC 1/7 unless skipped |
| `--fsc-weighting` | ✓ (two halves) | – | ✓ (two halves) | ✓ | sqrt(FSC) of the two **outputs**; wavelet Wiener filter with `non-uniform`; barrier only on rank 0 → possible multi-GPU hang |
| `--threshold-res` | inert | – | inert | inert | only feeds the unusable `keep_lowres` op |
| `--debug`, `--log-file-path` | ✓ | ✓ | ✓ | ✓ | debug writes patches/FSC/energy volumes next to outputs; the log file's directory must exist (opened before `-o` is created) |

Execution order (den): parse → logging → `Accelerator()` → `load_model` → `prepare_input` → `makedirs(-o)` → sampling.
Model errors therefore surface before input errors; `--norm-grad` and variant/command mismatches surface only at the
first model call, after resampling, FSC and (inpaint) back-projection.

## 5. Input/output matrix [code]

| Command | `-i` | `-i1` | `-i2` | Behaviour | Files in `-o` |
|---|---|---|---|---|---|
| denoise | – | ✓ | ✓ | each half sampled separately (shared FSC) | `<stem1>_external_reconstruct.mrc`, `<stem2>_…`, `avg_external_reconstruct.mrc` |
| denoise | ✓ | ✓ | ✓ | only `-i` sampled; halves give FSC; `-i` pixel size ignored | **`<stem1>_external_reconstruct.mrc`** (named after `-i1`, not `-i`) |
| denoise | ✓ | – | – | `RuntimeError: You must specify the two half map paths, either by mrc or by starfile.` | none |
| denoise | – | ✓ | – | `TypeError: expected str, bytes or os.PathLike object, not NoneType` (from `Path(None)`) | none |
| enhance | ✓ | – | – | pure conditional ODE sampling with CFG (log `Apply pure conditional inference on density map …`) | `<stem(-i)>_external_reconstruct.mrc` |
| enhance | – | ✓ | ✓ | conditional posterior sampling per half | as denoise (3 files) |
| enhance | ✓ | ✓ | ✓ | posterior on `-i`; `-i` must match `-i1` shape and pixel size (±0.005 Å) | `<stem(-i)>_external_reconstruct.mrc` |
| enhance | – | – | – | `NotImplementedError: Mode not supported: None` | none |

Stems are `Path(x).stem`: `half1.mrc` → `half1`. Two inputs with the same stem in different folders overwrite one
another. STAR inputs (`*_external_reconstruct.star`) double the suffix: `…_external_reconstruct_external_reconstruct.mrc`.

## 6. Documented commands that do not work (errata to upstream docs) [code + derived]

| Where | Problem | Working form |
|---|---|---|
| quick-start "Anisotropy correction": `--op inpaint denoise --data-starfile-path … --op denoise --norm-grad --use-lamb-w` | second `--op` replaces the first → plain `denoise`, STAR unused | one `--op denoise inpaint --data-starfile-path /abs/run_data.star` |
| quick-start "Add extra control" (EMhancer/EMReady): `cfm denoise -i map -i1 h1 -i2 h2 … --model-dir …-emhancer --output-tag 1 [--cfg-weight 0.5]` | `uncond_sampling` has no `--output-tag`/`--cfg-weight` → exit 2; even without them a 3-channel model gets 2 channels → conv shape `RuntimeError` | `cfm enhance -i map -i1 h1 -i2 h2 -o OUT --model-dir …-emhancer --output-tag 1 --op denoise --norm-grad --use-lamb-w` (EMReady: `--output-tag 0 --cfg-weight 0.5`) |
| `cfm --help` epilog denoise examples | no `--norm-grad` → `AssertionError` | add `--norm-grad --use-lamb-w` |
| likelihood-control "`--cfg-weight`: 0.3-0.7 (default 0.5)" for EMReady; HF card "default varies by model" | code default is 2.0 for every model | always pass `--cfg-weight 0.5` with emready |
| likelihood-control "High quality: 300-500 steps" | 300 and 400 integrate 0.9 / 0.8 of the flow in posterior modes | use divisors of 1000 (250, 500) |
| likelihood-control / HF card multi-GPU: `accelerate launch --num_processes=4 … python -m cryofm.projects…` | passes `python` as the training script (accelerate semantics) | `cfm denoise --num_processes 4 …` (builds `accelerate launch … -m <module>`) |
| quick-start RELION string `--threshold-res 10` | inert (only `keep_lowres`, which cannot run) | drop it |
| quick-start RELION "`--num_processes`: Number of GPUs" | the wrapper discards `--num_processes` and uses all visible GPUs | set `CUDA_VISIBLE_DEVICES` or an accelerate config |
| unconditional-sampling / v1 card `save_mrc(…, apix=1.5)` | `cryofm.core.utils.mrc_io.save_mrc` has `voxel_size=`, not `apix=` | `save_mrc(vol, path, voxel_size=1.5)` |
| likelihood-control "`--odeint` currently supports euler" | enh-pure accepts six solvers; den ignores it | — |

## 7. Site launcher additions seen on the validated site (not upstream) [live]

The validated site wraps upstream `cfm` in a launcher script: it resolves `--model-dir pretrain|emhancer|emready` (and
`cryofm2-<name>`, also the `=` form) to `<weights dir>/cryofm2-<name>`, exits 1 early if that folder lacks
`model.safetensors` + `config.yaml`, adds `--nv` only when a GPU device node exists, binds the shared file systems, and
gives the read-only image a job-local `/rwcache` for matplotlib/HF/Triton caches. Invoked as `cfm-relion` it runs the
RELION wrapper instead (§07). Everything after the subcommand still reaches upstream `cfm` unchanged, so §1–§6 apply as
written. Other sites have none of this unless they build it: there `--model-dir` must be the absolute variant folder
(`scripts/build_cfm_command.py --models <dir>`; `--shorthand` only where a launcher resolves the names).

## 8. Other entry points (not reachable through `cfm`)

- `relion/relion_wrapper.py` (not installed by pip; inside the validated site's image at `/opt/cryofm/relion/relion_wrapper.py`): accepts the full
  §2 flag set, requires the RELION STAR as the **last** argument, `--model-dir` or `CRYOFM_MODEL_DIR`, and
  relaunches itself under `accelerate launch` whenever `LOCAL_RANK`/`RANK` are unset. See [07](07_relion_integration.md).
- `scripts/test_cryofm1.py`, `scripts/prepare_cryofm1_dataset.py`: CryoFM1 benchmark tooling (needs cryofm-v1
  weights, `natten`, `relion_image_handler`); not covered by the validated install.
- Python API (`CryoFM2Uncond.load_from_safetensors`, `sample_from_fm`): unconditional generation for developers; the
  docs' snippets have the `apix=` bug above.
