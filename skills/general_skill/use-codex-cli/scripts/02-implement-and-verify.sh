#!/usr/bin/env bash
# Pattern 02: focused implementation, then INDEPENDENT verification.
# Codex edits under a workspace-write sandbox; this script (the orchestrator)
# then inspects the diff and runs the tests itself. Codex exiting 0 is NOT
# proof the task succeeded — verify.
#
# Usage: 02-implement-and-verify.sh <repo-dir> <task> [test-cmd]
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> <task> [test-cmd]}"
TASK="${2:?usage: $0 <repo-dir> <task> [test-cmd]}"
TEST_CMD="${3:-}"

TIMEOUT="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_CMD=""
if [ -n "$TIMEOUT" ]; then TIMEOUT_CMD="$TIMEOUT 600"; else echo "warn: no timeout guard" >&2; fi

codex login status >/dev/null 2>&1 || { echo "Not logged in: run 'codex login'." >&2; exit 1; }
git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "$REPO is not a Git repo." >&2; exit 1; }

# workspace-write allows edits inside the repo; still no network-by-default.
printf '%s\n' "$TASK
Constraints: make the smallest change that satisfies the task. Do not commit. List the files you changed and why." \
  | $TIMEOUT_CMD codex -C "$REPO" -s workspace-write exec -o codex-summary.txt -

echo "== Codex summary =="; cat codex-summary.txt; echo
echo "== git diff --stat (verify independently) =="; git -C "$REPO" --no-pager diff --stat; echo

if [ -n "$TEST_CMD" ]; then
  echo "== running tests: $TEST_CMD =="
  if ( cd "$REPO" && eval "$TEST_CMD" ); then
    echo "TESTS PASSED"
  else
    echo "TESTS FAILED — review 'git -C $REPO diff' before keeping the change." >&2
    exit 1
  fi
else
  echo "No test command supplied; inspect 'git -C $REPO diff' before keeping the change." >&2
fi
