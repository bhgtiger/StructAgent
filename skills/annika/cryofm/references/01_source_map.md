# 01 — Source map (pins, URLs, how to cite)

## 1. Pinned sources

| Source | Pin | Notes |
|---|---|---|
| Code `main` | https://github.com/ByteDance-Seed/cryofm @ `64486814723010bd200525cda2fa463a25ba1339` (2026-03-03, "Update README.md", 16 commits) | Apache-2.0, **no tags, no releases, no PRs**, 2 issues. Package `cryofm` 0.1.0 at every commit (version string cannot identify the code) |
| `unstable` | `6792340da4def68bfe7c2ebe154c2799c5f1b3ae` (2026-08-11) | = main + `relion/cryoseed/` (144 files); nothing else differs |
| `gradio-demo` | `bacde8d1ff2ac5ad242e4e2dcf39fe226b3d7a61` (2026-01-07) | unrelated root; `app.py` only ever calls `cfm enhance` |
| Docs | https://bytedance-seed.github.io/cryofm/docs/ (MkDocs from `user-guide/`), last deployed from `abe3ac83` (2026-01-23); `user-guide/` identical at `6448681` | pages: getting-started/installation, model-guides/cryofm2/{index,quick-start,likelihood-control,operators,unconditional-sampling,gui-demo}, cryofm1/{index,sampling,downstream-tasks}, how-to/{working-with-cryo-em-software,working-with-emdb}, troubleshooting/common-issues |
| Website / blog | https://bytedance-seed.github.io/cryofm/ , blog/cryofm2 (2025-12-24) | claims only |
| Weights v2 | https://huggingface.co/ByteDance-Seed/cryofm-v2 @ `4e308f7f028af46ca2c7ee5af81e29775bc370dd` (2026-01-16; weights unchanged since `0ef798b8`, 2025-12-25) | `cryofm2-pretrain/model.safetensors` 672 397 148 B sha256 `8f10dc55…9512f413`; `cryofm2-emhancer` 672 409 268 B `96576420…dbfaee163`; `cryofm2-emready` 672 409 268 B `77c1fa59…c6d2bca`; all F32, 168.09 M / 168.09 M params |
| Weights v1 | https://huggingface.co/ByteDance-Seed/cryofm-v1 @ `4b5c5baba2d76bc5f0fc1cb2475dd43e3346895b` | `cryofm-s` (1.5 Å, 64³, 335 M), `cryofm-l` (3.0 Å, 128³, 309 M); not covered by the validated install |
| Dataset lists | https://zenodo.org/records/18013604 (doi:10.5281/zenodo.18013604), `cryoFM-emdb-lists.zip` 358 328 B | pretrain train/test (3 430 / 32 EMDB ids), EMhancer and EMReady train/val/test lists |
| CryoFM2 paper | Li Y., Yuan J., Zhou Y., Wang Z., Chen S., Yang F., Ling H., Kovalsky S. Z., Zheng X., Gu Q. "A Generative Foundation Model for Cryo-EM Densities", bioRxiv v1 2025-12-29, doi:10.64898/2025.12.29.696802, CC BY-NC-ND 4.0 | **no peer-reviewed version** as of 2026-10-08 |
| CryoFM1 paper | Zhou Y. et al., "CryoFM: A Flow-based Foundation Model for Cryo-EM Densities", arXiv:2410.08631, ICLR 2025 (OpenReview T4sMzjy7fO) | HDiT model, synthetic benchmarks |
| Issues | #1 OOM on 4×16 GB (open, maintainer: `--batch-size 2`), #2 quick-start display question (closed; contour level) | maintainer = co-author |
| Third-party use | ARCHER (`ndnng/ARCHER`, bioRxiv 2026): runs `cfm denoise … --op denoise --norm-grad --use-lamb-w --bf16` on RELION half maps as a restorer baseline | only independent script found |
| RELION side | `3dem/relion` 5.1.1 @ `29dfb4e3`; tags 3.0.8–5.1.1 read for the external-reconstruct contract | ≥ 4.0.1 writes `rlnPixelSize`/`rlnParticleDiameter` |

## 2. Validated-site install record

The 2026-10-08 install and GPU validation (Apptainer image built from a definition that pins the base-image digest, the
source tarball sha256 and a hash-locked dependency list; weights fetched and sha256-verified against the HF LFS digests;
a site launcher; one A100 smoke job and one low-pass CC job) is summarised, sanitized, in
[configs/site_config.example.md](../configs/site_config.example.md). The unsanitized record (real paths, account, job
scripts, logs) lives only in the site copy's git-ignored `configs/site_config.local.md` and in the site's own install
folder; neither is bundled.

## 3. Evidence folder behind this skill (not bundled)

The gathering project's `sources/` folder (2026-10-08, adversarially verified, pinned to commit `6448681` and HF
`4e308f7f`) is **not bundled** with this skill and is not kept at a fixed path: ask the maintainer. It held static
inventories of code (`source/cli_reference.md`,
`io_formats.md`, `configs_reference.md`, `model_loading_and_weights_code.md`, `fixtures_headers.md`,
`mrc_header_semantics.md`), algorithms (`algorithms/*.md`), RELION/cryoSPARC interop (`interop/*.md`), docs/web/weights
(`web/*.md`), papers (`papers/*.md` + PDFs), community (`community/*.md`), environment (`environment/*.md`), usage rules
(`usage/decision_rules_evidence.md`, `scenario_matrix.md`), errata (`errata/errata_log.md`). Every claim there carries a
`file:line` citation into the clone `sources/source/cryofm/` at `6448681`. When a user asks "where does that come from"
and the references here do not answer it, ask the maintainer.

## 4. How to cite

- Software/method: the CryoFM2 preprint (doi:10.64898/2025.12.29.696802) and, for the model family, the CryoFM1
  ICLR 2025 paper (arXiv:2410.08631). README: "If you use CryoFM in your research, please cite the relevant paper(s)".
- Code: `ByteDance-Seed/cryofm`, commit `6448681` (no release to cite). Weights: HF `ByteDance-Seed/cryofm-v2`,
  revision `4e308f7f`. Dataset lists: Zenodo doi:10.5281/zenodo.18013604.
- Styles imitated: DeepEMhancer (Sanchez-Garcia et al. 2021), EMReady (He et al. 2023), LocScale (Jakobi et al. 2017)
  when you describe what the fine-tuned models emulate. RELION 4/5 and Blush for the external-reconstruct protocol.
- Say "processed with CryoFM2 (`cfm denoise --op …`, commit 6448681, weights 4e308f7f)" in methods; keep the raw
  half maps as the deposited ones.
