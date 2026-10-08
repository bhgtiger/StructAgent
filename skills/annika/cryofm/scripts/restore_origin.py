#!/usr/bin/env python3
"""restore_origin.py -- copy the placement (NSTART + ORIGIN) of a CryoFM2 *input* map onto its same-grid *output*.

    python3 restore_origin.py REFERENCE_INPUT CRYOFM2_OUTPUT REGISTERED_OUTPUT [--force]

CryoFM2 writes every output with ORIGIN (0,0,0) and NXSTART/NYSTART/NZSTART 0, so inputs that carry their placement
in the header (EMDB maps: NSTART; ChimeraX/cryoSPARC-written maps: ORIGIN words) no longer overlay their outputs or
models. This tool writes a NEW file (never in place): a byte copy of the output with header bytes 16-27 (NSTART, as
XYZ because CryoFM2 outputs are MAPC/MAPR/MAPS 1,2,3) and 196-207 (ORIGIN) taken from the reference. Checks first that
the output really is a 1,2,3 map on the reference's XYZ grid with the same voxel size (1e-4 A). stdlib only.

Which reference: -i1 for the half-1 output and avg_external_reconstruct.mrc, -i2 for the half-2 output, -i for
`cfm enhance` outputs; for `cfm denoise -i F -i1 A -i2 B` the output is named after A but holds F -> pass F.
"""
import argparse
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mrcheader as mh  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reference")
    ap.add_argument("cryofm_output")
    ap.add_argument("registered_output")
    ap.add_argument("--force", action="store_true", help="overwrite an existing REGISTERED_OUTPUT")
    ap.add_argument("--tolerance", type=float, default=1e-4, help="voxel-size tolerance in A (default 1e-4)")
    a = ap.parse_args(argv)
    if a.reference.endswith(".gz"):
        pass  # header-only read works through gzip
    if os.path.abspath(a.registered_output) == os.path.abspath(a.cryofm_output):
        sys.exit("refusing to edit the CryoFM2 output in place; give a new path")
    if os.path.exists(a.registered_output) and not a.force:
        sys.exit(f"{a.registered_output} exists (use --force)")
    try:
        ref = mh.read_header(a.reference)
        out = mh.read_header(a.cryofm_output)
    except (OSError, mh.HeaderError) as e:
        sys.exit(f"cannot read header: {e}")
    order = (ref["mapc"], ref["mapr"], ref["maps"])
    if sorted(order) != [1, 2, 3]:
        sys.exit(f"reference MAPC/MAPR/MAPS {order} is not a permutation of 1,2,3")
    if (out["mapc"], out["mapr"], out["maps"]) != (1, 2, 3):
        sys.exit(f"CryoFM2 outputs are written with MAPC/MAPR/MAPS 1,2,3; got {(out['mapc'], out['mapr'], out['maps'])} — is this a CryoFM2 output?")
    ref_size_xyz = mh.xyz_from_crs((ref["nx"], ref["ny"], ref["nz"]), *order)
    out_size_xyz = (out["nx"], out["ny"], out["nz"])
    if tuple(ref_size_xyz) != out_size_xyz:
        sys.exit(f"not the same grid: output XYZ {out_size_xyz} vs reference XYZ {ref_size_xyz}")
    ref_vox = ref["voxel"]
    out_vox = out["voxel"]
    if any(abs(x - y) > a.tolerance for x, y in zip(ref_vox, out_vox)):
        sys.exit(f"voxel size mismatch: output {out_vox} vs reference {ref_vox} (CryoFM2 writes voxel_size.x of the reference on all axes)")
    ref_nstart_xyz = mh.xyz_from_crs((ref["nxstart"], ref["nystart"], ref["nzstart"]), *order)
    ref_origin = ref["origin"]
    if all(v == 0 for v in ref_nstart_xyz) and all(abs(v) < 1e-6 for v in ref_origin):
        print("reference has NSTART 0 and ORIGIN 0: no re-registration needed; copying unchanged")
    shutil.copyfile(a.cryofm_output, a.registered_output)
    end = out["endian"]
    with open(a.registered_output, "r+b") as fh:
        fh.seek(16)
        fh.write(struct.pack(end + "3i", *[int(v) for v in ref_nstart_xyz]))
        fh.seek(196)
        fh.write(struct.pack(end + "3f", *[float(v) for v in ref_origin]))
    chk = mh.read_header(a.registered_output)
    print(f"wrote {a.registered_output}")
    print(f"NSTART (X,Y,Z): {(chk['nxstart'], chk['nystart'], chk['nzstart'])}   (reference CRS {(ref['nxstart'], ref['nystart'], ref['nzstart'])} order {order})")
    print(f"ORIGIN words (A): {tuple(round(v, 4) for v in chk['origin'])}")
    print(f"voxel (A): {tuple(round(v, 5) for v in chk['voxel'])}")
    if any(abs(v) > 1e-6 for v in ref_origin):
        print("note: ORIGIN-word placements are read by ChimeraX only from .mrc (not .map) and by cctbx/Phenix only when on-grid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
