#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_deepemhancer_env.sh — reproducible DeepEMhancer 0.17 GPU environment.
#
# Encodes a recipe verified working on a Linux + NVIDIA RTX 2080 Ti box
# (driver 535 / CUDA 12.2), running DeepEMhancer 0.17 on TensorFlow 2.10 with
# pip-installed CUDA 11.8 + cuDNN 8.6. The same env runs across newer drivers
# because the driver is backward-compatible with the CUDA 11.8 runtime.
#
# This script MUTATES your system: it creates a conda env and installs
# packages, and (only if you pass --download-models) downloads ~705 MB of
# model weights from Zenodo. It therefore refuses to run until you confirm,
# either interactively or with --yes.
#
# It NEVER touches cryo-EM map data and NEVER uploads anything.
#
# Usage:
#   setup_deepemhancer_env.sh --env deepemhancer [--yes] [--download-models]
#   setup_deepemhancer_env.sh --env-prefix /path/to/env --conda-sh /opt/conda/etc/profile.d/conda.sh --yes
#
# Options:
#   --env NAME            create/use a named conda env (mutually exclusive with --env-prefix)
#   --env-prefix PATH     create/use an env at this prefix path
#   --conda-sh PATH       conda.sh to source (auto-detected if omitted)
#   --models-dir PATH     model directory (default: ~/.local/share/deepEMhancerModels/production_checkpoints)
#   --source pypi|github  where to get DeepEMhancer (default: pypi; github falls back to a local/remote clone)
#   --github-url URL      git URL or local path for --source github (default: https://github.com/rsanchezgarc/deepEMhancer)
#   --download-models     also run `deepemhancer --download` into the models dir (network + ~705 MB write)
#   --yes                 skip the interactive confirmation prompt
#   -h, --help            show this help
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_NAME=""
ENV_PREFIX=""
CONDA_SH=""
MODELS_DIR="$HOME/.local/share/deepEMhancerModels/production_checkpoints"
SOURCE="pypi"
GITHUB_URL="https://github.com/rsanchezgarc/deepEMhancer"
DOWNLOAD_MODELS=0
ASSUME_YES=0

# Verified pin set (matches a known-good install) -----------------------------
DEH_VERSION="0.17"
KERAS_CONTRIB_REF="git+https://www.github.com/keras-team/keras-contrib.git@3fc5ef709e061416f4bc8a92ca3750c824b5d2b0"
KERAS_RADAM="keras-rectified-adam==0.20.0"
NVIDIA_PKGS=(
  "nvidia-cuda-runtime-cu11==11.8.89"
  "nvidia-cublas-cu11==11.11.3.6"
  "nvidia-cufft-cu11==10.9.0.58"
  "nvidia-curand-cu11==10.3.0.86"
  "nvidia-cusolver-cu11==11.4.1.48"
  "nvidia-cusparse-cu11==11.7.5.86"
  "nvidia-cudnn-cu11==8.6.0.163"
  "nvidia-cuda-cupti-cu11==11.8.87"
  "nvidia-cuda-nvrtc-cu11==11.8.89"
  "nvidia-nccl-cu11"
)

usage() { sed -n '2,38p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)            ENV_NAME="${2:-}"; shift 2 ;;
    --env-prefix)     ENV_PREFIX="${2:-}"; shift 2 ;;
    --conda-sh)       CONDA_SH="${2:-}"; shift 2 ;;
    --models-dir)     MODELS_DIR="${2:-}"; shift 2 ;;
    --source)         SOURCE="${2:-}"; shift 2 ;;
    --github-url)     GITHUB_URL="${2:-}"; shift 2 ;;
    --download-models) DOWNLOAD_MODELS=1; shift ;;
    --yes)            ASSUME_YES=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "setup: unknown option '$1'" >&2; exit 2 ;;
  esac
done

if [[ -n "$ENV_NAME" && -n "$ENV_PREFIX" ]]; then
  echo "setup: pass only one of --env / --env-prefix." >&2; exit 2
fi
if [[ -z "$ENV_NAME" && -z "$ENV_PREFIX" ]]; then
  echo "setup: one of --env / --env-prefix is required." >&2; exit 2
fi

ENV_FLAG=(); ENV_DESC=""
if [[ -n "$ENV_NAME" ]]; then ENV_FLAG=(-n "$ENV_NAME"); ENV_DESC="name=$ENV_NAME"
else ENV_FLAG=(-p "$ENV_PREFIX"); ENV_DESC="prefix=$ENV_PREFIX"; fi

# --- locate conda.sh -------------------------------------------------------
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
[[ -f "${CONDA_SH:-}" ]] || { echo "setup: conda.sh not found; pass --conda-sh." >&2; exit 3; }

# --- confirm ---------------------------------------------------------------
cat <<PLAN

