#!/usr/bin/env python3
"""Read-only ModelAngelo install-readiness / config probe.

Gathers the facts needed to decide whether a target host can install and run
ModelAngelo (3dem/model-angelo), and emits a config report (JSON or Markdown)
plus a readiness ``state`` computed from the state machine in
``references/02_config_session_and_environment.md``.

Design contract (binding):
  * stdlib only (portable across Claude and Codex harnesses).
  * The DEFAULT run performs NO heavyweight or side-effecting action: no install,
    no ``git clone``, no ``pip``/``conda`` mutation, no weight download, no
    ``torch`` import, no network, no directory creation, no ``chmod``. It only
    reads ``platform``/``socket``, looks up executables on PATH, runs read-only
    ``nvidia-smi``/``conda env list``/``conda info`` if present, reads
    ``importlib.metadata`` for an installed model_angelo, computes the would-be
    weight-cache dir, and ``stat``s it for existing weights + free disk.
  * The home directory path is redacted from all emitted output.
  * This script never creates directories. ``--output`` must point into an
    already-existing directory (intended: ``configs/``).

Allowlisted optional live call (opt-in only):
  * ``--torch-probe`` -> import torch in an isolated child process to report
    version + cuda.is_available() + device names, with a hard timeout.

Forbidden here (never invoked): ``install_script.sh``, ``git clone``,
``pip``/``conda install``, ``model_angelo setup_weights`` / any download,
``chmod``, scheduler submission.
"""

import argparse
import datetime
import importlib.metadata as ilmd
import json
import os
import platform
import shutil
import socket
import subprocess
import sys

PROBE_VERSION = "0.1.0"
SCHEMA_VERSION = "0.1.0"
SOURCE_BASIS_COMMIT = "994945bdfa6e5368e0d62349a47792f4864eebc3"
SOURCE_BASIS_NOTE = (
    "3dem/model-angelo tag v1.0.18. Install/weights/CLI facts derived from pinned "
    "source. Live installed `model_angelo --version` and the installed "
    "install_script.sh on the target win for that machine."
)

# Disk needed for the weight cache (ESM-1b ~7 GB + two bundles ~ >10 GB total).
WEIGHTS_MIN_FREE_GB = 12.0
# Recommended minimum GPU memory (README: >=8 GB, 2080-class+).
GPU_MIN_GB = 8.0

DEFAULT_ENV_NAME = "model_angelo"
PACKAGE_NAME_CANDIDATES = ("model_angelo", "model-angelo")
EXCERPT_LIMIT = 600
HOME = os.path.expanduser("~")


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def redact(value):
    """Replace the user's home directory prefix with ``~`` in any string."""
    if value is None or not isinstance(value, str):
        return value
    return value.replace(HOME, "~") if HOME and HOME in value else value


# --------------------------------------------------------------------------- #
# Safe subprocess helper (hard timeout, captured exit code/stdout/stderr)
# --------------------------------------------------------------------------- #
def run_subprocess(argv, timeout, extra_env=None, capture_full=False):
    """Run a read-only command with a hard timeout; never raise."""
    result = {
        "ran": False, "exit_code": None, "timed_out": False,
        "stdout_excerpt": None, "stderr_excerpt": None, "error": None,
    }
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, env=env, text=True,
        )
        result["ran"] = True
        result["exit_code"] = proc.returncode
        full_stdout = redact((proc.stdout or "").strip())
        result["stdout_excerpt"] = full_stdout[:EXCERPT_LIMIT]
        result["stderr_excerpt"] = redact((proc.stderr or "").strip())[:EXCERPT_LIMIT]
        if capture_full:
            result["stdout_full"] = full_stdout
    except subprocess.TimeoutExpired:
        result["ran"] = True
        result["timed_out"] = True
        result["error"] = "timeout after %ss" % timeout
    except FileNotFoundError:
        result["error"] = "executable not found"
    except Exception as exc:  # never let the probe crash on an optional call
        result["error"] = "%s: %s" % (type(exc).__name__, exc)
    return result


