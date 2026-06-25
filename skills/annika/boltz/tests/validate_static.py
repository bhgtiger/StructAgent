#!/usr/bin/env python3
"""Static self-check for the boltz skill (stdlib only; no Boltz needed).

Checks structure, not behavior:
  - SKILL.md has YAML-ish frontmatter with name + description.
  - description <= 1024 chars (skill-creator quick_validate hard limit).
  - all references/00..10 exist and are referenced from SKILL.md.
  - scripts exist and the Python ones byte-compile.
  - evals/evals.json parses and references_answers exists.

Run:  python tests/validate_static.py
Exit 0 = all good.
"""
import json
import os
import py_compile
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errs = []
oks = []


def ok(m): oks.append(m)
def err(m): errs.append(m)


def read(p):
    with open(os.path.join(ROOT, p), "r", errors="replace") as f:
        return f.read()


# --- SKILL.md + frontmatter ---
try:
    skill = read("SKILL.md")
except OSError:
    err("SKILL.md missing")
    skill = ""

if skill.startswith("---"):
    fm = skill.split("---", 2)[1]
    if "name:" in fm:
        ok("frontmatter has name")
    else:
        err("frontmatter missing name")
    # extract description block (folded scalar `description: >-` ... until next top key)
    desc = ""
    if "description:" in fm:
        after = fm.split("description:", 1)[1]
        lines = after.splitlines()
        body = []
        for ln in lines[1:]:
            if ln and not ln.startswith((" ", "\t")) and ":" in ln.split()[0:1] != []:
                break
            if ln.strip() and not ln.lstrip().startswith("#") and \
               (ln.startswith("  ") or ln.startswith("\t") or not ln.strip().endswith(":")):
                body.append(ln.strip())
            elif not ln.strip():
                continue
            else:
                break
        desc = " ".join(body)
    if not desc:
        err("could not extract description")
    elif len(desc) > 1024:
        err(f"description too long: {len(desc)} > 1024 chars")
    else:
        ok(f"description length ok ({len(desc)} chars)")
else:
    err("SKILL.md has no frontmatter")

# --- references exist + are routed ---
refs = [
    "00_scope_and_trust", "01_source_map", "02_install_and_environment",
    "03_cli_reference", "04_input_yaml_schema", "05_core_workflows",
    "06_affinity_workflow", "07_outputs_and_confidence",
    "08_validation_and_benchmarks", "09_troubleshooting", "10_decision_trees",
]
for r in refs:
    p = os.path.join("references", r + ".md")
    if os.path.isfile(os.path.join(ROOT, p)):
        ok(f"exists {p}")
        if r not in skill:
            err(f"{p} exists but is not referenced from SKILL.md")
    else:
        err(f"missing {p}")

# --- scripts ---
for s in ["scripts/boltz_env_probe.py", "scripts/verify_boltz.py"]:
    fp = os.path.join(ROOT, s)
    if not os.path.isfile(fp):
        err(f"missing {s}")
        continue
    try:
        py_compile.compile(fp, doraise=True)
        ok(f"compiles {s}")
    except py_compile.PyCompileError as e:
        err(f"compile error {s}: {e}")
for s in ["scripts/install_boltz.sh"]:
    if os.path.isfile(os.path.join(ROOT, s)):
        ok(f"exists {s}")
    else:
        err(f"missing {s}")

# --- evals ---
try:
    data = json.loads(read("evals/evals.json"))
    n = len(data.get("evals", []))
    ok(f"evals.json parses ({n} evals)") if n else err("evals.json has no evals")
except Exception as e:  # noqa: BLE001
    err(f"evals.json invalid: {e}")
if os.path.isfile(os.path.join(ROOT, "evals/reference_answers.md")):
    ok("exists evals/reference_answers.md")
else:
    err("missing evals/reference_answers.md")

# --- config template ---
if os.path.isfile(os.path.join(ROOT, "configs/site_config.template.md")):
    ok("exists configs/site_config.template.md")
else:
    err("missing configs/site_config.template.md")

# --- report ---
print(f"PASS checks: {len(oks)}")
for e in errs:
    print("  FAIL:", e)
if errs:
    print(f"\n{len(errs)} problem(s).")
    sys.exit(1)
print("\nAll static checks passed.")
