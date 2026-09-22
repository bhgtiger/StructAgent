# 01 — Source Map

This page lists where every claim in the skill can be checked. All sources were retrieved on **2026-09-22** unless a row
says otherwise. Citation style inside the skill is `openfold-3@v0.5.0:<path>` and `uplifting-biomolecular-modeling@f4f62fa:<path>`.
This is a source review; host validation is described in `09_validation_and_benchmarks.md`. To refresh this page, see
`maintenance.md`.

## Upstream OpenFold3

| Item | Identity | Authoritative for |
|---|---|---|
| Repository | https://github.com/aqlaboratory/openfold-3 (Apache-2.0, `LICENSE`) | Code, examples, in-repo docs |
| Release **v0.5.0** "OpenBind Model Release" | Tag `v0.5.0`, commit `c4771653c5d0a3ebb0b3af71b05efd64bc44ee86`, published 2026-08-21: https://github.com/aqlaboratory/openfold-3/releases/tag/v0.5.0 | The skill's pin. The release note says preview-2 weights are deprecated on `>=0.5`. It misspells the checkpoint key as `openbind-2025-06-03-174k`; use the registry spelling |
| Tag **0.4.1** | Commit `d12f59554adacf8638e41f1ebc2d7725a8bb7a4b` (2026-04-09) | Legacy kit `openfold3/` only (preview-2 weights) |
| `main` snapshot | `68b9c5e7fc44b1ca6f16e36bff2aee1656ca6919` (2026-09-22), 48 commits after v0.5.0 | Drift watch only. It is not a release and the kit refuses it |
| PyPI | `openfold3==0.5.0`, wheel sha256 `9948071ed086ec063dac2b7d47a8d31a352536baab80a23f436158dbedfde721` (from kit `stock/PINS.json`) | Packaged install identity |
| Software citation | Zenodo **software** DOIs (not paper DOIs): v0.5.0 record `10.5281/zenodo.22042719`; concept DOI (all versions) `10.5281/zenodo.17485509`. The README BibTeX DOI `10.5281/zenodo.19001000` resolves to the 0.4.0 record and `CITATION.cff` to 0.3.1 (`10.5281/zenodo.17485510`) | How to cite upstream |

### Key source paths at `v0.5.0`

| Path | Authoritative for |
|---|---|
| `openfold3/run_openfold.py` | Click CLI. Commands `predict`, `train`, `align-msa-server`. Option names and aliases. Value-taking `BOOLEAN` flags. Loading `$OPENFOLD_CACHE/runner.yml` |
| `pyproject.toml` `[project.scripts]` | Console scripts `run_openfold`, `setup_openfold`, `validate-openfold3-rocm` |
| `openfold3/setup_openfold.py` | Setup flow: `ckpt_root` pointer, default-checkpoint download, CCD `components.bcif` placed into Biotite |
| `openfold3/entry_points/parameters.py` | Checkpoint registry: names, files, `version_compatibility`, `DEFAULT_CHECKPOINT_NAME`, `LEGACY_CHECKPOINTS`, S3 bucket `openfold3-data`, key prefix `openfold3-parameters/`, `$OPENFOLD_CACHE` / `~/.openfold3/` resolution |
| `openfold3/entry_points/validator.py` | Experiment settings defaults (`use_msa_server = True`, `use_templates = True`, seeds `[42]`). The **missing-checkpoint refusal** ("cowardly refusing to perform inference") |
| `openfold3/entry_points/experiment_runner.py` | Inference runner. Tri-state MSA/template overrides. Automatic `mps` preset |
| `openfold3/projects/of3_all_atom/config/inference_query_format.py` | Pydantic query schema (`Query`, chains, query-level MSA switches, extra fields forbidden) |
| `openfold3/projects/of3_all_atom/config/model_setting_presets.yml` | Presets: `train`, `predict`, `low_mem`, `mps` |
| `openfold3/projects/of3_all_atom/project_entry.py` | Preset validation (unknown preset → error) |
| `openfold3/core/runners/writer.py` | Output file names and confidence JSON keys (`*_model.cif`, `*_confidences.json`, `*_confidences_aggregated.json`) |
| `openfold3/core/data/tools/colabfold_msa_server.py` | MSA server client. Default host `https://api.colabfold.com`. Calls the RCSB chain mapping |
| `openfold3/core/data/tools/rscb.py`, `core/data/pipelines/preprocessing/template.py` | RCSB GraphQL chain-ID mapping (`data.rcsb.org/graphql`); template structure fetch from RCSB via Biotite |
| `examples/example_inference_inputs/*.json` | 9 public example queries (ubiquitin, homomer, multimer, cyclic multimer, DNA+PTM, protein–ligand variants, pocket constraint) |
| `examples/example_runner_yamls/` | 8 runner YAML **examples, not presets** (`low_mem`, `cuequivariance`, `triton`, `multiple_gpu`, `output_settings`, `save_msa_output`, `profiling`, `affinity.yaml`) |
| `docs/source/*.md`, `README.md` | In-repo docs at the tag. This rung is below the source; known doc/source conflicts are listed in `00_scope_and_trust.md` |
| `pixi.toml`, `docker/`, `environments/` | Install routes (pixi CPU/MPS, CUDA 12/13, ROCm 7 envs; Dockerfiles) |

