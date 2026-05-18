#!/usr/bin/env bash
# make_params.sh — generate a Rosetta GenFF ligand .params file.
# Two paths, matching the user-chosen "support both" preference:
#   1) antechamber (AmberTools) → AM1-BCC charges, as in the EMERALD paper
#   2) Rosetta's mol2genparams.py → default GenFF charges (acceptable fallback)
#
# Usage:
#   make_params.sh [--dry-run] <ligand.{sdf,mol2,pdb}> <3-letter-code>
#
# Produces:
#   <code>.params  — Rosetta params
#   <code>.pdb     — ligand coords in Rosetta-ready PDB
# Conformers (if generated) go to <code>_confs.pdb.

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

LIG="${1:-}"; CODE="${2:-}"
die() { echo "[FAIL] $*" >&2; exit 2; }

[ -n "$LIG" ]  && [ -f "$LIG" ] || die "Usage: $0 [--dry-run] <ligand file> <3-letter code>"
[ -n "$CODE" ]                  || die "Missing 3-letter code (e.g. LIG)"
[ ${#CODE} -le 3 ]              || die "Code must be ≤3 chars: $CODE"

ROSETTA3="${ROSETTA3:-}"
MOL2GEN="$ROSETTA3/source/scripts/python/public/generic_potential/mol2genparams.py"

if command -v antechamber >/dev/null 2>&1; then
  ROUTE="antechamber"
elif [ -f "$MOL2GEN" ]; then
  ROUTE="mol2genparams"
else
  die "Neither antechamber nor $MOL2GEN is available. Install AmberTools, or supply a pre-made .params file."
fi

echo "[ROUTE] $ROUTE"

if [ "$ROUTE" = "antechamber" ]; then
  CMD_AC=( antechamber -i "$LIG" -fi "${LIG##*.}" -o "${CODE}.mol2" -fo mol2 -c bcc -s 2 -rn "$CODE" )
  CMD_CONV=( python "$MOL2GEN" -s "${CODE}.mol2" --prefix "$CODE" --no_pdb )
  echo "[CMD] ${CMD_AC[*]}"
  echo "[CMD] ${CMD_CONV[*]}"
  [ "$DRY_RUN" -eq 1 ] && { echo "[DRY-RUN] Exiting."; exit 0; }
  "${CMD_AC[@]}"
  [ -f "$MOL2GEN" ] || die "mol2genparams.py missing; cannot convert AM1-BCC mol2 to params."
  "${CMD_CONV[@]}"
else
  CMD=( python "$MOL2GEN" -s "$LIG" --prefix "$CODE" )
  echo "[CMD] ${CMD[*]}"
  [ "$DRY_RUN" -eq 1 ] && { echo "[DRY-RUN] Exiting."; exit 0; }
  "${CMD[@]}"
fi

echo "[DONE] Wrote ${CODE}.params (plus ${CODE}.pdb / ${CODE}_confs.pdb if generated)."
