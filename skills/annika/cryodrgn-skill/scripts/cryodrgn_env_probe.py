#!/usr/bin/env python3
"""Read-only environment probe for the cryodrgn-skill config-first session.

PURPOSE
-------
Capture a *read-only* snapshot of whether the current host is ready to run
cryoDRGN (https://github.com/ml-struct-bio/cryodrgn), and write it to a
``site_config.local.md`` (markdown) or JSON report. This report is the per-host
input to the cryodrgn-skill's config-first gate: the skill tailors machine-
specific advice, concrete commands, and workflow recommendations to the host's
computed ``config_state`` (see ``references/02_config_session_and_environment.md``).
On a ``ready`` host the skill MAY emit concrete commands with the user's real
paths and run real cryoDRGN jobs AFTER explicit user confirmation; this probe
only inspects the host and never runs those jobs itself.

SAFETY POLICY (enforced in code, see ``_is_allowed`` and ``FORBIDDEN_TOKENS``)
-----------------------------------------------------------------------------
This probe (NOT the skill as a whole) is strictly read-only. It runs ONLY
harmless presence / version / help inspection commands from an explicit
allowlist, each with a timeout, and writes ONLY the requested output file (or
stdout). The probe itself MUST NEVER:

  * install / create / update / remove packages or environments
    (no ``pip install``, ``conda create``, ``conda install``, ...),
  * download anything or make any network call
    (no ``curl``, ``wget``, ``git clone``, no URLs),
  * run cryoDRGN compute (no training / abinit / analyze / backproject /
    eval_vol / eval_images / dashboard / filter / Jupyter / notebook),
  * submit scheduler jobs (no ``sbatch`` / ``srun`` / ``qsub`` / ``bsub``),
  * dump all environment variables, or traverse private data directories.

These restrictions scope the probe only; running cryoDRGN compute is the
skill's job, gated on the host being ``ready`` and on explicit user
confirmation. The probe stays read-only so that merely characterizing a host is
always side-effect-free.

The user home directory is redacted to ``~`` in any path-like output.

By default the probe does NOT invoke cryoDRGN at all; it only locates
executables, queries package metadata, and reports GPU/Python state. The
optional ``--live-help`` flag captures ``cryodrgn --version`` / ``-h`` (and
selected ``cryodrgn <cmd> -h``) ONLY if a cryodrgn executable is already found;
those are help-only invocations (always terminated by ``-h``/``--version``),
never compute.

This file ships no cryoDRGN source, weights, or data.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone

__probe_version__ = "1.0.0"

# Target cryoDRGN release this skill is grounded against (stable).
TARGET_CRYODRGN_VERSION = "4.2.1"
TARGET_COMMIT = "23ae1a3303b1e623f421b816fc7ea426c9d5b580"

# Python interpreter versions cryoDRGN 4.2.1 is documented/tested against.
# pyproject requires-python is `>=3.10` (no upper bound); README says
# "3.10 through 3.13"; installation docs say tested 3.10-3.12 (with a 3.13
# mention). We treat 3.10-3.13 inclusive as the supported interpreter range and
# flag anything outside it as drift rather than asserting a single range.
PY_TESTED_MIN = (3, 10)
PY_TESTED_MAX = (3, 13)

# --- Command namespace at tag 4.2.1 (from cryodrgn/command_line.py) -----------
# Used only to validate `--selected-help CMD` requests and to enumerate the
# help-only command surface for the static validator. These are NEVER run
# without a trailing `-h`.
MAIN_COMMANDS = [
    "abinit", "abinit_het_old", "abinit_homo_old", "analyze",
    "analyze_landscape", "analyze_landscape_full", "backproject_voxel",
    "dashboard", "direct_traversal", "downsample", "eval_images", "eval_vol",
    "filter", "graph_traversal", "parse_ctf_csparc", "parse_ctf_star",
    "parse_pose_csparc", "parse_pose_star", "parse_star", "pc_traversal",
    "train_nn", "train_vae", "train_dec",
]
UTIL_COMMANDS = [
    "analyze_convergence", "add_psize", "clean", "concat_pkls", "filter_cs",
    "filter_mrcs", "filter_pkl", "filter_star", "flip_hand", "fsc", "gen_mask",
    "invert_contrast", "make_movies", "parse_relion", "phase_flip",
    "plot_classes", "plot_fsc", "select_clusters", "select_random",
    "translate_mrcs", "view_cs_header", "view_header", "view_mrcs", "write_cs",
    "write_star",
]
# Default subcommands whose help is captured with --live-help (no heavy/compute
# launchers like dashboard/filter in the default set; they may still be
# requested explicitly via --selected-help, and remain help-only via `-h`).
DEFAULT_SELECTED_HELP = ["downsample", "parse_pose_star", "parse_ctf_star",
                         "train_vae", "analyze", "abinit"]

# --- Safety allowlist ---------------------------------------------------------
ALLOWED_EXECUTABLES = {
    "sw_vers", "conda", "mamba", "micromamba", "pip", "pip3",
    "nvidia-smi", "cryodrgn", "cryodrgn_utils",
}
# Substrings that must never appear in any command the probe runs. These cover
# install / environment-mutation / download / network / scheduler verbs. NOTE:
# cryoDRGN subcommand *names* are intentionally NOT listed here, because
# `cryodrgn <cmd> -h` (help-only) is allowlisted; compute is prevented instead
# by the structural rule that subcommand calls must terminate in `-h`.
FORBIDDEN_TOKENS = [
    "install", "reinstall", "uninstall", "upgrade", "create", "update",
    "remove", "download", "clone", "curl", "wget", "fetch", "sbatch", "srun",
    "qsub", "bsub", "jupyter", "notebook", "http://", "https://", "ftp://",
    "rm ", "mv ", ">", "&&", "|",
]
NVIDIA_QUERY = [
    "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader",
]


def _contains_forbidden(argv) -> bool:
    joined = " ".join(argv).lower()
    return any(tok in joined for tok in FORBIDDEN_TOKENS)


def _is_allowed(argv) -> bool:
    """Strict structural allowlist for every subprocess the probe may run.

    Returns True only for the exact known-safe read-only command shapes.
    """
    if not argv:
        return False
    if _contains_forbidden(argv):
        return False
    exe = os.path.basename(argv[0])
    if exe not in ALLOWED_EXECUTABLES:
        return False
    rest = argv[1:]

    if exe == "sw_vers":
        return rest == []
    if exe in {"conda", "mamba", "micromamba", "pip", "pip3"}:
        return rest == ["--version"]
    if exe == "nvidia-smi":
        return rest == ["-L"] or rest == NVIDIA_QUERY
    if exe == "cryodrgn":
        if rest in (["--version"], ["-h"]):
            return True
        return len(rest) == 2 and rest[0] in MAIN_COMMANDS and rest[1] == "-h"
    if exe == "cryodrgn_utils":
        if rest == ["-h"]:
            return True
        return len(rest) == 2 and rest[0] in UTIL_COMMANDS and rest[1] == "-h"
    return False


def enumerate_candidate_commands():
    """Every command shape the probe could ever run (for static auditing).

    Assumes a hypothetical host where all executables exist and --live-help plus
    every selectable subcommand were requested. Used by the static validator to
    prove the probe's entire command surface is read-only and allowlisted.
    """
    cmds = [["sw_vers"]]
    for pm in ("conda", "mamba", "micromamba", "pip", "pip3"):
        cmds.append([pm, "--version"])
    cmds.append(["nvidia-smi", "-L"])
    cmds.append(["nvidia-smi"] + NVIDIA_QUERY)
    cmds.append(["cryodrgn", "--version"])
    cmds.append(["cryodrgn", "-h"])
    cmds.append(["cryodrgn_utils", "-h"])
    for c in MAIN_COMMANDS:
        cmds.append(["cryodrgn", c, "-h"])
    for c in UTIL_COMMANDS:
        cmds.append(["cryodrgn_utils", c, "-h"])
    return cmds


# --- Redaction ----------------------------------------------------------------
def _redactor():
    home = os.path.expanduser("~")
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""

    def redact(text):
        if text is None:
            return None
        out = str(text)
        if home and home not in ("", "/"):
            out = out.replace(home, "~")
        if user and len(user) >= 3:
            out = out.replace("/Users/" + user, "~").replace("/home/" + user, "~")
        return out

    return redact


REDACT = _redactor()


# --- Safe subprocess wrapper --------------------------------------------------
def _run(argv, timeout):
    """Run an allowlisted read-only command; return (rc, stdout, stderr).

    Raises PermissionError if the command is not on the allowlist. Never raises
    on command failure/timeout; those are returned as a non-zero rc so the probe
    can degrade gracefully.
    """
    if not _is_allowed(argv):
        raise PermissionError(f"probe refused non-allowlisted command: {argv!r}")
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, REDACT(proc.stdout.strip()), REDACT(proc.stderr.strip())
    except FileNotFoundError:
        return 127, "", "executable not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except OSError as exc:  # pragma: no cover - defensive
        return 1, "", f"error: {exc.__class__.__name__}"


def _which(name):
    path = shutil.which(name)
    return REDACT(path) if path else None


def _pkg_version(name):
    """cryoDRGN package version via metadata only (does NOT import the package)."""
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:
        return None


# --- Probe sections -----------------------------------------------------------
def probe_host():
    uname = platform.uname()
    return {
        "hostname": socket.gethostname(),
        "system": uname.system,
        "release": uname.release,
        "machine": uname.machine,
        "platform": platform.platform(),
        "is_linux": uname.system == "Linux",
        "is_macos": uname.system == "Darwin",
    }


def probe_macos(host, timeout):
    if not host["is_macos"] or not shutil.which("sw_vers"):
        return None
    rc, out, _ = _run(["sw_vers"], timeout)
    if rc != 0:
        return None
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info or None


def probe_python():
    v = sys.version_info
    tested = PY_TESTED_MIN <= (v.major, v.minor) <= PY_TESTED_MAX
    return {
        "executable": REDACT(sys.executable),
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "within_tested_range": tested,
        "tested_range": "3.10-3.13",
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "virtualenv": REDACT(os.environ.get("VIRTUAL_ENV")),
    }


def _clean_version(text):
    """Collapse a multi-line `--version` blob to a single clean line.

    Some managers print more than one line (e.g. `mamba --version` emits
    "mamba 1.5.1\nconda 23.7.4"); join the non-empty lines with "; " so the
    reported value never embeds a raw newline.
    """
    if not text:
        return None
    parts = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "; ".join(parts) if parts else None


def _resolve_pip(pm):
    """Prefer the active interpreter's pip over a user-site pip on PATH.

    `shutil.which("pip")` can resolve to a ~/.local user-site pip rather than
    the pip belonging to the active environment's interpreter. For `pip`/`pip3`
    we report the active interpreter's `python -m pip` location instead, when it
    exists, so the reported pip matches the environment being characterized.
    This is cosmetic: the version/path are advisory only.
    """
    if pm not in ("pip", "pip3"):
        return None
    pydir = os.path.dirname(sys.executable or "")
    if not pydir:
        return None
    for cand in (os.path.join(pydir, "pip"), os.path.join(pydir, "pip3")):
        if os.path.exists(cand):
            return REDACT(cand)
    return None


def probe_package_managers(timeout):
    out = {}
    for pm in ("conda", "mamba", "micromamba", "pip", "pip3"):
        if shutil.which(pm):
            rc, sout, _ = _run([pm, "--version"], timeout)
            # Prefer the active interpreter's pip path over a user-site pip.
            env_pip = _resolve_pip(pm)
            out[pm] = {"found": True, "path": env_pip or _which(pm),
                       "version": _clean_version(sout) if rc == 0 else None}
        else:
            out[pm] = {"found": False, "path": None, "version": None}
    return out


def probe_gpu(timeout):
    info = {
        "nvidia_smi_found": bool(shutil.which("nvidia-smi")),
        "nvidia_smi_path": _which("nvidia-smi"),
        "gpus": None,
        "query": None,
        "cuda_home": REDACT(os.environ.get("CUDA_HOME")),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "has_nvidia_gpu": False,
    }
    if info["nvidia_smi_found"]:
        rc, out, _ = _run(["nvidia-smi", "-L"], timeout)
        if rc == 0 and out:
            info["gpus"] = out
            info["has_nvidia_gpu"] = "GPU" in out
        rc2, out2, _ = _run(["nvidia-smi"] + NVIDIA_QUERY, timeout)
        if rc2 == 0 and out2:
            info["query"] = out2
    return info


def probe_cryodrgn(live_help, selected, host, timeout):
    info = {
        "cryodrgn_path": _which("cryodrgn"),
        "cryodrgn_utils_path": _which("cryodrgn_utils"),
        "package_version": _pkg_version("cryodrgn"),
        "executable_found": bool(shutil.which("cryodrgn")),
        "live_help_requested": bool(live_help),
        "live_version": None,
        "live_help_captured": [],
        "live_help_note": None,
    }
    if not info["executable_found"]:
        info["live_help_note"] = "cryodrgn executable not found; live help skipped."
        return info
    if not live_help:
        # Default: do NOT invoke cryoDRGN at all. The executable is located via
        # `which` and the version comes from package metadata; we only run
        # cryoDRGN (`--version`/`-h`) when --live-help is explicitly requested.
        info["live_help_note"] = (
            "cryodrgn found (via PATH); --live-help not requested, so cryoDRGN "
            "was not invoked. Version shown is from package metadata."
        )
        return info
    # --live-help: confirm with `--version`, then capture help-only invocations
    # (every subcommand call is terminated by -h, so no compute can run).
    rc, out, _ = _run(["cryodrgn", "--version"], timeout)
    if rc == 0 and out:
        info["live_version"] = out
    captured = []
    for argv in (["cryodrgn", "-h"], ["cryodrgn_utils", "-h"]):
        rc, out, _ = _run(argv, timeout)
        if rc == 0:
            captured.append(" ".join(argv))
    for cmd in selected:
        if cmd in MAIN_COMMANDS:
            rc, out, _ = _run(["cryodrgn", cmd, "-h"], timeout)
            if rc == 0:
                captured.append(f"cryodrgn {cmd} -h")
    info["live_help_captured"] = captured
    info["live_help_note"] = (
        "Help-only invocations captured; no compute commands were run."
    )
    return info


def determine_config_state(host, cryo, gpu, error):
    """Map findings to the capability state used by the config-first gate.

    The probe emits only blocked / partial / ready / unknown. The absent and
    stale states are determined by the skill when no current report file exists
    or it has exceeded its TTL.
    """
    reasons = []
    if error:
        return "unknown", [f"probe error: {error}"]
    if not cryo["executable_found"] and not cryo["package_version"]:
        reasons.append("cryoDRGN is not installed (no executable, no package metadata).")
        # Reinforce with general, sourced platform facts (per-host, not a verdict
        # hardcoded for any one machine).
        if not host["is_linux"]:
            reasons.append(
                f"host OS is {host['system']}, not Linux; cryoDRGN ships the "
                "classifier 'Operating System :: POSIX :: Linux' (pyproject.toml) "
                "and its install docs require a Linux workstation/cluster.")
        if not gpu["has_nvidia_gpu"]:
            reasons.append("no NVIDIA GPU visible (nvidia-smi).")
        return "blocked", reasons
    # cryoDRGN appears installed.
    if not host["is_linux"]:
        reasons.append(
            f"host OS is {host['system']}, not Linux; cryoDRGN targets Linux + "
            "NVIDIA GPUs (pyproject classifier 'Operating System :: POSIX :: "
            "Linux'; install docs require a Linux workstation/cluster), so this "
            "host does not meet the documented compute requirements.")
        return "blocked", reasons
    if not gpu["has_nvidia_gpu"]:
        reasons.append("no NVIDIA GPU visible; cryoDRGN training/reconstruction "
                       "requires NVIDIA GPUs (per the install docs).")
        return "blocked", reasons
    if not cryo["live_help_captured"]:
        reasons.append("cryoDRGN installed on Linux + NVIDIA GPU, but live CLI "
                       "help was not captured (run with --live-help) and "
                       "scheduler/project details are not yet known.")
        return "partial", reasons
    reasons.append("cryoDRGN installed; Linux + NVIDIA GPU detected; live help captured.")
    return "ready", reasons


def build_report(args):
    now = datetime.now(timezone.utc)
    error = None
    try:
        host = probe_host()
        macos = probe_macos(host, args.timeout)
        py = probe_python()
        pms = probe_package_managers(args.timeout)
        gpu = probe_gpu(args.timeout)
        selected = (args.selected_help.split(",") if args.selected_help
                    else DEFAULT_SELECTED_HELP)
        selected = [s.strip() for s in selected if s.strip()]
        cryo = probe_cryodrgn(args.live_help, selected, host, args.timeout)
    except PermissionError as exc:
        error = str(exc)
        host = macos = py = pms = gpu = cryo = None

    state, reasons = determine_config_state(
        host or {}, cryo or {"executable_found": False, "package_version": None,
                             "live_help_captured": []},
        gpu or {"has_nvidia_gpu": False}, error)

    # Cosmetic metadata only; `config_state` is the authoritative gate.
    # Mark the current host as a target runtime only after it has the minimum
    # Linux + NVIDIA + installed-cryodrgn facts needed to be partial/ready.
    if error or not host:
        is_target_runtime = None
    else:
        is_target_runtime = bool(host.get("is_linux") and state in {"partial", "ready"})

    ttl = int(args.stale_after_days)
    return {
        "report": "cryodrgn-skill site config",
        "schema_version": "1",
        "probe_version": __probe_version__,
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ttl_days": ttl,
        "valid_until_utc": (now + timedelta(days=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_cryodrgn_version": TARGET_CRYODRGN_VERSION,
        "target_commit": TARGET_COMMIT,
        "config_state": state,
        "config_state_reasons": reasons,
        "is_target_runtime": is_target_runtime,
        "error": error,
        "host": host,
        "macos": macos,
        "python": py,
        "package_managers": pms,
        "gpu": gpu,
        "cryodrgn": cryo,
        "staleness_triggers": [
            "OS / host change",
            "GPU / driver / CUDA change",
            "Python / conda environment change",
            "cryoDRGN executable path or version change",
            "user states the target server changed",
        ],
        "notes": [
            "Read-only probe. No installs, downloads, network calls, or "
            "cryoDRGN jobs were performed.",
            "Home directory redacted to ~ in path-like fields.",
            "absent/stale config states are determined by the skill (missing or "
            "expired report), not by this probe.",
        ],
    }


# --- Rendering ----------------------------------------------------------------
def _yn(v):
    return "yes" if v else "no"


def _fmt(v):
    return "—" if v in (None, "", []) else str(v)


def render_markdown(d):
    L = []
    A = L.append
    A(f"# {d['report']} (local / private)")
    A("")
    A("> Generated by `scripts/cryodrgn_env_probe.py`. **Local/private** — do "
      "not commit, upload, or share. Read-only snapshot for the config-first "
      "gate; see `references/02_config_session_and_environment.md`.")
    A("")
    A("## Status")
    A("")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| config_state | **{d['config_state']}** |")
    A(f"| generated (UTC) | {d['generated_utc']} |")
    A(f"| valid until (UTC) | {d['valid_until_utc']} (TTL {d['ttl_days']} days) |")
    A(f"| probe version | {d['probe_version']} |")
    A(f"| target cryoDRGN | {d['target_cryodrgn_version']} (commit "
      f"{d['target_commit'][:12]}…) |")
    A(f"| is target runtime | {_fmt(d['is_target_runtime'])} |")
    A(f"| probe error | {_fmt(d['error'])} |")
    A("")
    A("**config_state rationale:**")
    A("")
    for r in d["config_state_reasons"]:
        A(f"- {r}")
    A("")
    host = d["host"] or {}
    A("## Host")
    A("")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| hostname | {_fmt(host.get('hostname'))} |")
    A(f"| system | {_fmt(host.get('system'))} |")
    A(f"| release | {_fmt(host.get('release'))} |")
    A(f"| machine (arch) | {_fmt(host.get('machine'))} |")
    A(f"| platform | {_fmt(host.get('platform'))} |")
    A(f"| is Linux | {_yn(host.get('is_linux'))} |")
    if d.get("macos"):
        A(f"| macOS | {d['macos'].get('ProductName', '')} "
          f"{d['macos'].get('ProductVersion', '')} "
          f"({d['macos'].get('BuildVersion', '')}) |")
    A("")
    py = d["python"] or {}
    A("## Python")
    A("")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| version | {_fmt(py.get('version'))} |")
    A(f"| within tested range ({_fmt(py.get('tested_range'))}) | "
      f"{_yn(py.get('within_tested_range'))} |")
    A(f"| implementation | {_fmt(py.get('implementation'))} |")
    A(f"| executable | {_fmt(py.get('executable'))} |")
    A(f"| conda env | {_fmt(py.get('conda_env'))} |")
    A(f"| virtualenv | {_fmt(py.get('virtualenv'))} |")
    A("")
    A("## Package managers")
    A("")
    A("| Tool | Found | Version |")
    A("|---|---|---|")
    for pm, info in (d["package_managers"] or {}).items():
        A(f"| {pm} | {_yn(info['found'])} | {_fmt(info['version'])} |")
    A("")
    gpu = d["gpu"] or {}
    A("## GPU / CUDA")
    A("")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| nvidia-smi found | {_yn(gpu.get('nvidia_smi_found'))} |")
    A(f"| NVIDIA GPU visible | {_yn(gpu.get('has_nvidia_gpu'))} |")
    A(f"| GPUs | {_fmt(gpu.get('gpus'))} |")
    A(f"| query | {_fmt(gpu.get('query'))} |")
    A(f"| CUDA_HOME | {_fmt(gpu.get('cuda_home'))} |")
    A(f"| CUDA_VISIBLE_DEVICES | {_fmt(gpu.get('cuda_visible_devices'))} |")
    A("")
    cryo = d["cryodrgn"] or {}
    A("## cryoDRGN")
    A("")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| executable found | {_yn(cryo.get('executable_found'))} |")
    A(f"| cryodrgn path | {_fmt(cryo.get('cryodrgn_path'))} |")
    A(f"| cryodrgn_utils path | {_fmt(cryo.get('cryodrgn_utils_path'))} |")
    A(f"| package version (metadata) | {_fmt(cryo.get('package_version'))} |")
    A(f"| live --version | {_fmt(cryo.get('live_version'))} |")
    A(f"| live help captured | {_fmt(cryo.get('live_help_captured'))} |")
    A(f"| note | {_fmt(cryo.get('live_help_note'))} |")
    A("")
    A("## Staleness triggers (re-run the probe if any change)")
    A("")
    for t in d["staleness_triggers"]:
        A(f"- {t}")
    A("")
    A("## Notes")
    A("")
    for n in d["notes"]:
        A(f"- {n}")
    A("")
    return "\n".join(L)


# --- CLI ----------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="cryodrgn_env_probe.py",
        description="Read-only cryoDRGN environment probe (config-first session). "
                    "Runs only allowlisted presence/version/help commands; never "
                    "installs, downloads, makes network calls, or runs cryoDRGN jobs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--format", choices=["markdown", "json"], default="markdown",
                   help="Output format (default: markdown).")
    p.add_argument("--output", metavar="PATH", default=None,
                   help="Write report to PATH instead of stdout (the only file "
                        "this probe writes).")
    p.add_argument("--live-help", action="store_true",
                   help="If a cryodrgn executable is found, also capture "
                        "`cryodrgn --version`/`-h`, selected `cryodrgn <cmd> -h`, "
                        "and `cryodrgn_utils -h` (help-only, never compute).")
    p.add_argument("--selected-help", metavar="CMD[,CMD...]", default=None,
                   help="Comma-separated cryodrgn subcommands whose -h to capture "
                        "with --live-help (default: a small safe set).")
    p.add_argument("--stale-after-days", metavar="N", type=int, default=14,
                   help="TTL in days recorded in the report (default: 14).")
    p.add_argument("--timeout", metavar="SECONDS", type=int, default=60,
                   help="Per-command subprocess timeout (default: 60).")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = build_report(args)
    text = (json.dumps(report, indent=2) if args.format == "json"
            else render_markdown(report))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + ("\n" if not text.endswith("\n") else ""))
        sys.stderr.write(
            f"[cryodrgn_env_probe] wrote {args.format} report to {args.output} "
            f"(config_state={report['config_state']})\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
