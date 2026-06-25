# 05 — CLI surface & post-install verification

Source-accurate to `model_angelo/__main__.py`, `apps/*.py`,
`utils/setup_weights.py` @ v1.0.18. For installation/verification you mostly need
`--version`, `--help`, `<sub> -h`, and `setup_weights`. The full surface is here
so verification is grounded and so you can sanity-check a user's pasted command —
but **running real build jobs is out of scope** (`references/00`).

## Entry point & subcommands

Console script `model_angelo = model_angelo.__main__:main`. Seven subcommands:
`build`, `build_no_seq`, `evaluate`, `eval_per_resid`, `hmm_search`, `refine`,
`setup_weights`. `model_angelo --version` → `ModelAngelo 1.0.18`.

> Note: every invocation (including `--version`) imports the app modules, which
> import `torch`. So `--version` is not free — it loads torch (fast, won't hang
> like a CUDA op). The verify script wraps it in a timeout.

## Argument surface (aliases are unusual — note both `-x` and `--x` single-letter forms)

**`build`** — map + sequences → model. Default `--model-bundle-name nucleotides`.
- Required: `--volume-path/-v/--v` (map `.mrc`); `--protein-fasta` (six aliases:
  `--protein-fasta` `--fasta-path` `--f` `--pf` `-f` `-pf`).
- Optional: `--rna-fasta/--rf/-rf`, `--dna-fasta/--df/-df`,
  `--output-dir/-o/--o` (default `output`), `--mask-path/-m/--m`,
  `--device/-d/--d` (default auto: `cuda:0` if available else `cpu`; accepts
  `cpu`, `0`, `cuda:0`, or a comma list `0,1`), `--config-path/-c/--c`,
  `--model-bundle-name` (default `nucleotides`), `--model-bundle-path`,
  `--keep-intermediate-results`. (`--pipeline-control` is SUPPRESSED — RELION.)

**`build_no_seq`** — sequence-free; emits per-chain HMM profiles. Default
`--model-bundle-name nucleotides_no_seq`.
- Required: `--volume-path/-v/--v`.
- Optional: same `-o/-m/-d/-c` family + `--model-bundle-name`/`-path` +
  `--keep-intermediate-results`.

**`hmm_search`** — search `build_no_seq` profiles vs a FASTA DB (uses bundled
`pyhmmer`; **no external HMMER binary required**).
- Required: `--input-dir/-i/--i` (the `build_no_seq` output dir),
  `--fasta-path/-f/--f` (FASTA database).
- Optional: `--output-dir/-o/--o`, `--alphabet/-a/--a` (`amino`/`RNA`/`DNA`,
  default `amino` — not guarded by argparse choices), HMMER thresholds
  `--F1 0.02 --F2 0.001 --F3 1e-5 --E 10 --T None`. (Loads no torch weights.)

**`refine`** — refine an existing model into a map (one GNN round).
- Required: `--input-structure/-i/--i`, `--volume-path/-v/--v`.
- Optional: `--output-dir/-o`, `--write-hmm-profiles/-w/--w`, `-d/-c`,
  `--model-bundle-name` (default `nucleotides`).

**`evaluate`** / **`eval_per_resid`** — compare predicted vs target mmCIF
(analysis only, no weights). `evaluate` requires `--predicted-structure/-p` +
`--target-structure/-t`; `eval_per_resid` is similar with `--data-file` reuse.

**`setup_weights`** — pre-download a bundle (+ESM) into the cache.
- `--bundle-name` (default `original` — **but use `nucleotides` /
  `nucleotides_no_seq`**; `references/04`).

## Post-install verification (what "working" means)

Use `scripts/verify_modelangelo.sh --env <name> [--check-gpu] [--check-weights]`.
It activates the env and runs (each with a timeout):

```text
model_angelo --version                       # -> ModelAngelo 1.0.18
model_angelo --help                          # lists the 7 subcommands
model_angelo build -h                        # subcommand parser loads
model_angelo build_no_seq -h
model_angelo setup_weights -h
python -c "import model_angelo, esm, pyhmmer, mrcfile, Bio; print(model_angelo.__version__)"
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"   # --check-gpu
python -c "import torch; print(torch.hub.get_dir())"                            # cache location
```
`--check-weights` also lists
`$(torch.hub.get_dir())/checkpoints/model_angelo_v1.0/nucleotides` (expect
`config.json`, `c_alpha/`, `gnn/`, `success.txt`) and the ESM `.pt`.

Interpretation:
- `--version` + `build -h` OK and deps import → **the install is functional.**
- `torch.cuda.is_available()` → `True` confirms the GPU path; `False` on a GPU
  box means a torch/driver mismatch (`references/06`).
- Weights present at the cache dir → ready for a (future, out-of-scope) build.
- A clean `build -h` does **not** mean a build will succeed on a given map — that
  depends on the map, resolution, and FASTA, which this skill does not run.

## Smoke test only — not a build

`model_angelo build -h` is the boundary. Do **not** launch `model_angelo build -v
<map> -f <fasta> ...` as part of "installing" — that is a production run
(separate concern; needs a validated target + fixture). If the user wants to run
a build, hand off: confirm the environment is `ready`/verified, then point to the
usage examples (README) and the validation-handoff guidance (`references/00`).
