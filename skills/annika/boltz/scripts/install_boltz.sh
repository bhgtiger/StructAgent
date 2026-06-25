#!/usr/bin/env bash
# Consent-gated installer/updater for Boltz (jwohlwend/boltz).
#
# Why consent-gated: installing Boltz pulls Torch + CUDA + RDKit and can take a
# while and a lot of disk. The agent must never install silently. This script
# PRINTS THE PLAN and refuses to act unless you pass --yes.
#
# Usage:
#   scripts/install_boltz.sh                       # dry-run: show the plan only
#   scripts/install_boltz.sh --yes                 # create/use env 'boltz2', GPU build
#   scripts/install_boltz.sh --yes --env myboltz --python 3.11
#   scripts/install_boltz.sh --yes --update        # upgrade boltz in the env
#   scripts/install_boltz.sh --yes --cpu           # CPU-only (slow; not a quality default)
#
# Grounded in upstream README v2.2.1: `pip install boltz[cuda] -U`,
# Python >=3.10,<3.13.
set -euo pipefail

ENV_NAME="boltz2"
PYVER="3.10"
EXTRA="[cuda]"
DO_YES=0
DO_UPDATE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --yes) DO_YES=1 ;;
    --update) DO_UPDATE=1 ;;
    --cpu) EXTRA="" ;;
    --env) ENV_NAME="$2"; shift ;;
    --python) PYVER="$2"; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

CONDA="$(command -v conda || command -v mamba || true)"
PKG="boltz${EXTRA}"

echo "=================================================================="
echo "BOLTZ INSTALL PLAN"
echo "=================================================================="
echo "  conda/mamba : ${CONDA:-<none on PATH>}"
echo "  env name    : ${ENV_NAME}"
echo "  python      : ${PYVER}   (must be >=3.10,<3.13)"
echo "  package     : ${PKG}"
echo "  mode        : $([ $DO_UPDATE -eq 1 ] && echo 'upgrade in existing env' || echo 'create-if-missing + install')"
echo "------------------------------------------------------------------"
echo "  Would run:"
if [ $DO_UPDATE -eq 1 ]; then
  echo "    conda run -n ${ENV_NAME} pip install -U \"${PKG}\""
else
  echo "    conda create -y -n ${ENV_NAME} python=${PYVER}    # if env missing"
  echo "    conda run -n ${ENV_NAME} pip install -U \"${PKG}\""
fi
echo "  Weights/data auto-download to \$BOLTZ_CACHE or ~/.boltz on first run."
echo "=================================================================="

# Guard: Python version constraint.
case "$PYVER" in
  3.10|3.11|3.12) : ;;
  *) echo "ERROR: Python ${PYVER} is outside Boltz's supported >=3.10,<3.13." >&2; exit 3 ;;
esac

if [ $DO_YES -ne 1 ]; then
  echo
  echo "DRY RUN — nothing was changed. Re-run with --yes to proceed."
  exit 0
fi

if [ -z "$CONDA" ]; then
  echo "ERROR: no conda/mamba on PATH; cannot manage an env. Install Miniforge or" >&2
  echo "       activate a Python ${PYVER} env yourself and run: pip install -U '${PKG}'" >&2
  exit 4
fi

echo ">> Proceeding (--yes given)."
if [ $DO_UPDATE -ne 1 ]; then
  if ! "$CONDA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo ">> Creating env ${ENV_NAME} (python ${PYVER})"
    "$CONDA" create -y -n "$ENV_NAME" "python=${PYVER}"
  else
    echo ">> Env ${ENV_NAME} already exists; reusing."
  fi
fi
echo ">> Installing ${PKG} into ${ENV_NAME}"
"$CONDA" run -n "$ENV_NAME" pip install -U "$PKG"
echo ">> Done. Verify with: scripts/verify_boltz.py --env \"\$($CONDA info --base)/envs/${ENV_NAME}\""
