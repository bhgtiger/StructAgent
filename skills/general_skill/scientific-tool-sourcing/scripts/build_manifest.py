#!/usr/bin/env python3
"""Write sources/MANIFEST.tsv: one row per gathered file (size, SHA-256, kind),
one row per git clone (URL, HEAD SHA, describe), and flag oversized files.

Use it after gathering so the hand-off can state exactly what evidence exists,
which bytes it was based on, and what is too large to package into a skill.
Also flags `.pdf` files that are not PDFs (publisher/PMC challenge pages saved
under a .pdf name) — exit code 1 if any are found. Paths are project-relative,
never absolute, so the manifest stays valid when the project moves hosts.

Stdlib only, Python >= 3.8. Writes only the manifest file.

Usage:
  python3 build_manifest.py --root <project> [--sources sources] [--max-mb 50]
"""
import argparse
import hashlib
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKIP = {".DS_Store"}


def sha256(p, buf=1 << 20):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(buf), b""):
            h.update(chunk)
    return h.hexdigest()


def git(clone, *args):
    try:
        return subprocess.run(["git", "-C", str(clone)] + list(args), capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def du(path):
    total = 0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                total += (Path(dp) / f).lstat().st_size
            except OSError:
                pass
    return total


def kind_of(p):
    name = p.name.lower()
    parts = {x.lower() for x in p.parts}
    if "raw" in parts:
        return "raw"
    if name.endswith((".pdf",)):
        return "paper-pdf"
    if name.endswith(".txt") and "help" in name:
        return "live-help"
    if name.endswith(".md"):
        return "verbatim" if "_verbatim" in name else "inventory"
    if name.endswith((".json", ".jsonl", ".tsv", ".csv", ".yaml", ".yml")):
        return "data"
    if name.endswith((".html", ".htm")):
        return "raw"
    return "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--sources", default="sources")
    ap.add_argument("--max-mb", type=float, default=50.0, help="flag files larger than this")
    ap.add_argument("--out", default=None, help="default: <sources>/MANIFEST.tsv")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    sources = root / args.sources
    if not sources.is_dir():
        print("error: %s is not a directory" % sources, file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else sources / "MANIFEST.tsv"
    limit = int(args.max_mb * 1024 * 1024)

    rows, big, fake_pdf = [], [], []
    per_class = defaultdict(lambda: [0, 0])
    for dirpath, dirnames, filenames in os.walk(sources):
        d = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            sub = d / name
            if name == ".git":
                continue
            if (sub / ".git").exists():
                url = git(sub, "remote", "get-url", "origin")
                head = git(sub, "rev-parse", "HEAD")
                desc = git(sub, "describe", "--tags", "--always")
                size = du(sub)
                rel = sub.relative_to(root)
                rel_s = sub.relative_to(sources).parts
                cls = rel_s[0] if len(rel_s) > 1 else "."
                rows.append((str(rel) + "/", str(size), "", "git-clone", "%s @ %s (%s)" % (url, head, desc)))
                per_class[cls][0] += 1
                per_class[cls][1] += size
                continue
            keep.append(name)
        dirnames[:] = keep
        for f in sorted(filenames):
            p = d / f
            if f in SKIP or p.resolve() == out.resolve() or p.is_symlink():
                continue
            rel = p.relative_to(root)
            size = p.stat().st_size
            rel_s = p.relative_to(sources).parts
            cls = rel_s[0] if len(rel_s) > 1 else "."
            kind, note = kind_of(rel), ""
            if f.lower().endswith(".pdf"):
                with p.open("rb") as fh:
                    magic = fh.read(5)
                if magic != b"%PDF-":
                    kind, note = "NOT-A-PDF", "first bytes %r (likely an HTML block/challenge page)" % magic
                    fake_pdf.append(str(rel))
            rows.append((str(rel), str(size), sha256(p), kind, note))
            per_class[cls][0] += 1
            per_class[cls][1] += size
            if size > limit:
                big.append((str(rel), size))

    with out.open("w") as fh:
        fh.write("path\tbytes\tsha256\tkind\tnote\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")

    print("Wrote %s (%d rows)" % (out, len(rows)))
    print("Per source class (files, MB):")
    for cls in sorted(per_class):
        n, b = per_class[cls]
        print("  %-20s %6d  %10.1f" % (cls, n, b / 1e6))
    if fake_pdf:
        print("Files named .pdf that are NOT PDFs (re-fetch from another source or record as a gap):")
        for path in fake_pdf:
            print("  " + path)
    if big:
        print("Files over %.0f MB (keep out of any packaged skill; consider deleting or gitignoring):" % args.max_mb)
        for path, size in big:
            print("  %s  %.1f MB" % (path, size / 1e6))
    return 1 if fake_pdf else 0


if __name__ == "__main__":
    sys.exit(main())
