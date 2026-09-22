# 09 — Validation and Benchmarks

## Talk about quality honestly

- Report published numbers as **the authors' claims**. Give the checkpoint, benchmark, protocol (MSA, templates, seeds ×
  samples, recycles) and hardware. Never launder them into guarantees for a user's target.
- The reports differ in checkpoint. Preview-1 and preview-2 numbers describe `openfold3-p1` and `of3-p2-155k`, not
  OpenBind-0. At v0.5.0 the default is OpenBind-0.
- **Oracle ≠ ranked.** Both OpenFold3 reports find the gap to AlphaFold3 larger for ranked (confidence-selected) results
  than for oracle (best-sample) results: the generator makes good samples that ranking can fail to pick. In practice, run
  several seeds, look beyond the top-ranked model, and treat ranking scores as advisory.
- Speed-ups are **hardware-, size- and setting-specific**. The kit baseline `off` is stock with the kit's stock
  configuration (cuEquivariance kernels + bf16-mixed), not upstream's shipped defaults (Triton kernels, fp32, chunk tuner).
  State which baseline a ratio uses.
- Single-sequence runs (`--use-msa-server false` with no MSAs) give low confidence on most proteins. Such runs test the
  software, not model quality.

## OpenFold3-preview white paper (preview-1) **[paper]**

- Protocol: 5 seeds × 5 samples, MSA subsampled to 1 024, templates on. AlphaFold3 was run without templates except on
  Runs N' Poses.
- Claims:
  - Close to the best AlphaFold3 reproduction on each modality.
  - At parity with AlphaFold3 on RNA monomers (CASP16 RNA, Ludaic & Elofsson). RNA MSAs improved one target (8TJU) by about
    23 Å RMSD.
  - AlphaFold3 is "substantially more performant" on antibody–antigen and protein–ligand complexes, especially novel
    pockets.
  - Ranking performance "substantially trails AF3 relative to oracle performance".
- Errata: a template inter-chain mask bug (fixed in preview-2). There was no nucleic-acid self-distillation.

## OpenFold3-preview2 technical report **[paper]**

- Training: 155 000 steps on 256 H100s. The benchmarks were run on AMD MI300A.
- Protocol: MSA subsampled to 1 024, templates, 10 recycles, 5 seeds × 5 samples. Scores come from a strict common subset
  of targets that every compared model completed.
- Runs N' Poses (protein–ligand): similar to Protenix-v1 on most similarity bins. AlphaFold3 is still best overall. The
  ranked gap to AlphaFold3 is larger than the oracle gap.
- FoldBench:
  - comparable to AlphaFold3 and Protenix-v1;
  - slightly behind on nucleic-acid monomers, protein–protein and protein–DNA;
  - on par or ahead on protein monomers and protein–RNA;
  - "mostly within statistical variation".
- Antibody–antigen (1 000 seeds): improves with seed count, but more slowly than AlphaFold3.
- Errata: the RNA distillation set was generated with rocBLASLt and had lower chemical validity. NVIDIA GPUs are
  unaffected, and the released set was regenerated.

## OpenBind-0 announcement and Zenodo benchmark **[docs]**

- Training data: PDB up to 30 June 2025, with no OpenBind data. Evaluated with the Runs N' Poses method on post-cutoff
  complexes. A success needs lDDT-PLI > 0.8 and ligand RMSD < 2 Å.
- Headline: "comparable to AlphaFold3" across similarity bins. OB0 and OF3-p2 are similar in many bins; gains appear in the
  highest and lowest similarity bins.
- Chemical steering raised joint success (correct pose + PoseBusters-valid) **from 48 % to 61 %**. This steering is not in
  v0.5.0 code (`00_scope_and_trust.md`), so a `run_openfold predict` at v0.5.0 may not reproduce such numbers.
- Per-target results (5 seeds × 5 samples, ranked by protein–ligand ipTM; success also needs PoseBusters validity):

| Target | Result |
|---|---|
| EV-A71 2A protease | top-25 92.2 %, top-1 73.8 % |
| FatA | top-25 28.2 % (OF3-p2 14.5 %, Protenix-v1-20250630 39.4 %) |
| RdRp DENV-2 / ZIKV | no model above 10 % top-25 (max 7.7 % / 6.7 %) |

- Zenodo 10.5281/zenodo.22037460: 462 protein–ligand systems with ground truth, queries and MSAs (9.3 GB, CC BY 4.0). The
  record says it is a preview and asks users to switch to the official updated PLINDER benchmark once released.

## Anthropic report — OpenFold3 sections **[paper]**

All measurements were on H100 80 GB (one GPU except the two-GPU reach probe). Inputs were 200–1 400 tokens, one query per
call. Settings were 10 recycles (upstream default 3), 200 diffusion steps and 5 samples, with precomputed MSAs and no
server. "Default" means upstream at its fastest reachable settings (cuEquivariance on, DeepSpeed attention off,
bf16-mixed, fixed chunk). The headline clock is the forward call only.

