#!/usr/bin/env python3
"""Mechanically verify citations in gathered source inventories.

Catches the cheap-to-detect fabrication modes of delegated gatherers:
  * `path:line` / `path:start-end` citations whose file is missing or whose line
    is past EOF;
  * "Verbatim `path:a-b`:" fenced excerpts that do not match the cited lines;
  * inventories that cite web URLs but carry no `fetched YYYY-MM-DD` date at all;
  * inventories that do not end with a "Gaps / unknowns" section.
Saved page/paper text copies (a header with `URL:` and a fetch date in the first
15 lines) are evidence, not inventories: only their local citations are checked.
It then prints a random sample of cited lines so a human/agent can eyeball that
each quote supports the claim next to it (the part a script cannot judge).

Stdlib only, Python >= 3.8. Read-only except for the optional --report file.

Usage:
  python3 check_citations.py --root <project> [--sources sources] [--sample 12]
                             [--seed 0] [--report sources/crosscheck/citation_check.txt]
                             [--prefix artifacts --prefix references ...]
Citations must be project-root-relative paths that start with one of the prefixes
(default: the first component of --sources, e.g. `sources` or `artifacts`, plus `tmp`).
Exit code: 0 = no errors (warnings allowed), 1 = errors found, 2 = bad arguments.
"""
import argparse
import os
import random
import re
import sys
from pathlib import Path

def build_patterns(prefixes):
    """Citation regexes for project-root-relative paths starting with one of `prefixes`."""
    alt = "|".join(re.escape(p) for p in sorted(set(prefixes), key=len, reverse=True))
    local = re.compile(
        r"(?<![\w/.-])(?:\./)?((?:" + alt + r")/[A-Za-z0-9_.@+%=/-]+):(\d+)(?:[-–](\d+))?(?!\d)"
    )
    verbatim = re.compile(
        r"Verbatim[^\n`]*`((?:" + alt + r")/[^`:\n]+):(\d+)(?:[-–](\d+))?`[^\n]*\n+"
        r"(`{3,}|~{3,})[^\n]*\n(.*?)\n\4[ \t]*(?:\n|$)",
        re.S,
    )
    return local, verbatim


URL = re.compile(r"https?://[^\s)>\]`'\"|]+")
FETCHED = re.compile(
    r"(?:fetch(?:ed| date)|clone(?:d| date| completed)|accessed|retrieved)[^\n0-9]{0,24}\d{4}-\d{2}-\d{2}", re.I)
COPY_URL = re.compile(r"^\s*(?:source |effective )?url:\s*https?://", re.I | re.M)
GAPS_HEADING = re.compile(r"^#{1,4}\s*(gaps|gaps\s*/\s*unknowns|unknowns|gaps and unknowns)\b", re.I | re.M)
PRUNE_DIR_NAMES = {"raw", ".git", "node_modules", "__pycache__"}


def is_clone(d):
    return (d / ".git").exists()


def iter_inventories(sources):
    for dirpath, dirnames, filenames in os.walk(sources):
        d = Path(dirpath)
        keep = []
        for name in dirnames:
            sub = d / name
            if name in PRUNE_DIR_NAMES or is_clone(sub):
                continue
            keep.append(name)
        dirnames[:] = keep
        for f in filenames:
            if f.endswith(".md") and "_verbatim" not in f:
                yield d / f


