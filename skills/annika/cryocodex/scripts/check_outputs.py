#!/usr/bin/env python3
"""check_outputs.py -- read-only completeness, header and (opt-in) value check of a CryoCodex output directory.

    python3 check_outputs.py OUT_DIR [-n cryocodex] [--input MAP] [--normal] [--keep-size] [--reverse-interpolation]
                             [--stats] [--log RUN.LOG] [--json]

Expects the four files predict.py writes (predict.py:149-152): <n>.mrc (enhanced), <n>_out_score.mrc,
<n>_in_mask.mrc, <n>_in_score.mrc. Checks, from the headers (stdlib): present, float32 (mode 2), size = header + data,
MAP id, axis order 1/2/3, ORIGIN 0 with the placement in NXSTART/NYSTART/NZSTART, all four on one grid, voxel 1.0 A
(or the input voxel with --reverse-interpolation), the box CryoCodex should have written for the given options
(with --input), that the output box lies inside the input's extent, mask binary and scores >= 0 (header min/max).
--stats reads the data (stdlib; slow for very large maps): exact mask values, score range and count > 1, zero
fraction of the enhanced map, non-finite voxels, outer 2-voxel shell. --log scans a run log for known failures.
Expectations are SOURCED from the code at a35e73a / DERIVED, not yet observed. Exit 0 = OK, 1 = problems, 2 = usage.
"""
import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mrcheader as mh  # noqa: E402

LOG_PATTERNS = [
    ("Traceback", "Python traceback"),
    ("out of memory", "CUDA out of memory -> lower -b (references/09)"),
    ("OutOfMemoryError", "CUDA out of memory -> lower -b (references/09)"),
    ("Input grid is not orthogonal", "non-orthogonal input: CryoCodex exited without outputs (exit status likely 0)"),
    ("Crop inspection needs terminal input", "--crop_check True without a terminal (never use it in batch)"),
    ("is not a cryo-em density map file format", "input name must end in lower-case mrc/map"),
    ("ERROR: Conda was not found", "conda not found by predict.sh (export CONDA_EXE)"),
    ("ERROR: Cannot use", "conda env missing (CRYOCODEX_ENV / README install)"),
    ("ERROR: Failed to download", "weights download failed (network / proxy)"),
    ("Unrecognized checkpoint format", "checkpoint file is not the CryoCodex weights"),
    ("Failed to load the checkpoint", "checkpoint does not match the network (wrong/corrupt file)"),
    ("expected True or False", "boolean option without True/False"),
    ("error: ", "argparse error (exit 2)"),
    ("CUDA error", "CUDA error"),
    ("No CUDA GPUs are available", "no visible GPU (-g / CUDA_VISIBLE_DEVICES)"),
]


