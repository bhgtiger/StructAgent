#!/usr/bin/env python3
"""mrcheader.py -- stdlib MRC2014 header reader + CryoFM2 geometry rules (shared by the cryofm skill scripts).

Reads only the 1024-byte header (gzip transparently), never the voxel data. Re-implements, from the pinned
CryoFM2 code (commit 6448681), what the CLI will do to a map: axis-order check, pad-to-even-cube rule, the
even-box resampling to the 1.5 A model grid, the 64^3/32 patch grid and the batch count.
"""
import gzip
import math
import os
import struct

MODEL_VOXEL_SIZE = 1.5          # sampling_helper.py MODEL_VOXEL_SIZE
DEFAULT_PATCH = 64              # --patch-size default
DEFAULT_OVERLAP = 32            # --patch-overlap default
DEFAULT_BATCH = 4               # --batch-size default
ALLOWED_AXIS_ORDERS = {(1, 2, 3), (3, 2, 1), (2, 1, 3)}   # infer_relion_utils.load_mrc
ACCEPTED_EXT = {".mrc", ".map"}                             # detect_cryoem_file_type
MODE_BYTES = {0: 1, 1: 2, 2: 4, 3: 4, 4: 8, 6: 2, 12: 2, 101: 0.5}


class HeaderError(Exception):
    pass


