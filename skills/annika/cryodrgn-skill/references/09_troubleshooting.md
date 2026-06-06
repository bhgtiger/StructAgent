# 09 — Troubleshooting

Every fix below is gated on a **current** report (`02_config_session_and_environment.md`):
read the per-host `config_state` first, then act. Flags and defaults are
`[VALIDATED: cryoDRGN 4.2.1]` against the captured live help (`--help` captured
2026-06-06 on a Linux + NVIDIA GPU host). If the installed version differs, confirm against its
own `-h`.

## Environment / readiness

| Symptom | Likely cause | What to do |
|---|---|---|
| `cryodrgn: command not found` | not installed / wrong env | report `config_state: blocked`; do **not** blindly install — offer the documented install (Anaconda + `pip install cryodrgn`) with the Linux+NVIDIA caveat, and run it only after the user confirms; recommend activating the right env. |
| No NVIDIA GPU / `nvidia-smi` missing | non-GPU host (e.g. login node, laptop) | per-host `blocked` for training/abinit/eval/backproject; cryoDRGN needs an NVIDIA GPU (CUDA); suggest a GPU node. Parse/downsample/`view_*` may still be feasible on CPU but confirm first. |
| Python out of tested range | interpreter 3.14+ or <3.10 | flag drift (`within_tested_range: no`); recommend a 3.10–3.13 env per docs; do not assert it will/won't work. |
| Report missing or > TTL / env changed | absent/stale | re-run the probe (`scripts/cryodrgn_env_probe.py`); until then give only general explanation. |
| Probe failed / ambiguous | permissions, odd PATH | `config_state: unknown`; request a re-run or a pasted report; no machine-specific advice. |

> macOS note (general, sourced — not a verdict on any one machine): cryoDRGN's
> `pyproject.toml` ships only the `Operating System :: POSIX :: Linux` classifier
> [src: `sources/source/cryodrgn_4.2.1/pyproject.toml`], and the install docs
> require a Linux workstation/cluster with NVIDIA GPUs. The probe computes support
> per host; let it decide rather than assuming.

## Data parsing / inputs

| Symptom | Likely cause | What to do |
|---|---|---|
| "file not found" for `.mrcs` referenced by `.star`/`.cs` | broken relative paths | add `--datadir <dir>` pointing at the `.mrcs` location [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.backproject_voxel.help.txt; same `--datadir` on parse/downsample/abinit). |
| Wrong/garbled translations or CTF scaling | `-D`/`--Apix` set to the downsampled box instead of the **original** | re-parse with `-D <original_box>` (and `--Apix <orig>`), the value of the *original* box, not the downsampled one (`04_data_model_and_formats.md`) [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.parse_ctf_star.help.txt). |
| `parse_ctf_star` missing fields | non-standard `.star` lacking `_rln*` CTF cols or image-size/pixel-size | supply the missing image parameters explicitly via the override flags `-D`/`--Apix`/`--kv`/`--cs`/`-w`/`--ps` [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.parse_ctf_star.help.txt — these are listed under "Optionally provide missing image parameters"); check the star actually has the CTF columns. |
| Loading config from `.pkl` errors | deprecated | use `config.yaml`; `eval_vol weights.pkl -c <workdir>/config.yaml` (the live help labels `-c/--config` as a `YAML` file) [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.eval_vol.help.txt). |

## Reconstruction quality

| Symptom | Likely cause | What to do |
|---|---|---|
| Backprojection / map sign looks wrong | data sign convention | cryoDRGN **inverts the data sign by default**; pass `--uninvert-data` only when the data should **not** be inverted (e.g. EMPIAR-10076) [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.backproject_voxel.help.txt: "`--uninvert-data  Do not invert data sign`"; cryodrgn.abinit.help.txt: "Flag for not inverting input data (e.g. for EMPIAR-10076)"). To flip the contrast of an **output** volume, use `--invert` on `analyze`/`eval_vol` (cryodrgn.analyze.help.txt / cryodrgn.eval_vol.help.txt). |
| Map is mirrored vs. RELION/cryoSPARC reference | **handedness** convention difference | usually not an error; `cryodrgn_utils flip_hand`, or `--flip` on analyze/eval_vol [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.analyze.help.txt / cryodrgn.eval_vol.help.txt: "Flip handedness of output volume(s)"). |
| Noisy/uninterpretable pilot map | too few particles in sanity check | use more images (`--first 25000`) or the full stack; this is expected for a quick subset (cryodrgn.backproject_voxel.help.txt). |
| Latent space looks like junk / one blob | junk particles, too-short training, wrong poses | filter junk with `cryodrgn filter` (runnable on a ready host after confirmation; writes a selection `indices.pkl`), train longer (e.g. 25→50 via `--load`), or reconsider poses (consider `abinit`) [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.filter.help.txt). `[run-with-confirmation]` |
| Results change a lot 25→50 epochs | not converged | train longer; compare; see `08_validation_and_benchmarks.md`. |

## Version / indexing

| Symptom | Likely cause | What to do |
|---|---|---|
| `weights.N.pkl`/epoch numbers seem off by one | **1-based indexing since v3.5.0** | for 4.2.1, indexing is 1-based: `analyze <workdir> 25` ↔ `z.25.pkl`/`weights.25.pkl` [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.analyze.help.txt: epoch is "1-based indexing, corresponding to z.N.pkl, weights.N.pkl"). On older installs confirm via the report's cryoDRGN version + live help. |
| Flags differ from these references | installed version ≠ 4.2.1, or live drift | if the installed version != 4.2.1, defer to its own `-h` (capture via `--live-help`); these references are `[VALIDATED: cryoDRGN 4.2.1]` and may not match other versions. |

## Interactive tools

`cryodrgn filter` and `cryodrgn dashboard` are interactive/served. On a host whose
probe reports `config_state: ready`, they **are** launchable after explicit user
confirmation `[run-with-confirmation]`:

- `cryodrgn dashboard [outdir]` serves a local web dashboard; default bind is
  `127.0.0.1` on port `5050`. Use `--no-browser` to skip auto-opening a tab and
  `--port`/`-p` to change the port (`--host` changes the bind address)
  [VALIDATED: cryoDRGN 4.2.1] (cryodrgn.dashboard.help.txt).
- `cryodrgn filter <outdir>` opens an interactive scatter selection; `cryodrgn
  analyze` must be run first in that workdir for the epoch you want to filter.
  Add `--force`/`-f` to save the selection to `indices.pkl` without prompting, and
  `--sel-dir` to pre-choose the output directory [VALIDATED: cryoDRGN 4.2.1]
  (cryodrgn.filter.help.txt).

## When unsure

Prefer routing to live `-h` (once `config_state` ≥ partial) over guessing. If a
fix would move, delete, or convert the user's data, **confirm with the user before
doing it** — explain the option and let the user approve (`07_safety_license_privacy.md`).
