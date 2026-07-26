#!/usr/bin/env bash
# Pattern 3: Multi-turn refinement.
# Open a session, send turns, accumulate context, close. Useful when the
# orchestrating agent wants iterative dialog: critique -> respond -> revise.
#
# Inputs (positional, one prompt per arg):
#   $1, $2, $3, ... — turns to send in order
#
# Output: each turn's `.result` printed in order; session ID printed to stderr.
#
# Verified against claude 2.1.220.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <turn1> [turn2] [turn3] ..." >&2
  exit 64
fi

SESSION=$(uuidgen | tr 'A-Z' 'a-z')
echo "Session: $SESSION" >&2

ROLE='You are in a multi-turn dialog with an external orchestrator.
Each turn is one message in that dialog; respond to it directly and concisely.'

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
      --model sonnet \
      --max-budget-usd 0.20 \
      --max-turns 2 \
      --output-format json \
      "$prompt"
  )

  if [[ "$(echo "$ENVELOPE" | jq -r '.is_error')" == "true" ]]; then
    echo "claude reported error on turn: $(echo "$ENVELOPE" | jq -r '.result')" >&2
    exit 1
  fi

  echo "--- turn ---"
  echo "$ENVELOPE" | jq -r '.result'
  echo
done

echo "Resume this session later with: claude --resume $SESSION" >&2