def _open(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def read_header(path):
    """Return a dict of the MRC header fields (XYZ-ordered cell/origin, CRS-ordered n/nstart)."""
    with _open(path) as fh:
        raw = fh.read(1024)
    if len(raw) < 1024:
        raise HeaderError("file shorter than a 1024-byte MRC header")
    machst = raw[212:216]
    if machst[:1] == b"\x11":
        end = ">"
    else:
        end = "<"
    ints = struct.unpack(end + "10i", raw[0:40])
    nx, ny, nz, mode, nxs, nys, nzs, mx, my, mz = ints
    cella = struct.unpack(end + "3f", raw[40:52])
    cellb = struct.unpack(end + "3f", raw[52:64])
    mapc, mapr, maps = struct.unpack(end + "3i", raw[64:76])
    dmin, dmax, dmean = struct.unpack(end + "3f", raw[76:88])
    ispg, nsymbt = struct.unpack(end + "2i", raw[88:96])
    exttyp = raw[104:108].decode("ascii", "replace")
    (nversion,) = struct.unpack(end + "i", raw[108:112])
    origin = struct.unpack(end + "3f", raw[196:208])
    mapid = raw[208:212]
    (rms,) = struct.unpack(end + "f", raw[216:220])
    (nlabl,) = struct.unpack(end + "i", raw[220:224])
    labels = []
    for i in range(max(0, min(nlabl, 10))):
        labels.append(raw[224 + 80 * i: 304 + 80 * i].decode("ascii", "replace").rstrip("\x00 "))
    h = dict(path=path, endian=end, nx=nx, ny=ny, nz=nz, mode=mode, nxstart=nxs, nystart=nys, nzstart=nzs,
             mx=mx, my=my, mz=mz, cella=cella, cellb=cellb, mapc=mapc, mapr=mapr, maps=maps,
             dmin=dmin, dmax=dmax, dmean=dmean, ispg=ispg, nsymbt=nsymbt, exttyp=exttyp, nversion=nversion,
             origin=origin, mapid=mapid.decode("ascii", "replace"), machst=machst.hex(), rms=rms, nlabl=nlabl,
             labels=labels)
    h["voxel"] = tuple((cella[i] / (mx, my, mz)[i]) if (mx, my, mz)[i] else 0.0 for i in range(3))
    h["voxel_x"] = h["voxel"][0]          # CryoFM2 uses voxel_size.x only
    h["mapid_ok"] = mapid == b"MAP "
    try:
        h["file_bytes"] = os.path.getsize(path) if not path.endswith(".gz") else None
    except OSError:
        h["file_bytes"] = None
    bpv = MODE_BYTES.get(mode)
    h["expected_bytes"] = (1024 + nsymbt + int(nx * ny * nz * bpv)) if bpv is not None else None
    return h


def xyz_from_crs(vals, mapc, mapr, maps):
    """Column/row/section-ordered triple -> XYZ-ordered triple (NX/NY/NZ and NSTART are CRS; MX, CELLA, ORIGIN are XYZ)."""
    out = [None, None, None]
    for v, axis in zip(vals, (mapc, mapr, maps)):
        if axis in (1, 2, 3):
            out[axis - 1] = v
    return tuple(out)


def rescaled_boxsize(box, apix, target=MODEL_VOXEL_SIZE):
    """infer_relion_utils.rescaled_boxsize_from_voxelsize: even box closest to box*apix/target."""
    out_sz = int(round(box * apix / target))
    if out_sz % 2 != 0:
        vs1 = apix * box / (out_sz + 1)
        vs2 = apix * box / (out_sz - 1) if out_sz > 1 else float("inf")
        if abs(vs1 - target) < abs(vs2 - target):
            out_sz += 1
        else:
            out_sz -= 1
    out_vs = apix * box / out_sz if out_sz else float("nan")
    return out_sz, out_vs


def patch_offsets(size, patch=DEFAULT_PATCH, overlap=DEFAULT_OVERLAP):
    """patchify.GridPatches3D._get_patches_locations for one axis; None if the box is too small."""
    end = size + 1 - patch
    step = patch - overlap
    if step <= 0 or end <= 0:
        return None
    idx = list(range(0, end, step))
    if idx[-1] != size - patch:
        idx.append(size - patch)
    return idx


def cryofm_geometry(h, patch=DEFAULT_PATCH, overlap=DEFAULT_OVERLAP, batch=DEFAULT_BATCH, bbox_edges=None):
    """What cfm would do: padding, resampled edge, patches, batches. Returns dict with gate flags."""
    g = {}
    ext = os.path.splitext(h["path"])[1].lower()
    g["ext_ok"] = ext in ACCEPTED_EXT
    g["ext"] = ext
    order = (h["mapc"], h["mapr"], h["maps"])
    g["axis_order"] = order
    g["axis_ok"] = order in ALLOWED_AXIS_ORDERS
    dims = (h["nx"], h["ny"], h["nz"])            # data array shape after load (reordered copies keep the set)
    g["dims"] = dims
    g["cubic"] = len(set(dims)) == 1
    apix = h["voxel_x"]
    g["apix"] = apix
    g["apix_ok"] = apix > 0
    if g["cubic"]:
        edge = dims[0]
        g["padded_edge"] = edge
        g["odd_cube_assert"] = (edge % 2 == 1)     # odd cubic boxes are not padded and hit assert iz % 2 == 0
    else:
        edge = max(dims)
        if edge % 2:
            edge += 1
        g["padded_edge"] = edge
        g["odd_cube_assert"] = False
    g["physical_box_A"] = edge * apix if apix else None
    if apix > 0 and not g["odd_cube_assert"]:
        S, vs = rescaled_boxsize(edge, apix)
        g["resampled_edge"] = S
        g["model_voxel_A"] = vs
        edges = bbox_edges if bbox_edges else (S, S, S)
        offs = [patch_offsets(e, patch, overlap) for e in edges]
        if any(o is None for o in offs):
            g["patches"] = None
            g["min_box_ok"] = False
        else:
            g["patches"] = offs[0].__len__() * offs[1].__len__() * offs[2].__len__()
            g["offsets_per_axis"] = [len(o) for o in offs]
            g["min_box_ok"] = True
        g["batches"] = math.ceil(g["patches"] / batch) if g["patches"] else None
    else:
        g["resampled_edge"] = None
        g["model_voxel_A"] = None
        g["patches"] = None
        g["batches"] = None
        g["min_box_ok"] = False
    nstart = (h["nxstart"], h["nystart"], h["nzstart"])
    g["nstart_crs"] = nstart
    g["nstart_xyz"] = xyz_from_crs(nstart, *order) if g["axis_ok"] else nstart
    g["origin_A"] = h["origin"]
    g["placement_nonzero"] = any(v != 0 for v in nstart) or any(abs(v) > 1e-6 for v in h["origin"])
    g["band_limit_note"] = apix < MODEL_VOXEL_SIZE if apix else False
    g["pass"] = bool(g["ext_ok"] and g["axis_ok"] and g["apix_ok"] and not g["odd_cube_assert"] and g["min_box_ok"])
    return g
