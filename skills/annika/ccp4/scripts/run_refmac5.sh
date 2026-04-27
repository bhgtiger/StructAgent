#!/usr/bin/env bash
# run_refmac5.sh — Refmac5 wrapper with explicit --labin and a no-silent-FreeR rule.
#
# Required:
#   --xyzin model.pdb           input model
#   --hklin data.mtz            input MTZ (must contain the FreeR column named in --labin)
#   --xyzout refined.pdb        output model
#   --hklout refined.mtz        output MTZ
#   --preset xray_default | xray_jellybody | tls
#   --labin "FP=F SIGFP=SIGF FREE=FreeR_flag"
#
# Optional:
#   --ncyc N                    macrocycles (default 10)
#   --libin ligand.cif          AceDRG-style restraint dictionary
#   --keyword-file extra.com    extra Refmac keywords appended verbatim
#   --tls-in tls.in             required when --preset tls
#   --dry-run                   render the keyword script and exit 0
#   --force                     allow overwriting --xyzout / --hklout
#
# Behaviour:
#   - Refuses to overwrite outputs unless --force.
#   - If FREE column missing from MTZ, prints the explicit freerflag command and exits 2.
#   - Writes the generated Refmac keyword script to the run directory before execution.

set -euo pipefail

XYZIN=""; HKLIN=""; XYZOUT=""; HKLOUT=""
PRESET=""; LABIN=""; NCYC=10; LIBIN=""; KEYFILE=""; TLSIN=""
DRY_RUN=0; FORCE=0

die() { echo "[FAIL] $*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --xyzin)        XYZIN="${2:-}";        shift 2 ;;
    --hklin)        HKLIN="${2:-}";        shift 2 ;;
    --xyzout)       XYZOUT="${2:-}";       shift 2 ;;
    --hklout)       HKLOUT="${2:-}";       shift 2 ;;
    --preset)       PRESET="${2:-}";       shift 2 ;;
    --labin)        LABIN="${2:-}";        shift 2 ;;
    --ncyc)         NCYC="${2:-}";         shift 2 ;;
    --libin)        LIBIN="${2:-}";        shift 2 ;;
    --keyword-file) KEYFILE="${2:-}";      shift 2 ;;
    --tls-in)       TLSIN="${2:-}";        shift 2 ;;
    --dry-run)      DRY_RUN=1;             shift   ;;
    --force)        FORCE=1;               shift   ;;
    -h|--help)      awk 'NR==1{next} /^[^#]/{exit} /^#/{sub(/^# ?/,""); print}' "$0"; exit 0 ;;
    *) die "Unknown arg: $1" ;;
  esac
done

[ -n "$XYZIN" ]  || die "--xyzin is required"
[ -n "$HKLIN" ]  || die "--hklin is required"
[ -n "$XYZOUT" ] || die "--xyzout is required"
[ -n "$HKLOUT" ] || die "--hklout is required"
[ -n "$PRESET" ] || die "--preset is required (xray_default | xray_jellybody | tls)"
[ -n "$LABIN" ]  || die "--labin is required (e.g. \"FP=F SIGFP=SIGF FREE=FreeR_flag\")"

[ -r "$XYZIN" ] || die "--xyzin not readable: $XYZIN"
[ -r "$HKLIN" ] || die "--hklin not readable: $HKLIN"
[ -z "$LIBIN" ]  || [ -r "$LIBIN" ]  || die "--libin not readable: $LIBIN"
[ -z "$KEYFILE" ] || [ -r "$KEYFILE" ] || die "--keyword-file not readable: $KEYFILE"

if [ "$PRESET" = "tls" ]; then
  [ -n "$TLSIN" ] || die "--tls-in is required when --preset tls"
  [ -r "$TLSIN" ] || die "--tls-in not readable: $TLSIN"
fi

if [ "$FORCE" -eq 0 ]; then
  [ ! -e "$XYZOUT" ] || die "--xyzout already exists: $XYZOUT (pass --force to overwrite)"
  [ ! -e "$HKLOUT" ] || die "--hklout already exists: $HKLOUT (pass --force to overwrite)"
