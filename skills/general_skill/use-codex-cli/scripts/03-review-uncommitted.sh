#!/usr/bin/env bash
# Pattern 03: independent review of uncommitted changes via `codex exec review`.
# IMPORTANT: -C and -s go in GLOBAL position (before `exec`) — `exec review`
# rejects them after the subcommand. Output is JSONL; we extract the final
# agent_message rather than assuming a stable findings array.
#
# Usage: 03-review-uncommitted.sh <repo-dir> [out-jsonl]
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> [out-jsonl]}"
OUT="${2:-codex-review.jsonl}"

TIMEOUT="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_CMD=""
if [ -n "$TIMEOUT" ]; then TIMEOUT_CMD="$TIMEOUT 300"; else echo "warn: no timeout guard" >&2; fi

codex login status >/dev/null 2>&1 || { echo "Not logged in: run 'codex login'." >&2; exit 1; }
git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "$REPO is not a Git repo." >&2; exit 1; }
if git -C "$REPO" diff --quiet && git -C "$REPO" diff --cached --quiet; then
  echo "warn: no uncommitted changes to review in $REPO" >&2
fi

# read-only; -C/-s GLOBAL; the review target (--uncommitted) is a subcommand flag.
$TIMEOUT_CMD codex -C "$REPO" -s read-only exec review --uncommitted --json > "$OUT" || true

# The final assistant message is the last agent_message item in the JSONL stream.
if command -v python3 >/dev/null 2>&1; then
  python3 - "$OUT" <<'PY'
import json, sys
last = None
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    if ev.get("type") == "turn.failed":
        sys.exit("Review turn failed: %s" % ((ev.get("error") or {}).get("message")))
    item = ev.get("item") or {}
    if item.get("type") == "agent_message":
        last = item.get("text")
print(last or "(no agent_message found; inspect %s)" % sys.argv[1])
PY
else
  echo "python3 not found; open $OUT and read the last agent_message item." >&2
fi
