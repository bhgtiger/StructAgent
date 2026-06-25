#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install_modelangelo.sh — reproducible, consent-gated ModelAngelo install.
#
# Wraps the OFFICIAL 3dem/model-angelo install_script.sh: it clones the repo at
# a pinned tag, sources conda, sets TORCH_HOME, and runs the upstream installer
# (which creates a conda env, pip-installs torch + ModelAngelo, and optionally
# downloads ~10 GB of weights). It does NOT reimplement the install — it makes
# the official path reproducible (pinned tag), route-aware, and safe.
#
# This script MUTATES your system (clones a repo, creates a conda env, installs
# packages, and — with --download-weights — downloads ~10 GB). It REFUSES to run
# until you confirm, interactively or with --yes. It NEVER touches cryo-EM data.
#
# Usage:
#   install_modelangelo.sh --route personal --env model_angelo [--yes] \
#       [--tag v1.0.18] [--repo-dir DIR] [--torch-home DIR] [--download-weights]
#   install_modelangelo.sh --route shared --torch-home /public/model_angelo_weights \
#       --download-weights --yes
#
# Options:
#   --route personal|shared   install style (default: personal). 'shared' requires --torch-home.
#   --env NAME                conda env name (default: model_angelo)
#   --tag TAG                 git tag/branch to clone (default: v1.0.18; use 'main' for latest)
#   --repo-dir DIR            where to clone (default: ./model-angelo)
#   --repo-url URL            repo URL (default: https://github.com/3dem/model-angelo.git)
#   --torch-home DIR          set TORCH_HOME (weights cache root; required for --route shared)
#   --download-weights        also download weights (~10 GB: nucleotides + nucleotides_no_seq + ESM-1b)
#   --conda-sh PATH           conda.sh to source (auto-detected if omitted)
#   --yes                     skip the interactive confirmation prompt
#   -h, --help                show this help
# ---------------------------------------------------------------------------
set -euo pipefail

ROUTE="personal"
ENV_NAME="model_angelo"
TAG="v1.0.18"
REPO_DIR="./model-angelo"
REPO_URL="https://github.com/3dem/model-angelo.git"
TORCH_HOME_ARG=""
DOWNLOAD_WEIGHTS=0
CONDA_SH=""
ASSUME_YES=0

usage() { awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next} {exit}' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --route)            ROUTE="${2:-}"; shift 2 ;;
    --env)              ENV_NAME="${2:-}"; shift 2 ;;
    --tag)              TAG="${2:-}"; shift 2 ;;
    --repo-dir)         REPO_DIR="${2:-}"; shift 2 ;;
    --repo-url)         REPO_URL="${2:-}"; shift 2 ;;
    --torch-home)       TORCH_HOME_ARG="${2:-}"; shift 2 ;;
    --download-weights) DOWNLOAD_WEIGHTS=1; shift ;;
    --conda-sh)         CONDA_SH="${2:-}"; shift 2 ;;
    --yes)              ASSUME_YES=1; shift ;;
    -h|--help)          usage; exit 0 ;;
    *) echo "install_modelangelo.sh: unknown option '$1'" >&2; exit 2 ;;
  esac
done

case "$ROUTE" in
  personal|shared) ;;
  *) echo "install: --route must be 'personal' or 'shared'." >&2; exit 2 ;;
esac
if [[ "$ROUTE" == "shared" && -z "$TORCH_HOME_ARG" ]]; then
  echo "install: --route shared requires --torch-home <world-readable dir>." >&2; exit 2
fi
if [[ "$DOWNLOAD_WEIGHTS" -eq 1 && -z "$TORCH_HOME_ARG" && -z "${TORCH_HOME:-}" ]]; then
  echo "install: --download-weights needs TORCH_HOME. Pass --torch-home <dir> (the" >&2
  echo "         upstream install_script.sh hard-errors if TORCH_HOME is unset)." >&2
  exit 2
fi

