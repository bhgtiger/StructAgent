# 09 — Evidence tiers, paper claims, validation record

## 1. Tier A — verified on the validated site (A100 40 GB, 2026-10-08; sanitized record in [configs/site_config.example.md](../configs/site_config.example.md))

| Item | Result |
|---|---|
| Build | job 27771682 (CPU build partition) rc 0; image sha256 `5170640312574b14c9bd07e7a86c329c68dfa25730731107818b66bce4d896b4` |
| Weights | three variants sha256 = HF LFS digests at `4e308f7f` |
| Smoke | job 27772096, A100 partition (A100-SXM4-40GB, driver 615.71.09), 8 m 32 s, COMPLETED 0:0: `cfm denoise --op denoise` on EMD-11638 half maps (251 s), `cfm enhance` emhancer (121 s), emready (119 s); all outputs finite, input grid and pixel size, origin 0; peak 21 443 MiB (batch 4, bf16) |
| Sanity | job 27772406: low-pass CC vs input 0.986–0.997 (denoise), 0.952/0.796 (emhancer), 0.705/0.806 (emready) at 3.5/6 Å; axis-permuted control 0.34–0.42; denoised-half FSC = input-half FSC |
| CLI | live `--help` for `cfm`, both subcommand stubs, both modules — identical to the static inventory (Python 3.10 `options:` heading) |
| Wrapper | `relion_wrapper.py --help` on a CPU node recurses through `accelerate launch` until killed (do not do this) |

Not run: inpaint/non-uniform, enhance with halves, masks, multi-GPU, RELION loop, H100, any map other than the fixture.

## 2. Tier B — static code facts (pinned `6448681`)

Everything in [03](03_cli_reference.md), [04](04_inputs_and_geometry.md), [06](06_operators_and_tuning.md) and the
hazards of [07](07_relion_integration.md). Derived consequences (batch-size coupling, incomplete integration for
N ∤ 1000, final-iteration abort, numpy broadcast on box mismatch, FSC inflation by `--fsc-weighting`) are reasoned
from the code and toy re-enactments, not measured.

## 3. Tier C — what the preprint claims (bioRxiv v1, unrefereed; say "the authors report")

- **Model**: 3D U-Net (64/128/256/512 channels, attention at the two deepest levels, head dim 8), flow matching with
  v-prediction, 64³ patches at 1.5 Å, pretrained 300 k steps on 8 H100 (global batch 96) on 3 479 EMDB maps
  (< 3.0 Å, half maps available, 32 held out, boxes ≤ 576 Å, no helical/huge assemblies), 24 rotation/flip
  augmentations, EMA 0.99. Fine-tunes: +300 k steps each; EMhancer-style on DeepEMhancer's lists (104/21/20 maps;
  DeepEMhancer's own paper says 107/21/20), EMReady-style on EMReady's lists (280/70/90; EMReady's paper says 110 test).
- **FPS**: `v ← v − t/(1−t)·∇log p(y|x_t)` with Laplace approximation, normalised gradient, capped weight; 200
  steps; likelihood from half maps (isotropic spectral noise), plus particle poses (anisotropy-aware) or per-band
  local variance (non-uniform). Missing-cone ablation: ~10 steps give most of the gain, no systematic gain beyond,
  degradation at β ≥ 60° with long chains.
- **Refinement benchmarks** (RELION `--external_reconstruct`, FPS from the first iteration, not in the final one):
  EMPIAR-11792 tilt series (no gain vs RELION/Blush on a well-behaved set); EMPIAR-10096/10097 HA trimer
  (anisotropy-aware: clearer features and model-FSC, but half-map anisotropy metrics favoured Blush/spIsoNet;
  printed 3DFSC sphericity/resolution on 10097: RELION 0.842/4.25, Blush 0.923/4.19, cryoSPARC 0.836/4.19, spIsoNet
  0.984/4.14, cryoFM 0.858/4.36 Å); nine particle sets (EMPIAR-10330, 11762, 12510, 11247, 10420, 11910) with the
  local-noise likelihood: "improved map quality relative to standard refinement, and performance at least comparable
  to the best existing approaches"; Blush sometimes higher GS-FSC.
- **Post-processing**: EMhancer-style beats DeepEMhancer on map-model FSC and real-space CC; EMReady-style beats
  EMReady on map-model FSC while "EMReady obtained slightly higher values" in real-space CC; box plots only, no
  per-map numbers, no statistics, no run-to-run variance.
- **Caveats the authors state**: GS-FSC can be inflated by shared priors ("relying solely on GS-FSC-based metrics can
  be misleading"); a non-negativity clip alone raises FSC; the prior covers only high-resolution maps; patch-based
  training limits global context (symmetry, large assemblies); sampling is slow; operators are estimated globally
  and applied locally. Abstract claims "without introducing hallucinated features" with no dedicated hallucination test.
- **Not in the paper**: parameter count, memory, CPU/other GPUs, output tags, λ values, number of bands, RELION
  version, per-dataset commands, deposition advice.

## 4. Tier D — third parties and community

- **ARCHER** (bioRxiv 2026, independent): uses `cfm denoise` as a restoration baseline on RELION half maps; finds
  both restorers "suffer on the resulting low-quality reconstructions" when poses are strongly shuffled; benchmark
  rule "restore every arm or none". The only independent run found.
- **Citations**: CryoFM1 ≈ 9 (mostly related-work); CryoFM2 0 by 2026-10-08. One third-party critique (CryoFM1):
  robustness "on genuinely noisy, low-resolution experimental maps … remain unvalidated".
- **Support**: 2 GitHub issues (OOM → `--batch-size 2`; display → contour level), no forum threads anywhere, 8
  forks with zero commits ahead, HF downloads in the low hundreds. Troubleshooting must come from code and docs.
- **Scope of validation anywhere**: no public end-to-end RELION run, no multi-GPU timing, no CPU/MPS run, no
  low-resolution (> 4.5 Å) benchmark, no ligand/nucleic-acid-specific evaluation, no helical/tomo use.

## 5. How to talk about results

"CryoFM2 (commit 6448681, weights 4e308f7f) processed the half maps with `--op denoise`; the output is a prior-
regularised map band-limited at 3 Å; map-model FSC@0.5 changed from X to Y against PDB NNNN; the GS-FSC of the two
outputs is not independent and is not reported as resolution." Never quote a resolution gain from the FSC of the two
outputs, and label every number from §3 as the authors' preprint result.
