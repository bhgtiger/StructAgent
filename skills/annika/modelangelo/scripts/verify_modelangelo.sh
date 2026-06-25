#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# verify_modelangelo.sh — confirm a ModelAngelo install works (read-only).
#
# Activates the conda env and runs a smoke test: version, subcommand help,
# dependency imports, and (optionally) a torch/CUDA check and a weight-cache
# listing. It does NOT run a build and does NOT touch map data. `model_angelo
# --version` imports torch (not free), so each call is wrapped in a timeout.
#
# Usage:
#   verify_modelangelo.sh --env model_angelo [--check-gpu] [--check-weights]
#                         [--conda-sh PATH] [--timeout SECONDS]
#
# Options:
#   --env NAME        conda env name (default: model_angelo)
#   --check-gpu       also report torch version + torch.cuda.is_available()
#   --check-weights   also list the weight-cache dir (torch.hub.get_dir())
#   --conda-sh PATH   conda.sh to source (auto-detected if omitted)
#   --timeout SECONDS hard timeout per command (default: 180)
#   -h, --help        show this help
# ---------------------------------------------------------------------------
set -uo pipefail   # not -e: we want to run all checks and summarise

ENV_NAME="model_angelo"
CHECK_GPU=0
CHECK_WEIGHTS=0
CONDA_SH=""
TIMEOUT=180

usage() { awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next} {exit}' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)           ENV_NAME="${2:-}"; shift 2 ;;
    --check-gpu)     CHECK_GPU=1; shift ;;
    --check-weights) CHECK_WEIGHTS=1; shift ;;
    --conda-sh)      CONDA_SH="${2:-}"; shift 2 ;;
    --timeout)       TIMEOUT="${2:-}"; shift 2 ;;
    -h|--help)       usage; exit 0 ;;
    *) echo "verify: unknown option '$1'" >&2; exit 2 ;;
  esac
done

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
[[ -f "${CONDA_SH:-}" ]] || { echo "verify: conda.sh not found; pass --conda-sh." >&2; exit 3; }

# shellcheck disable=SC1090
source "$CONDA_SH"
conda activate "$ENV_NAME" 2>/dev/null || { echo "verify: could not activate env '$ENV_NAME'." >&2; exit 4; }

PASS=0; FAIL=0
run() {  # run <label> <cmd...>
  local label="$1"; shift
  if timeout "$TIMEOUT" "$@" >/tmp/ma_verify.$$ 2>&1; then
    echo "  [PASS] $label"
    PASS=$((PASS+1))
  else
    echo "  [FAIL] $label  (exit $?)"
    sed 's/^/         /' /tmp/ma_verify.$$ | tail -4
    FAIL=$((FAIL+1))
  fi
  rm -f /tmp/ma_verify.$$
}

echo "verify_modelangelo.sh: env=$CONDA_PREFIX"
echo "-- core --"
run "model_angelo --version"          model_angelo --version
run "model_angelo --help"             model_angelo --help
run "model_angelo build -h"           model_angelo build -h
run "model_angelo build_no_seq -h"    model_angelo build_no_seq -h
run "model_angelo setup_weights -h"   model_angelo setup_weights -h
run "deps import (model_angelo, esm, pyhmmer, mrcfile, Bio)" \
    python -c "import model_angelo, esm, pyhmmer, mrcfile, Bio; print('deps ok', model_angelo.__version__)"

if [[ "$CHECK_GPU" -eq 1 ]]; then
  echo "-- gpu --"
  run "torch + cuda.is_available()" \
      python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
fi

if [[ "$CHECK_WEIGHTS" -eq 1 ]]; then
  echo "-- weights --"
  HUB="$(timeout "$TIMEOUT" python -c 'import torch; print(torch.hub.get_dir())' 2>/dev/null || true)"
  if [[ -n "$HUB" ]]; then
    echo "  hub dir: $HUB"
    NUC="$HUB/checkpoints/model_angelo_v1.0/nucleotides"
    if [[ -f "$NUC/success.txt" ]]; then
      echo "  [PASS] nucleotides bundle present ($NUC)"; PASS=$((PASS+1))
    else
      echo "  [WARN] nucleotides bundle missing at $NUC (run: model_angelo setup_weights --bundle-name nucleotides)"
    fi
    [[ -f "$HUB/checkpoints/esm1b_t33_650M_UR50S.pt" ]] \
      && echo "  [PASS] ESM-1b present" && PASS=$((PASS+1)) \
      || echo "  [WARN] ESM-1b (esm1b_t33_650M_UR50S.pt) missing"
  else
    echo "  [WARN] could not resolve torch.hub.get_dir()"
  fi
fi

echo ""
echo "verify: $PASS passed, $FAIL failed."
if [[ "$FAIL" -gt 0 ]]; then
  echo "verify: see references/06_troubleshooting.md."
  exit 1
fi
echo "verify: install looks functional. (A clean 'build -h' does NOT guarantee a build"
echo "        succeeds on a given map — that depends on the map/resolution/FASTA.)"
