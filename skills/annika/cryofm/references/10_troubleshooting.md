# 10 — Troubleshooting (symptom → cause → check → fix)

Read the **last line** of the traceback first. Under `accelerate launch` (multi-GPU, RELION wrapper) the last line
is a wrapper (`subprocess.CalledProcessError … returned non-zero exit status 1.` or torch-elastic `failed (exitcode:
1)`): scroll up to the child's own traceback. Messages marked [template] were assembled from the pinned library
sources; exact live text may differ in numbers and wrapping. [live] = observed on the validated site 2026-10-08.

## 1. Launch and arguments

| Symptom | Cause | Fix |
|---|---|---|
| `uncond_sampling.py: error: unrecognized arguments: --output-tag 1` (or `--output-tag 0 --cfg-weight 0.5`), exit 2 | the quick-start "Add extra control" command uses `cfm denoise` | `cfm enhance -i … -i1 … -i2 … --model-dir …-emhancer --output-tag 1 --op denoise --norm-grad --use-lamb-w` |
| `… error: unrecognized arguments: --num-processes 4` | hyphen spelling is forwarded to the module | `--num_processes 4` (underscores), after the subcommand |
| `cfm: error: argument command: invalid choice: '4' (choose from 'denoise', 'enhance')` | `--num_processes` placed before the subcommand | move it after `denoise`/`enhance` |
| `… error: the following arguments are required: --model-dir` | — | add `--model-dir <variant dir>` |
| `cfm denoise --help` shows only `usage: cfm denoise [-h]` [live] | launcher stub consumes `-h` | `python -m cryofm.projects.cryofm2.uncond_sampling --help` (03) |
| `TypeError: expected str, bytes or os.PathLike object, not NoneType` right after model loading | `-o` missing (`os.path.join(None, …)`) or `-i2` missing (`Path(None)`) | add `-o /abs/new_dir` / both half maps |
| `RuntimeError: You must specify the two half map paths, either by mrc or by starfile.` | `cfm denoise` with `-i` only | use `cfm enhance -i` (style only) or supply the halves |
| `NotImplementedError: Mode not supported: None` | `cfm enhance` with no inputs; `Mode not supported: classification` = STAR without `half1/half2` and without FSC | give `-i` and/or halves; RELION: Refine3D only |
| `FileNotFoundError: [Errno 2] No such file or directory: 'accelerate'` | `--num_processes` given but `accelerate` not on PATH (env not activated) | activate the env / run inside the container |
| `Error while finding module specification for 'cryofm.projects.cryofm2.uncond_sampling'` | the `accelerate` found belongs to another Python | same env for `cfm` and `accelerate` |

