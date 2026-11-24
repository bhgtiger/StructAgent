# 01 — Source map: pins, how to cite, where the evidence is

## 1. Pins (source review 2026-11-24)

| Component | Pin | Notes |
|---|---|---|
| Upstream repo | `https://github.com/YangLab-SDU/CryoCodex`, tag `v1.0.0` → commit `a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17` | lightweight tag; `main` HEAD was the same commit; commit 2026-10-25, GitHub release 2026-10-28 (empty body, no assets); `predict.py` `__version__ = "1.0.0"` |
| Colab notebook (in repo) | clones `6d1a7401ef9b477d75d5f4cc63b95bda4d46b993` | Python files byte-identical to v1.0.0; different launcher (calls `predict.main()` directly) |
| Weights | `https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth` | 470,938,660 B; Last-Modified 2026-10-01 02:13:30 GMT; ETag `"1c11f424-65cbdf6493754"` (size-based, not a hash); **no published checksum or version**. sha256 of the file downloaded 2026-11-24 (validation host): `dfb814c63ed2dbdca99d0e3803e408d88775217a48d72a4fbb60618f8feda380` (md5 `5f22a2b7557e742511fcf129d10e4824`); `weights_only=True` load OK; dict with `model_state_dict` (344 tensors, 39,484,636 parameters) plus optimizer/scheduler state |
| Preprint | Cheng B., Su B., Yang J. bioRxiv 2026, doi:10.64898/2026.09.30.755675 v1 | PDF banner "posted October 2, 2026"; bioRxiv API date 2026-10-08; CC BY-NC-ND 4.0; not peer reviewed |
| Lab site | `https://yanglab.qd.sdu.edu.cn/CryoCodex/` | heading + `benchmark/` (train/valid EMDB lists, per-map author results as zips) |
| Scipion plugin (deferred) | `scipion-em/scipion-em-cryocodex` 0.3.2 (PyPI), GitHub `main` `38a91a5` | pins backend 1.0.0 @ `a35e73a`; same author |

File:line citations in this skill (`predict.sh:85`, `predict.py:47`, …) refer to the clone at `a35e73a`.

## 2. How to cite

```bibtex
@article{Cheng2026CryoCodex,
  title={CryoCodex: learning discrete structural representations for cryo-EM map post-processing},
  author={Cheng, Bin and Su, Baoquan and Yang, Jianyi},
  journal={bioRxiv},
  year={2026},
  doi={10.64898/2026.09.30.755675}
}
```
(README `README.md:380-386`.) Also cite the CryoCodex version (`v1.0.0`, commit `a35e73a`) and, when a fixture map is
used, its EMDB entry.

## 3. Evidence pack (not bundled)

The skill was built from a cited evidence pack gathered on 2026-11-24 with the `scientific-tool-sourcing` skill
(project folder `cryocodex_skill/` in the maintainers' workspace; not shipped). It holds the pinned clone, ten source
inventories, the preprint with text extracts, license/terms notes, a CLI parity table with an allowlist, I/O parity,
22 resolved contradictions, a gap report, and the server runbook copied here as
[validation_runbook.md](validation_runbook.md). Paths in the runbook that start with `sources/` point into that pack.
Preprint citations written `pp l.N` are line numbers of the pack's text extract of the preprint PDF
(`sources/papers/2026_cheng_cryocodex.txt`); the section and figure context is given alongside where it matters.
New findings go into this skill and `lessons.md`, not into the pack.

## 4. Tier labels used in this skill

- **Tier 1 VALIDATED (live), 2026-11-24**, one Linux Slurm cluster (Ubuntu 24.04, drivers 595.99 / 580.178, RTX 2070 SUPER 8 GB
  and RTX 2080 Ti 11 GB; README route and a shared site launcher; [validation_runbook.md](validation_runbook.md) §0):
  README install (with `PYTHONNOUSERSITE=1`) and package versions; `-h` / `-h advanced` / `--version` texts; the
  download trigger and its failure path; weights size, sha256 and safe load; every argparse and launcher error in 03;
  input-name and non-orthogonal gates (exit 0, no outputs); a user `-m` overriding the launcher's; the four outputs
  for EMD-10387 in default, `--keep_size`, keep + reverse, normal and 40³ cases (grids, NSTART, value ranges, zero
  shell, scores > 1 after reverse resampling, `--keep_size` broadcast error); `--crop_check` with EOF, with silent
  stdin and at a pseudo-terminal; `-g` overriding a scheduler's `CUDA_VISIBLE_DEVICES`; no network egress with the
  weights in place; agreement with the authors' published EMD-10387 result; batch-size determinism and memory;
  stride-46 gaps; GPU memory, host RAM and wall times on the two cards (also for the 432³ README example map); the
  Slurm template end to end. The word **verified** in the references marks these facts.
- **Tier 2 SOURCED:** everything else — code at the pin (rank 2), README (rank 3), notebook (rank 4), preprint (rank 5).
- **Derived:** arithmetic or code reading not observed (RAM per window for normal mode on big maps, maps with both
  ORIGIN and NSTART non-zero, strides other than 12 and 46); always labelled.
