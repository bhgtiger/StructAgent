# 00 — Scope, trust ladder, claims never to make, licences

## 1. Scope

**Does:** explain what CryoCodex computes and what its four outputs mean; check map headers against the input
gates; write and check `predict.sh` commands (fast/normal mode, `True|False` option values, batch, stride, GPU,
resampling, keep-size); plan an install that follows the README; size host RAM and choose a batch size; plan and
(on a VALIDATED host, after per-job confirmation) run jobs; check outputs; triage errors; flag privacy and weights
issues; cite pinned sources.

**Does not:** install, download the weights or run GPU jobs without explicit confirmation; train or fine-tune
(no training code upstream); promise resolution gains or "no hallucination"; invent flags, input rules or deposition
advice the authors never wrote; upload maps anywhere (including Colab); transfer a verdict from one host to another;
cover the Scipion plugin beyond a pointer (deferred in v0, see [06](06_interoperability.md)).

## 2. Trust ladder (highest first)

1. **Live behaviour on a validated host** — one Linux Slurm cluster, 2026-11-24 ([01 §4](01_source_map.md),
   [validation_runbook.md](validation_runbook.md) §0). It ranks first **for what was run there**; a new host repeats the
   runbook and records it in `configs/site_config.local.md` and `lessons.md`.
2. **Code at the pinned commit** `a35e73a` (`predict.sh`, `predict.py`, `grid_utils.py`, `data_processor.py`,
   `crop_check.py`): flags, defaults, file names, headers, messages. Wins over everything below.
3. **README at the same commit** (the only documentation; no docs site). Right on intent, wrong in places
   (download timing, what `--keep_size` restores, stride range — see [03 §5](03_cli_reference.md)).
4. **Colab notebook in the repo** (`CryoCodex.ipynb`, pins its own commit `6d1a740` with identical Python files):
   shows the authors' defaults for the notebook route only.
5. **bioRxiv preprint v1** (10.64898/2026.09.30.755675, posted 2026-10-02, CC BY-NC-ND 4.0, **not peer reviewed**):
   justifies *why* and *when*, never flags. Where it disagrees with code (trilinear vs cubic resampling), code wins for
   behaviour.
6. **Community** — none: 0 issues, PRs or Discussions on 2026-11-24.

Label statements: *verified on this host* / *source code* / *README* / *preprint claim* / *derived (code reading or
arithmetic)*.

## 3. State machine

UNCONFIGURED → PROBED → VALIDATED (SKILL.md). A probe never yields VALIDATED; a passed fixture run recorded in the site
config does. Stale after host, GPU/driver, env, clone commit or weights change, or 90 days.

## 4. Claims never to make

- "Runs on CPU / Apple Silicon / macOS / Windows / AMD" — device is hard-coded `cuda:0`; README requires Linux + CUDA GPU.
- "`-g 0,1` uses two GPUs" or "`-g` respects the scheduler's GPU" — only the first visible device is used and `-g`
  overwrites `CUDA_VISIBLE_DEVICES` (verified: a job given GPU 1 ran on GPU 0 without `-g`).
- "A conda env isolates CryoCodex from `~/.local`" — it does not (verified both at install and at run time).
- "The weights checksum is published" — the sha256 in 01 is our recorded observation, not an authors' value.
- "The weights are MIT / redistributable / free for commercial use" — no terms are published for the checkpoint.
- "The download is checksum-verified" or "the server ETag is a hash" — neither (the ETag's first field is the size).
- "`--version` is side-effect free" — it triggers the first-run download through `predict.sh`.
- "Boolean flags work without a value" or "accept 1/0/yes/no".
- "`--crop_check True` works in batch, Slurm or Scipion".
- "Score maps are local resolution (Å), FSC or Q-score" or "always within [0, 1]".
- "The mask is soft / a probability map" — the saved mask is binary.
- "Outputs are on the input grid by default" or "`--keep_size True` alone reproduces the input box".
- "There is a hosted CryoCodex web server" or "Colab keeps the map private".
- "CryoCodex beats DeepEMhancer / LocScale" — not compared in the preprint.
- "The authors recommend enhanced maps for refinement / validation / deposition" — the preprint is silent.
- "The paper is peer reviewed", "the paper's numbers will be reproduced on your map", "trained up to date X"
  (no cutoff stated; check the published train/valid lists instead, [08](08_validation_and_benchmarks.md)).
- "`pip install cryocodex` exists", "Python 3.12 / aarch64 / micromamba are supported", "training is supported".
- Runtime, VRAM or RAM figures for a GPU other than the ones measured (paper's A800; RTX 2070 SUPER, 2080 Ti in 05 §4)
  unless measured on the host.
- A runbook result from one host as valid on another — each host runs the runbook itself.

## 5. Licences and terms (texts only; no legal advice)

| Item | Licence / terms |
|---|---|
| Code `YangLab-SDU/CryoCodex` | MIT, "Copyright (c) 2026 Bin Cheng" (`LICENSE:1-3`) |
| Adapted third-party code | VAR (`quant.py`), EMReady2 (`grid_utils.py` I/O + interpolation), model-angelo (`make_cubic`, auto-mask) — all MIT (`THIRD_PARTY_NOTICES.md`) |
| Weights `CryoCodex.pth` | **no terms published** (README, LICENSE, release, lab page and preprint checked 2026-11-24) |
| Preprint | CC BY-NC-ND 4.0 (paper text only) |
| Benchmark lists and author results on the lab site | no terms stated |
| EMDB maps used as fixtures | EMDB terms: free use with attribution of the entry |

Citation requested by the README: the bioRxiv preprint (BibTeX in [01](01_source_map.md)).
