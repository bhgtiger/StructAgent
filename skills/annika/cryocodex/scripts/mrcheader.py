#!/usr/bin/env python3
"""mrcheader.py -- stdlib MRC2014 header reader + CryoCodex v1.0.0 geometry rules (shared by the cryocodex scripts).

Reads only the 1024-byte header (gzip transparently, for inspection only: CryoCodex itself rejects .gz), never the
voxel data, except read_data() which check_outputs.py --stats uses. Re-implements, from the pinned CryoCodex code
(commit a35e73a, files grid_utils.py / data_processor.py / predict.py), what predict.py will do to a map:
the input-name gate, the orthogonal-cell gate, the regridding to 1.0 A, the 48^3 window grid, the box padding, the
reverse interpolation box, and a host-RAM estimate. Everything here is SOURCED (code reading) or DERIVED (arithmetic),
matched by the 2026-11-24 live runs (150^3 at 1.043 A -> 156^3; 432^3 at 0.86 A -> 371^3; 40^3 -> 41^3 padded to
48^3; reverse boxes). Float32 rounding of the voxel size is emulated so boundary cases match NumPy.
"""
import gzip
import math
import os
import struct
from array import array

PIN_COMMIT = "a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17"   # tag v1.0.0
WEIGHTS_BYTES = 470938660                                 # HEAD 2026-11-24, no published checksum
WEIGHTS_URL = "https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth"
TARGET_VOXEL = 1.0          # predict.py:15 DateProcessor(target_voxel_size=1.0)
WINDOW = 48                 # predict.py:17 WINDOW_SIZE
MARGIN = 2                  # grid_utils.py:371 margin=2 -> each window contributes [i+2, i+46)
DEFAULT_STRIDE = 12         # predict.py:180
DEFAULT_BATCH = 9           # predict.py:181
MAX_SAFE_STRIDE = WINDOW - 2 * MARGIN    # 44 (derived: larger strides leave uncovered voxels)
CROP_PAD = 5                # data_processor.py:33 crop_by_mask(pad=5)
BYTES_PER_WINDOW = (4 + 1) * WINDOW ** 3 * 4   # predict.py:92 outputs (4 ch) + seg input (1 ch), float32 = 2,211,840 B
OUTPUT_SUFFIXES = ("", "_out_score", "_in_mask", "_in_score")   # predict.py:149-152
MODE_BYTES = {0: 1, 1: 2, 2: 4, 3: 4, 4: 8, 6: 2, 12: 2, 101: 0.5}
MRCFILE_MODES = {0, 1, 2, 4, 6, 12}      # modes mrcfile reads as real/complex arrays; others are unusual for maps


class HeaderError(Exception):
    pass


