#!/usr/bin/env python3
"""star_min.py - dependency-free RELION STAR reader.

Parses the subset of STAR that RELION emits: named `data_<name>` blocks, each
either a `loop_` table or a set of `_label value` pairs. No numpy/pandas needed.

Read-only. Designed to read small metadata STARs (default_pipeline.star, job.star,
the data_optics block of a particles STAR) without loading multi-GB particle tables
into memory: `read_star(path, only_blocks=[...], max_loop_rows=N)` stops early.

Usage as a library:
    from star_min import read_star
    blocks = read_star("default_pipeline.star")
    # blocks["pipeline_processes"]["loop"] -> {"labels": [...], "rows": [[...], ...]}
    # blocks["job"]["pairs"] -> {"_rlnJobTypeLabel": "relion.refine3d", ...}

Usage as a CLI:
    python3 star_min.py file.star                 # list blocks + shapes
    python3 star_min.py file.star data_optics     # dump one block
"""
from __future__ import annotations
import shlex
import sys
from typing import Dict, List, Optional


def _split(line: str) -> List[str]:
    # RELION quotes strings with double quotes; shlex handles that and comments-free lines.
    try:
        return shlex.split(line, comments=False)
    except ValueError:
        return line.split()


def read_star(path: str,
              only_blocks: Optional[List[str]] = None,
              max_loop_rows: Optional[int] = None) -> Dict[str, dict]:
    """Parse a STAR file into {block_name: {"loop"|"pairs": ...}}.

    block_name is the part after `data_` (e.g. "optics", "pipeline_processes").
    A loop block -> {"loop": {"labels": [...], "rows": [[...]]}, "n_rows": int}.
    A pairs block -> {"pairs": {label: value}}.
    `only_blocks` (names without the data_ prefix) limits parsing; others are skipped.
    `max_loop_rows` caps stored rows per loop (n_rows still counts the full total).
    """
    blocks: Dict[str, dict] = {}
    cur = None            # current block name
    state = None          # None | "expect" | "labels" | "rows" | "pairs"
    labels: List[str] = []
    rows: List[List[str]] = []
    n_rows = 0
    want = set(only_blocks) if only_blocks else None
    skipping = False

    def flush():
        nonlocal cur, labels, rows, n_rows
        if cur is None:
            return
        if labels:
            blocks[cur] = {"loop": {"labels": labels, "rows": rows}, "n_rows": n_rows}
        elif cur not in blocks:
            blocks.setdefault(cur, {"pairs": {}})

    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("data_"):
                flush()
                cur = line[len("data_"):].strip() or "_unnamed"
                labels, rows, n_rows = [], [], 0
                skipping = bool(want and cur not in want)
                state = "expect"
                if cur not in blocks and not skipping:
                    blocks[cur] = {"pairs": {}}
                continue
            if skipping or cur is None:
                continue
            if line == "loop_":
                state = "labels"
                labels, rows, n_rows = [], [], 0
                continue
            if state == "labels" and line.startswith("_"):
                labels.append(line.split()[0])  # strip '#N' index suffix
                continue
            if state == "labels" and not line.startswith("_"):
                state = "rows"  # fall through to row handling
            if state == "rows":
                n_rows += 1
                if max_loop_rows is None or len(rows) < max_loop_rows:
                    rows.append(_split(line))
                continue
            # pairs block: `_label value...`
            if line.startswith("_"):
                parts = _split(line)
                key = parts[0]
                val = " ".join(parts[1:]) if len(parts) > 1 else ""
                blocks[cur].setdefault("pairs", {})[key] = val
                state = "pairs"
    flush()
    return blocks


def loop_dicts(block: dict):
    """Yield each loop row as {label: value}. Empty if not a loop block."""
    loop = block.get("loop")
    if not loop:
        return
    labels = loop["labels"]
    for row in loop["rows"]:
        yield {labels[i]: row[i] for i in range(min(len(labels), len(row)))}


def _main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    only = [argv[2][len("data_"):] if argv[2].startswith("data_") else argv[2]] if len(argv) > 2 else None
    blocks = read_star(path, only_blocks=only)
    for name, b in blocks.items():
        if "loop" in b:
            print(f"data_{name}: loop, {len(b['loop']['labels'])} labels, {b['n_rows']} rows")
            print("  labels:", ", ".join(b["loop"]["labels"]))
            if only:
                for d in list(loop_dicts(b))[:20]:
                    print("  ", d)
        else:
            print(f"data_{name}: pairs ({len(b.get('pairs', {}))})")
            if only:
                for k, v in b.get("pairs", {}).items():
                    print(f"  {k} = {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