# --------------------------------------------------------------------------- #
# Fact collection (all read-only)
# --------------------------------------------------------------------------- #
def collect_host_identity():
    system = platform.system()
    return {
        "hostname": socket.gethostname(),
        "os_system": system,
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "is_linux": system == "Linux",
        "username_redacted": True,
    }


def collect_python():
    managers = {
        name: shutil.which(name) is not None
        for name in ("conda", "mamba", "micromamba", "pip", "pip3")
    }
    return {
        "executable": redact(sys.executable),
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "conda_env_active": bool(os.environ.get("CONDA_DEFAULT_ENV")),
        "conda_prefix_set": bool(os.environ.get("CONDA_PREFIX")),
        "virtualenv_active": bool(os.environ.get("VIRTUAL_ENV")),
        "package_managers_present": managers,
        "git_present": shutil.which("git") is not None,
        "conda_present": managers["conda"] or managers["mamba"] or managers["micromamba"],
    }


def collect_model_angelo(env_name):
    """Look for an existing install: PATH binary, package metadata, conda env."""
    info = {"executable_on_path": None, "package_found": False,
            "package_version": None, "conda_env_present": None,
            "conda_env_name_checked": env_name}
    exe = shutil.which("model_angelo")
    info["executable_on_path"] = redact(exe)
    for name in PACKAGE_NAME_CANDIDATES:
        try:
            info["package_version"] = ilmd.version(name)
            info["package_found"] = True
            break
        except ilmd.PackageNotFoundError:
            continue
        except Exception:
            break
    # Read-only conda env listing (only if conda is available). Capture the FULL
    # stdout (not the 600-char excerpt) so a same-name env that sorts late in a
    # long env list is still seen — otherwise an existing install is missed.
    if shutil.which("conda"):
        envs = run_subprocess(["conda", "env", "list"], timeout=15, capture_full=True)
        full = envs.get("stdout_full")
        if envs["ran"] and envs["exit_code"] == 0 and full:
            names = []
            for line in full.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    names.append(line.split()[0])
            info["conda_env_present"] = env_name in names
    # "installed" must include an existing same-name conda env: it may simply not
    # be on the current PATH because the env isn't activated. Missing this risks
    # treating an installed host as a fresh-install target (and clobbering it).
    info["on_path"] = bool(exe)
    info["installed"] = bool(exe) or info["package_found"] or bool(info["conda_env_present"])
    return info


def _parse_mem_to_gb(text):
    try:
        return round(float(text.strip().split()[0]) / 1024.0, 1)  # MiB -> GiB
    except Exception:
        return None


def probe_nvidia_smi():
    """Read-only GPU query (not a torch/model_angelo call)."""
    if shutil.which("nvidia-smi") is None:
        return {"present": False, "gpus": [], "gpu_count": 0, "max_mem_gb": None,
                "cuda_visible_devices_set": bool(os.environ.get("CUDA_VISIBLE_DEVICES")),
                "query": None}
    query = run_subprocess(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
         "--format=csv,noheader,nounits"], timeout=10)
    gpus, mems = [], []
    if query["ran"] and not query["timed_out"] and query["exit_code"] == 0:
        for line in (query["stdout_excerpt"] or "").splitlines():
            line = line.strip()
            if not line:
                continue
            gpus.append(line)
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gb = _parse_mem_to_gb(parts[1])
                if gb is not None:
                    mems.append(gb)
    return {
        "present": True, "gpus": gpus, "gpu_count": len(gpus),
        "max_mem_gb": max(mems) if mems else None,
        "cuda_visible_devices_set": bool(os.environ.get("CUDA_VISIBLE_DEVICES")),
        "query": query,
    }


def _torch_hub_dir(torch_home_override):
    """Compute torch.hub.get_dir() = $TORCH_HOME/hub WITHOUT importing torch."""
    th = torch_home_override or os.environ.get("TORCH_HOME")
    if th:
        root = os.path.expanduser(th)
        source = "TORCH_HOME"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        root = os.path.join(os.path.expanduser(xdg) if xdg else os.path.join(HOME, ".cache"),
                            "torch")
        source = "XDG_CACHE_HOME/torch" if xdg else "~/.cache/torch"
    return os.path.join(root, "hub"), source, th


