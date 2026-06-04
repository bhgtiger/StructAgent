"""
make_mask_from_model.py — model-reference mask base generator.

Run inside ChimeraX (≥1.8):
  ChimeraX --nogui --exit --script make_mask_from_model.py -- \
    --model model.cif --target-map ref_map.mrc --out mask.mrc \
    [--selection "/A:120-340"] [--resolution 16] \
    [--binarize/--no-binarize] [--threshold 0.5] \
    [--dilation 0] [--soft 8.0] \
    [--gsfsc-resolution 3.5]

Writes:
  <out>             the .mrc mask base, resampled onto the target map's grid
  <out>.json        sidecar: {"ok": bool, "params": {...}, "stats": {...}, "error"?}

Pipeline:
  close all
  open <target_map>                       -> #1
  open <model>                            -> #2
  molmap <selection> <resolution> grid p  -> #3
  [volume threshold #3 ...]               -> #4
  [volume morphology #4 dilation n]       -> #5
  [volume gaussian #X sDev s]             -> #6
  volume resample #LAST onGrid #1         -> #7
  save <out> #7
"""
import argparse
import json
import os
import sys
import traceback

from chimerax.core.commands import run


SENTINEL = "@@MASK_DONE@@"


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="PDB/CIF atomic model")
    p.add_argument("--target-map", required=True, help="Reference map (.mrc) for box/apix/origin")
    p.add_argument("--out", required=True, help="Output .mrc path")
    p.add_argument("--selection", default="", help="ChimeraX atomspec, e.g. '/A:120-340'. Default: whole model.")
    p.add_argument("--resolution", type=float, default=16.0, help="molmap resolution (Å). Default 16.")
    p.add_argument("--binarize", dest="binarize", action="store_true", default=True)
    p.add_argument("--no-binarize", dest="binarize", action="store_false")
    p.add_argument("--threshold", type=float, default=None,
                   help="Binarization threshold in molmap value units. Default: 0.5 * max(molmap).")
    p.add_argument("--dilation", type=float, default=0.0, help="Dilation in Å (0 disables).")
    p.add_argument("--soft", type=float, default=None,
                   help="Soft padding width in Å (Gaussian sDev). Default: 5*apix or 5*gsfsc-resolution if provided.")
    p.add_argument("--gsfsc-resolution", type=float, default=None,
                   help="GSFSC resolution (Å) of the target map; if set and --soft not given, soft = 5 * gsfsc.")
    return p.parse_args(argv)


def get_volume_by_id(session, mid):
    """Find a Volume model whose id_string starts with mid (e.g. '1' or '1.2')."""
    from chimerax.map.volume import Volume
    for m in session.models:
        if isinstance(m, Volume) and m.id_string == mid:
            return m
    return None


def get_target_grid(volume):
    """Return (apix_x, box_size, origin) from a Volume's grid."""
    data = volume.data
    step = data.step  # (sx, sy, sz) Å
    size = data.size  # (nx, ny, nz)
    origin = data.origin
    return step, size, origin


def write_sidecar(out_path, payload):
    side = out_path + ".json"
    with open(side, "w") as f:
        json.dump(payload, f, indent=2)


