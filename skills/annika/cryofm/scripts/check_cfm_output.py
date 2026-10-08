#!/usr/bin/env python3
"""check_cfm_output.py -- read-only completeness and header check of a `cfm` output directory.

    python3 check_cfm_output.py OUT_DIR [--input REFERENCE_MAP] [--expect N] [--log run.log] [--cc]

Finds `*_external_reconstruct.mrc` in OUT_DIR, parses each header (stdlib), and checks: file size = header + data,
mode 2 (float32), grid and voxel size equal to --input, header stats finite and non-degenerate, origin/NSTART reset
(warns when the input's placement was non-zero -> restore_origin.py). Scans the log (--log, or OUT_DIR/run.log) for
`Output to file`, tracebacks and OOM. --cc additionally computes the correlation with --input (needs numpy; run it
inside the CryoFM environment / container). Exit 0 = complete, 1 = problems, 2 = usage.
"""
import argparse
import glob
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mrcheader as mh  # noqa: E402


def finite(x):
    return not (math.isnan(x) or math.isinf(x))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("--input", help="reference input map (-i1 for denoise, -i for enhance) to compare grid/placement")
    ap.add_argument("--expect", type=int, help="expected number of *_external_reconstruct.mrc files (3 denoise halves, 1 enhance)")
    ap.add_argument("--log", help="log file (default OUT_DIR/run.log if present)")
    ap.add_argument("--cc", action="store_true", help="compute CC vs --input (needs numpy)")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.out_dir):
        print(f"FAIL: {a.out_dir} is not a directory", file=sys.stderr)
        return 2
    files = sorted(glob.glob(os.path.join(a.out_dir, "*_external_reconstruct.mrc")))
    problems = 0
    print(f"== {a.out_dir}: {len(files)} output map(s)")
    if not files:
        print("   FAIL: no *_external_reconstruct.mrc found")
        problems += 1
    if a.expect is not None and len(files) != a.expect:
        print(f"   FAIL: expected {a.expect} outputs, found {len(files)}")
        problems += 1
    ref = None
    if a.input:
        try:
            ref = mh.read_header(a.input)
            g = mh.cryofm_geometry(ref)
            print(f"   input {os.path.basename(a.input)}: {g['dims']} @ {g['apix']:.4f} A, NSTART {g['nstart_crs']}, ORIGIN {tuple(round(v,3) for v in g['origin_A'])}")
            if g["placement_nonzero"]:
                print("   WARN: the input has a non-zero placement; every CryoFM2 output has origin 0 -> run restore_origin.py before overlaying/validating")
        except (OSError, mh.HeaderError) as e:
            print(f"   WARN: cannot read --input header: {e}")
    for f in files:
        try:
            h = mh.read_header(f)
        except (OSError, mh.HeaderError) as e:
            print(f"   FAIL {os.path.basename(f)}: {e}")
            problems += 1
            continue
        issues = []
        if h["mode"] != 2:
            issues.append(f"mode {h['mode']} (expected 2 float32)")
        if h["expected_bytes"] is not None and h["file_bytes"] != h["expected_bytes"]:
            issues.append(f"size {h['file_bytes']} != {h['expected_bytes']} (truncated/partial write?)")
        if not h["mapid_ok"]:
            issues.append("MAP id missing")
        for k in ("dmin", "dmax", "dmean", "rms"):
            if not finite(h[k]):
                issues.append(f"{k} not finite")
        if finite(h["rms"]) and h["rms"] == 0:
            issues.append("rms 0 (constant map?)")
        if ref is not None:
            if (h["nx"], h["ny"], h["nz"]) != (ref["nx"], ref["ny"], ref["nz"]):
                issues.append(f"grid {(h['nx'], h['ny'], h['nz'])} != input {(ref['nx'], ref['ny'], ref['nz'])}")
            if abs(h["voxel_x"] - ref["voxel_x"]) > 1e-3:
                issues.append(f"voxel {h['voxel_x']:.4f} != input {ref['voxel_x']:.4f}")
        place0 = all(v == 0 for v in (h["nxstart"], h["nystart"], h["nzstart"])) and all(abs(v) < 1e-6 for v in h["origin"])
        tag = "FAIL" if issues else "ok  "
        print(f"   {tag} {os.path.basename(f)}: {h['nx']}x{h['ny']}x{h['nz']} mode {h['mode']} voxel {h['voxel_x']:.4f} A"
              f" min {h['dmin']:.4g} max {h['dmax']:.4g} mean {h['dmean']:.4g} rms {h['rms']:.4g} placement {'0 (as written by cfm)' if place0 else 'non-zero (already restored?)'}")
        for i in issues:
            print(f"        - {i}")
        problems += len(issues)
        if a.cc and ref is not None and not issues:
            try:
                import numpy as np  # optional
                def load(p):
                    hh = mh.read_header(p)
                    with open(p, "rb") as fh:
                        fh.seek(1024 + hh["nsymbt"])
                        return np.fromfile(fh, dtype=(hh["endian"] + "f4"), count=hh["nx"] * hh["ny"] * hh["nz"]).astype(np.float32)
                x = load(f); y = load(a.input)
                cc = float(np.corrcoef(x, y)[0, 1])
                print(f"        CC vs input (whole spectrum) = {cc:.3f}  (sub-1.5 A inputs give ~0.3 because of the 3 A band limit; low-pass both to >= 3.5 A for a fair number)")
                if not np.isfinite(x).all():
                    print("        - FAIL: non-finite voxels"); problems += 1
            except ImportError:
                print("        (numpy not available: skip --cc, or run inside the CryoFM container)")
            except Exception as e:  # pragma: no cover
                print(f"        (cc failed: {e})")
    log = a.log or (os.path.join(a.out_dir, "run.log") if os.path.exists(os.path.join(a.out_dir, "run.log")) else None)
    if log and os.path.exists(log):
        outs, bad = [], []
        with open(log, errors="replace") as fh:
            for line in fh:
                if "Output to file" in line:
                    outs.append(line.strip().split("Output to file", 1)[1].strip())
                if any(k in line for k in ("Traceback", "Error", "OutOfMemoryError", "AssertionError", "error:")) and "RuntimeWarning" not in line:
                    bad.append(line.strip()[:160])
        print(f"   log {os.path.basename(log)}: {len(outs)} 'Output to file' line(s)" + (f"; {len(bad)} suspicious line(s):" if bad else ""))
        for b in bad[:8]:
            print(f"        ! {b}")
        if bad:
            problems += 1
    print(f">> OUTPUT CHECK: {'OK' if problems == 0 else 'PROBLEMS (' + str(problems) + ')'}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
