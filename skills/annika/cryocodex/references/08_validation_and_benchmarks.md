# 08 — Paper claims, training data, benchmarks, what results do and do not mean

Source: Cheng B., Su B., Yang J., bioRxiv preprint v1, doi:10.64898/2026.09.30.755675 (posted 2026-10-02; **not peer
reviewed**; CC BY-NC-ND 4.0). `pp l.N` = line N of the evidence pack's text extract ([01 §3](01_source_map.md)).
Paper numbers are copied verbatim; "derived" marks our arithmetic. The paper names no software version or checkpoint,
so its numbers are **not** a promise about v1.0.0 on the user's map (M24).

## 1. Method in three lines

48³ boxes of the 1 Å-resampled, percentile-normalised map go through "MMVQ-UNet" — a U-Net (adapted from CryoAtom2's
RU-Net) with a multi-head, multi-scale residual vector quantiser (one shared codebook of 4096 vectors, EMA-updated,
gated fusion with continuous features) plus global attention — which predicts four channels: enhanced density, input
quality, enhanced quality, mask; box outputs are blended back (pp l.131-143, 874-976). No training code is released.

## 2. Training data (and how to check for leakage)

| Item | Statement | Cite |
|---|---|---|
| Source | EMDB maps paired with PDB models, reported resolution 3–8 Å | pp l.982-984 |
| Filters | FSC-0.143 resolution; unique, complete model; orthogonal axes; CC_mask > 0.5; Chimera map-model correlation > 0.6; ≤ 10,000 Cα + C4′ atoms | pp l.984-1001 |
| Redundancy | MMseqs2: proteins 30 % identity / 80 % coverage; nucleic acids 80 %/80 % | pp l.1004-1012 |
| Total / split | 1658 non-redundant pairs; 126 test, 66 validation, the rest (1466, derived) training | pp l.1013-1022 |
| Published lists | `train.csv` (1466 rows) and `valid.csv` (66) under `https://yanglab.qd.sdu.edu.cn/CryoCodex/benchmark/`; format `emdb_id,pdb_id`, e.g. `emd_1980,4a6j` | lab site |
| Reconstruction types | mostly SPA; subtomogram averages and helical maps only "a small fraction", not evaluated separately | pp l.1037-1042 |
| Date cutoff | **not stated**; entries released up to at least March 2026 are included (derived lower bound) | — |

Leakage check for a user's EMDB entry: download the two lists and `grep -i "^emd_<id>," train.csv valid.csv`. A hit
(or a > 30 % sequence-identical entry) means the network saw that structure in training; benchmark-style claims on
that map are then optimistic. Never state a cutoff date or that an entry was "not seen" without checking the lists.

## 3. Benchmarks (verbatim numbers)

Test set: 126 deposited EMDB **primary** maps (FSC-0.5 on the 120 with valid results; Q-score on 126). Map-model FSC-0.5
(unmasked, `phenix.mtriage`) and Q-score (MapQ in UCSF Chimera) against the deposited models (pp l.198-201, 1186-1200).

| Method | FSC-0.5 (Å) | Q-score | ΔFSC-0.5 > 1 Å (%) | ΔQ > 0.05 (%) | ΔQ > 0.08 (%) |
|---|---|---|---|---|---|
| deposited | 6.87 | 0.422 | – | – | – |
| CryoTEN | 4.86 | 0.405 | 27.50 | 0.79 | 0.00 |
| DEMO-EMReF | 4.82 | 0.446 | 45.00 | 33.33 | 8.73 |
| EMReady | 4.83 | 0.450 | 40.00 | 33.33 | 7.14 |
| EMReady2 | 4.62 | 0.460 | 43.33 | 35.71 | 11.11 |
| CryoCodex | 3.93 | 0.503 | 75.83 | 73.81 | 57.94 |

(Supplementary Table 1.) Also:
- Nucleic-acid subset (22 maps): CryoCodex FSC-0.5 3.43 Å, Q 0.522 vs EMReady2 4.02 / 0.474, deposited 5.45 / 0.427.
- Automated model building (`phenix.map_to_model`, 761 chains): residue coverage 72.1 % vs EMReady2 66.7 %, deposited
  51.5 %; sequence recall 31.7 % vs 25.8 % / 15.5 % (pp l.295-300).
- Local quality vs per-atom Q-score (Spearman): input-map score per-map mean 0.22 vs CryoRes 0.18 (pooled 0.48 vs
  0.43); enhanced-map score per-map 0.47, pooled 0.71 (pp l.648-667).
- Mask: mIoU 0.88, foreground IoU 0.79 vs CryoRes 0.69 / 0.54 (pp l.675-677).
- Runtime: all methods capped at 8 GB GPU memory on one NVIDIA A800; CryoCodex fitted batch 9; mean 74.87 s per map vs
  EMReady2 106.69 s, CryoTEN 44.80 s (pp l.796-807); EMD-10387: 17.87 s (Supplementary Data 7).
- Evaluation detail: all methods except CryoTEN ran on maps resampled to 1 Å (pp l.1240-1243).

Baselines were CryoTEN, DEMO-EMReF, EMReady, EMReady2 and CryoRes. **DeepEMhancer and LocScale were not benchmarked.**

## 4. What the results mean — and what they do not

- Map-model FSC and Q-score measure agreement with the **deposited model**. Higher values say the enhanced map looks
  more like that model; they are not a new resolution of the experimental data.
- The quality maps predict local SSIM against a model-simulated map; they are not local resolution and only modestly
  track Q-score (§3).
- Gains: FSC-0.5 gains did not fall monotonically with resolution, but "Q-score gains declined progressively and became
  limited beyond approximately 5 Å" (pp l.220-221, 235-236).
- Hallucination: one case study (EMD-19811) showed ambiguous density was not forced into canonical features
  (pp l.581-596) — anecdotal, not a systematic test. The half-map analysis "cannot establish the correctness of every
  individual enhanced feature" (pp l.525-527).
- Half maps processed one at a time: processed halves agree more strongly with each other than raw halves; the authors
  do not interpret those FSC crossings as physical resolution (pp l.504-514).
- No statement on using enhanced maps for refinement, validation or deposition (M14); no explicit limitations section.
- Under-represented: subtomogram-average and helical maps; maps outside 3–8 Å.

## 5. Checking results on the user's own map (our practice, not the authors')

1. Compare the enhanced map with the input at matched contours; distrust features absent from the input.
2. Look at `out_score` where the enhanced map shows new detail; low scores mean low predicted reliability.
3. Fit and validate models against the **experimental** map; use the enhanced map as a building aid.
4. If the entry is in `train.csv`/`valid.csv`, say so when reporting results on it.

## 6. Live validation of this skill

None yet. [validation_runbook.md](validation_runbook.md) (R0–R20) checks install, help texts, the weights, argparse
errors, input acceptance, the four outputs on EMD-10387 (in the paper's test set, not in train/valid), the
`--keep_size`/`--reverse_interpolation` grids, `--crop_check` without a terminal, GPU selection and egress. Expected
values there are derived from code and are **not** observations. Optional R18 compares with the authors' published
result for EMD-10387 (whether it was made with the released checkpoint is unknown).
