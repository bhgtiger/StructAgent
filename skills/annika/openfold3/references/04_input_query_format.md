# 04 — Input query JSON (OpenFold3 v0.5.0)

Grounded in the Pydantic model `openfold-3@v0.5.0:openfold3/projects/of3_all_atom/config/inference_query_format.py`
(`InferenceQuerySet` → `Query` → `Chain` / `PocketConstraint`), the builder
`openfold3/core/data/primitives/structure/query.py`, the tokenizer `openfold3/core/data/primitives/structure/tokenization.py`
and `openfold3/core/data/resources/residues.py` (tag v0.5.0, commit `c4771653`). **[live]** below = run against the
installed 0.5.0 package (files byte-identical to the tag) on CPU: schema parse, structure build and tokenization, no
prediction. Both kit routes feed this same JSON to upstream
(`uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/opt/openfold3_ob0_opt/inputs.py`: "no schema of the package's own").
The upstream page (`openfold-3@v0.5.0:docs/source/input_format_reference.md`, rendered at openfold-3.readthedocs.io) has
errors at v0.5.0; this file wins where they differ. Helper: `scripts/make_query.py`; examples: `templates/queries/`.

## Rules first

- Put `use_msas` / `use_main_msas` / `use_paired_msas` at **query** level. The docs show them inside chains; `Chain`
  forbids extra keys, so that JSON is rejected (`Extra inputs are not permitted`). **[source] [live]**
- Unknown **query-level** and top-level keys are **silently ignored** (`Query` has no `extra="forbid"`): a typo such as
  `use_msa` changes nothing and raises nothing. Run `make_query.py --validate` before every job. **[live]**
- One chain entry per unique molecule; `chain_ids: ["A","B"]` makes identical copies. Chain ids must be unique across the
  whole query: duplicates are not rejected, the builder silently merges them into one chain. **[live]**
- Ligand: `smiles` **or** `ccd_codes` (one code). Both → per-query `KeyError`; a list of codes → `NotImplementedError`;
  `sdf_file_path` → `NotImplementedError`; `covalent_bonds` → accepted and ignored. **[live]**
- MSA/template paths are Pydantic `FilePath`/`DirectoryPath`: they must **exist when the JSON is loaded**, resolved
  against the process working directory (not the JSON's folder). Use absolute paths visible inside any container. **[live]**
- Do not put `seeds` in the input: it is accepted but inference uses the run's seeds (`--num-model-seeds` / runner YAML;
  see `03_cli_reference.md`). **[source]**
- The query key names the outputs: `<output-dir>/<key>/seed_<s>/<key>_seed_<s>_sample_<k>_model.cif`. Use
  `[A-Za-z0-9._-]` only (a `/` would become a sub-directory). Any `query_name` field is overwritten by the key. **[source]**

## Shape and strictness

```json
{ "queries": { "<query_key>": { "chains": [ {...}, {...} ], "use_paired_msas": true,
                                "pocket_constraint": { ... } },
               "<query_key_2>": { "chains": [ ... ] } } }
```

| Level | Model | Unknown keys | Required |
|---|---|---|---|
| top | `InferenceQuerySet` | ignored silently | `queries` (object; a list is rejected) |
| query | `Query` | **ignored silently** | `chains` (list) |
| chain | `Chain` | **rejected** (`extra_forbidden`) | `molecule_type`, `chain_ids` |
| pocket | `PocketConstraint` | **rejected** | `ligand_chain_id`, `pocket_residues` |

Empty containers pass the schema: `"queries": {}` leaves nothing to predict, `"chains": []` fails that query at build,
`"chain_ids": []` silently drops the entry **[live]**.

Several queries in one file = a batch: each query is its own forward pass (no cross-query batching), peak memory is set by
the largest query, time adds up. The query JSON is parsed before the checkpoint loads, so a schema error stops the whole run
first. A query that fails at build/featurization is skipped and listed in `summary.txt` while the rest continue; stock
`run_openfold predict` can still exit 0, so always read `summary.txt` (the kit reports it as `incomplete`, rc 1; see
`08_outputs_and_confidence.md`). **[source]**