DeepEMhancer environment setup plan
-----------------------------------
  conda.sh        : $CONDA_SH
  env             : $ENV_DESC
  python          : 3.10  (conda-forge)
  deepemhancer    : $DEH_VERSION  (source: $SOURCE)
  extra wheels    : keras-contrib (pinned), $KERAS_RADAM, nvidia-*-cu11 (CUDA 11.8 / cuDNN 8.6)
  activate hook   : LD_LIBRARY_PATH -> pip CUDA-11 libs
  keras_contrib   : moments() TF2 patch
  models dir      : $MODELS_DIR
  download models : $([[ $DOWNLOAD_MODELS -eq 1 ]] && echo 'YES (~705 MB from Zenodo)' || echo 'no (place .hd5 files yourself)')

This will CREATE/MODIFY a conda environment and install packages.
PLAN
if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "Proceed? [y/N] " ans || ans=""   # closed stdin -> reach the abort below
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "Aborted."; exit 0; }
fi

# --- create env ------------------------------------------------------------
# shellcheck disable=SC1090
source "$CONDA_SH"
export CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-$HOME/.conda/pkgs}"   # writable cache

CREATE=conda
command -v mamba >/dev/null 2>&1 && CREATE=mamba   # mamba+conda-forge dodges broken defaults

echo ">> creating python 3.10 env ($ENV_DESC) via $CREATE / conda-forge"
"$CREATE" create -y "${ENV_FLAG[@]}" -c conda-forge --override-channels python=3.10

PY=(conda run "${ENV_FLAG[@]}" python -m pip)

echo ">> installing DeepEMhancer $DEH_VERSION ($SOURCE)"
if [[ "$SOURCE" == "github" ]]; then
  "${PY[@]}" install "git+$GITHUB_URL" 2>/dev/null || "${PY[@]}" install "$GITHUB_URL"
else
  "${PY[@]}" install "deepemhancer==$DEH_VERSION"
fi

echo ">> installing keras-contrib (pinned) + keras_radam (DEH 0.17 drops these from its deps)"
"${PY[@]}" install --no-deps "$KERAS_CONTRIB_REF"
"${PY[@]}" install --no-deps "$KERAS_RADAM"

echo ">> installing pip CUDA 11.8 / cuDNN 8.6 runtime wheels (TF 2.10 does not bundle them)"
"${PY[@]}" install "${NVIDIA_PKGS[@]}"

# --- activate hook for LD_LIBRARY_PATH -------------------------------------
ENV_PREFIX_RESOLVED="$(conda run "${ENV_FLAG[@]}" python -c 'import sys,os;print(sys.prefix)')"
HOOK_DIR="$ENV_PREFIX_RESOLVED/etc/conda/activate.d"
mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/cuda_libs.sh" <<'HOOK'
#!/usr/bin/env bash
# Add the pip-installed CUDA 11 libs (nvidia-*-cu11) to LD_LIBRARY_PATH.
# Resolve the python minor version by glob (robust to any interpreter version).
for NVD in "$CONDA_PREFIX"/lib/python3.*/site-packages/nvidia; do
  [ -d "$NVD" ] || continue
  for sub in cublas cuda_cupti cuda_nvrtc cuda_runtime cudnn cufft curand cusolver cusparse nccl; do
    if [ -d "$NVD/$sub/lib" ]; then
      export LD_LIBRARY_PATH="$NVD/$sub/lib:${LD_LIBRARY_PATH:-}"
    fi
  done
done
HOOK
echo ">> wrote activate hook: $HOOK_DIR/cuda_libs.sh"

# --- patch keras_contrib for TF 2.x ----------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ">> patching keras_contrib moments() for TF 2.x"
conda run "${ENV_FLAG[@]}" python "$SCRIPT_DIR/patch_keras_contrib.py" \
    --env-prefix "$ENV_PREFIX_RESOLVED"

# --- optional model download -----------------------------------------------
if [[ "$DOWNLOAD_MODELS" -eq 1 ]]; then
  echo ">> downloading model weights into $MODELS_DIR (network + ~705 MB)"
  mkdir -p "$(dirname "$MODELS_DIR")"
  # `deepemhancer --download <dir>` fetches + unzips the production checkpoints.
  conda run "${ENV_FLAG[@]}" deepemhancer --download "$(dirname "$MODELS_DIR")"
else
  echo ">> skipping model download. Ensure these exist in $MODELS_DIR :"
  echo "     deepEMhancer_tightTarget.hd5  deepEMhancer_wideTarget.hd5"
  echo "     deepEMhancer_highRes.hd5      deepEMhancer_masked.hd5 (for -m mode)"
fi

# --- verify ----------------------------------------------------------------
echo ">> verifying install (deepemhancer --version; GPU hidden to avoid contention)"
conda activate "${ENV_NAME:-$ENV_PREFIX}"
CUDA_VISIBLE_DEVICES= timeout 180 deepemhancer --version || echo "WARN: --version did not return cleanly; check the env."

echo ">> DONE. Run maps with:  run_deepemhancer.sh --env ${ENV_NAME:-$ENV_PREFIX} -- -i half1.mrc -i2 half2.mrc -o out.mrc"