| | OpenFold3-p2 (0.4.1, pp. 27–30) | OpenBind-0 (0.5.0, pp. 31–34) |
|---|---|---|
| Forward speed-up, Fast / Big | 8.77× / 8.54× at 200 tokens, 4.3–4.7× from 600; geomean 5.10× | geomean 4.93× / 4.94× |
| Exact | 1.43–1.94× | smaller and inconsistent; slower than default once |
| Whole-pass speed-up | Fast 2.46–3.62×, Big 3.68–5.11×, Exact 1.91–2.18× | recorded, not shown. Smaller than forward for Fast/Big |
| Peak memory | Above default at small sizes (Exact up to 2.6× through 600 tokens). 0.37–0.70× at 800–1 200 | Exact (200–400) and Fast/Big (200) can exceed default. Below default at larger sizes |
| Reach (largest input completed) | default 3 000; Big 6 000 (1 GPU), 17 000 (2 GPUs, shortened probe) | default 3 000; Big 6 000 (1 GPU), 17 000 (2 GPUs, one-recycle probe) |
| FoldBench-Lite acceptable top-1 (DockQ ≥ 0.23) | 251 interfaces: 56.6 % default; 55.8 / 53.4 / 54.2 % Exact / Fast / Big | 251 interfaces: 58.2 % default; 59.0 / 56.6 / 56.6 % |
| Paired changes whose CI excludes 0 | protein-monomer lDDT −0.005 (Fast, Big) | protein-monomer lDDT +0.001, RNA-monomer lDDT −0.013 (Fast, Big) |
| Identity | Exact bit-identical on all 435 identity-set predictions, deterministic recipe | Exact byte-identical to default, deterministic setting. Big on 2 GPUs matches 1 GPU within tolerance, not bit-for-bit |

- The report's shipped-settings run ("base": fp32/TF32, chunk tuner, no cuEquivariance) averaged about 0.68× default speed
  (OpenBind-0, geometric mean; faster than default only at the smallest size).
- Cross-model pooled result: no significant change. However, OpenFold3-p2 Fast weighted per target changed by
  −3.4 points, with a CI ending just below zero. Small losses "cannot be ruled out".
- Stock OpenFold3 is not reproducible run to run at production settings. That is why identity is checked only under
  deterministic settings.
- The report's accurate assemblies above 10 000 tokens ran `big` on 8-GPU nodes (H100/H200/B200) across up to four
  different models, mostly with templates. Do not attribute them to OpenFold3 on one GPU.

## Kit README headline claims **[docs]**

- Kit README (ob0) comparison, H100 80 GB vs stock:
  - `exact`: identical outputs, faster;
  - `fast`: "within stock's seed-to-seed variation";
  - `big`: "up to 5,000 tokens on one GPU" (the 0.4.1 kit README says 6 000, and the report says 6 000 for OB0);
  - `--n_gpu P`: splits `big` across GPUs of one host.
- Quote the lower figure. A size is not a promise.
- Every call spends about 45 s starting Python and loading the 2.3 GB checkpoint. The first kit-mode run compiles Triton
  kernels (about 20 s) and runs a one-time kernel self-check (seconds on H100, up to about 30 s on A100).

## Measured on one site **[measured]**

This is a Slurm HPC site with A100-SXM4 40 GB and H100 94 GB nodes, validated 2026-09-22. Setup: kit `openfold3_ob0` @
`f4f62fa` as an Apptainer image built from the kit Dockerfile, driver 595.91.07.

- **Completion:** 218/218 calls rc 0 across `off/exact/fast/big`. The input ladder had 12 inputs from 13 to 995 polymer
  residues (52 → 995 model tokens; modified residues and ligands tokenize per heavy atom): 9 upstream example queries plus
  3 public 1BRS barnase–barstar assemblies of 199, 508 and 995 residues. Both cards ran with no OOM through 995 tokens.
- **Identity:** `exact --det 1` equals `off --det 1` byte for byte for 60/60 model/confidence file pairs (5 samples × 3
  files × 2 inputs × 2 cards) on the 13-residue modified-DNA query (52 tokens) and the 508-residue assembly. Ordinary
  `exact` (det 0) is **not** byte-identical to `off`. `exact --det 1` ran at 0.92–1.05× the whole-call speed of ordinary
  `off` (single calls that include cold-cache effects), i.e. about stock speed.
- **Warm whole-call speed-up vs `off`:**

| Mode | A100 | H100 |
|---|---|---|
| `exact` | 1.12–1.40× | 1.11–1.37× |
| `fast` | 1.24–2.13× | 1.21–1.83× |

- **Forward-pass speed-up vs `off`:**

| Mode | A100 | H100 |
|---|---|---|
| `exact` | 1.23–2.30× | 1.28–2.36× |
| `fast` | 3.11–5.59× | 3.14–5.45× |

