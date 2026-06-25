# Lessons (running log for this skill)

Append-only notes that improve the skill over time. v0.1 seed entries come from
the pinned-source review (v1.0.18) + the web currency/operational gather
(2026-06-22). **v1.0 = first real install, executed end-to-end on volta
(2026-06-22)** — see the v1.0 section.

## v0.1 — seeds from source review + gather (2026-06-22)

- **The install is clean; the value is around it.** Upstream is just `git clone`
  + `source install_script.sh` (conda env `model_angelo`, Python 3.11,
  `torch==2.9.1 torchvision`, `pip install .`). So this skill adds: a config-first
  readiness gate, route selection, weight-cache planning, a pinned-tag reproducible
  wrapper, and verification — not a reimplemented installer.
- **Weights live at `$TORCH_HOME/hub`, NOT `$TORCH_HOME`.** `torch.hub.get_dir()`
  = `$TORCH_HOME/hub`; bundles land in
  `…/hub/checkpoints/model_angelo_v1.0/<bundle>/` and ESM-1b in `…/hub/checkpoints/`.
  Users will look in the wrong place; always resolve with `python -c "import
  torch; print(torch.hub.get_dir())"`. (torch_utils.py.)
- **`setup_weights` default bundle is `original` — the WRONG one for building.**
  `build`/`refine` default to `nucleotides`, `build_no_seq` to
  `nucleotides_no_seq`, and only those two ship runnable model definitions. A bare
  `model_angelo setup_weights` fetches `original`. Always pass `--bundle-name
  nucleotides` (+ `nucleotides_no_seq`) — which is what `install_script.sh
  --download-weights` does.
- **~10 GB, mostly ESM-1b (~7 GB).** The ESM language model is the bulk and is
  shared across seq-aware bundles (downloaded once); `build_no_seq` doesn't need
  it. Plan >10 GB free at the cache target; the probe checks free disk there.
- **`hhblits`/hhsuite is an EXTERNAL, OPTIONAL dependency.** The bundled
  `hmm_search` uses `pyhmmer` (no external binary). Only the HHblits-based ID path
  downstream of `build_no_seq` needs hhsuite (`conda install -c bioconda hhsuite`).
  Biowulf's note "some features require the hhblits command of hhsuite" refers to
  that path. ModelAngelo ships no sequence databases.
- **RELION 5 imports `model_angelo` as a module, not the PATH binary.** A
  standalone install on PATH is not enough for RELION integration; RELION needs
  `import model_angelo` to work in its compiled-against Python env
  (`-DPYTHON_EXE_PATH`) with `TORCH_HOME` set, else `ModuleNotFoundError`.
- **Non-Linux is `blocked`.** macOS/Apple Silicon/Windows have no supported
  install (SBGrid Linux-64 only; NVIDIA/CUDA stack). Route to a Linux box, an HPC
  module (Biowulf `module load model-angelo`), SBGrid, or a Linux container.
- **`--version` is not free.** `model_angelo --version` imports the app modules
  which import torch. It won't hang like a CUDA op, but wrap it in a timeout and
  don't treat its success as proof a build will work.
- **Probe verified on a real Linux/GPU host (volta, 2× RTX 2080 Ti).** Computed
  `partial` correctly (installable; `TORCH_HOME` unset + torch unprobed). Confirms
  the deterministic `determine_state()` gate works on a real machine.

## v1.0 — first real install (volta, 2026-06-22)

Installed a **private v1.0.18** into `~/.conda/envs/model_angelo` on volta (Linux,
2× RTX 2080 Ti). Verified end-to-end: `ModelAngelo 1.0.18`, `torch 2.9.1+cu128`,
`cuda.is_available()=True`, verifier **9/9**, weights (~10 GB: nucleotides +
nucleotides_no_seq + ESM-1b) present at `~/model_angelo_weights/hub/checkpoints`.
**The skill is now execution-validated on Linux+NVIDIA.** Findings:

- **PROBE BUG (found + fixed).** The probe truncated `conda env list` at the
  600-char excerpt and `installed` ignored `conda_env_present`, so it reported
  *"not installed"* on a host that already had a year-old shared `model_angelo`
  env — a near-clobber. Fixed: read the FULL `conda env list` (`capture_full`) and
  set `installed = exe or package or conda_env_present`, with an "env exists but
  not on current PATH" reason. Real machines have pre-existing envs; trust the
  full listing.
- **READ-ONLY BASE ANACONDA needs `CONDA_PKGS_DIRS`.** volta's base is
  `/soft/anaconda-new` (read-only for the user); `conda create` died with
  `PermissionError` writing repodata cache into `/soft/anaconda-new/pkgs`. Fix:
  `export CONDA_PKGS_DIRS=$HOME/.conda/pkgs` before create, and prefer `mamba`.
  **`install_modelangelo.sh` and upstream `install_script.sh` do NOT set this** →
  they fail on shared read-only bases. → installer fix needed (see below).
- **SAME-NAME SHARED ENV = clobber risk.** Upstream `install_script.sh` decides
  "env exists?" by `grep`-ing `conda info --envs` for the name; a shared same-name
  env in another `envs_dir` matches, so it skips `create` and pip-installs into
  whatever `conda activate <name>` resolves to — potentially **clobbering a shared
  env**. Mitigation used: install by explicit private **prefix**
  (`conda create -p ~/.conda/envs/model_angelo`). → installer guard needed.
- **`envs_dir` shadowing (useful).** A private `~/.conda/envs/model_angelo`
  (envs_dir[0]) shadows a shared `/soft/.../model_angelo` by name for that user —
  so the user gets v1.0.18 via `conda activate model_angelo` while others keep the
  shared one; reach the shared one only via its full prefix.
- **numpy<2.0 downgrade is expected.** torch 2.9.1 pulls numpy 2.x; ModelAngelo's
  pin downgrades to 1.26.4. pip prints benign "dependency conflicts" but
  `model_angelo.apps.build` + torch + numpy import and run fine. Not an error.
- **Live CLI confirmed:** `model_angelo --version` → `ModelAngelo 1.0.18`; the 7
  subcommands + `build -h` surface match the pinned source.

## Installer fixes proposed (NOT yet applied — pending owner OK)

These would make `scripts/install_modelangelo.sh` survive the volta-class case:
1. `export CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-$HOME/.conda/pkgs}"` + prefer `mamba`
   for env creation (read-only shared base anaconda).
2. Detect an existing same-name env in ANY `envs_dir`; if found, refuse or switch
   to an explicit `--env-prefix` install (never pip into a pre-existing shared
   env). Add an `--env-prefix` option.
The probe already warns about the same-name shadow/clobber; the installer should
act on it.

## Open items

- [x] Execute a full install end-to-end + verify on a real Linux+GPU host — DONE
      (volta, private v1.0.18, verifier 9/9).
- [x] Exercise `--download-weights`/`setup_weights` against live Zenodo + FAIR-ESM
      + confirm cache layout — DONE (bundles + ESM-1b present; MD5 verified in log).
      (ESM `chmod 0555` not separately checked on this single-user prefix install.)
- [x] Capture a live `model_angelo --version` — DONE (1.0.18).
- [ ] Apply the two installer fixes above to `install_modelangelo.sh` (owner OK).
- [ ] Confirm the shared-route wrapper + world-readable weights on a real
      multi-user cluster (volta used a personal prefix, not the shared-route path).
- [ ] Add a verified site config (module name, partition, TORCH_HOME) only once a
      real cluster target is known — site specifics are not universal.

## How to add a lesson

One bullet per lesson: what surprised you, the evidence (source ref or observed
behavior), and the rule it changes. Update the matching reference so the lesson
is enforced, not just noted.
