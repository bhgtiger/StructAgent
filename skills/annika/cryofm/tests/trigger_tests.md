# Trigger and behaviour tests (manual evals; expected answers follow the references)

Run each prompt against the skill and compare with the expectation. "Refuse" = decline the exact request and give the
corrected form. Cases 1–4 test triggering; 5–30 test behaviour.

| # | Prompt | Expected |
|---|---|---|
| 1 | "denoise my half maps with cryoFM" | triggers; asks for/inspects the two half maps; proposes `cfm denoise … --op denoise --norm-grad --use-lamb-w --bf16` after a probe |
| 2 | "run cfm enhance on this map, EMReady style" | triggers; emits `--model-dir …/cryofm2-emready --output-tag 0 --cfg-weight 0.5`; says no data term, outputs vary run to run |
| 3 | "how do I use CryoFM2 inside RELION refinement" | triggers; RELION ≥ 4.0.1, env var string with `cfm-relion`/`relion_wrapper.py`, final-iteration ValueError hazard, `--num_processes` ignored, not run here |
| 4 | "cryo-fluorescence microscopy workflow" | does **not** trigger (name collision cryo-FM = cryo-fluorescence) |
| 5 | "Just copy the quick-start anisotropy command" (`--op inpaint denoise … --op denoise`) | refuse: second `--op` wins → plain denoise; give one `--op denoise inpaint --data-starfile-path …` |
| 6 | "cfm denoise -i map.mrc -i1 h1 -i2 h2 --model-dir cryofm2-emhancer --output-tag 1" (docs "Add extra control") | refuse: `cfm denoise` has no `--output-tag`; use `cfm enhance -i -i1 -i2 … --op denoise --norm-grad --use-lamb-w` |
| 7 | "I only have the sharpened deposited map, can I denoise it?" | no: `cfm denoise` needs two half maps; offer `cfm enhance` style modes and explain there is no data term |
| 8 | "Why does cfm denoise --help not show the flags?" | launcher stub; use `python -m cryofm.projects.cryofm2.uncond_sampling --help`; list from 03 |
| 9 | "It crashed with AssertionError: Now we only support norm=True for flow" | missing `--norm-grad`; add `--norm-grad --use-lamb-w` |
| 10 | "CUDA out of memory on a 16 GB card even with 4 GPUs" | `--batch-size 2` (maintainer), `--bf16`; multi-GPU does not lower per-GPU memory; docs table numbers |
| 11 | "Error: Given groups=1, weight of size [64, 3, 3, 3, 3], expected input[4, 2, 64, 64, 64] to have 3 channels" | emhancer/emready dir used with `cfm denoise`; use `cryofm2-pretrain` |
| 12 | "My half maps are 127³" | odd cube → bare AssertionError; pad to an even box first (both halves and mask) |
| 13 | "The output does not overlay my model in ChimeraX" | origin/NSTART reset to 0; `restore_origin.py` or `volume #N originIndex`; never `volume resample` |
| 14 | "Can I compute the resolution from the two denoised half maps?" | no: outputs share the input FSC; not gold-standard; use map-model FSC/CC, visual checks |
| 15 | "My 1.8 Å map came back blurrier than the input" | 1.5 Å model grid → 3 Å band limit; `--spectral-mixing` pastes raw input above 3 Å; expected behaviour |
| 16 | "Use 400 sampling steps for higher quality" | warn: 400 ∤ 1000 → 0.8 of the flow; docs tier conflicts with code; use 200/250/500; paper: no gain beyond 200 |
| 17 | "Run it on my Mac M3" | no validated non-NVIDIA path; explain only; no command |
| 18 | "Set --model-dir to the cryofm-v2 folder" | refuse: repo root manifest → `AttributeError … z_scale`; point at the variant subfolder |
| 19 | "Which half maps should I export from cryoSPARC, and should I sharpen first?" | undocumented upstream; give context (map_half_A/B unfiltered, training on EMDB halves, EMReady-style on sharpened deposited maps); do not invent a rule |
| 20 | "Deposit the denoised maps as my half maps in EMDB" | advise against: processed maps, outputs not independent, EMDB wants unfiltered halves; "Other EM maps" at most; upstream silent |
| 21 | "Submit the job now" (no probe this session) | probe first (`cryofm_env_probe.py`), inspect headers, show run plan, ask for go-ahead; no silent submission |
| 22 | On a cluster login node: "run cfm denoise here" | refuse to run sampling on a login node; Slurm template (`templates/slurm_cfm.sbatch.template`) on the GPU partition; `--help` only here |
| 23 | "Get the RELION wrapper's help text" | never run `relion_wrapper.py --help` (recursion); read 03/07 |
| 24 | "Make the anisotropy run faster with --num_processes 4 and --fsc-weighting" | warn: multi-GPU untested here; `--fsc-weighting` barrier hazard with > 1 process; drop it |
| 25 | "Is `--mask-path` going to mask the output?" | no: only crops the sampling region with `--bbox`; without `--bbox` it does nothing; cubic mask on the input grid |
| 26 | "Use the EMD-12042 primary map as -i with its half maps" | refuse: 128³ vs 256³ → shape mismatch; use a half map as `-i` |
| 27 | "What does the paper prove about resolution?" | preprint, unrefereed; half-map metrics inflated by shared priors; map-model FSC favoured CryoFM; no hallucination test; cite tiers |
| 28 | "Our RELION 3.1 cluster" | `KeyError: 'rlnParticleDiameter'`: needs ≥ 4.0.1 |
| 29 | "Why is my CC between output and input only 0.3?" | 3 Å band limit on a sub-1.5 Å map; compare after low-passing both (validated-site fixture 0.986 at 3.5 Å) |
| 30 | "Refresh this skill, upstream may have moved" | follow maintenance.md: check branch heads (no tags), HF revision, docs last-modified, paper status; no runtime action |

Automated companions: `python3 tests/validate_static.py` (frontmatter, flag whitelist, scripts, geometry, synthetic
MRC round trips) and `python3 <skill-creator>/scripts/quick_validate.py <this skill's folder>`.
