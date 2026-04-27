#!/bin/bash
set -euo pipefail
# ─────────────────────────────────────────────────────────
# Launcher for ISOLDE monitored batch runs
# - Single-instance lock (prevents duplicate ChimeraX)
# - macOS popup auto-clicker (disulfide Yes, unparameterised OK, etc.)
# - Runs ChimeraX in GUI mode (ISOLDE requires it)
# ─────────────────────────────────────────────────────────

# ── EDIT THIS ──
SCRIPT="${1:-/path/to/isolde_monitored_template.py}"
# ────────────────

CHIMERAX=$(ls -1d /Applications/ChimeraX-*.app/Contents/MacOS/ChimeraX 2>/dev/null | sort -V | tail -1)
LOCK="${SCRIPT}.launch.lock"
POPUP_PID=""

# ── single-instance guard ──
if [[ -f "$LOCK" ]]; then
  OLD_PID=$(cat "$LOCK" 2>/dev/null || true)
  if [[ -n "${OLD_PID:-}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Another monitored launch is already running (PID $OLD_PID); exiting."
    exit 1
  fi
fi

echo $$ > "$LOCK"
cleanup() {
  if [[ -n "${POPUP_PID:-}" ]]; then
    kill "$POPUP_PID" 2>/dev/null || true
    wait "$POPUP_PID" 2>/dev/null || true
  fi
  rm -f "$LOCK"
}
trap cleanup EXIT INT TERM

echo "ChimeraX: $CHIMERAX"
echo "Script: $SCRIPT"

# ── popup handler (background) ──
(
  while true; do
    osascript -e 'tell application "System Events" to tell process "ChimeraX"
      try
        click button "OK" of front window
      end try
      try
        click button "Yes" of front window
      end try
    end tell' 2>/dev/null
    sleep 2
  done
) &
POPUP_PID=$!
echo "Popup handler PID: $POPUP_PID"

# ── launch ──
"$CHIMERAX" --cmd "runscript $SCRIPT" 2>&1

echo "Done."
