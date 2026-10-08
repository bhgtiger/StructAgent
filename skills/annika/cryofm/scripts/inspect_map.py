#!/usr/bin/env python3
"""inspect_map.py -- read-only MRC header inspector with the CryoFM2 geometry gates.

    python3 inspect_map.py half1.mrc half2.mrc [map.mrc] [--batch-size 4] [--patch-size 64] [--patch-overlap 32] [--json]

Reads only the 1024-byte header (also inside .map.gz). Reports, per file, what `cfm` would do (axis order, padding,
resampled box at 1.5 A, patches, batches, origin/NSTART, band limit) and, for several files, whether they may be
used together (same grid, same pixel size, same placement). Exit 0 = every gate passes, 1 = a gate fails or files
disagree, 2 = usage / unreadable file. Nothing is written.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mrcheader as mh  # noqa: E402


def report(h, g, batch):
    lines = []
    p = h["path"]
    lines.append(f"== {p}")
    lines.append(f"   header: {h['nx']}x{h['ny']}x{h['nz']} (CRS) mode {h['mode']} voxel {h['voxel'][0]:.4f}/{h['voxel'][1]:.4f}/{h['voxel'][2]:.4f} A"
                 f" axis {g['axis_order']} NSTART {g['nstart_crs']} ORIGIN ({h['origin'][0]:.3f}, {h['origin'][1]:.3f}, {h['origin'][2]:.3f}) A"
                 f" MAP id {'ok' if h['mapid_ok'] else 'MISSING'} nversion {h['nversion']} nsymbt {h['nsymbt']}")
    if h["file_bytes"] is not None and h["expected_bytes"] is not None and h["file_bytes"] != h["expected_bytes"]:
        tag = "WARN" if h["file_bytes"] > h["expected_bytes"] else "FAIL"
        lines.append(f"   {tag}: file is {h['file_bytes']} B, header implies {h['expected_bytes']} B"
                     + (" (truncated: mrcfile.open will raise)" if tag == "FAIL" else " (extra bytes: mrcfile only warns)"))
    lines.append(f"   {'PASS' if g['ext_ok'] else 'FAIL'}: extension {g['ext'] or '(none)'} "
                 + ("accepted (.mrc/.map)" if g["ext_ok"] else "rejected by cfm -> ValueError 'Unknown input file type'; gunzip/rename first"))
    lines.append(f"   {'PASS' if g['axis_ok'] else 'FAIL'}: axis order {g['axis_order']} "
                 + ("supported" if g["axis_ok"] else "-> RuntimeError 'MRC file axis arrangement not supported!'"))
    if not g["apix_ok"]:
        lines.append("   FAIL: voxel size 0 (CELLA/MX) -> division by zero in the resampler")
    if g["cubic"]:
        lines.append(f"   {'FAIL' if g['odd_cube_assert'] else 'PASS'}: cubic box {g['dims'][0]}"
                     + (" is ODD -> bare AssertionError (assert iz % 2 == 0); pad to an even box first" if g["odd_cube_assert"] else " (even)"))
    else:
        lines.append(f"   NOTE: non-cubic {g['dims']} -> cfm zero-pads to {g['padded_edge']}^3 and crops back (masks are NOT padded)")
    if g["resampled_edge"] is not None:
        lines.append(f"   {'PASS' if g['min_box_ok'] else 'FAIL'}: model grid {g['resampled_edge']}^3 at {g['model_voxel_A']:.4f} A "
                     f"(physical box {g['physical_box_A']:.1f} A)"
                     + (f"; patches {g['patches']} ({'x'.join(str(o) for o in g['offsets_per_axis'])}), batches {g['batches']} at --batch-size {batch} per half map"
                        if g["min_box_ok"] else " < 64 voxels -> IndexError in GridPatches3D; box must be >= ~96 A"))
    if g["band_limit_note"]:
        lines.append(f"   NOTE: pixel {g['apix']:.4f} A < 1.5 A -> output band-limited at ~3.0 A on-axis unless --spectral-mixing")
    elif g["apix_ok"] and g["apix"] > mh.MODEL_VOXEL_SIZE:
        lines.append(f"   NOTE: pixel {g['apix']:.4f} A > 1.5 A -> Fourier up-sampling to the model grid; prior trained on < 3 A maps")
    if g["placement_nonzero"]:
        lines.append(f"   WARN: placement is non-zero (NSTART {g['nstart_crs']} / ORIGIN {tuple(round(v, 3) for v in g['origin_A'])} A);"
                     " cfm writes origin 0 -> run scripts/restore_origin.py on the outputs")
    else:
        lines.append("   PASS: NSTART and ORIGIN are zero; outputs will overlay the input")
    if any(abs(h["voxel"][i] - h["voxel"][0]) > 1e-4 for i in (1, 2)):
        lines.append(f"   WARN: anisotropic voxel {h['voxel']}; cfm uses voxel_size.x only")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="+", help="MRC/MAP files (half1 half2 [map] [mask]); .gz is read header-only")
    ap.add_argument("--batch-size", type=int, default=mh.DEFAULT_BATCH)
    ap.add_argument("--patch-size", type=int, default=mh.DEFAULT_PATCH)
    ap.add_argument("--patch-overlap", type=int, default=mh.DEFAULT_OVERLAP)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    results = []
    rc = 0
    for p in a.maps:
        try:
            h = mh.read_header(p)
        except (OSError, mh.HeaderError) as e:
            print(f"== {p}\n   FAIL: cannot read header: {e}", file=sys.stderr)
            rc = 2
            continue
        g = mh.cryofm_geometry(h, a.patch_size, a.patch_overlap, a.batch_size)
        results.append((h, g))
        if not g["pass"]:
            rc = max(rc, 1)
    if not results:
        return rc or 2
    pair_notes = []
    if len(results) >= 2:
        h0, g0 = results[0]
        for h, g in results[1:]:
            same_dims = g["dims"] == g0["dims"]
            same_apix = abs(g["apix"] - g0["apix"]) <= 0.005
            same_place = g["nstart_crs"] == g0["nstart_crs"] and all(abs(x - y) < 1e-3 for x, y in zip(g["origin_A"], g0["origin_A"]))
            if not same_dims:
                pair_notes.append(f"FAIL: {os.path.basename(h['path'])} box {g['dims']} != {os.path.basename(h0['path'])} {g0['dims']}"
                                  " -> ValueError 'All volumes must have the same shape' (EMDB primary vs half maps often differ)")
                rc = max(rc, 1)
            if not same_apix:
                pair_notes.append(f"WARN: pixel size {g['apix']:.4f} vs {g0['apix']:.4f} A; cfm denoise silently uses half1's value, cfm enhance -i rejects > 0.005 A")
                rc = max(rc, 1)
            if not same_place:
                pair_notes.append(f"WARN: placement differs ({g['nstart_crs']}/{tuple(round(v,3) for v in g['origin_A'])} vs {g0['nstart_crs']}/{tuple(round(v,3) for v in g0['origin_A'])}); outputs all get origin 0")
    if a.json:
        out = {"files": [{"header": {k: v for k, v in h.items() if k != "labels"}, "geometry": g} for h, g in results],
               "pair_notes": pair_notes, "rc": rc}
        print(json.dumps(out, indent=1, default=str))
    else:
        for h, g in results:
            print("\n".join(report(h, g, a.batch_size)))
        if pair_notes:
            print("== together")
            for n in pair_notes:
                print("   " + n)
        elif len(results) >= 2:
            print("== together\n   PASS: same box, pixel size and placement")
        print(f">> GATES: {'PASS' if rc == 0 else 'FAIL'} (rc {rc})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