## Query-level fields

| Field | Type / default | Notes |
|---|---|---|
| `chains` | list[Chain], required | at least one entry in practice (see above) |
| `use_msas` | bool, `true` | `false` = **empty** MSA features; upstream discourages it — for single-sequence runs prefer the query-only MSA (below) |
| `use_main_msas` | bool, `true` | `false`: monomer/homomer → query sequence only; heteromer → paired rows only |
| `use_paired_msas` | bool, `true` | `false`: heteromer uses main MSAs only; no effect on homomers |
| `pocket_constraint` | object or null | one constrained ligand per query; see below |
| `covalent_bonds` | list or null | schema only — **never consumed** at v0.5.0 |
| `query_name` | str or null | overwritten by the query key |

JSON strings such as `"false"` are coerced to booleans (Pydantic lax mode) **[live]**; write real `true`/`false`.

## Chain-level fields

| Field | Type / default | Molecule types | Notes |
|---|---|---|---|
| `molecule_type` | str, required | all | `protein` `rna` `dna` `ligand`, case-insensitive (ints 0–3 also accepted). No `ion` type |
| `chain_ids` | str or list[str], required | all | a string becomes a one-item list; ints are rejected; list length = copies |
| `sequence` | str | protein/rna/dna | one-letter codes, used as given (no upper-casing, no whitespace stripping). On a ligand entry it breaks the build (`KeyError`) |
| `non_canonical_residues` | {pos: CCD} | protein/rna/dna | 1-based positions (string keys cast to int); replaces that residue; a position past the sequence end is silently ignored |
| `smiles` | str | ligand | one molecule per chain entry; residue name in outputs `LIG0`, `LIG1`, … |
| `ccd_codes` | str or list[str] | ligand | exactly ONE upper-case CCD code (`ATP`, `NAG`, `MG`) |
| `cyclic` | bool, `false` | polymers | head-to-tail cyclic relative-position encoding |
| `main_msa_file_paths` | path(s) | protein, rna | `.a3m`/`.sto` file(s), a directory of them, or a preparsed `.npz` |
| `paired_msa_file_paths` | path(s) | protein, rna | pre-paired MSAs for heteromers (optional; online pairing otherwise) |
| `template_alignment_file_path` | one file | protein | `.sto`, `.a3m` or `.m8`; excludes `template_cif_paths` |
| `template_entry_chain_ids` | list[str] | protein | auto-populated from the alignment; manual choice is "upcoming" upstream |
| `template_cif_paths` | list[file] | protein | CIF-direct templates, aligned on the fly with Kalign |
| `template_cif_chain_ids` | list[str or null] | protein | same length as `template_cif_paths`; `null` = best-matching chain |
| `description` | str | all | free text, not used by the model (handy as an in-file comment) |
| `sdf_file_path` | file | ligand | schema only — builder raises `NotImplementedError` |

Not in v0.5.0 (do not transfer from newer upstream): `ligand_name` (upstream `main` only; v0.5.0 rejects it), covalent
bonds that are actually applied (branch `pr-397`), OpenBind chemical steering (branch `feature/stereo-steering-framework`),
affinity prediction. **[source]**

## Sequences, copies, entities

- Alphabets (`residues.py`): protein `ACDEFGHIKLMNPQRSTVWY` + `X` (UNK); DNA `ACGTN`; RNA `ACGUN`. Any other character —
  including protein `U` (selenocysteine, despite the docs), lower-case letters, gaps and spaces — becomes UNK / `N` / `DN`
  with only a log warning **[live]**. Selenocysteine: put `C` (any letter) and `"non_canonical_residues": {"<pos>": "SEC"}`.
- DNA duplexes need two `dna` chains (one per strand, 5'→3' each).
- Identical sequences share an entity id, whether given as copies or as separate entries **[source]**; different entries
  still need different chain ids. Multi-character ids work (a validated run used `A1`, `B1`) **[measured]**; keep them
  short (the optional `pdb` output format holds one character).