class LineCache:
    def __init__(self):
        self._c = {}

    def get(self, p):
        if p not in self._c:
            try:
                self._c[p] = p.read_text(errors="replace").splitlines()
            except (OSError, UnicodeDecodeError):
                self._c[p] = None
        return self._c[p]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="project root; citations are resolved relative to it")
    ap.add_argument("--sources", default="sources", help="evidence folder under root (default: sources)")
    ap.add_argument("--sample", type=int, default=12, help="number of cited lines to print for eyeballing")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--report", help="also write the report to this path (relative to root)")
    ap.add_argument("--prefix", action="append", default=[],
                    help="top-level folder citations may start with (repeatable); "
                         "default: first component of --sources, plus tmp")
    args = ap.parse_args()
    LOCAL_CIT, VERBATIM = build_patterns(args.prefix or [Path(args.sources).parts[0], "tmp"])

    root = Path(args.root).resolve()
    sources = root / args.sources
    if not sources.is_dir():
        print("error: %s is not a directory" % sources, file=sys.stderr)
        return 2

    cache = LineCache()
    errors, warnings, cited = [], [], []
    n_files = n_copies = n_local = n_verbatim = n_urls = 0

    for inv in sorted(iter_inventories(sources)):
        rel = inv.relative_to(root)
        text = inv.read_text(errors="replace")
        head = "\n".join(text.splitlines()[:15])
        is_copy = bool(COPY_URL.search(head) and FETCHED.search(head))
        local = LOCAL_CIT.findall(text)
        urls = [] if is_copy else URL.findall(text)
        if is_copy:
            n_copies += 1
        elif local or urls:
            n_files += 1
        else:
            continue  # no citations at all: not an inventory

        for path, a, b in local:
            n_local += 1
            target = root / path
            lines = cache.get(target) if target.is_file() else None
            if lines is None:
                errors.append("%s: cites missing/unreadable file %s:%s" % (rel, path, a))
                continue
            start, end = int(a), int(b or a)
            if start < 1 or end < start or end > len(lines):
                errors.append("%s: out-of-range %s:%s%s (file has %d lines)"
                              % (rel, path, a, "-" + b if b else "", len(lines)))
                continue
            cited.append((str(rel), path, start, lines[start - 1]))

        for m in VERBATIM.finditer(text):
            n_verbatim += 1
            path, a, b, _fence, body = m.groups()
            lines = cache.get(root / path) if (root / path).is_file() else None
            if lines is None:
                continue  # already reported as missing above
            start, end = int(a), int(b or a)
            actual = [l.rstrip() for l in lines[start - 1:end]]
            quoted = [l.rstrip() for l in body.splitlines()]
            if actual != quoted:
                errors.append("%s: verbatim excerpt does not match %s:%s-%d" % (rel, path, a, end))

        if is_copy:
            continue
        n_urls += len(urls)
        if urls and not FETCHED.search(text):
            warnings.append("%s: cites %d URL(s) but has no 'fetched YYYY-MM-DD' date anywhere, e.g. %s"
                            % (rel, len(urls), urls[0]))

        headings = list(re.finditer(r"^#{1,4}\s.*$", text, re.M))
        if not headings or not GAPS_HEADING.match(headings[-1].group(0)):
            warnings.append("%s: last section is not a 'Gaps / unknowns' section" % rel)

    out = [
        "Citation check — root: %s" % root,
        "Inventories checked: %d (plus %d saved page/paper copies)" % (n_files, n_copies),
        "Local path:line citations checked: %d" % n_local,
        "Verbatim excerpts checked: %d" % n_verbatim,
        "Web URLs cited in inventories: %d" % n_urls,
        "Errors: %d   Warnings: %d" % (len(errors), len(warnings)),
    ]
    if errors:
        out += ["", "## Errors"] + ["- " + e for e in errors]
    if warnings:
        out += ["", "## Warnings"] + ["- " + w for w in warnings]
    if cited and args.sample > 0:
        rnd = random.Random(args.seed)
        pick = rnd.sample(cited, min(args.sample, len(cited)))
        out += ["", "## Random sample of cited lines (eyeball: does each line support the claim?)"]
        for inv, path, ln, content in pick:
            out.append("- [%s] %s:%d → %s" % (inv, path, ln, content.strip()[:160]))
    report = "\n".join(out) + "\n"
    print(report, end="")
    if args.report:
        rp = root / args.report
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(report)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
