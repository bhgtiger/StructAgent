# 08 — Validation & limits (what the paper does and does not license)

Paper: Sánchez-García R, Gómez-Blanco J, Cuervo A, Carazo JM, Sorzano COS, Vargas J. **DeepEMhancer: a deep learning solution for cryo-EM volume post-processing.** *Communications Biology* 4, 874 (2021). DOI `10.1038/s42003-021-02399-1` (PMC8282847). Use the paper for **rationale and limitations only** — never for CLI flags, install commands, versions, or download URLs (those come from source/live help).

## What the method is (rationale)

- An **automatic** post-processing method for cryo-EM maps that performs **masking-like and sharpening-like** operations **in one step**.
- An **end-to-end 3D U-net** applied to **chunked cubic** sub-volumes of the input map.
- **Trained** on experimental maps paired with target maps **sharpened using atomic models** (LocScale-like targets).
- Evaluated on a **testing set of 20 experimental maps**, reporting noise reduction and more detailed maps.

## What you must NOT claim (no quantitative generalization)

- **Do not** generalize the paper's quantitative benchmark numbers (FSC / DeepRes improvements, the 20-map test-set statistics) to a user's specific map. Those are paper-contextual on a particular benchmark. The skill must not promise a resolution gain, an FSC shift, or a quality score for any user map.
- Do not claim DeepEMhancer "improves" a given map. It produces a post-processed map **for visualization and model building**; whether it helps is a judgement the user makes against their own data and the science.
- The output is **not** an independent resolution measurement. Do not treat post-processed appearance as a resolution claim.

## Scientific limits & cautions to surface

- **Input must be raw/unmasked/unsharpened** (from refinement). Post-processed/masked/sharpened inputs are out-of-distribution for the trained models and can mislead (`references/04`).
- **Model trained on particular targets.** The README cautions that features absent from training (e.g. some ligands / post-translational modifications) may not be faithfully represented; do not over-interpret novel densities introduced or removed by the network.
- **`highRes` only for overall FSC < 4 Å**, and it can look noisier. **`tightTarget`/`highRes` can over-mask**; `wideTarget` is the less-aggressive option.
- **Auto-normalization can rarely fail / be less accurate** — consider `--noiseStats` or a binary mask if results look wrong (`references/04`).
- **`--cleaningStrengh`** (sic) deletes small connected components; it can remove real weak density. Default is off (`-1`).
- A successful run / loaded model says **nothing** about biological correctness. Always inspect the output map and cross-check with independent evidence (half-map FSC, model-to-map agreement, known chemistry).

## Skill-level validation status

- **Runtime (functional) test: PASSED on a Linux + RTX 2080 Ti host.** DeepEMhancer 0.17 on TF 2.10 loaded the `tightTarget` checkpoint, ran 3D-U-net inference over a 128³ test volume (padded to 160³, 49 cubes) on the GPU in ~70 s, and wrote a valid `.mrc` with the expected DeepEMhancer transform (solvent denoised toward 0, signal preserved). Both the direct CLI and the `run_deepemhancer.sh` runner were exercised. This is a **functional** test — it proves the pipeline runs and writes valid output, **not** that any user map improves. See `references/09`.
- Static validation in place: `tests/validate_static.py` (package integrity, config-first rule, flag exact-spellings/phantoms, privacy/packaging hygiene, confirmation-gate language, probe safety, `determine_state()` semantics) and `python3 -m py_compile` of the Python scripts.
- Config-state validation: `determine_state()` is exercised with synthetic facts (non-Linux/uninstalled → `blocked`; provisioned Linux → `ready`) and confirmed against the two real reports (a `blocked` Mac mini and a `ready` Linux/GPU host).

## How to talk about results responsibly

```text
reporting guidance
- Say what the model/normalization/inputs WERE, and that the output is for viewing/model building.
- Do NOT attach a resolution number, FSC delta, or quality score derived from the paper.
- Recommend independent validation (half-map FSC, model-map agreement, chemistry).
- If asked "did it improve my map?", explain it is a user judgement against their data, not a guarantee.
```
