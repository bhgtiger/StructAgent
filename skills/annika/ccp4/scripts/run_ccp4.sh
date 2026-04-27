#!/usr/bin/env bash
# run_ccp4.sh — generic CCP4 dispatcher.
#
# Usage:
#   run_ccp4.sh [--dry-run] [--force] [--stdin <file>] -- <ccp4-binary> [args...]
#
# Examples:
#   run_ccp4.sh --dry-run -- mtzdump HKLIN data.mtz
#   run_ccp4.sh --stdin keywords.com -- refmac5 HKLIN d.mtz HKLOUT o.mtz \
#                                              XYZIN m.pdb XYZOUT r.pdb
#   run_ccp4.sh --stdin <(printf 'END\n') -- freerflag HKLIN d.mtz HKLOUT df.mtz
#
# Rules:
#   - Never guesses paths or binaries. The user supplies the full invocation.
#   - Sources CCP4 setup; prints the resolved env and the exact command.
#   - With --dry-run, exits 0 without execution.
#   - With --force, allows overwriting existing outputs the dispatcher can see
#     (HKLOUT / XYZOUT / -o style args). Without --force, refuses to clobber.
#   - Writes everything (resolved command, stdin copy, stdout, stderr) to
#     ccp4_runs/<binary>_<UTC-timestamp>/.

set -euo pipefail

DRY_RUN=0
FORCE=0
STDIN_FILE=""

usage() {
  awk 'NR==1{next} /^[^#]/{exit} /^#/{sub(/^# ?/,""); print}' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force)   FORCE=1;   shift ;;
    --stdin)   STDIN_FILE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    *) echo "[FAIL] Unknown arg: $1" >&2; echo "       Use -- to separate dispatcher flags from the CCP4 command." >&2; exit 2 ;;
  esac
done

if [ $# -lt 1 ]; then
  echo "[FAIL] Supply a CCP4 command after --, e.g. -- mtzdump HKLIN data.mtz" >&2
  echo "       Skills never guess. Aborting." >&2
  exit 2
fi

BIN="$1"; shift
ARGS=( "$@" )

# Resolve setup script.
CCP4_SETUP="${CCP4_SETUP:-}"
if [ -z "$CCP4_SETUP" ] || [ ! -f "$CCP4_SETUP" ]; then
  for p in /Applications/ccp4-*/bin/ccp4.setup-sh \
           /opt/xtal/ccp4-*/bin/ccp4.setup-sh \
           "$HOME"/ccp4-*/bin/ccp4.setup-sh; do
    [ -f "$p" ] && CCP4_SETUP="$p" && break
  done
fi
if [ -z "$CCP4_SETUP" ] || [ ! -f "$CCP4_SETUP" ]; then
  echo "[FAIL] ccp4.setup-sh not found. Run scripts/check_env.sh for fix guidance." >&2
  exit 2
fi

# No-overwrite: scan args for HKLOUT / XYZOUT / -o targets and reject if they exist.
if [ "$FORCE" -eq 0 ]; then
  i=0
  while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
      HKLOUT|XYZOUT|MAPOUT|LIBOUT|SCROUT|XMLOUT)
        next=$((i+1))
        if [ $next -lt ${#ARGS[@]} ] && [ -e "${ARGS[$next]}" ]; then
          echo "[FAIL] Output already exists: ${ARGS[$next]}" >&2
          echo "       Pass --force to overwrite, or pick a different path." >&2
          exit 2
        fi
        ;;
      -o)
        next=$((i+1))
        if [ $next -lt ${#ARGS[@]} ] && [ -e "${ARGS[$next]}" ]; then
          echo "[FAIL] Output already exists: ${ARGS[$next]}" >&2
          echo "       Pass --force to overwrite, or pick a different path." >&2
          exit 2
        fi
        ;;
    esac
    i=$((i+1))
  done
fi

# Run directory.
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="ccp4_runs/${BIN}_${TS}"
mkdir -p "$RUN_DIR"

# Save resolved command and stdin.
{
  echo "# Resolved at $(date -u +%FT%TZ)"
  echo "# CCP4_SETUP=$CCP4_SETUP"
  printf '%q ' "$BIN" "${ARGS[@]}"
  echo
} > "$RUN_DIR/command.sh"
chmod +x "$RUN_DIR/command.sh"

if [ -n "$STDIN_FILE" ]; then
  if [ ! -r "$STDIN_FILE" ]; then
    echo "[FAIL] --stdin file not readable: $STDIN_FILE" >&2
    exit 2
  fi
  cp -f "$STDIN_FILE" "$RUN_DIR/stdin.txt"
fi

echo "[ENV] source $CCP4_SETUP"
echo "[CMD] $BIN ${ARGS[*]}"
[ -n "$STDIN_FILE" ] && echo "[STDIN] $STDIN_FILE -> $RUN_DIR/stdin.txt"
echo "[RUN] $RUN_DIR"

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

if [ -n "$STDIN_FILE" ]; then
  "$BIN" "${ARGS[@]}" \
    < "$RUN_DIR/stdin.txt" \
    > "$RUN_DIR/stdout.log" \
    2> "$RUN_DIR/stderr.log"
else
  "$BIN" "${ARGS[@]}" \
    > "$RUN_DIR/stdout.log" \
    2> "$RUN_DIR/stderr.log"
fi
RC=$?

echo "[EXIT] $RC"
echo "[LOG]  $RUN_DIR/stdout.log"
echo "[LOG]  $RUN_DIR/stderr.log"
exit $RC
