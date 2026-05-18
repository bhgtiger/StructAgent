#!/usr/bin/env bash
# check_env.sh — validate Rosetta/EMERALD environment.
# Exit 0 on success, 1 on failure with numbered fix guidance.

set -u

FAIL=0
note() { echo "  • $*"; }
ok()   { echo "[OK] $*"; }
bad()  { echo "[FAIL] $*"; FAIL=1; }

# 1. Locate rosetta/main
ROSETTA3="${ROSETTA3:-}"
if [ -z "$ROSETTA3" ]; then
  for p in "$HOME"/rosetta*/main /Applications/rosetta*/main /opt/rosetta*/main; do
    [ -d "$p" ] && ROSETTA3="$p" && break || true
  done
fi

if [ -z "$ROSETTA3" ] || [ ! -d "$ROSETTA3" ]; then
  bad "Rosetta 'main' directory not found"
  note "Fix options:"
  note "  1) Read references/install.md and install Rosetta ≥ 2023.06"
  note "  2) Set ROSETTA3 env var to the absolute path of rosetta/main"
  note "     e.g. export ROSETTA3=\"\$HOME/rosetta.binary/main\""
  echo
  exit 1
fi
ok "ROSETTA3: $ROSETTA3"

# 2. Locate a rosetta_scripts binary
BIN_DIR="$ROSETTA3/source/bin"
RS=""
for suffix in macosclangrelease linuxgccrelease default.macosclangrelease \
              default.linuxgccrelease static.macosclangrelease static.linuxgccrelease \
              mpi.linuxgccrelease; do
  candidate="$BIN_DIR/rosetta_scripts.$suffix"
  if [ -x "$candidate" ]; then
    RS="$candidate"
    break
  fi
done

if [ -z "$RS" ]; then
  bad "No rosetta_scripts.* binary found in $BIN_DIR"
  note "Either Rosetta wasn't built, or the build suffix is unusual."
  note "Run: ls $BIN_DIR/rosetta_scripts.*"
  note "Then export ROSETTA_SCRIPTS_BIN=<full path> to override auto-detect."
else
  ok "rosetta_scripts: $RS"
fi

# 3. Verify GenFF params file (required by EMERALD)
GENFF="$ROSETTA3/database/scoring/score_functions/generic_potential/generic_bonded.round6p.txt"
if [ ! -f "$GENFF" ]; then
  bad "GenFF params file missing: $GENFF"
  note "Your Rosetta is likely pre-2023.06. EMERALD needs ≥ 2023.06."
  note "Upgrade: re-download a newer weekly release from rosettacommons.org."
else
  ok "GenFF params: $(basename "$GENFF")"
fi

# 4. Version probe (best-effort)
if [ -n "$RS" ] && [ -f "$ROSETTA3/../.release.json" ]; then
  VERSION=$(grep -oE '"version"\s*:\s*"[^"]+"' "$ROSETTA3/../.release.json" | head -1 || true)
  [ -n "$VERSION" ] && note "Rosetta release: $VERSION"
fi

# 5. Optional: antechamber for ligand params
if command -v antechamber >/dev/null 2>&1; then
  ok "antechamber: $(command -v antechamber) (AM1-BCC params generation available)"
else
  note "antechamber not found — make_params.sh will fall back to mol2genparams.py"
  note "  Install AmberTools for AM1-BCC charges (the EMERALD paper's recipe)."
fi

echo
if [ $FAIL -eq 0 ]; then
  echo "[DONE] Environment looks good for EMERALD."
else
  echo "[DONE] Fix the FAIL lines above before running EMERALD."
fi
exit $FAIL
