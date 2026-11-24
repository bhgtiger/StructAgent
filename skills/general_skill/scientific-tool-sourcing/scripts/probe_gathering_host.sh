#!/usr/bin/env bash
# Report which gathering tools exist on THIS host (the machine doing the collecting,
# which is often not the target runtime). Read-only: installs nothing, changes nothing.
# Usage: probe_gathering_host.sh [target_cli_name ...]   > logs/gathering_host.txt
set -u
echo "# Gathering host probe — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "host: $(uname -srm)"
echo
printf '%-12s %s\n' tool "version / status"
for t in git gh curl jq python3 pdftotext pdfinfo yt-dlp codex claude shasum sha256sum timeout gtimeout docker apptainer conda pixi; do
  if command -v "$t" >/dev/null 2>&1; then
    case "$t" in
      pdftotext|pdfinfo) v=$("$t" -v 2>&1 | head -1) ;;
      timeout|gtimeout) v="present" ;;
      *) v=$("$t" --version 2>&1 | head -1) ;;
    esac
    printf '%-12s %s\n' "$t" "$v"
  else
    printf '%-12s %s\n' "$t" "MISSING"
  fi
done
echo
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then echo "gh auth: logged in (use 'gh api' — 5000 req/h)"; else echo "gh auth: not logged in (unauthenticated GitHub API — 60 req/h)"; fi
fi
code=$(curl -sS -o /dev/null -m 10 -w '%{http_code}' https://github.com 2>/dev/null) || code=""
if [ -n "$code" ] && [ "$code" != "000" ]; then echo "network: github.com HTTP $code"; else echo "network: github.com unreachable"; fi
if [ "$#" -gt 0 ]; then
  echo
  echo "## Target tool(s) on this host (presence check only; nothing is executed)"
  for t in "$@"; do
    if command -v "$t" >/dev/null 2>&1; then printf '%-20s %s\n' "$t" "$(command -v "$t")"; else printf '%-20s %s\n' "$t" "not installed here"; fi
  done
fi
