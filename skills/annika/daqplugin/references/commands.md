# DAQplugin Command Reference

Source: `https://github.com/kiharalab/DAQplugin` at commit `8a367f6` (`v1.0.4` docs).

## Commands

### Compute grid-based DAQ scores

```chimerax
daqscore compute_grid mapInput contour [structure #model] [output npyPath] [stride N] [batch_size N] [max_points N] [ckpt ckptPath] [metric metricName] [k N] [colormap cmap] [half_window N] [monitor true|false] [backend name] [gpu_id N]
```

Use when the user has a cryo-EM map and wants a reusable DAQ `.npy` score grid. `mapInput` can be a loaded volume model such as `#1` or an MRC/MAP path. If `structure` is supplied, DAQplugin also colors the model.

Examples:

```chimerax
daqscore compute_grid #1 0.007 output ./daq_scores.npy
daqscore compute_grid #1 0.007 structure #2 metric aa_score
daqscore compute_grid #1 0.007 structure #2 monitor true metric aa_score half_window 9
daqscore compute_grid /path/to/map.mrc 0.5 output /path/to/output.npy
daqscore compute_grid #1 0.5 backend cpu
daqscore compute_grid #1 0.5 backend tensorrt gpu_id 1
```

Defaults from upstream docs: `stride 2`, `batch_size 0` (auto), `max_points 500000`, `metric aa_score`, `k 1`, `half_window 9`, `backend auto`, `gpu_id 0`.

### Compute PDB/model-position DAQ scores

```chimerax
daqscore compute_pdb mapInput structure #model [output npyPath] [batch_size N] [ckpt ckptPath] [metric metricName] [k N] [colormap cmap] [half_window N] [apply_color true|false] [save_model modelPath] [backend name] [gpu_id N]
```

Use for original-style DAQ scoring at heavy atom/model positions. Monitoring is not started by this command.

Examples:

```chimerax
daqscore compute_pdb #1 structure #2 metric aa_score
daqscore compute_pdb #1 structure #2 apply_color false
daqscore compute_pdb #1 structure #2 metric aa_score save_model scored_model.pdb
daqscore compute_pdb #1 structure #2 metric atom_score k 1 half_window 9 save_model output.cif
```

### Color a model from existing scores

```chimerax
daqcolor apply npyPath model [k N] [metric metricName] [atom_name atomName] [half_window N] [colormap cmap] [clamp_min value] [clamp_max value] [log_timing true|false] [knn_workers N]
```

Examples:

```chimerax
daqcolor apply ./daq_scores.npy #2 metric aa_score
daqcolor apply ./daq_scores.npy #2 metric atom_score atom_name CA clamp_min -1 clamp_max 1
daqcolor apply ./daq_scores.npy #2 metric ss_score half_window 9 log_timing true
save scored_model.cif #2
```

Notes:

- `atom_name` defaults to `CA`.
- Window averaging is within each chain by residue number; missing residue numbers are skipped.
- The colored/scored model stores displayed DAQ values in B-factors when saved.

### Live recoloring

```chimerax
daqcolor monitor model [npy_path npyPath] [k N] [metric metricName] [atom_name atomName] [half_window N] [colormap cmap] [clamp_min value] [clamp_max value] [on true|false] [interval seconds] [log_timing true|false] [knn_workers N]
```

Examples:

```chimerax
daqcolor monitor #2 npy_path ./daq_scores.npy metric aa_score
daqcolor monitor #2 npy_path ./daq_scores.npy metric aa_score interval 1.0
daqcolor monitor #2 on false
```

Use in interactive ChimeraX/ISOLDE workflows, not as the main value of a `--nogui` batch job.

### Show DAQ points

```chimerax
daqcolor points npyPath [radius value] [metric metricName] [colormap cmap] [clamp_min value] [clamp_max value]
daqcolor clear
```

Examples:

```chimerax
daqcolor points ./daq_scores.npy radius 0.4
daqcolor points ./daq_scores.npy metric aa_conf radius 0.3
daqcolor points ./daq_scores.npy metric aa_top:ALA radius 0.3
daqcolor clear
```

For point display, supported metrics include `aa_conf` and `aa_top:<AA>`.

### Sequence-shift arrows and optional ISOLDE restraints

```chimerax
daq arrowwin structure npy_path [chain chainId] [nwin N] [kshift N] [minmove value] [radius value] [min_improvement value] [vmax_color value] [vmax_radius value] [max_radius_scale value] [min_radius_scale value] [group_name name] [apply_isolde_restraints true|false] [spring_constant value]
daq clearrestraints structure
```

Examples:

```chimerax
daq arrowwin #2 ./daq_scores.npy nwin 5 kshift 5 min_improvement 0.5
daq arrowwin #2 ./daq_scores.npy chain A apply_isolde_restraints true spring_constant 1500
daq clearrestraints #2
```

If residues are selected, `daq arrowwin` processes the selected residues; otherwise it processes the model, optionally restricted by `chain`.

## Metrics

| Metric | Use |
|---|---|
| `aa_score` | DAQ(AA), amino-acid assignment quality. Start here. |
| `atom_score` | DAQ(CA), atom/CA likelihood support. |
| `ss_score` | DAQ(SS), secondary-structure agreement. |
| `aa_conf:<AA>` | Confidence for a specific residue type, for example `aa_conf:ALA`. |
| `aa_top:<AA>` | Point-display metric for top amino-acid confidence. |

## Backends

Backend names: `auto`, `tensorrt`, `cuda`, `directml`, `mlx`, `mlx-cpu`, `cpu`.

Use `backend auto` first. Force `backend cpu` when GPU setup is suspect or reproducibility matters. On Linux NVIDIA, `gpu_id N` selects the device for TensorRT/CUDA. Lower `batch_size` to reduce memory pressure. Increase `stride` or lower `max_points` to reduce grid workload.

## Standalone B-Factor Writer

The DAQplugin repository includes `cli/daq_write_bfactor.py` for writing scores from a DAQ `.npy` into a PDB/mmCIF B-factor field outside ChimeraX:

```bash
python cli/daq_write_bfactor.py \
  -i model.cif \
  -p points_AA_ATOM_SS_swap.npy \
  -m aa_score \
  -o model.daq.b.cif
```

Prefer ChimeraX `daqcolor apply` + `save` when DAQplugin is installed in ChimeraX; use the CLI when working from an upstream checkout or when a non-interactive Python path is easier.