## Ligands and ions

| | CCD code (`ccd_codes`) | SMILES (`smiles`) |
|---|---|---|
| Use for | cofactors, ions, sugars, known PDB components (`ATP`, `HEM`, `NAG`, `MG`, `ZN`) | anything not in the CCD, drug-like compounds, a specific protomer |
| Chemistry from | the CCD (`components.bcif` installed by `setup_openfold`; see `07_msa_templates_weights.md`) | RDKit parse; state charges/stereo explicitly |
| Output naming | keeps the CCD code and CCD atom names | `LIG0`, `LIG1`, … (sorted by SMILES string), atom names `C1`, `C2`, `O1`, … |
| Failure mode | unknown/lower-case code → per-query `KeyError` | invalid SMILES → per-query RDKit error; text after a space is dropped |

Recommendation (skill guidance, not an upstream statement): CCD code when the exact component exists — it is canonical,
PDB-comparable and needs no protonation choice; SMILES otherwise. Ions are ligands with a one-atom CCD code (`MG`, `ZN`,
`CA`, `CL`); give each ion copy its own chain id (`"chain_ids": ["M1","M2"]`) **[live]**. A multi-residue glycan cannot be
written at v0.5.0 (one CCD code per chain, no bonds): use single sugars or a SMILES of the whole glycan. A `.`-separated
SMILES puts several molecules into one chain; use one entry per molecule. Ion placement accuracy is **[unverified]** here.

## Modified residues, cyclic peptides, pockets

- PTMs / modified nucleotides: `"non_canonical_residues": {"4": "SEP"}` on the polymer chain. The CCD leaving atoms are
  removed; the residue is tokenized per heavy atom. MSAs still use the plain `sequence`. The upstream DNA example
  (`PSU` at 3, `5MC` at 4) ran rc 0 in every mode on the validation site **[measured]**. An unknown code fails that query.
- Cyclic peptide: `"cyclic": true` on a (usually short) protein chain; it changes only the relative-position encoding (no
  explicit head–tail bond is added) **[source]**. The upstream MDM2 + cyclic-peptide example ran rc 0 **[measured]**.
- Pocket constraint (new in v0.5.0; biases ONE ligand toward residues via pocket proposals + partial-diffusion refinement):

```json
"pocket_constraint": { "ligand_chain_id": "B",
                       "pocket_residues": [["A", 84], ["A", 99], ["A", 153]],
                       "max_distance": 4.0 }
```

  `residue_id` = 1-based position in the query sequence (not PDB author numbering). Checks: ligand chain must exist
  (load error); ≥1 residue, `max_distance` > 0 (default 4.0 Å); a residue that does not exist fails that query at
  featurization (`Pocket constraint residue A:99 does not match any atoms`) **[live]**. Disable without editing the JSON
  with runner YAML `dataset_config_kwargs: {pocket_sampling: {enabled: false}}` (the docs misspell it
  `datset_config_kwargs`, which the runner config rejects: extra fields are forbidden). Protein–protein contact or bond
  constraints do not exist at v0.5.0.

## Precomputed MSAs (fields only; file naming, pairing and the server are in `07_msa_templates_weights.md`)

- Only protein and RNA chains get MSA features; DNA/ligand MSA fields are ignored. The ColabFold server fills protein
  chains only and **overwrites** their user MSA paths when `--use-msa-server true`: precomputed MSAs need
  `--use-msa-server false`.
- `.a3m`/`.sto`, query sequence first. The file **stem** selects the slot (`uniref90_hits`, `mgnify_hits`, `colabfold_main`,
  …); unknown stems are skipped silently, and a main-MSA path with no default-slot file fails that query
  (`IndexError`/`ValueError`) **[live]**. Full stem list: `07_msa_templates_weights.md` §4.
