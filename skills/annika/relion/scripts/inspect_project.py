#!/usr/bin/env python3
"""inspect_project.py - READ-ONLY RELION project-tree diagnostic.

Walks a RELION project directory and summarizes it the way a human triaging a
failed run would: pipeline graph from default_pipeline.star, per-job exit
sentinels, the real error excerpt from run.err (filtering X11/MPI noise),
optics-group / pixel-size summary, and the standard outputs a job did or did
not produce.

This script NEVER writes inside the project. It only reads. It tails logs and
reads small metadata STARs; it does not load particle tables.

Usage:
    python3 inspect_project.py PROJECT_DIR              # whole-project summary
    python3 inspect_project.py PROJECT_DIR JOB          # one job, deep (e.g. Refine3D/job034)
    python3 inspect_project.py PROJECT_DIR --failed      # only failed/aborted jobs
    python3 inspect_project.py PROJECT_DIR --json        # machine-readable

Exit status is always 0 on a readable project (it is a report, not a test).
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from star_min import read_star, loop_dicts  # noqa: E402

SENTINELS = {
    "RELION_JOB_EXIT_SUCCESS": "SUCCEEDED",
    "RELION_JOB_EXIT_FAILURE": "FAILED",
    "RELION_JOB_EXIT_ABORTED": "ABORTED",
    "RELION_JOB_ABORT_NOW": "ABORT-REQUESTED",
}

# Lines in run.err that are noise, not the real error.
NOISE = (
    "No protocol specified",
    "MPI_ABORT was invoked",
    "NOTE: invoking MPI_ABORT",
    "You may or may not see output",
    "exactly when Open MPI kills",
    "orte_base_help_aggregate",
    "has sent help message",
    "Set MCA parameter",
    "--------------------------------------------------------------------------",
    "Warning: Unable to load",
    "QStandardPaths",
    "libGL error",
)


def _tail(path: str, n: int = 40) -> list[str]:
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read().splitlines()[-n:]
    except OSError:
        return []


def _job_sentinel(job_dir: str) -> str:
    for fn, label in SENTINELS.items():
        if os.path.exists(os.path.join(job_dir, fn)):
            return label
    return "RUNNING/UNKNOWN"  # no sentinel: still running, killed, or never started


def _real_error(job_dir: str) -> str:
    """Best-effort extraction of the meaningful error line from run.err."""
    lines = _tail(os.path.join(job_dir, "run.err"), 80)
    signal = [l for l in lines if l.strip() and not any(tok in l for tok in NOISE)]
    # RELION prints `ERROR:` then the message on the next non-empty line.
    for i, l in enumerate(signal):
        if l.strip() == "ERROR:" and i + 1 < len(signal):
            return signal[i + 1].strip()
        if l.startswith("ERROR:"):
            return l[len("ERROR:"):].strip() or (signal[i + 1].strip() if i + 1 < len(signal) else l)
    # Otherwise the last meaningful line.
    return signal[-1].strip() if signal else ""


def _job_command(job_dir: str) -> str:
    """The executed command, from note.txt (between the backticks/`which`)."""
    note = os.path.join(job_dir, "note.txt")
    try:
        with open(note, "r", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if s.startswith("`") or "relion_" in s and "--" in s:
                    return s
    except OSError:
        pass
    return ""


def _job_type(job_dir: str) -> str:
    js = os.path.join(job_dir, "job.star")
    if os.path.exists(js):
        try:
            b = read_star(js, only_blocks=["job"])
            return b.get("job", {}).get("pairs", {}).get("_rlnJobTypeLabel", "?")
        except Exception:
            return "?"
    return "legacy(run.job)" if os.path.exists(os.path.join(job_dir, "run.job")) else "?"


def read_pipeline(project: str) -> list[dict]:
    """Return [{name, alias, type, status}] from default_pipeline.star."""
    pp = os.path.join(project, "default_pipeline.star")
    if not os.path.exists(pp):
        return []
    blocks = read_star(pp, only_blocks=["pipeline_processes"])
    out = []
    for d in loop_dicts(blocks.get("pipeline_processes", {})):
        out.append({
            "name": d.get("_rlnPipeLineProcessName", "?"),
            "alias": d.get("_rlnPipeLineProcessAlias", "None"),
            "type": d.get("_rlnPipeLineProcessTypeLabel", d.get("_rlnPipeLineProcessType", "?")),
            "status": d.get("_rlnPipeLineProcessStatusLabel", d.get("_rlnPipeLineProcessStatus", "?")),
        })
    return out


def optics_summary(project: str) -> list[dict]:
    """Optics groups + pixel sizes from the first particles STAR we can find."""
    candidates = ["particles.star"]
    for root in ("Extract", "Select", "Refine3D", "Polish", "CtfRefine"):
        d = os.path.join(project, root)
        if os.path.isdir(d):
            for sub in sorted(os.listdir(d)):
                for fn in ("particles.star", "shiny.star", "run_data.star"):
                    candidates.append(os.path.join(root, sub, fn))
    for rel in candidates:
        path = os.path.join(project, rel)
        if not os.path.exists(path):
            continue
        try:
            b = read_star(path, only_blocks=["optics"], max_loop_rows=50)
        except Exception:
            continue
        rows = list(loop_dicts(b.get("optics", {})))
        if rows:
            keep = ("_rlnOpticsGroupName", "_rlnOpticsGroup", "_rlnMicrographPixelSize",
                    "_rlnMicrographOriginalPixelSize", "_rlnImagePixelSize", "_rlnImageSize",
                    "_rlnVoltage", "_rlnSphericalAberration", "_rlnAmplitudeContrast")
            return [{k: r.get(k) for k in keep if k in r} | {"_source": rel} for r in rows]
    return []


def scan_jobs(project: str) -> list[dict]:
    jobs = []
    for typ in sorted(os.listdir(project)):
        tdir = os.path.join(project, typ)
        if not os.path.isdir(tdir) or typ in ("Trash",) or typ.startswith("."):
            continue
        for jb in sorted(os.listdir(tdir)):
            jdir = os.path.join(tdir, jb)
            if not (os.path.isdir(jdir) and jb.startswith("job")):
                continue
            status = _job_sentinel(jdir)
            rec = {"job": f"{typ}/{jb}", "type": _job_type(jdir), "status": status}
            if status in ("FAILED", "ABORTED"):
                rec["error"] = _real_error(jdir)
            jobs.append(rec)
    return jobs


def inspect_one(project: str, job: str) -> dict:
    jdir = os.path.join(project, job)
    if not os.path.isdir(jdir):
        return {"error": f"no such job dir: {jdir}"}
    files = sorted(os.listdir(jdir))
    out = {
        "job": job,
        "type": _job_type(jdir),
        "status": _job_sentinel(jdir),
        "command": _job_command(jdir),
        "n_files": len(files),
        "outputs": [f for f in files if f.endswith((".star", ".mrc", ".mrcs", ".pdf", ".bild"))][:40],
    }
    if out["status"] in ("FAILED", "ABORTED"):
        out["error"] = _real_error(jdir)
        out["run_err_tail"] = _tail(os.path.join(jdir, "run.err"), 25)
    # continuation pointers
    opt = [f for f in files if f.endswith("_optimiser.star")]
    if opt:
        out["optimiser_files"] = opt[-3:]
    return out


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    if not args:
        print(__doc__)
        return 2
    project = args[0]
    if not os.path.isdir(project):
        print(f"[FAIL] not a directory: {project}", file=sys.stderr)
        return 2

    if len(args) > 1:
        report = inspect_one(project, args[1].rstrip("/"))
        print(json.dumps(report, indent=2) if "--json" in flags else _fmt_one(report))
        return 0

    pipeline = read_pipeline(project)
    jobs = scan_jobs(project)
    optics = optics_summary(project)
    report = {"project": project, "pipeline_processes": pipeline, "jobs": jobs, "optics": optics}

    if "--json" in flags:
        print(json.dumps(report, indent=2))
        return 0

    failed = [j for j in jobs if j["status"] in ("FAILED", "ABORTED")]
    if "--failed" in flags:
        print(_fmt_failed(failed))
        return 0
    print(_fmt_summary(project, pipeline, jobs, failed, optics))
    return 0


def _fmt_summary(project, pipeline, jobs, failed, optics) -> str:
    by_status: dict[str, int] = {}
    for j in jobs:
        by_status[j["status"]] = by_status.get(j["status"], 0) + 1
    L = [f"RELION project: {project}",
         f"  default_pipeline.star: {len(pipeline)} processes" if pipeline else "  default_pipeline.star: MISSING",
         f"  job folders on disk: {len(jobs)} ({', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))})",
         ""]
    if optics:
        L.append(f"Optics ({optics[0].get('_source','?')}): {len(optics)} group(s)")
        for o in optics[:6]:
            px = o.get("_rlnImagePixelSize") or o.get("_rlnMicrographPixelSize")
            opx = o.get("_rlnMicrographOriginalPixelSize")
            L.append(f"  - {o.get('_rlnOpticsGroupName','?')}: pixel={px} A"
                     + (f" (original {opx} A)" if opx else "")
                     + f", {o.get('_rlnVoltage','?')}kV, Cs={o.get('_rlnSphericalAberration','?')}")
        L.append("")
    if failed:
        L.append(f"FAILED / ABORTED jobs ({len(failed)}):")
        for j in failed:
            L.append(f"  ✗ {j['job']:24} [{j['type']}]  {j.get('error','')}")
    else:
        L.append("No FAILED/ABORTED sentinels found.")
    L.append("")
    L.append("Next: `inspect_project.py PROJECT <job>` for a failed job; see references/21_error_lookup.md.")
    return "\n".join(L)


def _fmt_failed(failed) -> str:
    if not failed:
        return "No FAILED/ABORTED jobs."
    return "\n".join(f"✗ {j['job']} [{j['type']}]\n    {j.get('error','')}" for j in failed)


def _fmt_one(r) -> str:
    if "error" in r and "status" not in r:
        return f"[FAIL] {r['error']}"
    L = [f"{r['job']}  type={r['type']}  status={r['status']}",
         f"  command: {r.get('command','(none in note.txt)')}",
         f"  outputs ({r['n_files']} files): {', '.join(r['outputs'][:20])}"]
    if r.get("optimiser_files"):
        L.append(f"  continue from: {', '.join(r['optimiser_files'])}")
    if r.get("error"):
        L.append(f"  ERROR: {r['error']}")
        L.append("  run.err tail:")
        L += [f"    {x}" for x in r.get("run_err_tail", [])]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
