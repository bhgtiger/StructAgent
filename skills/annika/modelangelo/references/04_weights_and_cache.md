# 04 — Weights, the ESM language model & the cache (`TORCH_HOME`)

All claims here are from `model_angelo/utils/torch_utils.py`,
`utils/setup_weights.py`, `model_angelo/config.json`, and `install_script.sh`
@ v1.0.18. Confirm against the installed version with the verify script.

## What gets downloaded

| Bundle | Used by (default for) | Source |
|---|---|---|
| `nucleotides` | `build`, `refine` (their default `--model-bundle-name`) | Zenodo record 7942241 `nucleotides.zip` (md5 `ce568d75…`) |
| `nucleotides_no_seq` | `build_no_seq` (its default) | Zenodo record 7942241 `nucleotides_no_seq.zip` (md5 `4fcbeba1…`) |
| `original`, `original_no_seq`, `small_gpu` | legacy / not runnable here (see caution) | Zenodo record 7733060 |
| **ESM-1b language model** `esm1b_t33_650M_UR50S` | shared dependency of every **seq-aware** bundle | `dl.fbaipublicfiles.com/fair-esm/models/esm1b_t33_650M_UR50S.pt` + matching `-contact-regression.pt` |

The ESM-1b `.pt` is **~7 GB** and is the bulk of the footprint; it is downloaded
**once** and shared across seq-aware bundles. README states ModelAngelo's bundle
weights + the language model combined are **~10 GB** — **plan for >10 GB free.**
`build_no_seq` uses a network not trained on sequences, so the no-seq bundle does
**not** pull ESM.

## How `setup_weights` works

`model_angelo setup_weights --bundle-name <name>`:
1. Prints a reminder to set `TORCH_HOME`.
2. `download_and_install_model(name)` — looks up the Zenodo URL + MD5, downloads
   to `<cache>/checkpoints/model_angelo_v1.0/<name>.zip`, **verifies the MD5**
   (RuntimeError on mismatch), extracts to
   `<cache>/checkpoints/model_angelo_v1.0/<name>/` (giving `config.json`,
   `c_alpha/chkpt.torch`, `gnn/chkpt.torch`), removes the zip, writes
   `success.txt`. **Idempotent**: if `success.txt` exists it short-circuits.
3. If the bundle's `config.json` `gnn_infer_args` has an `esm_model`, calls
   `download_and_install_esm_model(...)` → fetches the two FAIR-ESM `.pt` files
   into `<cache>/checkpoints/` (NOT under `model_angelo_v1.0/`) and `chmod 0o555`
   them (readable+executable for all — for shared installs). Skipped if present.

`install_script.sh --download-weights` calls `setup_weights` for **both**
`nucleotides` and `nucleotides_no_seq`, so a normal `--download-weights` install
fetches both bundles + ESM-1b.

## Exactly where weights land (the cache path)

The cache root is **`torch.hub.get_dir()` = `$TORCH_HOME/hub`**, where PyTorch
defines `TORCH_HOME` defaulting to `${XDG_CACHE_HOME:-~/.cache}/torch` when the
env var is unset. So:

- `TORCH_HOME` **set** (recommended): `$TORCH_HOME/hub/checkpoints/...`
- `TORCH_HOME` **unset**: `~/.cache/torch/hub/checkpoints/...` (per-user)

Exact destinations:
```text
<TORCH_HOME or ~/.cache/torch>/hub/checkpoints/model_angelo_v1.0/nucleotides/        (config.json, c_alpha/, gnn/, success.txt)
<...>/hub/checkpoints/model_angelo_v1.0/nucleotides_no_seq/
<...>/hub/checkpoints/esm1b_t33_650M_UR50S.pt
<...>/hub/checkpoints/esm1b_t33_650M_UR50S-contact-regression.pt
```
It is `torch.hub.get_dir()` = **`$TORCH_HOME/hub`**, NOT `$TORCH_HOME` directly
and NOT `~/.cache/torch` directly. `install_script.sh` records `TORCH_HOME` as a
**conda env var** (`conda env config vars set TORCH_HOME=...`), so it persists
when the env is activated. Confirm the live value with:
```text
python -c "import torch; print(torch.hub.get_dir())"
echo $TORCH_HOME
```
(Model *definitions* — the `model.py` files — live in the installed package under
`model_angelo/model_definitions/<bundle>/{c_alpha,gnn}/`; only the *checkpoints*
are in the cache.)

## Disk & cache planning

- Need **>10 GB free** at the cache target (ESM-1b ~7 GB + two bundles).
- On **shared systems**, set `TORCH_HOME` to a large, world-readable filesystem
  **before** downloading; otherwise every user re-downloads ~10 GB into their own
  `~/.cache/torch`.
- Re-running `setup_weights` is **safe** (idempotent via `success.txt` and ESM
  file-existence checks). A corrupt/partial bundle download raises a RuntimeError
  on MD5 mismatch — delete the `<bundle>/` dir (or its `.zip`) and re-run.

## Cautions (carry these)

- **Default-bundle mismatch.** `setup_weights`' own CLI default is `--bundle-name
  original`, but the build path needs `nucleotides` / `nucleotides_no_seq`. A bare
  `model_angelo setup_weights` downloads the **wrong** bundle. Always pass
  `--bundle-name nucleotides` (and `nucleotides_no_seq`) — which is exactly what
  `install_script.sh --download-weights` does.
- **Only two bundles are runnable in this tree.** `model_definitions/` ships only
  `nucleotides` and `nucleotides_no_seq`; `build`/`build_no_seq`/`refine` raise a
  RuntimeError for `original`/`original_no_seq`/`small_gpu` even though their
  download URLs exist. Don't recommend those bundles for building.
- **Offline / air-gapped install:** pre-fetch on a connected box, then copy the
  whole `<cache>/hub/checkpoints/` tree (preserving the `model_angelo_v1.0/<name>/
  + success.txt` layout and the ESM `.pt` files) to the target's `TORCH_HOME/hub`.
- The download reaches Zenodo + `dl.fbaipublicfiles.com` (FAIR-ESM). Both must be
  reachable; on locked-down clusters this is a common failure (`references/06`).
