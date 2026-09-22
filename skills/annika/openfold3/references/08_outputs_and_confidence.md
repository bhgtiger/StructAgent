# 08 — Outputs and Confidence

Grounded in `openfold-3@v0.5.0` (`c4771653`): `openfold3/core/runners/writer.py`, `core/utils/callbacks.py`,
`core/metrics/{aggregate_confidence_ranking,sample_ranking,confidence,rasa}.py`, `entry_points/{validator,experiment_runner}.py`.
The 0.4.1 writer (legacy kit) writes the same paths and keys, but does not round floats, has no
`full_confidence_output_dtype`, and casts per-atom chain ids to bool before the clash check, so its `has_clash` stays 0
**[source]**. Kit behaviour is from
`uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/opt/openfold3_ob0_opt/{cli,manifest,tp}.py`. **[live]** means
checked on real stock and kit `exact`/`fast` trees from a validated Slurm site (A100-SXM4 40 GB + H100 94 GB, 2026-09-22).
The upstream docs are wrong in several places; each is marked "docs say".

## Output tree [live]

```
<output-dir>/
├── experiment_config.json        # resolved runner config (Pydantic dump)
├── model_config.json             # resolved model config; architecture.shared.diffusion.no_full_rollout_samples = samples/seed
├── inference_query_set.json      # queries as parsed, MSA paths filled in
├── summary.txt                   # PREDICTION SUMMARY (COMPLETE): processed / successful / failed (+ failed names)
├── msas/msa-<user>-<UTC stamp>-<8 hex>/   # saved MSA record; dummy/<sha256>.npz = single-sequence placeholder
├── logs/predict_err_rank<r>.log  # only when a query failed (traceback); an empty logs/ is removed [source, live]
└── <query>/                      # one directory per key of "queries"
    └── seed_<s>/                 # one per model seed
        ├── <query>_seed_<s>_sample_<k>_model.cif
        ├── <query>_seed_<s>_sample_<k>_confidences.json
        ├── <query>_seed_<s>_sample_<k>_confidences_aggregated.json
        └── timing.json
```

- `k` runs from 1 to the sample count (default 5). Nothing is ranked or renamed on disk: there is no `ranked_0` or "best"
  file. `sample_1` is not the best sample. Rank the samples yourself (below).
- Seed directories come from the runner YAML's `experiment_settings.seeds` (default `[42]`) or from `--num-model-seeds N`,
  which draws N seeds after `random.seed(42)` (`validator.py:generate_seeds`), e.g. `seed_2746317213/` [live]. Find seed
  directories with a `seed_*` glob.
