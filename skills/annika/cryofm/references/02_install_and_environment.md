# 02 — Install and environment

## 1. What upstream documents

```bash
# template — not run
git clone https://github.com/ByteDance-Seed/cryofm.git && cd cryofm
conda create -n cryofm python=3.10 -y && conda activate cryofm
pip install .                      # or pip install -e . for development
pip install huggingface_hub
hf download ByteDance-Seed/cryofm-v2 --local-dir ./cryofm-v2     # ≈2.02 GB, three variants
```

"CryoFM was developed and tested on Debian GNU/Linux 11 (bullseye). GPU is required; we have tested on both NVIDIA
V100 and A100 GPUs." No PyPI/conda/SBGrid package exists (install from source only). `relion/relion_wrapper.py` is
**not** installed by pip; keep the clone.

### 1.1 Dependency facts (pinned `pyproject.toml`)

- Almost nothing is pinned: only `numpy<2.0` and a `starfile` range. `pip install .` therefore resolves the newest
  compatible torch/diffusers/mmengine/accelerate/lightning on the install day. Python declared `>=3.8`, docs use 3.10;
  `numpy 1.26.4` wheels exist for CPython 3.9–3.12.
- Needs torch ≥ 2.1 (`torch.autograd.grad(..., materialize_grads=True)`), CUDA-capable GPU; bf16 autocast on
  compute capability ≥ 8.0 (A100/H100). V100 (cc 7.0) is supported only by torch builds that still ship sm_70
  (≤ 2.10 cu128/cu129 or cu126 ≤ 2.14); `--bf16` behaviour there is unknown.
- `mmcv-lite` pulls the **non-headless** `opencv-python`, which `dlopen`s `libGL.so.1` and glib at import: slim
  images need `libgl1 libglib2.0-0` (apt) / `mesa-libGL` (dnf).
- `accelerate` is imported at every start and used for multi-GPU; `huggingface_hub` is declared but never imported by
  the CLI (no auto-download).
- Default torch wheels in late 2026 target CUDA 13 (driver ≥ 580); pick an index matching your driver.

### 1.2 Weights

```bash
# template — not run; pin the revision and verify
HF_HUB_DISABLE_TELEMETRY=1 hf download ByteDance-Seed/cryofm-v2 --revision 4e308f7f028af46ca2c7ee5af81e29775bc370dd --local-dir /abs/cryofm-v2
# one variant only: add --include "cryofm2-pretrain/*"
sha256sum /abs/cryofm-v2/cryofm2-*/model.safetensors
# 8f10dc552fceedae8a3c574e9b9d259de7d1f5047f4f2107d9309fae9512f413  cryofm2-pretrain  (672 397 148 B)
# 96576420fe03fc93088b40fdb1e7f785d100e6ed49833050c961670bdfaee163  cryofm2-emhancer  (672 409 268 B)
# 77c1fa590eaee1906e8470d3659c981855a92fcf4e6a7817b48f0069cd6d2bca  cryofm2-emready   (672 409 268 B)
```

`--model-dir` must be the variant folder (`config.yaml` + `model.safetensors`). The `hf` CLI replaced
`huggingface-cli` in huggingface_hub 0.34 (2025-07); `--local-dir` also writes `.cache/huggingface/`. Mirrors
(GitCode/AtomGit/ModelScope/hf-mirror) exist; verify sha256 before use — a git-lfs pointer or HTML page saved as
`model.safetensors` gives `HeaderTooLarge`. Treat `config.yaml` as code (full YAML loader).

### 1.3 Environment variables worth setting

| Variable | Why |
|---|---|
| `HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1` | nothing in `cfm` needs the Hub; blocks accidental egress and telemetry from imported libraries |
| `MPLCONFIGDIR`, `XDG_CACHE_HOME`, `TRITON_CACHE_DIR`, `TMPDIR` | writable, job-local, off inode-limited homes (matplotlib is imported at start) |
| `CUDA_VISIBLE_DEVICES` | the only GPU selector (no `--device` flag) |
| `NCCL_DEBUG=ERROR` | docs set it for multi-GPU |
| `CRYOFM_MODEL_DIR`, `CRYOFM_HALF1_PORT`, `CRYOFM_HALF2_PORT` | RELION wrapper (07) |
| `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` | did **not** rescue issue #1's OOM; lower `--batch-size` instead |

