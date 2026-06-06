# 01 — Source map (citations, pins, drift)

All facts in this skill trace to the sources below. Cite as
`[src: <artifact/URL> @ <pin/fetch-date>]`.

## Pin block (authoritative)

```text
Repo                   : https://github.com/ml-struct-bio/cryodrgn.git
Target tag             : 4.2.1
Tag object (annotated) : 2f4db4c02021fd136c53f03a572684921369b268
Commit (4.2.1^{})      : 23ae1a3303b1e623f421b816fc7ea426c9d5b580
Fetched                : 2026-06-05T21:46:02Z
PyPI latest captured   : 4.2.1  (2026-06-05)
Repo main HEAD @ fetch : cb28f71b32a92e1a75331968eee86921b16796f6
Beta tag (out of scope): 4.3.0-b2  → tag object 28736aea04817e9ceb1cb7582ebeb6d7db0d6304,
                                      commit 392bfc2e4f8ae56da637ec41a2d37fe1c831dc9d
```

> **Tag vs commit:** cite the dereferenced commit `23ae1a33…` for code; the
> annotated tag *object* is `2f4db4c0…`. They are different SHAs for the same
> release — do not conflate them.

## P0 web / packaging sources (fetched 2026-06-05)

| Source | URL / artifact | Key captured facts |
|---|---|---|
| Homepage | https://cryodrgn.cs.princeton.edu/ | cryoDRGN = deep NNs for continuous heterogeneous cryo-EM reconstruction; links repo + user guide + papers. |
| User guide | https://ez-lab.gitbook.io/cryodrgn/ | install via pip in a separate anaconda env; commands via `cryodrgn` / `cryodrgn_utils`; `-h` lists subcommands; inputs = particle images + CTF (+ optional poses); outputs include `z.pkl` and NN weights; `analyze` samples volumes + PC trajectories + PCA/UMAP. |
| Installation | https://ez-lab.gitbook.io/cryodrgn/installation | recommends Anaconda; quick install `conda create --name cryodrgn python=3.13` → `pip install cryodrgn` → `cryodrgn --version`; **requires high-performance Linux workstation/cluster + NVIDIA GPUs**; tested Python 3.10–3.12 (3.13 mentioned), PyTorch 2.0–2.9; ships `tests/quicktest.sh`; `Use cuda True` as a GPU check. **Reconciled with captured:** package metadata version `4.2.1` and `requires-python = ">=3.10"` (no upper bound) [src: `sources/source/cryodrgn_4.2.1/pyproject.toml`]; live runtime confirms `cryoDRGN 4.2.1` [src: `_version.txt`]. The doc `python=3.13` line is the docs' suggested env; the *enforced* floor is `>=3.10`, and the validated host ran Python 3.10.20 [src: the validation run]. |
| Release notes | https://ez-lab.gitbook.io/cryodrgn/cryodrgn-user-guide/news-and-release-notes | 04/2026 v4.2.1 (dashboard); 03/2026 v4.2.0 (cryoDRGN-AI pose search as `cryodrgn abinit`); 11/2025 v3.5.0 (1-indexing for output volumes/epochs; unified `parse_star`). |
| EMPIAR-10076 tutorial | https://ez-lab.gitbook.io/cryodrgn/cryodrgn-empiar-10076-tutorial | end-to-end workflow: stack+metadata → optional C1 consensus poses → parse poses/CTF → downsample D=128/256 → train VAE → analyze → filter junk → high-res → trajectories. |
| GitHub README | https://github.com/ml-struct-bio/cryodrgn (and pinned `README.md`) | mirrors quickstart; "compatible with Python 3.10 through 3.13"; `CUDA_VISIBLE_DEVICES` + `--multigpu`. **Superseded for CLI syntax by live capture:** full live `--help` is now captured for all 23 `cryodrgn` + 25 `cryodrgn_utils` subcommands (e.g. `cryodrgn.downsample.help.txt`, `cryodrgn.train_vae.help.txt`, `cryodrgn.analyze.help.txt`, `cryodrgn.eval_vol.help.txt`, …). Cite the captured `*.help.txt` filenames — NOT the README `-h` excerpts — for every flag/default/positional claim. |
| PyPI metadata | https://pypi.org/pypi/cryodrgn/json | latest `4.2.1`; `requires_python >=3.10`; wheel `cryodrgn-4.2.1-py3-none-any.whl` + sdist. |