### Rendered docs — ReadTheDocs `stable` (= v0.5.0 build, 2026-08-21)

The tagged URL `https://openfold-3.readthedocs.io/en/v0.5.0/` returns 404. `stable` maps to `c4771653`. `latest` tracks `main`.

| Page | URL |
|---|---|
| Index | https://openfold-3.readthedocs.io/en/stable/index.html |
| Setup / install | https://openfold-3.readthedocs.io/en/stable/Installation.html |
| Inference | https://openfold-3.readthedocs.io/en/stable/inference.html |
| Parameters (checkpoints) | https://openfold-3.readthedocs.io/en/stable/parameters_reference.html |
| Input format | https://openfold-3.readthedocs.io/en/stable/input_format_reference.html |
| Configuration | https://openfold-3.readthedocs.io/en/stable/configuration_reference.html |
| Kernels (cuEquivariance / DeepSpeed) | https://openfold-3.readthedocs.io/en/stable/kernels.html |
| Pixi environments | https://openfold-3.readthedocs.io/en/stable/modern-conda-environments-with-pixi.html |
| Precomputed MSA — how-to / generation / explanation | https://openfold-3.readthedocs.io/en/stable/precomputed_msa_how_to.html · https://openfold-3.readthedocs.io/en/stable/precomputed_msa_generation_how_to.html · https://openfold-3.readthedocs.io/en/stable/precomputed_msa_explanation.html |
| Templates — how-to / explanation | https://openfold-3.readthedocs.io/en/stable/template_how_to.html · https://openfold-3.readthedocs.io/en/stable/template_explanation.html |
| Debugging | https://openfold-3.readthedocs.io/en/stable/debugging_how_to.html |
| Training, data pipeline, dataset caches (out of scope) | https://openfold-3.readthedocs.io/en/stable/training.html · https://openfold-3.readthedocs.io/en/stable/data_pipeline_reference.html · https://openfold-3.readthedocs.io/en/stable/understanding_dataset_caches.html |
| Contribution | https://openfold-3.readthedocs.io/en/stable/contribution.html |

The rendered parameters table gives preview-2 compatibility as `>=0.4,<0.5`. The source registry says `>=0.4,<0.4.4dev0`.
Trust the source.

## Anthropic optimization kits

Repository: https://github.com/anthropics/uplifting-biomolecular-modeling @ `f4f62fa6592ae4938d49b1757bea0cfeff9f468e`
(2026-09-17, "Initial public release of the model-optimization kits", no tags). Apache-2.0 (`LICENSE`, `NOTICE`). Described as "not maintained and not
accepting contributions".

