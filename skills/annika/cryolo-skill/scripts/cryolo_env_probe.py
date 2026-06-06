#!/usr/bin/env python3
"""cryolo_env_probe.py - read-only environment/config probe for the cryolo-skill.

Config-first. This script ONLY inspects the local machine and writes a single
requested output file. The skill that consumes this report MAY emit concrete
commands and (after explicit user confirmation) run real crYOLO jobs on a host
whose probe verdict is "supported"/"partial"; this probe itself, however, never
runs a job. By construction it:

  * performs NO installs (never calls pip/conda/mamba/micromamba to add anything),
  * performs NO downloads and makes NO network calls,
  * NEVER starts crYOLO training / prediction / evaluation / GUI / napari / any job,
  * NEVER enumerates or reads user micrograph / annotation / model data,
  * only discovers executables, reads installed-package metadata, and (opt-in)
    runs `--version` on already-installed crYOLO scripts with a timeout,
  * runs `nvidia-smi -L` (a read-only GPU listing) unless told not to,
  * reads only a small allowlist of environment variables, never the full env,
  * redacts the user's home directory from path-like values in its output.

Support-status interpretation: official installation requirements govern whether a
configuration is *supported*. A crYOLO script that merely runs locally is reported
as "locally runnable but officially unsupported/untested", never promoted to
"supported". See references/02_config_session_and_environment.md for the schema and
the support-assessment decision rules, and references/07_safety_license_privacy.md
for how to treat the generated report (local/private; do not upload).

Source pin for the embedded support rules: crYOLO docs cryolo.readthedocs.io/en/stable
(MPI-Dortmund/cryolo tag 1.9.9 / commit 30039bde34d65c179541568b0c27f09916ac5652),
installation page fetched 2026-06-05. crYOLO 1.9.9 is INSTALLED and VALIDATED on a
Linux + NVIDIA GPU host - see the captured live --help (incl. _versions.txt) and the GPU
smoke run from the validation run (crYOLO section). This script makes NO factual
claim beyond what that captured source and the per-host probe results support.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Constants / allowlists
# --------------------------------------------------------------------------- #

PROBE_VERSION = "0.1.0"

DOCS_URL = "https://cryolo.readthedocs.io/en/stable/"
DOCS_INSTALL_URL = "https://cryolo.readthedocs.io/en/stable/installation.html"
DOCS_SOURCE_COMMIT = "30039bde34d65c179541568b0c27f09916ac5652"
DOCS_SOURCE_TAG = "1.9.9"
GROUNDED_ON = "2026-06-05"
INSTALL_SOURCE = (
    "crYOLO installation docs, %s (fetched %s)" % (DOCS_INSTALL_URL, GROUNDED_ON)
)

# crYOLO-related executables we are allowed to *discover* on PATH. We never invoke
# anything outside this allowlist, and even these only ever with `--version`.
# All names below were confirmed present on the validated install (captured help:
# _versions.txt "which scripts" list).
CRYOLO_EXES = [
    "cryolo_gui.py",
    "cryolo_predict.py",
    "cryolo_train.py",
    "cryolo_evaluation.py",
    "cryolo_evaluation_tomo.py",
    "cryolo_boxmanager_tools.py",
    "cryolo_boxmanager_legacy.py",
    "janni_denoise.py",
    "napari_boxmanager",
]

# Package distributions whose *metadata* (not the package itself) we may read.
# importlib.metadata reads on-disk metadata; it does NOT import the package and so
# does not load TensorFlow or touch the GPU.
CRYOLO_PACKAGES = [
    "cryolo",
    "cryoloBM",
    "napari-boxmanager",
    "tensorflow",
    "tensorflow-gpu",
]

# Exactly the environment variables we are allowed to read. Never the whole env.
ENV_ALLOWLIST = [
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "VIRTUAL_ENV",
    "CUDA_HOME",
    "CUDA_PATH",
    "CUDA_VISIBLE_DEVICES",
    "LD_LIBRARY_PATH",
    "CUDNN_PATH",
]

DEFAULT_STALE_AFTER_DAYS = 14
SUBPROCESS_TIMEOUT_GPU = 15
SUBPROCESS_TIMEOUT_CRYOLO = 60

# Audit trail of every external command this run attempted (see no-install proof).
COMMANDS_RUN: list[dict] = []

_HOME = os.path.expanduser("~")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def redact(value):
    """Redact the user's home dir and user path segments from a string value."""
    if value is None:
        return None
    s = str(value)
    if _HOME and _HOME != os.sep and _HOME in s:
        s = s.replace(_HOME, "~")
    s = re.sub(r"/Users/[^/:\s]+", "/Users/<user>", s)
    s = re.sub(r"/home/[^/:\s]+", "/home/<user>", s)
    return s