## P0 pinned-source artifacts (in `sources/source/cryodrgn_4.2.1/`)

| Artifact | Captured facts |
|---|---|
| `pyproject.toml` | name `cryodrgn`; classifiers **GPLv3** + **`Operating System :: POSIX :: Linux`**; `requires-python = ">=3.10"` (no upper bound); `torch>=2.0.0,<2.10.0`; deps incl. numpy<1.27, pandas<3, starfile, healpy, igraph, jupyterlab, flask; console scripts `cryodrgn` → `command_line:main_commands`, `cryodrgn_utils` → `command_line:util_commands`. |
| `cryodrgn/command_line.py` | enumerates the shipped subcommands (see `03_cli_reference.md`): 23 `cryodrgn` + 25 `cryodrgn_utils`. |
| `LICENSE.txt` | GNU General Public License v3, 29 June 2007. |
| command module docstrings | example-usage strings for `abinit`, `parse_pose_star`, `parse_ctf_star`, `backproject_voxel`, `filter`, `analyze_landscape`, etc. |

## Captured live help + validation provenance (realized trust-ladder #1)

Live `--help`/`--version` for the installed tool was captured 2026-06-06 on a
Linux + NVIDIA GPU host (cryoDRGN 4.2.1, torch 2.9.1+cu128, cuda True, CUDA 12.8). These captures
are the **authoritative source for every CLI flag, default, positional, and
subcommand** — they outrank docs and README `-h`. End-to-end GPU smoke confirmed the
command templates actually run; commands are **VALIDATED against cryoDRGN 4.2.1**.

| Artifact | Captured facts / provenance |
|---|---|
| `_version.txt` | `cryoDRGN 4.2.1`; `torch 2.9.1+cu128 cuda True 12.8` — the validated runtime stamp. |
| `cryodrgn.help.txt` | top-level `cryodrgn -h`: exactly **23** subcommands (`abinit, abinit_het_old, abinit_homo_old, analyze, analyze_landscape, analyze_landscape_full, backproject_voxel, dashboard, direct_traversal, downsample, eval_images, eval_vol, filter, graph_traversal, parse_ctf_csparc, parse_ctf_star, parse_pose_csparc, parse_pose_star, parse_star, pc_traversal, train_nn, train_vae, train_dec`). |
| `cryodrgn_utils.help.txt` | top-level `cryodrgn_utils -h`: exactly **25** utility subcommands (`analyze_convergence, add_psize, clean, concat_pkls, filter_cs, filter_mrcs, filter_pkl, filter_star, flip_hand, fsc, gen_mask, invert_contrast, make_movies, parse_relion, phase_flip, plot_classes, plot_fsc, select_clusters, select_random, translate_mrcs, view_cs_header, view_header, view_mrcs, write_cs, write_star`). |
| `cryodrgn.<sub>.help.txt` (one per subcommand) | per-subcommand live `--help`; cite the exact filename when stating any flag/default/positional (e.g. `cryodrgn.downsample.help.txt`, `cryodrgn.train_vae.help.txt`, `cryodrgn.backproject_voxel.help.txt`, `cryodrgn.eval_vol.help.txt`, `cryodrgn.analyze.help.txt`, `cryodrgn.parse_pose_star.help.txt`, `cryodrgn.parse_ctf_star.help.txt`, `cryodrgn.parse_pose_csparc.help.txt`, `cryodrgn.parse_ctf_csparc.help.txt`). |
| `cryodrgn_utils.<sub>.help.txt` | per-utility live `--help` (e.g. `cryodrgn_utils.write_cs.help.txt`, `cryodrgn_utils.filter_cs.help.txt`, `cryodrgn_utils.write_star.help.txt`, `cryodrgn_utils.parse_relion.help.txt`, `cryodrgn_utils.fsc.help.txt`, `cryodrgn_utils.gen_mask.help.txt`). |
| GPU smoke summary (the validation run) | GPU smoke ground truth (what actually ran): downsample, parse_pose_star, parse_ctf_star, backproject_voxel, train_vae (`Use cuda True`), analyze, view_header — all PASS on a Linux + NVIDIA GPU host. Documents real output layout (train_vae workdir `config.yaml/run.log/weights.pkl/z.pkl/analyze.N/`; backproject `--outdir` → `backproject.mrc/half_map_a.mrc/half_map_b.mrc/fsc-plot.png/fsc-vals.txt`) and real `train_vae` defaults from `run.log`. |
| per-host probe report (the validation run) | per-host probe report (read-only): `config_state = ready`; a Linux + NVIDIA GPU host, Linux x86_64, Python 3.10.20 (within tested range), an NVIDIA GPU, cryoDRGN 4.2.1, live help captured. Provenance for the `ready` verdict — but this is one host's snapshot; the probe recomputes support per machine. |

