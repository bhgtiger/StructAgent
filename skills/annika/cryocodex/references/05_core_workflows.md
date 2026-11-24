# 05 — Core workflows, sizing, Slurm, provenance

The commands of §1–§5 ran on the validation host on 2026-11-24 with the EMD-10387 fixture (runbook §0); §6–§7 (half
maps, several maps) were not run. On any other host every command is a **template — not run here** until that host is
VALIDATED (SKILL.md). Paths are placeholders: `$CC` = the
CryoCodex clone (holds `predict.sh`) — or use a site launcher with the same options (02 §2b) — maps and output
directories absolute. Generate real commands with `scripts/build_cryocodex_command.py`, which refuses the traps in
[03 §4](03_cli_reference.md). Export `PYTHONNOUSERSITE=1` before `predict.sh` (02 §2).

## 0. Before any job (every time)

1. State: fresh probe on the node that will run it (`scripts/cryocodex_env_probe.py --home $CC --env-check`).
2. Inputs: `python3 scripts/inspect_map.py /abs/map.mrc` — name gate, orthogonal cell, 1 Å box, window count, host-RAM
   estimate, expected output boxes.
3. Weights: present and 470,938,660 B? If not, the run starts with a 471 MB download — ask first ([02 §4](02_config_session_and_environment.md)).
4. Output: a **new** `-o` directory per run (same-name outputs are overwritten without warning).
5. Show the user [../templates/run_plan.md](../templates/run_plan.md) filled in, and get a yes for this one job.
6. Run with a log: `… 2>&1 | tee /abs/out.log` (CryoCodex writes no log of its own). Keep the log outside `-o` or
   name it so it does not collide with the outputs.
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
  `--reverse_interpolation True` resamples back to the input voxel size (150³ at 1.043 Å, NSTART 0 — verified; mean
  input density 0.0100 inside the predicted mask vs −0.0002 outside, i.e. the outputs overlay the input).
- After the reverse resampling the score maps exceed 1 in places (no upper clamp; max 1.14 observed); the mask stays binary.
- For a 1.0 Å input `--keep_size True` alone already restores the input box (reverse interpolation is skipped).

## 3. Normal mode (no crop)

```bash
# template — not run
$CC/predict.sh -i /abs/map.mrc -o /abs/out_cc_normal --normal True
```
Use when the auto-crop might clip density (elongated or off-centre molecules, parts near box corners — G33), or to
compare with a fast-mode run. Costs: every window of the whole box (see the normal-mode window count and RAM estimate
from `inspect_map.py`); EMD-10387: 1000 windows, 3:48 vs 0:58 in fast mode, 3.9 vs 1.8 GB host RAM (verified, 8 GB card).
Results differ slightly from fast mode (Pearson 0.996). `--keep_size` and `--crop_check` do not apply.

## 4. Batch / Slurm (one GPU)

```bash
# template — not run here. Writes a filled job file; read it, bash -n it, show the run plan, ask, then sbatch.
python3 scripts/build_cryocodex_command.py -i /abs/map.mrc -o /abs/out_cc_job1 --home /abs/CryoCodex \
    --sbatch /abs/jobs/cc_job1.sbatch --account ACCT --partition GPU_PART --cpus 8 --mem 32G --time 01:00:00 \
    --site-env "source /abs/miniconda3/etc/profile.d/conda.sh"
# site requesting GPUs with --gres and no account; shared install with a site launcher:
python3 scripts/build_cryocodex_command.py -i /abs/map.mrc -o /abs/out_cc_job2 --home /abs/CryoCodex \
    --launcher /abs/cryocodex.sh --sbatch /abs/jobs/cc_job2.sbatch --partition GPU_PART --gres gpu:1 --cpus 4 --time 00:30:00
```
Two filled jobs ran end to end on the validation cluster (rc 0, `OUTPUT CHECK: OK`, each job on its own GPU): the
`predict.sh` route and the `--launcher` route, both with `--gres gpu:1` and no account/mem/site-env (those options were
not exercised there).
The template ([../templates/slurm_cryocodex.sbatch.template](../templates/slurm_cryocodex.sbatch.template)):
- requests **one** GPU and passes `-g "${CUDA_VISIBLE_DEVICES:-0}"`, because CryoCodex overwrites
  `CUDA_VISIBLE_DEVICES` with `-g` (default `"0"`) and computes on the first visible device (`predict.py:82`, `:194`;
  verified on a node without per-job GPU fencing: without it a job given GPU 1 ran on GPU 0);
