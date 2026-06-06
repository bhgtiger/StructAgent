#!/usr/bin/env bash
# Pattern 2: Headless execution with feedback contract.
# An external agent has an approved plan and wants claude to carry it out.
# Claude CLI runs with bypassPermissions so it never stalls on permission UI;
# safety/approval is handled by the calling agent, cwd/worktree, and budget/timeout.
# In -p/non-TTY mode Claude skips workspace-trust prompts. Run this only from
# an intended trusted cwd/worktree/sandbox selected by the parent agent.
#
# Inputs:
#   $1 — path to file containing the approved plan
#
# Output (stdout): structured JSON with status completed|needs_feedback|blocked.
# Audit envelope summary is printed on stderr.

set -euo pipefail

if [[ $# -lt 1 || ! -f "$1" ]]; then
  echo "usage: $0 <path-to-approved-plan>" >&2
  exit 64
fi

PLAN_PATH="$1"

# Tool set for execution. With bypassPermissions this is a tool-availability
# boundary, not a fine-grained command allowlist. Bash remains arbitrary: run this
# only in an intended cwd/worktree/sandbox after the parent agent has approved it.
TOOL_SET=("Edit" "Read" "Write" "Grep" "Glob" "Bash")

# Final answer contract. If Claude needs human feedback, credentials, external
# approval, or a scope decision, it must return status=needs_feedback and stop.
SCHEMA='{
  "type": "object",
  "properties": {
    "status": {"enum": ["completed", "needs_feedback", "blocked"]},
    "summary": {"type": "string"},
    "questions": {"type": "array", "items": {"type": "string"}},
    "changed_files": {"type": "array", "items": {"type": "string"}},
    "verification": {"type": "array", "items": {"type": "string"}},
    "next_steps": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["status", "summary"],
  "additionalProperties": false
}'

ROLE='You are an executor agent invoked by an external planner.
The approved plan is on stdin. Execute it step by step using the tools you have.
You are running headless with bypassPermissions; do not wait for interactive permission UI.
If you need human feedback, credentials, external approval, or a scope decision, stop and return status="needs_feedback" with concise questions.
If the task is impossible without missing inputs/tools, return status="blocked".
Otherwise return status="completed" with summary, changed_files, verification, and next_steps.'

# Generate a session ID up-front so the caller can resume if needed.
SESSION=$(python3 -c "import uuid; print(uuid.uuid4())")

ENVELOPE=$(
  cat "$PLAN_PATH" \
    | claude -p \
        --session-id "$SESSION" \
        --append-system-prompt "$ROLE" \
        --tools "${TOOL_SET[@]}" \
        --permission-mode bypassPermissions \
        --effort max \
        --model sonnet \
        --fallback-model haiku \
        --max-budget-usd 20 \
        --output-format json \
        --json-schema "$SCHEMA" \
        "Execute the plan provided on stdin."
)

# Always log the envelope to stderr for audit
echo "$ENVELOPE" | jq '{is_error, num_turns, total_cost_usd, permission_denials, session_id, stop_reason, terminal_reason, status: .structured_output.status}' >&2

if [[ "$(echo "$ENVELOPE" | jq -r '.is_error')" == "true" ]]; then
  echo "claude reported error: $(echo "$ENVELOPE" | jq -r '.result')" >&2
  exit 1
fi

# Permission denials should be rare with bypassPermissions; if present, surface
# them as a runtime/flag mismatch for the parent agent to inspect.
DENIALS=$(echo "$ENVELOPE" | jq -r '.permission_denials | length')
if [[ "$DENIALS" -gt 0 ]]; then
  echo "WARNING: claude had $DENIALS permission denials despite bypassPermissions:" >&2
  echo "$ENVELOPE" | jq '.permission_denials' >&2
fi

PAYLOAD=$(echo "$ENVELOPE" | jq -c 'if .structured_output != null then .structured_output else (.result | fromjson? // {"status":"completed","summary":.result}) end')
STATUS=$(echo "$PAYLOAD" | jq -r '.status // "completed"')
echo "Session: $SESSION (resume with: claude --resume $SESSION)" >&2
if [[ "$STATUS" == "needs_feedback" ]]; then
  echo "Claude needs feedback; ask the user the questions in stdout, then resume this session." >&2
elif [[ "$STATUS" == "blocked" ]]; then
  echo "Claude reported blocked; inspect stdout and decide whether to resume." >&2
fi
echo "$PAYLOAD"
