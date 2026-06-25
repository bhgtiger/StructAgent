# 03 — Installation routes

Five routes. Pick by `state` + who owns the machine. All are Linux + NVIDIA.
Always confirm before any mutating command; `scripts/install_modelangelo.sh`
wraps routes 1–2 (and the container build of route 3) around the official
`install_script.sh`, pinned to a tag.

Table of contents: 1) Personal Linux + conda · 2) Shared cluster (self-managed)
· 3) Container (Docker / Singularity) · 4) SBGrid · 5) HPC environment module
(e.g. NIH Biowulf) · Route picker.

---

## 1. Personal Linux + conda (the upstream "Personal use" path)

Prereqs: Linux, conda/miniconda, `git`, an NVIDIA GPU (≥8 GB recommended),
>~10–15 GB free disk.

Upstream steps (README v1.0.18):
```text
# 0. (if needed) install miniconda3; check `conda info`
git clone https://github.com/3dem/model-angelo.git
cd model-angelo
source install_script.sh            # creates conda env `model_angelo`
conda activate model_angelo
model_angelo build -h               # smoke test
```
`install_script.sh` creates a Python 3.11 env, `pip install torch==2.9.1
torchvision`, then `pip install .`. Weights are **not** downloaded unless you
pass `-w/--download-weights` (see route notes + `references/04`).

Wrapped + pinned + reproducible (this skill, confirm first):
```text
bash scripts/install_modelangelo.sh --route personal --env model_angelo \
    --tag v1.0.18 --repo-dir ~/src/model-angelo \
    --torch-home ~/model_angelo_weights --download-weights --yes
```
The wrapper clones the pinned tag, sources conda, runs the official script with
your flags, sets `TORCH_HOME` as a conda env var, and (with `--download-weights`)
fetches the `nucleotides` + `nucleotides_no_seq` bundles. Then:
```text
bash scripts/verify_modelangelo.sh --env model_angelo --check-gpu --check-weights
```

Install-script flags (upstream): `-h/--help`, `-w/--download-weights`,
`-n/--name <env>` (default `model_angelo`). It errors if `--download-weights` is
set while `TORCH_HOME` is unset.

---

## 2. Shared cluster you manage yourself (install once, all users run it)

Prereqs: a public account/location; a weights dir **readable + executable by all
users**; conda available to those users.

Upstream pattern (README "Shared computational environment"):
```text
export TORCH_HOME=/public/model_angelo_weights     # EXAMPLE path — choose your own
cd model-angelo
source install_script.sh --download-weights
# verify the weights landed under $TORCH_HOME/hub/checkpoints/ (references/04)
```
Then expose a thin wrapper on everyone's PATH:
```bash
#!/bin/bash
source `which activate` model_angelo
model_angelo "$@"
```
Wrapped (this skill): `--route shared` sets `TORCH_HOME`, downloads weights
there, and prints the wrapper for you to place. The weights' ESM `.pt` files are
`chmod 0o555` by the installer so all users can read+execute them
(`references/04`).

Notes: pick a `TORCH_HOME` on a large, shared filesystem (the cache is ~10 GB).
Set it **before** the download. Per-user installs that omit `TORCH_HOME` scatter
~10 GB into each `~/.cache/torch` — avoid on shared systems.

---

## 3. Container (Docker / Singularity / Apptainer)

The repo ships three recipes. Two of them (`Dockerfile`, `Singularity.from.scratch`)
build the env from source by running `bash install_script.sh --download-weights`
with `TORCH_HOME=/public/model_angelo_weights`; `Singularity.from.ghcr.io` instead
bootstraps from a prebuilt image and only ships a `%runscript` (no build-time install):

- **`Dockerfile`** — base `continuumio/miniconda`; clones the repo and installs
  with weights baked in. Build: `docker build -t model-angelo .` (needs NVIDIA
  Container Toolkit + `--gpus all` at run time).
- **`Singularity.from.scratch`** — base `continuumio/miniconda3`; builds the env
  from source; `%runscript` activates `model_angelo` and execs it. Build:
  `singularity build model-angelo.sif Singularity.from.scratch` (or `apptainer
  build`).
- **`Singularity.from.ghcr.io`** — bootstraps from a prebuilt image
  `ghcr.io/truatpasteurdotfr/model-angelo:main` (third-party mirror; verify trust
  before use). Lighter build.

Run pattern: `singularity run --nv model-angelo.sif build -h`. The image bakes
weights at `/public/model_angelo_weights`; bind-mount a host weights dir if you
prefer to manage them outside the image. Containers are the cleanest answer when
the host is non-Linux (run the Linux container on a Linux VM/host with GPU
passthrough) or when conda/CUDA on the host is fragile.

---

## 4. SBGrid (managed software environment)

For sites/users with an SBGrid subscription. SBGrid lists ModelAngelo **Linux-64
only**, default version **1.0.18** (~5.8 GB version + 11.3 GB common files ≈ 17
GB). It runs under the SBGrid environment manager — no conda/clone needed:
```text
sbgrid-list modelangelo            # see available versions/executables
sbgrid-cli install modelangelo     # install via SBGrid
# then `model_angelo` is available through the SBGrid software environment
```
SBGrid abstracts activation behind its own machinery; the version may have
advanced past 1.0.18 — check with `sbgrid-list`. No macOS build.

---

## 5. HPC environment module (e.g. NIH Biowulf)

Many clusters publish ModelAngelo as an environment module — you do **not**
install it; the site staff did. NIH Biowulf example (module name `model-angelo`):
```text
module load model-angelo
# interactive GPU session (Biowulf-specific resources):
sinteractive --gres=gpu:a100:1 --mem=20g -c 8
model_angelo build -v map.mrc -f sequence.fasta -o output      # (usage, not this skill's job)
# batch:
sbatch --gres=gpu:a100:1 --partition=gpu --mem=20g -c 8 model-angelo.sh
```
ModelAngelo is multithreaded; Biowulf examples allocate `-c 8`. **Site
specifics are not universal:** the module name (`model-angelo` vs `modelangelo`
vs versioned `model-angelo/1.0.x`), GPU type, partition, and memory differ per
cluster. Always confirm with `module avail model` / `module spider model-angelo`,
and find the staff-managed `TORCH_HOME` from the site's docs. On clusters the
weights are typically pre-staged by staff; you rarely download them yourself.

**hhsuite note (Biowulf):** "Some features of ModelAngelo require the `hhblits`
command of hhsuite." This is the optional HHblits-based identification path
*downstream of* `build_no_seq` (feeding `output/hmm_profiles/*.hhm` to `hhblits`
against your own database). The bundled `hmm_search` uses `pyhmmer` and needs no
external binary; only the HHblits route needs hhsuite installed separately
(`references/06`). ModelAngelo ships no sequence databases.

---

## Route picker

```text
Is the machine non-Linux (macOS/Windows)?           -> blocked. Use a Linux box,
                                                       HPC module, or a Linux
                                                       container/VM with GPU.
Does your site already provide a module / SBGrid?   -> route 5 / route 4 (don't
                                                       install; load it).
Personal Linux workstation, you own it?             -> route 1 (conda).
Shared Linux cluster you administer?                -> route 2 (TORCH_HOME +
                                                       wrapper) or route 3
                                                       (container) for isolation.
Fragile host conda/CUDA, or reproducible deploys?   -> route 3 (container).
```
