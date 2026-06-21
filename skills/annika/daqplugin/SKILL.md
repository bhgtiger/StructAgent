---
name: daqplugin
description: "Use DAQplugin for residue-wise DAQ quality scoring of protein atomic models in cryo-EM maps through ChimeraX. Trigger when users ask for DAQ scores, DAQ coloring, map-model compatibility, residue-wise local quality, amino-acid assignment quality, DAQ .npy files, DAQ B-factor export, DAQ sequence-shift arrows, or live DAQ monitoring during ISOLDE/manual model movement."
---

# DAQplugin

Drive DAQplugin, a ChimeraX bundle for residue-wise local quality scoring of protein models in cryo-EM maps. DAQplugin can compute DAQ probability grids, color structures by DAQ metrics, monitor live coordinate changes, draw sequence-shift suggestion arrows, and export scores through B-factors.

Use this skill together with `chimerax` for batch invocation. Use `isolde` as well when the user wants live DAQ feedback during interactive ISOLDE refinement.

## Choose The Workflow

1. **Compute new DAQ scores from a map**: run `daqscore compute_grid` when the user has a cryo-EM map and wants a reusable `.npy` score grid.
2. **Score directly at atom/model positions**: run `daqscore compute_pdb` when the user wants original-style DAQ scoring or a scored model quickly.
3. **Color or export from existing scores**: run `daqcolor apply` followed by `save` when the user already has a DAQ `.npy`.
4. **Inspect sequence-register problems**: run `daq arrowwin` when the user asks for sequence-shift suggestions or DAQ arrows.
5. **Live monitoring**: use the GUI/interactive ChimeraX plus ISOLDE. Do not promise live monitoring from a `--nogui` batch job.

Load `references/commands.md` when you need exact command syntax, metrics, backend names, or examples.

## Installation Checks

DAQplugin is a ChimeraX bundle. Prefer the ChimeraX Toolshed install if available:

```chimerax
toolshed install /path/to/chimerax_daqplugin-X.Y.Z-py3-none-any.whl
```

For a development checkout:

```chimerax
devel clean /path/to/DAQplugin/daqcolor
devel install /path/to/DAQplugin/daqcolor
help daqcolor
help daqscore
```

The upstream repository uses submodules, so clone source checkouts with:

```bash
git clone --recurse-submodules https://github.com/kiharalab/DAQplugin.git
```

If command registration is uncertain, run a tiny ChimeraX job with `help daqcolor` or `help daqscore` and treat missing help as a failed install.

## Batch Pattern

Use the `chimerax` skill wrapper for one-shot jobs. Start with `close all`, open map/model with explicit formats, run DAQplugin commands, save to new files, then inspect the wrapper result JSON and output files.

```json
{
  "resultFile": "/tmp/daq_job/result.json",
  "commands": [
    "close all",
    "open /abs/path/map.mrc format mrc",
    "open /abs/path/model.cif format mmcif",
    "daqscore compute_grid #1 0.007 structure #2 metric aa_score output /abs/path/daq_scores.npy stride 2 half_window 9 backend auto",
    "save /abs/path/model_daq_colored.cif #2"
  ]
}
```

For a precomputed `.npy`:

```chimerax
daqcolor apply /abs/path/daq_scores.npy #2 metric aa_score half_window 9
save /abs/path/model_daq_colored.cif #2
```

Prefer `.cif` output. DAQ scores used for coloring are written into the model B-factor field when the model is saved.

## Practical Defaults

- Use `aa_score` first for amino-acid assignment quality.
- Use `atom_score` for CA/atom-position support.
- Use `ss_score` for secondary-structure agreement when available.
- Use `half_window 9` for normal residue-wise smoothing unless the user asks for a sharper local view.
- Use `stride 2` for grid scoring unless the user prioritizes maximum detail over runtime.
- Use `backend auto` first. Force `cpu` for reproducibility or when GPU backends fail.
- Set `batch_size` lower if the run hits GPU/host memory limits.
- Save both the `.npy` and a colored/scored `.cif` into the job output folder.

## Backend And Runtime Notes

DAQplugin auto-selects inference backends by platform:

| Platform | Typical chain |
|---|---|
| Linux NVIDIA | TensorRT -> CUDA -> CPU |
| Windows | DirectML -> CPU |
| macOS Apple Silicon | MLX-Metal -> MLX-CPU -> ORT-CPU |
| macOS Intel | ORT-CPU |

The active backend is printed in the ChimeraX log. If a forced GPU backend silently falls back or fails, rerun with `backend cpu` to separate DAQ/plugin correctness from GPU setup.

## ISOLDE / Live Monitoring

For live feedback during model movement:

1. Compute or load an existing DAQ `.npy`.
2. In interactive ChimeraX, start DAQplugin from `Tools > Validation > DAQplugin`, or run `daqcolor monitor`.
3. Move/refine in ISOLDE.
4. Stop monitoring before closing or saving final outputs:

```chimerax
daqcolor monitor #2 npy_path /abs/path/daq_scores.npy metric aa_score interval 0.5
daqcolor monitor #2 on false
```

Batch `--nogui` jobs are appropriate for compute/apply/save, not for interactive monitoring.

## Sequence-Shift Arrows

Use DAQ arrows when the task is to find possible residue-register or sequence-shift errors:

```chimerax
daq arrowwin #2 /abs/path/daq_scores.npy nwin 5 kshift 5 min_improvement 0.5
daq arrowwin #2 /abs/path/daq_scores.npy chain A apply_isolde_restraints true spring_constant 1500
daq clearrestraints #2
```

Only use `apply_isolde_restraints true` when the user explicitly wants ISOLDE restraints from DAQ suggestions.

## Interpretation

- Positive DAQ values mean local density supports the modeled amino-acid type better than the average distribution.
- Negative values suggest possible amino-acid misassignment or local model inconsistency.
- Near-zero values are ambiguous and can reflect low local resolution or weak density.
- Treat DAQ as evidence for inspection and rebuilding, not as an automatic model-editing instruction.

## Failure Modes

- **Wrong map contour**: grid scoring samples points above the contour. Use the same contour level used for map inspection unless the user gives a different threshold.
- **Map/model frame mismatch**: DAQ scores are meaningless if the model and map are not in the same coordinate frame.
- **Missing `.npy` output**: treat the run as failed even if ChimeraX exits cleanly.
- **Plugin not registered**: `daqscore`/`daqcolor` commands will be unknown. Check Toolshed/dev install.
- **Memory pressure**: reduce `batch_size`, increase `stride`, cap `max_points`, or force `backend cpu`.
- **Monitoring in batch**: live coordinate tracking expects interactive ChimeraX frame updates; use GUI/ISOLDE, not `--nogui`.

## Citation

When reporting DAQ results, cite Terashi et al., Nature Methods 2022, "Residue-wise local quality estimation for protein models from cryo-EM maps", and note that DAQplugin came from `https://github.com/kiharalab/DAQplugin`.
