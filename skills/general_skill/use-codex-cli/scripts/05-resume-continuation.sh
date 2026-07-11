#!/usr/bin/env bash
# Pattern 05: two-turn continuation. Turn 1 establishes a thread; turn 2 resumes
# it by EXPLICIT thread id (more reliable than --last, which is cwd-filtered and
# can pick an unrelated session).
#
# Usage: 05-resume-continuation.sh <repo-dir> <first-prompt> <follow-up-prompt>
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> <first-prompt> <follow-up-prompt>}"
P1="${2:?usage: $0 <repo-dir> <first-prompt> <follow-up-prompt>}"
P2="${3:?usage: $0 <repo-dir> <first-prompt> <follow-up-prompt>}"

TIMEOUT="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_CMD=""
if [ -n "$TIMEOUT" ]; then TIMEOUT_CMD="$TIMEOUT 300"; else echo "warn: no timeout guard" >&2; fi

codex login status >/dev/null 2>&1 || { echo "Not logged in: run 'codex login'." >&2; exit 1; }
git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "$REPO is not a Git repo." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 required to read the thread id." >&2; exit 1; }

# Turn 1 — capture JSONL; the thread id is in the thread.started event.
FIRST="$(mktemp)"; trap 'rm -f "$FIRST"' EXIT
printf '%s' "$P1" | $TIMEOUT_CMD codex -C "$REPO" -s read-only exec --json - > "$FIRST"

TID="$(python3 - "$FIRST" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    try:
        ev = json.loads(line)
    except Exception:
        continue
    if ev.get("type") == "thread.started":
        print(ev.get("thread_id", ""))
        break
PY
)"
[ -n "$TID" ] || { echo "Could not find a thread_id in turn 1 output." >&2; exit 1; }
echo "thread id: $TID" >&2

# Turn 2 — resume by explicit id; follow-up prompt on stdin.
printf '%s' "$P2" | $TIMEOUT_CMD codex -C "$REPO" -s read-only exec resume "$TID" -