## 2. Model directory and weights

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: file "<abs>/config.yaml" does not exist` (mmengine) | wrong `--model-dir` or missing config | point at `…/cryofm2-pretrain` etc. (or the launcher shorthand `pretrain` where one exists) |
| `cfm: --model-dir … has no model.safetensors + config.yaml`, exit 1 [validated site's launcher pre-check] | weights folder incomplete | re-download the variant ([02 §1.2](02_install_and_environment.md)) or run the site's fetch/verify script |
| `AttributeError: 'ConfigDict' object has no attribute 'z_scale'` | `--model-dir` = HF repo root (manifest `config.yaml`) | use a variant subfolder |
| `FileNotFoundError: No such file or directory: "<dir>/model.safetensors"` [template] | config present, weights missing/partial copy | re-download; check size 672 397 148 / 672 409 268 B and sha256 (02) |
| `safetensors_rust.SafetensorError: Error while deserializing header: HeaderTooLarge` / `header too large` [template] | git-lfs pointer (134 B) or an HTML page saved as the weights (`/blob/` URL, mirror without LFS) | download with `hf download` / the `resolve/` URL; verify sha256 |
| `… MetadataIncompleteBuffer` / `incomplete metadata` / `InvalidHeaderLength` [template] | truncated download | re-download, verify size |
| `RuntimeError: Error(s) in loading state_dict for UNet3DModel: Unexpected key(s) … "class_embedding.weight" … size mismatch for conv_in.weight … [64, 3, 3, 3, 3] … [64, 2, 3, 3, 3]` [template] | pretrain `config.yaml` with fine-tuned weights in one folder (or the reverse: `Missing key(s)`) | keep each variant's two files together; never mix |
| emhancer ↔ emready swap | **no error** (identical shapes) — wrong style silently | check `exp_name` in `config.yaml` (`cond_model_emhancer` / `cond_model_emready`) and the sha256 |

## 3. First model call (after preprocessing, so minutes in)

| Symptom | Cause | Fix |
|---|---|---|
| `AssertionError: Now we only support norm=True for flow` | `--norm-grad` missing on a likelihood path (also the `cfm --help` epilog examples) | add `--norm-grad` (and `--use-lamb-w`) |
| `RuntimeError: Given groups=1, weight of size [64, 3, 3, 3, 3], expected input[4, 2, 64, 64, 64] to have 3 channels, but got 2 channels instead` [template] | `cfm denoise`/RELION with an emhancer/emready `--model-dir` | use `cryofm2-pretrain` |
| `ValueError: class_embedding needs to be initialized in order to use class conditioning` | `cfm enhance` with the pretrain `--model-dir` | use emhancer/emready |
| `IndexError: index out of range in self` (CPU) / `CUDA error: device-side assert triggered` [template] | `--output-tag` ≥ 5 or negative | tag 1 (EMhancer) or 0 (EMReady) |
| `UnboundLocalError: … 'cond_v_t'` [derived] | `--op` list without `denoise`, `inpaint` or `non-uniform` (typo such as `nonuniform`) | spell `non-uniform` |
| `TypeError … NoneType` inside `starfile/parser.py` | `inpaint` in `--op` without `--data-starfile-path` | add the particle STAR |
| numpy broadcast error at `sampling_helper.py:718` [derived] | particle box ≠ half-map box (inpaint) | re-extract/re-box so `rlnImageSize` equals the (padded) map box |
| `FileNotFoundError: Unable to find base directory for relative path: …` | particle stacks or RELION data not found from the STAR's ancestors (≤ 9 levels) | run from a path where `rlnImageName` resolves; absolute STAR path |

## 4. Geometry

| Symptom | Cause | Fix |
|---|---|---|
| `ValueError: Unknown input file type: …` | `.map.gz`, `.ccp4`, `.mrcs`, … | gunzip / convert to `.mrc` or `.map` |
| `ValueError: Half map file type must be the same, got MRC and STAR` | mixed types | same type for both |
| `RuntimeError: MRC file axis arrangement not supported!` | MAPC/MAPR/MAPS not (1,2,3)/(3,2,1)/(2,1,3) | rewrite the map in standard axis order (ChimeraX `save`, `relion_image_handler`) |
| bare `AssertionError` from `normalize_voxel_size_fourier` (`assert iz % 2 == 0`) | odd **cubic** box | pad to an even box (same for both halves and the mask) |
| `IndexError` in `GridPatches3D._get_patches_locations` | resampled box < 64 (box·apix < ≈96 Å) | pad the box; CryoFM2 is not meant for tiny particles |
| `ValueError: All volumes must have the same shape. Got shapes: …` | halves (or `-i`) on different grids (EMDB primary vs half maps) | use the half maps only, or resample onto one grid |
| `… shape mismatch` / `… apix mismatch` (`cfm enhance -i -i1 -i2`) | `-i` differs from `-i1` | use a half map as `-i` |
| `ValueError("density must be a cube (D, D, D)")` / `D must be even` with `--fsc-weighting` | non-cubic/odd output in the FSC weighting step | drop `--fsc-weighting` for non-cubic maps |
| mask fails the cubic assert | non-cubic mask (masks are not padded) | pad the mask to the map's cubic box |

## 5. Memory, speed, hangs

| Symptom | Cause | Fix |
|---|---|---|
| `torch.OutOfMemoryError: CUDA out of memory. Tried to allocate …` | `--batch-size 4` on ≤ 24 GB (docs: 24 G / 21 G with bf16; measured 21.4 GB on A100) | `--batch-size 2` (16 GB) or 1; `--bf16`; `--num_processes` does **not** help (issue #1) |
| OOM only with `inpaint` | back-projection mask on the GPU grows with the particle box (≈2.7 GiB at 256, 6.9 at 400) | smaller batch; bigger card |
| host RAM killed (Slurm `oom-kill`) with `non-uniform` | wavelet stacks ≈ 64 MiB per patch per process | more `--mem`, `--mask-path … --bbox`, smaller box |
| very slow, progress `0/32 … 62.96s/it` | normal: bars count patch batches, each = 200 steps; 125 patches → 32 batches ≈ 33 min per half | plan walltime from `inspect_map.py`; use `--bbox` with a mask |
| `--bf16` made no difference | clone older than 2026-01-23 (`abe3ac83`) had no autocast in `cfm denoise` | update to ≥ `abe3ac83` (the validated site's image is `6448681`) |
| multi-GPU run never finishes after the bars complete | `--fsc-weighting` barrier counted only on rank 0 [derived] | drop `--fsc-weighting` or run single-GPU |
| `EADDRINUSE` with two RELION jobs or two multi-GPU runs on one node | default ports 29500/29501 | `--main_process_port` / `CRYOFM_HALF1_PORT`, `CRYOFM_HALF2_PORT` |

## 6. Environment and install

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError: libGL.so.1: cannot open shared object file` [live, build 27768152] | `opencv-python` (via `mmcv-lite`) on a slim/headless image | install `libgl1 libglib2.0-0` (apt) or `mesa-libGL` (dnf); the validated site's image has them |
| `pip install --require-hashes` rejects `fsspec[http]` [live, build 27767838] | hash mode cannot resolve the extra | install the lock with `--no-deps`, then `pip check` |
| `UserWarning: CUDA is not available or torch_xla is imported. Disabling autocast.` at import | CPU node (login/staging) | harmless for `--help`; sampling needs a GPU node |
| `FutureWarning: The cuda.cudart module is deprecated …` | cuda-bindings 12.9 in the image | ignore |
| `RuntimeWarning: invalid value encountered in divide` (scipy `_measurements.py`) and `UserWarning: The .grad attribute of a Tensor that is not a leaf Tensor…` | normal during FSC shell averaging / gradient step (issue #2 run completed) | ignore unless outputs are missing |
| `could not determine a constructor for the tag 'tag:yaml.org,2002:python/tuple'` | you loaded a variant `config.yaml` with `yaml.safe_load` | the code uses mmengine's full loader; do not "validate" with safe_load |
| `cfm: image not found: …cryofm2.sif`, exit 127 [validated site's launcher] | image moved/deleted | rebuild it from the site's definition file as a CPU job ([02 §2](02_install_and_environment.md)) |
| outputs not visible inside the container / `No such file` for a shared-filesystem path [container sites] | `--no-mount hostfs` (or a plain `apptainer exec`) binds only `$HOME`, `$PWD` and the paths in `apptainer.conf` / `-B` | use absolute paths under the bound trees, or add `-B` |

## 7. RELION wrapper (static unless marked)

| Symptom | Cause | Fix |
|---|---|---|
| `cfm-relion --help` / `python relion_wrapper.py --help` never prints help, spawns `accelerate launch … relion_wrapper.py --help` repeatedly, dies with SIGKILL / `Transport endpoint is not connected` [live, staging node] | the wrapper relaunches itself whenever `LOCAL_RANK`/`RANK` are unset; on a GPU-less node accelerate's simple launcher sets neither → infinite chain | never call it by hand without a STAR; read 03/07 instead; kill stray `accelerate`/`relion_wrapper.py` processes |
| `ValueError: Last argument must be a .star file, got: …` | RELION's STAR must be last; your env-var string ends with a flag value | end the string with flags that take no value, or put `--data-starfile-path` before them |
| `ValueError: --model-dir must be specified or set via CRYOFM_MODEL_DIR environment variable` | neither given (the `--model-dir=` form is not recognised by the pre-check) | `export CRYOFM_MODEL_DIR=/abs/cryofm2-pretrain` (or the launcher shorthand where one exists) |
| `ValueError: Starfile path must contain 'half1' or 'half2'. Got: run_itNNN_class001_external_reconstruct.star` | RELION's final joined iteration, non-MPI `relion_refine`, Class3D/InitialModel | expected with the public wrapper (CONFLICT with the paper); the refinement has converged by then — the previous iteration's half maps are the result |
| `KeyError: 'rlnParticleDiameter'` / `'rlnPixelSize'` | RELION < 4.0.1 | RELION ≥ 4.0.1 |
| `FileNotFoundError: Could not find corresponding half2 starfile for …` | half1 started before RELION wrote the half2 STAR; or `--sequential_halves_recons` | default parallel halves; no `--sequential_halves_recons` |
| half2 exits 0 after 30 s "half1 has not started" and RELION then fails reading `…half2…_external_reconstruct.mrc` | half1 delayed (model load, queue) | both halves on one node; fast local disk for the lock file |
| nothing CryoFM happens with `--blush` | RELION's Blush path takes precedence | drop `--blush` |
| `ERROR: there was something wrong with system call: …` (RELION) | any non-zero exit of the wrapper | read `run.out`/`run.err` of the RELION job for the Python traceback |

## 8. Display and interpretation

| Symptom | Cause | Fix |
|---|---|---|
| output looks like a solid grey cube in ChimeraX (issue #2) | ChimeraX auto-threshold on the denoised map | set the level manually ("higher = cleaner density, lower = more noise"; maintainer) |
| output does not overlay the input or the model | origin/NSTART reset to 0 ([04 §7](04_inputs_and_geometry.md)) | `scripts/restore_origin.py`, or ChimeraX `volume #N originIndex`; keep `.mrc` for ORIGIN-word fixes |
| no detail beyond ≈3 Å although the input is 2 Å | 1.5 Å model grid band limit | expected; `--spectral-mixing` pastes the raw input back above 3 Å |
| FSC between the two outputs is near 1.0 everywhere | outputs share the input FSC and (non-uniform) difference map | not a resolution estimate; use map-model FSC and visual checks |
| whole-spectrum CC between output and a sub-1.5 Å input is low (≈0.3) [live] | band limit, not a failure | compare after low-passing both to ≥ 3.5 Å |
