# 05 — Core Workflows

Each workflow gives when to use it, the command template and the checks. Flags come only from
[03_cli_reference.md](03_cli_reference.md), query fields only from [04_input_query_format.md](04_input_query_format.md), modes
from [06_kit_modes_and_multigpu.md](06_kit_modes_and_multigpu.md), outputs from [08_outputs_and_confidence.md](08_outputs_and_confidence.md).
Pins: `openfold-3@v0.5.0` (`c4771653`) and kit `uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/`. Every command
block is a template until the host is VALIDATED and the user confirms that exact run.

```bash
# template — not run. Placeholders come from configs/site_config.local.md:
#   <OF3>   stock CLI: run_openfold on PATH, or a wrapper that execs it in the image
#   <KIT>   kit CLI: "bash <kit_dir>/openfold3_ob0/run.sh", "apptainer run --nv <image>.sif", or a site wrapper
#   <CARD>  kit --config card: a100 | h100 | h200 | b200 | b300
#   <Q>     ABSOLUTE path to a query JSON        <OUT>  ABSOLUTE path to a NEW output directory
```

## Pre-run checklist (every workflow that predicts)

| Check | Pass condition | Why |
|---|---|---|
| State | VALIDATED from a probe taken this session on this host. At PROBED the only prediction allowed, with consent, is the public GPU fixture (ubiquitin, `--use-msa-server false`, workflow 1) | [00_scope_and_trust.md](00_scope_and_trust.md) state machine |
| Consent | User approved this run: inputs, GPU cost, MSA route | Uses a GPU allocation |
| Privacy | `--use-msa-server false` on the line, unless the user approved the public server **for these sequences** | Unset means **true**: every protein sequence in the JSON goes to `api.colabfold.com`, even in queries with `use_msas: false` **[source]** ([07](07_msa_templates_weights.md) §2) |
| Privacy (outputs) | `<OUT>/inference_query_set.json` holds the sequences; `<OUT>/msas/msa-<login>-<UTC time>-<hex>/` holds the login name **[live]** | Scrub before sharing ([08](08_outputs_and_confidence.md) "Before sharing outputs") |
| Cost | Calls × ≈45 s start-up (kit README, every mode) **[docs]**, plus queries × seeds × samples of compute; first `fast` call adds JIT ([09](09_validation_and_benchmarks.md)) | Batch into one call (workflow 6) |
| Memory | Largest query's tokens ([04](04_input_query_format.md) §Token count) vs the card ([11](11_decision_trees.md) §5). Upstream asks for ≥ 32 GB **[docs]** | Too big: `fast` below 1 401 polymer tokens, `big` at or above it, or the `low_mem` preset (workflow 9) |
| Weights | Checkpoint sha256 `bd43301c…8e29e4`; full CCD installed ([07](07_msa_templates_weights.md) §8–9) | An unknown checkpoint only warns. A missing CCD falls back silently to Biotite's subset |
| Output | `<OUT>` does not exist yet, is absolute and writable, not in an inode-limited home. Caches node-local | Old files would pass the completeness count (workflow 12) |
| Script | No `set -e`. Capture `rc=$?` | Kit rc 3 and 5 are results, not crashes |

## 1. First-contact configuration session (probe → site config → readiness verdict)

