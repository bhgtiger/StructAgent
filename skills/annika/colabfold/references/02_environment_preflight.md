# Environment preflight

Package manifest requires Python >=3.10. Its core console entry points are colabfold_batch and colabfold_search. Prediction extras pull AlphaFold/JAX-related dependencies; an install is not a trivial package action.

Before a future execution workflow, capture:
- exact ColabFold version and command help;
- Python, JAX, CUDA/driver, GPU architecture, and model-weight status;
- MSA host choice and data-privacy approval;
- input/result paths, compute/time budget, and overwrite/archive decision.

Local MSA search needs prepared MMseqs2 databases and substantial disk/RAM. It is not an automatic fallback. NVIDIA/CUDA is the practical prediction route; GPU Amber relaxation is documented as unsupported on AMD/ROCm and Apple Silicon.

Docker CLI presence alone is not evidence of a functioning NVIDIA runtime or compatible image.