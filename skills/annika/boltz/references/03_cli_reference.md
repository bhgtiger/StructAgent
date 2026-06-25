# 03 — CLI Reference (`boltz predict`)

Captured **live** from `boltz predict --help` in the validated `boltz2` env on
`volta` (boltz 2.2.1), cross-checked against `src/boltz/main.py` at v2.2.1. Only
generate commands from flags listed here; if a user needs something not here,
capture live help on *their* host first.

## Entry point

- Package `boltz`; console script `boltz` → `boltz.main:cli`.
- Only subcommand: `boltz predict DATA [OPTIONS]`.
- `DATA` = one `.yaml`/`.yml`/`.fasta`/`.fa`/`.fas` file **or a directory** of
  such files. YAML is preferred; FASTA is deprecated and can't express all
  features.
- Writes to `<out_dir>/boltz_results_<input_stem>/`.

## Options — names and LIVE defaults (volta, v2.2.1)

| Option | Live default | Notes |
|---|---|---|
| `--out_dir PATH` | `./` | Final dir is `boltz_results_<stem>`. |
| `--cache PATH` | `~/.boltz` or `$BOLTZ_CACHE` | Where weights/data live/download. |
| `--checkpoint PATH` | model checkpoint | **Help string is stale** (says "Boltz-1"); default model is Boltz-2. |
| `--devices INTEGER` | `1` | Multi-GPU via Lightning/DDP. |
| `--accelerator [gpu\|cpu\|tpu]` | `gpu` | `cpu` prints a slow warning. |
| `--recycling_steps INTEGER` | `3` | Docs suggest `10` for AF3-like heavier runs. |
| `--sampling_steps INTEGER` | `200` | Structure diffusion steps. |
| `--diffusion_samples INTEGER` | `1` | Number of models; raise for diversity (e.g. 5/25). |
| `--max_parallel_samples INTEGER` | **`None`** | (source-derived doc guessed 5 — live says None.) |
| `--step_scale FLOAT` | `1.638` Boltz-1 / `1.5` Boltz-2 | Lower = more diverse samples. |
| `--write_full_pae` | help: **`True`** | A `pae_*.npz` is emitted by default (observed). |
| `--write_full_pde` | `False` | A `pde_*.npz` was still observed with defaults — see 07. |
| `--output_format [pdb\|mmcif]` | `mmcif` | `.cif` default; pass `pdb` for `.pdb`. |
| `--num_workers INTEGER` | `2` | Dataloader workers. |
| `--override` | `False` | Recompute instead of reusing cached processed/predictions. |
| `--seed INTEGER` | `None` | Set for reproducibility. |
| `--use_msa_server` | `False` | Auto-MSA via MMseqs2/ColabFold (network; privacy!). |
| `--msa_server_url TEXT` | `https://api.colabfold.com` | Used only with `--use_msa_server`. |
| `--msa_pairing_strategy TEXT` | `greedy` | `greedy` or `complete`. |
| `--msa_server_username TEXT` | env `BOLTZ_MSA_USERNAME` | Basic auth. |
| `--msa_server_password TEXT` | env `BOLTZ_MSA_PASSWORD` | Basic auth. |
| `--api_key_header TEXT` | `None` → `X-API-Key` | Param default None; Boltz falls back to `X-API-Key` internally. |
| `--api_key_value TEXT` | — | Custom MSA server auth value. |
| `--use_potentials` | `False` | Inference-time steering potentials. |
| `--model [boltz1\|boltz2]` | `boltz2` | Default is Boltz-2. |
| `--method TEXT` | `None` | Boltz-2 only; see method vocabulary below. |
| `--preprocessing-threads INTEGER` | `1` (CLI) | CLI/decorator default is 1 (live); the Python fn-signature uses `cpu_count()`. |
| `--affinity_mw_correction` | `False` | Add molecular-weight correction to affinity head. |
| `--sampling_steps_affinity INTEGER` | `200` | Affinity diffusion steps. |
| `--diffusion_samples_affinity INTEGER` | **`5`** | (resolves the 5-vs-3 ambiguity — live says 5.) |
| `--affinity_checkpoint PATH` | affinity checkpoint | **Help string stale** (says "Boltz-1"). |
| `--max_msa_seqs INTEGER` | `8192` | Max MSA sequences used. |
| `--subsample_msa` | **`True`** | (resolves docs-false vs source-true — live says True.) |
| `--num_subsampled_msa INTEGER` | `1024` | Used when subsampling. |
| `--no_kernels` | `False` | Disable cuEquivariance kernels (for problem/old GPUs). |
| `--write_embeddings` | `False` | Dump `s`/`z` embeddings to `embeddings_<id>.npz`. |

### `--method` vocabulary (Boltz-2 only)

Case-insensitive, from `const.py:method_types_ids`. Most useful:
`X-RAY DIFFRACTION`, `ELECTRON MICROSCOPY`, `SOLUTION NMR`, `MD`, `AFDB`.
Full set also includes `SOLID-STATE NMR`, `NEUTRON DIFFRACTION`,
`ELECTRON CRYSTALLOGRAPHY`, `FIBER DIFFRACTION`, `POWDER DIFFRACTION`,
`INFRARED SPECTROSCOPY`, `FLUORESCENCE TRANSFER`, `EPR`, `THEORETICAL MODEL`,
`SOLUTION SCATTERING`, `OTHER`, `BOLTZ-1`, `FUTURE1`–`FUTURE5`.

## Known-stale / surprising help strings (don't repeat the mistake)

- `--checkpoint` and `--affinity_checkpoint` help say "Boltz-1 model by default"
  even though the default model is **Boltz-2**. The defaults are correct; the
  wording is stale.
- `--max_parallel_samples` default is `None` (live), not `5`.
- `--write_full_pae` help reads "Default is True"; treat the **observed output**
  (07) as ground truth and don't promise exact npz contents without checking.
- **Click decorator vs Python fn-signature mismatches** — the CLI (decorator =
  what live `--help` prints) is what actually applies:
  - `--preprocessing-threads`: decorator/CLI = `1`; fn-signature = `cpu_count()`.
  - `--diffusion_samples_affinity`: decorator/CLI/live = `5`; fn-signature = `3`.
- `--api_key_header`: parameter default is `None`; Boltz falls back to
  `X-API-Key` internally when unset.

## Common command shapes (only flags above)

```bash
# Monomer/complex, auto MSA, CIF out
boltz predict input.yaml --use_msa_server --out_dir results

# Reproducible, more samples, PDB out
boltz predict input.yaml --use_msa_server --diffusion_samples 5 \
  --seed 42 --output_format pdb --out_dir results

# Custom MSA already in the YAML (no server)
boltz predict input.yaml --out_dir results

# Older/problem GPU
boltz predict input.yaml --use_msa_server --no_kernels --out_dir results
```