def main(argv):
    args = parse_args(argv)
    session = globals().get("session")
    if session is None:
        from chimerax.core import session as _s  # pragma: no cover
        raise RuntimeError("ChimeraX session not found — run via --script")

    params = vars(args).copy()
    stats = {}

    try:
        run(session, "close all")

        # 1. Open target map -> #1
        run(session, f"open {args.target_map}")
        target = get_volume_by_id(session, "1")
        if target is None:
            raise RuntimeError(f"Could not open target map: {args.target_map}")
        step, size, origin = get_target_grid(target)
        apix = float(step[0])
        stats["apix"] = apix
        stats["box"] = list(size)
        stats["origin"] = list(origin)

        # 2. Open model -> #2
        run(session, f"open {args.model}")

        # 3. Sanity-check selection (non-empty)
        sel_spec = args.selection.strip() or "#2"
        run(session, f"select {sel_spec}")
        from chimerax.atomic import selected_atoms
        n_atoms = len(selected_atoms(session))
        stats["selected_atoms"] = n_atoms
        if n_atoms == 0:
            raise RuntimeError(f"Selection '{sel_spec}' matched 0 atoms.")
        run(session, "~select")

        # 4. molmap -> next available id (typically #3)
        molmap_cmd = (
            f"molmap {sel_spec} {args.resolution} gridSpacing {apix:.6f}"
        )
        run(session, molmap_cmd)

        # Find the freshly-made volume: the highest-numbered top-level Volume
        from chimerax.map.volume import Volume
        vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
        vols_sorted = sorted(vols, key=lambda v: int(v.id_string))
        molmap_vol = vols_sorted[-1]
        cur_id = molmap_vol.id_string
        stats["molmap_id"] = cur_id
        stats["molmap_max"] = float(molmap_vol.matrix().max())

        # 5. Optional binarize via two-step volume threshold:
        #    (a) values < t  -> 0
        #    (b) values > 0  -> 1   (so surviving >=t values become 1)
        if args.binarize:
            t = args.threshold if args.threshold is not None else 0.5 * stats["molmap_max"]
            stats["threshold_used"] = t
            run(session, f"volume threshold #{cur_id} minimum {t} set 0")
            vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
            cur_id = sorted(vols, key=lambda v: int(v.id_string))[-1].id_string
            run(session, f"volume threshold #{cur_id} maximum 0 setMaximum 1")
            vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
            cur_id = sorted(vols, key=lambda v: int(v.id_string))[-1].id_string

        # 6. Optional dilation: ChimeraX has no native morphology op, so use the
        #    blur + re-threshold trick. sDev = dilation_A, re-threshold at 0.25
        #    expands the 1-region by ~dilation_A and re-binarizes.
        if args.dilation and args.dilation > 0:
            stats["dilation_A"] = args.dilation
            run(session, f"volume gaussian #{cur_id} sDev {args.dilation:.4f}")
            vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
            cur_id = sorted(vols, key=lambda v: int(v.id_string))[-1].id_string
            run(session, f"volume threshold #{cur_id} minimum 0.25 set 0")
            vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
            cur_id = sorted(vols, key=lambda v: int(v.id_string))[-1].id_string
            run(session, f"volume threshold #{cur_id} maximum 0 setMaximum 1")
            vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
            cur_id = sorted(vols, key=lambda v: int(v.id_string))[-1].id_string

        # 7. Soft edge
        soft = args.soft
        if soft is None and args.gsfsc_resolution is not None:
            soft = 5.0 * args.gsfsc_resolution
        elif soft is None:
            soft = 5.0 * apix
        stats["soft_A"] = soft
        if soft and soft > 0:
            run(session, f"volume gaussian #{cur_id} sDev {soft:.4f}")
            vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
            cur_id = sorted(vols, key=lambda v: int(v.id_string))[-1].id_string

        # 8. Resample onto target grid
        run(session, f"volume resample #{cur_id} onGrid #1")
        vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
        final = sorted(vols, key=lambda v: int(v.id_string))[-1]
        cur_id = final.id_string
        stats["final_id"] = cur_id
        stats["final_box"] = list(final.data.size)

        # 9. Save
        out_abs = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        run(session, f"save {out_abs} #{cur_id}")

        write_sidecar(out_abs, {"ok": True, "params": params, "stats": stats})
        print(SENTINEL + " ok")

    except Exception as e:
        tb = traceback.format_exc()
        out_abs = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        write_sidecar(out_abs, {
            "ok": False,
            "params": params,
            "stats": stats,
            "error": str(e),
            "traceback": tb,
        })
        print(SENTINEL + " error: " + str(e), file=sys.stderr)
        raise


# ChimeraX --script passes everything after `--` in sys.argv
argv = sys.argv[1:]
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
main(argv)