## Drift / caveats to keep labeled

1. **Python range drift.** `pyproject` `requires-python` is `>=3.10` (unbounded);
   README says "3.10 through 3.13"; installation docs say tested 3.10–3.12 (3.13
   mentioned); README "Updates" notes Python 3.13 + PyTorch 2.9 support and that
   PyTorch <2.0 is dropped. Effective torch cap `<2.10.0` comes from `pyproject`.
   → Report a **range (3.10–3.13)**, flag anything outside as drift; never assert
   a single exact supported version. The probe marks `within_tested_range`.
2. **`4.3.0-b2` beta exists** (test.pypi beta channel) but this skill targets
   **stable 4.2.1** (the validated runtime). Re-pin reminder: repo `main` had moved
   to `cb28f71…` at capture.
3. **Tag-object vs commit SHA** (`2f4db4c0…` vs `23ae1a33…`) — see pin block.
4. **GitBook docs not separately version-pinned** — rendered pages captured by
   date; treat as trust-ladder class 3 until a docs-source repo is pinned.
5. **Live `--help` captured 2026-06-06 on a Linux + NVIDIA GPU host** (cryoDRGN 4.2.1, torch
   2.9.1+cu128, cuda True). All command templates are now **VALIDATED against
   cryoDRGN 4.2.1** (cite the captured `*.help.txt` file where each flag was
   confirmed); GPU smoke confirms they run. See the validation run.
   Label commands `[VALIDATED: cryoDRGN 4.2.1]` with the captured-help filename, and
   add `[run-with-confirmation]` on any command that touches real data/compute.
   Support is per-machine: the read-only probe recomputes `config_state`
   (`ready|partial|blocked|absent|stale|unknown`) on each host — never hardcode one
   host's verdict.

## Papers (for science/validation only — not CLI syntax)

- Zhong et al., *cryoDRGN*, **Nature Methods 2021**, doi:10.1038/s41592-020-01049-4.
- Zhong et al., ICLR 2020 (continuous distributions), arXiv:1909.05215.
- Zhong et al., *cryoDRGN2* (ab initio), ICCV 2021.
- Kinman et al., *Uncovering structural ensembles … cryoDRGN*, **Nature Protocols 2023**, doi:10.1038/s41596-022-00763-x.
- Rangan et al., *cryoDRGN-ET*, **Nature Methods 2024**, doi:10.1038/s41592-024-02340-4.
- Levy et al., *cryoDRGN-AI*, **Nature Methods 2025**, doi:10.1038/s41592-025-02720-4.

Do not cite paper numbers as performance claims (`08_validation_and_benchmarks.md`).