def f32(x):
    """Round a Python float to float32 precision (as NumPy stores voxel sizes)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _open(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def read_header(path):
    """Return a dict of the MRC header fields (XYZ-ordered cell/origin/voxel, CRS-ordered n/nstart)."""
    with _open(path) as fh:
        raw = fh.read(1024)
    if len(raw) < 1024:
        raise HeaderError("file shorter than a 1024-byte MRC header")
    machst = raw[212:216]
    end = ">" if machst[:1] == b"\x11" else "<"
    nx, ny, nz, mode, nxs, nys, nzs, mx, my, mz = struct.unpack(end + "10i", raw[0:40])
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
    labels = [raw[224 + 80 * i: 304 + 80 * i].decode("ascii", "replace").rstrip("\x00 ") for i in range(max(0, min(nlabl, 10)))]
    h = dict(path=path, endian=end, nx=nx, ny=ny, nz=nz, mode=mode, nxstart=nxs, nystart=nys, nzstart=nzs,
             mx=mx, my=my, mz=mz, cella=cella, cellb=cellb, mapc=mapc, mapr=mapr, maps=maps,
             dmin=dmin, dmax=dmax, dmean=dmean, ispg=ispg, nsymbt=nsymbt, exttyp=exttyp, nversion=nversion,
             origin=origin, mapid=mapid.decode("ascii", "replace"), machst=machst.hex(), rms=rms, nlabl=nlabl,
             labels=labels)
    # mrcfile: voxel_size = cella / (mx, my, mz), stored as float32 (XYZ order)
    h["voxel"] = tuple(f32(cella[i] / m) if m else 0.0 for i, m in enumerate((mx, my, mz)))
    h["mapid_ok"] = mapid == b"MAP "
    try:
        h["file_bytes"] = None if path.endswith(".gz") else os.path.getsize(path)
    except OSError:
        h["file_bytes"] = None
    bpv = MODE_BYTES.get(mode)
    h["expected_bytes"] = (1024 + nsymbt + int(nx * ny * nz * bpv)) if bpv is not None else None
    return h


def axis_order_ok(h):
    return sorted((h["mapc"], h["mapr"], h["maps"])) == [1, 2, 3]


def xyz_from_crs(vals, mapc, mapr, maps):
    """Column/row/section-ordered triple -> XYZ-ordered triple (grid_utils.py:169-174)."""
    out = [None, None, None]
    for v, axis in zip(vals, (mapc, mapr, maps)):
        if axis in (1, 2, 3):
            out[axis - 1] = v
    return tuple(out)


def name_gate(path):
    """grid_utils.py:215: the path string must end in 'map' or 'mrc' (case-sensitive). Returns (ok, reason)."""
    if path.endswith("map") or path.endswith("mrc"):
        return True, "path ends in 'map'/'mrc' (accepted)"
    low = path.lower()
    if low.endswith((".gz", ".bz2", ".zip")):
        why = "compressed: decompress first (gzip -dc in.map.gz > in.map)"
    elif low.endswith(("map", "mrc")):
        why = "upper-case extension: the test is case-sensitive; rename to lower-case .mrc/.map"
    elif low.endswith((".ccp4", ".mrcs", ".st", ".rec")):
        why = "extension not accepted: copy or symlink to a name ending in .mrc"
    else:
        why = "name does not end in 'map' or 'mrc'"
    return False, why + " -> RuntimeError 'File <path> is not a cryo-em density map file format.'"


def cell_orthogonal(h):
    """grid_utils.py:160-167: all three CELLB angles must equal 90.0 exactly (else '# Input grid is not orthogonal. EXIT.')."""
    return all(a == 90.0 for a in h["cellb"])


def dims_xyz(h):
    return xyz_from_crs((h["nx"], h["ny"], h["nz"]), h["mapc"], h["mapr"], h["maps"])


def input_origin_A(h):
    """grid_utils.py:157-179: origin = header ORIGIN + (nxstart, nystart, nzstart) permuted to XYZ x voxel (both summed)."""
    st = xyz_from_crs((h["nxstart"], h["nystart"], h["nzstart"]), h["mapc"], h["mapr"], h["maps"])
    return tuple(h["origin"][i] + st[i] * h["voxel"][i] for i in range(3))


def needs_resampling(h):
    """True when parse_map resamples (grid_utils.py:181-195, 217-222): voxel not exactly 1.0 on every axis, or the
    origin is not on the 1 A lattice (then a second pass resamples with a sub-voxel shift)."""
    if any(v != TARGET_VOXEL for v in h["voxel"]):
        return True
    o = input_origin_A(h)
    return any(abs(round(x) - x) >= 1e-4 for x in o)


def regrid_dims(dims, voxel):
    """grid_utils.py:38-41 Interp3D.cubic: floor(voxel*(n-1)/1.0)+1 per axis; unchanged when voxel == 1.0."""
    out = []
    for n, v in zip(dims, voxel):
        if v == TARGET_VOXEL:
            out.append(n)
        else:
            out.append(int(math.floor(v * (n - 1) / TARGET_VOXEL)) + 1)
    return tuple(out)


def reverse_dims(dims_1A, native_voxel):
    """grid_utils.py:79-81 Interp3D.inverse_cubic: ceil(1.0*(n-1)/native)+1 per axis (used by --reverse_interpolation True)."""
    return tuple(int(math.ceil(TARGET_VOXEL * (n - 1) / v)) + 1 for n, v in zip(dims_1A, native_voxel))


def reverse_skipped(native_voxel):
    """predict.py:128 np.allclose(native, 1.0, atol=1e-4) (rtol 1e-5): reverse interpolation is skipped."""
    return all(abs(v - TARGET_VOXEL) <= 1e-4 + 1e-5 * TARGET_VOXEL for v in native_voxel)


def padded(dims):
    """data_processor.py:59-61: axes shorter than 48 are zero-padded at the far end up to 48."""
    return tuple(max(n, WINDOW) for n in dims)


def window_starts(n, stride=DEFAULT_STRIDE):
    """grid_utils.py:344-347 get_indices on an axis already padded to >= 48."""
    if n < WINDOW:
        raise ValueError("axis shorter than the window; pad first")
    if stride < 1:
        raise ValueError("stride must be >= 1")
    return sorted(set(list(range(0, n - WINDOW, stride)) + [n - WINDOW]))


def window_count(dims, stride=DEFAULT_STRIDE):
    p = padded(dims)
    c = 1
    for n in p:
        c *= len(window_starts(n, stride))
    return c


def uncovered_voxels_per_axis(n, stride=DEFAULT_STRIDE):
    """Voxels of one padded axis that no window's inner [i+2, i+46) covers (grid_utils.py:383-393). The outer 2 voxels
    at each end are never covered (written as 0); interior gaps appear only for stride > 44. Derived."""
    cov = [False] * n
    for i in window_starts(n, stride):
        for j in range(i + MARGIN, i + WINDOW - MARGIN):
            cov[j] = True
    return [j for j, c in enumerate(cov) if not c]


def interior_gaps(n, stride=DEFAULT_STRIDE):
    return [j for j in uncovered_voxels_per_axis(n, stride) if MARGIN <= j < n - MARGIN]


RUNTIME_BASE_BYTES = 1.4e9       # Python + torch + CUDA context, fitted to max RSS of live runs (2026-11-24)
BYTES_PER_VOXEL_1A = 20          # working copies of the 1 A grid, fitted (150^3 fast/normal, 432^3 fast within ~5 %)


def ram_estimate_bytes(n_windows, n_voxels_1A):
    """Host RAM (max RSS) estimate: runtime base + the window arrays (predict.py:90-92) + working copies of the 1 A grid.
    Fitted on 2026-11-24 live runs: 150^3 fast 1.8 GB (175 windows), 150^3 normal 3.9 GB (1000 windows), 432^3 fast
    4.1 GB (693 windows) -- all within ~5 %. Normal mode on big maps is extrapolated (derived)."""
    return int(RUNTIME_BASE_BYTES + n_windows * BYTES_PER_WINDOW + BYTES_PER_VOXEL_1A * n_voxels_1A)


def geometry(h, stride=DEFAULT_STRIDE, batch=DEFAULT_BATCH):
    """What predict.sh/predict.py would do to this header. Returns dict with gate flags and derived boxes."""
    g = {}
    g["name_ok"], g["name_reason"] = name_gate(h["path"])
    g["mapid_ok"] = h["mapid_ok"]
    g["axis_ok"] = axis_order_ok(h)
    g["orthogonal"] = cell_orthogonal(h)
    g["mode_ok"] = h["mode"] in MRCFILE_MODES
    g["voxel"] = h["voxel"]
    g["voxel_ok"] = all(v > 0 for v in h["voxel"])
    g["anisotropic"] = any(abs(v - h["voxel"][0]) > 1e-4 for v in h["voxel"][1:])
    g["size_ok"] = None
    if h["file_bytes"] is not None and h["expected_bytes"] is not None:
        g["size_ok"] = h["file_bytes"] >= h["expected_bytes"]
        g["size_extra"] = h["file_bytes"] > h["expected_bytes"]
    # header statistics may be unset (MRC2014: DMAX < DMIN means "not computed"); then the check is unknown (None)
    if math.isnan(h["dmax"]) or math.isnan(h["dmin"]) or h["dmax"] < h["dmin"] or (h["dmin"] == 0 and h["dmax"] == 0):
        g["positive_density_header"] = None
    else:
        g["positive_density_header"] = h["dmax"] > 0   # grid_utils.py:224 quantile of positive voxels fails without any
    g["dims_xyz"] = dims_xyz(h) if g["axis_ok"] else (h["nx"], h["ny"], h["nz"])
    g["origin_A"] = input_origin_A(h) if g["axis_ok"] else tuple(h["origin"])
    g["both_origin_fields"] = any(abs(v) > 1e-6 for v in h["origin"]) and any(v != 0 for v in (h["nxstart"], h["nystart"], h["nzstart"]))
    if g["voxel_ok"] and g["axis_ok"]:
        g["resampled"] = needs_resampling(h)
        g["dims_1A"] = regrid_dims(g["dims_xyz"], h["voxel"])
        g["box_normal"] = padded(g["dims_1A"])
        g["windows_normal"] = window_count(g["dims_1A"], stride) if stride >= 1 else None
        g["batches_normal"] = math.ceil(g["windows_normal"] / batch) if (g["windows_normal"] and batch >= 1) else None
        nvox = g["dims_1A"][0] * g["dims_1A"][1] * g["dims_1A"][2]
        g["voxels_1A"] = nvox
        g["ram_normal_bytes"] = ram_estimate_bytes(g["windows_normal"], nvox) if g["windows_normal"] else None
        g["origin_on_lattice"] = all(abs(round(x) - x) < 1e-4 for x in g["origin_A"])
        g["keep_size_box"] = g["dims_1A"]
        g["reverse_skipped"] = reverse_skipped(h["voxel"])
        g["keep_size_reverse_box"] = g["dims_1A"] if g["reverse_skipped"] else reverse_dims(g["dims_1A"], h["voxel"])
        g["normal_reverse_box"] = g["box_normal"] if g["reverse_skipped"] else reverse_dims(g["box_normal"], h["voxel"])
        g["small_axis"] = any(n < WINDOW for n in g["dims_1A"])
        g["stride_gaps"] = stride > MAX_SAFE_STRIDE
    else:
        for k in ("resampled", "dims_1A", "box_normal", "windows_normal", "batches_normal", "voxels_1A", "ram_normal_bytes",
                  "origin_on_lattice", "keep_size_box", "reverse_skipped", "keep_size_reverse_box", "normal_reverse_box",
                  "small_axis", "stride_gaps"):
            g[k] = None
    g["pass"] = bool(g["name_ok"] and g["mapid_ok"] and g["axis_ok"] and g["orthogonal"] and g["voxel_ok"]
                     and g["mode_ok"] and g["size_ok"] is not False and g["positive_density_header"] is not False)
    return g


def read_data(path, h=None):
    """Read the voxel data of an uncompressed mode-2 (float32) map as array('f') in file order (x fastest)."""
    h = h or read_header(path)
    if h["mode"] != 2:
        raise HeaderError(f"mode {h['mode']}: only float32 (mode 2) data are read here")
    n = h["nx"] * h["ny"] * h["nz"]
    a = array("f")
    with open(path, "rb") as fh:
        fh.seek(1024 + h["nsymbt"])
        a.fromfile(fh, n)
    import sys
    if (h["endian"] == "<") != (sys.byteorder == "little"):
        a.byteswap()
    return a


def shell_max_abs(a, nx, ny, nz, width=MARGIN):
    """Max |value| over the outer `width`-voxel shell of a C-ordered (z, y, x) array stored flat."""
    m = 0.0
    plane = nx * ny
    for z in range(nz):
        base = z * plane
        if z < width or z >= nz - width:
            seg = a[base: base + plane]
            if len(seg):
                m = max(m, max(seg), -min(seg))
            continue
        for y in range(ny):
            row = base + y * nx
            if y < width or y >= ny - width:
                seg = a[row: row + nx]
            else:
                seg = a[row: row + width] + a[row + nx - width: row + nx]
            if len(seg):
                m = max(m, max(seg), -min(seg))
    return m


def fmt_bytes(b):
    if b is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1000 or unit == "TB":
            return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
        b /= 1000.0
    return f"{b:.1f} TB"
