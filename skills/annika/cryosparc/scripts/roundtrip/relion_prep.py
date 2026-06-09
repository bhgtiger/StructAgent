#!/usr/bin/env python3
"""relion_prep.py — make cryoSPARC particle stacks loadable by RELION (.mrcs farm).

RELION-side glue for the OUTBOUND leg of the round-trip (cryoSPARC -> RELION). It is
pure file/STAR manipulation: no RELION binary, no cryosparc-tools, no numpy.

cryoSPARC writes particle stacks as `.mrc`; RELION rejects `.mrc` for multi-particle
stacks and wants `.mrcs`. After you convert a cryoSPARC job to a STAR with
`csparc2star.py` (its rlnImageName points at `idx@<stack>.mrc`, typically relative to
the cryoSPARC project root), this builds a `.mrcs` symlink farm and rewrites every
rlnImageName to an ABSOLUTE `.mrcs` path, so the RELION project is location-independent.

What it does NOT do (those use RELION/pyem binaries — see the relion skill):
  * run csparc2star.py            (cryoSPARC .cs -> STAR)
  * downsample particles          (relion_image_handler --new_box / --rescale_angpix)
  * re-soften the focus mask       (relion_mask_create --width_soft_edge ...)

Usage:
  relion_prep.py \
    --in  particles_400px.star \
    --cs-project-root /path/CS-project/ \
    --symlink-dir /path/relion_proj/JXXX_class3d/Particles \
    --out particles_400px_abs.star

Then point your RELION Class3D `--i` at the rewritten STAR (or its downsampled child).
"""
from __future__ import annotations

import argparse
import os
import sys


def die(msg: str):
    raise SystemExit(f"error: {msg}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True, help="csparc2star output STAR")
    ap.add_argument("--out", required=True, help="rewritten STAR (absolute .mrcs paths)")
    ap.add_argument("--symlink-dir", required=True,
                    help="directory to hold the <stem>.mrcs symlinks (created if absent)")
    ap.add_argument("--cs-project-root", default="",
                    help="prefix for resolving RELATIVE stack paths in the input STAR "
                         "(the cryoSPARC project root). Ignored for absolute paths.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be linked/rewritten; create/write nothing")
    args = ap.parse_args()

    if not os.path.isfile(args.inp):
        die(f"input STAR not found: {args.inp}")
    symdir = os.path.abspath(args.symlink_dir)
    root = os.path.abspath(args.cs_project_root) if args.cs_project_root else ""

    if not args.dry_run:
        os.makedirs(symdir, exist_ok=True)

    in_particles = in_loop = False
    img_col = None
    labels = []
    linked, missing, collisions = {}, 0, 0
    rows = 0
    out_lines = []

    def resolve_and_link(img_token: str) -> str:
        nonlocal missing, collisions
        if "@" not in img_token:
            die(f"rlnImageName has no '@': {img_token!r}")
        idx, path = img_token.split("@", 1)
        phys = path if os.path.isabs(path) else os.path.join(root, path)
        phys = os.path.abspath(phys)
        stem = os.path.basename(path)
        for ext in (".mrcs", ".mrc"):
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break
        link = os.path.join(symdir, stem + ".mrcs")
        if link not in linked:  # first time we see this stack
            linked[link] = phys
            if not os.path.exists(phys):
                missing += 1
            if not args.dry_run:
                if os.path.islink(link) or os.path.exists(link):
                    if os.path.realpath(link) != phys:
                        collisions += 1  # existing link points elsewhere; leave it
                else:
                    os.symlink(phys, link)
        return f"{idx}@{link}"

    with open(args.inp) as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            s = line.strip()
            if s.startswith("data_"):
                in_particles = (s == "data_particles")
                in_loop = False
                labels = []
                img_col = None
                out_lines.append(line)
                continue
            if in_particles and s == "loop_":
                in_loop = True
                labels = []
                out_lines.append(line)
                continue
            if in_particles and in_loop and s.startswith("_"):
                labels.append(s.split()[0])
                if s.split()[0] == "_rlnImageName":
                    img_col = len(labels) - 1
                out_lines.append(line)
                continue
            if in_particles and in_loop and s and not s.startswith("#"):
                if img_col is None:
                    die("data_particles loop has no _rlnImageName column")
                parts = s.split()
                parts[img_col] = resolve_and_link(parts[img_col])
                out_lines.append(" ".join(parts))
                rows += 1
                continue
            out_lines.append(line)

    print(f"data_particles rows: {rows}")
    print(f"unique stacks symlinked: {len(linked)}")
    if missing:
        print(f"  WARNING: {missing} stack target(s) do not exist on disk "
              "(check --cs-project-root)")
    if collisions:
        print(f"  WARNING: {collisions} existing link(s) pointed elsewhere — left as-is, "
              "NOT overwritten (basename collision?)")
    if args.dry_run:
        print("dry-run: no symlinks created, no STAR written")
        return
    with open(args.out, "w") as fh:
        fh.write("\n".join(out_lines) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
