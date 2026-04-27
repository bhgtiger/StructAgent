#!/usr/bin/env bash
# run_acedrg.sh — AceDRG wrapper with explicit input mode and residue-code validation.
#
# Required (exactly one input mode):
#   --smiles "<SMILES>"      |
#   --smiles-file ligand.smi |
#   --mol ligand.mol         |
#   --mmcif ligand.cif
#
#   --resname LIG            1–3 uppercase alphanumeric chars
#   --out-prefix LIG         basename for AceDRG outputs
#
# Optional:
#   --dry-run                resolve everything and exit 0
#   --force                  allow overwriting outputs and existing CLIBD_MON code
#
# The wrapper:
#   - sources the CCP4 setup
#   - validates the residue code (regex ^[A-Z0-9]{1,3}$)
#   - warns if the residue code already exists in $CLIBD_MON
#   - runs acedrg with the chosen input mode
#   - writes everything (resolved command, input copy, stdout, stderr, generated CIF/PDB)
#     to ccp4_runs/acedrg_<timestamp>/

set -euo pipefail

SMILES=""; SMILES_FILE=""; MOL_FILE=""; MMCIF_FILE=""
RESNAME=""; OUT_PREFIX=""
DRY_RUN=0; FORCE=0

die() { echo "[FAIL] $*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smiles)      SMILES="${2:-}";      shift 2 ;;
    --smiles-file) SMILES_FILE="${2:-}"; shift 2 ;;
    --mol)         MOL_FILE="${2:-}";    shift 2 ;;
    --mmcif)       MMCIF_FILE="${2:-}";  shift 2 ;;
    --resname)     RESNAME="${2:-}";     shift 2 ;;
    --out-prefix)  OUT_PREFIX="${2:-}";  shift 2 ;;
    --dry-run)     DRY_RUN=1;            shift   ;;
    --force)       FORCE=1;              shift   ;;
    -h|--help)     awk 'NR==1{next} /^[^#]/{exit} /^#/{sub(/^# ?/,""); print}' "$0"; exit 0 ;;
    *) die "Unknown arg: $1" ;;
  esac
done

# Exactly one input mode.
MODES=0
[ -n "$SMILES" ]      && MODES=$((MODES+1))
[ -n "$SMILES_FILE" ] && MODES=$((MODES+1))
[ -n "$MOL_FILE" ]    && MODES=$((MODES+1))
[ -n "$MMCIF_FILE" ]  && MODES=$((MODES+1))
[ "$MODES" -eq 1 ] || die "Exactly one of --smiles / --smiles-file / --mol / --mmcif is required (got $MODES)"

[ -n "$RESNAME" ]    || die "--resname is required"
[ -n "$OUT_PREFIX" ] || die "--out-prefix is required"

# Residue-code validation.
if ! [[ "$RESNAME" =~ ^[A-Z0-9]{1,3}$ ]]; then
  die "--resname must be 1–3 uppercase alphanumeric chars (got: $RESNAME)"
fi

# Input file readability.
[ -z "$SMILES_FILE" ] || [ -r "$SMILES_FILE" ] || die "--smiles-file not readable: $SMILES_FILE"
[ -z "$MOL_FILE"    ] || [ -r "$MOL_FILE"    ] || die "--mol not readable: $MOL_FILE"
[ -z "$MMCIF_FILE"  ] || [ -r "$MMCIF_FILE"  ] || die "--mmcif not readable: $MMCIF_FILE"

# Resolve setup script.
CCP4_SETUP="${CCP4_SETUP:-}"
if [ -z "$CCP4_SETUP" ] || [ ! -f "$CCP4_SETUP" ]; then
  for p in /Applications/ccp4-*/bin/ccp4.setup-sh \
           /opt/xtal/ccp4-*/bin/ccp4.setup-sh \
           "$HOME"/ccp4-*/bin/ccp4.setup-sh; do
    [ -f "$p" ] && CCP4_SETUP="$p" && break
  done
fi
[ -n "$CCP4_SETUP" ] && [ -f "$CCP4_SETUP" ] || die "ccp4.setup-sh not found. Run scripts/check_env.sh."