def check_weights(torch_home_override):
    """Stat the would-be cache dir; report existing weights + free disk. No download."""
    hub_dir, source, th = _torch_hub_dir(torch_home_override)
    ckpt = os.path.join(hub_dir, "checkpoints")
    ma = os.path.join(ckpt, "model_angelo_v1.0")
    info = {
        "torch_home_set": bool(th),
        "torch_home_value": redact(os.path.expanduser(th)) if th else None,
        "cache_root_source": source,
        "hub_dir": redact(hub_dir),
        "checkpoints_dir": redact(ckpt),
        "nucleotides_present": os.path.isfile(os.path.join(ma, "nucleotides", "success.txt")),
        "nucleotides_no_seq_present": os.path.isfile(
            os.path.join(ma, "nucleotides_no_seq", "success.txt")),
        "esm_present": os.path.isfile(os.path.join(ckpt, "esm1b_t33_650M_UR50S.pt")),
        "free_gb": None,
    }
    # Free disk at the nearest existing ancestor of the cache root.
    probe_path = hub_dir
    while probe_path and not os.path.isdir(probe_path):
        parent = os.path.dirname(probe_path)
        if parent == probe_path:
            break
        probe_path = parent
    try:
        if probe_path and os.path.isdir(probe_path):
            info["free_gb"] = round(shutil.disk_usage(probe_path).free / (1024 ** 3), 1)
            info["free_measured_at"] = redact(probe_path)
    except Exception:
        pass
    info["weights_complete"] = (info["nucleotides_present"]
                                and info["nucleotides_no_seq_present"]
                                and info["esm_present"])
    return info


def collect_external():
    return {
        "hhblits_present": shutil.which("hhblits") is not None,  # optional HHblits ID path
        "module_cmd_present": shutil.which("module") is not None
        or bool(os.environ.get("MODULESHOME")),                  # HPC env modules
        "sbgrid_present": shutil.which("sbgrid-cli") is not None
        or shutil.which("sbgrid-list") is not None,
    }


# --------------------------------------------------------------------------- #
# Optional HEAVYWEIGHT probe (opt-in only, isolated subprocess + timeout)
# --------------------------------------------------------------------------- #
def probe_torch(timeout):
    """Import torch in a CHILD process. Never import inline. State in {ok,failed,timeout}."""
    child_lines = [
        "import json as _j", "_r = {}",
        "try:",
        "    import torch as _t",
        "    _r['version'] = _t.__version__",
        "    _r['cuda_available'] = bool(_t.cuda.is_available())",
        "    _r['device_count'] = int(_t.cuda.device_count()) if _t.cuda.is_available() else 0",
        "    _r['devices'] = [_t.cuda.get_device_name(i) for i in range(_r['device_count'])]",
        "    _r['hub_dir'] = _t.hub.get_dir()",
        "    _r['ok'] = True",
        "except Exception as _e:",
        "    _r['ok'] = False",
        "    _r['error'] = type(_e).__name__ + ': ' + str(_e)",
        "print(_j.dumps(_r))",
    ]
    child = run_subprocess([sys.executable, "-c", "\n".join(child_lines)],
                           timeout, capture_full=True)
    full_stdout = child.pop("stdout_full", None)
    result = {"requested": True, "state": "failed", "version": None,
              "cuda_available": None, "devices": None, "hub_dir": None, "raw": child}
    if child["timed_out"]:
        result["state"] = "timeout"
        return result
    if child["ran"] and child["exit_code"] == 0 and full_stdout:
        try:
            payload = json.loads(full_stdout)
            if payload.get("ok"):
                result["state"] = "ok"
                result["version"] = payload.get("version")
                result["cuda_available"] = payload.get("cuda_available")
                result["devices"] = payload.get("devices")
                result["hub_dir"] = redact(payload.get("hub_dir"))
            else:
                result["error"] = payload.get("error")
        except Exception:
            pass
    return result


