# 06 — Installation & environment troubleshooting

Install-time failure modes only (this skill stops at a verified install). Each:
symptom → cause → fix. Confirm any mutating fix first.

## conda / activation

- **`conda: command not found` / `bin/activate` not found.** Miniconda's
  `condabin` isn't on PATH. Fix: `export PATH="$PATH:/path/to/miniconda3/bin"`, or
  run `conda init` and restart the shell (README "Installation issues"). The
  install/verify scripts auto-locate `conda.sh`; pass `--conda-sh <path>` if it's
  in a non-standard place.
- **`Could not run conda activate model_angelo`.** The env wasn't created or the
  shell isn't conda-initialised. Re-run the installer; ensure `source
  <conda.sh>` happened first (the wrapper does this).
- **`source install_script.sh` exits the terminal.** The script chooses
  `return` vs `exit` by detecting whether it was sourced; v1.0.18's only change
  over the prior tag is making that termination safe. `install_modelangelo.sh`
  *sources* the script (so its `conda activate` persists); the container recipes
  instead run `bash install_script.sh`. If on an older clone hitting this, run it
  via `bash install_script.sh` inside a subshell.

## torch / CUDA / GPU

- **`torch.cuda.is_available()` is `False` on a GPU box.** The `torch==2.9.1`
  wheel's CUDA runtime doesn't match the driver, or the GPU isn't visible. Check
  `nvidia-smi` (driver present?), `echo $CUDA_VISIBLE_DEVICES` (not emptied?). A
  recent driver is backward-compatible with torch's bundled runtime; a *too-old*
  driver is the usual cause — update the driver, or install a torch build matching
  the available CUDA. ModelAngelo does not pin CUDA separately (`references/01`).
- **CPU-only host.** Install succeeds but building is impractically slow. The
  probe marks this `partial`; CPU use must be explicitly accepted. Prefer a GPU
  box, HPC module, or container with GPU passthrough.
- **Out-of-memory at build time (≥8 GB recommended).** Out of this skill's
  install scope, but worth flagging: the `small_gpu` bundle is *not* runnable here
  (no model definitions), so the practical levers are a bigger GPU or `--device`
  selection — handled when building, not installing.
- **Old PyTorch needed.** If a site is stuck on torch 2.0-era, note v1.0.14 was
  the last torch-2.0 line and v1.0.17 improved old-PyTorch compatibility; but the
  pinned, supported path is torch 2.9.1 on v1.0.18.

## pip / dependencies

- **numpy ABI errors / `numpy>=2` conflicts.** `setup.py` pins `numpy<2.0`.
  Installing ModelAngelo into a pre-existing env with numpy 2.x breaks it — use a
  **fresh** `model_angelo` env (the installer does), don't graft it onto another
  tool's env.
- **`fair-esm`/`pyhmmer` version conflicts.** Pins are `fair-esm==1.0.3`,
  `pyhmmer==0.7.1`. Conflicts come from a dirty env; reinstall clean.
- **`pip install .` fails (no compiler / network).** Needs network to PyPI;
  some deps may build. On air-gapped hosts, pre-build/mirror wheels or use a
  container (route 3).

## weights / download / cache

- **`ERROR: TORCH_HOME is not set, but --download-weights … is set`.** The
  install script hard-errors. Set `TORCH_HOME` to a large dir first
  (`references/04`), then re-run.
- **MD5 mismatch / RuntimeError during bundle download.** Partial/corrupt
  download. Delete the offending `<cache>/hub/checkpoints/model_angelo_v1.0/
  <bundle>/` (or its `.zip`) and re-run `setup_weights` (idempotent).
- **Wrong bundle downloaded.** A bare `model_angelo setup_weights` fetches
  `original` (its default), not the runnable `nucleotides*`. Always pass
  `--bundle-name nucleotides` and `nucleotides_no_seq` (`references/04`).
- **Weights "missing" after download.** They are under **`$TORCH_HOME/hub`**, not
  `$TORCH_HOME` directly. Verify with `python -c "import torch;
  print(torch.hub.get_dir())"`. On shared installs, also check the ESM `.pt` is
  `chmod 0o555` so all users can read it.
- **Zenodo / fbaipublicfiles unreachable (cluster firewall).** The download hits
  `zenodo.org` and `dl.fbaipublicfiles.com`. If blocked, pre-fetch on a connected
  host and copy the `checkpoints/` tree across (`references/04`, offline note).

## hhsuite / hmm_search

- **"Some features require the `hhblits` command of hhsuite".** Only the optional
  **HHblits**-based identification path (feeding `build_no_seq` profiles to
  `hhblits` against your own DB) needs hhsuite installed separately — ModelAngelo
  does not bundle it or any sequence database. The built-in `hmm_search` uses
  `pyhmmer` and needs **no** external binary. Install hhsuite via conda
  (`conda install -c bioconda hhsuite`) only if the HHblits route is wanted.

## non-Linux host

- **macOS / Apple Silicon / Windows.** No supported native install (SBGrid is
  Linux-64 only; the stack is NVIDIA/CUDA). The probe returns `blocked`. Paths: a
  Linux workstation/server, an HPC module (Biowulf/SBGrid), or a Linux container
  on a Linux host with GPU passthrough (route 3). Do not attempt a local macOS
  install.

## RELION 5 integration

- **`ModuleNotFoundError: No module named 'model_angelo'` from RELION.** RELION 5
  imports `model_angelo` as a Python *module* from the env it was compiled
  against — it does **not** call a PATH binary. Build RELION with
  `-DPYTHON_EXE_PATH=<python>` pointing at the env where ModelAngelo is installed,
  and set `TORCH_HOME` (`-DTORCH_HOME_PATH`) so weights are found
  (`references/07`).