- **995-token warm calls:**

| Card | `off` wall / fwd s | `exact` | `fast` | `big` | Peak MiB `off` → `fast` |
|---|---|---|---|---|---|
| A100 40 GB | 136.9 / 77.8 | 97.9 / 45.6 | 69.0 / 13.9 | 68.6 / 14.0 | 24 844 → 13 662 |
| H100 94 GB | 95.2 / 47.6 | 69.3 / 27.6 | 52.7 / 8.7 | 54.1 / 8.7 | 25 053 → 13 701 |

- **Bare stock vs armed stock (ubiquitin):** bare `run_openfold predict` uses upstream's shipped settings. The same command
  with `OPENFOLD3_OB0_OPT=fast` exported took 42.6 / 33.9 s, against 57.2 / 45.4 s bare (A100 / H100). This env route has
  no exit rule or token count (`06_kit_modes_and_multigpu.md`).
- **JIT:** the first `fast` call cost 22–39 s more than the warm call. JIT caches held 668–1 013 files (40–65 MB) per job.
  Keep them on node-local storage.

**Limits of this evidence:**
- All inputs were single-sequence (`--use-msa-server false`), so the confidences are not representative of MSA runs
  (top-model mean pLDDT 31–92).
- No templates were used.
- Only one seed with 5 samples was run.
- Every input was at or below 995 polymer residues. That is below `big`'s 1 401-polymer-token gate, so `big` behaved as
  `fast`, and nothing above the gate or with `--n_gpu` was tested.
- **`fast` fidelity was not calibrated.** Top-model CA RMSD of `fast` vs `off` reached 29.4 Å (A100, 590-residue
  multimer) / 29.9 Å (H100, 995-residue 1BRS tiling) on low-confidence single-sequence inputs. That says nothing about
  accuracy either way.
- Peak memory was sampled with nvidia-smi at 1 Hz.
- Whole-call times include startup and output writing.

## Recommended validation for a new host

Do each step only with the user's confirmation (`00_scope_and_trust.md`). Start from the post-install checks in
`02_install_and_environment.md` (probe, pins, `predict --help`, `run.sh check`, weights, GPU fixture). Record the results
in `configs/site_config.local.md`.

```bash
# template — not run; from inside openfold3_ob0/ (or through the image's run.sh)
bash run.sh warm  --config <card> --mode fast --out <warm_dir>   # public 199-token input: JIT, graphs, self-check
Q=stock/src/examples/example_inference_inputs/query_ubiquitin.json
unset OPENFOLD3_OB0_OPT                                          # a --mode that disagrees with it is refused
for m in off exact; do
  bash run.sh pred --config <card> --mode "$m" --det 1 --query-json "$Q" \
    --output-dir "<out>/${m}_det1" --use-msa-server false
  echo "$m rc=$?"                                                # no set -e: rc 3/5 are results
done
for m in off exact; do
  (cd "<out>/${m}_det1" && find . \( -name '*_model.cif' -o -name '*_confidences*' \) | sort | xargs sha256sum) > "<out>/${m}.sha"
done
diff "<out>/off.sha" "<out>/exact.sha" && echo IDENTICAL          # expected: identical under --det 1
```

1. **Fixture ladder.** Run the smallest upstream example first, then the remaining example queries. Then run public
   assemblies up to the largest size you intend to use, for example the kit's 1BRS tilings (199–1 194 tokens). For each
   call record rc, wall time, `Model forward time:` lines, peak device memory and output completeness
   (`scripts/summarize_openfold3_output.py`).
2. **Identity check.** Confirm that `off --det 1` and `exact --det 1` give byte-identical outputs on at least one small
   and one mid-size input. Do not expect ordinary `exact` to match `off`.
3. **Seed spread before trusting `fast`.** On 2–3 inputs that look like production, using the MSA route you will use in
   production, run `off` with several seeds. Seeds are generated deterministically from the start seed, so the same flags
   give the same seeds in every mode. Measure stock's own seed-to-seed spread (top-model CA RMSD, ipTM, pLDDT). Then run
   `fast` with the same seeds. Accept `fast` only if its deviation from `off` stays within that spread, which is the
   report's accuracy-guard design. Single-sequence, low-confidence inputs make this test uninformative.
4. **Memory route.** If inputs reach 1 401 or more polymer tokens, test `big` at those sizes and any `--n_gpu P` layout
   separately. Below the gate `big` is `fast`, and it will not rescue a small-input OOM.
5. **Network features.** Test the MSA server and templates with a public sequence after approval. Check for
   `TEMPLATES DROPPED` (exit 5) on offline hosts.
6. **Scope the claim.** Write down the card, driver, image or stack, kit commit, token range, modes, seeds and MSA route
   that you validated. Claim nothing outside that range, and never relabel it for a newer release (`maintenance.md`).
