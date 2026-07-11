#!/usr/bin/env bash
# Pattern 01: read-only analysis.
# Ask Codex to explain something about a repo WITHOUT editing it. The final
# answer is captured to a file via -o (robust; no scraping of interleaved stdout).
#
# Usage: 01-analyze-readonly.sh <repo-dir> <question> [out-file]
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> <question> [out-file]}"
QUESTION="${2:?usage: $0 <repo-dir> <question> [out-file]}"
OUT="${3:-codex-analysis.txt}"

# GNU timeout ('timeout' on this host, 'gtimeout' if installed via coreutils).
TIMEOUT="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_CMD=""
if [ -n "$TIMEOUT" ]; then TIMEOUT_CMD="$TIMEOUT 300"; else echo "warn: no timeout/gtimeout; running without a wall-clock guard" >&2; fi

# Preflight: auth + repo, so we fail fast instead of after a noisy retry.
codex login status >/dev/null 2>&1 || { echo "Not logged in: run 'codex login'." >&2; exit 1; }
git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "$REPO is not a Git repo." >&2; exit 1; }

# read-only sandbox; prompt on stdin (trailing '-'); -o writes ONLY the final
# message (note: no trailing newline). $TIMEOUT_CMD is intentionally unquoted.
printf '%s\n' "$QUESTION
Constraints: do not modify any files. Cite file paths and line numbers for each claim." \
  | $TIMEOUT_CMD codex -C "$REPO" -s read-only exec -o "$OUT" -

echo "Final answer written to: $OUT" >&2
