# 06 — Operators and tuning knobs (code defaults, effects, documented guidance)

Source: pinned code (`sampling_helper.py` = SH, `uncond_sampling.py` = U, `cond_sampling.py` = C), upstream docs
(quick-start QS, likelihood-control LC, operators OPS, common-issues CI), the HF model card, the bioRxiv v1 paper
and the authors' Gradio demo (UI defaults, not advice). "DERIVED" = reasoned from code, never measured; the validated site's
smoke run exercised only the defaults.

## 1. How an operator is chosen

`--op` is `nargs="+"` without `choices`; the sampler tests membership on the list in this order:

| `--op` contains | Branch | Data term | Extra inputs |
|---|---|---|---|
| `inpaint` but not `denoise` | hard Fourier replacement of observed voxels, no gradient | none (λ flags inert) | particle STAR |
| `denoise` but not `inpaint` | FSC/energy-weighted Fourier MSE, weight `1/(1−FSC)/power` | yes | two halves |
| `denoise` and `inpaint` | the same MSE restricted to observed voxels, FSC/energy modulated by the sampling density | yes | halves + STAR |
| `non-uniform` (and neither above) | wavelet-band weighted MSE, weight `1/(0.5·(A−B)²_band + 1e-6)` | yes | two halves |
| none of these | `UnboundLocalError` on `cond_v_t` (DERIVED) | — | — |

`denoise non-uniform` therefore runs `denoise`. `keep_lowres` (an extra post-processing token the paper used for
"retain the reference up to 10 Å") needs a reference volume the CLI never sets — **not usable**. Repeating `--op`
replaces the list (argparse store); the quick-start anisotropy example loses `inpaint` this way.

Posterior update per Euler step (den and enh-post): `x̂₀ = x_t − t·v`, loss on `A(x̂₀)` vs the observed half,
`v ← v + λ_w·λ_base·∇loss/‖∇loss‖` (norm over the whole batch), `x_{t−h} = x_t − v·h/1000`, with
`λ_w = min(t/(1000−t), λ_max)` when `--use-lamb-w` else 1. In `cfm enhance` posterior mode CFG is applied after
this step: `v = (1+w)·v_guided − w·v_uncond`.

## 2. Likelihood knobs (den, enh-post, RELION)

| Knob | Default | Effect | Upstream guidance | DERIVED caveats |
|---|---|---|---|---|
| `--norm-grad` | False | unit-norm gradient | "must be enabled … Disabling it will cause unstable sampling" (LC); every recipe sets it | code **asserts** it; the docs understate |
| `--use-lamb-w` | False | decaying weight t/(1000−t), capped | "stronger data constraints in early sampling steps … more reliance on the model prior in later steps"; set in every likelihood recipe and by the demo | without it λ_w = 1 for all t (constant push; not what the paper describes) |
| `--lamb-w-max` | 5.0 | cap on λ_w (reached for t ≳ 834) | "maximum guidance strength in early timesteps" | paper gives no number (CryoFM1 used 5) |
| `--lamb-base` | 1000.0 | base step of the data term | "one of the most important parameters, directly affecting the balance between data consistency and prior"; recipes use 1000.0; demo slider 0–2 ×1000 | total displacement ≈ 1.0·λ_base (≈1.8·λ_base with `--use-lamb-w`) in normalised units; ×(1+CFG) in enh-post. No tuning rule published |
| `--num-timesteps` | 200 | Euler steps, integer step h = 1000 // N | "Quick preview: 50-100 / Standard: 200 (recommended) / High quality: 300-500"; paper used 200 | N ∤ 1000 integrates only 0.9 (300), 0.8 (400) of the path; paper SI: no systematic gain beyond ~10–200 steps on synthetic missing cones, degradation at β ≥ 60° |
| `--fmask-threshold` | 10.0 | back-projection count ≥ threshold = observed | "Controls which frequency regions are considered missing"; recipes 10 | an absolute particle count, so it scales with particle number; no guidance |
| `--data-starfile-path` | None | particle poses for the inpaint mask | required by every inpaint recipe | missing → `TypeError … NoneType` inside `starfile` |
| `--nbands` | 64 | equal-width radial Shannon-wavelet bands | "Controls the frequency decomposition granularity" | memory/time ∝ nbands; batch-summed weights for batch > 1 |
| `--seed` | None | den: `torch.manual_seed` at **every batch** | none | fixed seed → both halves share the initial noise; None → irreproducible; enhance ignores it |
| `--threshold-res` | 10.0 | only `keep_lowres` | appears in the RELION string | inert |