def finite(x):
    return not (math.isnan(x) or math.isinf(x))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("-n", "--name", default="cryocodex", help="the -n value of the run (default cryocodex)")
    ap.add_argument("--input", help="the -i map of the run, to check grid, voxel size and placement")
    ap.add_argument("--normal", action="store_true", help="the run used --normal True")
    ap.add_argument("--keep-size", action="store_true", help="the run used --keep_size True")
    ap.add_argument("--reverse-interpolation", action="store_true", help="the run used --reverse_interpolation True")
    ap.add_argument("--stats", action="store_true", help="read the voxel data for exact value checks (stdlib, slower)")
    ap.add_argument("--log", help="run log to scan (default: OUT_DIR/run.log if present)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.out_dir):
        print(f"usage error: {a.out_dir} is not a directory", file=sys.stderr)
        return 2
    if a.normal and a.keep_size:
        print("usage error: --keep_size True is fast-mode only (predict.py:191-192); a run cannot have both", file=sys.stderr)
        return 2
    lines, problems, notes = [], [], []
    res = {"out_dir": a.out_dir, "files": {}, "label": "expectations SOURCED/DERIVED from CryoCodex a35e73a; not observed"}

    def bad(msg):
        problems.append(msg)
        lines.append("   FAIL: " + msg)

    def note(msg):
        notes.append(msg)
        lines.append("   " + msg)

    lines.append(f"== {a.out_dir}  (-n {a.name})")
    paths = {s: os.path.join(a.out_dir, f"{a.name}{s}.mrc") for s in mh.OUTPUT_SUFFIXES}
    present = {s: os.path.isfile(p) for s, p in paths.items()}
    for s, p in paths.items():
        if not present[s]:
            bad(f"missing {os.path.basename(p)}")
    if not any(present.values()):
        others = sorted(os.path.basename(x) for x in glob.glob(os.path.join(a.out_dir, "*.mrc")))
        note("no outputs with this -n" + (f"; other .mrc files here: {', '.join(others[:6])}" if others else "")
             + ". If the log ends with '# Input grid is not orthogonal. EXIT.' CryoCodex stopped (likely with exit status 0).")
    checks = sorted(glob.glob(os.path.join(a.out_dir, "round_*_check")))
    if checks:
        note(f"WARN: {len(checks)} round_*_check folder(s) left: a --crop_check review did not finish (EOF/abort); "
             "they are deleted only when the review continues")

    ref, rg = None, None
    if a.input:
        try:
            ref = mh.read_header(a.input)
            rg = mh.geometry(ref)
            o = rg["origin_A"]
            lines.append(f"   input {os.path.basename(a.input)}: {mh.dims_xyz(ref)} @ {tuple(round(v, 4) for v in ref['voxel'])} A, "
                         f"origin used ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f}) A; 1 A box {rg['dims_1A']}")
        except (OSError, mh.HeaderError) as e:
            note(f"WARN: cannot read --input header: {e}")
            ref = None

    heads = {}
    for s, p in paths.items():
        if not present[s]:
            continue
        try:
            h = mh.read_header(p)
        except (OSError, mh.HeaderError) as e:
            bad(f"{os.path.basename(p)}: {e}")
            continue
        heads[s] = h
        issues = []
        if h["mode"] != 2:
            issues.append(f"mode {h['mode']} (expected 2 = float32)")
        if h["expected_bytes"] is not None and h["file_bytes"] != h["expected_bytes"]:
            issues.append(f"size {h['file_bytes']} != {h['expected_bytes']} B implied by the header (partial write?)")
        if not h["mapid_ok"]:
            issues.append("MAP id missing")
        if (h["mapc"], h["mapr"], h["maps"]) != (1, 2, 3):
            issues.append(f"axis order ({h['mapc']},{h['mapr']},{h['maps']}) (CryoCodex writes 1,2,3)")
        if any(abs(v) > 1e-6 for v in h["origin"]):
            issues.append(f"ORIGIN {h['origin']} != 0 (CryoCodex writes 0 and stores placement in NSTART) -- edited after the run?")
        for k in ("dmin", "dmax", "dmean", "rms"):
            if not finite(h[k]):
                issues.append(f"header {k} not finite")
        if s == "_in_mask" and finite(h["dmin"]) and finite(h["dmax"]):
            if h["dmin"] < 0 or h["dmax"] > 1 or h["dmin"] not in (0.0, 1.0) or h["dmax"] not in (0.0, 1.0):
                issues.append(f"mask min/max {h['dmin']:.4g}/{h['dmax']:.4g}: the saved mask should be binary 0/1 (predict.py:105, 143)")
            elif h["dmax"] == 0:
                note("WARN: mask is empty (all 0): nothing was recognised as molecule")
        if s in ("_out_score", "_in_score") and finite(h["dmin"]) and h["dmin"] < 0:
            issues.append(f"score min {h['dmin']:.4g} < 0 (scores are clipped at 0, predict.py:146-147)")
        if s == "" and finite(h["rms"]) and h["rms"] == 0 and h["dmax"] == h["dmin"]:
            issues.append("enhanced map is constant (empty?)")
        st = (h["nxstart"], h["nystart"], h["nzstart"])
        res["files"][os.path.basename(p)] = {"dims": (h["nx"], h["ny"], h["nz"]), "voxel": h["voxel"], "nstart": st,
                                             "min": h["dmin"], "max": h["dmax"], "mean": h["dmean"], "rms": h["rms"], "issues": issues}
        lines.append(f"   {'FAIL' if issues else 'ok  '} {os.path.basename(p)}: {h['nx']}x{h['ny']}x{h['nz']} mode {h['mode']} "
                     f"voxel {h['voxel'][0]:.4f} A NSTART {st} min {h['dmin']:.4g} max {h['dmax']:.4g} mean {h['dmean']:.4g}")
        for i in issues:
            lines.append(f"        - {i}")
            problems.append(f"{os.path.basename(p)}: {i}")
        if s in ("_out_score", "_in_score") and finite(h["dmax"]) and h["dmax"] > 1:
            note(f"NOTE: {os.path.basename(p)} max {h['dmax']:.4g} > 1 -- possible after --reverse_interpolation (no upper clamp); "
                 "on the 1 A grid unexpected (derived). Scores are predicted local SSIM, not resolution.")

    if heads:
        first = next(iter(heads.values()))
        g0 = ((first["nx"], first["ny"], first["nz"]), tuple(round(v, 4) for v in first["voxel"]),
              (first["nxstart"], first["nystart"], first["nzstart"]))
        for s, h in heads.items():
            gi = ((h["nx"], h["ny"], h["nz"]), tuple(round(v, 4) for v in h["voxel"]), (h["nxstart"], h["nystart"], h["nzstart"]))
            if gi != g0:
                bad(f"{os.path.basename(paths[s])} grid {gi} differs from {g0}: the four outputs should share one grid")
        dims, vox, nst = g0
        # expected voxel size
        exp_vox = 1.0
        if a.reverse_interpolation and ref is not None and not rg["reverse_skipped"]:
            exp_vox = None
            if any(abs(v - r) > 1e-3 for v, r in zip(first["voxel"], ref["voxel"])):
                bad(f"voxel {vox} != input voxel {tuple(round(v, 4) for v in ref['voxel'])} although --reverse_interpolation True")
        elif a.reverse_interpolation and ref is None:
            exp_vox = None
            note("NOTE: --reverse-interpolation without --input: voxel size not checked")
        if exp_vox is not None and any(abs(v - exp_vox) > 1e-4 for v in first["voxel"]):
            bad(f"voxel {vox} != 1.0 A expected without (effective) --reverse_interpolation")
        # expected box and placement
        if ref is not None and rg["dims_1A"] is not None:
            o1 = tuple(int(round(x)) for x in rg["origin_A"])          # regridded origin on the 1 A lattice
            rev = a.reverse_interpolation and not rg["reverse_skipped"]
            exp_dims = exp_st = None
            if a.keep_size and not rev:
                exp_dims, exp_st, why = rg["keep_size_box"], o1, "--keep_size True: the regridded 1 A box"
            elif a.keep_size and rev:
                exp_dims, why = rg["keep_size_reverse_box"], "--keep_size True --reverse_interpolation True"
                exp_st = tuple(int(round(x / v)) for x, v in zip(o1, ref["voxel"]))
            elif a.normal and not rev:
                exp_dims, exp_st, why = rg["box_normal"], o1, "--normal True: the 1 A box, axes < 48 padded"
            elif a.normal and rev:
                exp_dims, why = rg["normal_reverse_box"], "--normal True --reverse_interpolation True"
                exp_st = tuple(int(round(x / v)) for x, v in zip(o1, ref["voxel"]))
            else:
                why = "fast mode: crop box, crop-dependent"
            if exp_dims is not None:
                if tuple(dims) != tuple(exp_dims):
                    bad(f"box {dims} != expected {tuple(exp_dims)} ({why}; derived)")
                else:
                    lines.append(f"   ok   box {dims} = expected ({why}; derived)")
                if exp_st is not None and tuple(nst) != tuple(exp_st):
                    bad(f"NSTART {nst} != expected {tuple(exp_st)} (placement; derived)")
            elif not rev:
                lo = [mh.WINDOW] * 3
                hi = [max(mh.WINDOW, n) for n in rg["dims_1A"]]
                off = [s - o for s, o in zip(nst, o1)]
                if any(d < l or d > u for d, l, u in zip(dims, lo, hi)):
                    bad(f"fast-mode box {dims} outside [48, {tuple(hi)}] per axis (derived)")
                elif any(f < 0 or f > n - 1 or (d > mh.WINDOW and f + d > n) for f, d, n in zip(off, dims, rg["dims_1A"])):
                    bad(f"crop {tuple(off)}+{tuple(dims)} (NSTART - input origin, box) does not fit the 1 A box {rg['dims_1A']} (derived)")
                else:
                    lines.append(f"   ok   fast-mode crop: box {dims}, start {tuple(off)} inside the 1 A box {rg['dims_1A']} (derived)")
            # generic overlay check in Angstrom
            out_lo = [s * v for s, v in zip(nst, first["voxel"])]
            out_hi = [(s + n - 1) * v for s, n, v in zip(nst, dims, first["voxel"])]
            in_lo = list(rg["origin_A"])
            in_hi = [o + (n - 1) * v for o, n, v in zip(rg["origin_A"], rg["dims_xyz"], ref["voxel"])]
            slack = [max(2.0, (mh.WINDOW - n1) * 1.0 + 2.0) if n1 < mh.WINDOW else 2.0 for n1 in rg["dims_1A"]]
            outside = [i for i in range(3) if out_lo[i] < in_lo[i] - slack[i] or out_hi[i] > in_hi[i] + slack[i]]
            span = ", ".join(f"{'xyz'[i]} {out_lo[i]:.1f}..{out_hi[i]:.1f}" for i in range(3))
            if outside:
                bad(f"output box ({span} A) extends beyond the input map ({', '.join(f'{in_lo[i]:.1f}..{in_hi[i]:.1f}' for i in range(3))} A)"
                    " -- placement wrong or wrong --input")
            else:
                lines.append(f"   ok   output box {span} A lies inside the input map's extent (overlay by NSTART; ORIGIN 0)")

    if a.stats:
        for s, h in heads.items():
            p = paths[s]
            try:
                d = mh.read_data(p, h)
            except (OSError, mh.HeaderError, EOFError) as e:
                bad(f"{os.path.basename(p)}: cannot read data ({e})")
                continue
            n = len(d)
            if n == 0:
                bad(f"{os.path.basename(p)}: no data")
                continue
            nan = sum(1 for v in d if v != v)
            if nan:
                bad(f"{os.path.basename(p)}: {nan} non-finite voxels")
                continue
            mn, mx = min(d), max(d)
            zf = d.count(0.0) / n
            info = {"min": mn, "max": mx, "zero_fraction": zf}
            msg = f"   stats {os.path.basename(p)}: min {mn:.4g} max {mx:.4g} zeros {100 * zf:.1f}%"
            if s == "_in_mask":
                ones = d.count(1.0)
                nonbin = n - ones - d.count(0.0)
                info.update(ones_fraction=ones / n, non_binary=nonbin)
                msg += f" ones {100 * ones / n:.1f}%"
                if nonbin:
                    bad(f"{os.path.basename(p)}: {nonbin} voxels neither 0 nor 1 (saved mask should be binary)")
            if s in ("_out_score", "_in_score"):
                gt1 = sum(1 for v in d if v > 1.0) if mx > 1.0 else 0
                info["n_gt_1"] = gt1
                msg += f" n>1 {gt1}"
                if mn < 0:
                    bad(f"{os.path.basename(p)}: negative scores (should be clipped at 0)")
            if not a.reverse_interpolation and h["nx"] > 4 and h["ny"] > 4 and h["nz"] > 4:
                sh = mh.shell_max_abs(d, h["nx"], h["ny"], h["nz"])
                info["outer_shell_max_abs"] = sh
                msg += f" outer-2-voxel-shell max|v| {sh:.3g}" + ("" if sh == 0 else " (derived expectation: 0)")
            lines.append(msg)
            res["files"].setdefault(os.path.basename(p), {})["stats"] = info

    log = a.log or (os.path.join(a.out_dir, "run.log") if os.path.isfile(os.path.join(a.out_dir, "run.log")) else None)
    if log:
        if not os.path.isfile(log):
            note(f"WARN: log {log} not found")
        else:
            hits, npath = [], 0
            with open(log, errors="replace") as fh:
                for line in fh:
                    if line.startswith("path:"):
                        npath += 1
                    for pat, meaning in LOG_PATTERNS:
                        if pat in line:
                            hits.append(f"{meaning}: {line.strip()[:140]}")
                            break
            lines.append(f"   log {os.path.basename(log)}: {npath} 'path:' line(s) (4 expected after a complete run)")
            for hline in hits[:10]:
                lines.append(f"        ! {hline}")
            if hits:
                problems.append(f"log shows {len(hits)} known failure line(s)")
            if any("Downloading the model weights" in x for x in open(log, errors="replace")):
                note("NOTE: this run downloaded the weights (471 MB); record their sha256 (cryocodex_env_probe.py --hash)")

    res["problems"], res["notes"] = problems, notes
    rc = 0 if not problems else 1
    res["rc"] = rc
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        print("\n".join(lines))
        print(f">> OUTPUT CHECK: {'OK' if rc == 0 else 'PROBLEMS (' + str(len(problems)) + ')'}  [expectations derived from the pinned code]")
    return rc


if __name__ == "__main__":
    sys.exit(main())
