# 07 — MSAs, Templates, Weights and CCD

Pins: `openfold-3@v0.5.0` (`c4771653`). Main code paths:
- `openfold3/core/data/tools/colabfold_msa_server.py` (server client, `MsaComputationSettings`)
- `openfold3/projects/of3_all_atom/config/dataset_config_components.py` (`MSASettings`, `TemplateSettings`)
- `openfold3/core/data/pipelines/preprocessing/template.py` (`TemplatePreprocessorSettings`)
- `openfold3/entry_points/parameters.py` (weights registry)

Kit: `uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/`. Labels are as in [00_scope_and_trust.md](00_scope_and_trust.md).
Workflows that use this file: [05_core_workflows.md](05_core_workflows.md) 7 and 8.

## 1. MSA routes at a glance

| Route | How | What leaves the host | Quality | Use when |
|---|---|---|---|---|
| Public ColabFold server (**default ON**) | `--use-msa-server true`, or the flag left unset | Every unique **protein** sequence in the JSON goes to `https://api.colabfold.com`; the PDB ids of its template hits go to RCSB (§2) | Full MSA | Public sequences, with explicit approval |
| `align-msa-server` → offline predict | 05 workflow 7 | The same, once | Full MSA | GPU nodes without internet; reuse |
| Your own MMseqs2 / ColabFold server | runner YAML `msa_computation_settings: {server_url: https://<your-server>}` + `--use-msa-server true --runner-yaml <yaml>` (the user approves that server for these sequences) | Sequences go to your server; template-hit PDB ids still go to RCSB (§2) unless your server returns no `pdb70` hits | Depends on its databases | Volume, or private data on your own infrastructure |
| Precomputed files | `--use-msa-server false` + `main_msa_file_paths` (+ `paired_msa_file_paths`) | Nothing | Depends on your databases | Unpublished sequences; RNA MSAs |
| Single-sequence | `--use-msa-server false`, no MSA paths | Nothing | **Lower** | Tests, DNA, or when nothing else is possible |

## 2. The public server: exact behaviour **[source]**

- **Endpoint and identity.** `MsaComputationSettings.server_url` defaults to `https://api.colabfold.com`;
  `server_user_agent` is `"openfold"`.
- **What is sent.** Protein chains only; RNA, DNA and ligands are never sent. In server mode an RNA chain without MSA files
  gets **no** MSA features at all (warning `No MSA features will be computed for this chain`), not the query-only MSA of
  §3. Identical sequences are sent once. Each run
  submits one main request for all unique sequences (`ticket/msa`, mode `env`: UniRef plus the BFD/MGnify/MetaEuk/SMAG
  environmental set). It then submits one pairing request (`ticket/pair`, `pairgreedy-env`) per unique set of ≥ 2
  distinct protein sequences. Total requests = 1 + n.
- **Query-level flags do not stop submission.** `use_msas: false` in a query does **not** keep that query's sequences
  local. The collector reads every protein chain of every query. Only `--use-msa-server false` keeps sequences on the host.
- **Server mode overwrites your inputs.** User `main_msa_file_paths` / `paired_msa_file_paths` on protein chains are
  replaced (a warning is printed), and so is `template_alignment_file_path` when the server has hits for that chain.
  Precomputed MSAs therefore need `--use-msa-server false`. CIF-direct `template_cif_paths` are kept.
- **RCSB contact in server mode.**
  - Whenever the server returns `pdb70.m8` hits, their PDB ids are sent in one request to the RCSB GraphQL API
    (`https://data.rcsb.org/graphql`) to remap author to label chain ids. This runs in the MSA step, so it also happens
    with `--use-templates false` and in `align-msa-server`. If RCSB is unreachable, it raises `RuntimeError` and the run
    stops.
  - With templates on, the hit structures are then downloaded from RCSB (`biotite.database.rcsb.fetch`) unless already
    in `structure_directory`. Hit ids leave the host; your sequence does not go to RCSB.
