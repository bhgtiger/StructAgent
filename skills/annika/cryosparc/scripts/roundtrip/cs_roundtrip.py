#!/usr/bin/env python3
"""cs_roundtrip.py — push RELION 3D-classification results back into cryoSPARC.

Config-driven automation for the RELION-class → cryoSPARC re-refinement round-trip
(see the cryoSPARC skill reference references/28_relion_class3d_roundtrip.md). Given a
per-particle class assignment that maps back to a cryoSPARC source job's particles
(built by map_relion_classes.py), it can, for each kept class:

  * create an External Job holding the class's particle subset (poses + CTF
    preserved as a passthrough from the source job — particles are NOT re-pushed
    as raw stacks);
  * build a Local Refinement of the focus region (params cloned from the source
    local-refine job by default);
  * optionally build a whole-molecule Non-Uniform Refinement against a consensus
    reference;
  * queue the built jobs to a lane.

SAFETY CONTRACT (mirrors the cryoSPARC skill SKILL.md):
  * 'inspect' is read-only.
  * 'build' / 'nurefine' create jobs but leave them in 'building' status (no compute).
  * Nothing is queued unless you pass --confirm AND a lane is resolvable.
  * Credentials come ONLY from env vars CRYOSPARC_EMAIL / CRYOSPARC_PASSWORD.

Subcommands:
  inspect   read-only: verify the source job + class<->uid overlap + per-class counts
  build     create per-class external subsets + build Local Refinements (no queue)
  queue     queue the built Local Refinements to a lane (needs --confirm + lane)
  nurefine  build per-class whole-molecule NU refinements (queue only with --confirm)
  verify    post-run check: output count and gold-standard split balance

Usage:
  cs_roundtrip.py inspect  --config roundtrip.json
  cs_roundtrip.py build    --config roundtrip.json
  cs_roundtrip.py queue    --config roundtrip.json --confirm
  cs_roundtrip.py nurefine --config roundtrip.json [--confirm]
  cs_roundtrip.py verify   --config roundtrip.json
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

from rt_common import (  # noqa: E402
    load_config, connect, load_assignment, clone_source_params, resolve_lane,
    built_jobs_path, nu_jobs_path, read_job_table, die,
    apply_subset_refine_params,
)


def _source_particles(cs, cfg):
    job = cs.find_job(cfg["project"], cfg["source_job"])
    pslot = cfg["source_outputs"]["particles"]
    ds = job.load_output(pslot, slots="all")
    return job, ds


def cmd_inspect(cfg, args):
    cs = connect(cfg)
    print("connected. accessible projects:", [p.uid for p in cs.find_projects()][:12])
    job, ds = _source_particles(cs, cfg)
    print(f"\nsource {cfg['source_job']} type: {job.type}")
    print(f"{cfg['source_job']} output groups:")
    job.print_output_spec()

    csuid = ds["uid"]
    print(f"\n{cfg['source_job']} particles loaded: {len(ds)} rows; has uid: {'uid' in ds.fields()}")
    uid, cls = load_assignment(cfg)
    ov = int(np.isin(csuid, uid).sum())
    print(f"uid overlap with assignment: {ov} / {len(csuid)}")
    if ov != len(csuid):
        print("  WARNING: not every source particle has an assignment — check map_relion_classes.py")
    print("\nper-class counts (matched against the source dataset):")
    seen = set(int(c) for c in cfg["keep_classes"])
    for c in cfg["keep_classes"]:
        n = int(np.isin(csuid, uid[cls == c]).sum())
        print(f"  class {c} (KEEP): {n}")
    for c in sorted(set(int(x) for x in np.unique(cls)) - seen):
        n = int(np.isin(csuid, uid[cls == c]).sum())
        print(f"  class {c} (drop): {n}")
    print("\ninspect OK. If counts look right, run: build")


def cmd_build(cfg, args):
    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    job, ds = _source_particles(cs, cfg)
    csuid = ds["uid"]
    uid, cls = load_assignment(cfg)

    out = cfg["source_outputs"]
    vol_out, mask_out, pslot = out["volume"], out["mask"], out["particles"]
    if cfg["local_refine"]["clone_params_from_source"]:
        params = clone_source_params(job)
        if not params:
            die(f"clone_params_from_source is set but no params were read from "
                f"{cfg['source_job']} — refusing to build Local Refinements with bare "
                "defaults. Check the cryosparc-tools version, or set "
                "local_refine.clone_params_from_source=false and supply params_override.")
        print(f"cloned {len(params)} params from {cfg['source_job']}")
    else:
        params = {}
    params.update(cfg["local_refine"].get("params_override", {}))
    params = apply_subset_refine_params(cfg, params)

    if not cfg["keep_classes"]:
        die("config 'keep_classes' is empty — nothing to build")

    built = []
    for c in cfg["keep_classes"]:
        m = np.isin(csuid, uid[cls == c])
        subset = ds.mask(m)
        n = len(subset)
        if n == 0:
            print(f"--- class {c}: 0 particles, skipping ---")
            continue
        print(f"\n--- class {c}: {n} particles ---")
        ext_uid = cs.save_external_result(
            cfg["project"], cfg["workspace"], dataset=subset,
            type="particle", name="particles",
            passthrough=(cfg["source_job"], pslot),
            title=f"{cfg['source_job']} RELION class {c} particles (n={n})",
        )
        print(f"  external particle job: {ext_uid}")
        lr = proj.create_job(
            cfg["workspace"], "new_local_refine",
            connections={
                "particles": (ext_uid, "particles"),
                "volume": (cfg["source_job"], vol_out),
                "mask": (cfg["source_job"], mask_out),
            },
            params=params,
            title=f"Local refine - RELION class {c} (n={n})",
        )
        print(f"  built local refine: {lr.uid} (status building, NOT queued)")
        built.append((c, ext_uid, lr.uid, n))

    path = built_jobs_path(cfg)
    os.makedirs(cfg["work_dir"], exist_ok=True)
    with open(path, "w") as f:
        for c, ext_uid, lr_uid, n in built:
            f.write(f"{c}\t{ext_uid}\t{lr_uid}\t{n}\n")
    print(f"\nwrote {path}")
    print("build done. Review jobs in the GUI, then: queue --confirm")


def cmd_queue(cfg, args):
    lane = resolve_lane(cfg)
    rows = read_job_table(built_jobs_path(cfg))
    if not args.confirm:
        print("DRY RUN (no --confirm). Would queue these Local Refinements"
              f" to lane {lane!r}:")
        for c, ext_uid, lr_uid, n in rows:
            print(f"  class {c}: {lr_uid} (n={n})")
        print("\nRe-run with --confirm to actually queue.")
        return
    if not lane:
        die("no lane resolvable: set 'lane' in the config or export CS_LANE")
    cs = connect(cfg)
    print(f"queueing {len(rows)} Local Refinements to lane {lane!r}:")
    for c, ext_uid, lr_uid, n in rows:
        cs.find_job(cfg["project"], lr_uid).queue(lane=lane)
        print(f"  class {c}: {lr_uid} queued (n={n})")
    print("done. Monitor in the GUI or with cryosparc-tools wait_for_done.")


def cmd_nurefine(cfg, args):
    nu = cfg["nu_refine"]
    if not nu.get("enabled"):
        die("config nu_refine.enabled is false — enable it and set whole_mol_ref")
    ref = nu.get("whole_mol_ref")
    if not ref or "job" not in ref:
        die("config nu_refine.whole_mol_ref must specify {'job': 'J###', 'output': 'volume'}")
    ref_pair = (ref["job"], ref.get("output", "volume"))
    rows = read_job_table(built_jobs_path(cfg))
    lane = resolve_lane(cfg)

    cs = connect(cfg)
    proj = cs.find_project(cfg["project"])
    built = []
    for c, ext_uid, lr_uid, n in rows:
        nuj = proj.create_job(
            cfg["workspace"], "nonuniform_refine_new",
            connections={"particles": (ext_uid, "particles"), "volume": ref_pair},
            params=apply_subset_refine_params(cfg, nu.get("params", {})),
            title=f"NU refine (whole mol) - RELION class {c} (n={n})",
        )
        print(f"class {c}: built NU refine {nuj.uid} "
              f"(particles {ext_uid}, ref {ref_pair[0]}/{ref_pair[1]}), status building")
        built.append((c, ext_uid, nuj.uid, n))

    path = nu_jobs_path(cfg)
    with open(path, "w") as f:
        for c, ext_uid, nu_uid, n in built:
            f.write(f"{c}\t{ext_uid}\t{nu_uid}\t{n}\n")
    print(f"\nwrote {path}")

    if args.confirm and lane:
        print(f"\nqueueing {len(built)} NU refinements to lane {lane!r}:")
        for c, ext_uid, nu_uid, n in built:
            cs.find_job(cfg["project"], nu_uid).queue(lane=lane)
            print(f"  class {c}: {nu_uid} queued (n={n})")
    elif args.confirm and not lane:
        die("no lane resolvable: set 'lane' in the config or export CS_LANE")
    else:
        print("built but NOT queued (no --confirm). Re-run with --confirm + a lane to queue.")


def _split_counts(ds):
    if "alignments3D/split" not in ds.fields():
        return [], float("inf")
    vals, counts = np.unique(ds["alignments3D/split"], return_counts=True)
    split = [(int(v), int(c)) for v, c in zip(vals, counts)]
    if len(counts) != 2 or min(counts) == 0:
        return split, float("inf")
    return split, float(max(counts) / min(counts))


def _verify_refine(cs, project, ext_uid, refine_uid, expected_n, tol, max_ratio):
    di = cs.find_job(project, ext_uid).load_output("particles", slots="all")
    do = cs.find_job(project, refine_uid).load_output("particles", slots="all")
    in_n = len(di)
    out_n = len(do)
    expected_n = int(expected_n)
    culled = in_n - out_n
    split, ratio = _split_counts(do)
    ok = culled <= tol and ratio <= max_ratio
    print(f"{refine_uid}: expected {expected_n}; in {in_n} -> out {out_n} "
          f"(culled {culled}); split {split} ratio {ratio:.2f} "
          f"{'OK' if ok else 'FAIL'}")
    if in_n != expected_n:
        print(f"  WARNING: job table expected n={expected_n}, external subset now has n={in_n}")
    return ok


def cmd_verify(cfg, args):
    paths = []
    if args.job_table:
        paths.append(args.job_table)
    else:
        for p in (built_jobs_path(cfg), nu_jobs_path(cfg)):
            if os.path.isfile(p):
                paths.append(p)
    if not paths:
        die("no job table found; run build/nurefine first or pass --job-table")

    cs = connect(cfg)
    all_ok = True
    for path in paths:
        rows = read_job_table(path)
        print(f"\nverifying {len(rows)} rows from {path}")
        for c, ext_uid, refine_uid, n in rows:
            ok = _verify_refine(cs, cfg["project"], ext_uid, refine_uid,
                                n, args.tol, args.max_ratio)
            all_ok = all_ok and ok
    if not all_ok:
        die("one or more subset refines failed count/split verification")
    print("\nverify OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, helptext in [
        ("inspect", cmd_inspect, "read-only verify source + class assignment"),
        ("build", cmd_build, "build per-class external subsets + Local Refinements"),
        ("queue", cmd_queue, "queue the built Local Refinements (needs --confirm)"),
        ("nurefine", cmd_nurefine, "build per-class NU refinements (queue with --confirm)"),
        ("verify", cmd_verify, "verify completed subset refines kept particles and resplit GS halves"),
    ]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--config", required=True, help="path to roundtrip JSON config")
        if name in ("queue", "nurefine"):
            p.add_argument("--confirm", action="store_true",
                           help="actually queue compute (otherwise dry-run)")
        if name == "verify":
            p.add_argument("--job-table",
                           help="specific TSV to verify; defaults to built_jobs.tsv and nu_jobs.tsv if present")
            p.add_argument("--tol", type=int, default=200,
                           help="maximum tolerated particle loss, usually duplicate removal (default: 200)")
            p.add_argument("--max-ratio", type=float, default=1.5,
                           help="maximum tolerated GS split imbalance ratio (default: 1.5)")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    cfg = load_config(args.config)
    args.fn(cfg, args)


if __name__ == "__main__":
    main()
