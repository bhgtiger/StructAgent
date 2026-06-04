#!/usr/bin/env bash
# run_relion.sh - guarded RELION execution wrapper.
#
# Safety model (see SKILL.md "Execution & safety contract"):
#   * DRY-RUN BY DEFAULT. It prints the resolved env + exact command and exits.
#   * It executes ONLY when you pass --execute (tier-X action, needs user approval).
#   * It never guesses inputs: you pass the full relion_* invocation after `--`.
#   * It refuses to write into a path you name with --forbid (e.g. the read-only fixture).
#
# Usage:
#   run_relion.sh -- relion_refine_mpi --o Refine3D/job050/run --i particles.star ...   # dry-run (default)
#   run_relion.sh --execute -- relion_refine_mpi --o Refine3D/job050/run --i ...         # actually run
#   run_relion.sh --execute --mpi 3 -- relion_refine_mpi ...                              # prefix with mpirun -n 3
#   run_relion.sh --execute -- sbatch /path/queue.sh                                      # submit to scheduler
#
# Options:
#   --execute            actually run (default is dry-run)
#   --mpi N              prepend `mpirun -n N` (for relion_*_mpi binaries)
#   --forbid PATH        abort if the command's --o output starts with PATH
#                        (default: $RELION_PROTECT_PATH; set it to a project you want kept read-only)
#   --log FILE           also tee combined output to FILE (only with --execute)
set -uo pipefail

EXECUTE=0
MPI_N=""
LOGFILE=""
# Write-protection: refuse to write a job into a path you want kept read-only.
# Portable default reads from env (empty = unset). On a given host, export e.g.
#   export RELION_PROTECT_PATH=<RELION_PROJECT_FIXTURE>
# or pass --forbid. The skill's execution contract also forbids writing into real projects.
FORBID="${RELION_PROTECT_PATH:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) EXECUTE=1; shift ;;
    --mpi) MPI_N="${2:-}"; shift 2 ;;
    --forbid) FORBID="${2:-}"; shift 2 ;;
    --log) LOGFILE="${2:-}"; shift 2 ;;
    --) shift; break ;;
    -h|--help) grep '^# ' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "[FAIL] unknown arg: $1 (did you forget '--' before the relion command?)" >&2; exit 2 ;;
  esac
done

if [ $# -lt 1 ]; then
  echo "[FAIL] No command after '--'. Skills never guess; pass the full relion_* invocation." >&2
  exit 2
fi

CMD=("$@")

# Extract the --o output rootname for the forbid check.
OUT=""
for ((i=0; i<${#CMD[@]}; i++)); do
  if [ "${CMD[$i]}" = "--o" ] && [ $((i+1)) -lt ${#CMD[@]} ]; then OUT="${CMD[$((i+1))]}"; fi
done
if [ -n "$FORBID" ] && [ -n "$OUT" ]; then
  # resolve OUT against CWD for the prefix test
  ABS_OUT="$OUT"; [[ "$OUT" != /* ]] && ABS_OUT="$(pwd)/$OUT"
  case "$ABS_OUT" in
    "$FORBID"/*|"$FORBID") echo "[FAIL] Refusing: --o '$OUT' writes inside protected path $FORBID" >&2; exit 3 ;;
  esac
fi

# Build the final command (optionally MPI-prefixed).
FINAL=("${CMD[@]}")
if [ -n "$MPI_N" ]; then
  if ! command -v mpirun >/dev/null 2>&1; then echo "[FAIL] --mpi requested but mpirun not found" >&2; exit 2; fi
  FINAL=(mpirun -n "$MPI_N" "${CMD[@]}")
fi

echo "[CWD] $(pwd)"
[ -n "$OUT" ] && echo "[OUT] $OUT"
echo "[CMD] ${FINAL[*]}"

if [ "$EXECUTE" -ne 1 ]; then
  echo "[DRY-RUN] Not executed. Re-run with --execute to launch (tier-X: needs your approval)."
  exit 0
fi

# Sanity: is the program resolvable?
if ! command -v "${FINAL[0]}" >/dev/null 2>&1; then
  echo "[FAIL] '${FINAL[0]}' not on PATH. Check RELION env / site_config.md." >&2
  exit 2
fi

echo "[EXEC] launching now..."
if [ -n "$LOGFILE" ]; then
  "${FINAL[@]}" 2>&1 | tee "$LOGFILE"
  exit "${PIPESTATUS[0]}"
else
  exec "${FINAL[@]}"
fi
