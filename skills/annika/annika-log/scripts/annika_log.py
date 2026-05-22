#!/usr/bin/env python3
"""annika_log: project/job folder discipline for Annika.

Subcommands:
  init          <project>
  new           <project> <short_name>
  close         <job_path> <status> [--reason ...] [--superseded-by ...]
  audit         <project>
  hash-input    <project> <file> [--source ...] [--derived-from ...] [--notes ...]
  export-failures <project> [--out PATH]
  export-lessons  <project> [--tool TAG] [--class CLASS] [--out PATH]

Project root resolution:
  <project> may be a bare name (resolved against $ANNIKA_PROJECTS_ROOT or
  the default project root under the user's Documents folder) or an absolute/relative path.

This script is intentionally dependency-free (stdlib only).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ----------------------------------------------------------------------------
# Constants

VALID_STATUS = {"draft", "running", "complete", "failed", "excluded", "superseded"}
INDEX_HEADER = (
    "| job_id | short_name | status | created | completed | primary_output |"
    " error_log | excluded_reason | superseded_by |"
)
INDEX_SEP = (
    "|--------|------------|--------|---------|-----------|----------------|"
    "-----------|-----------------|---------------|"
)
INPUTS_HEADER = "| file | sha256 | source | retrieved | derived_from | notes |"
INPUTS_SEP = "|------|--------|--------|-----------|--------------|-------|"

ERRORS_HEADER = "| ID | Stage | Failure mode | Diagnosis | Fix | Outcome |"

JOB_LOG_TEMPLATE = """# Job {nnn} — {short_name}

- Status: running
- Created: {created}
- Closed:  -
- Tools:   -
- Inputs:  -
- Outputs: -
- Depends on:    -
- Supersedes:    -
- Superseded by: -

## 1. Description
TODO: user request verbatim, agent restatement, objective, success criteria.
See log/description.md.

## 2. Parameters
See log/parameters.json. Key choices:
- TODO

## 3. Steps
1. TODO

## 4. Human decisions / approval gates
See log/decisions.md. If none: "None.".

## 5. Errors & Recovery
See log/errors.md (canonical) + log/errors_detail.md (if present).

## 6. Result
TODO: metrics, pass/fail vs. success criteria, next-step recommendation.

## 7. Lessons
None.
"""

ERRORS_TEMPLATE = """- job_id: {job_id}
- timestamp_iso: {created}
- tool: -
- tool_version: -
- linked_log_files: stdout.log, stderr.log

| ID | Stage | Failure mode | Diagnosis | Fix | Outcome |
|----|-------|--------------|-----------|-----|---------|
"""

DESCRIPTION_TEMPLATE = """# Description — Job {nnn} {short_name}

## User request (verbatim)
TODO

## Agent restatement
TODO

## Objective
TODO

## Success criteria
TODO
"""

PROJECT_NOTES_TEMPLATE = """# {project} — project notes

Free-form decisions, context, links. JOB_LOG.md and INDEX.md are the
machine-readable surface; this file is for prose.
"""

INPUTS_TEMPLATE = f"""# shared_inputs manifest

A file under `shared_inputs/` cannot be cited as a job input unless it has a
row here with sha256 + source + retrieved date.