| Path (under `openfold3_ob0/` unless noted) | Authoritative for |
|---|---|
| `README.md` | Setup routes A (Docker) / B (Apptainer) / C (venv), run lines, what each mode does, exit-code table, "at a glance" claims |
| `STOCK.md` | Pins and stack (CUDA 12.8, driver ≥ 570, Python 3.11, torch 2.10.0+cu128, …). The **stock configuration** used by `off` (cuEquivariance + bf16-mixed, chunk 1024) versus upstream's shipped configuration |
| `CHANGES.md` | What each optimization ("lever") changes |
| `run.sh` | Commands `pred\|check\|warm\|install`. `install` rejects `--config`/`--mode`. Mode precedence. Exit codes 0/1/2/3/5 |
| `opt/openfold3_ob0_opt/cli.py` | Registered `pred`/`check`/`warm` options. This is the limited passthrough list, not arbitrary upstream flags |
| `opt/openfold3_ob0_opt/modes.py` | The mode table. `big` gate. Below the gate `big` returns the full `fast` composition |
| `opt/openfold3_ob0_opt/det.py` | `--det` accepts only `0\|1` |
| `opt/openfold3_ob0_opt/stock_pred.py`, `report.py` | `--mode off` clean-subprocess route. `Model forward time:` line grammar |
| `configs/{a100,h100,h200,b200,b300}.env` | Per-card deployment parameters (`--config`) |
| `stock/PINS.json`, `stock/check_pins.py`, `stock/install_upstream.py` | Wheel, source, weights and CCD digests. Pin enforcement (exit 3) |
| `environment/{Dockerfile,apptainer.def,requirements.lock}` | Container recipes and the full pinned package set |
| `upstream_issues/OB0-001*.md`, `OB0-002*.md` | Templates silently dropped on fetch failure (kit exit 5). Chunk-tuner issue |
| `opt/forward/fast_inference/tests/public_inputs.py` | Public 1BRS barnase–barstar tilings used by `warm` (199–1 194 tokens) |
| `../common/opt_core/` | Shared kernel core. Its README states the libstdc++/glibc floor |
| `../openfold3/` (legacy kit) | Same layout. Upstream 0.4.1 + preview-2. Env `OPENFOLD3_CKPT` / `OPENFOLD3_OPT` |

| Anthropic publication | Identity | Authoritative for |
|---|---|---|
| Blog "How Claude is uplifting biomolecular modeling" | https://www.anthropic.com/research/claude-uplifts-biomolecular-modeling (2026-09-17) | Cross-model headline claims only. It gives no OpenFold3-specific numbers |
| Report "Accelerating open-source biomolecular models with Claude" (Claude Science, Shuai R. et al.; 17 Sep 2026, updated 21 Sep 2026; 140 pp.; no DOI verified) | https://www-cdn.anthropic.com/e96b5807039a88168733d9687afe41dfbbd5de13.pdf | OpenFold3-p2 §S1.3 (pp. 27–30) and OpenBind-0 §S1.4 (pp. 31–34): setup, speed-ups, memory, reach, FoldBench-Lite accuracy, identity checks. Pooled results pp. 5–7 |

## Weights, data and images

