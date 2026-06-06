#!/usr/bin/env bash
# Pattern 3: Multi-turn refinement.
# Open a session, send turns, accumulate context, close. Useful when the
# orchestrating agent wants iterative dialog: critique -> respond -> revise.
#
# Inputs (positional, one prompt per arg):
#   $1, $2, $3, ... — turns to send in order
#
# Output: each turn's structured payload printed in order; session ID printed to stderr.
# If a turn returns status=needs_feedback, ask the user and resume this session.
# In -p/non-TTY mode Claude skips workspace-trust prompts. Keep this in a
# deliberate trusted cwd, or adapt it to run from a neutral temp dir for Q&A.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <turn1> [turn2] [turn3] ..." >&2
  exit 64
fi

SESSION=$(python3 -c "import uuid; print(uuid.uuid4())")
echo "Session: $SESSION" >&2

SCHEMA='{
  "type": "object",
  "properties": {
    "status": {"enum": ["completed", "needs_feedback", "blocked"]},
    "response": {"type": "string"},
    "questions": {"type": "array", "items": {"type": "string"}},
    "next_steps": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["status", "response"],
  "additionalProperties": false
}'

ROLE='You are in a multi-turn dialog with an external orchestrator.
Each turn is one message in that dialog; respond directly and concisely.
You are running headless with bypassPermissions; do not wait for interactive permission UI.
If you need human feedback, credentials, external approval, or a scope decision, return status="needs_feedback" with concise questions and stop.'

first=true
for prompt in "$@"; do
  if $first; then
    SESSION_FLAG=(--session-id "$SESSION")
    first=false
  else
    SESSION_FLAG=(--resume "$SESSION")
  fi

  ENVELOPE=$(
    claude -p \
      "${SESSION_FLAG[@]}" \
      --append-system-prompt "$ROLE" \
      --tools "" \
      --permission-mode bypassPermissions \
      --effort max \
      --model sonnet \
      --max-budget-usd 0.20 \
      --output-format json \
      --json-schema "$SCHEMA" \
      "$prompt"
  )

  if [[ "$(echo "$ENVELOPE" | jq -r '.is_error')" == "true" ]]; then
    echo "claude reported error on turn: $(echo "$ENVELOPE" | jq -r '.result')" >&2
    exit 1
  fi

  PAYLOAD=$(echo "$ENVELOPE" | jq -c 'if .structured_output != null then .structured_output else (.result | fromjson? // {"status":"completed","response":.result}) end')
  STATUS=$(echo "$PAYLOAD" | jq -r '.status // "completed"')
  echo "--- turn ---"
  echo "$PAYLOAD"
  echo
  if [[ "$STATUS" == "needs_feedback" || "$STATUS" == "blocked" ]]; then
    echo "Stop here. Ask the user, then resume with: claude --resume $SESSION" >&2
    break
  fi
done

echo "Resume this session later with: claude --resume $SESSION" >&2
