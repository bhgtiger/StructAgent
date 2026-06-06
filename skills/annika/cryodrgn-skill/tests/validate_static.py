#!/usr/bin/env python3
"""Static validator for the cryodrgn-skill (checks the SKILL, not cryoDRGN).

Mechanically verifies the structural invariants of the installed, VALIDATED,
execution-capable skill so a reviewer has objective pass/fail criteria:

  1. all named reference files exist;
  2. SKILL.md has YAML frontmatter with name == cryodrgn-skill and a 1.x
     version (the first execution-capable, live-verified release pins 1.0.0);
  3. a config-state capability table with all six states exists;
  4. every command block in SKILL.md / references / eval docs carries the
     realized label scheme: a `[config-state: ...]` tag plus a
     `[VALIDATED: cryoDRGN 4.2.1]` tag citing the captured help. Commands are
     now runnable (with confirmation), so the old mandatory `[not-run]` /
     `[live-unverified]` tags are NOT required and standalone command lines are
     permitted;
  5. the env probe's entire command surface stays read-only / allowlisted with
     no install/download/job tokens, and it ships a forbidden-token guard
     (the probe is and remains read-only, even though the skill may run jobs);
  6. configs/site_config.local.md is the per-machine stub, not a shipped report
     for one specific host;
  7. the probe compiles and imports.

Run:  python3 tests/validate_static.py   (exit 0 = pass, 1 = fail)
This validator runs NO cryoDRGN and makes no network call.
"""
from __future__ import annotations

import importlib.util
import os
import py_compile
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
REFS = os.path.join(SKILL_ROOT, "references")
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
PROBE = os.path.join(SKILL_ROOT, "scripts", "cryodrgn_env_probe.py")
LOCAL_CONFIG = os.path.join(SKILL_ROOT, "configs", "site_config.local.md")

REQUIRED_REFS = [
    "00_scope_and_trust.md", "01_source_map.md",
    "02_config_session_and_environment.md", "03_cli_reference.md",
    "04_data_model_and_formats.md", "05_core_workflows.md",
    "06_interoperability.md", "07_safety_license_privacy.md",
    "08_validation_and_benchmarks.md", "09_troubleshooting.md",
    "10_decision_trees.md",
]
CONFIG_STATES = ["absent", "stale", "blocked", "partial", "ready", "unknown"]
# Realized label scheme for the execution-capable release: a config-state tag
# plus a validation tag citing the captured cryoDRGN 4.2.1 --help. `[not-run]`
# is reserved for illustrative/destructive examples and `[run-with-confirmation]`
# marks commands that touch real data/compute; neither is required on every
# block, and `[live-unverified]` has been retired (live help is now captured).
CANONICAL_LABELS = ["[config-state:", "[VALIDATED: cryoDRGN"]
# A standalone cryoDRGN command line (excludes `usage:`, `#` comments, inline
# backticked mentions, and `python3 .../cryodrgn_env_probe.py`).
CMD_RE = re.compile(r"^\s*\$?\s*(cryodrgn|cryodrgn_utils)\s+\S")

results = []  # (ok, label, detail)


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def iter_fenced_blocks(text):
    """Yield (block_text, lines, start_lineno) for each ``` fenced block."""
    lines = text.splitlines()
    in_block = False
    buf = []
    start = 0
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            if in_block:
                yield ("\n".join(buf), buf, start)
                buf = []
                in_block = False
            else:
                in_block = True
                start = i
            continue
        if in_block:
            buf.append(line)
    # An unterminated block would be a markdown error; surface it as content.
    if in_block:
        yield ("\n".join(buf), buf, start)


# --- 1. references exist ------------------------------------------------------
missing = [r for r in REQUIRED_REFS if not os.path.isfile(os.path.join(REFS, r))]
check(not missing, "references exist",
      "missing: " + ", ".join(missing) if missing else f"{len(REQUIRED_REFS)} present")

# --- 2. frontmatter: name + 1.x version ---------------------------------------
fm_ok = False
fm_detail = "SKILL.md not found"
if os.path.isfile(SKILL_MD):
    sk = read(SKILL_MD)
    if sk.startswith("---"):
        end = sk.find("\n---", 3)
        front = sk[3:end] if end != -1 else ""
        m = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
        vm = re.search(r"^version:\s*([0-9][^\s]*)\s*$", front, re.MULTILINE)
        name_ok = bool(m) and m.group(1) == "cryodrgn-skill"
        ver = vm.group(1) if vm else None
        # First execution-capable, live-verified release pins 1.0.0; accept 1.x.
        ver_ok = bool(ver) and re.match(r"^1(\.|$)", ver) is not None
        if name_ok and ver_ok:
            fm_ok = True
            fm_detail = f"name: cryodrgn-skill; version: {ver}"
        elif not name_ok:
            fm_detail = f"name not cryodrgn-skill (got {m.group(1) if m else 'none'})"
        else:
            fm_detail = f"version not 1.x (got {ver or 'none'}; expected 1.0.0)"
    else:
        fm_detail = "no leading --- frontmatter"
check(fm_ok, "frontmatter present + name cryodrgn-skill + version 1.x", fm_detail)

# --- 3. config-state capability table -----------------------------------------
cfg_text = ""
cfg_path = os.path.join(REFS, "02_config_session_and_environment.md")
if os.path.isfile(cfg_path):
    cfg_text = read(cfg_path)
has_all_states = all(s in cfg_text for s in CONFIG_STATES)
has_table = ("Allowed" in cfg_text and "Forbidden" in cfg_text
             and "capability" in cfg_text.lower())
