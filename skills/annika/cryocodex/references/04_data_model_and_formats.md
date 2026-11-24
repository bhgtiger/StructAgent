# 04 — Data model: what goes in, what happens to it, what comes out

Everything here is read from the code at `a35e73a` (SOURCED) or computed from it (DERIVED); rows marked **verified**
were observed on the validation host on 2026-11-24 with EMD-10387 (150³ at 1.043 Å), a 40³ sub-box of it, a
non-orthogonal copy and EMD-14763 (432³ at 0.86 Å). `scripts/inspect_map.py` applies §1–§3 to a header,
`scripts/check_outputs.py` checks §4–§6 (its expectations matched every live run).
Preprint line numbers (`pp l.N`) refer to the evidence pack's text extract (see [01 §3](01_source_map.md)).

## 1. Input: one map per run

| Aspect | Rule (code) | Consequence |
|---|---|---|
| Number of maps | one `-i`; no half-map pair, mask, model or resolution input (`predict.py:161-185`) | half maps are processed one at a time, as in the preprint (pp l.477-480) |
| File name | path string must end in `map` or `mrc`, **case-sensitive** (`grid_utils.py:215`; verified for `.ccp4`, `.MRC`, `.map.gz`) | `.ccp4`, `.MRC`, `.MAP`, `.mrcs`, `.mrc.gz`, `.map.gz` → `RuntimeError: File <path> is not a cryo-em density map file format.` Decompress (`gzip -dc in.map.gz > in.map`); a `.ccp4` file is the same format: copy or symlink it to a `.mrc` name |
| Reader | `mrcfile` 1.5.4, `mrc.open(path, mode='r')` (non-permissive; `grid_utils.py:154`) | a missing `MAP ` id, an unknown mode or a truncated file stops the run with an mrcfile error |
| Cell angles | all three CELLB angles must be exactly 90.0 (`grid_utils.py:160-167`) | else `# Input grid is not orthogonal. EXIT.` and a bare `exit()` — **exit status 0, no outputs** (verified). Always check outputs, not only the exit code |
| Axis order | any permutation of MAPC/MAPR/MAPS; data transposed to (z, y, x) (`grid_utils.py:169-175`) | no action needed; outputs are written 1/2/3 |
| Voxel size | per axis from the header (`cella/mx` …); anisotropic allowed (`grid_utils.py:156`) | each axis is resampled to 1.0 Å separately |
| Origin | `ORIGIN + (NXSTART, NYSTART, NZSTART) × voxel` — **both summed** (`grid_utils.py:157-158`, `:178-179`) | headers with both fields non-zero are rare; other programs may use only one of them (contradiction C10, untested) |
| Density | 99.999th percentile of the **positive** voxels (`grid_utils.py:224`) | a map without positive voxels fails (NumPy error; wording unverified) |
| Box size | any; after regridding, axes shorter than 48 are zero-padded at the far end (`data_processor.py:59-61`) | very small maps give ≥ 48³ outputs; `--keep_size True` then fails (§4) |
| Resolution | not checked | the network was trained and tested on 3–8 Å maps (pp l.983-984, 188-189) |

**Which map to feed** is not stated anywhere (gap G12): the benchmark used the deposited EMDB **primary** maps
(Supplementary Data 1 title), and the preprint processed half maps "independently". Whether a sharpened or unsharpened,
masked or unmasked map works better is unknown — say so; do not invent a rule.

## 2. Preprocessing (in code order)

1. **Read** the map, transpose to (z, y, x), compute the origin as in §1.
2. **Resample to 1.0 Å** with a cubic-convolution kernel (Keys, a = −0.5, from EMReady2; `grid_utils.py:15-75`), new
   extent `floor(voxel × (n − 1) / 1.0) + 1` per axis (`grid_utils.py:39-41`). Skipped only when all three voxel sizes are
   exactly 1.0 **and** the origin lies on the 1 Å lattice; a fractional origin triggers a second pass that shifts the map
   by the sub-voxel remainder (`grid_utils.py:181-195`, `:217-222`). The preprint says "trilinear" (pp l.1048-1049) —
   code wins for behaviour; whether training used trilinear is unknown (C16).
   *Example (verified):* EMD-10387, 150³ at 1.043 Å → 156³ at 1.0 Å; EMD-14763, 432³ at 0.86 Å → 371³ (the log prints
   the header voxel in float32, e.g. `[0.8600001 0.8600001 0.8600001]`).
3. **Normalise**: divide by the 99.999th percentile of positive voxels, clip to [0, 1] (negatives → 0)
   (`data_processor.py:13-17`); windows are later multiplied by 100 (`data_processor.py:65`).