# --------------------------------------------------------------------------- #
# State machine (references/02)
# --------------------------------------------------------------------------- #
def determine_state(facts):
    """Return (state, reasons). Fatal blockers dominate; else untested/absent
    prerequisites downgrade ready -> partial."""
    host = facts["host_identity"]
    py = facts["python"]
    ma = facts["model_angelo"]
    gpu = facts["gpu_cuda"]
    weights = facts["weights"]
    torch_state = facts["torch"].get("state", "not_run")

    if not host.get("os_system"):
        return "unknown", ["Host OS could not be determined; run the probe on the target."]

    installed = ma.get("installed")

    # ---- Fatal blocker: non-Linux and not already installed ----------------- #
    if not host.get("is_linux") and not installed:
        return "blocked", [
            "OS is %s/%s, not Linux. ModelAngelo's official route is Linux + "
            "NVIDIA/CUDA (SBGrid ships Linux-64 only; no macOS build). Use a Linux "
            "workstation, an HPC module (Biowulf/SBGrid), or a Linux container/VM "
            "with GPU passthrough." % (host.get("os_system"), host.get("machine"))]

    partials = []

    if installed:
        if ma.get("executable_on_path"):
            loc = "PATH binary"
        elif ma.get("package_found"):
            loc = "package v%s" % ma.get("package_version")
        else:
            loc = ("conda env '%s' exists but is not on the current PATH — "
                   "activate it and verify (a same-name env in another envs_dir "
                   "can be shadowed; a name-based install could clobber it)"
                   % ma.get("conda_env_name_checked"))
        reasons = ["ModelAngelo already installed: %s. Verify with "
                   "verify_modelangelo.sh; installer is idempotent if reinstalling."
                   % loc]
        if not weights.get("weights_complete"):
            reasons.append("Weights look incomplete at %s (nucleotides=%s, "
                           "nucleotides_no_seq=%s, esm=%s). Fetch with "
                           "`model_angelo setup_weights --bundle-name nucleotides` "
                           "(+ nucleotides_no_seq)." % (
                               weights.get("checkpoints_dir"),
                               weights.get("nucleotides_present"),
                               weights.get("nucleotides_no_seq_present"),
                               weights.get("esm_present")))
        if not gpu.get("present"):
            reasons.append("No NVIDIA GPU visible; building will be CPU-only "
                           "(impractical) — accept explicitly before running builds.")
        return "ready", reasons

    # ---- Not installed: assess install prerequisites ------------------------ #
    if not py.get("conda_present"):
        partials.append("No conda/mamba on PATH. Install miniconda3 first "
                        "(README) — the official installer needs conda.")
    if not py.get("git_present"):
        partials.append("`git` not found; needed to clone the repo. Install git "
                        "or use a pre-fetched repo dir.")
    if not gpu.get("present"):
        partials.append("No NVIDIA GPU detected (nvidia-smi absent). Install works, "
                        "but building is impractical on CPU — must be explicitly "
                        "accepted. Prefer a GPU host / HPC module / GPU container.")
    elif gpu.get("max_mem_gb") is not None and gpu["max_mem_gb"] < GPU_MIN_GB:
        partials.append("Largest GPU has ~%.0f GB; README recommends >=%.0f GB "
                        "(2080-class+). Small GPUs may OOM when building."
                        % (gpu["max_mem_gb"], GPU_MIN_GB))
    if weights.get("free_gb") is not None and weights["free_gb"] < WEIGHTS_MIN_FREE_GB:
        partials.append("Only ~%.0f GB free at the weight-cache target (%s); need "
                        ">~%.0f GB for weights (~10 GB) + headroom."
                        % (weights["free_gb"], weights.get("free_measured_at"),
                           WEIGHTS_MIN_FREE_GB))
    if not weights.get("torch_home_set"):
        partials.append("TORCH_HOME unset: weights would land in per-user "
                        "%s. On shared systems set TORCH_HOME to a large, "
                        "world-readable dir before downloading." % weights.get("hub_dir"))
    if torch_state in ("failed", "timeout"):
        partials.append("torch probe %s; a pre-existing torch in this env may be "
                        "broken (a fresh model_angelo env avoids this)." % torch_state)
    elif torch_state == "not_run":
        partials.append("torch/CUDA not probed (default). Pass --torch-probe on the "
                        "target to confirm the GPU path before claiming run-readiness.")

    if partials:
        return "partial", partials
    return "ready", ["Linux host with conda + git + an NVIDIA GPU + enough disk; "
                     "no existing install. Ready to install via "
                     "install_modelangelo.sh after the user confirms."]


