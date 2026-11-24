# 10 — Decision trees

Short answers with pointers. Anything marked *(ours)* is this skill's practical advice, not the authors'.

## 1. Is CryoCodex the right tool?

```text
Want: enhanced map + local-quality maps + molecular mask from ONE cryo-EM map?
├─ Map is crystallographic / non-90° cell ............ no (refused: "Input grid is not orthogonal")
├─ Resolution far outside 3–8 Å ........................ trained/tested on 3–8 Å; Q-score gains limited beyond ~5 Å → expect less, say so
├─ Subtomogram average or helical map .................. under-represented in training, not evaluated separately → possible, unvalidated
├─ Need local RESOLUTION in Å ........................... no: scores are predicted local SSIM (use a local-resolution tool)
├─ Need a soft refinement / FSC mask ................... the mask is a hard 4-Å-envelope prediction; resample + soften in your mask tool (ours)
├─ Want it compared with DeepEMhancer / LocScale ....... not benchmarked; don't rank
└─ Otherwise ............................................ yes → probe the host (SKILL.md)
```

## 2. Can this machine run it?

```text
probe verdict
├─ BLOCKED (macOS / Windows / no NVIDIA GPU visible / no executable conda)
│    → explain, inspect headers, draft commands labelled "template — not run"; never the Colab route for private maps
├─ NOT_INSTALLED → README install (02 §2) or a shared install with a site launcher (02 §2b), one confirmation per step
├─ PARTIAL       → fix the named gap (weights with confirmation, chmod +x, git checkout v1.0.0, --env-check,
│                  PYTHONNOUSERSITE=1 when the probe shows user-site packages)
└─ READY_TO_VALIDATE → validation_runbook.md once on this host → site config state VALIDATED → jobs with per-job confirmation
```
A login node is not the GPU node: probe where the job will run. A site that already has a shared install: use its
launcher (probe with `--env-prefix --launcher`), do not build a second env.

## 3. Which map to feed

No author guidance on sharpened vs unsharpened or masked vs unmasked input (G12). The benchmark used deposited EMDB
**primary** maps; half maps were processed one at a time. *(ours)* Start with the map you would otherwise interpret
(often the sharpened full map); if results look odd, try the unsharpened map and compare; never feed a map that was
already processed by another enhancement network without saying so.

## 4. Mode

```text
default (fast) ............ most maps; crops background → fewer windows, faster
├─ molecule elongated / off-centre / parts near box corners / several separate bodies → --normal True
├─ user at an interactive terminal and wants to see the crop → --crop_check True (fast mode only, never batch)
└─ host RAM tight → stay in fast mode; check the window count first (inspect_map.py)
```

## 5. Output grid

```text
Need …
├─ quick look / colouring in ChimeraX .............. default (1 Å grid, crop, placed by NSTART)
├─ same box and voxel size as the input ............. --keep_size True --reverse_interpolation True (scores may exceed 1)
├─ whole box at 1 Å ................................. --keep_size True (fast) or --normal True
├─ input already 1.0 Å ............................... --keep_size True alone gives the input box (reverse is skipped)
└─ very small map (1 Å box axis < 48) ............... no --keep_size (expected to fail); outputs are padded to 48
```

## 6. Batch size (`-b`, default 9)

```text
GPU memory free (nvidia-smi)
├─ ≥ 7,400 MiB → 9 (verified: 7,328 MiB peak on an 8 GB card for a 150³ and a 432³ map; 7,164 MiB on an 11 GB card)
├─ less      → ≈ 0.67 GiB + 0.72 GiB per window: ~4 on 4 GiB, 1 on 2 GiB (-b 1 = 1,420 MiB, verified)
├─ ≥ 16 GiB  → larger -b is possible but untested for speed; -b 18 needs > 7.6 GiB (OOM on an 8 GB card, verified)
└─ OOM      → halve and rerun; check for other processes on the GPU (and, on unfenced nodes, that you are on your GPU)
```
The network normalises per sample only (InstanceNorm / LayerNorm / GroupNorm; no BatchNorm), so `-b` changes speed and
memory, not results: `-b 1` vs `-b 9` differed by ≤ 0.012 on the enhanced map and in one mask voxel; the same `-b`
repeated on the same GPU model is bit-identical, and two GPU models (RTX 2070 SUPER vs 2080 Ti) differed at the same
float level (verified).

## 7. Stride (`-s`, default 12)

Keep 12 (paper and code default). Larger strides (≤ 44) cut windows and RAM roughly by (s/12)³ but less overlap; the
effect on quality is undocumented. > 44 leaves gaps (`-s 46`: all-zero planes inside the molecule, verified): refused.
Smaller than 12 costs more and is untested.

## 8. Where to run

```text
workstation with an NVIDIA GPU ..... direct, in a terminal (log with tee; PYTHONNOUSERSITE=1)
cluster ............................ Slurm template (one GPU, weights pre-placed, -g "${CUDA_VISIBLE_DEVICES:-0}",
                                     --launcher for a shared install; verified end to end)
login node / laptop / Mac .......... only -h, header inspection, command drafting
Google Colab ........................ not supported; privacy warning (map is uploaded)
```

## 9. Stop and ask the user when

- the weights are missing (471 MB download), or their size/sha256 differs from the record;
- the safe `weights_only=True` load fails;
- the clone is not at `a35e73a`, or upstream has moved (maintenance.md);
- the output directory is not new, or the host-RAM estimate exceeds what the node has;
- the request needs a flag not in [03 §3](03_cli_reference.md), the Scipion route, or the Colab notebook;
- a result contradicts this skill's expectations (record it in `lessons.md` after confirming).
