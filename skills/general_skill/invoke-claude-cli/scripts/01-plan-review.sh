#!/usr/bin/env bash
# Pattern 1: Plan review.
# An external agent has produced a plan or diff. We hand it to claude as a
# read-only critic and parse a structured verdict.
#
# Inputs:
#   $1 — path to file containing the plan or diff
#
# Output (stdout): JSON object: {"verdict": "...", "reasons": [...]}

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
You have no tools. Read the input on stdin, judge it, and return JSON per the schema.
Be concise. Reasons should be specific, not generic.'

# Pure Q&A: no tools, no session, capped budget, cheap model.
# Rollout policy: always run non-interactive Claude CLI with bypassPermissions
# so it never stalls on an internal permission prompt. With --tools "", there is
# no tool surface; the calling agent remains the approval/feedback gate.
# Use --bare only when API-key auth is available; Claude Max / claude.ai
# desktop login is disabled by --bare and reports is_error: true / Not logged in.
BASE_ARGS=(--no-session-persistence)
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  BASE_ARGS=(--bare "${BASE_ARGS[@]}")
fi

# Run pure critique from a neutral cwd. Non-bare Claude Code sees cwd/git
# dynamic context even when tools are disabled; avoid biasing the review.
# In -p/non-TTY mode Claude skips workspace-trust prompts, so use only a cwd
# the caller already trusts (here: an empty temp dir).
RUN_CWD=$(mktemp -d)
trap 'rm -rf "$RUN_CWD"' EXIT

ENVELOPE=$(
  cat "$PLAN_PATH" \
    | (cd "$RUN_CWD" && claude -p \
        "${BASE_ARGS[@]}" \
        --tools "" \
        --permission-mode bypassPermissions \
        --effort max \
        --model haiku \
        --max-budget-usd 0.05 \
        --append-system-prompt "$ROLE" \
        --output-format json \
        --json-schema "$SCHEMA" \
        "Review the content on stdin and respond per the schema.")
)

# Surface errors immediately
if [[ "$(echo "$ENVELOPE" | jq -r '.is_error')" == "true" ]]; then
  echo "claude reported error: $(echo "$ENVELOPE" | jq -r '.result')" >&2
  exit 1
fi

# Extract the schema-validated payload. Current Claude Code uses
# .structured_output; older builds put a JSON string in .result.
echo "$ENVELOPE" | jq -c 'if .structured_output != null then .structured_output else (.result | fromjson) end'
