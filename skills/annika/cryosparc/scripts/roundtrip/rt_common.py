"""Shared helpers for the RELION-class -> cryoSPARC round-trip tools.

Portable: nothing here is hard-coded to a host, project, or job. Everything
site- and dataset-specific is read from a JSON config (see roundtrip.example.json
and README.md). Credentials come ONLY from the environment variables
CRYOSPARC_EMAIL and CRYOSPARC_PASSWORD and are never written or echoed.

Run every tool with a cryosparc-tools interpreter whose version matches the
master. Export credentials first (never put them on the command line — that lands
in shell history and logs):

    export CRYOSPARC_EMAIL='you@lab.org'
    export CRYOSPARC_PASSWORD='...'      # typed at the shell, never committed
    /path/to/cs-tools-venv/bin/python cs_roundtrip.py inspect --config roundtrip.json
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Tuple

import numpy as np

REQUIRED_TOP = ("instance", "project", "workspace", "source_job", "assignment_npz")


def die(msg: str) -> "NoReturn":  # noqa: F821
    raise SystemExit(f"error: {msg}")


def load_config(path: str) -> Dict[str, Any]:
    """Read and minimally validate the round-trip JSON config."""
    if not path or not os.path.isfile(path):
        die(f"config file not found: {path!r} (copy roundtrip.example.json and edit it)")
    with open(path) as fh:
        try:
            cfg = json.load(fh)
        except json.JSONDecodeError as e:
            die(f"config {path!r} is not valid JSON: {e}")
    missing = [k for k in REQUIRED_TOP if k not in cfg]
    if missing:
        die(f"config {path!r} is missing required keys: {', '.join(missing)}")
    inst = cfg["instance"]
    for k in ("host", "port"):
        if k not in inst:
            die(f"config 'instance' block is missing '{k}'")
    # sensible defaults
    cfg.setdefault("source_outputs", {})
    cfg["source_outputs"].setdefault("particles", "particles")
    cfg["source_outputs"].setdefault("volume", "volume")
    cfg["source_outputs"].setdefault("mask", "mask")
    cfg.setdefault("keep_classes", [])
    cfg.setdefault("local_refine", {})
    cfg["local_refine"].setdefault("clone_params_from_source", True)
    cfg["local_refine"].setdefault("params_override", {})
    cfg.setdefault("nu_refine", {})
    cfg["nu_refine"].setdefault("enabled", False)
    cfg["nu_refine"].setdefault("params", {})
    cfg.setdefault("force_gs_resplit", True)
    cfg.setdefault("lane", None)
    # work_dir defaults to the directory holding the assignment npz
    cfg.setdefault("work_dir", os.path.dirname(os.path.abspath(cfg["assignment_npz"])))
    return cfg


def connect(cfg: Dict[str, Any]):
    """Connect to cryoSPARC. Credentials come from env vars only."""
    from cryosparc.tools import CryoSPARC

    em = os.environ.get("CRYOSPARC_EMAIL")
    pw = os.environ.get("CRYOSPARC_PASSWORD")
    if not em or not pw:
        die("set CRYOSPARC_EMAIL and CRYOSPARC_PASSWORD in the environment "
            "(never put them in the config or any file)")
    inst = cfg["instance"]
    kwargs = dict(host=inst["host"], base_port=int(inst["port"]), email=em, password=pw)
    if inst.get("license"):  # instance license id; deprecated kwarg but still accepted
        kwargs["license"] = inst["license"]
    cs = CryoSPARC(**kwargs)
    if not cs.test_connection():
        die("cryoSPARC connection / authentication failed")
    return cs


def load_assignment(cfg: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """Load the (uid, cls) class assignment produced by map_relion_classes.py."""
    npz = cfg["assignment_npz"]
    if not os.path.isfile(npz):
        die(f"assignment npz not found: {npz} (run map_relion_classes.py first)")
    d = np.load(npz)
    for k in ("uid", "cls"):
        if k not in d:
            die(f"{npz} is missing array '{k}' (expected keys: uid, cls)")
    return d["uid"], d["cls"]


def clone_source_params(job) -> Dict[str, Any]:
    """Return every parameter value from a source job so a new job of the same type
    can reproduce it verbatim.

    cryosparc-tools v5: params live flat under job.params (a Params model, extra=allow);
    job.params.model_dump() yields {name: value}. Falls back to the pre-v5 document
    shape job.doc["params_spec"][k]["value"] only if the v5 path yields nothing, so the
    tool stays correct across tools versions. Returns {} if neither shape is readable —
    callers must guard against an empty clone (see cs_roundtrip.cmd_build)."""
    pm = getattr(job, "params", None)
    if pm is not None:
        try:
            params = pm.model_dump()
        except AttributeError:
            params = dict(pm)
        if params:
            return params
    # legacy pre-v5 fallback
    spec = (getattr(job, "doc", {}) or {}).get("params_spec", {}) or {}
    return {k: v.get("value") for k, v in spec.items()
            if isinstance(v, dict) and "value" in v}


def apply_subset_refine_params(cfg: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Force a fresh gold-standard split for a per-class subset refinement.

    The subset External Job preserves source-job passthrough metadata, including
    alignments3D/split. Reusing that inherited split can silently cull particles
    from an imbalanced class subset, so per-class Local/NU refines should resplit
    unless the operator explicitly disables force_gs_resplit in the config.
    """
    params = dict(params)
    if cfg.get("force_gs_resplit", True):
        params["refine_gs_resplit"] = True
    return params


def resolve_lane(cfg: Dict[str, Any]) -> str | None:
    """Lane precedence: env CS_LANE overrides config 'lane'."""
    return os.environ.get("CS_LANE") or cfg.get("lane")


def built_jobs_path(cfg: Dict[str, Any]) -> str:
    return os.path.join(cfg["work_dir"], "built_jobs.tsv")


def nu_jobs_path(cfg: Dict[str, Any]) -> str:
    return os.path.join(cfg["work_dir"], "nu_jobs.tsv")


def read_job_table(path: str):
    """Read a TSV of (class, ext_uid, refine_uid, n) rows written by this tool."""
    if not os.path.isfile(path):
        die(f"job table not found: {path} (run the 'build' step first)")
    rows = []
    for line in open(path):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            die(f"malformed row in {path}: {line!r}")
        rows.append(parts)
    if not rows:
        die(f"job table {path} is empty")
    return rows
