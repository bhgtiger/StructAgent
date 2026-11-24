# 05 — Core workflows, sizing, Slurm, provenance

Every command below is a **template — not run** until a host is VALIDATED (SKILL.md). Paths are placeholders:
`$CC` = the CryoCodex clone (holds `predict.sh`), maps and output directories absolute. Generate real commands with
`scripts/build_cryocodex_command.py`, which refuses the traps in [03 §4](03_cli_reference.md).

## 0. Before any job (every time)

1. State: fresh probe on the node that will run it (`scripts/cryocodex_env_probe.py --home $CC --env-check`).
2. Inputs: `python3 scripts/inspect_map.py /abs/map.mrc` — name gate, orthogonal cell, 1 Å box, window count, host-RAM
   estimate, expected output boxes.
3. Weights: present and 470,938,660 B? If not, the run starts with a 471 MB download — ask first ([02 §4](02_config_session_and_environment.md)).
4. Output: a **new** `-o` directory per run (same-name outputs are overwritten without warning).
5. Show the user [../templates/run_plan.md](../templates/run_plan.md) filled in, and get a yes for this one job.
6. Run with a log: `… 2>&1 | tee /abs/out/run.log` (CryoCodex writes no log of its own).
7. After: `python3 scripts/check_outputs.py /abs/out --input /abs/map.mrc [matching flags] --log /abs/out/run.log`.

## 1. Default run (fast mode, outputs on the 1 Å grid)

```bash
# template — not run
$CC/predict.sh -i /abs/map.mrc -o /abs/out_cc_run1 2>&1 | tee /abs/out_cc_run1.log
python3 scripts/check_outputs.py /abs/out_cc_run1 --input /abs/map.mrc --log /abs/out_cc_run1.log
```
Outputs: four float32 maps at 1.0 Å, cropped to the molecule, placed by NSTART ([04 §4–5](04_data_model_and_formats.md)).
Good for looking at the enhanced map and the score colouring in ChimeraX ([06 §1](06_interoperability.md)).

## 2. Outputs on the input grid (overlay, comparison, use in other programs)

```bash
# template — not run
$CC/predict.sh -i /abs/map.mrc -o /abs/out_cc_inputgrid --keep_size True --reverse_interpolation True
python3 scripts/check_outputs.py /abs/out_cc_inputgrid --input /abs/map.mrc --keep-size --reverse-interpolation
```
- `--keep_size True` alone gives the **1 Å regridded box** (156³ for a 150³ map at 1.043 Å), not the input box; adding
  `--reverse_interpolation True` resamples back to the input voxel size (150³ expected, derived; runbook R12).
- After the reverse resampling the score maps can exceed 1 (no upper clamp); the mask stays binary.
- For a 1.0 Å input `--keep_size True` alone already restores the input box (reverse interpolation is skipped).

## 3. Normal mode (no crop)

```bash
# template — not run
$CC/predict.sh -i /abs/map.mrc -o /abs/out_cc_normal --normal True
```
Use when the auto-crop might clip density (elongated or off-centre molecules, parts near box corners — G33), or to
compare with a fast-mode run. Costs: every window of the whole box (see the normal-mode window count and RAM estimate
from `inspect_map.py`); slower ("Slower than Fast mode", README). `--keep_size` and `--crop_check` do not apply.

## 4. Batch / Slurm (one GPU)

```bash
# template — not run. Writes a filled job file; read it, bash -n it, show the run plan, ask, then sbatch.
python3 scripts/build_cryocodex_command.py -i /abs/map.mrc -o /abs/out_cc_job1 --home /abs/CryoCodex \
    --sbatch /abs/jobs/cc_job1.sbatch --account ACCT --partition GPU_PART --cpus 8 --mem 32G --time 01:00:00 \
    --site-env "source /abs/miniconda3/etc/profile.d/conda.sh"
```
The template ([../templates/slurm_cryocodex.sbatch.template](../templates/slurm_cryocodex.sbatch.template)):
- requests **one** GPU and passes `-g "${CUDA_VISIBLE_DEVICES:-0}"`, because CryoCodex overwrites
  `CUDA_VISIBLE_DEVICES` with `-g` (default `"0"`) and computes on the first visible device (derived from
  `predict.py:82`, `:194`; runbook R16c decides it on a real site);