{INPUTS_HEADER}
{INPUTS_SEP}
"""


# ----------------------------------------------------------------------------
# Helpers

def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def projects_root() -> Path:
    env = os.environ.get("ANNIKA_PROJECTS_ROOT")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Documents" / "Annika_projects"


def resolve_project(project: str) -> Path:
    p = Path(project).expanduser()
    if p.is_absolute() or p.exists():
        return p
    return projects_root() / project


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def next_job_number(proj: Path) -> int:
    n = 0
    for child in proj.iterdir():
        m = re.match(r"^Job_(\d+)_", child.name)
        if m and child.is_dir():
            n = max(n, int(m.group(1)))
    return n + 1


def append_index_row(proj: Path, row: dict) -> None:
    idx = proj / "INDEX.md"
    if not idx.exists():
        raise SystemExit(f"INDEX.md missing under {proj}; run `init` first.")
    cells = [
        row.get("job_id", "-"),
        row.get("short_name", "-"),
        row.get("status", "-"),
        row.get("created", "-"),
        row.get("completed", "-"),
        row.get("primary_output", "-"),
        row.get("error_log", "-"),
        row.get("excluded_reason", "-"),
        row.get("superseded_by", "-"),
    ]
    line = "| " + " | ".join(c if c else "-" for c in cells) + " |\n"
    text = idx.read_text()
    if INDEX_SEP not in text:
        raise SystemExit(f"INDEX.md at {idx} is malformed (missing header).")
    if not text.endswith("\n"):
        text += "\n"
    idx.write_text(text + line)


def update_index_row(proj: Path, job_id: str, updates: dict) -> None:
    idx = proj / "INDEX.md"
    text = idx.read_text().splitlines(keepends=True)
    out = []
    found = False
    for ln in text:
        if ln.startswith("| ") and f"| {job_id} |" in ln and INDEX_HEADER not in ln:
            found = True
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            keys = [
                "job_id", "short_name", "status", "created", "completed",
                "primary_output", "error_log", "excluded_reason", "superseded_by",
            ]
            row = dict(zip(keys, cells))
            row.update({k: v for k, v in updates.items() if v is not None})
            ln = "| " + " | ".join(row.get(k) or "-" for k in keys) + " |\n"
        out.append(ln)
    if not found:
        raise SystemExit(f"INDEX row for {job_id} not found in {idx}.")
    idx.write_text("".join(out))


# ----------------------------------------------------------------------------
# Commands

def cmd_init(args) -> int:
    proj = resolve_project(args.project)
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "shared_inputs").mkdir(exist_ok=True)
    idx = proj / "INDEX.md"
    if not idx.exists():
        idx.write_text(
            f"# {proj.name} — INDEX\n\n{INDEX_HEADER}\n{INDEX_SEP}\n"
        )
    notes = proj / "PROJECT_NOTES.md"
    if not notes.exists():
        notes.write_text(PROJECT_NOTES_TEMPLATE.format(project=proj.name))
    inputs = proj / "shared_inputs" / "INPUTS.md"
    if not inputs.exists():
        inputs.write_text(INPUTS_TEMPLATE)
    print(f"Initialized {proj}")
    return 0


def cmd_new(args) -> int:
    proj = resolve_project(args.project)
    if not (proj / "INDEX.md").exists():
        cmd_init(argparse.Namespace(project=str(proj)))
    n = next_job_number(proj)
    nnn = f"{n:03d}"
    short = re.sub(r"[^A-Za-z0-9_]+", "_", args.short_name).strip("_")
    job_dir = proj / f"Job_{nnn}_{short}"
    if job_dir.exists():
        raise SystemExit(f"{job_dir} already exists.")
    (job_dir / "log").mkdir(parents=True)
    (job_dir / "output").mkdir()
    (job_dir / "scripts").mkdir()

    created = now_iso()
    job_id = f"{proj.name}:Job_{nnn}"

    (job_dir / "JOB_LOG.md").write_text(
        JOB_LOG_TEMPLATE.format(nnn=nnn, short_name=short, created=created)
    )
    (job_dir / "log" / "description.md").write_text(
        DESCRIPTION_TEMPLATE.format(nnn=nnn, short_name=short)
    )
    (job_dir / "log" / "parameters.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "created": created,
                "tool": None,
                "tool_version": None,
                "env": {},
                "params": {},
            },
            indent=2,
        )
    )
    (job_dir / "log" / "stdout.log").write_text("")
    (job_dir / "log" / "stderr.log").write_text("")
    (job_dir / "log" / "errors.md").write_text(
        ERRORS_TEMPLATE.format(job_id=job_id, created=created)
    )
    (job_dir / "log" / "decisions.md").write_text("")

    append_index_row(
        proj,
        {
            "job_id": job_id,
            "short_name": short,
            "status": "running",
            "created": created.split("T")[0],
            "completed": "-",
            "primary_output": "-",
            "error_log": f"Job_{nnn}_{short}/log/errors.md",
            "excluded_reason": "-",
            "superseded_by": "-",
        },
    )

    print(str(job_dir))
    return 0


def _job_id_from_path(job_dir: Path) -> str:
    m = re.match(r"^Job_(\d+)_", job_dir.name)
    if not m:
        raise SystemExit(f"{job_dir} is not a Job_NNN_* folder.")
    return f"{job_dir.parent.name}:Job_{m.group(1)}"


def cmd_close(args) -> int:
    job_dir = Path(args.job_path).expanduser().resolve()
    if not job_dir.is_dir():
        raise SystemExit(f"{job_dir} is not a directory.")
    if args.status not in VALID_STATUS:
        raise SystemExit(f"status must be one of {sorted(VALID_STATUS)}")
    if args.status == "excluded" and not args.reason:
        raise SystemExit("--reason is mandatory when closing as 'excluded'")
    if args.status == "superseded" and not args.superseded_by:
        raise SystemExit("--superseded-by is mandatory when closing as 'superseded'")

    proj = job_dir.parent
    job_id = _job_id_from_path(job_dir)
    closed = now_iso()

    # Stamp JOB_LOG.md
    log_path = job_dir / "JOB_LOG.md"
    text = log_path.read_text()
    text = re.sub(r"^- Status: .*$", f"- Status: {args.status}", text, count=1, flags=re.M)
    text = re.sub(r"^- Closed:.*$", f"- Closed:  {closed}", text, count=1, flags=re.M)
    if args.superseded_by:
        text = re.sub(
            r"^- Superseded by: .*$",
            f"- Superseded by: {args.superseded_by} ({args.reason or 'no reason given'})",
            text,
            count=1,
            flags=re.M,
        )
    log_path.write_text(text)

    # Validate mandatory fields
    issues = _audit_job(job_dir)
    if issues:
        print("WARN — close validation issues:", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)

    update_index_row(
        proj,
        job_id,
        {
            "status": args.status,
            "completed": closed.split("T")[0],
            "excluded_reason": args.reason if args.status == "excluded" else None,
            "superseded_by": args.superseded_by if args.status == "superseded" else None,
        },
    )
    print(f"Closed {job_id} as {args.status}")
    return 1 if issues else 0


def _audit_job(job_dir: Path) -> list[str]:
    issues = []
    log = job_dir / "log"
    must_exist = ["description.md", "parameters.json", "errors.md"]
    for f in must_exist:
        if not (log / f).exists():
            issues.append(f"{job_dir.name}: missing log/{f}")
    jl = job_dir / "JOB_LOG.md"
    if not jl.exists():
        issues.append(f"{job_dir.name}: missing JOB_LOG.md")
        return issues
    text = jl.read_text()
    if "## 6. Result" not in text:
        issues.append(f"{job_dir.name}: JOB_LOG missing '## 6. Result'")
    if "## 7. Lessons" not in text:
        issues.append(f"{job_dir.name}: JOB_LOG missing '## 7. Lessons'")
    else:
        lessons_block = text.split("## 7. Lessons", 1)[1].strip()
        if not lessons_block:
            issues.append(f"{job_dir.name}: '## 7. Lessons' is empty (write 'None.' explicitly)")
    if "TODO" in text:
        issues.append(f"{job_dir.name}: JOB_LOG still contains TODO markers")
    return issues


def cmd_audit(args) -> int:
    proj = resolve_project(args.project)
    issues: list[str] = []
    for child in sorted(proj.iterdir()):
        if child.is_dir() and re.match(r"^Job_\d+_", child.name):
            issues.extend(_audit_job(child))
    if issues:
        for i in issues:
            print(i)
        print(f"\n{len(issues)} issue(s).")
        return 1
    print("audit: clean.")
    return 0


def cmd_hash_input(args) -> int:
    proj = resolve_project(args.project)
    src = Path(args.file).expanduser()
    if not src.is_absolute():
        src = (proj / "shared_inputs" / args.file).resolve()
    if not src.exists():
        raise SystemExit(f"{src} does not exist.")
    digest = sha256_file(src)
    today = _dt.date.today().isoformat()
    shared = (proj / "shared_inputs").resolve()
    rel = src.name if src.parent.resolve() == shared else str(src)
    row = (
        f"| {rel} | {digest} | {args.source or '-'} | {today} | "
        f"{args.derived_from or '-'} | {args.notes or '-'} |\n"
    )
    inputs = proj / "shared_inputs" / "INPUTS.md"
    text = inputs.read_text() if inputs.exists() else INPUTS_TEMPLATE
    if not text.endswith("\n"):
        text += "\n"
    inputs.write_text(text + row)
    print(f"{digest}  {rel}")
    return 0


def cmd_export_failures(args) -> int:
    proj = resolve_project(args.project)
    chunks = []
    for child in sorted(proj.iterdir()):
        if not (child.is_dir() and re.match(r"^Job_\d+_", child.name)):
            continue
        ep = child / "log" / "errors.md"
        if not ep.exists():
            continue
        body = ep.read_text().strip()
        # Skip empty (header-only) error files
        if ERRORS_HEADER not in body:
            continue
        rows = [
            ln for ln in body.splitlines()
            if ln.startswith("| ") and not ln.startswith("| ID ")
            and not ln.startswith("|----")
        ]
        if not rows:
            continue
        chunks.append(f"\n### {child.name}\n\n{body}\n")
    out = f"# {proj.name} — failure export (Supp. Table 3)\n" + "".join(chunks)
    if args.out:
        Path(args.out).write_text(out)
        print(args.out)
    else:
        sys.stdout.write(out)
    return 0


def cmd_export_lessons(args) -> int:
    proj = resolve_project(args.project)
    blocks = []
    for child in sorted(proj.iterdir()):
        if not (child.is_dir() and re.match(r"^Job_\d+_", child.name)):
            continue
        jl = child / "JOB_LOG.md"
        if not jl.exists():
            continue
        text = jl.read_text()
        if "## 7. Lessons" not in text:
            continue
        section = text.split("## 7. Lessons", 1)[1].strip()
        if not section or section.lower().startswith("none"):
            continue
        if args.tool and f"tool_tag: {args.tool}" not in section:
            continue
        if args.failure_class and f"failure_class: {args.failure_class}" not in section:
            continue
        blocks.append(f"\n### {child.name}\n\n{section}\n")
    out = f"# {proj.name} — lessons export\n" + "".join(blocks)
    if args.out:
        Path(args.out).write_text(out)
        print(args.out)
    else:
        sys.stdout.write(out)
    return 0


# ----------------------------------------------------------------------------
# CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="annika_log")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("project"); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("new")
    s.add_argument("project"); s.add_argument("short_name")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("close")
    s.add_argument("job_path")
    s.add_argument("status", choices=sorted(VALID_STATUS))
    s.add_argument("--reason")
    s.add_argument("--superseded-by")
    s.set_defaults(fn=cmd_close)

    s = sub.add_parser("audit"); s.add_argument("project"); s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("hash-input")
    s.add_argument("project"); s.add_argument("file")
    s.add_argument("--source"); s.add_argument("--derived-from"); s.add_argument("--notes")
    s.set_defaults(fn=cmd_hash_input)

    s = sub.add_parser("export-failures")
    s.add_argument("project"); s.add_argument("--out")
    s.set_defaults(fn=cmd_export_failures)

    s = sub.add_parser("export-lessons")
    s.add_argument("project")
    s.add_argument("--tool"); s.add_argument("--class", dest="failure_class")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_export_lessons)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
