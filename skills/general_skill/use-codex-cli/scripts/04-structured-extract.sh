#!/usr/bin/env bash
# Pattern 04: structured extraction with --output-schema.
# Codex's FINAL message is constrained to the schema; -o captures just that
# object (no trailing newline). Validate before trusting it.
#
# Usage: 04-structured-extract.sh <repo-dir> <question> [out-json]
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> <question> [out-json]}"
QUESTION="${2:?usage: $0 <repo-dir> <question> [out-json]}"
OUT="${3:-codex-extract.json}"

TIMEOUT="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_CMD=""
if [ -n "$TIMEOUT" ]; then TIMEOUT_CMD="$TIMEOUT 300"; else echo "warn: no timeout guard" >&2; fi

codex login status >/dev/null 2>&1 || { echo "Not logged in: run 'codex login'." >&2; exit 1; }
git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "$REPO is not a Git repo." >&2; exit 1; }

# Edit this schema to match the fields your code will branch on.
SCHEMA="$(mktemp)"; trap 'rm -f "$SCHEMA"' EXIT
cat > "$SCHEMA" <<'JSON'
{
  "type": "object",
  "properties": {
    "summary": { "type": "string" },
    "risks":   { "type": "array", "items": { "type": "string" } }
  },
  "required": ["summary", "risks"],
  "additionalProperties": false
}
JSON

printf '%s\n' "$QUESTION
Return an object that matches the provided JSON schema. Do not modify any files." \
  | $TIMEOUT_CMD codex -C "$REPO" -s read-only exec --output-schema "$SCHEMA" -o "$OUT" -

# -o has no trailing newline; json.load handles that fine.
if command -v python3 >/dev/null 2>&1; then
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d,dict) and "summary" in d and "risks" in d; print("valid schema-conforming JSON:"); print(json.dumps(d, indent=2))' "$OUT" \
    || { echo "Output did not validate against the schema — do not trust it." >&2; exit 1; }
else
  echo "python3 not found; validate $OUT against the schema yourself." >&2
fi
