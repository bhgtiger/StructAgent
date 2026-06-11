#!/usr/bin/env python3
"""cryolo_pick.py — crYOLO general-model picking -> cryoSPARC extract / 2D.

Generalized, config-driven version of the verified split-output picking session (see
the cryoSPARC skill reference references/29_cryolo_picking_to_2d.md). It picks particles
with SPHIRE-crYOLO's general model on motion-corrected micrographs that already live
in a cryoSPARC project, injects the picks back via a cryosparc-tools external job,
Extracts, runs 2D Classification, and can optimize the 2D — all without leaving the
cryoSPARC project's metadata model (native micrograph<->particle linkage, per-particle
CTF).

TWO environments are involved (see README.md):
  * cryosparc-tools interpreter — inspect / threshold / inject / extract / verify /
    class2d (talk to the master);
  * crYOLO conda env — config / predict (CUDA/TF picking) and make_montage.py
    (matplotlib rendering). This script shells out to the crYOLO env for those.

SAFETY CONTRACT (mirrors the cryoSPARC skill SKILL.md):
  * inspect / threshold / verify / dumpclasses are read-only (no jobs queued).
  * inject creates an external picks job (cheap, no GPU compute).
  * predict / extract / class2d only QUEUE GPU compute when you pass --confirm
    AND a lane is resolvable; otherwise they print what they WOULD do (dry-run).
  * Credentials come ONLY from env vars CRYOSPARC_EMAIL / CRYOSPARC_PASSWORD.

Subcommands:
  inspect      read-only: report source exposures (n / pixel / shape), suggest box sizes
  config       write a crYOLO config JSON (shells out to the crYOLO env cryolo_gui.py)
  predict      symlink mics + run cryolo_predict.py in the crYOLO env (GPU; --confirm)
  threshold    CBOX per-image distribution -> recommend a confidence for target_per_image
  inject       CBOX -> external picks job at a confidence (--flip-y to mirror Y)
  extract      Extract From Micrographs (GPU; --confirm + lane)
  verify       dump a particle sample + centre/edge std (Y-flip check), print next step
  class2d      2D Classification, with optional optimization knobs (GPU; --confirm + lane)
  dumpclasses  read-only: dump a finished 2D job's class averages + counts -> cls_*.npy

Usage:
  cryolo_pick.py inspect     --config cryolo_pick.json
  cryolo_pick.py config      --config cryolo_pick.json [--box <PIX>]
  cryolo_pick.py predict     --config cryolo_pick.json [--confirm]
  cryolo_pick.py threshold   --config cryolo_pick.json
  cryolo_pick.py inject      --config cryolo_pick.json [--conf 0.3] [--flip-y]
  cryolo_pick.py extract     --config cryolo_pick.json --picks J### [--confirm]
  cryolo_pick.py verify      --config cryolo_pick.json --extract J###
  cryolo_pick.py class2d     --config cryolo_pick.json --extract J### [--optimize] [--confirm]
  cryolo_pick.py dumpclasses --config cryolo_pick.json --class2d J###
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

from cp_common import (  # noqa: E402
    load_config, connect, load_exposures, read_cbox, cbox_files_by_stem,
    per_image_distribution, inject_picks, resolve_lane, suggest_box_sizes, die,
)


# --------------------------------------------------------------------------- #
# crYOLO-env shell-out helpers
# --------------------------------------------------------------------------- #
def _cryolo_prefix(cfg):
    """Bash prefix that activates the crYOLO conda env, or die with guidance."""
    cr = cfg["cryolo"]
    sh = cr.get("conda_sh")
    env = cr.get("env")
    if not sh:
        die("config cryolo.conda_sh is not set (path to <conda>/etc/profile.d/conda.sh)")
    return f"source {sh} && conda activate {env} && "


def _run_bash(cmd, confirm, what):
    """Print the command; run it only when confirm is True."""
    print(f"\n{what}:")
    print("  " + cmd)
    if not confirm:
        print("DRY RUN (no --confirm) — not executed. Re-run with --confirm to run it.")
        return False
    subprocess.run(["bash", "-lc", cmd], check=True)
    return True


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #
def cmd_inspect(cfg, args):
    cs = connect(cfg)
    # Do not enumerate cs.find_projects() — on a shared multi-user instance that echoes
    # other users' project UIDs. Just confirm the configured project is reachable.
    print(f"connected. using project {cfg['project']} / workspace {cfg['workspace']}")
    job, ds = load_exposures(cs, cfg)
    n = len(ds)
    print(f"\nsource {cfg['source_job']} type: {job.type}")
    print(f"source output {cfg['source_output']!r}: {n} exposures")
    fl = list(ds.fields())
    psize = None
    if "micrograph_blob/psize_A" in fl:
        ps = sorted(set(np.round(ds["micrograph_blob/psize_A"].astype(float), 4)))
        psize = float(ps[0])
        print("  pixel size (A/px):", ps[:5])
    if "micrograph_blob/shape" in fl:
        print("  micrograph shape [NY, NX]:", list(map(int, ds["micrograph_blob/shape"][0])))
    p0 = ds["micrograph_blob/path"][0]
    print("  example path:", p0.decode() if isinstance(p0, bytes) else p0)

    pd = cfg.get("particle_diameter_A")
    sug = suggest_box_sizes(pd, psize)
    print(f"\nbox-size suggestions (particle_diameter_A={pd}, psize_A={psize}):")
    if sug["cryolo_box_pix"]:
        print(f"  crYOLO config box  ~ {sug['cryolo_box_pix']} px  (particle / psize)")
        print(f"  Extract box        ~ {sug['extract_box_pix']} px  (~1.8x particle, FFT-friendly)")
        print(f"  Fourier-crop box   ~ {sug['crop_box_pix']} px  (-> ~1.7 A/px output)")
        print("  (set box_extract_pix / box_crop_pix in the config; these are starting points)")
    else:
        print("  set particle_diameter_A in the config to get suggestions")
    print("\ninspect OK. Next: config (crYOLO), then predict.")


def cmd_config(cfg, args):
    cr = cfg["cryolo"]
    # The crYOLO detection/anchor box is NOT the cryoSPARC extraction box — it is
    # ~particle_longest / psize (box_extract_pix is ~1.8x larger). Default to the
    # explicit cryolo_box_pix; otherwise derive it from particle geometry + the source
    # pixel size; never reuse box_extract_pix here.
    box = args.box if args.box is not None else cfg.get("cryolo_box_pix")
    if not box:
        pd = cfg.get("particle_diameter_A")
        psize = None
        if pd:
            try:
                cs = connect(cfg)
                _job, _ds = load_exposures(cs, cfg)
                if "micrograph_blob/psize_A" in _ds.fields():
                    psize = float(np.round(float(_ds["micrograph_blob/psize_A"][0]), 4))
            except SystemExit:
                raise
            except Exception:
                psize = None
        sug = suggest_box_sizes(pd, psize)
        box = sug["cryolo_box_pix"]
    if not box:
        pd = cfg.get("particle_diameter_A")
        die("no crYOLO box size: pass --box <PIX>, or set cryolo_box_pix, or set "
            f"particle_diameter_A (={pd}) so it can be derived as particle_longest / psize. "
            "Do NOT reuse box_extract_pix here — the crYOLO anchor box is the smaller "
            "~particle/psize box, not the cryoSPARC extraction box.")
    out_json = os.path.join(cfg["work_dir"], "config_cryolo.json")
    flt = cr.get("filter", "LOWPASS")
    cmd = _cryolo_prefix(cfg) + f"cryolo_gui.py config {out_json} {int(box)} --filter {flt}"
    if flt == "LOWPASS":
        cmd += f" --low_pass_cutoff {cr.get('low_pass_cutoff', 0.1)}"
    print(f"crYOLO config -> {out_json}")
    # building a config is cheap and not GPU; run it directly (still prints the command)
    _run_bash(cmd, confirm=True, what="cryolo_gui.py config")
    print(f"\nwrote {out_json}. Next: predict.")


def cmd_predict(cfg, args):
    cr = cfg["cryolo"]
    model = cr.get("general_model")
    if not model:
        die("config cryolo.general_model is not set (path to the filter-matched *.h5). "
            "The user supplies the model; never download weights (licensing).")
    cfgjson = os.path.join(cfg["work_dir"], "config_cryolo.json")
    if not os.path.isfile(cfgjson):
        print(f"note: {cfgjson} not found yet — run 'config' first (or it will fail).")

    # build the symlink farm of chosen micrographs from the cryoSPARC source
    cs = connect(cfg)
    job, ds = load_exposures(cs, cfg)
    proj = cs.find_project(cfg["project"])
    proj_dir = proj.dir()
    mics_dir = os.path.join(cfg["work_dir"], "input_mics")
    os.makedirs(mics_dir, exist_ok=True)
    paths = ds["micrograph_blob/path"]
    linked = 0
    for i in range(len(ds)):
        p = paths[i].decode() if isinstance(paths[i], bytes) else paths[i]
        src = os.path.join(str(proj_dir), p)
        dst = os.path.join(mics_dir, os.path.basename(p))
        if not os.path.lexists(dst):
            os.symlink(src, dst)
        linked += 1
    print(f"symlinked {linked} micrographs into {mics_dir}")

    out_dir = os.path.join(cfg["work_dir"], "out")
    thr = cfg.get("threshold", 0.3)
    flt = cr.get("filter", "LOWPASS")
    otf = " --otf" if flt != "NONE" else ""   # --otf is silently ignored with --filter NONE
    cmd = (_cryolo_prefix(cfg) +
           f"cd {cfg['work_dir']} && cryolo_predict.py -c {cfgjson} -w {model} "
           f"-i {mics_dir}/ -o {out_dir}/ -g 0 -t {thr}{otf}")
    ran = _run_bash(cmd, confirm=args.confirm,
                    what="cryolo_predict.py (GPU picking in the crYOLO env)")
    if ran:
        print(f"\npicking done. CBOX (all detections) under {out_dir}/CBOX/.")
        print("Next: threshold (recommend a confidence), then inject.")


def cmd_threshold(cfg, args):
    cbox_dir = os.path.join(cfg["work_dir"], "out", "CBOX")
    if not os.path.isdir(cbox_dir):
        die(f"{cbox_dir} not found — run 'predict' first")
    cands = [0.10, 0.15, 0.18, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
    dist = per_image_distribution(cbox_dir, cands)
    target = cfg.get("target_per_image")
    print(f"CBOX re-threshold distribution (no GPU re-run; dir={cbox_dir}):")
    print("  conf   total    median/img   mean/img")
    best, best_gap = None, None
    for c in cands:
        d = dist[c]
        print(f"  {c:>4.2f}  {d['total']:>7d}   {d['median']:>9.1f}   {d['mean']:>8.1f}")
        if target is not None:
            gap = abs(d["median"] - target)
            if best_gap is None or gap < best_gap:
                best, best_gap = c, gap
    if target is not None and best is not None:
        print(f"\ntarget_per_image={target} -> recommended confidence ~ {best:.2f} "
              f"(median {dist[best]['median']:.1f}/img, {dist[best]['total']} total).")
        print(f"Next: inject --conf {best:.2f}")
    else:
        print("\nset target_per_image in the config to get a recommended confidence.")
        print("Next: inject --conf <value>")


def cmd_inject(cfg, args):
    cbox_dir = os.path.join(cfg["work_dir"], "out", "CBOX")
    if not os.path.isdir(cbox_dir):
        die(f"{cbox_dir} not found — run 'predict' first")
    conf = args.conf if args.conf is not None else cfg.get("threshold", 0.3)

    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    job, ds = load_exposures(cs, cfg)
    files = cbox_files_by_stem(cbox_dir)

    paths = ds["micrograph_blob/path"]
    picks_by_index = {}
    matched, missing = 0, []
    total = 0
    for i in range(len(ds)):
        p = paths[i].decode() if isinstance(paths[i], bytes) else paths[i]
        stem = os.path.basename(p)[:-4]   # strip .mrc
        f = files.get(stem)
        if f is None:
            missing.append(stem)
            continue
        matched += 1
        picks = [(cx, cy) for (cx, cy, _c) in read_cbox(f, conf)]
        if picks:
            picks_by_index[i] = picks
            total += len(picks)
    print(f"exposures={len(ds)}  CBOX matched={matched}  missing={len(missing)}  "
          f"picks(conf>={conf})={total}  flip_y={args.flip_y}")
    if missing:
        print("  example missing:", missing[:3])

    cfg["_inject_title"] = f"crYOLO picks {cfg['source_job']}/{cfg['source_output']} (conf>={conf})"
    ext, n = inject_picks(proj, cfg, ds, picks_by_index, flip_y=args.flip_y)
    print(f"\nSAVED {n} picks to {ext.uid}.picked_particles (workspace {cfg['workspace']})")
    print(f"PICKS_JOB_UID={ext.uid}")
    print(f"Next: extract --picks {ext.uid}")


def cmd_extract(cfg, args):
    box = cfg.get("box_extract_pix")
    crop = cfg.get("box_crop_pix")
    if not box or not crop:
        die("set box_extract_pix and box_crop_pix in the config (see inspect for suggestions)")
    lane = resolve_lane(cfg)

    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    ex = proj.create_job(
        cfg["workspace"], "extract_micrographs_multi",
        connections={"micrographs": (cfg["source_job"], cfg["source_output"]),
                     "particles": (args.picks, "picked_particles")},
        title=f"Extract crYOLO picks {args.picks} (box{box} crop{crop})",
    )
    ex.set_param("box_size_pix", int(box))
    ex.set_param("bin_size_pix", int(crop))
    if cfg.get("output_f16", True):
        ex.set_param("output_f16", True)
    ex.refresh()
    p2 = ex.params.model_dump()
    print(f"built extract job {ex.uid}: box_size_pix={p2.get('box_size_pix')} "
          f"bin_size_pix={p2.get('bin_size_pix')} output_f16={p2.get('output_f16')}")
    print(f"  micrographs <- {cfg['source_job']}/{cfg['source_output']}, "
          f"particles <- {args.picks}/picked_particles")

    if not args.confirm:
        print(f"\nDRY RUN (no --confirm). Would queue {ex.uid} to lane {lane!r}.")
        print("Re-run with --confirm to queue.")
        return
    if not lane:
        die("no lane resolvable: set 'lane' in the config or export CS_LANE")
    ex.queue(lane=lane)
    print(f"\nQUEUED {ex.uid} to lane {lane!r}.")
    print(f"EXTRACT_JOB_UID={ex.uid}")
    print(f"Next (after it finishes): verify --extract {ex.uid}")


def cmd_verify(cfg, args):
    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    proj_dir = str(proj.dir())
    job = cs.find_job(cfg["project"], args.extract)

    # find the particle output group
    parts = grp = None
    for g in ("particles", "particles_all", "particles_selected"):
        try:
            parts = job.load_output(g)
            grp = g
            break
        except Exception:
            pass
    if parts is None:
        die(f"could not load a particle output from {args.extract}")
    n = len(parts)
    print(f"particle group: {grp} | n: {n}")

    nsample = min(args.nsample, n)
    paths, idxs = parts["blob/path"], parts["blob/idx"]
    rng = np.random.default_rng(0)
    sel = rng.choice(n, size=nsample, replace=False)
    from collections import defaultdict
    from cryosparc import mrc
    bypath = defaultdict(list)
    for i in sel:
        p = paths[i].decode() if isinstance(paths[i], bytes) else paths[i]
        bypath[p].append(int(idxs[i]))

    imgs = []
    for p, fidxs in bypath.items():
        res = mrc.read(os.path.join(proj_dir, p))
        data = res[1] if isinstance(res, tuple) else res
        arr = np.asarray(data)
        if arr.ndim == 2:
            arr = arr[None]
        for fidx in fidxs:
            if fidx < arr.shape[0]:
                imgs.append(np.asarray(arr[fidx], dtype="float32"))
    imgs = np.stack(imgs)
    box = imgs.shape[-1]
    print(f"sample stack: {imgs.shape} | box px: {box}")

    avg, std = imgs.mean(0), imgs.std(0)
    c, r = box // 2, max(4, box // 6)
    center = std[c - r:c + r, c - r:c + r].mean()
    edge = np.concatenate([std[:r].ravel(), std[-r:].ravel(),
                           std[:, :r].ravel(), std[:, -r:].ravel()]).mean()
    ratio = float(center / edge)
    print(f"CENTER/EDGE std ratio = {ratio:.3f}")
    print("  NOTE: for small low-contrast particles this ratio is a WEAK discriminator")
    print("  (it can read ~1.0 even when localization is correct). The reliable test is")
    print("  the AVERAGE: a faint CENTRED blob = OK; a flat average = suspect Y-flip.")

    out_imgs = os.path.join(cfg["work_dir"], "verif_imgs.npy")
    out_avg = os.path.join(cfg["work_dir"], "verif_avg.npy")
    out_std = os.path.join(cfg["work_dir"], "verif_std.npy")
    np.save(out_imgs, imgs)
    np.save(out_avg, avg.astype("float32"))
    np.save(out_std, std.astype("float32"))
    print(f"\nsaved {out_imgs} / verif_avg.npy / verif_std.npy")
    mp = cfg.get("montage_python") or "<crYOLO-env python>"
    print("render the montage IN THE crYOLO ENV (has matplotlib):")
    print(f"  {mp} make_montage.py verify --work-dir {cfg['work_dir']}")
    print("If the average shows a centred blob: class2d. If flat/flipped: "
          "inject --flip-y, then re-extract.")


def cmd_dumpclasses(cfg, args):
    """Read a finished 2D job's class averages + per-class counts -> cls_*.npy.

    Read-only. Loads the class_averages output (blob/path + blob/idx via cryosparc.mrc)
    and the per-class particle counts, then np.saves cls_imgs.npy / cls_counts.npy into
    work_dir so make_montage.py class2d can render the sorted class montage. Mirrors the
    original session's read_2d_classes.py, generalized.
    """
    from collections import defaultdict
    from cryosparc import mrc

    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    proj_dir = str(proj.dir())
    job = cs.find_job(cfg["project"], args.class2d)

    try:
        out_names = [o.name for o in job.outputs()]
    except Exception:
        out_names = []
    ca = grp = None
    for g in ["class_averages", "templates"] + out_names:
        try:
            ca = job.load_output(g)
            grp = g
            break
        except Exception:
            pass
    if ca is None:
        die(f"could not load a class-average output from {args.class2d}")
    K = len(ca)
    print(f"class group: {grp} | n classes: {K}")

    paths, idxs = ca["blob/path"], ca["blob/idx"]
    bypath = defaultdict(list)
    for i in range(K):
        p = paths[i].decode() if isinstance(paths[i], bytes) else paths[i]
        bypath[p].append((int(idxs[i]), i))
    imgs = [None] * K
    for p, lst in bypath.items():
        res = mrc.read(os.path.join(proj_dir, p))
        data = res[1] if isinstance(res, tuple) else res
        arr = np.asarray(data)
        if arr.ndim == 2:
            arr = arr[None]
        for fidx, i in lst:
            imgs[i] = arr[fidx]
    imgs = np.stack(imgs)

    # per-class particle counts: prefer a num_particles field, else bincount the
    # particle output's alignments2D/class (matches FACTS 1g).
    fields = list(ca.fields())
    counts = None
    for cf in fields:
        if "num_particles" in cf.lower():
            counts = np.asarray(ca[cf]).astype(float)
            print(f"count field: {cf}")
            break
    if counts is None:
        parts = pg = None
        for g in ("particles", "particles_selected", "particles_all"):
            try:
                parts = job.load_output(g)
                pg = g
                break
            except Exception:
                pass
        if parts is not None and "alignments2D/class" in parts.fields():
            bc = np.bincount(np.asarray(parts["alignments2D/class"]).astype("i8"), minlength=K)
            counts = bc[:K].astype(float)
            print(f"counts from np.bincount({pg}.alignments2D/class)")
    if counts is None:
        counts = np.full(K, -1.0)
        print("no per-class counts available; montage will be unsorted/unlabelled")

    out_imgs = os.path.join(cfg["work_dir"], "cls_imgs.npy")
    out_counts = os.path.join(cfg["work_dir"], "cls_counts.npy")
    np.save(out_imgs, imgs.astype("float32"))
    np.save(out_counts, counts)
    good = int((counts >= 0).sum())
    tot = int(counts[counts >= 0].sum()) if good else -1
    print(f"\nsaved {out_imgs} {imgs.shape} and cls_counts.npy "
          f"(total particles in classes: {tot if tot >= 0 else 'n/a'})")
    mp = cfg.get("montage_python") or "<crYOLO-env python>"
    print("render the 2D class montage IN THE crYOLO ENV (has matplotlib):")
    print(f"  {mp} make_montage.py class2d --work-dir {cfg['work_dir']} --label {args.class2d}")


def cmd_class2d(cfg, args):
    K = int(cfg.get("class2D_K", 50))
    lane = resolve_lane(cfg)

    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    tag = " (optimized)" if args.optimize else ""
    cl = proj.create_job(cfg["workspace"], "class_2D_new",
                         connections={"particles": (args.extract, "particles")},
                         title=f"2D class {args.extract} ({K} cls){tag}")
    cl.set_param("class2D_K", K)

    if args.optimize:
        # the verified pair for a small/low-contrast particle with a background ring:
        # a tighter circular mask AND a high-pass on the alignment.
        wo = cfg.get("class2D_window_outer_A")
        mr = cfg.get("class2D_min_res_align")
        if wo:
            cl.set_param("class2D_window_outer_A", float(wo))
            print(f"  class2D_window_outer_A = {wo} A (tighter circular mask)")
        if mr:
            cl.set_param("class2D_min_res_align", float(mr))
            print(f"  class2D_min_res_align  = {mr} A (high-pass to stop ice/background driving alignment)")
        if not wo and not mr:
            print("  --optimize set but neither class2D_window_outer_A nor "
                  "class2D_min_res_align is in the config; building with defaults.")

    cl.refresh()
    print(f"built 2D job {cl.uid}: class2D_K={cl.params.model_dump().get('class2D_K')} "
          f"<- particles {args.extract}/particles")

    if not args.confirm:
        print(f"\nDRY RUN (no --confirm). Would queue {cl.uid} to lane {lane!r}.")
        print("Re-run with --confirm to queue.")
        return
    if not lane:
        die("no lane resolvable: set 'lane' in the config or export CS_LANE")
    cl.queue(lane=lane)
    print(f"\nQUEUED {cl.uid} to lane {lane!r}.")
    print(f"CLASS2D_JOB_UID={cl.uid}")
    print("Inspect class_averages (blob/res_A per class) when it finishes. To render the "
          "class montage, first dump the class npys:")
    print(f"  dumpclasses --class2d {cl.uid}    # writes cls_imgs.npy / cls_counts.npy")
    print("then render in the crYOLO env: make_montage.py class2d --work-dir <work_dir>.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, helptext, extra=None):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--config", required=True, help="path to the crYOLO-pick JSON config")
        if extra:
            extra(p)
        p.set_defaults(fn=fn)

    add("inspect", cmd_inspect, "read-only: source exposures + box-size suggestions")
    add("config", cmd_config, "write a crYOLO config JSON (crYOLO env)",
        lambda p: p.add_argument("--box", type=int, default=None,
                                 help="crYOLO anchor box in px (default: cryolo_box_pix from "
                                      "config, else derived ~particle_diameter_A / psize)"))
    add("predict", cmd_predict, "symlink mics + run cryolo_predict.py (GPU; --confirm)",
        lambda p: p.add_argument("--confirm", action="store_true",
                                 help="actually run the GPU picking (otherwise dry-run)"))
    add("threshold", cmd_threshold, "CBOX per-image distribution -> recommend a confidence")
    add("inject", cmd_inject, "CBOX -> external picks job at a confidence",
        lambda p: (p.add_argument("--conf", type=float, default=None,
                                  help="confidence to inject at (default: threshold from config)"),
                   p.add_argument("--flip-y", action="store_true",
                                  help="mirror Y (center_y_frac = 1 - cy/NY)")))
    add("extract", cmd_extract, "Extract From Micrographs (GPU; --confirm + lane)",
        lambda p: (p.add_argument("--picks", required=True, help="external picks job uid (J###)"),
                   p.add_argument("--confirm", action="store_true",
                                  help="actually queue the extract (otherwise dry-run)")))
    add("verify", cmd_verify, "sample extracted particles + Y-flip check (read-only)",
        lambda p: (p.add_argument("--extract", required=True, help="extract job uid (J###)"),
                   p.add_argument("--nsample", type=int, default=100,
                                  help="number of particles to sample (default 100)")))
    add("class2d", cmd_class2d, "2D Classification (GPU; --confirm + lane)",
        lambda p: (p.add_argument("--extract", required=True, help="extract job uid (J###)"),
                   p.add_argument("--optimize", action="store_true",
                                  help="apply config optimization knobs (tight mask + high-pass)"),
                   p.add_argument("--confirm", action="store_true",
                                  help="actually queue the 2D (otherwise dry-run)")))
    add("dumpclasses", cmd_dumpclasses,
        "read-only: dump a finished 2D job's class averages + counts -> cls_*.npy",
        lambda p: p.add_argument("--class2d", required=True,
                                 help="finished 2D class job uid (J###)"))

    args = ap.parse_args()
    cfg = load_config(args.config)
    args.fn(cfg, args)


if __name__ == "__main__":
    main()