- The `seeds` recorded in `experiment_config.json` (runner list before the CLI override) and `inference_query_set.json`
  (the query file's unused field) stay `[42]` under `--num-model-seeds`; the override sets only the runner's own list
  (`experiment_runner.py:update_config_with_cli_args`) **[source]**. Trust the directories, not the dumps.
- Written only on request: `<query>_seed_<s>_batch.pt` (`write_features`) and `<query>_seed_<s>_latent_output.pt`
  (`write_latent_outputs`: `si_trunk`, `zij_trunk`, `atom_positions_predicted`) **[source]**.
- A distributed run whose final sync times out writes `fallback_summary_rank_<r>.txt` instead of `summary.txt` **[source]**
  (upstream's own comment says this path is rarely reached).
- `align-msa-server` writes a different tree (`query_msa.json` + alignments). See
  [07_msa_templates_weights.md](07_msa_templates_weights.md).

## What each file holds

| File | Content | Notes |
|---|---|---|
| `*_model.cif` | Structure. Categories: `_chem_comp_bond`, `_atom_site`, `_chem_comp`, `_entity`, `_struct_asym`. Data block `data_structure` | **Per-atom pLDDT (0–100) in `_atom_site.B_iso_or_equiv`** [live]. Docs say this happens only "if .pdb"; the writer sets it for every format. There is no ModelCIF QA table |
| `*_confidences_aggregated.json` | Scalar and per-chain scores (next table) | Always written, even when full confidences are off |
| `*_confidences.json` | `plddt`, `pae`, `pde` arrays (table after next) | 268 KB per sample at 76 tokens; **45 MB per sample at 995 tokens** [live]. Grows as tokens² |
| `timing.json` | `{"runtime_s": …}` for this (query, seed) predict batch | Timer runs from batch start until after the writer callback (forward, confidence heads, file writing; the kit's `writer_overlap` moves the writing to a worker). Excludes process start, checkpoint load (≈45 s per call per the kit README), featurisation and MSA: not the wall time of the call [source] |
| `summary.txt` | Counts of (query, seed) items: "Total Queries Processed" = queries × seeds | **A failed query does not fail the call.** `predict_step` catches the OOM or exception, writes a traceback to `logs/predict_err_rank<r>.log`, counts the item under "Failed Queries" and carries on (`of3_all_atom/runner.py`) [source]. Always read this file |
| `experiment_config.json` | Output settings, `use_msa_server`, `use_templates`, checkpoint path/name | Contains absolute paths |
| `inference_query_set.json` | Parsed queries, including sequences and resolved `main_msa_file_paths` | A path containing `/dummy/` means that chain ran single-sequence |

## `*_confidences_aggregated.json` — every key [source + live]

| Key | Meaning | Scale | Per |
|---|---|---|---|
| `avg_plddt` | Mean of the per-atom pLDDT array (`np.mean(plddt)`) | **0–100** | complex, over atoms |
| `gpde` | Global PDE: PDE weighted by contact probability (distogram bins ≤ 8 Å; AF3 SI §5.7 eq. 16) | Å, lower is better | complex |
| `ptm` | Predicted TM-score of the whole complex (AF3 SI §5.9.1) | 0–1 | complex |
| `iptm` | Interface pTM over inter-chain token pairs. **0.0 for a single-chain query by construction** | 0–1 | complex |
| `disorder` | **Fraction** of protein residues whose windowed (25-residue) relative SASA exceeds 0.581 (`rasa.py: np.mean(rasa > 0.581)`). Docs say "average RASA", which is wrong | 0–1 (0.0 with no protein; NaN if RASA fails) | complex |
| `has_clash` | 1.0 if any pair of **polymer** chains clashes, else 0.0. A clash means >100 atom pairs under 1.1 Å, or clashing pairs > 50% of the smaller chain's atoms. Ligands are excluded | 0/1 | complex |
| `sample_ranking_score` | `0.8·iptm + 0.2·ptm + 0.5·disorder − 100·has_clash` | **not 0–1**: −100 … 1.5 by construction. Measured 0.10–1.16 over 582 single-sequence samples; a clash makes it about −100 | sample |
| `chain_ptm` | pTM restricted to each chain | 0–1 | `{"A": …}` keyed by output chain ID |
| `chain_pair_iptm` | ipTM of each chain pair (AF3 SI §5.9.3 item 3) | 0–1 | `{"(A, B)": …}` upper triangle only; key string has comma **and space**; `{}` for one chain |
| `bespoke_iptm` | Pair score for ranking interfaces. A pair with a ligand chain uses that ligand's mean ipTM against all other chains; otherwise the mean of the two chains' mean ipTMs | 0–1 | same keys as `chain_pair_iptm` |

Chain keys are the output chain IDs from your query's `chain_ids`, for example `A1…A5`, `B1…B5`, or `Z` for a ligand [live],
listed in sorted string order. They are not integer indices. v0.5.0 rounds float32 values to 6 decimals.

## Full confidences `*_confidences.json` / `.npz`

| Array | Shape [live] | Scale |
|---|---|---|
| `plddt` | `[N_atoms]` in model-file atom order (ubiquitin: 601) | 0–100 (50 bins over 0–1, ×100) |
| `pae` | `[N_tokens, N_tokens]` (ubiquitin: 76 × 76) | Å, 64 bins over 0–32 Å |
| `pde` | `[N_tokens, N_tokens]` | Å, 64 bins over 0–32 Å |

Docs call all three arrays "per-atom". Only pLDDT is per atom: PAE and PDE are per token. A token is one residue or
nucleotide, or one heavy atom of a ligand or modified residue. The NPZ variant has the same keys, stored as **float16 by
default** (`full_confidence_output_dtype`). NPZ output was not exercised live **[unverified]**.

## Ranking and picking the top model

- Upstream computes one full-complex ranking score per sample (`sample_ranking.py:full_complex_sample_ranking_metric`,
  weights in `projects/of3_all_atom/config/model_config.py` → `confidence.sample_ranking.full_complex`, also dumped to
  `model_config.json`) but never picks a winner. Take the sample with the highest `sample_ranking_score` **across all seeds
  of that query**. The formula has no chirality term; AF3's PoseBusters ranking added one [paper].
- **Single chain:** `iptm` = 0, so the score is `0.2·ptm + 0.5·disorder`. For example, ubiquitin gives 0.166 = 0.2 × 0.832
  [live]. `disorder` can dominate the score: a 68-residue leucine-zipper homodimer scored 1.12 with `disorder` = 0.5
  (A100, `off`, single-sequence) [measured].
- **Protein–ligand:** also look at the protein–ligand entries of `chain_pair_iptm` / `bespoke_iptm`. The OpenBind
  announcement's benchmark ranked poses by protein–ligand ipTM [docs].
- One-liner, stdlib; tested on a real stock tree, where it printed `…sample_2_model.cif` [live]:
  `python3 -c "import json,glob,sys;f=max(glob.glob(sys.argv[1]+'/seed_*/*_confidences_aggregated.json'),key=lambda p:json.load(open(p))['sample_ranking_score']);print(f.replace('_confidences_aggregated.json','_model.cif'))" <output-dir>/<query>`
  (it assumes `cif`). Prefer the summarizer below: it also checks completeness.

## Runner options that change outputs (`--runner-yaml`; `OutputWritingSettings`, `validator.py`)

```yaml
# template — not run
output_writer_settings:
  structure_format: cif              # cif (default) | pdb | cif.gz  -> *_model.<fmt>
  full_confidence_output_format: json  # json (default) | npz  -> *_confidences.<fmt>
  full_confidence_output_dtype: float16  # float16 (default) | float32; npz only; absent in 0.4.1
  write_full_confidence_scores: true # false = aggregated JSON only (use for big or many-seed runs)
  write_features: false              # true -> <query>_seed_<s>_batch.pt
  write_latent_outputs: false        # true -> <query>_seed_<s>_latent_output.pt
experiment_settings:
  skip_existing: false               # true = skip queries whose every seed x sample model file exists
```

- The sample and seed counts come from CLI flags (seeds also from `experiment_settings.seeds`). See
  [03_cli_reference.md](03_cli_reference.md).
- `skip_existing` checks model files only, not confidences. Skipped queries are missing from that run's
  `inference_query_set.json`.
- **Kit caveat [source, not run]:** the kit counts structures with the glob `**/seed_*/*_model.cif`
  (`manifest.count_structures`). Under `run.sh pred`, `structure_format: pdb` or `cif.gz` (upstream's
  `examples/example_runner_yamls/output_settings.yml` sets `pdb`) therefore reports `incomplete` with rc 1 even though the
  files exist. Keep `cif` under the kit.

## Kit trees and the completeness rule

- **Single-GPU `run.sh pred` (any mode):** writes the same file set as stock. "No kit file is written beside the outputs"
  (`cli.py`); confirmed on the `exact` tree [live]. The kit's JSON encoder and writer levers render the same bytes
  **[source]**.
- **`--n_gpu P` (big, row-sharded) [source]:** adds `<out>/_tp/rank<r>.log` for every rank and `<out>/tp_predict.yml` (the
  pinned runner YAML). It may leave an emptied `<out>/_tp/rank<r>/` for ranks > 0. It also writes a
  `<prefix>_structure_first.json` sidecar beside each model (`OF3TP_STRUCTURE_FIRST=1` default). The structure file is written
  **before** the confidence heads, with the B-factor column set to 0.00, and the sidecar flips to
  `confidence_written: true` only after pLDDT is filled in. A structure-only file (`false`, B-factors 0.00) is not a
  finished prediction.
- **Exit rule** (`cli.py:exit_rule`, `expected_structures`): `expected = queries × seeds × samples`. The seed count is
  `--num-model-seeds`, else the list length of the runner YAML's `experiment_settings.seeds`, else 1. The sample count is
  `--num-diffusion-samples`, else 5.
  - A `*_model.cif` counts unless a structure-first sidecar marks it `confidence_written: false`
    (`OUTPUT NOT COUNTED … confidence_not_written`) or a coordinate is nan/inf (`OUTPUT REJECTED … nan_coordinates`).
    Without sidecars (single GPU), a model file whose confidence JSON is missing still counts. The summarizer checks
    for that case.
  - Fewer counted structures than expected → `incomplete: n/expected`, **rc 1**.
  - stderr carries one verdict line, `[openfold3_ob0-opt] pred --mode <m>: exit rule -> <rc> (ok; structures 5/5; …)`
    [live]; grep for `exit rule ->` (LEVER census lines follow it, so it is not the last line). Other exit codes:
    [03_cli_reference.md](03_cli_reference.md).
  - The env route (`OPENFOLD3_OB0_OPT=<mode> run_openfold predict`) has no exit rule: upstream's rc only, no
    `incomplete`. Check such trees with the summarizer.
- The count covers the **whole** output directory, so stale files from an earlier run can mask a short new run. Use a
  fresh `--output-dir` per run and mode.
- `big` on a query set that straddles its token gate runs one pass per side into the same directory. `summary.txt` and
  `inference_query_set.json` are restored to whole-call content, but `experiment_config.json` / `model_config.json` are the
  last pass's (`cli.py:run_item_groups`). See [06_kit_modes_and_multigpu.md](06_kit_modes_and_multigpu.md).

## Check a run: `scripts/summarize_openfold3_output.py` (stdlib, Python ≥ 3.9, read-only)

```bash
python3 scripts/summarize_openfold3_output.py <output-dir> --expect-seeds 1 --expect-samples 5   # ranked table per query
python3 scripts/summarize_openfold3_output.py <output-dir> --chains --top 3     # + chain_ptm / chain_pair_iptm of the top sample
python3 scripts/summarize_openfold3_output.py <output-dir> --query-json q.json --check-coords --json > summary.json
```

The script works on a run directory, a single query directory (only that query is expected), or a parent holding several
runs; each run is ranked separately. Without flags, it takes the expected samples per seed from `model_config.json` and the
expected queries from `inference_query_set.json`. It never infers seeds: without `--expect-seeds` the grand total is not
checked and the verdict says `NO PROBLEMS FOUND (grand total not checked …)` instead of `COMPLETE`. It flags the following:
- models without aggregated confidences, including B-factor-0.00 structure-only files;
- confidences without a model;
- kit sidecars with `confidence_written: false`;
- extra files and renamed query directories;
- a mismatch with the recomputed ranking formula (weights from `model_config.json` when present);
- `--check-coords`: model files with nan/inf coordinates (the kit's counting rule);
- failures in `summary.txt`, `logs/predict_err_rank*.log`, and fallback summaries;
- single-sequence (`dummy`) chains;
- kit `_tp/` and `tp_predict.yml` files.

Exit codes: **0** no problems, **1** incomplete or problems, **2** usage error. Tested with Python 3.9 on stock and
`exact` ubiquitin trees (5/5, rc 0; top = sample 2, ranking 0.1669 / 0.1667), on an A100 `fast` 995-token 1BRS tree (5/5,
top = sample 3, 0.1407), on a `--num-model-seeds 1` warm-up tree (`seed_2746317213`), and on synthetic broken copies
(missing model/confidence, sidecar `false`, nan coordinate, failed `summary.txt`, renamed query dir: rc 1) [live].

## Interpretation guardrails

- **pLDDT** measures local confidence, per atom, on a 0–100 scale. The AF3 figure bands are >90, 70–90, 50–70 and <50
  [paper]. These are AlphaFold conventions, not an OpenFold3 calibration. Low pLDDT in a flexible region can be correct
  disorder, and a hallucinated compact region can still look ordered.
- **PAE/PDE** are in Å; lower is better. Read inter-chain PAE blocks for relative placement. A high `avg_plddt` does not
  validate an interface.
- **pTM / ipTM / `chain_pair_iptm`** judge global fold and interfaces. For a complex, use ipTM and the relevant pair
  entries. For a monomer, ignore `iptm` (it is 0).
- **`has_clash` = 1** puts the sample at the bottom (−100). Do not use a clashing sample. If every sample clashes, report
  that the prediction failed this check.
- **Single-sequence runs** (`--use-msa-server false`, no MSAs; `dummy` MSAs) usually give low confidence, for example
  `avg_plddt` ≈ 35 on the 995-token 1BRS assembly (A100 and H100, all modes) [measured]. They show the software works, not
  that the prediction is good. Never compare their scores with MSA runs.
- **Rank within one run only.** Do not rank across modes, cards, checkpoints, MSA settings or queries. `fast`/`big` use
  bf16 in the confidence phase (kit README), so their scores and top picks move: on the A100 leucine zipper, the top
  score went from 1.1219 (`off`) to 1.1507 (`fast`) [measured]. Near-identical scores can hide different structures:
  top-model CA RMSD between `fast` and `off` reached 29.9 Å on the H100 995-token 1BRS input while the top scores differed
  by 0.003 [measured]. Only `exact --det 1` vs `off --det 1` is byte-identical (see
  [09_validation_and_benchmarks.md](09_validation_and_benchmarks.md)).
- **The ranking score is a sorting key, not a probability.** Measured values run up to 1.16 because of `disorder`.
  Top-ranked accuracy can keep improving with more seeds (AF3: antibody–antigen interfaces) [paper], so inspect several
  samples and seeds.
- **No experimental claims.** Confidence is the model's own estimate, not measured accuracy, a binding affinity, or proof
  of an interaction. Check ligand geometry and chirality separately, for example with PoseBusters-style checks [paper].

## Before sharing outputs

The output files can reveal private information:
- `msas/msa-<local username>-…` names the local user.
- `experiment_config.json` and `inference_query_set.json` hold absolute paths.
- `inference_query_set.json` also holds every sequence and SMILES, and `msas/` holds the alignments.

For unpublished targets, share only the model files and aggregated JSON, or scrub these files first. Troubleshooting for
missing or incomplete outputs is in [10_troubleshooting.md](10_troubleshooting.md).
