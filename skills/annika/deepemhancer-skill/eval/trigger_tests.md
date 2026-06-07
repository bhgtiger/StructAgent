# Trigger tests (when should this skill activate?)

Checks that the skill's `description` routes correctly. "Activate" = this skill should be selected/consulted.

## Should ACTIVATE

| Prompt | Why |
|---|---|
| "Help me run DeepEMhancer on my cryo-EM map." | Direct tool use |
| "What does `-p highRes` do in deepemhancer?" | CLI question |
| "Can my server run DeepEMhancer?" | Readiness/config |
| "DeepEMhancer says models not found — what now?" | Troubleshooting |
| "How do I post-process my half maps with the deep-learning sharpening tool by Sanchez-Garcia?" | Named method, paraphrased |
| "Wire DeepEMhancer into our CryoSPARC cluster." | Integration |
| "Is `--deepLearningModelDir` correct?" | Flag conflict |
| "Should I feed my sharpened map to DeepEMhancer?" | Input suitability |
| "Plan a deepemhancer command but don't run it." | Config-first planning |

## Should NOT activate (or hand off)

| Prompt | Why not |
|---|---|
| "Sharpen my map in RELION postprocess / Phenix AutoSharpen." | Different tool (note DeepEMhancer as an alternative only if asked) |
| "Run 3D refinement / pick particles in CryoSPARC." | Upstream processing, not DeepEMhancer |
| "Generic TensorFlow install help unrelated to DeepEMhancer." | Out of scope unless tied to DeepEMhancer readiness |
| "Explain cryo-EM resolution / FSC in general." | General concept, not this tool |

## Boundary behaviors (activate, then gate on config + confirmation)

| Prompt | Expected gate |
|---|---|
| "Give me the exact command for /data/x.mrc right now." | Activate → config-first gate; produce/read a config, then plan; run only on confirm |
| "Download the models for me." | Activate → confirm (network + ~705 MB), then `setup_deepemhancer_env.sh --download-models` |
| "Just run it on my map, it's fine." | Activate → require a `ready` config + explicit confirm, then run via the runner; never upload the map |
| "Submit it to Slurm for me." | Activate → needs a site config; do not auto-create wrappers / submit without it |

## Self-check for routing

- The `description` names DeepEMhancer, the key flags, model files, GPU/TF/CUDA, CryoSPARC/HPC, and "config-first" — so readiness, CLI, troubleshooting, and integration prompts all match.
- If a prompt is about a *different* post-processing tool, do not hijack it; mention DeepEMhancer only if the user is comparing.