## 3. Style knobs (enh-pure, enh-post)

| Knob | Default | Effect | Guidance |
|---|---|---|---|
| `--output-tag` | 1 | class label into a 5-row embedding | 1 = EMhancer, 0 = EMReady (card, docs, demo). Tags 2–4 exist but untrained; ≥ 5 → index error (CPU `IndexError`, CUDA device-side assert) |
| `--cfg-weight` | 2.0 | classifier-free guidance; both branches always evaluated in pure mode | EMhancer 1.5–3.0 (default 2.0); EMReady 0.3–0.7 (pass 0.5); paper: 2.0 and 0.5 |
| `--odeint` | euler | solver, pure mode only | docs say euler only; code also accepts `rk4` (4 evals/step), `midpoint`, `heun`, `ralston` (2/step), `midpoint_no_bar` |

## 4. Shared execution knobs

| Knob | Default | Effect | Guidance / measured |
|---|---|---|---|
| `--batch-size` | 4 | patches per forward per process | docs table (G): likelihood bs 1/2/4 = 7.3/13/24 without bf16, 6.9/11/21 with; pure enhance bs 1/2/4/8 = 4.1/5.8/9.1/16 and 3.8/5/7.3/19.9. measured on an A100 40 GB: **21 443 MiB** at 4 + bf16 (denoise). Maintainer: 16 GB → 2. DERIVED: also changes the posterior (shared gradient norm; summed non-uniform weights) |
| `--bf16` | False | autocast bf16 around UNet and loss; FFT float32 | "Always use `--bf16` if possible" (A100/H100; V100 behaviour unknown). Clones older than 2026-01-23 ignored it for `cfm denoise` |
| `--patch-size` | 64 | patch edge at 1.5 Å (96 Å field of view) | keep 64 (trained size; pure enhance hard-codes 64 for the noise) |
| `--patch-overlap` | 32 | stride = 64 − overlap; plain averaging of overlaps | 0 → 8× fewer patches (seams), 48 → ~6–8× more; no guidance |
| `--mask-path` + `--bbox` | None / False | crop sampling to the mask bbox (+5 voxels, ≥ 64) | "to speed up CryoFM inference"; the paper's 44 s / six patches was measured this way; mask without `--bbox` does nothing |
| `--spectral-mixing` | False | MRC: raw input pasted above ≈3 Å; STAR: Blush-style mixing/trailing | "experimental feature"; in the RELION string |
| `--skip-spectral-trailing` | False | STAR + mixing only: skip the FSC(1/7) low-pass | in the RELION string; RELION's Blush analogue warns it "may inflate resolution estimates" |
| `--fsc-weighting` | False | sqrt(FSC of the two outputs) per shell; wavelet Wiener filter with `non-uniform` | "preserve high-frequency details"; DERIVED: inflates output FSC (toy: pure noise halves → FSC +0.83 with non-uniform); barrier only on rank 0 |
| `--no-ema` | False | no effect (EMA shadow = loaded weights) | — |
| `--debug` | False | writes patches, FSC plot, FSC/energy volumes, fmask, model-grid in/out next to the outputs | use once to inspect the inpaint mask |
| `--log-file-path` | None | adds a file handler; directory must exist | always set it in jobs |
| `--num_processes`, `--main_process_port` (launcher) | — | `accelerate launch`; patches split across GPUs | per-GPU memory unchanged; results may differ with N |

Environment: `CRYOFM_MODEL_DIR` (wrapper fallback), `CRYOFM_HALF1_PORT`/`CRYOFM_HALF2_PORT` (29500/29501),
`NCCL_DEBUG=ERROR` (docs), `CUDA_VISIBLE_DEVICES` (GPU choice). The validated site's launcher adds `CFM_NO_NV` / `CFM_FORCE_NV` (site-specific, [03 §7](03_cli_reference.md)).

## 5. Hard-coded constants

`MODEL_VOXEL_SIZE 1.5`, mean 0.04 / std 0.09, percentile 99.999, `EPS_FSC 1e-5`, `BBOX_ENLARGE 5`, train timesteps
1000, class embeddings 5, STAR mixing threshold FSC 1/7, 3-shell crossover, radial-mask edge 20·pixel, back-projection
batch 256 particles.

## 6. What is not tunable

No symmetry, no helical mode, no device flag, no pixel-size override, no output-origin option, no per-region λ, no
blind/semi-blind operators (paper: future work). Training code is not released (`NotImplementedError` in the training
steps); do not improvise a fine-tuning recipe.
