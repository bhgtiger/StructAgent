# CLI and outputs

Evidence: the flag list below was read from `cryoatom build -h` inside an
installed CryoAtom2 2.1.1 image at commit `856e250`, not inferred from source.
Semantics of individual flags are static source inspection unless noted.

**Confirm the flag surface on the machine you are on** before emitting a
command — one cheap call, no checkpoint touched:

```bash
cryoatom --version        # expect: CryoAtom 2.1.1
cryoatom build -h
```

If the observed help differs from this table, the installed revision differs.
Trust the live help and re-pin the config.

## Entry point

The registered command is `cryoatom`, with a `build` subcommand. Through this
package it is reached via `scripts/cryoatom_launcher.sh`, which binds the
external weight cache into the runtime.

## Main arguments

| Flag | Aliases | Meaning |
|---|---|---|
| `--map-path` | `-v`, `--v` | **Required.** Input cryo-EM density map |
| `--protein-sequence-path` | `-ps`, `--ps` | Protein sequence FASTA |
| `--rna-sequence-path` | `-rs`, `--rs` | RNA sequence FASTA |
| `--dna-sequence-path` | `-ds`, `--ds` | DNA sequence FASTA |
| `--output-dir` | `-o`, `--o` | Output directory (source default: `output`) |
| `--device` | `-d`, `--d` | `cpu` or a GPU number. Default: find an available GPU |

## Additional arguments

| Flag | Aliases | Meaning |
|---|---|---|
| `--mask-path` | `-m`, `--m` | Mask map; masks out redundant regions of the density |
| `--protein-fasta-path` | `-pf`, `--pf` | Protein FASTA **database** for sequence identification |
| `--na-fasta-path` | `-nf`, `--nf` | Nucleic-acid FASTA **database** |
| `--refine-backbone-path` | `-r`, `--r` | Backbone (Cα and P) file for refinement/identification |
| `--keep-intermediate-results` | `-k`, `--k` | Keep `see_alpha_output` and `CryoNet_round_x` |
| `--config-path` | `-c`, `--c` | Additional parameter file. Upstream advises understanding the software first |

Do not invent aliases such as `--protein-fasta` or `--hmm-db`. Do not present
source defaults as recommended parameters.

## Modes

- **With sequence** — pass `-ps` / `-rs` / `-ds` for **every polymer class the map
  contains**. Omitting a class does not mean "build it without a sequence" — it
  means **delete it**. See the warning below.
- **Without sequence** — omit all three; CryoAtom2 assigns the most likely
  residue type per position from density alone, and keeps every polymer class.
  This is the simplest invocation and the only one that is safe when you do not
  know what the map contains.
- **Database identification** — no per-chain sequence, but `-pf` / `-nf`
  databases that must **cover every sequence present in the map**. An incomplete
  database is a silent quality problem, not an error.

`-ps`/`-rs`/`-ds` take the sequences *in this map*. `-pf`/`-nf` take large search
databases. Confusing the two is the most common misuse.

### ⚠ A partial sequence set silently deletes the other polymer classes

**Verified in the installed image, 2026-07-28.** Stage 1 always predicts both Cα
and P atoms, so nucleotide backbone *is* traced regardless. But the model is
masked at write time — `CryoAtom2/utils/flood_fill.py:169-173`:

```python
if rna_sequences is None and dna_sequences is None:
    existence_mask *= prot_mask
```

So `cryoatom build -v map.mrc -ps protein.fasta -o out` on a map containing RNA
or DNA returns a **protein-only model**, with no error, no warning, and no log
line saying anything was removed. The nucleotides were built and then discarded.

Consequences for how you invoke it:

- If the map contains nucleic acid and you have any sequence at all, pass
  **`-rs` and/or `-ds` too**. If you have a protein sequence but no NA sequence,
  prefer the fully sequence-free mode over `-ps` alone — sequence-free keeps
  every class.
- **Never infer scope from what happens to be in the output.** A protein-only
  result is what this flag combination produces whether or not the map had RNA.
- Check the built classes against what you expected. A one-line assertion —
  every polymer class you believe is in the map appears in the output — is the
  cheapest guard there is, and its absence is how a downstream pipeline scored a
  model missing 30% of its atoms as complete.

ModelAngelo 1.0.18 has the **same trap** with a different mechanism
(`skip_nucleotides` when neither `--rna-fasta` nor `--dna-fasta` is given, which
drops every predicted P atom before its GNN stage). If you are comparing the two
tracers, give both of them the full sequence set or neither.

## Pipeline stages

1. **Stage 1** — RU-Net predicts Cα / P atom positions.
2. **Stage 2** — CryoNet builds the all-atom structure, run in **3 rounds**.
3. **Post-processing** — adapted from ModelAngelo.

Both ESM2-650M and RNA-FM are loaded **unconditionally**, including in the
no-sequence path — which is why all six weight files must be present even for a
protein-only or sequence-free run.

## Output risk — the sharpest edge

CryoAtom creates the chosen output directory with `exist_ok`, moves and replaces
files under it, and **deletes intermediates** unless `-k` is given. A reused
directory silently mixes runs.

Always use a fresh, non-existing output path. Never point `-o` at a directory
that holds results you care about.

## Output files

| File | What it is |
|---|---|
| `<out>/<name>.cif` | The final model. In sequence-guided mode it is filtered against the sequences you supplied; in no-sequence mode there is nothing to filter against, so it is the post-processed model |
| `<out>/<name>_raw.cif` | Pre-filtering: more built region, more unassigned noise |
| `<out>/see_alpha_output/`, `<out>/CryoNet_round_x/` | Intermediates — only with `-k` |

**There is no `running_time.log` at 2.1.1.** The write is commented out in
`build.py`, so the pipeline never produces one. The `running_time.log` inside the
public 7XHT fixture archive is a file upstream *shipped* with that example
(contents: `161s`, a total, not a per-stage breakdown). Do not tell a user to
look for a timing log their run will not write, and do not treat its absence as
a failure — time the run yourself.

`scripts/summarize_cryoatom_output.py` reads a tree read-only and reports atom
count, chain count, and the confidence distribution per model.

## Interpretation

Model confidence is written into the output mmCIF **B-factor column**. It is not
an experimental B-factor, not proof of accuracy, and not a biological
conclusion. A predicted model still needs density-fit assessment, geometry
validation, and expert review before it means anything.
