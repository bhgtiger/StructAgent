# 01 — Source map (which source backs which claim)

Pinned baseline: **`3dem/model-angelo` tag `v1.0.18`, commit
`994945bdfa6e5368e0d62349a47792f4864eebc3`**, released **2026-06-15**. Verified
current latest as of **2026-06-22** (GitHub releases/tags API: v1.0.18 is the top
release; its sole change vs the prior tag is an install-script safety fix —
"safely terminate sourced install script"). License **MIT**.

When in doubt, the live installed target wins over this map (`references/00`
trust ladder).

## Authoritative for installation/setup

| Claim area | Source | Notes |
|---|---|---|
| Install steps, conda env name `model_angelo`, Python 3.11, `torch==2.9.1 torchvision`, `pip install .`, optional `--download-weights` | `install_script.sh` @ v1.0.18 | The script is meant to be `source`d; it creates the env, installs torch then the package, and (with `-w`) calls `setup_weights` for `nucleotides` + `nucleotides_no_seq`. |
| Python dependency pins | `setup.py` @ v1.0.18 | `fair-esm==1.0.3`, `pyhmmer==0.7.1`, `biopython>=1.81`, `numpy<2.0`, plus tqdm, scipy, einops, matplotlib, mrcfile, pandas, loguru. Console script `model_angelo = model_angelo.__main__:main`. |
| Subcommand surface (7 subcommands) | `model_angelo/__main__.py` + `apps/*.py` + `utils/setup_weights.py` | build, build_no_seq, evaluate, eval_per_resid, hmm_search, refine, setup_weights. Exact args in `references/05`. |
| Weight bundles, Zenodo URLs+MD5, ESM-1b, cache path = `torch.hub.get_dir()` = `$TORCH_HOME/hub` | `model_angelo/utils/torch_utils.py` (`download_and_install_model`, `download_and_install_esm_model`, bundle dict) + `config.json` | `references/04`. ESM model `esm1b_t33_650M_UR50S` (~7 GB), chmod 0o555 for shared use. |
| Compute requirements: NVIDIA GPU ≥8 GB (2080-class+), weights ~10 GB | README @ v1.0.18 "Compute requirements" | Disk must exceed ~10 GB for weights. |
| Container builds | `Dockerfile`, `Singularity.from.scratch`, `Singularity.from.ghcr.io` @ v1.0.18 | `Dockerfile` + `Singularity.from.scratch` run `bash install_script.sh --download-weights` with `TORCH_HOME=/public/model_angelo_weights`. `Singularity.from.ghcr.io` instead bootstraps from a prebuilt image (`ghcr.io/truatpasteurdotfr/model-angelo:main`) and ships only a `%runscript` — no build-time install. |

## Authoritative for usage limits / validation handoff

| Claim area | Source |
|---|---|
| Method, benchmarks, what it does/doesn't model (no ligands/glycans/cofactors; degradation < ~3.5–4 Å; nucleotide base ID hard) | Jamali et al., *Nature* **628**, 450–457 (2024), DOI 10.1038/s41586-024-07215-4; ICLR 2023 (OpenReview `65XDF_nwI61`) |
| "Builds, does not validate"; route to Servalcat/Phenix/ISOLDE/Coot + MolProbity/Q-score | Local DB digest `jamali_2024_automated_model_building_protein`; README FAQs (cis-prolines fixed by a REFMAC round; glycosylation/non-standard residues checked manually) |

## Operational / managed-distribution sources (route patterns; site specifics not universal)

| Source | URL | Gives | Caution |
|---|---|---|---|
| README (shared-cluster section) | github.com/3dem/model-angelo | `TORCH_HOME=/public/...` + `--download-weights` + wrapper script pattern | `/public/...` is an example path, not fixed |
| NIH Biowulf | hpc.nih.gov/apps/model-angelo.html | module name `model-angelo`; `module load model-angelo`; A100/Slurm examples (`--gres=gpu:a100:1 --mem=20g -c 8`, partition `gpu`); multithreaded; **"Some features of ModelAngelo require the hhblits command of hhsuite"** | A100/mem/cores/partition/module-name are Biowulf conventions; other clusters differ — `module avail model` / `module spider` |
| SBGrid | sbgrid.org/software/titles/modelangelo | default Linux version 1.0.18; ~5.8 GB version + 11.3 GB common files; Linux-64 only; `sbgrid-cli install modelangelo` | Sizes/version are SBGrid packaging and may be stale |
| RELION 5 ModelBuilding | relion.readthedocs.io (release-5.0) | GUI job; runtimes (~18 min w/ seq, ~12 min no-seq+HMMer on four 1080s); Hmmer tab | Imports `model_angelo` as a module, not the PATH binary (`references/07`) |
| CCP-EM Icknield 2024 tutorial | ccpem.ac.uk (icknield2024 PDF) | public fixture EMD-18645 (2.2 Å) + UniProt Q8CZ28; proteome UP000038237 | Fully GUI/course-preconfigured; no raw install commands |

## Currency / divergence notes

- Pinned snapshot matches upstream exactly as of 2026-06-22 (tag, commit, date,
  deps, weights, MIT). The release cadence has been frequent; if the user's clone
  is newer, prefer the **live** `model_angelo --version` and the *installed*
  `install_script.sh`/`setup.py` over this map.
- Torch pin history (from release notes): v1.0.15+ tracks torch 2.9; v1.0.14 was
  the last torch-2.0 line; v1.0.17 fixed older-PyTorch compatibility. So the
  exact torch pin is version-tied — read it from the installed
  `install_script.sh`, not memory.
- CUDA is **not** separately pinned; it rides the `torch==2.9.1` wheel. A recent
  NVIDIA driver is backward-compatible with that runtime.
