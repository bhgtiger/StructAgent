#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_deepemhancer.sh — portable launcher for DeepEMhancer.
#
# Activates a DeepEMhancer conda environment, makes sure the pip-installed
# CUDA 11 libraries are on LD_LIBRARY_PATH, sets a conservative GPU-memory
# policy, then execs `deepemhancer` with whatever arguments you pass.
#
# It does NOT choose scientific flags for you and it processes maps ONLY on
# the local machine — it never uploads, copies, moves, or deletes map data.
# The calling skill is responsible for picking correct, source-verified flags
# and for getting the user's confirmation before a real (GPU) run.
#
# Usage:
#   run_deepemhancer.sh --env <name|prefix> [--conda-sh <path>] -- <deepemhancer args...>
#
# Everything after `--` is passed verbatim to deepemhancer. Example:
#   run_deepemhancer.sh --env deepemhancer -- \
#       -i half1.mrc -i2 half2.mrc -o out.mrc -p tightTarget -g 0 -b 4
#
# Options:
#   --env NAME|PREFIX   conda env name or full prefix path (required)
#   --conda-sh PATH     path to conda's profile.d/conda.sh (auto-detected if omitted)
#   --no-allow-growth   do NOT set TF_FORCE_GPU_ALLOW_GROWTH=true (default: set it)
#   --dry-run           print the resolved command and environment, do not run
#   -h, --help          show this help
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_REF=""
CONDA_SH=""
ALLOW_GROWTH=1
DRY_RUN=0

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

# --- parse runner options up to `--` ---------------------------------------
DEH_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)            ENV_REF="${2:-}"; shift 2 ;;
    --conda-sh)       CONDA_SH="${2:-}"; shift 2 ;;
    --no-allow-growth) ALLOW_GROWTH=0; shift ;;
    --dry-run)        DRY_RUN=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    --)               shift; DEH_ARGS=("$@"); break ;;
    *) echo "run_deepemhancer.sh: unknown runner option '$1' (did you forget '--' before the deepemhancer args?)" >&2; exit 2 ;;
  esac
done

if [[ -z "$ENV_REF" ]]; then
  echo "run_deepemhancer.sh: --env <name|prefix> is required." >&2; exit 2
fi
if [[ ${#DEH_ARGS[@]} -eq 0 ]]; then
  echo "run_deepemhancer.sh: no deepemhancer arguments given after '--'." >&2; exit 2
fi

# --- locate conda.sh (prefer the user's own conda; site-shared paths last) --
if [[ -z "$CONDA_SH" ]]; then
  cands=()
  command -v conda >/dev/null 2>&1 && \
    cands+=("$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh")
  cands+=( \
      "$HOME/miniconda3/etc/profile.d/conda.sh" \
      "$HOME/anaconda3/etc/profile.d/conda.sh" \
      "$HOME/mambaforge/etc/profile.d/conda.sh" \
      "$HOME/miniforge3/etc/profile.d/conda.sh" \
      "/soft/anaconda-new/etc/profile.d/conda.sh")
  for cand in "${cands[@]}"; do
    [[ -n "$cand" && -f "$cand" ]] && { CONDA_SH="$cand"; break; }
  done
fi
if [[ -z "$CONDA_SH" || ! -f "$CONDA_SH" ]]; then
  echo "run_deepemhancer.sh: could not find conda.sh. Pass --conda-sh <path>." >&2; exit 3
fi

# --- activate --------------------------------------------------------------
# shellcheck disable=SC1090
source "$CONDA_SH"
conda activate "$ENV_REF"

# --- make pip CUDA-11 libs discoverable (defensive; the env's activate.d
#     hook normally does this, but not every env has one). Resolve the python
#     minor version by glob so this works for any interpreter, not just 3.10. -
NVD=""
for cand in "${CONDA_PREFIX:-}"/lib/python3.*/site-packages/nvidia; do
  [[ -d "$cand" ]] && { NVD="$cand"; break; }
done
if [[ -n "$NVD" && -d "$NVD" ]]; then
  for sub in cublas cuda_cupti cuda_nvrtc cuda_runtime cudnn cufft curand cusolver cusparse nccl; do
    [[ -d "$NVD/$sub/lib" ]] && export LD_LIBRARY_PATH="$NVD/$sub/lib:${LD_LIBRARY_PATH:-}"
  done
fi

# --- conservative GPU memory policy (mitigates cuDNN-init / OOM on shared GPUs)
if [[ "$ALLOW_GROWTH" -eq 1 && -z "${TF_FORCE_GPU_ALLOW_GROWTH:-}" ]]; then
  export TF_FORCE_GPU_ALLOW_GROWTH=true
fi

DEH_BIN="$(command -v deepemhancer || true)"
if [[ -z "$DEH_BIN" ]]; then
  echo "run_deepemhancer.sh: 'deepemhancer' not found in env '$ENV_REF'. Is it installed? (see setup_deepemhancer_env.sh)" >&2
  exit 4
fi

echo "run_deepemhancer.sh: env=$CONDA_PREFIX"
echo "run_deepemhancer.sh: deepemhancer=$DEH_BIN"
echo "run_deepemhancer.sh: TF_FORCE_GPU_ALLOW_GROWTH=${TF_FORCE_GPU_ALLOW_GROWTH:-<unset>}"
echo "run_deepemhancer.sh: command -> deepemhancer ${DEH_ARGS[*]}"

# Non-fatal warning: DeepEMhancer asserts (late, after model load) if the -o
# output already exists. We only warn — we never delete the user's file.
out_path=""
for ((i = 0; i < ${#DEH_ARGS[@]}; i++)); do
  case "${DEH_ARGS[$i]}" in
    -o|--outputMap) out_path="${DEH_ARGS[$((i + 1))]:-}" ;;
  esac
done
if [[ -n "$out_path" && -e "$out_path" ]]; then
  echo "run_deepemhancer.sh: WARNING: output '$out_path' already exists; DeepEMhancer will abort rather than overwrite. Use a new -o, or remove/rename it first." >&2
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "run_deepemhancer.sh: --dry-run set; not executing."
  exit 0
fi

exec deepemhancer "${DEH_ARGS[@]}"
