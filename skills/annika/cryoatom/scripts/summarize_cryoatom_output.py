#!/usr/bin/env python3
"""Read-only summary of a CryoAtom2 output tree.

  python3 summarize_cryoatom_output.py /path/to/output [--json]

Reports, per mmCIF model: atom count, chains, residue count, and the
distribution of the value in the B-factor column.

That column carries MODEL CONFIDENCE, not an experimental B-factor and not
proof of accuracy. This script never rewrites, moves, or deletes anything.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

INTERMEDIATE_HINTS = ("see_alpha_output", "CryoNet_round")


def parse_atom_site(path, limit=None):
    """Parse the _atom_site loop by header position (the column order is not fixed)."""
    cols, rows = [], []
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("_atom_site."):
                cols.append(line.strip().split(".", 1)[1])
            elif line.startswith(("ATOM", "HETATM")):
                rows.append(line.split())
                if limit and len(rows) >= limit:
                    break
    return cols, rows


def summarize_model(path):
    cols, rows = parse_atom_site(path)
    info = {"file": path, "bytes": os.path.getsize(path), "atoms": len(rows),
            "chains": [], "residues": None, "confidence": None, "warnings": []}
    if not rows:
        info["warnings"].append("no ATOM/HETATM records found")
        return info

    def index(name):
        return cols.index(name) if name in cols else None

    ch_i = index("label_asym_id")
    if ch_i is None:
        ch_i = index("auth_asym_id")
    seq_i = index("label_seq_id")
    if seq_i is None:
        seq_i = index("auth_seq_id")
    b_i = index("B_iso_or_equiv")

    def field(row, i):
        return row[i] if i is not None and i < len(row) else None

    if ch_i is not None:
        info["chains"] = sorted({field(r, ch_i) for r in rows if field(r, ch_i)})
    else:
        info["warnings"].append("no chain column in the _atom_site loop")

    if seq_i is not None and ch_i is not None:
        info["residues"] = len({(field(r, ch_i), field(r, seq_i)) for r in rows})

    if b_i is not None:
        values = []
        for r in rows:
            raw = field(r, b_i)
            try:
                values.append(float(raw))
            except (TypeError, ValueError):
                continue
        if values:
            values.sort()
            n = len(values)
            info["confidence"] = {
                "n": n,
                "min": round(values[0], 2),
                "median": round(values[n // 2], 2),
                "mean": round(sum(values) / n, 2),
                "max": round(values[-1], 2),
                "note": "model confidence in the B-factor column, NOT an experimental B-factor",
            }
        else:
            info["warnings"].append("B-factor column present but unparseable")
    else:
        info["warnings"].append("no B_iso_or_equiv column")
    return info


def summarize_tree(root):
    out = {"root": root, "exists": os.path.isdir(root), "models": [],
           "raw_models": [], "timing": None, "intermediates": [], "other_files": []}
    if not out["exists"]:
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            if any(h in d for h in INTERMEDIATE_HINTS):
                out["intermediates"].append(os.path.join(dirpath, d))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if name.endswith(".cif"):
                model = summarize_model(path)
                (out["raw_models"] if name.endswith("_raw.cif") else out["models"]).append(model)
            elif name == "running_time.log":
                try:
                    with open(path, errors="replace") as fh:
                        out["timing"] = fh.read().strip()[:2000]
                except OSError:
                    pass
            else:
                out["other_files"].append(path)
    return out


def human(report):
    lines = []
    if not report["exists"]:
        return "no such directory: %s" % report["root"]
    lines.append("output tree : %s" % report["root"])
    for label, key in (("model (filtered)", "models"), ("model (raw)", "raw_models")):
        for m in report[key]:
            lines.append("")
            lines.append("%s : %s" % (label, m["file"]))
            lines.append("  atoms    : %d" % m["atoms"])
            lines.append("  chains   : %d  %s" % (len(m["chains"]), " ".join(m["chains"])))
            if m["residues"] is not None:
                lines.append("  residues : %d" % m["residues"])
            c = m["confidence"]
            if c:
                lines.append("  confidence: min %.2f / median %.2f / mean %.2f / max %.2f"
                             % (c["min"], c["median"], c["mean"], c["max"]))
            for w in m["warnings"]:
                lines.append("  warning  : %s" % w)
    if report["timing"]:
        lines.append("")
        lines.append("running_time.log:")
        lines.extend("  " + l for l in report["timing"].splitlines()[:20])
    if report["intermediates"]:
        lines.append("")
        lines.append("intermediates kept (-k): %d directories" % len(report["intermediates"]))
    if not report["models"] and not report["raw_models"]:
        lines.append("")
        lines.append("NO mmCIF model found — the run did not finish, or this is the wrong directory.")
    else:
        lines.append("")
        lines.append("The B-factor column carries MODEL CONFIDENCE, not an experimental")
        lines.append("B-factor. High confidence is not proof the model is correct: it still")
        lines.append("needs density-fit assessment, geometry validation, and expert review.")
    return "\n".join(lines)


SAMPLE_CIF = """data_test
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
ATOM 1 N ALA A 1 1.0 2.0 3.0 1.00 55.00
ATOM 2 CA ALA A 1 1.5 2.5 3.5 1.00 65.00
ATOM 3 N GLY B 2 4.0 5.0 6.0 1.00 75.00
"""


def self_test():
    import tempfile
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "model.cif")
        with open(path, "w") as fh:
            fh.write(SAMPLE_CIF)
        with open(os.path.join(tmp, "running_time.log"), "w") as fh:
            fh.write("stage1: 14s\n")
        report = summarize_tree(tmp)
        if len(report["models"]) != 1:
            failures.append("expected one filtered model")
        else:
            m = report["models"][0]
            if m["atoms"] != 3:
                failures.append("atom count wrong: %s" % m["atoms"])
            if m["chains"] != ["A", "B"]:
                failures.append("chains wrong: %s" % m["chains"])
            if m["residues"] != 2:
                failures.append("residue count wrong: %s" % m["residues"])
            c = m["confidence"]
            if not c or c["min"] != 55.0 or c["max"] != 75.0 or c["mean"] != 65.0:
                failures.append("confidence stats wrong: %s" % c)
        if not report["timing"]:
            failures.append("running_time.log not picked up")
        if "MODEL CONFIDENCE" not in human(report):
            failures.append("human report must carry the confidence caveat")
    missing = summarize_tree("/nonexistent-cryoatom-output")
    if missing["exists"]:
        failures.append("missing directory must report exists=false")
    print(json.dumps({"self_test": "ok" if not failures else "failed",
                      "failures": failures}, indent=2))
    return 0 if not failures else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output_dir", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.output_dir:
        ap.error("output_dir is required")

    report = summarize_tree(os.path.expanduser(args.output_dir))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(human(report))
    return 0 if report["exists"] and (report["models"] or report["raw_models"]) else 1


if __name__ == "__main__":
    sys.exit(main())