4. **Auto-mask (both modes; used for cropping in fast mode)** — model-angelo's auto-mask on a copy padded to an even cube:
   15 Å low-pass, everything outside the inscribed sphere set to 0, threshold at the 97th percentile of the positive
   low-passed voxels, dilated by `max(5, round(0.01 × edge) + 1)` voxels plus a soft edge of the same width
   (`grid_utils.py:302-310`, `data_processor.py:19-26`).
5. **Fast mode only (default)**: crop to the bounding box of that mask ± 5 voxels, clipped to the box
   (`data_processor.py:33-57`). The crop is data-dependent. Because density outside the inscribed sphere is zeroed
   before thresholding, molecule parts near box corners can be cropped away (G33): review with `--crop_check True` (an
   interactive terminal only) or use `--normal True`.
6. **Tile**: axes < 48 padded to 48; window starts `range(0, n − 48, s) + [n − 48]` per axis (`grid_utils.py:344-347`);
   all windows are cut at once and held in (pinned) host memory together with a 4-channel output array —
   about **2.2 MB per window** (`predict.py:88-92`; derived). Batches of `-b` windows run on `cuda:0`. The progress bar
   counts windows: EMD-10387 175 (fast) / 1000 (normal), EMD-14763 693 (fast) — verified.
7. **Network**: one MMVQ-UNet pass per window with four heads — enhanced density (linear), input-map score and
   enhanced-map score (`tanh`), mask (`sigmoid`) (`VQUnet.py:319-328`).
8. **Blend**: each window contributes only its inner `[i + 2, i + 46)` with a Gaussian weight (σ = 8)
   (`grid_utils.py:371-395`). Consequences (verified): the outermost **2 voxels** of every output are 0; a stride
   **> 44** leaves interior voxels that no window covers (written as 0) — with `-s 46` on the 156³ box the planes
   46, 47, 92 and 93 were all zero on every axis (20,023 zero-score voxels inside the mask vs 51 at `-s 12`). Keep `-s`
   in 1–44.
9. **Post-process** (`predict.py:105-147`):
   - mask = `(mask ≥ 0.5)` → binary 0/1;
   - soft mask = binary mask grown 15 voxels (15 Å on the 1 Å grid) with a cosine fall-off 1 → 0; **only the enhanced
     map** is multiplied by it (the code comment says "every output"; the code does not fade the scores — C19);
   - `--keep_size True`: paste all four into the uncropped 1 Å canvas, background 0 (`predict.py:116-125`);
   - `--reverse_interpolation True`: inverse cubic resampling to the input voxel size, extent
     `ceil(1.0 × (n − 1) / voxel) + 1` (`grid_utils.py:79-81`), mask re-binarised at 0.5; skipped if the input is
     already 1.0 Å within 1e-4 (`predict.py:126-144`);
   - scores clipped at 0 **after** any resampling; no upper clamp (`predict.py:146-147`).
10. **Write** four files with `mrcfile.new(..., overwrite=True)` (§5).

## 3. Host and GPU resources (derived)

| Quantity | Rule | Where |
|---|---|---|
| Windows | product over axes of `len(range(0, n − 48, s)) + 1` (after dedup), n = padded box | `scripts/inspect_map.py` prints it for normal mode |
| Host RAM | ≈ 1.4 GB + windows × 2.2 MB + ~20 B per voxel of the 1 Å grid (fits three measured runs within ~5 %) | 156³ normal: 1000 windows → 3.7 GB (3.9 GB measured); a 432³ map at 0.86 Å regrids to 371³ → 21 952 windows ≈ 51 GB in normal mode (derived) |
| GPU memory | per batch of `-b` windows: `-b 9` → 7,328 MiB, `-b 1` → 1,420 MiB, `-b 18` OOM on 8 GB (verified; the preprint: batch 9 within an 8 GB cap on an A800) | lower `-b` on smaller cards |
| Fast mode | crop first, so fewer windows (data-dependent) | always ≤ the normal-mode numbers |

## 4. Output grid by option (code; EMD-10387 column verified except where marked)