# --------------------------------------------------------------------------- #
# Assemble + render
# --------------------------------------------------------------------------- #
def build_report(args):
    host = collect_host_identity()
    py = collect_python()
    ma = collect_model_angelo(args.env)
    gpu = probe_nvidia_smi()
    weights = check_weights(args.torch_home)
    external = collect_external()

    torch_info = {"state": "not_run",
                  "note": "Not probed by default; heavyweight (imports torch)."}
    if args.torch_probe:
        torch_info = probe_torch(args.timeout)

    facts = {
        "host_identity": host, "python": py, "model_angelo": ma,
        "gpu_cuda": gpu, "weights": weights, "external": external, "torch": torch_info,
    }
    state, reasons = determine_state(facts)

    report = {
        "schema_version": SCHEMA_VERSION, "probe_version": PROBE_VERSION,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat(),
        "state": state, "state_reasons": reasons,
        "source_basis": {"commit": SOURCE_BASIS_COMMIT, "note": SOURCE_BASIS_NOTE},
        "probe_invocation": {
            "default_safe_run": not args.torch_probe,
            "torch_probe_requested": bool(args.torch_probe),
            "env_name_checked": args.env,
            "timeout_seconds": args.timeout,
        },
    }
    report.update(facts)
    return report


def render_json(report):
    return json.dumps(report, indent=2, sort_keys=False)


def _yn(v):
    return "yes" if v else "no"