**When:** a new host, a new session, or a stale site config (`configs/site_config.template.md`). Run nothing else first.
Steps: read-only probe on the **target** host (the agent's machine is not the runtime) → live help on a CPU or login
node, compared with 03 → weights and dry-run gate on a **GPU** node → write `configs/site_config.local.md` (git-ignored),
`state: PROBED` → with consent, the GPU fixture (workflow 2, public ubiquitin) on each card type; pass → `VALIDATED`.

```bash
# template — not run
python3 scripts/openfold3_env_probe.py --json > probe.json   # read-only, stdlib. --deep runs the CLI/kit dry run and MAY create cache files: ask first
python3 scripts/openfold3_env_probe.py --kit-dir <kit_dir>/openfold3_ob0 --ckpt <CKPT>          # kit checkout (routes A/C); --kit-cli NAME = a wrapper on PATH
python3 scripts/openfold3_env_probe.py --deep --kit-dir <kit_dir>/openfold3_ob0 --card <CARD>   # ask first (see above)
<OF3> predict --help > predict_help.txt 2>&1; echo "rc=$?"    # CPU node: on a GPU node bare --help can print almost nothing (03 trap 5)
<KIT> > kit_usage.txt 2>&1; echo "rc=$?"                      # bare kit prints its usage; rc 2 is expected [live]
sha256sum <CKPT>                                              # bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4
<KIT> check --config <CARD> --mode exact; echo "rc=$?"        # GPU node: "DRY-RUN mode=exact …". gpu=none = no GPU proof. Re-hashes the 2.3 GB checkpoint
```

| Probe finds | Verdict | Next |
|---|---|---|
| No `run_openfold`, kit or image | not installed | Pick a route in [02](02_install_and_environment.md). Ask before any install |
| CLI present; checkpoint missing | not runnable (stock raises, rc 1; kit rc 2) | `setup_openfold --config` or `run.sh install --weights DIR` after consent (2.3 GB; 07 §8) |
| CLI present; checkpoint sha256 ≠ pin | runs, but unpinned (kit prints `WARNING: WEIGHTS unknown`) | Replace it; do not validate on unknown weights |
| CLI and checkpoint OK; full CCD not in Biotite | CCD ligand codes at risk | Install the CCD (07 §9) |
| All present; no GPU with cc ≥ 8.0 reachable | kit modes exit 3; stock on older cards untested **[unverified]** | Find a cc ≥ 8.0 GPU partition or node |
| All present; GPU cc ≥ 8.0; no fixture yet | PROBED, ready to validate (probe verdict `VALIDATED-CANDIDATE`) | Run the fixture after consent |
| Fixture rc 0 with 5 `*_model.cif` on every listed card | VALIDATED | Record the evidence in the site config |

## 2. Single protein

**When:** one chain, a quick structure. Query: `templates/queries/ubiquitin_monomer.json`.

```bash
# template — not run
<KIT> pred --config <CARD> --mode exact --query-json <Q> --output-dir <OUT> --use-msa-server false
<OF3> predict --query-json <Q> --output-dir <OUT> --use-msa-server false      # stock, no kit
```
**Checks:** rc 0; five `<OUT>/<key>/seed_42/<key>_seed_42_sample_{1..5}_model.cif` with their `_confidences*.json`;
`Failed Queries: 0` in `summary.txt` **[live]** (08). Report single-sequence runs as such (less accurate, not comparable).

## 3. Protein complex / homomer

**When:** several protein chains. Homomer: one chain entry with `"chain_ids": ["A","B"]` (`templates/queries/homodimer.json`).
Heteromer: one entry per distinct sequence (`templates/queries/barnase_barstar_1brs.json`).
- **Pairing.** Paired MSAs exist only for queries with ≥ 2 **distinct** protein sequences; monomers and homomers get main
  MSAs only **[source]**. Precomputed MSAs pair on species ids in `uniprot_hits` headers, or use your
  `paired_msa_file_paths` (07 §4). Without MSAs, interfaces are the least reliable part of the model: say so.

```bash
# template — not run
<KIT> pred --config <CARD> --mode exact --query-json <Q> --output-dir <OUT> --use-msa-server false --num-model-seeds 3
```
**Checks:** `iptm`, `chain_pair_iptm`, `has_clash` in `*_confidences_aggregated.json` (08). Expect 3 seed directories
with non-42 names (`--num-model-seeds` draws from `random.seed(42)`; 03 trap 14).

## 4. Protein–ligand (SMILES vs CCD)

**When:** small molecule, cofactor or ion with a protein. OpenBind-0 targets protein–ligand performance **[docs]**. It
gives **no affinity**, and v0.5.0 does not steer ligand chemistry.

- `ccd_codes` (exactly one code per entry) for PDB components (`ATP`, `HEM`, `MG`; needs the full CCD installed);
  `smiles` for novel compounds (write the intended protonation state). Never both in one entry; copies via `chain_ids`
  (04 §Ligands and ions). Examples: `templates/queries/protein_ligand_{ccd,smiles,pocket}.json`.
- Optional query-level `pocket_constraint` (one ligand chain per query) biases placement **[source]**; switch it off
  without editing the JSON via runner YAML `dataset_config_kwargs.pocket_sampling.enabled: false`.
- `covalent_bonds`, `sdf_file_path` and multiple CCD codes are **not** usable at v0.5.0 (04).

```bash
# template — not run
python3 scripts/make_query.py --validate <Q>         # prints a token estimate; see 04 for the spec format
<KIT> pred --config <CARD> --mode exact --query-json <Q> --output-dir <OUT> --use-msa-server false
```
**Checks:** the ligand chain is in the CIF with the expected atom count; `chain_pair_iptm` for the ligand chain and
`has_clash`; inspect the pose. A high score is a self-estimate, not proof of binding.

## 5. Nucleic acids (DNA / RNA)

**When:** protein–DNA, protein–RNA, or a nucleic acid alone (`templates/queries/protein_dna.json`).
- **DNA:** no MSA (the AF3 default) **[docs]**. **RNA:** never sent to the ColabFold server; MSAs only from precomputed
  files (07 §5), else single-sequence with `--use-msa-server false` (server mode leaves it with no MSA features, 07 §2).
  No RNA templates and no protein–RNA pairing at v0.5.0 ("coming soon") **[docs]**.
- **Modified bases/residues:** `non_canonical_residues` `{position: CCD}`, 1-based; each modified residue adds tokens (04).

**Checks:** both duplex strands are present and base-paired where expected. Treat nucleic-acid confidence as weaker
evidence than protein confidence (09).

## 6. Batch many queries in one JSON

**When:** more than a few predictions. Every call pays the start-up and checkpoint load, and the first `fast` call in a
fresh JIT cache compiles kernels, so put all queries in **one JSON and one call**. The server also deduplicates identical
sequences and complexes across that JSON **[source]**.

- Seeds × samples: [11](11_decision_trees.md) §6 (default 1 × 5; hard interfaces want more **seeds**, not more samples
  **[paper]**). A fixed list goes in runner YAML `experiment_settings: {seeds: [1, 2, 3]}`; `--num-model-seeds`
  overrides it **[source]**.
- Structures = queries × seeds × samples. The biggest query sets the memory: group queries of similar size. Kit `big`
  runs a set that straddles its gate as two calls (06).
- Resume after a crash or preemption: `experiment_settings: {skip_existing: true}` and the **same** `<OUT>` (the only
  correct reuse of an output dir). A query is skipped only when every seed × sample structure exists **[source]**.
- Upstream data-parallel runs (`pl_trainer_args.devices`) exist **[docs]**, untested here; not the same as kit `--n_gpu`.

**Checks:** `*_model.cif` count = queries × seeds × samples, and `Failed Queries: 0`. Upstream **catches OOM and other
per-query errors, logs them to `<OUT>/logs/predict_err_rank<r>.log` and still exits 0** **[source]**. The kit turns a
short count into rc 1 (`incomplete`); rules in 08 "Kit trees and the completeness rule".

## 7. Precomputed MSA route (private sequences, offline GPU nodes, reuse)

**When:** sequences must not leave the host; GPU nodes have no internet; one target is screened against many ligands.

| Route | Leaves the host? | Use |
|---|---|---|
| `align-msa-server` once, then `predict --use-msa-server false` on its `query_msa.json` | Yes, once: sequences to the server (public unless `server_url` names yours), template hit ids to RCSB | Public sequences; offline GPU nodes; reuse |
| Local OF3 Snakemake pipeline or your own a3m/sto | No | Unpublished sequences; RNA MSAs |
| No MSA (single-sequence) | No | Last resort; say it is less accurate |

```bash
# template — not run. PRIVATE route: your own a3m/sto files (07 §4 layout), nothing leaves the host
python3 scripts/make_query.py --name <q> --protein @a.fasta --protein @b.fasta --msa-dir /abs/msas --out <Q>
<KIT> pred --config <CARD> --mode exact --query-json <Q> --output-dir <OUT> --use-msa-server false
```

```bash
# template — not run. PUBLIC or approved sequences only: align-msa-server SENDS sequences (not a private route).
# Step 1 on a node WITH internet; no GPU needed.
<OF3> align-msa-server --query-json <Q> --output-dir <MSA_DIR>        # writes <MSA_DIR>/query_msa.json
# Step 2 on the GPU node, offline:
<KIT> pred --config <CARD> --mode exact --query-json <MSA_DIR>/query_msa.json --output-dir <OUT> --use-msa-server false
```
- **Precomputed MSAs need `--use-msa-server false`:** server mode overwrites user protein MSA paths. Field layout:
  `templates/queries/precomputed_msa.json`; file rules: 07 §4.
- Reuse: point every copy of the same sequence, across queries and runs, at the **same** directory or `.npz`.
- `query_msa.json` also points templates at server hits whose structures are fetched from RCSB at predict time. Offline:
  give local structures (workflow 8), or remove the template keys (then `--use-templates false` is safe).

**Checks:** no `Submitting … to the Colabfold MSA server` line in the log; `<OUT>/inference_query_set.json` lists your MSA
paths; `<OUT>/msas/<run-id>/dummy/` exists only for chains you left without an MSA **[live]**.

## 8. Templates

**When:** a homologous structure exists and you want it used. Sources: server hits (default when server and templates
are both on), a precomputed alignment (`template_alignment_file_path`) plus structures, or CIF-direct
(`template_cif_paths`). Details and caveats: 07 §7.

```yaml
# template — not run. runner YAML for an offline GPU node (kit note upstream_issues/OB0-001):
template_preprocessor_settings:
  structure_directory: <ABS_DIR_WITH_HIT_MMCIF_FILES>
  structure_file_format: cif
  fetch_missing_structures: false
```
- Kit **rc 5 `TEMPLATES DROPPED`**: a declared template never reached the model. Fix the cause (usually the structure
  fetch). `--allow-template-drop` only as a recorded, deliberate acceptance.
- Stock drops templates silently with rc 0. For an untemplated run **remove the template keys**: `--use-templates false`
  on a query that still has them fails (`UnpicklingError`) **[docs]**.

**Checks:** kit stderr has `TEMPLATES DECLARED … chains_templated=<n>` and no `TEMPLATES DROPPED`. Stock: an exception
trace followed by `Preprocessing templates: 0/1` and no `Loading template structure` line means they were lost (OB0-001).

## 9. Runner YAML overrides

Merge order: `$OPENFOLD_CACHE/runner.yml` (if present; default `~/.openfold3/runner.yml`), then `--runner-yaml`, then CLI
flags, which win **[source]**. The kit lays your YAML over the mode's configuration; the mode's execution keys win (06 §10).

| Need | YAML (key names verified at v0.5.0) |
|---|---|
| Lower GPU memory, slower | `model_update: {presets: [predict, low_mem]}`. The list **replaces** the default, so keep `predict` first. Presets at v0.5.0: `train`, `predict`, `low_mem`, `mps` (cuEquivariance / Triton are example YAMLs, not presets) |
| More recycles (default 3; the Anthropic report used 10) | `model_update: {custom: {architecture: {shared: {num_recycles: 10}}}}` (applied after the presets) |
| Output format, less disk, embeddings | `output_writer_settings: {structure_format: pdb, write_full_confidence_scores: false, …}` (08 "Runner options") |
| Explicit seeds; resume | `experiment_settings: {seeds: [..], skip_existing: true}` |
| MSA server settings | `msa_computation_settings: {server_url: .., msa_file_format: a3m}` (07 §6) |
| Custom MSA file names | `dataset_config_kwargs: {msa: {aln_order: [..], max_seq_counts: {..}, msas_to_pair: [..]}}` (07 §4) |

- Unknown keys are **rejected** at the top level (so is the docs' misspelling `datset_config_kwargs`) and inside
  `model_update`, `data_module_args`, `msa_computation_settings`, `template_preprocessor_settings`, `pocket_sampling`.
- Unknown keys are **silently ignored** inside `experiment_settings`, `output_writer_settings` and `dataset_config_kwargs`
  (including `.msa` / `.template`) **[source]**. Confirm the value in `<OUT>/experiment_config.json` after the run.
- `--mode off` runs the kit's stock configuration (cuEquivariance triangle kernels, `bf16-mixed`, no chunk tuner), not
  bare `run_openfold predict` (Triton kernels, `32-true`, tuner on) (kit `STOCK.md`) **[docs]**. Compare like with like.

## 10. Kit run (choose mode → check → warm → pred → read the lines)

Mode: [11](11_decision_trees.md) §3 (skill default `exact`, always passed explicitly: without `--mode` the kit runs
`fast`; `exact --det 1` for byte identity with `off --det 1`; `fast` for throughput; `big` for any query at or above
1 401 polymer tokens, where its gate engages). Order: `unset OPENFOLD3_OB0_OPT` (a value that disagrees with `--mode`
exits 2; any mode other than `off` arms plain `run_openfold`, an unsupported value is refused with rc 3) → `check` on the
GPU node → optional `warm` → `pred` → rc.

```bash
# template — not run
<KIT> check --config <CARD> --mode fast
<KIT> warm  --config <CARD> --mode fast --out <WARM_OUT>      # public barnase-barstar input; not with --mode off (rc 2)
<KIT> pred  --config <CARD> --mode fast --query-json <Q> --output-dir <OUT> --use-msa-server false
rc=$?
```
Read the `WEIGHTS`, `TEMPLATES`, `ACTIVE` (or `stock subprocess:` under `off`) and `LEVER` lines (06 §7). Grep for the
verdict line (census lines follow it), e.g. `pred --mode exact: exit rule -> 0 (ok; structures 5/5; templates_dropped=0;
partial=False; …)` **[live]**. rc: 0 ok · 1 failed or `incomplete` · 2 usage · 3 `NOT ACTIVE: <reason>` (report it; never retry silently as
stock) · 5 templates dropped (workflow 8). Full table: 03 §8.

## 11. Slurm / HPC submission with job-local caches

**When:** any cluster run. Copy `templates/slurm_predict.sbatch.template`, fill every `<PLACEHOLDER>`, then
`bash -n <copy> && sbatch <copy>` (template — not run). It encodes:
- `--export=NONE`, absolute paths, no `set -e` / `set -u`; `--use-msa-server false` (precompute MSAs: workflow 7).
- Refusals (exit 2) before GPU work: unfilled placeholder, relative path, existing output dir, bad `MODE`/`DET`/`N_GPU`.
- A node-local `WORK` dir, removed on exit, for `TMPDIR`, `MODEL_OPT_JIT_ROOT`, `XDG_CACHE_HOME` and the other caches
  (668–1 013 JIT files per job **[measured]**, 06 §12).
- A kit `check` gate; the rc echoed with its meaning; the `*_model.<ext>` count checked against queries × seeds ×
  samples (short count with rc 0 → exit 1); a ledger (workflow 12).
- Under `apptainer --cleanenv`, variables reach the container only as `APPTAINERENV_<name>` (`APPTAINER_FORWARD=1`) or
  through a wrapper that forwards by prefix (02 Route 3).

**Checks:** Slurm state COMPLETED; the job's `== rc=0` line and a complete count. On a new setup also confirm no new
files under `~/.triton` or `~/.cache` (`HOME_CACHE_AUDIT=1`).

## 12. Run ledger (record every real run)

One record per run, next to the output (the template writes `<OUT_PARENT>/of3_<jobid>.ledger.txt`) or in the project
log. Never overwrite a previous `<OUT>`; `skip_existing` resume (workflow 6) is the only exception.

| Field | Source |
|---|---|
| Exact command; mode, `--det`, `--config`, `--n_gpu` | The script; the `ACTIVE` line |
| openfold3 version, kit commit, image sha256 or env | Site config; `python -m openfold3_ob0_opt --version` |
| Checkpoint path and sha256 | The kit `WEIGHTS` line, or `sha256sum` |
| Seeds, samples, recycles, presets | `<OUT>/experiment_config.json`, `<OUT>/model_config.json` |
| MSA route and the user's approval; templates declared and used | The command, `inference_query_set.json`, `<OUT>/msas/`; the `TEMPLATES` lines |
| GPU model, driver | `nvidia-smi --query-gpu=name,driver_version --format=csv,noheader` |
| rc, exit-rule line, structure count vs expected, wall time | The job log; `timing.json` per seed |

Summarize read-only (completeness, including the grand total, and sample ranking; see 08):
`python3 scripts/summarize_openfold3_output.py <OUT> --query-json <Q> --expect-seeds <M> --expect-samples <N>`.
