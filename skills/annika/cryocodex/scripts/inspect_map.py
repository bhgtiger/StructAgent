#!/usr/bin/env python3
"""inspect_map.py -- read-only MRC header inspector with the CryoCodex v1.0.0 input gates and geometry.

    python3 inspect_map.py MAP [MAP ...] [-s 12] [-b 9] [--json]

Reads only the 1024-byte header (also inside .gz, for inspection; CryoCodex itself rejects .gz). Reports, per file,
what predict.sh would do (SOURCED from the code at a35e73a, not observed):
  gates   : path ends in lower-case 'map'/'mrc' (grid_utils.py:215); CELLB angles all 90 (grid_utils.py:160-167);
            MAP id, axis order, mode and file size as mrcfile will need them; some positive density (header DMAX)
  geometry: voxel size, origin used by CryoCodex (ORIGIN + NSTART*voxel, both summed), whether cubic resampling to
            1.0 A happens, the 1 A box, the normal-mode box (axes < 48 padded to 48), 48^3 window count and batches,
            the --keep_size box and the --reverse_interpolation boxes, a rough host-RAM estimate for normal mode
            (fast mode crops to the molecule: data-dependent, always <= the normal-mode numbers)
Exit 0 = every gate passes, 1 = a gate fails, 2 = usage / unreadable file. Nothing is written.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mrcheader as mh  # noqa: E402


def tri(t, fmt="{}"):
    return "x".join(fmt.format(v) for v in t) if t else "?"


def report(h, g, stride, batch):
    L = [f"== {h['path']}"]
    L.append(f"   header: {h['nx']}x{h['ny']}x{h['nz']} (CRS) mode {h['mode']} voxel {tri(h['voxel'], '{:.4f}')} A "
             f"axis ({h['mapc']},{h['mapr']},{h['maps']}) NSTART ({h['nxstart']},{h['nystart']},{h['nzstart']}) "
             f"ORIGIN ({h['origin'][0]:.3f},{h['origin'][1]:.3f},{h['origin'][2]:.3f}) A cell angles "
             f"{tri(h['cellb'], '{:g}')} MAP id {'ok' if h['mapid_ok'] else 'MISSING'} nsymbt {h['nsymbt']}")
    L.append(f"   {'PASS' if g['name_ok'] else 'FAIL'}: file name -- {g['name_reason']}")
    L.append(f"   {'PASS' if g['orthogonal'] else 'FAIL'}: cell angles "
             + ("90/90/90" if g["orthogonal"] else f"{tri(h['cellb'], '{:g}')} -> prints '# Input grid is not orthogonal. EXIT.' and exits"
                " (bare exit(): status 0 expected, no outputs -- code reading)"))
    if not g["mapid_ok"]:
        L.append("   FAIL: no 'MAP ' id at byte 208 -> mrcfile (non-permissive) refuses the file")
    if not g["axis_ok"]:
        L.append(f"   FAIL: MAPC/MAPR/MAPS ({h['mapc']},{h['mapr']},{h['maps']}) is not a permutation of 1,2,3")
    if not g["mode_ok"]:
        L.append(f"   FAIL: MRC mode {h['mode']} is unusual for a density map; mrcfile may refuse it -- convert to float32 (mode 2)")
    if g["size_ok"] is False:
        L.append(f"   FAIL: file is {h['file_bytes']} B, header implies {h['expected_bytes']} B (truncated: mrcfile raises)")
    elif g.get("size_extra"):
        L.append(f"   WARN: file is {h['file_bytes']} B, header implies {h['expected_bytes']} B (extra bytes: mrcfile warns)")
    if g["positive_density_header"] is False:
        L.append(f"   FAIL: header DMAX {h['dmax']:.4g} <= 0: no positive density -> the 99.999th-percentile normalisation fails")
    elif g["positive_density_header"] is None:
        L.append("   NOTE: header min/max not set; positive density not checked")
    if not g["voxel_ok"]:
        L.append("   FAIL: voxel size 0 (CELLA or MX/MY/MZ is 0) -> resampling cannot work")
        return L
    if g["anisotropic"]:
        L.append(f"   NOTE: anisotropic voxel {tri(h['voxel'], '{:.4f}')}: CryoCodex resamples each axis to 1.0 A")
    if g["dims_1A"] is None:
        return L
    o = g["origin_A"]
    L.append(f"   origin used by CryoCodex: ({o[0]:.3f}, {o[1]:.3f}, {o[2]:.3f}) A (= ORIGIN + NSTART*voxel)"
             + ("  WARN: ORIGIN and NSTART are both non-zero; CryoCodex adds both (other programs may use only one)" if g["both_origin_fields"] else ""))
    if g["resampled"]:
        why = "voxel != 1.0" if any(v != 1.0 for v in h["voxel"]) else "origin not on the 1 A lattice"
        L.append(f"   resample: cubic (Keys a=-0.5) to 1.0 A ({why}); 1 A box {tri(g['dims_1A'])} = floor(voxel*(n-1))+1")
    else:
        L.append(f"   resample: none (voxel exactly 1.0 and origin on the 1 A lattice); box {tri(g['dims_1A'])}")
    if g["small_axis"]:
        L.append(f"   NOTE: an axis of the 1 A box is < 48 -> zero-padded to 48 at the far end; outputs are at least 48 per axis."
                 " --keep_size True may then fail (pastes a 48-voxel crop into a smaller canvas; code reading, runbook R12b)")
    L.append(f"   normal mode (--normal True): box {tri(g['box_normal'])} at 1.0 A, {g['windows_normal']} windows of 48^3 "
             f"(stride {stride}), {g['batches_normal']} batches at -b {batch}")
    L.append(f"   host RAM, normal mode (derived, rough): ~{mh.fmt_bytes(g['ram_normal_bytes'])} "
             f"({g['windows_normal']} windows x 2.2 MB + whole-grid copies); fast mode (default) crops to the molecule first -> less")
    L.append("   fast mode (default): crop = auto-mask bounding box +-5 voxels (data-dependent; each axis between 48 and "
             f"{tri(g['box_normal'])}); outputs at 1.0 A, placement in NXSTART/NYSTART/NZSTART, ORIGIN 0")
    L.append(f"   --keep_size True: {tri(g['keep_size_box'])} at 1.0 A (the regridded box"
             + (", = input box)" if g["keep_size_box"] == g["dims_xyz"] else f", NOT the input box {tri(g['dims_xyz'])})"))
    if g["reverse_skipped"]:
        L.append("   --reverse_interpolation True: skipped (input already 1.0 A within 1e-4); outputs stay on the 1 A grid")
    else:
        L.append(f"   --keep_size True --reverse_interpolation True: {tri(g['keep_size_reverse_box'])} at {tri(h['voxel'], '{:.4f}')} A"
                 + (" (= input box)" if g["keep_size_reverse_box"] == g["dims_xyz"] else f" (input box {tri(g['dims_xyz'])}; differs by rounding)"))
        L.append(f"   --normal True --reverse_interpolation True: {tri(g['normal_reverse_box'])}; fast mode + reverse: crop-dependent")
    if g["stride_gaps"]:
        L.append(f"   FAIL: stride {stride} > 44 leaves voxels no window covers (written as 0; derived from grid_utils.py:383-393)")
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="+", help="input map(s) to check (.mrc/.map; .gz is read header-only)")
    ap.add_argument("-s", "--stride", type=int, default=mh.DEFAULT_STRIDE, help="sliding-window stride to plan with (default 12)")
    ap.add_argument("-b", "--batch", type=int, default=mh.DEFAULT_BATCH, help="batch size to plan with (default 9)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    if a.stride < 1 or a.batch < 1:
        print("usage error: --stride and --batch must be >= 1", file=sys.stderr)
        return 2
    rc = 0
    results = []
    for p in a.maps:
        try:
            h = mh.read_header(p)
        except (OSError, mh.HeaderError) as e:
            print(f"== {p}\n   FAIL: cannot read MRC header: {e}", file=sys.stderr)
            rc = 2
            continue
        g = mh.geometry(h, a.stride, a.batch)
        if g["stride_gaps"]:
            g["pass"] = False
        results.append((h, g))
        if not g["pass"] and rc == 0:
            rc = 1
    if a.json:
        out = {"files": [{"header": {k: v for k, v in h.items() if k != "labels"}, "geometry": g} for h, g in results], "rc": rc,
               "label": "SOURCED from CryoCodex a35e73a code reading; not observed on a real install"}
        print(json.dumps(out, indent=1, default=str))
    else:
        for h, g in results:
            print("\n".join(report(h, g, a.stride, a.batch)))
        print(f">> GATES: {'PASS' if rc == 0 else 'FAIL'} (rc {rc})  [derived from the pinned code, not observed]")
    return rc


if __name__ == "__main__":
    sys.exit(main())