# also require SKILL.md to surface the same table
sk_states = os.path.isfile(SKILL_MD) and all(s in read(SKILL_MD) for s in CONFIG_STATES)
check(has_all_states and has_table and sk_states, "config-state capability table",
      "all six states + Allowed/Forbidden table in ref 02 and states in SKILL.md"
      if (has_all_states and has_table and sk_states)
      else f"states={has_all_states} table={has_table} skill={sk_states}")

# --- 4. realized labels on every command block --------------------------------
# RELAXED for the execution-capable release: a fenced block containing a
# cryoDRGN command must carry the config-state tag AND the VALIDATED tag. We no
# longer require [not-run]/[live-unverified], and standalone command lines are
# allowed (the skill may emit and run concrete commands with confirmation).
label_failures = []
scan_files = [("SKILL.md", SKILL_MD)] + [
    (r, os.path.join(REFS, r)) for r in REQUIRED_REFS]
EXTRA_DOCS = [
    os.path.join(SKILL_ROOT, "tests", "trigger_tests.md"),
    os.path.join(SKILL_ROOT, "tests", "eval", "eval_cases.md"),
    os.path.join(SKILL_ROOT, "tests", "eval", "reference_answers.md"),
]
scan_files += [(os.path.relpath(p, SKILL_ROOT), p) for p in EXTRA_DOCS]
for name, path in scan_files:
    if not os.path.isfile(path):
        continue
    text = read(path)
    # every fenced block containing a command line must carry the realized tags
    for block_text, block_lines, start in iter_fenced_blocks(text):
        if any(CMD_RE.match(ln) for ln in block_lines):
            missing_labels = [lb for lb in CANONICAL_LABELS if lb not in block_text]
            if missing_labels:
                label_failures.append(
                    f"{name} (block @ line {start}): missing {missing_labels}")
check(not label_failures, "realized labels on command blocks",
      "; ".join(label_failures) if label_failures
      else "all command blocks carry [config-state: ...] + [VALIDATED: cryoDRGN ...]")

# --- 5. probe command surface is read-only / allowlisted ----------------------
spec = importlib.util.spec_from_file_location("cryodrgn_env_probe", PROBE)
probe = importlib.util.module_from_spec(spec)
import_ok = True
import_detail = "imported"
try:
    spec.loader.exec_module(probe)
except Exception as exc:  # pragma: no cover - defensive
    import_ok = False
    import_detail = f"import failed: {exc!r}"
check(import_ok, "probe imports", import_detail)

if import_ok:
    cands = probe.enumerate_candidate_commands()
    not_allowed = [c for c in cands if not probe._is_allowed(c)]
    forbidden = [c for c in cands if probe._contains_forbidden(c)]
    check(not not_allowed and not forbidden,
          "probe command surface allowlisted + no forbidden tokens",
          f"{len(cands)} commands; not_allowed={not_allowed}; forbidden={forbidden}")
    # guard exists (explicit no-install/no-download policy on the probe itself)
    guard_ok = (hasattr(probe, "FORBIDDEN_TOKENS")
                and hasattr(probe, "_is_allowed")
                and any(t in probe.FORBIDDEN_TOKENS
                        for t in ("install", "download", "clone")))
    check(guard_ok, "probe ships forbidden-token guard",
          "FORBIDDEN_TOKENS + _is_allowed present" if guard_ok else "guard missing")
    # known-bad commands must be refused BY THE PROBE (the probe stays read-only;
    # actual cryoDRGN jobs are run by the skill with confirmation, not the probe).
    bad = [["pip", "install", "cryodrgn"], ["conda", "create", "-n", "x"],
           ["cryodrgn", "train_vae", "particles.mrcs"], ["curl", "http://x"],
           ["nvidia-smi"], ["cryodrgn", "downsample"], ["git", "clone", "x"],
           ["wget", "x"], ["sbatch", "job.sh"]]
    leaked = [c for c in bad if probe._is_allowed(c)]
    check(not leaked, "probe refuses known-bad commands",
          f"leaked: {leaked}" if leaked else "all refused")
else:
    check(False, "probe command surface allowlisted + no forbidden tokens", "skipped")
    check(False, "probe ships forbidden-token guard", "skipped")
    check(False, "probe refuses known-bad commands", "skipped")

# --- 6. site_config.local.md is the per-machine stub, not a shipped report ----
# Posture: the local report is generated per-host by the probe and is .gitignored;
# it must NOT ship one specific machine's hostname / GPU verdict.
HOST_TOKENS = re.compile(
    r"\b(nvidia|cuda|geforce|rtx|gtx|tesla|quadro|a100|h100|v100|"
    r"driver[ _]version|hostname)\b", re.IGNORECASE)
if os.path.isfile(LOCAL_CONFIG):
    lc = read(LOCAL_CONFIG)
    # Allow the literal probe-invocation line that names the probe script.
    leaked_host = [ln.strip() for ln in lc.splitlines()
                   if HOST_TOKENS.search(ln) and "cryodrgn_env_probe.py" not in ln]
    stub_ok = (not leaked_host) and ("cryodrgn_env_probe.py" in lc)
    stub_detail = ("per-machine stub (no host/GPU verdict; references the probe)"
                   if stub_ok else f"looks like a shipped host report: {leaked_host}")
else:
    # Absent is fine: it is generated per-host and .gitignored.
    stub_ok = True
    stub_detail = "absent (generated per-host, .gitignored) — ok"
check(stub_ok, "site_config.local.md is per-machine stub, not a shipped report",
      stub_detail)

# --- 7. probe compiles --------------------------------------------------------
try:
    py_compile.compile(PROBE, doraise=True)
    check(True, "probe py_compile", "ok")
except py_compile.PyCompileError as exc:
    check(False, "probe py_compile", str(exc))

# --- report -------------------------------------------------------------------
print("cryodrgn-skill static validation")
print("=" * 60)
passed = 0
for ok, label, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    passed += ok
print("=" * 60)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