- The MSA id is the directory (or `.npz`) basename, or the parent directory of a listed file: keep one uniquely named
  directory per unique sequence (`/abs/msas/barnase/`, `/abs/msas/barstar/`). Online pairing needs species ids in headers.
- No MSA paths + `--use-msa-server false` → a query-only ("dummy") MSA is written under `<output-dir>/msas/` **[live]**:
  the recommended single-sequence mode (lower accuracy; say so in reports).

## Templates (fields only; see `07_msa_templates_weights.md` §7)

Protein only, monomeric templates. Either `template_alignment_file_path` (template structures in CIF, located via the
template settings) or `template_cif_paths` (+ optional `template_cif_chain_ids`), never both. CIF-direct keeps a chain only
if identity × coverage ≥ `template_preprocessor_settings.cif_direct_min_score` (0.1). `--use-templates` defaults to true.
The kit counts a polymer entry with either key as templated and exits **5** if those templates were dropped
(`--allow-template-drop` accepts; not judged under `--use-templates false`); remove the keys for an intentionally
untemplated query (`03_cli_reference.md`).

## Token count (estimate before you run)

| Component | Tokens |
|---|---|
| standard residue / nucleotide (incl. `X`, `N`) | 1 each × copies |
| modified residue (`non_canonical_residues`) | its heavy atoms minus leaving atoms (SEP 10, ABA 6, MSE 8, PSU 20, 5MC 21) |
| ligand (CCD or SMILES) | its heavy atoms (ATP 31, GTP 32, HEM 43, NAG 15, benzene 6); ion 1 |

Rule from the AF3-style tokenizer **[source]**; the per-code counts above and the 77 codes in `make_query.py` were checked
against the real builder **[live]**. Confirmed on real outputs (PAE matrix size = tokens: ubiquitin 76, T4L + toluene
171, β-lactamase + ligand 286, Mcl-1 ×4 + 3 ATP + ligand 737, 13-nt DNA with PSU+5MC = **52**, not 13) **[measured]**.
`make_query.py --validate` prints this estimate and the kit's own count.

Why it matters: pair activations grow with tokens² (triangle updates ~tokens³ compute) **[paper]**, so memory and time are
set by the largest query. The kit sizes its gates on **polymer tokens only** (`inputs.py`: protein/RNA/DNA residues ×
copies; ligand and modified-residue atoms not counted): `exact` CUDA graphs up to 512, `big` row blocks / host streaming
from 1 401 (details and capacity: `06_kit_modes_and_multigpu.md` §4). Measured memory by size: `09_validation_and_benchmarks.md`
(no OOM up to 995 tokens on A100 40 GB, single-sequence). Beyond your own measured size, test before promising.

## Common errors

| Symptom (verbatim fragment) | Stage | Cause → fix |
|---|---|---|
| `chains.0.use_msas  Extra inputs are not permitted` | load | MSA flag inside a chain → move to query level |
| `Extra inputs are not permitted` on `ligand_name`, `force`, … | load | field not in v0.5.0 `Chain`/`PocketConstraint` → remove |
| `molecule_type  Input should be 0, 1, 2 or 3` | load | e.g. `"ion"` → `ligand` + `ccd_codes` |
| `chain_ids.0  Input should be a valid string` | load | numeric id → quote it |
| `queries  Input should be an object` | load | `queries` given as a list → map of key → query |
| `Path does not point to a file` / `…a directory` | load | MSA/template path missing, relative, or not bound into the container |
| `pocket constraint ligand_chain_id 'Z' does not match any ligand chain` | load | wrong ligand chain id |
| `Cannot specify both 'template_alignment_file_path' and 'template_cif_paths'` | load | pick one template mode |
| `Multiple CCD codes for a single chain are not yet supported.` | per query | one code per ligand chain |
| `SDF format for ligands is not yet supported.` | per query | use `smiles` |
| `No valid molecule specification found.` | per query | ligand without `smiles`/`ccd_codes` |
| `KeyError: '<SMILES>'` or `KeyError: '<CCD>'` | per query | ligand with both `smiles` and `ccd_codes`, or with a `sequence` → keep one identifier |
| `No atom information found for residue 'atp' in CCD` | per query | lower-case or unknown CCD code |
| `'NoneType' object has no attribute 'as_array'` | per query | unknown code in `non_canonical_residues` |
| `TypeError: 'NoneType' object is not iterable` | per query | polymer chain without `sequence` |
| RDKit `MolToSmiles(NoneType)` | per query | invalid SMILES |
| `Pocket constraint residue A:99 does not match any atoms` | per query | residue number beyond the sequence / wrong chain |
| nothing, but results look wrong | — | query-level typo ignored; lower-case sequence → UNK; duplicate chain ids merged |

