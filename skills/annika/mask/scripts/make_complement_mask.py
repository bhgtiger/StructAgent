"""
make_complement_mask.py — produce a particle-subtraction mask = full - region.

  ChimeraX --nogui --exit --script make_complement_mask.py -- \
    --full mask_full.mrc --region mask_R.mrc --target-map ref.mrc --out mask_sub.mrc

Logic:
  close all
  open target -> #1
  open full   -> #2
  open region -> #3
  volume subtract #2 #3 minRMS false  -> #4
  volume threshold #4 minimum 0 setMinimum 0     # clamp negatives
  (optional) volume gaussian sDev <soft>         # soft edge
  volume resample onGrid #1
  save out
"""
import argparse, json, os, sys, traceback
from chimerax.core.commands import run


def parse_args(a):
    p = argparse.ArgumentParser()
    p.add_argument("--full", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--target-map", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--soft", type=float, default=None, help="Soft edge sDev (Å). Default 5*apix.")
    return p.parse_args(a)


def latest_id(session):
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
        run(session, f"open {args.target_map}")
        from chimerax.map.volume import Volume
        target = [m for m in session.models if isinstance(m, Volume)][0]
        apix = float(target.data.step[0])
        stats["apix"] = apix
        run(session, f"open {args.full}")
        run(session, f"open {args.region}")
        run(session, "volume subtract #2 #3 minRMS false")
        cur = latest_id(session)
        # clamp negatives to 0 (values < 0 -> 0)
        run(session, f"volume threshold #{cur} minimum 0 set 0")
        cur = latest_id(session)
        soft = args.soft if args.soft is not None else 5.0 * apix
        if soft > 0:
            run(session, f"volume gaussian #{cur} sDev {soft}")
            cur = latest_id(session)
        run(session, f"volume resample #{cur} onGrid #1")
        cur = latest_id(session)
        out_abs = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        run(session, f"save {out_abs} #{cur}")
        json.dump({"ok": True, "params": params, "stats": stats},
                  open(out_abs + ".json", "w"), indent=2)
        print("@@MASK_DONE@@ ok")
    except Exception as e:
        out_abs = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        json.dump({"ok": False, "params": params, "stats": stats,
                   "error": str(e), "traceback": traceback.format_exc()},
                  open(out_abs + ".json", "w"), indent=2)
        print("@@MASK_DONE@@ error: " + str(e), file=sys.stderr)
        raise


argv = sys.argv[1:]
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
main(argv)
