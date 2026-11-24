# 06 — Interoperability: ChimeraX, using the outputs elsewhere, Scipion (deferred), Colab (warning only)

## 1. Colouring a map by the local-quality scores in UCSF ChimeraX (README)

The README's recipe (`README.md:342-371`). Open the map and its score map, e.g.

```text
#1   deposited map
#2   cryocodex_in_score.mrc
```

then colour the surface of `#1` by the values of `#2` (verbatim, `README.md:356`):

```bash
color sample #1 map #2 palette "#1B3A5F:#245A8D:#2F80C0:#6BAED6:#BFD9EA:#7F7F7F:#C9B458:#FEE191:#F9B233:#FC8E59:#F04438:#DC3223:#8B0000" key true ; key fontSize 11 size 0.65,0.02 pos 0.18,0.06 colorTreatment distinct
```

For the enhanced map use the enhanced-map score the same way (`README.md:363-371`):

```text
#3   cryocodex.mrc
#4   cryocodex_out_score.mrc
```

```bash
color sample #3 map #4 palette "#1B3A5F:#245A8D:#2F80C0:#6BAED6:#BFD9EA:#7F7F7F:#C9B458:#FEE191:#F9B233:#FC8E59:#F04438:#DC3223:#8B0000" key true ; key fontSize 11 size 0.65,0.02 pos 0.18,0.06 colorTreatment distinct
```

Notes (ours, not the README's):
- Blue = lower, dark red = higher predicted local quality. The palette carries **no numeric values**, so ChimeraX
  spreads it over the range it samples; the README's own panels use different ranges (`README.md:79-80`). To compare
  `in_score` with `out_score`, or two maps, pin the range with ChimeraX's `range 0,1` option of `color sample`
  (a ChimeraX option, not in the CryoCodex README — check `usage color sample` in your ChimeraX).
- `color sample` samples by position, so the score map may be on a different grid (1 Å, cropped) than the coloured map;
  it relies on both maps being placed correctly. CryoCodex stores placement only in NXSTART/NYSTART/NZSTART
  ([04 §6](04_data_model_and_formats.md)): check once that the score map overlays the map before trusting the colours.
- Scores are predicted local SSIM against a model-simulated map, not resolution in Å; do not label a colour key "Å".
- Show the mask as a surface at level 0.5 (it is 0/1).

## 2. Using the outputs in other programs

| Output | Reasonable use | Watch out for |
|---|---|---|
| enhanced map | visualisation; manual or automated model building (the only downstream use the preprint evaluated: `phenix.map_to_model` on chain-extracted sub-maps, pp l.270-281) | the authors give **no** advice on refinement, validation or deposition (M14). General practice, not theirs: validate and refine models against the experimental map, deposit the experimental map as the primary map, and describe any post-processed map as such |
| `in_score` / `out_score` | find weak/uncertain regions; colour maps; per-atom values (e.g. ChimeraX `measure mapvalues` — check `usage measure mapvalues`) | not local resolution; correlation with per-atom Q-score is modest (Spearman, per-map mean 0.22 for `in_score`, 0.47 for `out_score` vs enhanced-map Q-scores; pp l.648-667) |
| `in_mask` | molecular envelope; starting point for a mask | hard 0/1 edge on the 1 Å grid (or the input grid with `--reverse_interpolation True`); for refinement, subtraction or FSC masks resample it onto the reference grid and add a soft edge in your mask tool — whether it suits those uses is not stated by the authors |

Resampling to another grid (e.g. ChimeraX `volume resample #mask onGrid #reference`) changes values at edges:
re-threshold a resampled mask at 0.5 before using it as binary.

**Input conversions that are safe**: `.map.gz` → decompress; `.ccp4` → same MRC format, copy/symlink to a `.mrc` name;
upper-case `.MRC` → rename. Maps with non-90° cell angles (crystallographic) are refused by CryoCodex.

## 3. Scipion plugin — not covered in v0 (pointer only)

`scipion-em/scipion-em-cryocodex` 0.3.2 (PyPI; MIT; same author) wraps CryoCodex v1.0.0 @ `a35e73a`. What its source
shows (not executed): protocol defaults batch 9, stride 12, fast mode; it always passes `--crop_check False --no_logo
True` and offers a GUI crop wizard instead; it runs `predict.py` directly in a private conda env (no `predict.sh`, no
`CRYOCODEX_ENV`); its installer computes the checkpoint SHA-256 but never compares it with anything; it allows stride
1–48 (this skill keeps 1–44) and reports scores as "0 to 1" (they can exceed 1 after reverse interpolation). Install,
GUI and GPU runs are untested; the runbook's R19 is optional. Ask before adding this route.

## 4. Google Colab notebook — privacy warning only

The README's "Online inference" badge opens `CryoCodex.ipynb` in the **user's own** Google Colab session. To run, the
map is **uploaded to a Google-hosted VM**; the results viewer loads three.js from jsdelivr in the browser. There is no
hosted CryoCodex server (the preprint's "web server … on Google Colab" is this notebook). Never suggest it for
unpublished, confidential or proprietary maps; this skill does not support the Colab route. If a user already uses
it: the notebook pins commit `6d1a740` (same Python files as v1.0.0) and has its own batch heuristic and OOM retry
that the CLI lacks.

## 5. Other post-processing tools

The preprint compared CryoCodex with CryoTEN, DEMO-EMReF, EMReady and EMReady2 (enhancement) and CryoRes (quality,
mask) — **not** with DeepEMhancer or LocScale. Do not rank CryoCodex against tools it was not compared with.