- exports `PYTHONNOUSERSITE=1`; uses `RUNNER` = `predict.sh` (needs conda) or a site launcher (no conda);
- refuses to start without `model_state_dicts/CryoCodex.pth` (compute nodes are often offline; `predict.sh` would try
  to download first), with a non-empty output directory, with `--crop_check True`, or with more than one visible GPU;
- runs `inspect_map.py` as a gate, samples the job's own GPU memory (`nvidia-smi -i $CUDA_VISIBLE_DEVICES`: on
  unfenced nodes nvidia-smi lists every card), uses `/usr/bin/time -v` for peak host RAM, feeds `/dev/null` to stdin,
  and ends with `check_outputs.py` (exit status 0 alone does not prove maps were written: a non-orthogonal input exits
  0 without outputs).

**Measured on the validation host (2026-11-24, `-b 9`, device-level GPU memory, max host RSS, wall time incl. conda
start-up and numba JIT):**

| Map | Mode | GPU | GPU mem | Host RAM | Wall |
|---|---|---|---|---|---|
| EMD-10387 150³ @ 1.043 Å (175 windows) | fast | RTX 2070 SUPER 8 GB | 7,328 MiB | 1.8 GB | 0:50–1:02 |
| same | fast | RTX 2080 Ti 11 GB | 7,164 MiB | 1.8 GB | 0:36–0:45 |
| same | normal (1000 windows) | RTX 2070 SUPER | 7,328 MiB | 3.9 GB | 3:48 |
| same, `-b 1` | fast | RTX 2070 SUPER | 1,420 MiB | 1.8 GB | 0:46 |
| same, `-b 18` | fast | RTX 2070 SUPER | OOM | — | fails |
| EMD-14763 432³ @ 0.86 Å (693 windows) | fast | RTX 2070 SUPER | 7,328 MiB | 4.1 GB | 3:05 |
| a 192³ map @ 1.31 Å (site launcher) | fast | RTX 4090 24 GB | — | 3.3 GB | 0:41 |

(Preprint: 17.9 s and 89.7 s for these two maps on an A800 capped at 8 GB.) `-b` changes speed and memory but not the
result beyond float noise (`-b 1` vs `-b 9`: max |Δ| 0.012 on the enhanced map, one mask voxel); the same `-b`
repeated is bit-identical.

**Sizing for other maps (derived):**
- `--mem`: `inspect_map.py` prints ≈ 1.4 GB + 2.2 MB per window + ~20 B per 1 Å voxel for normal mode (matched the
  measured RSS within ~5 %); fast mode needs less (crop-dependent). Add ~25 % headroom.
- GPU: `-b 9` needs ~7,330 MiB free; with less, lower `-b` (≈ 0.67 GiB fixed + 0.72 GiB per window in a batch, from
  the `-b` 1 and 9 measurements — rough) (README: "For GPUs with limited memory, reduce the batch size using `-b`"). The Colab notebook's own heuristic,
  `max(1, min(cap, int(9 × free_GiB × 0.9 / 8)))` with cap 9 on cards ≤ 8 GiB and 64 above, is the notebook's, not
  the CLI's — the CLI has no automatic batch size and does not retry on OOM.
- Walltime: see the table; fast mode scales with the crop's window count (~4.7 windows/s on a 2070 SUPER at `-b 9`),
  normal mode with the whole box. Ask for generous time on the first job and record the real wall time.

## 5. Interactive crop review (terminal only)

```bash
# template — not run. Only when the user sits at an interactive terminal on the GPU node.
$CC/predict.sh -i /abs/map.mrc -o /abs/out_cc_cropcheck --crop_check True
```
After preprocessing it writes `round_1_check/*.png` in `-o`, prints the current bounds and waits at
`[Enter] Continue without changes  |  [e] Edit bounds: `. Enter (or `c`) continues; `e` asks for new `min,max` per axis
(voxel indices on the 1 Å grid) and renders a new round. No timeout. Input does reach the prompt through
`conda run --no-capture-output` (verified at a pseudo-terminal: Enter → `No changes made. Continuing with the current
crop bounds.`, the PNG folder removed, four maps written). Never in Slurm, `nohup`, cron, pipes or scripts: closed
stdin → `RuntimeError`, silent open stdin → waits forever (both verified).

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
