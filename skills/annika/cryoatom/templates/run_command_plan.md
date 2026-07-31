# Run plan — a host whose config state is `ready`

Use this **only** when `scripts/cryoatom_env_probe.py --validate-config` reports
`ready` for the machine you are on. Otherwise use
`not_run_command_outline.md`.

Fill this in, show it to the user, and wait for explicit confirmation before
submitting anything.

## 1. Readiness (run these now, paste the real output)

```bash
python3 scripts/cryoatom_env_probe.py --validate-config <CONFIG>   # expect state: ready
cryoatom --version                                                 # expect: CryoAtom 2.1.1
python3 scripts/check_cryoatom_weights.py --cache <CACHE> --mode size
```

- State:
- Version observed:
- Weight cache:
- Verdict: **ready / not ready** → if not ready,
  `references/07_operations_and_troubleshooting.md` § Recovery

## 2. Inputs

| | Path | Checked |
|---|---|---|
| Density map (`-v`) | | exists, readable, inside a bound filesystem |
| Protein FASTA (`-ps`) | | optional |
| RNA FASTA (`-rs`) | | optional |
| DNA FASTA (`-ds`) | | optional |
| Mask (`-m`) | | optional |
| Protein DB (`-pf`) | | optional; must cover every protein sequence in the map |
| NA DB (`-nf`) | | optional; must cover every nucleic-acid sequence in the map |

Mode: **sequence-guided** / **sequence-free** / **database identification**

`-ps/-rs/-ds` are the sequences *in this map*. `-pf/-nf` are search databases.
Do not mix them up.

On a container install, every input and output path must lie inside `$HOME`,
`$PWD`, or an entry of `install.extra_binds`. Otherwise the run sees nothing.

## 3. Output — must not already exist

```
-o  <RESULTS_ROOT>/<run_name>_<date>
```

- [ ] Path does **not** exist yet
- [ ] Not inside an existing result directory
- [ ] On scratch, not home

CryoAtom creates the directory with `exist_ok`, replaces files under it, and
deletes intermediates unless `-k` is passed. Reusing a directory silently mixes
runs. If the user names an existing path, stop and ask for a new one.

## 4. Command

```bash
cryoatom build \
  -v  <MAP> \
  -ps <PROTEIN_FASTA> \
  -rs <RNA_FASTA> \
  -ds <DNA_FASTA> \
  -o  <FRESH_OUTPUT_DIR>
```

Add `-k` to keep `see_alpha_output` / `CryoNet_round_x` for debugging.

## 5. Allocation

Render from the site config rather than hand-typing directives:

```bash
python3 scripts/render_job_template.py templates/run_cryoatom.sbatch.template \
  --set MAP=<MAP> --set OUTPUT_DIR=<FRESH_OUTPUT_DIR> --set JOB_NAME=<NAME> \
  --output <JOB_SCRIPT>
```

- Partition / queue:
- GPU (must be ≥14 GiB VRAM):
- CPUs, memory:
- Estimated runtime (basis: the public 7XHT fixture, a *small* 131 MB map with
  4 chains, takes ~161 s upstream — scale by map size and chain count):
- Requested walltime:

Read the rendered script before submitting. Unresolved double-brace tokens
mean it is not finished.

## 6. Confirm before submitting

State plainly: the command, the output directory, the partition, the walltime,
and that this consumes a GPU allocation. **Wait for the user to say yes.**

## 7. After the run

- Job id and exit state (Slurm: `sacct -j <id> --format=JobID,State,Elapsed,ExitCode`)
- `python3 scripts/summarize_cryoatom_output.py <FRESH_OUTPUT_DIR>`
- `<out>/<name>.cif` — final model, filtered by the supplied sequences
- `<out>/<name>_raw.cif` — unfiltered; more built region, more unassigned noise

Then say what it means, honestly:

> The B-factor column carries **model confidence**, not an experimental
> B-factor. High confidence is not proof the model is correct. This model still
> needs density-fit assessment, geometry validation, and expert review.