# Run directory.
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="ccp4_runs/acedrg_${TS}"
mkdir -p "$RUN_DIR"

# Warn on existing CLIBD_MON entry.
EXISTING=""
EXISTING=$(bash -lc "source \"$CCP4_SETUP\" >/dev/null 2>&1 && \
  ls \"\$CLIBD_MON/$(echo "$RESNAME" | tr '[:upper:]' '[:lower:]' | cut -c1)/$RESNAME.cif\" 2>/dev/null" || true)
if [ -n "$EXISTING" ]; then
  echo "[WARN] Residue code '$RESNAME' already exists in CLIBD_MON: $EXISTING"
  if [ "$FORCE" -eq 0 ] && [ -e "${OUT_PREFIX}.cif" ]; then
    die "Output ${OUT_PREFIX}.cif exists and CLIBD_MON has '$RESNAME'. Pass --force to proceed deliberately."
  fi
fi

# Save input copy.
INPUT_COPY=""
case 1 in
  *)
    if [ -n "$SMILES" ]; then
      INPUT_COPY="$RUN_DIR/input.smi"
      printf '%s\n' "$SMILES" > "$INPUT_COPY"
    elif [ -n "$SMILES_FILE" ]; then
      INPUT_COPY="$RUN_DIR/input.smi"; cp -f "$SMILES_FILE" "$INPUT_COPY"
    elif [ -n "$MOL_FILE" ]; then
      INPUT_COPY="$RUN_DIR/input.mol"; cp -f "$MOL_FILE" "$INPUT_COPY"
    elif [ -n "$MMCIF_FILE" ]; then
      INPUT_COPY="$RUN_DIR/input.cif"; cp -f "$MMCIF_FILE" "$INPUT_COPY"
    fi
    ;;
esac

# Build acedrg command from preset + input mode + residue/out-prefix.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRESET_FILE="$SKILL_DIR/presets/acedrg_default.txt"
[ -r "$PRESET_FILE" ] || die "Preset not found: $PRESET_FILE"

PRESET_FLAGS=()
while IFS= read -r line; do
  case "$line" in
    ''|\#*) continue ;;
  esac
  # shellcheck disable=SC2206
  PRESET_FLAGS+=( $line )
done < "$PRESET_FILE"

ACEDRG_ARGS=( "${PRESET_FLAGS[@]}" -r "$RESNAME" -o "$OUT_PREFIX" )
if [ -n "$SMILES" ]; then
  ACEDRG_ARGS+=( --smi "$SMILES" )
elif [ -n "$SMILES_FILE" ]; then
  ACEDRG_ARGS+=( -i "$INPUT_COPY" )
elif [ -n "$MOL_FILE" ]; then
  ACEDRG_ARGS+=( -m "$INPUT_COPY" )
elif [ -n "$MMCIF_FILE" ]; then
  ACEDRG_ARGS+=( -c "$INPUT_COPY" )
fi

# Save resolved command.
{
  echo "# Resolved at $(date -u +%FT%TZ)"
  echo "# CCP4_SETUP=$CCP4_SETUP"
  printf 'acedrg '
  printf '%q ' "${ACEDRG_ARGS[@]}"
  echo
} > "$RUN_DIR/command.sh"
chmod +x "$RUN_DIR/command.sh"

echo "[ENV]    source $CCP4_SETUP"
echo "[INPUT]  $INPUT_COPY"
echo "[CMD]    acedrg ${ACEDRG_ARGS[*]}"
echo "[RUN]    $RUN_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[DRY-RUN] Exiting without execution."
  exit 0
fi

# CCP4's setup script references some env vars (e.g. MANPATH) without guards;
# relax nounset just for the source so it doesn't trip `set -u`.
set +u
# shellcheck disable=SC1090
source "$CCP4_SETUP"
set -u
( cd "$RUN_DIR" && acedrg "${ACEDRG_ARGS[@]}" \
    > acedrg.log \
    2> acedrg.err )
RC=$?

echo "[EXIT] $RC"
echo "[LOG]  $RUN_DIR/acedrg.log"
echo "[LOG]  $RUN_DIR/acedrg.err"
exit $RC
