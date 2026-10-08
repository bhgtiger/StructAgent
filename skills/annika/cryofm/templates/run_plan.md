# Run plan (show this before any GPU job; one job per approval)

**Host / node**: <hostname, partition, card> — probe verdict `<X>` on <date>, site config state `<VALIDATED|PROBED>`.

**Goal**: <denoise two halves | anisotropy correction | non-uniform | EMhancer-style | EMReady-style | style + data term>

**Inputs** (`inspect_map.py` output):
| file | box | apix | axis order | origin / NSTART | note |
|---|---|---|---|---|---|
| half1 | | | | | |
| half2 | | | | | |
Gates: extension OK · even cubic/padded · S = <n> ≥ 64 · halves identical grid · patches <n> → batches <n> at batch <b>.

**Command** (exact, absolute paths, NEW output dir):
```bash
<command>
```
Evidence level of this exact mode on this host: <validated (job id) | untested here>.

**Resources**: 1 GPU `<card>`, `--cpus-per-task <n> --mem <n>G`, walltime <n> (≈ batches × ~1 min × halves + 2 min).
Expected peak GPU memory ≈ <n> GB (docs table / measured). Account <acct>, budget left <n>.

**Outputs**: `<-o>/<stem>_external_reconstruct.mrc` ×<n> (+ `avg_external_reconstruct.mrc`), float32, input grid,
origin 0 → restore needed: <yes/no>.

**Known caveats for this run**: <3 Å band limit | outputs not independent halves | tag/CFG pairing | untested op | …>

**After**: `check_cfm_output.py`, `restore_origin.py` (if needed), visual check at a chosen contour, map-model
FSC/CC vs <model>; ledger entry Job_NNN.

**Approval requested**: submit `<job file>` now? (yes/no)
