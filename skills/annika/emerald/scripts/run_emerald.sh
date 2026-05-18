#!/usr/bin/env bash
# run_emerald.sh — lean EMERALD (Rosetta GALigandDock + density) wrapper.
# Prints the full command before executing; supports --dry-run.
#
# Usage:
#   run_emerald.sh [--dry-run] \
#       --receptor receptor.pdb \
#       --map map.mrc \
#       --reso 3.3 \
#       --params LIG.params \
#       --xml presets/emerald.xml \
#       [--flags presets/emerald_flags.txt] \
#       [--seed site.pdb] \
#       [--nstruct 20] \
#       [--out_prefix emerald_]
#
# Never guesses paths. Any missing required input is a hard failure.

set -euo pipefail

DRY_RUN=0
RECEPTOR=""; MAP=""; RESO=""; PARAMS=""; XML=""
FLAGS=""; SEED=""; NSTRUCT=20; OUT_PREFIX="emerald_"

die() { echo "[FAIL] $*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=1; shift ;;
    --receptor)   RECEPTOR="$2"; shift 2 ;;
    --map)        MAP="$2"; shift 2 ;;
    --reso)       RESO="$2"; shift 2 ;;
    --params)     PARAMS="$2"; shift 2 ;;
    --xml)        XML="$2"; shift 2 ;;
    --flags)      FLAGS="$2"; shift 2 ;;
    --seed)       SEED="$2"; shift 2 ;;
    --nstruct)    NSTRUCT="$2"; shift 2 ;;
    --out_prefix) OUT_PREFIX="$2"; shift 2 ;;
    -h|--help)    grep '^# ' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown arg: $1" ;;
  esac
done

# --- Required inputs (fail loudly, never guess) ---
[ -n "$RECEPTOR" ] && [ -f "$RECEPTOR" ] || die "--receptor <pdb> is required and must exist"
[ -n "$MAP" ]      && [ -f "$MAP" ]      || die "--map <mrc/map> is required and must exist"
[ -n "$RESO" ]                           || die "--reso <Å> is required (use the *local* resolution in the binding site)"
[ -n "$PARAMS" ]   && [ -f "$PARAMS" ]   || die "--params <LIG.params> is required (generate with scripts/make_params.sh)"
[ -n "$XML" ]      && [ -f "$XML" ]      || die "--xml <emerald.xml> is required"
[ -z "$SEED" ] || [ -f "$SEED" ]         || die "--seed points at missing file: $SEED"

# --- Resolve Rosetta binary ---
ROSETTA3="${ROSETTA3:-}"
if [ -z "$ROSETTA3" ]; then
  for p in "$HOME"/rosetta*/main /Applications/rosetta*/main /opt/rosetta*/main; do
    [ -d "$p" ] && ROSETTA3="$p" && break || true
  done
fi
[ -n "$ROSETTA3" ] && [ -d "$ROSETTA3" ] || die "ROSETTA3 not set and no rosetta install auto-detected. See references/install.md."

RS="${ROSETTA_SCRIPTS_BIN:-}"
if [ -z "$RS" ]; then
  for suffix in macosclangrelease linuxgccrelease default.macosclangrelease \
                default.linuxgccrelease static.macosclangrelease static.linuxgccrelease \
                mpi.linuxgccrelease; do
    candidate="$ROSETTA3/source/bin/rosetta_scripts.$suffix"
    if [ -x "$candidate" ]; then RS="$candidate"; break; fi
  done
fi
[ -n "$RS" ] && [ -x "$RS" ] || die "No rosetta_scripts binary found under $ROSETTA3/source/bin. Set ROSETTA_SCRIPTS_BIN to override."

GENFF="$ROSETTA3/database/scoring/score_functions/generic_potential/generic_bonded.round6p.txt"
[ -f "$GENFF" ] || die "GenFF file missing: $GENFF — your Rosetta is pre-2023.06, EMERALD unavailable."

# --- Build command ---
CMD=( "$RS"
  -parser:protocol "$XML"
  -s "$RECEPTOR"
  -in:file:extra_res_fa "$PARAMS"
  -gen_potential
  -score::gen_bonded_params_file scoring/score_functions/generic_potential/generic_bonded.round6p.txt
  -edensity::mapfile "$MAP"
  -edensity::mapreso "$RESO"
  -edensity::grid_spacing 1.0
  -edensity::sliding_window 1
  -edensity::score_sliding_window_context
  -edensity::atom_mask 2
  -nstruct "$NSTRUCT"
  -out:prefix "$OUT_PREFIX"
  -overwrite
)

[ -n "$FLAGS" ] && [ -f "$FLAGS" ] && CMD+=( "@$FLAGS" )

if [ -n "$SEED" ]; then
  # seed overrides -s so the pre-placed ligand is docked within the receptor
  CMD=( "$RS" -parser:protocol "$XML" -s "$SEED" "${CMD[@]:3}" )
fi

echo "[ENV] ROSETTA3=$ROSETTA3"
echo "[ENV] rosetta_scripts=$RS"
echo "[CMD]"
printf '  %q \\\n' "${CMD[@]}" | sed '$ s/ \\$//'

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[DRY-RUN] Exiting without execution."
  exit 0
fi

exec "${CMD[@]}"