| Options | Grid | Voxel | Box | Placement (NSTART) | EMD-10387 (150³ @ 1.043 Å) |
|---|---|---|---|---|---|
| default (fast) | crop of the 1 Å grid | 1.0 Å | crop, each axis 48 … 1 Å box | input origin (Å, rounded) + crop start | **93×86×113** (XYZ), NSTART (29, 35, 34) — the same crop as the authors' published result |
| `--keep_size True` | 1 Å regridded box | 1.0 Å | = 1 Å box (equals the input box only for 1.0 Å inputs) | input origin (Å) | **156³**, NSTART 0 |
| `--keep_size True --reverse_interpolation True` | input voxel size | input | `ceil((n₁ − 1)/voxel) + 1` ≈ input box | input origin / voxel | **150³ at 1.043 Å**, NSTART 0 |
| `--normal True` | full 1 Å box | 1.0 Å | 1 Å box, axes < 48 padded | input origin (Å) | **156³**, NSTART 0 |
| `--normal True --reverse_interpolation True` | input voxel size | input | from the (padded) 1 Å box | input origin / voxel | 150³ (derived) |
| fast + `--reverse_interpolation True` (no keep) | input voxel size | input | from the crop | crop start / voxel | crop-dependent (derived) |

EMD-14763 (432³ at 0.86 Å), default: 141×118×163 at 1.0 Å, NSTART (171, 99, 87) (verified).
A 40³ map at 1.043 Å (1 Å box 41³), default: 48³ outputs (padded), NSTART 0; with `--keep_size True`:
`ValueError: could not broadcast input array from shape (48,48,48) into shape (41,41,41)`, exit 1 (both verified).
The command builder refuses that combination.

Fast and normal mode do not give identical maps (the window grid starts differently): on EMD-10387 the enhanced maps
correlate at Pearson 0.996 over the crop (verified). Compare runs only within one mode.

## 5. The four outputs

Written to `-o` as `<n>.mrc`, `<n>_out_score.mrc`, `<n>_in_mask.mrc`, `<n>_in_score.mrc` (`-n`, default `cryocodex`;
`predict.py:149-152`). All float32 (MRC mode 2), MAPC/MAPR/MAPS = 1/2/3, header ORIGIN = 0, placement in
NXSTART/NYSTART/NZSTART = `round(origin / voxel)` (`grid_utils.py:314-331`). Same-name files are overwritten silently.
No log file is written (console only) — redirect it yourself.

| File | What it is | Values | Use and limits |
|---|---|---|---|
| `<n>.mrc` | enhanced map | unbounded float32 (EMD-10387: −0.66 … 21.2, 53 % exact zeros in the crop; EMD-14763: max 28.8 — verified); exactly 0 from ~15 voxels (15 Å on the 1 Å grid) outside the predicted mask onward; intensity scale is **not** the input's (normalised input × 100 through a linear head; G24) | visual interpretation and model building; choose the contour by eye, never compare absolute densities with the input |
| `<n>_in_score.mrc` | predicted local quality of the **input** map | ≥ 0 (negatives clipped); on the 1 Å grid ≤ 1 (max 0.996 / 0.9997 fast / normal, verified); **exceeds 1 after `--reverse_interpolation True`** (no upper clamp; 50 voxels, max 1.125, verified) | predicted local SSIM against a model-simulated map (5×5×5 Gaussian window; pp l.636-638, 1084-1098) — **not local resolution, FSC or Q-score**; not faded outside the mask |
| `<n>_out_score.mrc` | predicted local quality of the **enhanced** map | as above (1 Å grid max 0.973; after reverse resampling 27,787 voxels > 1, max 1.137 — verified) | flags regions where sharpened-looking features may not be reliable (pp l.668-671) |
| `<n>_in_mask.mrc` | predicted molecular mask | **binary** 0/1 (≥ 0.5), also after resampling (verified) | training label = voxels within 4 Å of any atom (pp l.1079-1080); a hard envelope, not a soft refinement mask |

With `--keep_size True` all four are 0 outside the crop region.

## 6. Placement and viewers

The outputs carry their position only in NXSTART/NYSTART/NZSTART (ORIGIN = 0). Programs differ in whether they read
ORIGIN, NSTART or both, so check once that the outputs overlay the input in the viewer you use (runbook R12 has a
numeric alignment check; `scripts/check_outputs.py --input` checks that the output box lies inside the input map's
extent). Fast-mode outputs are smaller than the input box but placed inside it; that is expected.

## 7. Side files

- `--crop_check True`: `round_<N>_check/projections_top_0p1pct.png` and `projections_top_1pct.png` per review round in
  `-o`; all `round_*_check` folders are **deleted** when you continue (Enter or `c`), and left behind if the run dies at
  the prompt (`crop_check.py:84-87`, `:386-423`; both verified). The README mentions only `round_1_check/`. The prompt
  shows the crop as `Current ranges: X-=29 X+=121, Y-=35 Y+=120, Z-=34 Z+=146` (1 Å voxel indices, EMD-10387).
- Nothing else is written: no config, log or provenance file.
