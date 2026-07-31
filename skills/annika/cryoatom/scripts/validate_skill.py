#!/usr/bin/env python3
"""Static and self-test validator for the portable CryoAtom2 skill package.

  python3 scripts/validate_skill.py [skill_dir]

Checks: required files, SKILL.md frontmatter, no host-specific leakage, no TLS
bypass, no broken relative links, valid JSON, parseable Python, shell syntax,
and the self-tests of the shipped scripts.

Exit 0 when the package is clean, 2 otherwise.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys

REQUIRED = [
    "SKILL.md",
    "references/00_scope_and_trust.md",
    "references/01_configuration.md",
    "references/02_install_routes.md",
    "references/03_cli_and_outputs.md",
    "references/04_versions_and_requirements.md",
    "references/05_scientific_evidence.md",
    "references/06_safety_privacy_licensing.md",
    "references/07_operations_and_troubleshooting.md",
    "templates/site-config.example.json",
    "templates/install_plan.md",
    "templates/readiness_report.md",
    "templates/run_command_plan.md",
    "templates/not_run_command_outline.md",
    "templates/run_cryoatom.sbatch.template",
    "templates/smoke_cryoatom.sbatch.template",
    "templates/build_sif.sbatch.template",
    "scripts/cryoatom_env_probe.py",
    "scripts/check_cryoatom_weights.py",
    "scripts/stage_cryoatom_weights.sh",
    "scripts/cryoatom_launcher.sh",
    "scripts/render_job_template.py",
    "scripts/summarize_cryoatom_output.py",
    "scripts/validate_skill.py",
    "install/cryoatom.def",
    "examples/trigger_tests.md",
    "examples/evals.json",
    "examples/fixture_expectations.json",
]

SELF_TESTING = [
    "scripts/cryoatom_env_probe.py",
    "scripts/check_cryoatom_weights.py",
    "scripts/render_job_template.py",
    "scripts/summarize_cryoatom_output.py",
]

# Host-specific leakage. Split so this file does not match its own patterns.
LEAK_PATTERNS = [
    (r"/home/" + r"[a-z][a-z0-9_-]{2,}/structbio", "an absolute private install path"),
    (r"/gpfs/home\d", "a site-specific home path"),
    (r"\bnksei\d+\b", "an allocation account code"),
    (r"\bgpu_a100\b|\bgpu_h100\b", "a site-specific partition name"),
    (r"\bsnellius\b", "a site name"),
    (r"\bcbuild\b", "a site-specific build partition"),
    (r"/scratch-shared/", "a site-specific scratch path"),
    (r"\bJob_0\d\d\b", "an internal job-log reference"),
]

# Things that must never appear anywhere in the package.
FORBIDDEN_LITERAL = [
    ("--no-check-certificate", "a TLS bypass"),
    ("curl -k ", "a TLS bypass"),
    ("curl --insecure", "a TLS bypass"),
]

# Allowed exceptions: prose that explains why the bypass must not be used.
TLS_CONTEXT_OK = re.compile(
    r"(not\s+needed|not\s+used|do\s+not|does\s+not|don'?t|never|refus|declin|"
    r"must\s+not|forbid|avoid|bypass|deviation|not\s+executed|no\s+wget|"
    r"install\.sh|verified\s+TLS|emitting)", re.IGNORECASE)

# A line that actually invokes the downloader is never acceptable, however it is
# commented; prose mentions are judged by the context window above.
TLS_COMMAND_LINE = re.compile(r"^\s*[#%]?\s*(wget|curl)\b")


def check_frontmatter(text):
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return ["SKILL.md must start with YAML frontmatter"]
    raw = text[4:text.index("\n---\n", 4)]
    keys = []
    for line in raw.splitlines():
        if line and not line.startswith((" ", "\t")) and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    if set(keys) != {"name", "description"}:
        return ["frontmatter keys must be exactly name, description; got %s" % sorted(set(keys))]
    errors = []
    for line in raw.splitlines():
        if line.startswith("name:") and "cryoatom" not in line:
            errors.append("frontmatter name must be cryoatom")
        if line.startswith("description:") and len(line) < 200:
            errors.append("description is too thin to route reliably")
    return errors


def leak_scan(rel, text):
    errors = []
    for pattern, why in LEAK_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            errors.append("%s: %s looks like %s" % (rel, match.group(0), why))
    for literal, why in FORBIDDEN_LITERAL:
        for lineno, line in enumerate(text.splitlines(), 1):
            if literal not in line:
                continue
            if TLS_COMMAND_LINE.match(line):
                errors.append("%s:%d: runnable %s (%s)" % (rel, lineno, literal, why))
                continue
            idx = text.find(line)
            window = text[max(0, idx - 400):idx + len(line) + 400]
            if not TLS_CONTEXT_OK.search(window):
                errors.append("%s:%d: %r appears without a do-not-use explanation (%s)"
                              % (rel, lineno, literal, why))
    return errors


def link_scan(root, path, text):
    errors = []
    rel = os.path.relpath(path, root)
    for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        if not os.path.exists(os.path.join(os.path.dirname(path), target)):
            errors.append("broken link in %s: %s" % (rel, target))
    # Backtick-quoted in-package paths, e.g. `references/02_install_routes.md`
    for target in re.findall(r"`((?:references|templates|scripts|examples|install)/[\w./-]+)`", text):
        if not os.path.exists(os.path.join(root, target)):
            errors.append("dangling reference in %s: %s" % (rel, target))
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", nargs="?",
                    default=str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument("--skip-self-tests", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.skill_dir)
    errors = []

    for rel in REQUIRED:
        if not os.path.isfile(os.path.join(root, rel)):
            errors.append("missing required file: %s" % rel)
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        return 2

    if os.path.basename(root) != "cryoatom":
        errors.append("skill directory must be named cryoatom (found %r)"
                      % os.path.basename(root))

    skill_text = open(os.path.join(root, "SKILL.md")).read()
    errors.extend(check_frontmatter(skill_text))
    if len(skill_text.splitlines()) > 500:
        errors.append("SKILL.md exceeds 500 lines")

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            try:
                text = open(path, errors="strict").read()
            except (UnicodeDecodeError, OSError):
                continue
            if rel != os.path.join("scripts", "validate_skill.py"):
                errors.extend(leak_scan(rel, text))
            if name.endswith(".md"):
                errors.extend(link_scan(root, path, text))

    for rel in ("templates/site-config.example.json", "examples/evals.json",
                "examples/fixture_expectations.json"):
        try:
            data = json.loads(open(os.path.join(root, rel)).read())
        except ValueError as exc:
            errors.append("invalid JSON in %s: %s" % (rel, exc))
            continue
        if rel.endswith("evals.json"):
            ids = [c.get("id") for c in data.get("cases", [])]
            if not ids or len(ids) != len(set(ids)) or any(not i for i in ids):
                errors.append("eval case ids must be present and unique")
            for case in data.get("cases", []):
                if case.get("mode") not in ("text-only", "may-act"):
                    errors.append("eval %s has an invalid mode %r"
                                  % (case.get("id"), case.get("mode")))

    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "scripts")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if not name.endswith((".py", ".sh")):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if name.endswith(".py"):
                try:
                    ast.parse(open(path).read(), filename=rel)
                except SyntaxError as exc:
                    errors.append("syntax error in %s: %s" % (rel, exc))
            elif name.endswith(".sh"):
                proc = subprocess.run(["bash", "-n", path], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, universal_newlines=True)
                if proc.returncode:
                    errors.append("shell syntax error in %s: %s" % (rel, proc.stderr.strip()))
            if not os.access(path, os.X_OK):
                errors.append("%s should be executable" % rel)

    # The pinned identity must stay consistent across the package.
    commit = "856e250df7b784b854b892f1b619d32d51188cef"
    for rel in ("install/cryoatom.def", "scripts/cryoatom_env_probe.py",
                "references/04_versions_and_requirements.md"):
        if commit not in open(os.path.join(root, rel)).read():
            errors.append("pinned commit missing from %s" % rel)

    if not args.skip_self_tests:
        for rel in SELF_TESTING:
            proc = subprocess.run([sys.executable, os.path.join(root, rel), "--self-test"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
            if proc.returncode:
                errors.append("self-test failed for %s: %s %s"
                              % (rel, proc.stdout.strip(), proc.stderr.strip()))
        if shutil.which("bash"):
            proc = subprocess.run(
                ["bash", os.path.join(root, "scripts/stage_cryoatom_weights.sh"),
                 "--cache", "/tmp/cryoatom-validate-nonexistent", "plan"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if proc.returncode or "total download" not in proc.stdout:
                errors.append("stage_cryoatom_weights.sh plan failed: %s" % proc.stderr.strip())

    print(json.dumps({"valid": not errors, "checked_files": len(REQUIRED),
                      "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
