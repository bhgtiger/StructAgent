#!/usr/bin/env python3
r"""map_relion_classes.py — map a RELION Class3D result back to cryoSPARC particle uids.

It joins a RELION classification (which carries rlnClassNumber per particle) back onto
the cryoSPARC SOURCE job's particles (which carry the durable `uid`), so the class
labels can be pushed back into cryoSPARC by cs_roundtrip.py WITHOUT re-importing
particle stacks (poses + CTF stay native).

The join key is (stack-stem, within-stack-index):
  * RELION side: rlnImageName is `NNNNNN@/path/<stem>[suffix].mrcs`. The index is
    1-based; <stem> is the basename with the .mrcs/.mrc extension and the optional
    downsample suffix (e.g. `_ds128`) removed.
  * cryoSPARC side: each particle has blob/path and blob/idx (0-based). The stem is
    basename(blob/path) without extension; the index is blob/idx + 1.
This is robust to row reordering. It ABORTS if any RELION particle fails to match a
source uid (the original round-trip required 0 unmatched).

Outputs an .npz with two equal-length arrays: `uid` (uint64) and `cls` (int32).

Usage (run with a cryosparc-tools interpreter; export credentials first so they
never land on the command line / in shell history):
  export CRYOSPARC_EMAIL='you@lab.org'
  export CRYOSPARC_PASSWORD='...'
  map_relion_classes.py --config roundtrip.json \
      --data-star /path/Class3D/run_it025_data.star \
      --strip-suffix _ds128 \   # the suffix YOUR relion_image_handler downsample added; '' if none
      --out /path/class_assign_uid.npz

  # If RELION row order is a 1:1 order-preserving descendant of the source job
  # (no particles dropped/reordered), you can skip the key join:
  map_relion_classes.py --config roundtrip.json --data-star ... --by order --out ...
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

from rt_common import load_config, connect, die  # noqa: E402


def _stem(name: str, strip_suffix: str | None) -> str:
    base = os.path.basename(name)
    for ext in (".mrcs", ".mrc"):
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    if strip_suffix and base.endswith(strip_suffix):
        base = base[: -len(strip_suffix)]
    return base


def read_relion_classes(data_star: str, strip_suffix: str | None):
    """Parse the data_particles loop; return parallel lists of (stem, idx1based, cls)
    in file order. Dependency-free STAR loop reader (no numpy/pandas needed)."""
    stems, idxs, clss = [], [], []
    img_col = cls_col = None
    in_particles = in_loop = False
    labels = []
    with open(data_star) as fh:
        for raw in fh:
            line = raw.strip()
            if line.startswith("data_"):
                in_particles = (line == "data_particles")
                in_loop = False
                labels = []
                img_col = cls_col = None
                continue
            if not in_particles:
                continue
            if line == "loop_":
                in_loop = True
                labels = []
                continue
            if in_loop and line.startswith("_"):
                lab = line.split()[0]  # e.g. _rlnImageName  (drop the '#N')
                labels.append(lab)
                if lab == "_rlnImageName":
                    img_col = len(labels) - 1
                elif lab == "_rlnClassNumber":
                    cls_col = len(labels) - 1
                continue
            if in_loop and line and not line.startswith("#"):
                if img_col is None or cls_col is None:
                    die(f"{data_star}: data_particles lacks _rlnImageName and/or "
                        "_rlnClassNumber")
                parts = line.split()
                img = parts[img_col]
                if "@" not in img:
                    die(f"unexpected rlnImageName (no '@'): {img!r}")
                idx_s, path = img.split("@", 1)
                stems.append(_stem(path, strip_suffix))
                idxs.append(int(idx_s))               # 1-based
                clss.append(int(float(parts[cls_col])))
    if not stems:
        die(f"{data_star}: no data_particles rows found")
    return stems, idxs, clss


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="round-trip JSON config")
    ap.add_argument("--data-star", required=True,
                    help="RELION Class3D run_itNNN_data.star to read classes from")
    ap.add_argument("--out", required=True, help="output .npz path (uid, cls)")
    ap.add_argument("--by", choices=("key", "order"), default="key",
                    help="join strategy: 'key' (stem+index, robust) or 'order' (row 1:1)")
    ap.add_argument("--strip-suffix", default="",
                    help="downsample suffix your relion_image_handler run appended to the "
                         "RELION stack stems, to strip before matching the cryoSPARC stems "
                         "(e.g. _ds128 if you downsampled to box 128). Default empty = none. "
                         "If unmatched>0, this is the first thing to check.")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if not os.path.isfile(args.data_star):
        die(f"data star not found: {args.data_star}")
    strip = args.strip_suffix or None

    cs = connect(cfg)
    job = cs.find_job(cfg["project"], cfg["source_job"])
    ds = job.load_output(cfg["source_outputs"]["particles"], slots="all")
    src_uid = np.asarray(ds["uid"])

    stems, idxs, clss = read_relion_classes(args.data_star, strip)
    rel_cls = np.asarray(clss, dtype=np.int32)

    if args.by == "order":
        if len(stems) != len(src_uid):
            die(f"--by order needs equal counts: RELION {len(stems)} vs "
                f"source {len(src_uid)}")
        uid_out, cls_out = src_uid.astype(np.uint64), rel_cls
        print(f"order join: {len(uid_out)} particles paired by row")
    else:
        src_path = np.asarray(ds["blob/path"]).astype(str)
        src_idx = np.asarray(ds["blob/idx"]).astype(np.int64)  # 0-based
        key2uid = {}
        for p, i, u in zip(src_path, src_idx, src_uid):
            key2uid[(_stem(p, None), int(i) + 1)] = int(u)
        uid_list, cls_list, unmatched = [], [], 0
        for stem, idx1, c in zip(stems, idxs, rel_cls):
            u = key2uid.get((stem, idx1))
            if u is None:
                unmatched += 1
                if unmatched <= 5:
                    print(f"  UNMATCHED: stem={stem!r} idx={idx1}")
                continue
            uid_list.append(u)
            cls_list.append(int(c))
        if unmatched:
            die(f"{unmatched} RELION particles did not match a source uid. "
                f"First check --strip-suffix (currently {strip!r}): it must equal the "
                "suffix relion_image_handler appended when you downsampled (e.g. _ds128 for "
                "box 128), or '' if you did not downsample. Also confirm source_job is the "
                "job csparc2star converted from. (The round-trip requires 0 unmatched.)")
        uid_out = np.asarray(uid_list, dtype=np.uint64)
        cls_out = np.asarray(cls_list, dtype=np.int32)
        print(f"key join: {len(uid_out)} particles matched, 0 unmatched")

    classes, counts = np.unique(cls_out, return_counts=True)
    print("class distribution:")
    for c, n in zip(classes, counts):
        print(f"  class {int(c)}: {int(n)}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    np.savez(args.out, uid=uid_out, cls=cls_out)
    print(f"\nwrote {args.out} (uid, cls). Next: cs_roundtrip.py inspect --config ...")


if __name__ == "__main__":
    main()