All fragments reproduced **[live]**. "per query" = the query is skipped and listed as failed in `summary.txt`; the rest of
the batch continues.

## Minimal examples

Protein + CCD cofactor + ion (`templates/queries/protein_ligand_ccd.json`, 199 tokens):
```json
{"queries": {"hras_gtp_mg": {"chains": [
  {"molecule_type": "protein", "chain_ids": ["A"], "sequence": "MTEYKLVVVGAGGVGKSALTIQ...EIRQH"},
  {"molecule_type": "ligand", "chain_ids": ["B"], "ccd_codes": "GTP"},
  {"molecule_type": "ligand", "chain_ids": ["C"], "ccd_codes": "MG"}]}}}
```
Homodimer with a phosphoserine in both copies (sequences shortened here):
```json
{"queries": {"dimer_sep": {"chains": [
  {"molecule_type": "protein", "chain_ids": ["A", "B"], "sequence": "MKTAYSAKR",
   "non_canonical_residues": {"6": "SEP"}}]}}}
```
Protein–DNA duplex (two strands) plus a cyclic peptide chain (syntax illustration):
```json
{"queries": {"pdna": {"chains": [
  {"molecule_type": "dna", "chain_ids": ["A"], "sequence": "TTTTGCCATGTAATTACCTAA"},
  {"molecule_type": "dna", "chain_ids": ["B"], "sequence": "ATTAGGTAATTACATGGCAAA"},
  {"molecule_type": "protein", "chain_ids": ["C"], "sequence": "MDEKRPRTAF...KIKKS"},
  {"molecule_type": "protein", "chain_ids": ["P"], "sequence": "EALKKESLLL", "cyclic": true}]}}}
```
Precomputed MSAs + SMILES ligand, query-level MSA flag (placeholders; run with `--use-msa-server false`):
```json
{"queries": {"msa_lig": {"use_main_msas": true, "chains": [
  {"molecule_type": "protein", "chain_ids": ["A"], "sequence": "...",
   "main_msa_file_paths": "<ABSOLUTE_MSA_ROOT>/protA"},
  {"molecule_type": "ligand", "chain_ids": ["L"], "smiles": "CC(=O)Oc1ccccc1C(=O)O"}]}}}
```
The `...` sequences above are illustrative; the `templates/queries/` files are complete and validated.

## Helper — `scripts/make_query.py` (stdlib, Python ≥ 3.9)

```bash
# template — not run
python3 scripts/make_query.py --name ras --protein @hras.fasta --ligand-ccd GTP --ligand-ccd MG --out ras.json
python3 scripts/make_query.py --spec batch.tsv --out batch.json   # query<TAB>type<TAB>value[<TAB>copies[<TAB>ids]]
python3 scripts/make_query.py --validate q.json [--strict] [--no-path-check] [--json]
```

Assigns chain ids A, B, C… in argument order, upper-cases sequences, maps `--msa-dir DIR` to `DIR/<first chain id>`,
prints the JSON to stdout unless `--out` is given, refuses to overwrite without `--force`, and validates every rule above
(exit 0 ok, 1 invalid, 2 usage; `--help` also documents the JSON spec). It is a convenience layer: the pinned Pydantic
model is authoritative, and it cannot confirm that a CCD code outside its built-in table exists (it says so in a NOTE).
