# CryoCodex run plan (show this before any GPU job; one job per approval)

**Host / node**: <hostname, node type, GPU model + free memory, driver> — probe verdict `<READY_TO_VALIDATE|PARTIAL|…>`
on <date>; site config state `<VALIDATED|PROBED>` (VALIDATED needs the runbook's fixture run on this host).

**Goal**: <enhanced map + quality maps + mask for …> · **why CryoCodex fits** (references/10 §1): <…>

**Input** (`scripts/inspect_map.py` output):
| file | box (XYZ) | voxel (Å) | origin used (Å) | 1 Å box | name gate | 90° cell |
|---|---|---|---|---|---|---|
| <map> | | | | | PASS | PASS |
Training-set check (references/08 §2): <EMDB id in train.csv/valid.csv? yes/no/not an EMDB entry>.

**Command** (exact; absolute paths; NEW output directory):
```bash
<command from scripts/build_cryocodex_command.py>  2>&1 | tee <OUT>/../<name>.log
```
Mode: <fast (default) | normal> · output grid: <1 Å, cropped | 1 Å regridded box | input voxel size> ·
evidence level on this host: <validated by the fixture run (date) | this option combination untested here>.

**Weights**: present, 470,938,660 B, sha256 <recorded / not yet> — or: **the run will download 471 MB first** (ask).

**Resources**: 1 GPU; batch `-b <n>` (9 fitted 8 GB on an A800 in the preprint; unmeasured here); windows <n> (normal-mode
upper bound) → host RAM ≈ <n> GB (derived); walltime <…> (preprint mean 75 s/map on an A800 + start-up). Slurm:
account <…>, partition <…>, `--mem <…>`.

**Outputs**: `<OUT>/<n>.mrc`, `<n>_out_score.mrc`, `<n>_in_mask.mrc`, `<n>_in_score.mrc`, float32, <grid>, ORIGIN 0 with
placement in NSTART. Expected box: <… (derived)>.

**Caveats for this run**: <scores are predicted local SSIM, not resolution | scores may exceed 1 after reverse
interpolation | fast-mode crop may clip corners | --keep_size alone ≠ input box | half maps processed separately are
not independent | untested option | …>

**After**: `python3 scripts/check_outputs.py <OUT> --input <map> [flags] --log <log>`; look at the enhanced map next to
the input at matched contours; colour by `out_score` (references/06 §1); record provenance (references/05 §8).

**Approval requested**: run / submit `<command or job file>` now? (yes/no)
