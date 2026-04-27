#!/usr/bin/env bash
# check_env.sh — validate CCP4 environment by capability group.
# Reports per-workflow status. A missing optional binary does not fail the
# whole skill; only a missing setup script or missing core-refinement binaries
# trigger a non-zero exit.
#
# Exit codes:
#   0  — setup found and core refinement available
#   1  — setup found but core refinement is incomplete
#   2  — CCP4 setup script not found

set -u

CCP4_FAIL=0

note() { echo "  • $*"; }
ok()   { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
bad()  { echo "[FAIL] $*"; CCP4_FAIL=1; }

# 1. Locate ccp4.setup-sh
CCP4_SETUP="${CCP4_SETUP:-}"
if [ -z "$CCP4_SETUP" ] || [ ! -f "$CCP4_SETUP" ]; then
  for p in /Applications/ccp4-*/bin/ccp4.setup-sh \
           /opt/xtal/ccp4-*/bin/ccp4.setup-sh \
           "$HOME"/ccp4-*/bin/ccp4.setup-sh; do
    [ -f "$p" ] && CCP4_SETUP="$p" && break
  done
fi

if [ -z "$CCP4_SETUP" ] || [ ! -f "$CCP4_SETUP" ]; then
  bad "ccp4.setup-sh not found"
  note "Fix options:"
  note "  1) Install CCP4 from https://www.ccp4.ac.uk/download/"
  note "  2) Set CCP4_SETUP to the absolute path of ccp4.setup-sh, e.g."
  note "       export CCP4_SETUP=\"\$HOME/ccp4-9.0/bin/ccp4.setup-sh\""
  note "  3) If only /path/to/ccp4-<version>/start exists, source it for an"
  note "     interactive shell and ask the maintainer for bin/ccp4.setup-sh."
  exit 2
fi

ok "CCP4 setup found: $CCP4_SETUP"

# Helper: probe a binary in a sourced sub-shell so PATH side-effects don't leak.
have() {
  bash -lc "source \"$CCP4_SETUP\" >/dev/null 2>&1 && command -v $1 >/dev/null"
}

# 2. Print key env vars and version
ENV_DUMP=$(bash -lc "source \"$CCP4_SETUP\" >/dev/null 2>&1 && \
  printf 'CCP4=%s\nCLIBD=%s\nCLIBD_MON=%s\nCCP4_SCR=%s\n' \
    \"\${CCP4:-}\" \"\${CLIBD:-}\" \"\${CLIBD_MON:-}\" \"\${CCP4_SCR:-}\"")
echo "$ENV_DUMP" | sed 's/^/  /'

# Refmac5 prints its version on -i; fall back to a generic banner if unavailable.
if have refmac5; then
  VER=$(bash -lc "source \"$CCP4_SETUP\" >/dev/null 2>&1 && refmac5 -i 2>/dev/null | grep -i '^[ ]*version' | head -1" || true)
  [ -n "$VER" ] && note "refmac5: $(echo "$VER" | sed 's/^[ ]*//')"
fi

# 3. Capability groups
report_group() {
  local label="$1"; shift
  local kind="$1"; shift   # "required" or "optional"
  local missing=""
  for bin in "$@"; do
    have "$bin" || missing="$missing $bin"
  done
  if [ -z "$missing" ]; then
    ok "$label: $*"
  elif [ "$kind" = "required" ]; then
    bad "$label missing:$missing"
  else
    warn "$label missing:$missing"
  fi
}

report_group "core refinement"     required refmac5 mtzdump freerflag cad
report_group "ligands"             required acedrg
report_group "molecular replacement" optional phaser molrep
report_group "autobuild"           optional cbuccaneer cnautilus
report_group "data reduction"      optional aimless pointless ctruncate
report_group "optional helpers"    optional sftools pdbset pdbcur privateer servalcat refmacat gemmi

if [ "$CCP4_FAIL" -ne 0 ]; then
  echo ""
  note "core refinement is the v1 baseline; install the missing binaries or"
  note "point CCP4_SETUP at a complete install."
fi

exit $CCP4_FAIL