def render_markdown(report):
    h, py = report["host_identity"], report["python"]
    ma, gpu = report["model_angelo"], report["gpu_cuda"]
    w, ext, t = report["weights"], report["external"], report["torch"]
    L = []
    L.append("# ModelAngelo site config report (local / private)")
    L.append("")
    L.append("> Per-environment report by `modelangelo_env_probe.py`. "
             "**Private/local: never packaged or committed** (see `.gitignore`); "
             "only `site_config.template.md` ships. Home path redacted.")
    L.append("")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| created_at (UTC) | %s |" % report["created_at"])
    L.append("| probe / schema | %s / %s |" % (report["probe_version"], report["schema_version"]))
    L.append("| **state** | **%s** |" % report["state"].upper())
    L.append("| source_basis | commit %s |" % report["source_basis"]["commit"][:12])
    L.append("| default safe run | %s |" % _yn(report["probe_invocation"]["default_safe_run"]))
    L.append("")
    L.append("## State reasons")
    for r in report["state_reasons"]:
        L.append("- %s" % r)
    L.append("")
    L.append("## Host identity")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| hostname | %s |" % h["hostname"])
    L.append("| os_system | %s |" % h["os_system"])
    L.append("| os_release | %s |" % h["os_release"])
    L.append("| machine/arch | %s |" % h["machine"])
    L.append("| is_linux | %s |" % _yn(h["is_linux"]))
    L.append("")
    L.append("## Python / package managers")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| executable | %s |" % py["executable"])
    L.append("| version | %s |" % py["version"])
    L.append("| conda/mamba present | %s |" % _yn(py["conda_present"]))
    L.append("| git present | %s |" % _yn(py["git_present"]))
    L.append("| conda env active | %s |" % _yn(py["conda_env_active"]))
    mgrs = ", ".join(n for n, p in py["package_managers_present"].items() if p) or "none"
    L.append("| package managers | %s |" % mgrs)
    L.append("")
    L.append("## ModelAngelo install")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| already installed | %s |" % _yn(ma["installed"]))
    L.append("| executable on PATH | %s |" % (ma.get("executable_on_path") or "n/a"))
    L.append("| package version | %s |" % (ma.get("package_version") or "n/a"))
    L.append("| conda env '%s' present | %s |"
             % (ma["conda_env_name_checked"],
                "unknown" if ma.get("conda_env_present") is None else _yn(ma["conda_env_present"])))
    L.append("")
    L.append("## GPU / CUDA")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| nvidia-smi present | %s |" % _yn(gpu["present"]))
    L.append("| gpu_count | %s |" % gpu["gpu_count"])
    L.append("| gpus | %s |" % (", ".join(gpu["gpus"]) if gpu["gpus"] else "none"))
    L.append("| max GPU mem (GB) | %s |" % (gpu.get("max_mem_gb") or "n/a"))
    L.append("")
    L.append("## Weights / cache")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| TORCH_HOME set | %s |" % _yn(w["torch_home_set"]))
    L.append("| TORCH_HOME value | %s |" % (w.get("torch_home_value") or "unset"))
    L.append("| cache root source | %s |" % w["cache_root_source"])
    L.append("| hub dir | %s |" % w["hub_dir"])
    L.append("| nucleotides present | %s |" % _yn(w["nucleotides_present"]))
    L.append("| nucleotides_no_seq present | %s |" % _yn(w["nucleotides_no_seq_present"]))
    L.append("| esm1b present | %s |" % _yn(w["esm_present"]))
    L.append("| free disk (GB) | %s |" % (w.get("free_gb") if w.get("free_gb") is not None else "n/a"))
    L.append("")
    L.append("## External / HPC")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| hhblits (hhsuite) present | %s |" % _yn(ext["hhblits_present"]))
    L.append("| module command present | %s |" % _yn(ext["module_cmd_present"]))
    L.append("| sbgrid present | %s |" % _yn(ext["sbgrid_present"]))
    L.append("")
    L.append("## torch probe")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| state | %s |" % t.get("state", "not_run"))
    L.append("| version | %s |" % (t.get("version") or "n/a"))
    L.append("| cuda_available | %s |" % ("n/a" if t.get("cuda_available") is None
                                          else _yn(t.get("cuda_available"))))
    if t.get("devices") is not None:
        L.append("| torch devices | %s |" % (", ".join(t["devices"]) if t["devices"] else "none"))
    L.append("")
    L.append("_Heavyweight live calls (`--torch-probe`, any `model_angelo` run) "
             "import torch / load weights; a successful import proves the import "
             "chain loaded, never that a build will succeed or that a model is good._")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Read-only ModelAngelo install-readiness/config probe. "
                    "Default run performs no install/clone/download/torch/network "
                    "action.")
    p.add_argument("--env", default=DEFAULT_ENV_NAME,
                   help="conda env name to look for (default: model_angelo).")
    p.add_argument("--torch-home", dest="torch_home", default=None,
                   help="Override TORCH_HOME for the weight-cache check (stat only).")
    p.add_argument("--torch-probe", dest="torch_probe", action="store_true",
                   help="OPT-IN heavyweight: import torch in an isolated, timed "
                        "child process to report version + cuda.is_available().")
    p.add_argument("--timeout", type=int, default=60,
                   help="Hard timeout (s) for any optional live subprocess. Default 60.")
    p.add_argument("--format", dest="fmt", choices=("json", "md"), default="json",
                   help="Output format. Default json.")
    p.add_argument("--output", dest="output", default=None,
                   help="Write report to this file (must be in an existing dir, "
                        "e.g. configs/). Default: stdout.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = build_report(args)
    rendered = render_json(report) if args.fmt == "json" else render_markdown(report)
    if args.output:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        if not os.path.isdir(out_dir):
            sys.stderr.write("Refusing to create directory '%s'. Create it first; "
                             "this probe never makes directories.\n" % out_dir)
            return 2
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(rendered)
            if not rendered.endswith("\n"):
                fh.write("\n")
        sys.stderr.write("Wrote %s report to %s (state=%s)\n"
                         % (args.fmt, args.output, report["state"]))
    else:
        sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
