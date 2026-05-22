#!/usr/bin/env python3
"""Safe cryoSPARC tools harness.

Default behavior is read-only / dry-run. This script refuses to queue jobs unless
all confirmation fields are supplied and --queue-confirm is exactly QUEUE.

Connection env vars supported by cryosparc-tools:
  CRYOSPARC_BASE_URL or CRYOSPARC_MASTER_HOSTNAME + CRYOSPARC_BASE_PORT
  CRYOSPARC_EMAIL + CRYOSPARC_PASSWORD, or an existing `python -m cryosparc.tools login` session
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Dict, List, Optional

TERMINAL = {"completed", "failed", "killed"}
SAFE_STATUSES_FOR_QUEUE = {"building"}


class HarnessError(RuntimeError):
    pass


def jprint(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def load_cryosparc():
    try:
        from cryosparc.tools import CryoSPARC  # type: ignore
        import cryosparc  # type: ignore
    except Exception as e:
        raise HarnessError(
            "cryosparc-tools is not importable in this Python. Install a version "
            "matching the target cryoSPARC minor version, e.g. `pip install "
            "--force 'cryosparc-tools~=5.0.0'`, or run inside the environment "
            "where cryosparc-tools is already installed."
        ) from e
    return CryoSPARC, cryosparc


def version_report() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "env_present": {k: bool(os.getenv(k)) for k in [
            "CRYOSPARC_BASE_URL", "CRYOSPARC_MASTER_HOSTNAME", "CRYOSPARC_BASE_PORT",
            "CRYOSPARC_EMAIL", "CRYOSPARC_PASSWORD",
        ]},
    }
    for pkg in ["cryosparc-tools", "cryosparc"]:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def connect(timeout: int = 60):
    CryoSPARC, cryosparc = load_cryosparc()
    cs = CryoSPARC(timeout=timeout)
    return cs, cryosparc


def safe_get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        try:
            val = getattr(obj, name)
            if callable(val) and name.startswith("get_"):
                val = val()
            if val is not None:
                return val
        except Exception:
            pass
    return default


def summarize_job(job: Any) -> Dict[str, Any]:
    try:
        job.refresh()
    except Exception:
        pass
    return {
        "uid": safe_get(job, "uid"),
        "project_uid": safe_get(job, "project_uid"),
        "type": safe_get(job, "type"),
        "status": safe_get(job, "status"),
        "title": safe_get(job, "title", default=""),
        "dir": str(safe_get(job, "dir", default="")),
        "params_keys": sorted(list(getattr(safe_get(job, "params", default={}), "keys", lambda: [])())) if hasattr(safe_get(job, "params", default={}), "keys") else None,
        "inputs": sorted(list(getattr(safe_get(job, "inputs", default={}), "keys", lambda: [])())) if hasattr(safe_get(job, "inputs", default={}), "keys") else None,
        "outputs": sorted(list(getattr(safe_get(job, "outputs", default={}), "keys", lambda: [])())) if hasattr(safe_get(job, "outputs", default={}), "keys") else None,
    }


def find_project(cs: Any, project_uid: str):
    return cs.find_project(project_uid)


def find_job(cs: Any, project_uid: str, job_uid: str):
    if hasattr(cs, "find_job"):
        return cs.find_job(project_uid, job_uid)
    return find_project(cs, project_uid).find_job(job_uid)


def cmd_doctor(args: argparse.Namespace) -> None:
    report = version_report()
    try:
        cs, cryosparc = connect(timeout=args.timeout)
        report["connect"] = "ok"
        report["cryosparc_module"] = getattr(cryosparc, "__file__", None)
        report["user"] = getattr(getattr(cs, "user", None), "email", None) or str(getattr(cs, "user", ""))
        try:
            report["server_version"] = cs.api.config.get_version()
        except Exception as e:
            report["server_version_error"] = str(e)
        try:
            report["lanes"] = cs.get_lanes()
        except Exception as e:
            report["lanes_error"] = str(e)
    except HarnessError as e:
        report["connect"] = "blocked"
        report["reason"] = str(e)
    except Exception as e:
        report["connect"] = "failed"
        report["reason"] = repr(e)
    jprint(report)


def cmd_list_projects(args: argparse.Namespace) -> None:
    cs, _ = connect(timeout=args.timeout)
    projects = cs.find_projects() if hasattr(cs, "find_projects") else cs.api.projects.find()
    jprint(projects)


def cmd_list_workspaces(args: argparse.Namespace) -> None:
    cs, _ = connect(timeout=args.timeout)
    project = find_project(cs, args.project_uid)
    if hasattr(project, "find_workspaces"):
        out = project.find_workspaces()
    else:
        out = cs.api.workspaces.find(args.project_uid)
    jprint(out)


def cmd_list_jobs(args: argparse.Namespace) -> None:
    cs, _ = connect(timeout=args.timeout)
    project = find_project(cs, args.project_uid)
    if hasattr(project, "find_jobs"):
        jobs = project.find_jobs(workspace_uid=args.workspace_uid) if args.workspace_uid else project.find_jobs()
    else:
        jobs = cs.api.jobs.find(args.project_uid, workspace_uid=args.workspace_uid)
    jprint(jobs)


def cmd_inspect_job(args: argparse.Namespace) -> None:
    cs, _ = connect(timeout=args.timeout)
    job = find_job(cs, args.project_uid, args.job_uid)
    out = summarize_job(job)
    if args.print_specs:
        # These print to stdout in cryosparc-tools; keep under explicit flag.
        for method in ["print_param_spec", "print_input_spec", "print_output_spec"]:
            if hasattr(job, method):
                print(f"\n--- {method} ---")
                getattr(job, method)()
    else:
        jprint(out)


def parse_json_arg(text: Optional[str], label: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as e:
        raise HarnessError(f"{label} must be valid JSON: {e}") from e
    if not isinstance(value, dict):
        raise HarnessError(f"{label} must be a JSON object")
    return value


@dataclass
class CreatePlan:
    action: str
    project_uid: str
    workspace_uid: str
    job_type: str
    title: str
    params: Dict[str, Any]
    connections: Dict[str, Any]
    lane: Optional[str]
    queue_requested: bool
    queue_confirmed: bool
    timestamp: str


def build_create_plan(args: argparse.Namespace) -> CreatePlan:
    return CreatePlan(
        action="create_job",
        project_uid=args.project_uid,
        workspace_uid=args.workspace_uid,
        job_type=args.job_type,
        title=args.title or "",
        params=parse_json_arg(args.params_json, "--params-json"),
        connections=parse_json_arg(args.connections_json, "--connections-json"),
        lane=args.lane,
        queue_requested=args.queue,
        queue_confirmed=(args.queue_confirm == "QUEUE"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def cmd_create_job(args: argparse.Namespace) -> None:
    plan = build_create_plan(args)
    if args.dry_run:
        jprint({"dry_run": True, "would": asdict(plan)})
        return
    if args.queue and not (args.project_uid and args.workspace_uid and args.lane and args.queue_confirm == "QUEUE"):
        raise HarnessError("Queue refused: require --project-uid, --workspace-uid, --lane, and --queue-confirm QUEUE")

    cs, _ = connect(timeout=args.timeout)
    project = find_project(cs, args.project_uid)
    job = project.create_job(
        args.workspace_uid,
        args.job_type,
        connections=plan.connections or None,
        params=plan.params or None,
        title=plan.title,
    )
    summary = summarize_job(job)
    result = {"created": summary, "queued": False}
    if args.queue:
        status = summary.get("status")
        if status not in SAFE_STATUSES_FOR_QUEUE:
            raise HarnessError(f"Queue refused: job status is {status!r}, expected one of {sorted(SAFE_STATUSES_FOR_QUEUE)}")
        job.queue(lane=args.lane)
        result["queued"] = True
        result["after_queue"] = summarize_job(job)
    jprint(result)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Safe cryoSPARC tools harness")
    p.add_argument("--timeout", type=int, default=60)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    sp = sub.add_parser("list-projects")
    sp.set_defaults(func=cmd_list_projects)

    sp = sub.add_parser("list-workspaces")
    sp.add_argument("--project-uid", required=True)
    sp.set_defaults(func=cmd_list_workspaces)

    sp = sub.add_parser("list-jobs")
    sp.add_argument("--project-uid", required=True)
    sp.add_argument("--workspace-uid")
    sp.set_defaults(func=cmd_list_jobs)

    sp = sub.add_parser("inspect-job")
    sp.add_argument("--project-uid", required=True)
    sp.add_argument("--job-uid", required=True)
    sp.add_argument("--print-specs", action="store_true")
    sp.set_defaults(func=cmd_inspect_job)

    sp = sub.add_parser("create-job")
    sp.add_argument("--project-uid", required=True)
    sp.add_argument("--workspace-uid", required=True)
    sp.add_argument("--job-type", required=True)
    sp.add_argument("--title", default="")
    sp.add_argument("--params-json", help='JSON object, e.g. {"abinit_K":3}')
    sp.add_argument("--connections-json", help='JSON object, e.g. {"particles":["J20","particles_selected"]}')
    sp.add_argument("--lane")
    sp.add_argument("--dry-run", action="store_true", default=True, help="Print plan only; default")
    sp.add_argument("--commit", dest="dry_run", action="store_false", help="Actually create the job, but do not queue unless --queue is also supplied")
    sp.add_argument("--queue", action="store_true", help="Queue after create; requires --queue-confirm QUEUE")
    sp.add_argument("--queue-confirm", default="")
    sp.set_defaults(func=cmd_create_job)

    args = p.parse_args(argv)
    try:
        args.func(args)
        return 0
    except HarnessError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
