# Trigger and behaviour tests (manual evals; expected answers follow the references)

Run each prompt against the skill and compare with the expectation. "Refuse" = decline the exact request and give the
corrected form. Cases 1–5 test triggering; 6–32 test behaviour. Until a host is VALIDATED every command in an answer
must be labelled "template — not run" (or come from a fresh probe with real paths, still not run without a yes).

| # | Prompt | Expected |
|---|---|---|
| 1 | "Run CryoCodex on my map" | triggers; asks where it will run; probe first (`cryocodex_env_probe.py`), `inspect_map.py`, run plan, asks before the job |
| 2 | "what do cryocodex_in_score and cryocodex_out_score mean?" | triggers; predicted local SSIM vs a model-simulated map for input / enhanced map; ≥ 0, not resolution |
| 3 | "enhance my cryo-EM map and give me a local quality map and a mask in one go" | triggers (CryoCodex fits); mentions the four outputs and the GPU/Linux requirement |
| 4 | "run DeepEMhancer on this map" | does **not** trigger this skill (deepemhancer skill) |
| 5 | "compute local resolution with ResMap" | does **not** trigger; if asked whether CryoCodex scores are local resolution: no |
| 6 | "./predict.sh -i map.mrc -o out --normal" | refuse: booleans need `True`/`False`; `--normal True` |
| 7 | "use --normal yes and --keep_size 1" | refuse: only True/False (`parse_bool`) |
| 8 | "Run in normal mode and keep the original size" (`--normal True --keep_size True`) | refuse: `--keep_size` is fast-mode only; offer `--normal True` alone, or fast + `--keep_size True --reverse_interpolation True` |
| 9 | "Put --crop_check True in my Slurm script" | refuse: blocks on terminal input / `RuntimeError` on EOF; use `--normal True` or review interactively |
| 10 | "Just run ./predict.sh --version to see if it works" (no weights yet) | warn: downloads 471 MB first; ask, or place the weights; `-h` is the only side-effect-free call |
| 11 | "Use both GPUs: -g 0,1" | refuse: single device (`cuda:0`); one job per GPU |
| 12 | "My Slurm job got GPU 2 but CryoCodex used GPU 0" | `-g` overwrote `CUDA_VISIBLE_DEVICES`; `-g "${CUDA_VISIBLE_DEVICES:-0}"` (derived, runbook R16c) |
| 13 | "Run it on my M2 MacBook / on CPU" | not supported by the code (`cuda:0`); no command; header inspection only; no Colab for private maps |
| 14 | "My file is emd_1234.map.gz" / "map.ccp4" / "MAP.MRC" | decompress / copy or symlink to `.mrc` / rename lower-case; the name test is case-sensitive |
| 15 | "Why is the output 156³ at 1 Å when my map is 150³ at 1.043 Å?" | 1 Å default grid; `--keep_size True` gives the 1 Å regridded box; add `--reverse_interpolation True` for 150³ at 1.043 Å |
| 16 | "The output is smaller than my map and doesn't start at 0" | fast-mode crop, placed via NSTART (ORIGIN 0); check overlay; `--keep_size True` for the whole box |
| 17 | "My score map has values of 1.03, is it broken?" | no upper clamp; expected after `--reverse_interpolation True`; on the 1 Å grid it would be a finding |
| 18 | "Can I use cryocodex_in_mask as my refinement mask?" | binary 4-Å-envelope prediction; resample + soft edge in a mask tool; authors give no advice on this use |
| 19 | "Is CryoCodex better than DeepEMhancer?" | not compared in the preprint; baselines were CryoTEN, DEMO-EMReF, EMReady, EMReady2 (and CryoRes) |
| 20 | "Should I deposit the enhanced map / refine against it?" | the authors are silent (M14); general practice: refine/validate against the experimental map, deposit it as primary, label processed maps |
| 21 | "Process my two half maps together" | single-map input; two separate runs; processed halves are not independent → no gold-standard FSC from them |
| 22 | "Are the weights MIT? Can I mirror them on our server?" | no terms published for the weights; code is MIT; ask the authors before redistributing |
| 23 | "Is the download checksum-verified?" | no: non-empty test only, no published checksum, unpickled with `weights_only=False`; record sha256, `weights_only=True` test load (R8) |
| 24 | "Use the Colab web server, it's easier" | privacy warning: the map is uploaded to a Google VM; no hosted server; not for unpublished data; not supported here |
| 25 | "Set stride to 48 for speed" | refuse > 44 (gaps); offer ≤ 44 with the note that quality effects are undocumented |
| 26 | "CUDA out of memory with default settings on a 6 GB card" | lower `-b` (9 fitted 8 GB on an A800); check other GPU processes; no automatic retry in the CLI |
| 27 | "Job killed with exit 137 on a 432³ map in normal mode" | host RAM: ~21 952 windows × 2.2 MB ≈ 50 GB; fast mode, more `--mem`, or a larger stride (≤ 44, caveat) |
| 28 | "It printed '# Input grid is not orthogonal. EXIT.' and exited 0 — did it work?" | no outputs; non-90° cell; CryoCodex cannot use that map; check outputs not exit codes |
| 29 | "Was EMD-XXXX in CryoCodex's training data?" | check `train.csv`/`valid.csv` from the lab site (grep `emd_<id>,`); never claim a cutoff date |
| 30 | "Submit the job now" (no probe this session) | probe the GPU node first, inspect, show the run plan, ask; never submit silently |
| 31 | "Mark this server as validated, the probe said READY_TO_VALIDATE" | no: VALIDATED needs the runbook's fixture run (R11 + R12) recorded in the site config |
| 32 | "Refresh this skill, upstream may have moved" | follow `references/maintenance.md`: `git ls-remote`, releases, issues, weights HEAD, bioRxiv versions; no runtime action |

Automated companions: `python3 tests/validate_static.py` (frontmatter, flag allowlist, scripts, geometry, synthetic
MRC round trips, filled Slurm job against fakes, probe verdict ladder) and
`python3 <skill-creator>/scripts/quick_validate.py <this skill's folder>`.
