"""
make_mask_from_map.py — map-only mask base (no model, no GUI).

  ChimeraX --nogui --exit --script make_mask_from_map.py -- \
    --map ref_map.mrc --out mask.mrc \
    [--sdev 2.0] [--threshold 0.05] [--dilation 0] [--soft 8.0]

Pipeline:
  close all; open map -> #1
  volume gaussian #1 sDev <sdev>             -> #2  (blur)
  volume threshold #2 minimum <t> set 0 …    -> #3  (binarize)
  [volume morphology dilation iters n]       -> #4
  [volume gaussian sDev <soft>]              -> #5
  volume resample #5 onGrid #1               -> #6
  save out #6

Note: this cannot replicate Segger or volume-eraser results — it just
gives a soft, thresholded blob. Use only when you don't have a model.
"""
import argparse
import json
import os
import sys
import traceback
from chimerax.core.commands import run


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--map", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--sdev", type=float, default=2.0, help="Gaussian sdev for initial blur (voxels).")
    p.add_argument("--threshold", type=float, required=False,
                   help="Map value to binarize at. If omitted, no binarize (soft mask of blur output).")
    p.add_argument("--dilation", type=float, default=0.0, help="Dilation in Å.")
    p.add_argument("--soft", type=float, default=None, help="Soft padding sDev (Å). Default 5*apix.")
    return p.parse_args(argv)


def write_sidecar(out_path, payload):
    with open(out_path + ".json", "w") as f:
        json.dump(payload, f, indent=2)


def latest_top_volume_id(session):
    from chimerax.map.volume import Volume
    vols = [m for m in session.models if isinstance(m, Volume) and "." not in m.id_string]
    return sorted(vols, key=lambda v: int(v.id_string))[-1].id_string


def main(argv):
    args = parse_args(argv)
    session = globals().get("session")
    params = vars(args).copy()
    stats = {}
    try:
        run(session, "close all")
        run(session, f"open {args.map}")
        from chimerax.map.volume import Volume
        target = [m for m in session.models if isinstance(m, Volume)][0]
        apix = float(target.data.step[0])
        stats["apix"] = apix

        # 1. Gaussian blur
        run(session, f"volume gaussian #1 sDev {args.sdev}")
        cur_id = latest_top_volume_id(session)

        # 2. Optional binarize
        if args.threshold is not None:
            t = args.threshold
            stats["threshold"] = t
            run(session, f"volume threshold #{cur_id} minimum {t} set 0")
            cur_id = latest_top_volume_id(session)
            run(session, f"volume threshold #{cur_id} maximum 0 setMaximum 1")
            cur_id = latest_top_volume_id(session)

        # 3. Dilation via blur + re-threshold trick (no native morphology in ChimeraX)
        if args.dilation and args.dilation > 0:
            stats["dilation_A"] = args.dilation
            run(session, f"volume gaussian #{cur_id} sDev {args.dilation}")
            cur_id = latest_top_volume_id(session)
            run(session, f"volume threshold #{cur_id} minimum 0.25 set 0")
            cur_id = latest_top_volume_id(session)
            run(session, f"volume threshold #{cur_id} maximum 0 setMaximum 1")
            cur_id = latest_top_volume_id(session)

        # 4. Soft edge
        soft = args.soft if args.soft is not None else 5.0 * apix
        stats["soft_A"] = soft
        if soft and soft > 0:
            run(session, f"volume gaussian #{cur_id} sDev {soft}")
            cur_id = latest_top_volume_id(session)

        # 5. Resample
        run(session, f"volume resample #{cur_id} onGrid #1")
        cur_id = latest_top_volume_id(session)

        out_abs = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        run(session, f"save {out_abs} #{cur_id}")
        write_sidecar(out_abs, {"ok": True, "params": params, "stats": stats})
        print("@@MASK_DONE@@ ok")
    except Exception as e:
        out_abs = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        write_sidecar(out_abs, {"ok": False, "params": params, "stats": stats,
                                "error": str(e), "traceback": traceback.format_exc()})
        print("@@MASK_DONE@@ error: " + str(e), file=sys.stderr)
        raise


argv = sys.argv[1:]
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
main(argv)