def run_cmd(args, timeout):
    """Run an allowlisted external command read-only, with a timeout.

    Returns a dict and appends a one-line record to COMMANDS_RUN. Never uses a
    shell. If the executable is not found, nothing is executed.
    """
    name = args[0]
    resolved = name if os.path.isabs(name) and os.path.exists(name) else shutil.which(name)
    record = {"cmd": redact(" ".join(args)), "status": None, "returncode": None}
    if not resolved:
        record["status"] = "not_found"
        COMMANDS_RUN.append(record)
        return {"ran": False, "status": "not_found", "returncode": None, "stdout": "", "stderr": ""}
    try:
        proc = subprocess.run(  # noqa: S603 - allowlisted, no shell, timeout-bounded
            [resolved] + list(args[1:]),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        record["status"] = "ok"
        record["returncode"] = proc.returncode
        COMMANDS_RUN.append(record)
        return {
            "ran": True,
            "status": "ok",
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired:
        record["status"] = "timeout"
        COMMANDS_RUN.append(record)
        return {"ran": True, "status": "timeout", "returncode": None, "stdout": "", "stderr": ""}
    except Exception as exc:  # pragma: no cover - defensive
        record["status"] = "error"
        COMMANDS_RUN.append(record)
        return {"ran": True, "status": "error", "returncode": None, "stdout": "", "stderr": str(exc)}


def _truncate(text, limit=2000):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


# --------------------------------------------------------------------------- #
# Detection steps (all read-only)
# --------------------------------------------------------------------------- #

def detect_os():
    system = platform.system()
    machine = platform.machine()
    is_macos = system == "Darwin"
    is_apple_silicon = is_macos and machine.lower() in ("arm64", "aarch64")
    release = platform.release()
    if is_macos:
        mac_ver = platform.mac_ver()[0]
        if mac_ver:
            release = "macOS %s (Darwin %s)" % (mac_ver, release)
    return {
        "system": system,
        "release": release,
        "machine": machine,
        "is_macos": is_macos,
        "is_apple_silicon": is_apple_silicon,
    }


def detect_python():
    active_env = os.environ.get("CONDA_DEFAULT_ENV")
    if not active_env and os.environ.get("VIRTUAL_ENV"):
        active_env = os.path.basename(os.environ["VIRTUAL_ENV"])
    return {
        "executable": redact(sys.executable),
        "version": platform.python_version(),
        "active_env": active_env,
    }


def detect_package_managers():
    result = {}
    for name in ("conda", "mamba", "micromamba", "pip"):
        path = shutil.which(name)
        result[name] = {"available": path is not None, "path": redact(path)}
    return result


def detect_executables(exe_overrides):
    result = {}
    for name in CRYOLO_EXES:
        override = exe_overrides.get(name)
        path = override if override else shutil.which(name)
        result[name] = {"found": path is not None, "path": redact(path)}
    return result


def detect_packages():
    try:
        from importlib import metadata as importlib_metadata
    except Exception:  # pragma: no cover - very old Python
        return {name: None for name in CRYOLO_PACKAGES}
    versions = {}
    for name in CRYOLO_PACKAGES:
        try:
            versions[name] = importlib_metadata.version(name)
        except Exception:
            versions[name] = None
    return versions


def detect_gpu(do_gpu_probe):
    info = {"nvidia_smi": "missing", "nvidia_gpus": [], "cuda_home": redact(os.environ.get("CUDA_HOME"))}
    if not do_gpu_probe:
        info["nvidia_smi"] = "skipped"
        COMMANDS_RUN.append({"cmd": "nvidia-smi -L", "status": "skipped", "returncode": None})
        return info
    res = run_cmd(["nvidia-smi", "-L"], timeout=SUBPROCESS_TIMEOUT_GPU)
    if res["status"] == "not_found":
        info["nvidia_smi"] = "missing"
    elif res["status"] == "ok" and res["returncode"] == 0:
        info["nvidia_smi"] = "present"
        info["nvidia_gpus"] = [ln.strip() for ln in res["stdout"].splitlines() if ln.strip().startswith("GPU")]
    else:
        info["nvidia_smi"] = "error"
    return info


def detect_cryolo(executables, packages, cryolo_exec, exe_overrides):
    installed = any(v["found"] for v in executables.values()) or any(
        packages.get(p) for p in ("cryolo", "cryoloBM")
    )
    detected_version = packages.get("cryolo")
    help_captured = False
    version_probes = {}
    if cryolo_exec:
        for name in ("cryolo_predict.py", "cryolo_gui.py"):
            entry = executables.get(name, {})
            if not entry.get("found"):
                continue
            target = exe_overrides.get(name) or name
            res = run_cmd([target, "--version"], timeout=SUBPROCESS_TIMEOUT_CRYOLO)
            version_probes[name] = {
                "status": res["status"],
                "returncode": res["returncode"],
                "output": redact(_truncate((res["stdout"] + "\n" + res["stderr"]).strip(), 400)),
            }
            if res["status"] == "ok" and res["returncode"] == 0:
                help_captured = True
                if not detected_version:
                    m = re.search(r"(\d+\.\d+\.\d+)", (res["stdout"] + res["stderr"]))
                    if m:
                        detected_version = m.group(1)
    return {
        "installed": bool(installed),
        "executable_paths": {k: v["path"] for k, v in executables.items() if v["found"]},
        "package_versions": {k: v for k, v in packages.items() if v},
        "help_captured": help_captured,
        "detected_version": detected_version,
        "version_probes": version_probes,
    }


def collect_env():
    env = {}
    for key in ENV_ALLOWLIST:
        if key in os.environ:
            env[key] = redact(os.environ[key])
    return env


def assess_support(os_info, gpu_info, cryolo_info):
    """Map detected facts -> support status. Every reason cites a source.

    Rules are grounded ONLY in the captured installation docs (see INSTALL_SOURCE):
      * macOS              -> blocked  (docs: crYOLO does not support macOS)
      * Linux + NVIDIA GPU -> supported (matches docs: Ubuntu/CentOS + NVIDIA + CUDA)
      * Linux, no NVIDIA   -> partial   (docs list NVIDIA GPUs + CUDA/cuDNN)
      * Windows            -> partial   (docs: untested, "should run")
      * other / unknown    -> unknown   (not covered by captured docs)
    """
    system = os_info["system"]
    machine = os_info["machine"]
    nvidia_present = gpu_info["nvidia_smi"] == "present" and bool(gpu_info["nvidia_gpus"])
    reasons = []
    blocked = []

    if os_info["is_macos"]:
        status = "blocked"
        reasons.append(
            "macOS detected (%s). Official docs: 'As the GPU accelerated version of "
            "tensorflow does not support MacOS, crYOLO does not support it either.' [%s]"
            % (machine, INSTALL_SOURCE)
        )
        if os_info["is_apple_silicon"]:
            reasons.append(
                "Apple Silicon (arm64): Apple GPU / Metal / MPS is not NVIDIA CUDA and "
                "does not satisfy crYOLO's stated CUDA Toolkit + cuDNN dependency. [%s]"
                % INSTALL_SOURCE
            )
        blocked = [
            "crYOLO config/train/predict/evaluation/GUI execution (officially unsupported on macOS)"
        ]
    elif system == "Linux":
        if nvidia_present:
            status = "supported"
            reasons.append(
                "Linux with NVIDIA GPU(s) detected via nvidia-smi: matches the official "
                "supported class (Linux + NVIDIA GPU + CUDA/cuDNN). crYOLO 1.9.9 was "
                "INSTALLED and validated END-TO-END on this class (a Linux + NVIDIA GPU "
                "host; crYOLO's docs list the RTX 2080 Ti among officially-tested GPUs). "
                "NOTE: the docs' specifically tested OSes are a fixed set; verify your exact "
                "distro/GPU against the docs rather than assuming parity. [%s]"
                % INSTALL_SOURCE
            )
        else:
            status = "partial"
            reasons.append(
                "Linux detected but no NVIDIA GPU found via nvidia-smi. Official docs list "
                "NVIDIA GPUs and a CUDA Toolkit + cuDNN dependency; GPU-accelerated "
                "workflows may be unavailable. [%s]" % INSTALL_SOURCE
            )
            blocked = ["GPU-accelerated train/predict/evaluation (no NVIDIA GPU detected)"]
    elif system == "Windows":
        status = "partial"
        reasons.append(
            "Windows detected. Official docs: 'We don't test it but it should run on "
            "Windows as well.' Treat as untested. [%s]" % INSTALL_SOURCE
        )
        blocked = ["Officially untested platform (Windows) per docs"]
    else:
        status = "unknown"
        reasons.append(
            "Unrecognized OS '%s'; not covered by captured official docs. [%s]"
            % (system, INSTALL_SOURCE)
        )
        blocked = ["Platform not covered by captured docs"]

    if not cryolo_info["installed"]:
        reasons.append(
            "No crYOLO executables on PATH and no crYOLO package metadata found: "
            "installation is required before any use. This skill does not install software."
        )
    elif os_info["is_macos"]:
        reasons.append(
            "NOTE: a crYOLO-related executable/package appears present locally, but per the "
            "trust ladder this is reported as 'locally present/runnable but officially "
            "unsupported/untested on macOS', NOT as supported."
        )

    return {"status": status, "reasons": reasons, "blocked_capabilities": blocked}


# --------------------------------------------------------------------------- #
# Report assembly + rendering
# --------------------------------------------------------------------------- #

def build_report(args):
    exe_overrides = parse_exe_overrides(args.exe_path)
    os_info = detect_os()
    python_info = detect_python()
    pkg_mgrs = detect_package_managers()
    executables = detect_executables(exe_overrides)
    packages = detect_packages()
    gpu_info = detect_gpu(do_gpu_probe=not args.no_gpu_probe)
    cryolo_info = detect_cryolo(executables, packages, cryolo_exec=args.cryolo_exec, exe_overrides=exe_overrides)
    support = assess_support(os_info, gpu_info, cryolo_info)

    validation_status = "full" if (cryolo_info["installed"] and cryolo_info["help_captured"]) else "partial"

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "probe_version": PROBE_VERSION,
        "hostname": platform.node() or "unknown",
        "os": os_info,
        "python": python_info,
        "package_managers": pkg_mgrs,
        "gpu": gpu_info,
        "cryolo": cryolo_info,
        "environment_variables": collect_env(),
        "support_assessment": support,
        "source_snapshot": {
            "docs_url": DOCS_URL,
            "docs_source_commit": DOCS_SOURCE_COMMIT,
            "docs_source_tag": DOCS_SOURCE_TAG,
            "grounded_on": GROUNDED_ON,
        },
        "validation_status": validation_status,
        "stale_after_days": args.stale_after_days,
        "safety_attestation": {
            "installs_performed": "none",
            "downloads_performed": "none",
            "network_calls": "none",
            "cryolo_jobs_run": "none",
            "cryolo_exec_enabled": bool(args.cryolo_exec),
            "commands_run": COMMANDS_RUN,
        },
    }
    return report


def parse_exe_overrides(pairs):
    """Parse --exe-path name=path entries. Only allowlisted names are accepted."""
    overrides = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit("ERROR: --exe-path expects NAME=PATH, got %r" % item)
        name, path = item.split("=", 1)
        if name not in CRYOLO_EXES:
            raise SystemExit(
                "ERROR: --exe-path name %r not in allowlist %s" % (name, CRYOLO_EXES)
            )
        if not os.path.exists(path):
            raise SystemExit("ERROR: --exe-path path does not exist: %s" % path)
        # Tighten P2-1: the override must actually point at the named script, so a
        # name cannot be aimed at an unrelated binary (e.g. cryolo_predict.py=/bin/rm).
        if os.path.basename(path) != name:
            raise SystemExit(
                "ERROR: --exe-path path basename must equal %r (got %r)"
                % (name, os.path.basename(path))
            )
        overrides[name] = path
    return overrides


def render_json(report):
    return json.dumps(report, indent=2, sort_keys=False)


def _yesno(b):
    return "yes" if b else "no"


def render_markdown(report):
    os_i = report["os"]
    py = report["python"]
    gpu = report["gpu"]
    cry = report["cryolo"]
    sup = report["support_assessment"]
    lines = []
    a = lines.append
    a("# crYOLO local site config (generated)")
    a("")
    a("> LOCAL / PRIVATE. Generated by `scripts/cryolo_env_probe.py` v%s." % report["probe_version"])
    a("> Contains host/env details; do not upload or commit. See "
      "`references/07_safety_license_privacy.md`.")
    a("")
    a("- generated_at: %s" % report["generated_at"])
    a("- hostname: %s" % report["hostname"])
    a("- validation_status: %s" % report["validation_status"])
    a("- stale_after_days: %s" % report["stale_after_days"])
    a("")
    a("## Support assessment")
    a("")
    a("- status: **%s**" % sup["status"])
    a("- reasons:")
    for r in sup["reasons"]:
        a("  - %s" % r)
    if sup["blocked_capabilities"]:
        a("- blocked_capabilities:")
        for b in sup["blocked_capabilities"]:
            a("  - %s" % b)
    else:
        a("- blocked_capabilities: (none recorded)")
    a("")
    a("## Operating system")
    a("")
    a("- system: %s" % os_i["system"])
    a("- release: %s" % os_i["release"])
    a("- machine: %s" % os_i["machine"])
    a("- is_macos: %s" % _yesno(os_i["is_macos"]))
    a("- is_apple_silicon: %s" % _yesno(os_i["is_apple_silicon"]))
    a("")
    a("## Python")
    a("")
    a("- executable: %s" % py["executable"])
    a("- version: %s" % py["version"])
    a("- active_env: %s" % (py["active_env"] or "(none)"))
    a("")
    a("## Package managers")
    a("")
    for name, info in report["package_managers"].items():
        a("- %s: %s%s" % (name, _yesno(info["available"]),
                          (" (%s)" % info["path"]) if info["path"] else ""))
    a("")
    a("## GPU")
    a("")
    a("- nvidia_smi: %s" % gpu["nvidia_smi"])
    if gpu["nvidia_gpus"]:
        for g in gpu["nvidia_gpus"]:
            a("  - %s" % g)
    a("- cuda_home: %s" % (gpu["cuda_home"] or "(unset)"))
    a("")
    a("## crYOLO")
    a("")
    a("- installed (detected): %s" % _yesno(cry["installed"]))
    a("- detected_version: %s" % (cry["detected_version"] or "(unknown)"))
    a("- help/version captured: %s" % _yesno(cry["help_captured"]))
    if cry["executable_paths"]:
        a("- executable_paths:")
        for k, v in cry["executable_paths"].items():
            a("  - %s: %s" % (k, v))
    else:
        a("- executable_paths: (none found on PATH)")
    if cry["package_versions"]:
        a("- package_versions:")
        for k, v in cry["package_versions"].items():
            a("  - %s: %s" % (k, v))
    else:
        a("- package_versions: (none found)")
    a("")
    a("## Environment variables (allowlisted only)")
    a("")
    if report["environment_variables"]:
        for k, v in report["environment_variables"].items():
            a("- %s: %s" % (k, v))
    else:
        a("- (none of the allowlisted variables are set)")
    a("")
    a("## Source snapshot")
    a("")
    snap = report["source_snapshot"]
    a("- docs_url: %s" % snap["docs_url"])
    a("- docs_source_commit: %s" % snap["docs_source_commit"])
    a("- docs_source_tag: %s" % snap["docs_source_tag"])
    a("- grounded_on: %s" % snap["grounded_on"])
    a("")
    a("## Safety attestation")
    a("")
    att = report["safety_attestation"]
    a("- installs_performed: %s" % att["installs_performed"])
    a("- downloads_performed: %s" % att["downloads_performed"])
    a("- network_calls: %s" % att["network_calls"])
    a("- cryolo_jobs_run: %s" % att["cryolo_jobs_run"])
    a("- cryolo_exec_enabled: %s" % _yesno(att["cryolo_exec_enabled"]))
    a("- external commands attempted:")
    for c in att["commands_run"]:
        rc = "" if c["returncode"] is None else " (rc=%s)" % c["returncode"]
        a("  - `%s` -> %s%s" % (c["cmd"], c["status"], rc))
    a("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="cryolo_env_probe.py",
        description=(
            "Read-only crYOLO environment/config probe. Inspects this machine and "
            "writes one report file. Performs NO installs, NO downloads, NO network "
            "calls, and this probe never runs crYOLO jobs/GUI. (The skill that consumes "
            "the report may run real jobs after explicit user confirmation on a "
            "supported host.) See references/02_config_session_and_environment.md."
        ),
        epilog=(
            "Safety: by default this probe does NOT execute crYOLO scripts (importing "
            "TensorFlow is heavyweight and may touch the GPU). Pass --cryolo-exec to "
            "opt into a timeout-bounded `--version` probe of already-installed scripts."
        ),
    )
    p.add_argument("--output", "-o", default=None,
                   help="Write the report to this path (default: stdout). The only file written.")
    p.add_argument("--format", "-f", choices=("markdown", "json"), default="markdown",
                   help="Output format (default: markdown).")
    p.add_argument("--cryolo-exec", action="store_true",
                   help="Opt in to running `--version` on discovered crYOLO scripts (timeout-bounded).")
    p.add_argument("--no-cryolo-exec", action="store_true",
                   help="Explicitly disable crYOLO script execution (this is the default).")
    p.add_argument("--no-gpu-probe", action="store_true",
                   help="Skip the read-only `nvidia-smi -L` GPU listing.")
    p.add_argument("--exe-path", action="append", metavar="NAME=PATH", default=[],
                   help=("Override discovery of an allowlisted crYOLO script (NAME must be one "
                         "of: %s). Only ever invoked with --version, only under --cryolo-exec." %
                         ", ".join(CRYOLO_EXES)))
    p.add_argument("--stale-after-days", type=int, default=DEFAULT_STALE_AFTER_DAYS,
                   help="Days before this report should be treated as stale (default: %d)." %
                        DEFAULT_STALE_AFTER_DAYS)
    p.add_argument("--probe-version", action="version", version="cryolo_env_probe.py %s" % PROBE_VERSION)
    return p


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Safety: --no-cryolo-exec always wins over --cryolo-exec.
    if args.no_cryolo_exec:
        args.cryolo_exec = False

    report = build_report(args)
    rendered = render_json(report) if args.format == "json" else render_markdown(report)

    if args.output:
        out_path = os.path.abspath(args.output)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(rendered)
            if not rendered.endswith("\n"):
                fh.write("\n")
        sys.stderr.write("Wrote %s report to %s\n" % (args.format, redact(out_path)))
    else:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
