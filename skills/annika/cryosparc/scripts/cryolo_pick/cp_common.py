"""Shared helpers for the crYOLO general-model picking -> cryoSPARC extract/2D tools.

Portable: nothing here is hard-coded to a host, project, or job. Everything
site- and dataset-specific is read from a JSON config (see cryolo_pick.example.json
and README.md). Credentials come ONLY from the environment variables
CRYOSPARC_EMAIL and CRYOSPARC_PASSWORD and are never written or echoed.

This bundle straddles TWO environments:
  * a cryosparc-tools interpreter (CryoSPARC API, numpy) for everything that talks
    to the master (inspect / inject / extract / verify / class2d);
  * a crYOLO conda env (CUDA/TF + matplotlib) for the picking itself and the montage
    rendering (make_montage.py). cp_common.py only imports cryosparc-tools/numpy.

Run the cryosparc-tools steps with an interpreter whose version matches the master.
Export credentials first (never put them on the command line — that lands in shell
history and logs):

    export CRYOSPARC_EMAIL='you@lab.org'
    export CRYOSPARC_PASSWORD='...'      # typed at the shell, never committed
    /path/to/cs-tools-venv/bin/python cryolo_pick.py inspect --config cryolo_pick.json
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np

REQUIRED_TOP = ("instance", "project", "workspace", "source_job")


def die(msg: str) -> "NoReturn":  # noqa: F821
    raise SystemExit(f"error: {msg}")


def load_config(path: str) -> Dict[str, Any]:
    """Read and minimally validate the crYOLO picking JSON config."""
    if not path or not os.path.isfile(path):
        die(f"config file not found: {path!r} (copy cryolo_pick.example.json and edit it)")
    with open(path) as fh:
        try:
            cfg = json.load(fh)
        except json.JSONDecodeError as e:
            die(f"config {path!r} is not valid JSON: {e}")
    missing = [k for k in REQUIRED_TOP if k not in cfg]
    if missing:
        die(f"config {path!r} is missing required keys: {', '.join(missing)}")
    inst = cfg["instance"]
    for k in ("host", "port"):
        if k not in inst:
            die(f"config 'instance' block is missing '{k}'")
    inst.setdefault("license", None)

    # which exposures output to read off the source job (motion-corrected + CTF'd)
    cfg.setdefault("source_output", "split_0")

    # particle geometry / box sizing (all in Angstrom unless _pix)
    cfg.setdefault("particle_diameter_A", None)   # particle longest dimension (A)
    cfg.setdefault("cryolo_box_pix", None)        # crYOLO detection/anchor box (~particle longest / psize)
    cfg.setdefault("box_extract_pix", None)       # Extract box (~1.5-2x particle longest, FFT-friendly)
    cfg.setdefault("box_crop_pix", None)          # Fourier-crop output box (-> ~1.5-2 A/px)
    cfg.setdefault("output_f16", True)            # 16-bit float extract output

    # picking thresholds
    cfg.setdefault("threshold", 0.3)              # crYOLO -t confidence at predict time
    cfg.setdefault("target_per_image", None)      # used by 'threshold' to recommend a confidence

    # 2D classification
    cfg.setdefault("class2D_K", 50)
    cfg.setdefault("class2D_window_outer_A", None)   # optional tight circular mask (A)
    cfg.setdefault("class2D_min_res_align", None)    # optional high-pass for alignment (A)

    # queueing / scratch
    cfg.setdefault("lane", None)
    cfg.setdefault("work_dir", os.path.dirname(os.path.abspath(path)))

    # crYOLO env + model (consumed by cryolo_pick.py predict/config; shelled out)
    cfg.setdefault("cryolo", {})
    cr = cfg["cryolo"]
    cr.setdefault("conda_sh", None)        # path to <conda>/etc/profile.d/conda.sh
    cr.setdefault("env", "cryolo")         # conda env name
    cr.setdefault("general_model", None)   # path to the filter-matched *.h5 general model
    cr.setdefault("filter", "LOWPASS")     # LOWPASS | JANNI | NONE — MUST match the model
    cr.setdefault("low_pass_cutoff", 0.1)  # only used with --filter LOWPASS

    # python interpreter inside the crYOLO env for make_montage.py (matplotlib)
    cfg.setdefault("montage_python", None)
    return cfg


def connect(cfg: Dict[str, Any]):
    """Connect to cryoSPARC. Credentials come from env vars only."""
    from cryosparc.tools import CryoSPARC

    em = os.environ.get("CRYOSPARC_EMAIL")
    pw = os.environ.get("CRYOSPARC_PASSWORD")
    if not em or not pw:
        die("set CRYOSPARC_EMAIL and CRYOSPARC_PASSWORD in the environment "
            "(never put them in the config or any file)")
    inst = cfg["instance"]
    kwargs = dict(host=inst["host"], base_port=int(inst["port"]), email=em, password=pw)
    if inst.get("license"):  # instance license id; deprecated kwarg but still accepted
        kwargs["license"] = inst["license"]
    cs = CryoSPARC(**kwargs)
    if not cs.test_connection():
        die("cryoSPARC connection / authentication failed")
    return cs


def load_exposures(cs, cfg):
    """Load the source exposures dataset (the motion-corrected + CTF'd micrographs).

    Returns (job, dataset). The dataset carries the fields crYOLO/Extract need:
    uid, micrograph_blob/{path,shape,psize_A}, mscope_params/exp_group_id, ctf.
    """
    job = cs.find_job(cfg["project"], cfg["source_job"])
    out = cfg["source_output"]
    ds = job.load_output(out, slots=["micrograph_blob", "mscope_params", "ctf"])
    return job, ds


def read_cbox(path: str, conf_min: float) -> List[Tuple[float, float, float]]:
    """Parse one crYOLO .cbox file, returning [(center_x, center_y, confidence), ...]
    for detections at or above conf_min.

    .cbox columns (v1.0): CoordinateX CoordinateY CoordinateZ Width Height Depth
    EstWidth EstHeight Confidence NumBoxes Angle. CoordinateX/Y is the box LOWER-LEFT
    corner and Width==Height==box, so the particle CENTRE = corner + box/2 (verified:
    corner 3471.9 + 84 = 3555.9 = the matching STAR centre). Confidence is column 9
    (0-indexed 8). CBOX holds EVERY detection with its confidence, so filtering at a
    new conf_min is mathematically identical to re-running cryolo_predict -t — no GPU
    re-run needed.
    """
    out: List[Tuple[float, float, float]] = []
    started = False
    for ln in open(path):
        s = ln.strip()
        if s.startswith("_Angle"):
            started = True
            continue
        if started and s and re.match(r"^[-\d.]", s):
            p = s.split()
            if len(p) < 9:
                continue
            try:
                x, y, w, h, c = float(p[0]), float(p[1]), float(p[3]), float(p[4]), float(p[8])
            except ValueError:
                continue
            if c >= conf_min:
                out.append((x + w / 2.0, y + h / 2.0, c))
    return out


def cbox_files_by_stem(cbox_dir: str) -> Dict[str, str]:
    """Map micrograph stem (basename without the .cbox suffix) -> .cbox path."""
    import glob
    return {os.path.basename(f)[:-5]: f for f in glob.glob(os.path.join(cbox_dir, "*.cbox"))}


def per_image_distribution(cbox_dir: str, confidences) -> Dict[float, Dict[str, float]]:
    """For each candidate confidence, count picks per .cbox file and summarise.

    Returns {conf: {'total': int, 'images': int, 'median': float, 'mean': float}}.
    Used by the 'threshold' subcommand to pick a confidence that hits a target
    particles/image without any GPU re-run (the CBOX re-threshold trick).
    """
    files = list(cbox_files_by_stem(cbox_dir).values())
    if not files:
        die(f"no .cbox files under {cbox_dir} (run 'predict' first)")
    # read each cbox once at the lowest candidate threshold, keep confidences
    lo = float(min(confidences))
    per_file_conf = []
    for f in files:
        per_file_conf.append(np.array([c for (_x, _y, c) in read_cbox(f, lo)], dtype="f4"))
    dist: Dict[float, Dict[str, float]] = {}
    for conf in confidences:
        counts = np.array([int((cc >= conf).sum()) for cc in per_file_conf], dtype="i8")
        dist[float(conf)] = {
            "total": int(counts.sum()),
            "images": int(len(counts)),
            "median": float(np.median(counts)) if len(counts) else 0.0,
            "mean": float(counts.mean()) if len(counts) else 0.0,
        }
    return dist


def inject_picks(proj, cfg, ds, picks_by_index, flip_y: bool = False):
    """Create the passthrough-FREE external picks job and save the particle output.

    `picks_by_index` maps exposure row index -> list of (center_x_px, center_y_px).
    Implements the EXACT verified external-job pattern: a 'particle' output with a
    'location' slot and NO passthrough. (Adding passthrough='input_micrographs' fails
    with APIError 422 "specified passthrough input ... does not match output type
    particle" — a particle output cannot passthrough an exposure input. The
    micrograph<->particle link is carried by location/micrograph_uid; Extract pulls
    per-particle CTF from the 'micrographs' input.)

    Returns (job, total_picks).
    """
    paths = ds["micrograph_blob/path"]
    uids = ds["uid"]
    shapes = ds["micrograph_blob/shape"]
    n = len(ds)
    if "mscope_params/exp_group_id" in ds.fields():
        egids = ds["mscope_params/exp_group_id"]
    else:
        egids = np.zeros(n, "u4")

    mu, eg, msh, cxf, cyf, mpath = [], [], [], [], [], []
    for i in range(n):
        picks = picks_by_index.get(i)
        if not picks:
            continue
        path = paths[i].decode() if isinstance(paths[i], bytes) else paths[i]
        ny, nx = int(shapes[i][0]), int(shapes[i][1])
        for cx, cy in picks:
            fy = cy / ny
            mu.append(int(uids[i]))
            eg.append(int(egids[i]))
            msh.append([ny, nx])
            cxf.append(cx / nx)
            cyf.append(1.0 - fy if flip_y else fy)
            mpath.append(path)

    total = len(mu)
    if total == 0:
        die("no picks to inject (every exposure had 0 detections at this confidence)")

    job = proj.create_external_job(cfg["workspace"], title=cfg.get("_inject_title", "crYOLO picks"))
    job.add_input("exposure", name="input_micrographs", min=1,
                  slots=["micrograph_blob", "ctf", "mscope_params"],
                  title="source exposures")
    job.connect("input_micrographs", cfg["source_job"], cfg["source_output"])
    job.add_output("particle", name="picked_particles", slots=["location"],
                   title="crYOLO picks")   # NO passthrough — see docstring
    out = job.alloc_output("picked_particles", total)
    out["location/micrograph_uid"] = np.array(mu, "u8")
    out["location/exp_group_id"] = np.array(eg, "u4")
    out["location/micrograph_path"] = np.array(mpath, object)
    out["location/micrograph_shape"] = np.array(msh, "u4")
    out["location/center_x_frac"] = np.array(cxf, "f4")
    out["location/center_y_frac"] = np.array(cyf, "f4")
    with job.run():
        job.save_output("picked_particles", out)
    return job, total


def resolve_lane(cfg: Dict[str, Any]):
    """Lane precedence: env CS_LANE overrides config 'lane'."""
    return os.environ.get("CS_LANE") or cfg.get("lane")


def suggest_box_sizes(particle_diameter_A, psize_A):
    """From the particle longest dimension (A) and pixel size (A/px) suggest:
      crYOLO box   ~ particle / psize                (anchor box)
      extract box  ~ 1.8x particle / psize, rounded to an FFT-friendly even size
      crop box     ~ extract box that yields ~1.5-2 A/px output
    Returns a dict of int suggestions; any None input yields None for that key.
    """
    res = {"cryolo_box_pix": None, "extract_box_pix": None, "crop_box_pix": None}
    if not particle_diameter_A or not psize_A:
        return res
    cryolo_box = int(round(particle_diameter_A / psize_A))
    extract = int(round(1.8 * particle_diameter_A / psize_A))
    res["cryolo_box_pix"] = cryolo_box
    res["extract_box_pix"] = _fft_friendly(extract)
    # crop so output pixel ~1.7 A/px (extract box * psize / out_psize)
    out_psize = 1.7
    crop = int(round(res["extract_box_pix"] * psize_A / out_psize))
    res["crop_box_pix"] = _fft_friendly(crop)
    return res


def _fft_friendly(n: int) -> int:
    """Round n up to the next even number that factors into small primes (2,3,5,7)."""
    if n < 2:
        return 2
    n += n % 2
    while True:
        m = n
        for p in (2, 3, 5, 7):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 2
