# Lessons (date · lesson · evidence)

Append things learned the hard way; keep each entry short with an evidence pointer (runbook step, job id, log line).
Never add host names, user names, accounts, partitions, private map names or local paths: this file ships in the
public package (site-only notes belong in `configs/site_config.local.md`). Preserve this file when updating the skill.

- 2026-11-24 · **pip in a conda env removes user-site packages.** `conda run … pip install -r requirements.txt` printed
  `Found existing installation: numba 0.60.0` / `Uninstalling …` and deleted numba, llvmlite and scipy from
  `~/.local/lib/python3.11/site-packages` (a conda env is not a virtualenv) — packages that other tools in that user
  site relied on. The exact versions were restored with `pip install --user --no-deps`. Always `PYTHONNOUSERSITE=1`
  for the install. · runbook R4 (attempt 2)
- 2026-11-24 · **The user site also shadows the env at run time.** Without `PYTHONNOUSERSITE=1` the env imported numba
  0.60.0 / scipy 1.17.1 from `~/.local` instead of the pinned 0.61.2 / 1.16.0; predict.sh and `conda run` do not isolate
  it. The probe's `--env-check` now reports shadowed packages. · runbook X4
- 2026-11-24 · `conda env remove` on NFS can leave a skeleton (`.nfs*` busy files, stale `*.dist-info`); the next pip
  run skipped timm and the env failed with `cannot import name 'DropPath' from 'timm.layers' (unknown location)`.
  `rm -rf` the prefix. · R6 (attempt 3)
- 2026-11-24 · Shared conda installs: `conda create` failed with `PermissionError` on the base package cache owned by
  another user; a private `CONDA_PKGS_DIRS` fixed it. · R4 (attempt 1)
- 2026-11-24 · The weights server is intermittently unreachable (served a file, 13 min later TCP timeouts for ~50 min):
  `predict.sh --version` then spends ~7 min (3 × ~134 s connect timeouts) before `ERROR: Failed to download …`, exit 1,
  no `.part`. Once the server was back, `--version` downloaded the file in 53 s (same sha256 as a download two hours
  earlier). The download trigger on `--version` is real. Copy + sha256 compare is a safe fallback. · R7
- 2026-11-24 · Weights reference: 470,938,660 B, sha256 `dfb814c6…a380`; `weights_only=True` load passes; the file also
  carries optimizer/scheduler state. · R8
- 2026-11-24 · Without `-g`, a Slurm job that was given GPU 1 on a node without GPU fencing ran on GPU 0 (another job's
  card): `predict.py` overwrites `CUDA_VISIBLE_DEVICES` with its default `"0"`. `-g "${CUDA_VISIBLE_DEVICES:-0}"` (or a
  launcher that appends it) fixed it. On such nodes `nvidia-smi` lists every card, so memory samplers must use
  `-i $CUDA_VISIBLE_DEVICES`. · R16c, template jobs
- 2026-11-24 · Non-orthogonal input: `# Input grid is not orthogonal. EXIT.`, exit status **0**, no files. · R14d
- 2026-11-24 · `--crop_check True`: closed stdin → `RuntimeError: Crop inspection needs terminal input.` (exit 1, PNGs
  left); open silent stdin → waits forever. `conda run --no-capture-output` does forward stdin. · R15a–c
- 2026-11-24 · `-b 9` peaked at 7,328 MiB (8 GB card, 150³ and 432³ maps) and 7,164 MiB (11 GB card, 150³); `-b 18`
  OOMs on 8 GB; `-b 1` needs 1,420 MiB and gives the same result (≤ 0.012 on the enhanced map, one mask voxel); the
  same `-b` repeated is bit-identical. · X1
- 2026-11-24 · Scores exceed 1 after `--reverse_interpolation True` in thousands of voxels (`out_score` 27,787 voxels,
  max 1.137 on the fixture), never on the 1 Å grid. · R11, R12
- 2026-11-24 · The released checkpoint reproduces the authors' published EMD-10387 result (Pearson ≥ 0.999997 for the
  map and both scores; 52 of 903,774 mask voxels differ). · R18
- 2026-11-24 · A site launcher that runs `<env>/bin/python predict.py -m <ckpt>` with `PYTHONNOUSERSITE=1` (and the
  filled `templates/site_launcher.sh.template`) gave outputs bit-identical to `predict.sh` + `conda run` on the same GPU
  model. Different GPU models give float-level differences (≤ 0.012 on the enhanced map, one mask voxel): compare
  runs on one GPU model, or allow for that. · runbook extra B, X6
