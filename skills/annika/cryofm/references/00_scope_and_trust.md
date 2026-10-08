# 00 — Scope, trust ladder, claims never to make, licences

## 1. Scope

**Does:** explain CryoFM2 and what each `cfm` mode computes; check map headers and geometry; write and verify
`cfm denoise` / `cfm enhance` / RELION wrapper commands with corrected syntax; size batch, memory and walltime; plan
and (on a VALIDATED host, after per-job confirmation) run jobs; read outputs, restore origins, and say honestly what
the outputs are; triage errors; cite pinned sources. CryoFM1 and cryoSeed: explanation only.

**Does not:** install, download weights or submit GPU jobs without explicit confirmation; train or fine-tune
(upstream withholds the training loop); promise accuracy, resolution gains or "no hallucination"; invent flags,
input rules, processing orders or deposition advice that upstream never wrote; upload maps anywhere; transfer a
verdict from one host to another.

## 2. Trust ladder (highest first)

1. **Live behaviour on the validated site** (A100 smoke job 27772096, live `--help` 2026-10-08, launcher source;
   sanitized record in [configs/site_config.example.md](../configs/site_config.example.md)).
2. **Code at the pinned commit** `6448681` (flags, defaults, assertions, file names, header writer). Wins over docs.
3. **Upstream docs / README / HF model card at the same commit and revision** — correct on intent, wrong on nine
   commands (03 §6). Quote them as "the docs say".
4. **The bioRxiv v1 paper** (unrefereed, 2025-12-29): justifies *why* and *when*, never exact flags; several
   paper features are not in the public code (`keep_lowres`, final-iteration skip, continuous anisotropic weight,
   adaptive likelihood weight).
5. **Gradio demo branch** (authors' UI defaults, not recommendations) and **community** (2 GitHub issues, one
   independent study ARCHER, no forum traffic). Lowest.

Label statements accordingly: *verified on this host* / *static code* / *docs* / *preprint claim* / *derived*.

## 3. State machine (see SKILL.md): UNCONFIGURED → PROBED → VALIDATED. A probe never yields VALIDATED; a passed GPU
fixture recorded in the site config does. Stale after host/image/weights/driver changes or 90 days.

## 4. Claims never to make

- "CryoFM2 improves resolution to X Å" or "removes noise without hallucination" — the paper's claims are preprint
  claims; half-map metrics are inflated; no hallucination test exists.
- "The two outputs are half maps you can post-process for a gold-standard FSC."
- "Works on CPU / Apple Silicon / AMD" — undeclared and untested (accelerate would pick `mps`/`cpu`; nothing validated).
- "Validated on V100 with `--bf16`" — only the README's "tested on V100 and A100" exists; bf16 on V100 is unknown.
- "RELION integration works end to end" — static reading predicts failure at the final joined iteration; nobody ran it here.
- "The quick-start commands work as printed" — four do not.
- "Use the unfiltered half maps" / "sharpen afterwards" / "deposit as …" as upstream advice — all undocumented; give
  the context (training data were EMDB half maps; EMReady-style trained on sharpened deposited maps) and say so.
- "Multi-GPU lowers memory" — it splits patches only.
- "`--mask-path` masks the output" — it only crops the sampling region with `--bbox`.
- "The output keeps the input origin" — it does not.
- "300–500 steps give higher quality" — 300/400 integrate only part of the flow; the paper found no gain beyond ~200.
- "Default `--cfg-weight` depends on the model" — it is 2.0 for every model.
- Anything about cryoSeed beyond "research module on `unstable`, not documented".
- "The weights are peer-reviewed / officially supported / integrated into ByteDance products" — the paper says
  "research purposes only and not integrated into ByteDance technologies".
- Numbers not in [09](09_evidence_and_benchmarks.md) or the site config.

## 5. Licences and terms (texts only; no legal advice)

| Item | Licence / terms |
|---|---|
| Code (GitHub `ByteDance-Seed/cryofm`) | Apache-2.0 (`LICENSE`, per-file headers "Copyright 2025 Bytedance Ltd. and/or its affiliates"); bundled code from k-diffusion (MIT), Diffusers (Apache-2.0), CryoSTAR (Apache-2.0), pytorch3d (BSD), fairseq (MIT), relion-blush and spIsoNet-derived functions. `gradio-demo` branch has no LICENSE file |
| Weights (HF `cryofm-v2`, `cryofm-v1`) | card `license: apache-2.0`, not gated, no extra terms; "Ethical Considerations" ask for attribution, experimental validation, bias awareness. No statement about outputs |
| Dataset lists (Zenodo 10.5281/zenodo.18013604) | Zenodo metadata CC BY 4.0 vs zip README "Apache License 2.0" — **conflict**, both permit reuse with attribution |
| EMDB maps (training data, fixtures) | "free of all copyright restrictions … non-commercial and commercial use"; attribute authors and accession ids |
| CryoFM2 preprint | CC BY-NC-ND 4.0 (applies to the paper text, not to code or weights) |
| CryoFM1 paper | arXiv non-exclusive licence; ICLR 2025 |
| Imitated styles | DeepEMhancer Apache-2.0; EMReady v1 GPL-3.0 (website), v2 MIT; CryoFM2 ships none of their code; terms of the EMReady-provided simulated training maps are not stated |

Commercial use of weights or outputs: only Apache-2.0 is stated; nothing restricts it and nothing about outputs is
written. Point commercial questions to the rights holders. Cite per [01](01_source_map.md).

## 6. Privacy

Default `cfm` and wrapper runs make no network calls (static import closure has no HTTP client; the validated site's image sets
`HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 WANDB_MODE=disabled`). Egress happens only when *you* download weights
(`hf download`), run the Gradio demo (HF + ByteDance CDN, binds 0.0.0.0 under `SPACE_ID`), use cryoSeed `--model-id`,
or the CryoFM1 dataset script (EMDB mirrors). Logs contain absolute paths and the full command line. `config.yaml`
is loaded with a full YAML loader: use only hash-verified weights folders.