- refuses to start without `model_state_dicts/CryoCodex.pth` (compute nodes are often offline; `predict.sh` would try
  to download first), with a non-empty output directory, with `--crop_check True`, or with more than one visible GPU;
- runs `inspect_map.py` as a gate, samples GPU memory, uses `/usr/bin/time -v` for peak host RAM, feeds `/dev/null` to
  stdin, and ends with `check_outputs.py` (exit status 0 from `predict.sh` alone does not prove maps were written).

**Sizing (derived — confirm on the first real job):**
- `--mem`: the normal-mode estimate from `inspect_map.py` is the upper bound; fast mode needs less (crop-dependent).
  Add headroom for Python, CUDA and conda (a few GB).
- GPU: the only data point is batch 9 within 8 GB on an A800 (preprint). On smaller cards lower `-b`
  (README: "For GPUs with limited memory, reduce the batch size using `-b`"). The Colab notebook's own heuristic,
  `max(1, min(cap, int(9 × free_GiB × 0.9 / 8)))` with cap 9 on cards ≤ 8 GiB and 64 above, is the notebook's, not
  the CLI's — the CLI has no automatic batch size and does not retry on OOM.
- Walltime: preprint mean 74.87 s per map (126 maps, A800, 8 GB cap); 17.87 s for EMD-10387. Add conda start-up, numba
  JIT compilation and the resampling; ask for generous time on the first job and record the real wall time.

## 5. Interactive crop review (terminal only)

```bash
# template — not run. Only when the user sits at an interactive terminal on the GPU node.
$CC/predict.sh -i /abs/map.mrc -o /abs/out_cc_cropcheck --crop_check True
```
After preprocessing it writes `round_1_check/*.png` in `-o`, prints the current bounds and waits at
`[Enter] Continue without changes  |  [e] Edit bounds: `. Enter (or `c`) continues; `e` asks for new `min,max` per axis
(voxel indices on the 1 Å grid) and renders a new round. No timeout. Whether input reaches the prompt through
`conda run --no-capture-output` is unverified (runbook R15). Never in Slurm, `nohup`, cron, pipes or scripts.

## 6. Half maps

CryoCodex takes one map. The preprint processed each half map **separately** (pp l.477-480). Two runs, two directories:
```bash
# template — not run
$CC/predict.sh -i /abs/half1.mrc -o /abs/out_cc_half1 -n half1
$CC/predict.sh -i /abs/half2.mrc -o /abs/out_cc_half2 -n half2
```
The same network processed both halves, so they now share structure: an FSC between processed halves is **not** a
gold-standard resolution estimate (the preprint itself does not read those crossings as physical resolution,
pp l.504-508).

## 7. Several maps

One map per call. Loop sequentially inside one GPU job, a fresh `-o` and a log per map; check each with
`check_outputs.py`. Do not start several CryoCodex processes on one GPU without measuring memory first.

## 8. Provenance (record for every run)

Host and node, GPU model and driver, conda env (`pip freeze` once per env), clone commit (`git rev-parse HEAD`),
weights size + sha256 (probe `--hash`, once per host), the exact command, input path + sha256 + header summary
(`inspect_map.py`), output directory, wall time, peak GPU memory and host RSS, and the `check_outputs.py` verdict.
Cite CryoCodex as in [01 §2](01_source_map.md).

## 9. What to show the user before a job

[../templates/run_plan.md](../templates/run_plan.md): host and state, the input summary, the exact command, expected
outputs and grid, resources, the evidence level of that mode on this host, caveats, and the approval question. One job
per approval.