# --- prerequisites ----------------------------------------------------------
command -v git >/dev/null 2>&1 || { echo "install: 'git' not found; install it first." >&2; exit 3; }

# --- locate conda.sh --------------------------------------------------------
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
  for c in "${cands[@]}"; do
    [[ -n "$c" && -f "$c" ]] && { CONDA_SH="$c"; break; }
  done
fi
[[ -f "${CONDA_SH:-}" ]] || { echo "install: conda.sh not found; pass --conda-sh, or install miniconda3 first." >&2; exit 3; }

EFFECTIVE_TORCH_HOME="${TORCH_HOME_ARG:-${TORCH_HOME:-<unset — weights would go to ~/.cache/torch>}}"

# --- confirm ----------------------------------------------------------------
cat <<PLAN

ModelAngelo install plan
------------------------
  route           : $ROUTE
  conda.sh        : $CONDA_SH
  conda env       : $ENV_NAME   (python 3.11, created by upstream install_script.sh)
  repo            : $REPO_URL @ tag '$TAG'
  clone into      : $REPO_DIR  $( [[ -d "$REPO_DIR" ]] && echo '(exists — will reuse, NOT re-clone)' )
  TORCH_HOME      : $EFFECTIVE_TORCH_HOME
  download weights: $([[ $DOWNLOAD_WEIGHTS -eq 1 ]] && echo 'YES (~10 GB: nucleotides + nucleotides_no_seq + ESM-1b)' || echo 'no (run setup_weights later)')
  installs        : torch==2.9.1 torchvision, then ModelAngelo (pip install .)

This CLONES a repo, CREATES/REUSES a conda env, and INSTALLS packages$([[ $DOWNLOAD_WEIGHTS -eq 1 ]] && echo ' and DOWNLOADS ~10 GB').
It does not touch any cryo-EM map data.
PLAN
if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "Proceed? [y/N] " ans || ans=""   # closed stdin -> abort below
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "Aborted."; exit 0; }
fi

# --- clone (pinned) ---------------------------------------------------------
if [[ -d "$REPO_DIR/.git" || -f "$REPO_DIR/install_script.sh" ]]; then
  echo ">> reusing existing repo at $REPO_DIR (tag not re-checked out)"
else
  echo ">> cloning $REPO_URL @ $TAG -> $REPO_DIR"
  git clone --branch "$TAG" --depth 1 "$REPO_URL" "$REPO_DIR"
fi
[[ -f "$REPO_DIR/install_script.sh" ]] || { echo "install: $REPO_DIR/install_script.sh missing." >&2; exit 4; }

# --- run the OFFICIAL installer (sourced, so its conda activate works here) --
# shellcheck disable=SC1090
source "$CONDA_SH"
if [[ -n "$TORCH_HOME_ARG" ]]; then
  export TORCH_HOME="$TORCH_HOME_ARG"
  mkdir -p "$TORCH_HOME"
fi

pushd "$REPO_DIR" >/dev/null
INSTALL_ARGS=(--name "$ENV_NAME")
[[ "$DOWNLOAD_WEIGHTS" -eq 1 ]] && INSTALL_ARGS+=(--download-weights)
echo ">> running upstream: source install_script.sh ${INSTALL_ARGS[*]}"
# shellcheck disable=SC1091
source ./install_script.sh "${INSTALL_ARGS[@]}"
popd >/dev/null

# --- shared-route wrapper hint ----------------------------------------------
if [[ "$ROUTE" == "shared" ]]; then
  cat <<WRAP

>> shared route: make this wrapper available on all users' PATH (e.g. as 'model_angelo'):
   #!/bin/bash
   source \`which activate\` $ENV_NAME
   model_angelo "\$@"
   # Ensure $TORCH_HOME_ARG is readable+executable by all users (the ESM .pt is chmod 0555 by the installer).
WRAP
fi

echo ""
echo ">> DONE. Verify with:"
echo "   bash $(dirname "$0")/verify_modelangelo.sh --env $ENV_NAME --check-gpu --check-weights"
