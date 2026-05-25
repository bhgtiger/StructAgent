"""
make_mask_from_map.py — map-only mask base (no model, no GUI).

  ChimeraX --nogui --exit --script make_mask_from_map.py -- \
    --map ref_map.mrc --out mask.mrc \
    [--sdev 2.0] [--threshold 0.05] [--dilation 0] [--soft 8.0]

Writes:
  <out>             the .mrc mask base, resampled onto the map's grid
  <out>.json        sidecar: {"ok": bool, "params": ..., "stats": ..., "error"?}
                    For --out mask.mrc the sidecar is mask.mrc.json.

Pipeline (ChimeraX has no native morphology op; dilation is a Gaussian
blur + re-threshold trick, not `volume morphology`):
  close all; open map                              -> #1
  volume gaussian #1 sDev <sdev>                   -> blur
  [volume threshold ... minimum t set 0;
   volume threshold ... maximum 0 setMaximum 1]    -> binarize
  [volume gaussian ... sDev <dilation_A>;
   volume threshold ... minimum 0.25 set 0;
   volume threshold ... maximum 0 setMaximum 1]    -> dilate-via-blur
  [volume gaussian ... sDev <soft_A>]              -> soft edge
  volume resample #LAST onGrid #1                  -> final
  save <out> #LAST

Note: this cannot replicate Segger or volume-eraser results — it just
gives a soft, thresholded blob. Use only when you don't have a model.
"""
import argparse
import json
import os
import sys
import traceback
from chimerax.core.commands import run


def _q(p):
    return '"' + str(p).replace('"', r'\"') + '"'


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--map", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--sdev", type=float, default=2.0,
                   help="Gaussian sDev for initial blur in Å (ChimeraX volume-gaussian data-step units).")
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
    if session is None:
        raise RuntimeError("ChimeraX session not found — run via --script inside ChimeraX")
    params = vars(args).copy()
    stats = {}
    try:
        run(session, "close all")
        run(session, f"open {_q(args.map)}")
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
        run(session, f"save {_q(out_abs)} #{cur_id}")
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