- **Rate limiting and errors.**
  - On `RATELIMIT` or `UNKNOWN`, the client resubmits every 5–10 s with **no retry cap**. A throttled job can wait
    indefinitely while holding a GPU.
  - `ERROR` raises `MMseqs2 API is giving errors…`; `MAINTENANCE` raises too.
  - Other transport errors are retried up to 5 times, then raised. Timeouts (6.02 s) are retried without limit.
  - The 150 s-per-sequence figure is only a progress-bar estimate.
- **Unverified.** Quotas, retention and terms of the public server were not reviewed. No title or body among the 112
  upstream issues collected on 2026-09-22 mentions rate limiting.
- **Community.**
  - #237 (closed): a doubled slash in the URL caused a misleading `invalid ID` error. The fix (`rstrip("/")`) is in v0.5.0.
  - #119 (open): SSL-certificate failures on some hosts. Fix the CA store; do not disable verification.
  - #421 (open): there is no "prepare inputs only" flag besides `align-msa-server`.

**Rule:** for unpublished or confidential sequences, never use the public server. Keep precomputed MSAs, your own server,
or single-sequence mode. Ask before any server use, and record the approval (05 workflow 12).

## 3. Single-sequence mode

- **What it does.** With `--use-msa-server false`, every protein or RNA chain without `main_msa_file_paths` gets a
  query-only MSA (`>query\n<seq>`) **[source]**. It is saved as `<OUT>/msas/<run-id>/dummy/<sha256 of seq>.npz`
  **[live]**. DNA never has an MSA.
- **Cost.** Upstream says only "prediction performance may be worse" **[docs]**. Expect weaker folds for proteins without
  close homologues and weaker interfaces. Confidence from single-sequence runs does not calibrate MSA runs. All inputs on
  the validated site were single-sequence **[measured]**.
- **`use_msas: false` is not the same thing.** At query level it empties the MSA features. For single-sequence runs,
  prefer the dummy MSA described above (04).
