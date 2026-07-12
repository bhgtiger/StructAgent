#!/usr/bin/env bash
# Pattern 2: Restricted execution.
# An external agent has an approved plan and wants claude to carry it out
# inside a tight tool allowlist. The cwd is the working tree; tools are scoped
# to Edit/Read/Write + a handful of safe Bash subcommands.
#
# Inputs:
#   $1 — path to file containing the approved plan
#
# Output: the run's result on stdout; the JSON envelope summary on stderr.
#
# Verified against claude 2.1.207.

set -euo pipefail

if [[ $# -lt 1 || ! -f "$1" ]]; then
  echo "usage: $0 <path-to-approved-plan>" >&2
  exit 64
fi

PLAN_PATH="$1"

# Tight allowlist using permission-rule syntax. Space + '*' allows args while
# enforcing a word boundary: Bash(git status *) matches "git status -sb" but
# NOT "git status-hack". Compound commands (a && b) require each part to match.
ALLOWED='Edit Read Write Grep Glob Bash(git status *) Bash(git diff *) Bash(npm test *) Bash(pytest *)'

ROLE='You are an executor agent invoked by an external planner.
The plan is on stdin. Execute it step by step using the tools you have.
After each meaningful step, briefly explain what you did and why.
If a step requires a tool you do not have, stop and report it rather than improvising.'

# Generate a session ID up-front so the caller can resume if needed.
SESSION=$(uuidgen | tr 'A-Z' 'a-z')

# dontAsk: auto-deny anything not on the allowlist / read-only set. Bounded by
# both a dollar cap and a turn cap so a stuck loop can't run away.
ENVELOPE=$(
  cat "$PLAN_PATH" \
    | claude -p \
        --session-id "$SESSION" \
        --append-system-prompt "$ROLE" \
        --allowedTools $ALLOWED \
        --permission-mode dontAsk \
        --model sonnet \
        --fallback-model haiku \
        --max-budget-usd 1.00 \
        --max-turns 24 \
        --output-format json \
        "Execute the plan provided on stdin."
)

# Always log the envelope summary to stderr for audit.
echo "$ENVELOPE" | jq '{is_error, num_turns, total_cost_usd, modelUsage, permission_denials, session_id, stop_reason, terminal_reason}' >&2

if [[ "$(echo "$ENVELOPE" | jq -r '.is_error')" == "true" ]]; then
  echo "claude reported error: $(echo "$ENVELOPE" | jq -r '.result')" >&2
  exit 1
fi

# If claude tried to use tools that weren't allowed, surface them.
DENIALS=$(echo "$ENVELOPE" | jq -r '.permission_denials | length')
if [[ "$DENIALS" -gt 0 ]]; then
  echo "WARNING: claude attempted $DENIALS tool call(s) that were denied. Review:" >&2
  echo "$ENVELOPE" | jq '.permission_denials' >&2
fi

echo "Session: $SESSION (resume with: claude --resume $SESSION)" >&2
echo "$ENVELOPE" | jq -r '.result'