fi

# Resolve preset path relative to this script.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
case "$PRESET" in
  xray_default)    PRESET_FILE="$SKILL_DIR/presets/refmac5_xray_default.com" ;;
  xray_jellybody) PRESET_FILE="$SKILL_DIR/presets/refmac5_xray_jellybody.com" ;;
  tls)             PRESET_FILE="$SKILL_DIR/presets/refmac5_tls.com" ;;
  *) die "Unknown --preset: $PRESET (xray_default | xray_jellybody | tls)" ;;
esac
[ -r "$PRESET_FILE" ] || die "Preset not found: $PRESET_FILE"

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

# Extract the FREE column from --labin and check it exists in the MTZ.
# We stay text-based here so the wrapper has no Python dependency at this layer;
# mtz_preflight.py is the place for richer checks.
FREE_COL=""
for tok in $LABIN; do
  case "$tok" in
    FREE=*) FREE_COL="${tok#FREE=}" ;;
  esac
done
[ -n "$FREE_COL" ] || die "--labin must include FREE=<column> (e.g. FREE=FreeR_flag)"

if [ "$DRY_RUN" -eq 0 ]; then
  if ! bash -lc "source \"$CCP4_SETUP\" >/dev/null 2>&1 && \
        printf 'HEAD\nEND\n' | mtzdump HKLIN \"$HKLIN\" 2>/dev/null | \
        awk '/Column Labels/{flag=1;next} flag&&NF{print \$0}' | grep -qw \"$FREE_COL\""; then
    cat >&2 <<EOF
[FAIL] FreeR column '$FREE_COL' not found in $HKLIN.
       Generate flags explicitly (skills never auto-create FreeR):

         bash scripts/run_ccp4.sh --stdin <(printf 'END\\n') -- \\
           freerflag HKLIN $HKLIN HKLOUT ${HKLIN%.mtz}_with_free.mtz

       Then re-run with --hklin ${HKLIN%.mtz}_with_free.mtz.
EOF
    exit 2
  fi
fi

# Build the Refmac keyword script in the run directory.
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="ccp4_runs/refmac5_${TS}"
mkdir -p "$RUN_DIR"

KEYS="$RUN_DIR/refmac5.com"
{
  echo "# Refmac5 keywords generated by run_refmac5.sh at $(date -u +%FT%TZ)"
  echo "# Preset: $PRESET ($PRESET_FILE)"
  echo "LABIN $LABIN"
  sed "s/__NCYC__/$NCYC/g" "$PRESET_FILE" | grep -v '^END\s*$'
  if [ -n "$KEYFILE" ]; then
    echo ""
    echo "# --- user override (--keyword-file $KEYFILE) ---"
    cat "$KEYFILE"
    echo "# --- end user override ---"
  fi
  echo "END"
} > "$KEYS"

# Build refmac5 invocation.
REFMAC_ARGS=( HKLIN "$HKLIN" XYZIN "$XYZIN" HKLOUT "$HKLOUT" XYZOUT "$XYZOUT" )
[ -n "$LIBIN" ] && REFMAC_ARGS+=( LIBIN "$LIBIN" )
[ -n "$TLSIN" ] && REFMAC_ARGS+=( TLSIN "$TLSIN" )

echo "[ENV]    source $CCP4_SETUP"
echo "[PRESET] $PRESET ($PRESET_FILE)"
echo "[KEYS]   $KEYS"
echo "[CMD]    refmac5 ${REFMAC_ARGS[*]} < $KEYS"
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
refmac5 "${REFMAC_ARGS[@]}" \
  < "$KEYS" \
  > "$RUN_DIR/refmac5.log" \
  2> "$RUN_DIR/refmac5.err"
RC=$?

echo "[EXIT] $RC"
echo "[LOG]  $RUN_DIR/refmac5.log"
echo "[LOG]  $RUN_DIR/refmac5.err"
exit $RC
