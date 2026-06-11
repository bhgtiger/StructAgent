#!/usr/bin/env python3
"""make_montage.py — render PNGs from .npy dumps produced by cryolo_pick.py.

Runs in the crYOLO conda env, which has matplotlib (cryosparc-tools' env does not).
It imports ONLY numpy + matplotlib — never cryosparc-tools — so it stays usable from
the crYOLO interpreter. The two-step split (cryosparc-tools dumps .npy here; this
renders) is deliberate: it keeps the heavy CS API out of the picking env.

Two modes:
  verify   render the extracted-particle montage + average/std PNGs
           (from verif_imgs.npy / verif_avg.npy / verif_std.npy, written by
           `cryolo_pick.py verify`). The AVERAGE is the Y-flip test: a faint
           CENTRED blob = localization OK; a flat average = suspect flip.
  class2d  render the 2D class-average montage (sorted by particle count)
           (from cls_imgs.npy / cls_counts.npy, written by
           `cryolo_pick.py dumpclasses --class2d J###`).

Usage (run with the crYOLO env's python):
  python make_montage.py verify  --work-dir /path/to/work_dir
  python make_montage.py class2d --work-dir /path/to/work_dir [--label J###]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _need(path):
    if not os.path.isfile(path):
        raise SystemExit(f"error: {path} not found (run the cryosparc-tools dump step first)")
    return path


def render_verify(work_dir, label):
    imgs = np.load(_need(os.path.join(work_dir, "verif_imgs.npy")))
    avg = np.load(_need(os.path.join(work_dir, "verif_avg.npy")))
    std = np.load(_need(os.path.join(work_dir, "verif_std.npy")))

    M = min(imgs.shape[0], 100)
    ncol = 10
    nrow = int(np.ceil(M / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(ncol, nrow))
    for k, ax in enumerate(np.atleast_1d(axes).ravel()):
        ax.axis("off")
        if k < M:
            im = imgs[k]
            lo, hi = np.percentile(im, [2, 98])
            ax.imshow(im, cmap="gray", vmin=lo, vmax=hi)
    fig.suptitle(f"{label} extracted crYOLO particles (random {M})", y=1.0)
    plt.tight_layout()
    out1 = os.path.join(work_dir, "verif_montage.png")
    plt.savefig(out1, dpi=80, bbox_inches="tight")
    plt.close()

    fig2, (a1, a2) = plt.subplots(1, 2, figsize=(6, 3.2))
    a1.imshow(avg, cmap="gray")
    a1.set_title("average (centred blob = OK)")
    a1.axis("off")
    a2.imshow(std, cmap="viridis")
    a2.set_title("per-pixel std")
    a2.axis("off")
    plt.tight_layout()
    out2 = os.path.join(work_dir, "verif_avgstd.png")
    plt.savefig(out2, dpi=80, bbox_inches="tight")
    plt.close()
    print("wrote", out1, "and", out2)


def render_class2d(work_dir, label):
    imgs = np.load(_need(os.path.join(work_dir, "cls_imgs.npy")))
    counts = np.load(_need(os.path.join(work_dir, "cls_counts.npy")))
    K = imgs.shape[0]
    order = np.argsort(-counts) if (counts >= 0).any() else np.arange(K)

    ncol = 10
    nrow = int(np.ceil(K / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 1.25, nrow * 1.3))
    for k, ax in enumerate(np.atleast_1d(axes).ravel()):
        ax.axis("off")
        if k < K:
            idx = order[k]
            im = imgs[idx]
            lo, hi = np.percentile(im, [1, 99])
            ax.imshow(im, cmap="gray", vmin=lo, vmax=hi)
            if counts[idx] >= 0:
                ax.set_title(str(int(counts[idx])), fontsize=6, pad=1)
    tot = int(counts[counts >= 0].sum()) if (counts >= 0).any() else -1
    fig.suptitle(f"{label} 2D class averages (K={K}, sorted by #particles; total={tot})", y=1.0)
    plt.tight_layout()
    out = os.path.join(work_dir, f"cls_{label}.png")
    plt.savefig(out, dpi=95, bbox_inches="tight")
    plt.close()
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    pv = sub.add_parser("verify", help="render extracted-particle avg/std/montage")
    pc = sub.add_parser("class2d", help="render 2D class-average montage")
    for p in (pv, pc):
        p.add_argument("--work-dir", required=True, help="dir holding the .npy dumps")
        p.add_argument("--label", default=None, help="title label (e.g. the job uid)")
    args = ap.parse_args()
    label = args.label or ("extract" if args.mode == "verify" else "2D")
    if args.mode == "verify":
        render_verify(args.work_dir, label)
    else:
        render_class2d(args.work_dir, label)


if __name__ == "__main__":
    main()