- **Templates barely move single-sequence predictions** (#234, #235) **[community]**.

## 4. Precomputed MSA files **[docs]** + **[source]**

| Kind | Format | Rules |
|---|---|---|
| Main MSA | `.a3m` or `.sto` | One alignment per file per chain, query sequence **first** |
| Main MSA layout | One directory per unique sequence | Same file names across chains; the file **stem** selects the database slot (see below) |
| Paired MSA | Same formats, under `paired_msa_file_paths` | Rows already paired across chains. Precomputed paired MSAs were dropped at inference before PR #373 (issue #371); that fix is in v0.5.0 |
| Preparsed | `.npz` from `scripts/data_preprocessing/preparse_alignments_of3.py` | Faster for redundant batches. Contains {file stem → MSA array} |
| Server output | `colabfold_main.a3m`, `colabfold_paired.a3m`, or their `.npz` | Reusable as precomputed |

Paths go in the chain as a list of files, one directory, or one `.npz`. They must exist when the JSON is loaded, so use
absolute paths visible inside the container (04).

File stems and slots (`MSASettings` defaults):
- **Main-MSA stack order (`aln_order`):** `uniref90_hits`, `bfd_uniclust_hits`, `bfd_uniref_hits`, `cfdb_uniref30`,
  `cfdb_hits`, `mgnify_hits`, `rfam_hits`, `rnacentral_hits`, `nt_hits`, `nucleotide_collection_hits`,
  `concat_cfdb_uniref100_filtered`, `mmseqs_colabfold`, `colabfold_main`, `dummy`. Parsed stems outside `aln_order` are
  not stacked (a warning names them); `uniprot_hits` is used only for online pairing.
- **Parsing (`max_seq_counts`):** an `.a3m`/`.sto` file is parsed only if its stem has an entry here; other files are
  skipped silently (a listed `.npz` is not filtered). If none of a chain's files match, the query fails with
  `IndexError: list index out of range` in `parse_msas` (#55).
- **Online pairing:** reads `msas_to_pair` (`uniprot_hits`, `uniprot`). Precomputed paired files use `paired_msa_order`
  (`colabfold_paired`).
- **Row limits:** `max_rows` 16384; `max_rows_paired` 8191.
- **Custom names:** rename your files, or override `dataset_config_kwargs.msa.{aln_order, max_seq_counts, msas_to_pair}`
  in the runner YAML. These fields **replace** the defaults, and typos inside `msa` are ignored silently.

**Online pairing** needs species headers on every row except the first:
`<str><sep><str><sep><str><sep><species_id><sep><str><sep><str>`, with `<sep>` one of `| _ / : -`. UniProt-style
headers work. Pairing happens only for queries with ≥ 2 unique protein chains. Monomers, homomers and RNA get main MSAs
only; protein–RNA pairing is "coming soon". #372 (open) reports an int64 overflow when ranking paired rows: it can occur
with many chains and deep MSAs above `max_rows_paired`, on the online-pairing path only **[community]**.

**Query-level switches** (query level only; inside a chain they are rejected, #172):

| Field (default `true`) | `false` means |
|---|---|
| `use_msas` | No MSA features at all for this query |
| `use_main_msas` | No unpaired rows |
| `use_paired_msas` | No paired rows (neither precomputed nor online) |

## 5. Local MSA generation (no server) **[docs]**, not run here

- **Workflow:** Snakemake, `scripts/snakemake_msa/MSA_Snakefile`. Example configs are `example_msa_config_protein.json`
  (jackhmmer/hhblits against `uniref90 uniprot mgnify bfd`) and `example_msa_config_RNA.json` (`rfam rnacentral
  nucleotide_collection`). Dry-run first: `snakemake -np -s MSA_Snakefile --configfile <cfg.json>`. The tools come from
  `scripts/snakemake_msa/aln_env.yml` (mamba), or from the pixi env `openfold3-msa` (02).
- **Databases:** `python scripts/snakemake_msa/download_of3_databases.py list | download [--output-dir DIR]
  [--download-bfd] [--download-cfdb] [--download-rna-dbs] [--jackhmmer-dbs …] [--hhblits-dbs …]`. They come from S3
  bucket `openfold`, prefix `alignment_databases`. The docs' bare `python download_of3_databases.py` lacks the required
  subcommand.
- **Disk (upstream estimates):**
  - UniRef90 + UniProt + MGnify + PDB SEQRES: 330 GB.
  - BFD: +2.3 TB.
  - ColabFold DB: +1.5 TB.
  - RNA databases: +27 GB.
  - UniRef30: size unverified.
  - Ask before any download.
- **Local template search:** `run_template_search: true` runs hmmbuild/hmmsearch against PDB SEQRES; it needs the
  `uniref90` database (or finished `uniref90_hits.sto` alignments).

## 6. MSA outputs, caching and reuse

- **Saved record:** `<OUT>/msas/<run-id>/{main,paired,template,mappings}`. Raw server files go to
  `<OUT>/msas/raw/<run-id>/`.
  - `<run-id>` is `msa-<login>-<UTC timestamp>-<8 hex>`, so the login name ends up in outputs **[source] [live]**.
  - Sequences are named by hash; `mappings/rep_id_to_seq.json` maps the hashes back to sequences.
- **Scratch:** `$TMPDIR/of3-of-<login>/<run-id>/`, removed at the end. Keep `TMPDIR` node-local.
- **Not a cache.** OpenFold3 never reads a previous run's `msas/` automatically **[docs]**. To reuse MSAs:
  - point chains at the saved files, or
  - feed `align-msa-server`'s `query_msa.json` to `predict --use-msa-server false`.

| `msa_computation_settings` key | Default | Note |
|---|---|---|
| `server_url` | `https://api.colabfold.com` | Your own server here |
| `server_user_agent` | `openfold` | Set `tool/version contact` for your server |
| `msa_file_format` | `npz` | `a3m` for human-readable files |
| `save_openfold_outputs`, `save_colabfold_outputs`, `save_mappings`, `cleanup_msa_dir` | `true` | Unknown keys are rejected |
| `msa_output_directory`, `colabfold_output_dir` | unset | Exact destinations. For `align-msa-server`, `msa_output_directory` must equal `--output-dir` |

For multi-node runs that generate MSAs, keep `save_openfold_outputs: true` and put `<OUT>` on shared storage **[docs]**.

## 7. Templates

Templates are protein-only and monomeric. `--use-templates` defaults to **true** **[source]**.

| Source | Query fields | Structures come from |
|---|---|---|
| Server hits (server on + templates on) | Filled in automatically: `template_alignment_file_path` → `…/template/<rep>/colabfold_template.m8` | RCSB fetch at predict time |
| Precomputed alignment | `template_alignment_file_path`: `.sto` (hmmer fields), `.a3m` (`><entry>_<chain>[/start-end]`) or `.m8` (realigned with Kalign) | `template_preprocessor_settings.structure_directory` (CIF only), else RCSB |
| CIF-direct | `template_cif_paths` [+ `template_cif_chain_ids`, `null` = best chain]; excludes the alignment field | Your CIF for the alignment. Coordinates: see the caveat below |

| Setting | Default | Meaning |
|---|---|---|
| `dataset_config_kwargs.template.n_templates` | 4 (top-k at inference) | Templates featurised per chain |
| `template_preprocessor_settings.max_templates` | 20 | Kept after filtering |
| `…fetch_missing_structures` | `true` | Needs internet |
| `…structure_directory`, `…structure_file_format` | `$TMPDIR/of3-of-<user>/template_data/template_structures`, `cif` | Local hit structures (`cif` or `npz` only) |
| `…cif_direct_min_score` | 0.1 | identity × coverage threshold for CIF-direct |
| `…preprocess_timeout` | 60 s per chain | #164 |
| `…max_release_date`, `…min_release_date_diff`, `…max_seq_id`, `…min_align` | unset | Leakage and quality filters |

- **Offline hosts (kit note OB0-001).**
  - On the offline fetch failure, a `ConnectionError` is raised, not a `RequestError`.
  - That abandons the chain's whole alignment, so stock predicts **untemplated and exits 0**.
  - The kit prints `TEMPLATES DROPPED: query=<q> …` and exits **5**.
  - Fix: set `structure_directory` + `structure_file_format: cif` + `fetch_missing_structures: false` (05 workflow 8).
  - `--allow-template-drop` is a deliberate, recorded acceptance only.
- **Untemplated on purpose:** remove the template keys. `--use-templates false` with keys present fails
  (`UnpicklingError`) **[docs]**.
- **CIF-direct caveat (#406, open, 2026-09-14):** the coordinates are reportedly loaded from
  `<structure_directory>/<file stem>.cif` or fetched from RCSB by that stem, not from your file. The v0.5.0 source carries
  a matching `TODO` in `core/data/primitives/structure/template.py`. Do not rely on edited or non-deposited templates
  without a controlled test **[community]**.
- **#420 (open; reported on post-0.5.0 `main`):** template cache paths in a previous run's `inference_query_set.json`
  are ignored on re-use. Re-run from the alignment files. Applicability to v0.5.0: **[unverified]**.
- The docs link `query_*_with_direct_cif_templates.json` examples that are **not** in the v0.5.0 tree.

## 8. Weights

| Registry name (`parameters.py`) | File | Compatible (code) | Status at v0.5.0 | Bytes | Terms |
|---|---|---|---|---|---|
| `openbind-2025-06-30-174k` | `of3-ob-2025-06-30-174k.pt` | `>=0.5.0` | **Default** (OpenBind-0) | 2 287 872 989 | Apache-2.0 per the OpenBind announcement; the kit's `PINS.json` says upstream states no parameter licence |
| `openfold3-p2-155k` | `of3-p2-155k.pt` | `>=0.4,<0.4.4dev0` (docs table: `<0.5`) | Legacy. Preview-2; legacy kit `openfold3/` (0.4.1). Also on the public S3 bucket | 2 287 928 196 (listing) | Hugging Face card Apache-2.0, behind a contact gate |
| `openfold3-p2-145k` | `of3-p2-145k.pt` | `>=0.4,<0.4.4dev0` | Legacy; not in the docs table. Also on S3 | 2 287 918 314 (listing) | Unverified |
| `openfold3-p1` | `of3_ft3_v1.pt` | `<0.4` | Legacy (preview-1) | 2 288 027 095 (listing) | Hugging Face card Apache-2.0, behind a contact gate |

**Getting OpenBind-0.** Every route needs consent (2.3 GB). There are three routes:
- `setup_openfold --config setup.json`: what it writes, in order, and an example JSON are in
  [02_install_and_environment.md](02_install_and_environment.md) "Weights and CCD"; flags and fields in 03 §4. Set both
  `openfold_cache` and `param_directory`: the latter defaults to `~/.openfold3` even when the former is set **[live]**.
- kit `run.sh install --weights DIR`, which fetches if absent and sha256-checks if present
- a manual download:

```bash
# template — not run
aws s3 cp s3://openfold3-data/openfold3-parameters/of3-ob-2025-06-30-174k.pt <DIR>/ --no-sign-request
#   or: https://openfold3-data.s3.amazonaws.com/openfold3-parameters/of3-ob-2025-06-30-174k.pt
sha256sum <DIR>/of3-ob-2025-06-30-174k.pt   # REQUIRE bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4
```

**Where the checkpoint is looked up** **[source]**:
1. `--inference-ckpt-path` (kit: `--ckpt`, or `$OPENFOLD3_OB0_CKPT`, which the kit requires).
2. Otherwise `<param dir>/<registry file>`. Cache = runner-YAML `cache_path`, else `$OPENFOLD_CACHE`, else `~/.openfold3`;
   param dir = the one line in `<cache>/ckpt_root`, else the cache itself.
   - If `ckpt_root` is missing, `predict` **creates** it pointing at the cache, and creates the cache directory too.
   - The checkpoint is never downloaded at predict time. A missing file raises `…cowardly refusing to perform inference`.
3. The kit's card config defaults `OPENFOLD_CACHE` to the checkpoint's directory.

**Compatibility rules:**
- `--inference-ckpt-name openfold3-p2-155k` (or any legacy name) on 0.5.0 is refused by the version check.
- `setup_openfold`'s `all` excludes legacy entries.
- By path, loading checks state-dict keys and the model version tensor: 0.5.0 has `[2,0,0]`, 0.4.1 has `[1,0,0]`; a
  mismatch raises. Expect preview weights to be refused **[unverified]** (not tested).
- To reproduce preview-2 results, use the legacy 0.4.1 kit (`OPENFOLD3_CKPT`), never 0.5.0.
- Do not suggest the unregistered objects in the bucket (`openbind/*.ckpt`, `waters/*`): they have no documented status
  or terms.

## 9. CCD (`components.bcif`)

- **Source:** `s3://openfold3-data/components.bcif`, 63 393 643 bytes, sha256
  `473d845c8b250b188dbed9bf505ae206692a178a2a7c4869bf8f9de707ffcc0c` (kit `stock/PINS.json`). It is separate from the
  weights.
- **Installation:** `setup_openfold` (only when stale) or kit `run.sh install` (`--ccd FILE` offline) writes it **into the
  installed Biotite package** (`biotite.setup_ccd.OUTPUT_CCD`). So:
  - the environment must be writable once;
  - in an image, this step belongs in the build;
  - a copy beside the weights is ignored.
- **Silent fallback:** nothing fetches the CCD at inference. An environment that skipped the step runs on Biotite's
  bundled subset without warning **[docs]**. `ccd_codes` missing from that subset are expected to fail per query
  **[unverified]**. Check the file's size or sha256 in the environment (see the probe).
- **Custom components:** runner YAML `dataset_config_kwargs.ccd_file_path: <CIF>` replaces the Biotite CCD for the run
  **[source]**.
