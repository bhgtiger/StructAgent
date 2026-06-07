# 01 — Source map (claim → evidence)

Every operational claim in this skill traces to a captured source. Pinned source is the spine; the live target machine overrides it for its own runtime. Project-local evidence lives under `sources/` (not shipped); this file is the distilled index.

## Pinned source snapshot

- Repo: `https://github.com/rsanchezgarc/deepEMhancer`
- Branch: `master`, depth-1 clone, fetched 2026-06-06
- Commit: **`961f028ca609017990de4473ab368cf1787e8282`**
- Source package version: **`0.17`** (`deepEMhancer/__init__.py`)

## Claim → evidence table

| Claim used by the skill | Evidence (pinned source unless noted) |
|---|---|
| Console entry point is `deepemhancer` | `setup.py` `entry_points` → `deepemhancer=deepEMhancer.exeDeepEMhancer:commanLineFun` |
| Required `-i/--inputMap`, `-o/--outputMap` | `applyProcessVol/cmdParserOptionsDeepEMHancer.py` (`required: True`) |
| Models `tightTarget`(default)/`wideTarget`/`highRes`; highRes only for FSC < 4 Å | same file, `-p/--processingType` `choices` + `default` + help |
| `-i2/--halfMap2`, `-s/--samplingRate` optional | same file |
| Normalization mode 1 `--noiseStats MEAN STD` (nargs 2); mode 2 `-m/--binaryMask`; auto if neither | same file (Normalization group) |
| Real model-path flag is `--deepLearningModelPath` (dir or `.hd5` file) | same file (Alternative options) |
| Dust-clean flag spelled **`--cleaningStrengh`**, default `-1` (off) | same file |
| `-g/--gpuIds` default `"0"`, `-1` → CPU; `-b/--batch_size` default `8` | same file + `config.py` `BATCH_SIZE=8`; `cmdParser.py` maps `"-1"`→`None` |
| Default model dir `~/.local/share/deepEMhancerModels/production_checkpoints` | `config.py` `DEFAULT_MODEL_DIR` |
| Model files `deepEMhancer_{tightTarget,wideTarget,highRes,masked}.hd5` | `exeDeepEMhancer.py` checkpoint construction; `cmdParser.py` checks `tightTarget` |
| Missing models → print "not found" + `sys.exit(1)`; a real run may `makedirs(DEFAULT_MODEL_DIR)` | `cmdParser.py` lines ~97–106 |
| Output must end `.mrc`/`.map` (error text says only `.mrc`) | `exeDeepEMhancer.py` assertion |
| Custom `.hd5` file forces `-p tightTarget`; `-m` forces `-p tightTarget` | `exeDeepEMhancer.py` asserts |
| The model-download flag = network GET from Zenodo + write/unzip (~705 MB) | `cmdParser.py` `_DownloadModel`; `config.py` `DOWNLOAD_MODEL_URL`, `MODEL_DOWNLOAD_EXPECTED_SIZE` |
| `import tensorflow` at module load (heavyweight) | `config.py` top-level `import tensorflow as tf`; `exeDeepEMhancer.py` import chain |
| License Apache 2.0 | `LICENSE` ("Apache License, Version 2.0"); `setup.py` `license='Apache 2.0'`; `meta.yaml` `license_family: APACHE` |

## Phantom / stale strings (never present as real flags)

| String | Where it appears | Status |
|---|---|---|
| `--deepLearningModelDir` | **README** example | **Stale** — real flag is `--deepLearningModelPath` |
| `-c path/to/...` | `cmdParser.py` `example_text` epilog | **Phantom** — no `-c` option is defined |
| `--precomputedModel` | help text of `-m/--binaryMask` and `--deepLearningModelPath`; `exeDeepEMhancer` docstring | **Phantom** — no such option is defined |

## Version / dependency divergence (record, don't hard-claim)

The exact dependency recipe differs across captured sources, so **never** assert one without the target's live metadata:

| Source | Package version | TensorFlow | Python | Notes |
|---|---|---|---|---|
| `deepEMhancer/__init__.py` (pinned) | **0.17** | — | — | source of truth for version string |
| `setup.py` (pinned) | 0.17 (derived) | `tensorflow-gpu==2.10.*` (or `tensorflow==2.10.*` if `DEEPEMHANCER_CPU_ONLY` set) | — | numpy 1.23.\*, scikit-image 0.19.\*, scipy 1.9.\*, mrcfile 1.4.\* |
| `README.md` | — | "TensorFlow 2.10", CUDA 11/11.8 | — | narrative |
| `deepEMhancer_env.yml` | — | `tensorflow==2.12.0`, `keras==2.12.0` | 3.9 | `cudatoolkit=11.8`, `nvidia-cudnn-cu11==8.6.0.163` |
| `condaDeepEMHancer/meta.yaml` | **0.16** | `tensorflow-gpu==2.12.*` | 3.10.\* | conda package recipe |
| Anaconda channel page | 0.16, linux-64 | — | — | `conda install rsanchez1369::deepemhancer` |

**Takeaway:** the installed version may be 0.16 (conda) or 0.17 (source); TF may be 2.10 or 2.12. The config probe records the *installed* version (`importlib.metadata`) so the skill speaks about the real runtime, not a guessed recipe.

## External sources & how to weight them

| Source | URL | Weight |
|---|---|---|
| Method paper (Sánchez-García et al., Comm Biol 2021) | `10.1038/s42003-021-02399-1` / PMC8282847 | Rationale/limits only; not CLI |
| Anaconda package | `anaconda.org/rsanchez1369/deepemhancer` | Distribution/platform facts |
| CryoSPARC wrapper docs | `guide.cryosparc.com/.../job-deepemhancer-wrapper` | Integration conventions (`references/07`) |
| Biowulf page | `hpc.nih.gov/apps/DeepEMhancer.html` | Community examples; **version-skewed (module 0.13)** — cross-check only |
| Zenodo model record | `zenodo.org/record/7432763` | Model download source; **not independently fetched** (403 here) |
