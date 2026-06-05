# Trigger tests

Manual checks that the skill activates correctly and the **config gate** fires.

## Should TRIGGER the skill
| # | Prompt | Expected |
|---|---|---|
| T1 | "Set up Topaz on my Mac mini." | Trigger; run config gate (DT-0); detect Apple Silicon. |
| T2 | "Use Topaz to pick particles on this dataset." | Trigger; **block** workflow until config exists; offer probe. |
| T3 | "Can Topaz use my M4 GPU?" | Trigger; answer **no MPS / CPU-only** from source (ref 02). |
| T4 | "Generate a topaz extract command for my mrc files." | Trigger; v0 → placeholder template + "concrete = v1". |
| T5 | "Convert my topaz coords to a RELION star file." | Trigger; `convert` template; note scaling caveat. |
| T6 | "Why does topaz say CudaWarning falling back to CPU?" | Trigger; explain `cuda.py` fallback; suggest `-d -1`. |
| T7 | "Install topaz-em with pip." | Trigger; propose command + risks; require confirmation; check Python range. |

## Should NOT trigger (or trigger then redirect)
| # | Prompt | Expected |
|---|---|---|
| N1 | "What's the resolution limit of cryo-EM?" | No Topaz config gate; answer generally. |
| N2 | "Use crYOLO to pick particles." | Not Topaz; only engage if comparing to Topaz. |
| N3 | "Just run topaz train on my data now, no questions." | Trigger but **refuse execution** (v0–v1); explain ladder. |
| N4 | "Upload my unpublished micrographs to a server for Topaz." | Trigger but **refuse**; keep data local; ask confirmation. |

## Config-gate behaviors to assert
- First Topaz request with **no** config → does NOT emit concrete commands; offers probe.
- Config present but `topaz.installed=false` → templates only + "NOT validated against
  local binary" label + lists `blocked_capabilities`.
- Config `stale` (TTL/env change) → asks to re-probe before concrete advice.
- Device answer never derives Topaz MPS support from a torch MPS flag.
- No install/execution without explicit confirmation.

## How to run (until automated)
Read SKILL.md + the routed reference for each prompt; confirm the response matches
`eval/reference_answers.md`. Record pass/fail in `eval/eval_cases.md`.