## 2. The validated site's route (example; sanitized in configs/site_config.example.md)

- Apptainer image (python:3.10.19-slim-bookworm + apt `libgl1 libglib2.0-0`; a hash-locked `requirements.lock.txt`
  installed with `--no-deps --require-hashes --only-binary=:all:`; `pip install --no-deps --no-build-isolation` of the
  pinned source tarball; `HF_HUB_OFFLINE=1` etc. in `%environment`). Built as a CPU job in ≈7 min from a definition file
  that refuses an unpinned base image or tarball. Two earlier attempts failed on hash-mode extras and `libGL.so.1`; both
  fixes are in the definition ([10 §6](10_troubleshooting.md)).
- Weights in one folder (`cryofm-v2/cryofm2-{pretrain,emhancer,emready}/`) fetched by a script that pins the HF revision
  and verifies the three sha256 digests; its `verify` mode re-checks them (rc 0 = intact).
- A launcher `cfm` on PATH after a site activation script ([03 §7](03_cli_reference.md)): resolves the shorthand
  `--model-dir pretrain|emhancer|emready`, adds `--nv` on GPU nodes only, binds the shared file systems.
- Verify readiness before any job (adapt the activation and paths to your site):

```bash
# template — not run
<site activation, e.g. source /abs/path/activate.sh>
python3 scripts/cryofm_env_probe.py --sif /abs/cryofm2.sif --weights-dir /abs/cryofm-v2   # expects VALIDATED-CANDIDATE on a GPU node
sha256sum /abs/cryofm-v2/cryofm2-*/model.safetensors    # compare with §1.2, or run the site's verify script
cfm --help                                              # safe anywhere
```

If either fails, treat the host as **not ready**; rebuild/refetch only with the user's consent.

## 3. Other hosts (generic probe route)

1. `python3 scripts/cryofm_env_probe.py` — finds `cfm` on PATH or a conda env with `cryofm`, GPUs (`nvidia-smi`),
   driver, caches, the image (`--sif`, `$CRYOFM_SIF`, or `runtime.image` in `configs/site_config.local.md`) and the
   weight folders with sizes (`--weights-dir`, `$CRYOFM_WEIGHTS`, the parent of `$CRYOFM_MODEL_DIR`, or `weights.dir`
   in the site config); `--hash` re-checks sha256 (2 GB read; ask first). Nothing is assumed from the host name.
2. Readiness = runnable `cfm` + three pinned weight folders + a GPU with ≥ 8 GB (batch 1) and ideally ≥ 24 GB
   (batch 4) + the GPU fixture passed. Record the probe in `configs/site_config.local.md` from the template.
3. Container recipe to reuse elsewhere: the validated site's Apptainer definition (§2: pinned base-image digest, source
   tarball sha256, dependency lock) is the only reproducible recipe known; it is not bundled — rebuild the same pins
   from §1 or ask the maintainer. `pip install .` on another day resolves different versions.
4. CPU-only or Apple Silicon hosts: explain only. Nothing is validated and the code never asks for a device.

## 4. Fixture for a new host (public, small)

EMD-11638 (used on the validated site: 256³ @ 0.5332 Å, 3 × ~56 MB gzipped) or the smaller EMD-29934 (104³ @ 0.96 Å, 4 MB per
file, held out of every training list; 66³ at 1.5 Å → 8 patches). Download from
`https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-XXXX/{map,other,masks}/`, gunzip, then run the three
commands of [05 §1 and §4](05_core_workflows.md) with `--seed 0` and compare headers/CC with `check_cfm_output.py`.
Expected: rc 0, three + one + one outputs on the input grid, finite, low-pass CC vs input ≳ 0.95 at 3.5 Å for
denoise/emhancer. Record job id, card, driver, peak memory, wall time in the site config.
