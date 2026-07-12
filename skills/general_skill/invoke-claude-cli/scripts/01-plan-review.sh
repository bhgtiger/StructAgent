#!/usr/bin/env bash
# Pattern 1: Plan review.
# An external agent has produced a plan or diff. We hand it to claude as a
# read-only critic and parse a structured verdict.
#
# Inputs:
#   $1 — path to file containing the plan or diff
#
# Output (stdout): JSON object: {"verdict": "...", "reasons": [...]}
#
# Verified against claude 2.1.207.

set -euo pipefail

if [[ $# -lt 1 || ! -f "$1" ]]; then
  echo "usage: $0 <path-to-plan-or-diff>" >&2
  exit 64
fi

PLAN_PATH="$1"

# Schema for the answer itself. Forces claude to return parseable JSON.
SCHEMA='{
  "type": "object",
  "properties": {
    "verdict":   {"enum": ["approve", "reject", "revise"]},
    "reasons":   {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "risk_areas":{"type": "array", "items": {"type": "string"}}
  },
  "required": ["verdict", "reasons"],
  "additionalProperties": false
}'

ROLE='You are a code reviewer being called by an external planning agent.
You have no tools. Read the input on stdin, judge it, and return your verdict via the
structured-output schema. Be concise. Reasons should be specific, not generic.'

# Pure Q&A: hermetic, no tools, capped budget + turns, cheap model.
ENVELOPE=$(
  cat "$PLAN_PATH" \
    | claude -p \
        --bare \
        --no-session-persistence \
        --tools "" \
        --model haiku \
        --fallback-model haiku \
        --max-budget-usd 0.05 \
        --max-turns 2 \
        --append-system-prompt "$ROLE" \
        --output-format json \
        --json-schema "$SCHEMA" \
        "Review the content on stdin and respond via the schema."
)

# Surface errors immediately (is_error can be true even though exit code is 0).
if [[ "$(echo "$ENVELOPE" | jq -r '.is_error')" == "true" ]]; then
  echo "claude reported error: $(echo "$ENVELOPE" | jq -r '.result')" >&2
  exit 1
fi

# Prefer the already-parsed structured_output. If the model answered in prose
# instead (clarification/refusal), structured_output is absent — surface that.
if [[ "$(echo "$ENVELOPE" | jq 'has("structured_output")')" == "true" ]]; then
  echo "$ENVELOPE" | jq -c '.structured_output'
else
  echo "claude did not produce structured output; prose reply follows on stderr" >&2
  echo "$ENVELOPE" | jq -r '.result' >&2
  exit 2
fi
