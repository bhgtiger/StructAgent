#!/usr/bin/env bash
# Run ONE delegated gathering task with the Codex CLI and keep a full audit trail.
#
# Usage: run_codex_task.sh <project_root> <task_id> <brief_path_relative_to_root>
# Env (optional):
#   CODEX_MODEL        model override; default = whatever ~/.codex/config.toml sets
#   CODEX_EFFORT       reasoning effort (default: high)
#   CODEX_TIMEOUT_S    wall-clock limit in seconds (default: 5400)
#   CODEX_NETWORK      1 = allow network inside the workspace-write sandbox (default: 1)
#
# Writes logs/codex_<task>_{prompt.md,events.jsonl,final.md,stderr.txt,status.txt}.
# The prompt = tasks/_common_rules.md + the brief, so every run is reproducible.
# Never trust exit 0 alone: this script also scans the event stream for failures.
# Verified against codex-cli 0.172 (`codex exec --help`): -C, -s, -c, -m, --json, -o,
# --skip-git-repo-check. Re-check `codex exec --help` if the CLI has moved on.
set -u
if [ "$#" -ne 3 ]; then echo "usage: $0 <project_root> <task_id> <brief_rel_path>" >&2; exit 2; fi
ROOT="$(cd "$1" && pwd)"; TASK="$2"; BRIEF="$3"
RULES="$ROOT/tasks/_common_rules.md"
[ -f "$RULES" ] || { echo "missing $RULES" >&2; exit 2; }
[ -f "$ROOT/$BRIEF" ] || { echo "missing $ROOT/$BRIEF" >&2; exit 2; }
command -v codex >/dev/null 2>&1 || { echo "codex CLI not found" >&2; exit 2; }

LOG="$ROOT/logs/codex_${TASK}"
mkdir -p "$ROOT/logs"
{ echo "# Task $TASK — brief: $BRIEF"; echo; cat "$RULES"; echo; cat "$ROOT/$BRIEF"; } > "${LOG}_prompt.md"

ARGS=(-C "$ROOT" -s workspace-write --skip-git-repo-check -c "model_reasoning_effort=${CODEX_EFFORT:-high}")
[ "${CODEX_NETWORK:-1}" = "1" ] && ARGS+=(-c sandbox_workspace_write.network_access=true)
[ -n "${CODEX_MODEL:-}" ] && ARGS+=(-m "$CODEX_MODEL")

TO=""
if command -v timeout >/dev/null 2>&1; then TO="timeout ${CODEX_TIMEOUT_S:-5400}";
elif command -v gtimeout >/dev/null 2>&1; then TO="gtimeout ${CODEX_TIMEOUT_S:-5400}";
else echo "warning: no timeout/gtimeout; running without a wall-clock limit" >&2; fi

date -u +"%Y-%m-%dT%H:%M:%SZ start codex=$(codex --version 2>/dev/null | head -1) model=${CODEX_MODEL:-config-default} effort=${CODEX_EFFORT:-high}" > "${LOG}_status.txt"
# shellcheck disable=SC2086
$TO codex exec "${ARGS[@]}" --json -o "${LOG}_final.md" - < "${LOG}_prompt.md" > "${LOG}_events.jsonl" 2> "${LOG}_stderr.txt"
RC=$?
FAILS=$(grep -c -E '"type":"(turn\.failed|error)"' "${LOG}_events.jsonl" 2>/dev/null || true)
date -u +"%Y-%m-%dT%H:%M:%SZ end exit=$RC failure_events=${FAILS:-0}" >> "${LOG}_status.txt"
if [ "$RC" -ne 0 ] || [ "${FAILS:-0}" != "0" ] || [ ! -s "${LOG}_final.md" ]; then
  echo "TASK $TASK NEEDS ATTENTION: exit=$RC failure_events=${FAILS:-0} final_message=$([ -s "${LOG}_final.md" ] && echo present || echo MISSING)" >&2
  [ "$RC" -eq 0 ] && RC=1
fi
exit $RC