| Item | Location | Authoritative for |
|---|---|---|
| OpenBind-0 checkpoint | `s3://openfold3-data/openfold3-parameters/of3-ob-2025-06-30-174k.pt` (public, unsigned; https://openfold3-data.s3.amazonaws.com/openfold3-parameters/of3-ob-2025-06-30-174k.pt). 2 287 872 989 bytes, sha256 `bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4` | Default v0.5.0 weights. Digest from kit `PINS.json` |
| Parameter listing | https://openfold3-data.s3.amazonaws.com/?list-type=2&prefix=openfold3-parameters%2F | Which objects exist. Unregistered objects (water/fine-tune checkpoints) are **not** supported defaults |
| CCD | https://openfold3-data.s3.amazonaws.com/components.bcif. 63 393 643 bytes, sha256 `473d845c8b250b188dbed9bf505ae206692a178a2a7c4869bf8f9de707ffcc0c` | Full chemical component dictionary installed into Biotite by `setup_openfold` or kit `install` |
| Preview weights (p1, p2) | https://huggingface.co/OpenFold/OpenFold3 (contact-information gate; card labelled Apache-2.0). `of3-p2-155k.pt` and `of3-p2-145k.pt` are also in the public S3 listing | Legacy checkpoints only. Not loadable on `>=0.5` |
| Training data | https://registry.opendata.aws/openfold3/ (CC BY 4.0) | Out of scope (training) |
| Docker image | `openfoldconsortium/openfold3:stable` (stated in the Installation page; not pulled here) | Upstream container route |
| Portal / consortium | https://portal.openfold.omsf.io/ · https://openfold.io/ | Reports, datasets, news |

## Papers and announcements (methods and claims only, never CLI syntax)

| Work | Identity | Use for |
|---|---|---|
| Abramson J. et al., "Accurate structure prediction of biomolecular interactions with AlphaFold 3", *Nature* 630, 493–500 (2024) | DOI 10.1038/s41586-024-07487-w | Architecture, metrics and limitations that OpenFold3 inherits |
| The OpenFold3 Team, "OpenFold3-preview technical white paper" (2025 release; exact date unverified; no DOI) | Repo `assets/of3p1_technical_report.pdf` | Preview-1 (`openfold3-p1`) results and errata |
| The OpenFold3 Team, "OpenFold3-preview2 Technical Report" (2026; exact date unverified; no DOI) | https://portal.openfold.omsf.io/reports/of3p2_technical_report.pdf (also `assets/of3p2_technical_report.pdf`) | Preview-2 training, benchmarks and errata |
| OpenBind Consortium, "OpenBind-0: Advancing Open Molecular Structure Prediction" (2026-08-21) | https://openbind.uk/news/blog-openbind-0-advancing-open-molecular-structure-prediction/ | OB0 training cutoff, benchmark claims, weights licence statement, steering description |
| OpenBind Consortium, "OpenBind-0 model release benchmarking materials" (Zenodo, 2026-08-21; CC BY 4.0) | DOI 10.5281/zenodo.22037460 (https://zenodo.org/records/22037460) | 462-system protein–ligand benchmark with queries and MSAs (9.3 GB). The record itself says to prefer the official updated PLINDER once it is released |
| Mirdita M. et al., "ColabFold: making protein folding accessible to all", *Nature Methods* (2022) | DOI 10.1038/s41592-022-01488-1 | The MMseqs2 MSA server behind `--use-msa-server` |

## How to cite (when publishing results)

| When | Cite |
|---|---|
| Always | OpenFold3 software as the upstream README "Citing this Work" asks (BibTeX `openfold3-preview`, DOI `10.5281/zenodo.19001000`, which resolves to a 0.4.x record), plus the v0.5.0 record `10.5281/zenodo.22042719` or the concept DOI `10.5281/zenodo.17485509`; and AlphaFold3 (Abramson et al. 2024, DOI 10.1038/s41586-024-07487-w), which the README also asks for |
| Default weights | The OpenBind-0 announcement (OpenBind Consortium, 2026-08-21, URL above), with the checkpoint name and sha256 |
| `--use-msa-server` used | ColabFold (Mirdita et al. 2022, DOI 10.1038/s41592-022-01488-1) |
| A kit mode used | `github.com/anthropics/uplifting-biomolecular-modeling@f4f62fa` and the report "Accelerating open-source biomolecular models with Claude" (2026); state the mode and `--det`. The kit ships no citation file [inferred wording] |
| OpenBind benchmark used | DOI 10.5281/zenodo.22037460 (CC BY 4.0: attribution required) |

## Community

GitHub issues: https://github.com/aqlaboratory/openfold-3/issues. Retrieved 2026-09-22: **112 issues** (plus 309 pull
requests) created from 2025-10-28 to 2026-09-18. GitHub Discussions is disabled. Recurring themes, cited by number where
used:
- kernels and install: #21, #218, #283, #352;
- OOM and `low_mem`: #25, #71, #225, #239;
- MSA server and pairing: #61, #237, #371, #372;
- weights discovery: #378.

Treat these as leads (see the trust ladder in `00_scope_and_trust.md`). The kit repository does not accept contributions,
and its issues may not be answered.
