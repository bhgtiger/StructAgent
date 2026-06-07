#!/usr/bin/env python3
"""Read-only DeepEMhancer target-environment / config probe.

This script gathers facts needed to decide whether a host is a usable
DeepEMhancer runtime, and emits a config report (JSON or Markdown) plus a
readiness ``state`` computed from the state machine in
``plans/config_state_machine_deepemhancer.md``.

Design contract (binding):
  * stdlib only.
  * Treat every ``deepemhancer`` invocation and every TensorFlow import as
    HEAVYWEIGHT. They are never run inline in this process. They run only in a
    child subprocess, behind explicit opt-in flags, with a hard timeout, with
    ``CUDA_VISIBLE_DEVICES=""``, and with exit code / timeout captured.
  * The DEFAULT run performs NO heavyweight or side-effecting action: no
    DeepEMhancer call, no TensorFlow import, no network, no install, no map
    processing, no model download, no chmod, no scheduler, no CryoSPARC call.
    It only reads metadata (importlib.metadata), looks up executables on PATH,
    runs ``nvidia-smi`` (read-only query) if present, and stats model files.
  * The home directory path is redacted from all emitted output.
  * This script never creates directories. ``--output`` must point into an
    already-existing directory (intended: ``configs/``).

Allowlisted optional live calls (opt-in only):
  * ``deepemhancer --version``  (with --live-help)
  * ``deepemhancer -h``         (with --live-help)
  * a TensorFlow version/GPU probe in a child process (with --tensorflow-probe)

Forbidden in this probe (never invoked): bare ``deepemhancer``, ``-i/-o`` map
processing, the model-download flag, conda/pip installs, chmod, scheduler
submission (sbatch/qsub), and CryoSPARC commands.
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
SOURCE_BASIS_COMMIT = "961f028ca609017990de4473ab368cf1787e8282"
SOURCE_BASIS_NOTE = (
    "rsanchezgarc/deepEMhancer master snapshot; flags/defaults/models derived "
    "from pinned source. Live installed `deepemhancer -h` on the target wins "
    "for that machine."
)

# From sources/source/source_refs.md (config.py): default model directory and
# the model files DeepEMhancer expects.
DEFAULT_MODEL_DIR = os.path.expanduser(
    "~/.local/share/deepEMhancerModels/production_checkpoints"
)
# tight/wide/highRes are required for the standard -p workflows; masked.hd5 is
# only needed for normalization mode 2 (-m/--binaryMask) so it is optional.
REQUIRED_MODEL_FILES = (
    "deepEMhancer_tightTarget.hd5",
    "deepEMhancer_wideTarget.hd5",
    "deepEMhancer_highRes.hd5",
)
OPTIONAL_MODEL_FILES = ("deepEMhancer_masked.hd5",)

# cmdParser.py checks specifically for tightTarget; if it is missing a real run
# prints "Deep learning models not found ..." and sys.exit(1).
GATING_MODEL_FILE = "deepEMhancer_tightTarget.hd5"

# Candidate distribution names for importlib.metadata lookup.
PACKAGE_NAME_CANDIDATES = ("deepEMhancer", "deepemhancer", "deepEMhancer-gpu")

EXCERPT_LIMIT = 600

HOME = os.path.expanduser("~")


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def redact(value):
    """Replace the user's home directory prefix with ``~`` in any string.

    Applied to every path-bearing field and to captured subprocess output so a
    distributable/pasted config never leaks the absolute home path (which
    contains the username).
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    out = value
    if HOME and HOME in out:
        out = out.replace(HOME, "~")
    return out


# --------------------------------------------------------------------------- #
# Safe subprocess helper (hard timeout, captured exit code/stdout/stderr)
# --------------------------------------------------------------------------- #
def run_subprocess(argv, timeout, extra_env=None, capture_full=False):
    """Run a read-only command with a hard timeout; never raise.

    Returns a dict describing the outcome. Used for ``nvidia-smi`` and, only
    when explicitly opted in, for the heavyweight ``deepemhancer``/TensorFlow
    probes.

    Redaction is applied to the FULL captured stream first, then the stored
    ``stdout_excerpt``/``stderr_excerpt`` are sliced to ``EXCERPT_LIMIT`` from
    the already-redacted text (so truncation can never leak a partial home
    path). When ``capture_full`` is set, the full redacted stdout is also
    returned under ``stdout_full`` so a caller can parse output that exceeds
    the excerpt limit; callers must drop that key before storing the result in
    the emitted report.
    """
    result = {
        "ran": False,
        "exit_code": None,
        "timed_out": False,
        "stdout_excerpt": None,
        "stderr_excerpt": None,
        "error": None,
    }
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
            text=True,
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
# Fact collection (all read-only / no heavyweight calls)
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
    env_flags = {
        "conda_env_active": bool(os.environ.get("CONDA_DEFAULT_ENV")),
        "conda_prefix_set": bool(os.environ.get("CONDA_PREFIX")),
        "virtualenv_active": bool(os.environ.get("VIRTUAL_ENV")),
    }
    managers = {
        name: shutil.which(name) is not None
        for name in ("conda", "mamba", "micromamba", "pip", "pip3")
    }
    return {
        "executable": redact(sys.executable),
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "env_indicators": env_flags,
        "package_managers_present": managers,
    }


def collect_package_version():
    for name in PACKAGE_NAME_CANDIDATES:
        try:
            return {"found": True, "dist_name": name, "version": ilmd.version(name)}
        except ilmd.PackageNotFoundError:
            continue
        except Exception as exc:
            return {"found": False, "dist_name": None, "version": None,
                    "error": "%s: %s" % (type(exc).__name__, exc)}
    return {"found": False, "dist_name": None, "version": None}


def locate_executable(provided_path):
    if provided_path:
        expanded = os.path.expanduser(provided_path)
        exists = os.path.isfile(expanded)
        return {
            "source": "user_provided",
            "path": redact(expanded),
            "exists": exists,
        }
    found = shutil.which("deepemhancer")
    return {
        "source": "PATH" if found else "not_found",
        "path": redact(found),
        "exists": found is not None,
    }


def probe_nvidia_smi():
    """Read-only GPU query. nvidia-smi is not a DeepEMhancer/TensorFlow call."""
    if shutil.which("nvidia-smi") is None:
        return {"present": False, "gpus": [], "gpu_count": 0,
                "cuda_visible_devices_set": bool(os.environ.get("CUDA_VISIBLE_DEVICES")),
                "query": None}
    query = run_subprocess(
        ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
        timeout=10,
    )
    gpus = []
    if query["ran"] and not query["timed_out"] and query["exit_code"] == 0:
        for line in (query["stdout_excerpt"] or "").splitlines():
            line = line.strip()
            if line:
                gpus.append(line)
    return {
        "present": True,
        "gpus": gpus,
        "gpu_count": len(gpus),
        "cuda_visible_devices_set": bool(os.environ.get("CUDA_VISIBLE_DEVICES")),
        "query": query,
    }


def check_models(model_dir_arg):
    """Stat model files only. No download, no directory creation."""
    info = {
        "default_model_dir": redact(DEFAULT_MODEL_DIR),
        "default_model_dir_exists": os.path.isdir(DEFAULT_MODEL_DIR),
        "user_model_dir": None,
        "checked_dir": None,
        "checked_dir_is_file": False,
        "custom_hd5_file": None,
        "files_present": {},
        "gating_file_present": False,
        "all_required_present": False,
        "missing_required": [],
    }

    target = None
    if model_dir_arg:
        expanded = os.path.expanduser(model_dir_arg)
        info["user_model_dir"] = redact(expanded)
        if os.path.isfile(expanded):
            # --deepLearningModelPath may point directly at an .hd5 file.
            info["checked_dir_is_file"] = True
            info["custom_hd5_file"] = redact(expanded)
            info["gating_file_present"] = expanded.endswith(".hd5")
            info["all_required_present"] = expanded.endswith(".hd5")
            info["checked_dir"] = redact(expanded)
            return info
        target = expanded
    elif info["default_model_dir_exists"]:
        target = DEFAULT_MODEL_DIR

    info["checked_dir"] = redact(target)
    if not target or not os.path.isdir(target):
        info["missing_required"] = list(REQUIRED_MODEL_FILES)
        return info

    present = {}
    for fname in REQUIRED_MODEL_FILES + OPTIONAL_MODEL_FILES:
        present[fname] = os.path.isfile(os.path.join(target, fname))
    info["files_present"] = present
    info["gating_file_present"] = present.get(GATING_MODEL_FILE, False)
    info["missing_required"] = [f for f in REQUIRED_MODEL_FILES if not present.get(f)]
    info["all_required_present"] = len(info["missing_required"]) == 0
    return info


# --------------------------------------------------------------------------- #
# Optional HEAVYWEIGHT probes (opt-in only, isolated subprocess + timeout)
# --------------------------------------------------------------------------- #
def probe_live_help(executable_info, timeout):
    """Run `deepemhancer --version` and `-h` ONLY. Heavyweight: imports TF.

    Isolated subprocess, hard timeout, CUDA_VISIBLE_DEVICES="" to avoid GPU
    allocation. Success proves only that the import chain loaded, NOT that the
    runtime is ready.
    """
    out = {"requested": True, "version": None, "help": None,
           "note": "Heavyweight: loads TensorFlow. Success != runtime ready."}
    if not executable_info.get("exists"):
        out["skipped"] = "executable not found"
        return out
    exe = os.path.expanduser(executable_info["path"].replace("~", HOME, 1)) \
        if executable_info.get("path") else "deepemhancer"
    safe_env = {"CUDA_VISIBLE_DEVICES": ""}
    out["version"] = run_subprocess([exe, "--version"], timeout, safe_env)
    out["help"] = run_subprocess([exe, "-h"], timeout, safe_env)
    return out


def probe_tensorflow(timeout):
    """Probe TensorFlow version/GPU in a CHILD process. Never import inline.

    Returns state in {ok, failed, timeout}. Default run leaves this not_run.
    """
    # Built as a string so this parent process never imports the framework.
    child_lines = [
        "import json as _j",
        "_r = {}",
        "try:",
        "    import tensorflow as _tf",
        "    _r['version'] = _tf.__version__",
        "    _r['gpus'] = [getattr(d, 'name', str(d)) for d in "
        "_tf.config.list_physical_devices('GPU')]",
        "    _r['ok'] = True",
        "except Exception as _e:",
        "    _r['ok'] = False",
        "    _r['error'] = type(_e).__name__ + ': ' + str(_e)",
        "print(_j.dumps(_r))",
    ]
    child = run_subprocess(
        [sys.executable, "-c", "\n".join(child_lines)],
        timeout,
        {"CUDA_VISIBLE_DEVICES": ""},
        capture_full=True,
    )
    # Parse the FULL (redacted) stdout, then drop it so the report keeps only
    # the truncated excerpt. A long GPU device list could exceed EXCERPT_LIMIT;
    # parsing the excerpt would then fail and misclassify a working TF as failed.
    full_stdout = child.pop("stdout_full", None)
    result = {"requested": True, "state": "failed", "version": None,
              "gpus": None, "raw": child}
    if child["timed_out"]:
        result["state"] = "timeout"
        return result
    if child["ran"] and child["exit_code"] == 0 and full_stdout:
        try:
            payload = json.loads(full_stdout)
            if payload.get("ok"):
                result["state"] = "ok"
                result["version"] = payload.get("version")
                result["gpus"] = payload.get("gpus")
            else:
                result["state"] = "failed"
                result["error"] = payload.get("error")
        except Exception:
            result["state"] = "failed"
    return result


# --------------------------------------------------------------------------- #
# State machine (plans/config_state_machine_deepemhancer.md)
# --------------------------------------------------------------------------- #
def determine_state(facts):
    """Return (state, reasons) for the host this report describes.

    States: ready / partial / blocked / unknown / stale. A freshly generated
    report only emits ready/partial/blocked/unknown. ``stale`` is a judgement
    the *skill* makes later by comparing identity/timestamp against the user's
    target (see references/02). Fatal blockers dominate; otherwise any untested
    required runtime fact downgrades ready -> partial.
    """
    host = facts["host_identity"]
    pkg = facts["deepemhancer_package"]
    exe = facts["deepemhancer_executable"]
    gpu = facts["gpu_cuda"]
    models = facts["models"]
    tf_state = facts["tensorflow"].get("state", "not_run")
    live = facts["live_help"]

    blockers = []
    partials = []

    # unknown: cannot even establish host identity.
    if not host.get("os_system"):
        return "unknown", ["Host OS could not be determined; run the probe on the target."]

    have_install = exe.get("exists") or pkg.get("found")

    # ---- Fatal blockers --------------------------------------------------- #
    if not host.get("is_linux"):
        blockers.append(
            "OS is %s/%s, not Linux. DeepEMhancer is Linux-tested; this host is "
            "not a supported execution target." % (host.get("os_system"),
                                                    host.get("machine")))
    if not have_install:
        blockers.append(
            "No `deepemhancer` executable on PATH and no Python package metadata "
            "found; DeepEMhancer is not installed in this environment.")
    if not models["all_required_present"] and not models.get("checked_dir_is_file"):
        if models["checked_dir"] is None:
            blockers.append(
                "No model directory found (default %s absent and none provided). "
                "A real run would print 'Deep learning models not found' and "
                "exit(1)." % models["default_model_dir"])
        elif not models["gating_file_present"]:
            blockers.append(
                "Required model file %s not found in %s; a real run would "
                "exit(1)." % (GATING_MODEL_FILE, models["checked_dir"]))
    if tf_state in ("failed", "timeout"):
        blockers.append(
            "TensorFlow probe %s; the install is likely unusable until the "
            "TF/CUDA/GPU stack is fixed." % tf_state)
    if live.get("requested"):
        for key in ("version", "help"):
            res = live.get(key)
            if isinstance(res, dict) and (res.get("timed_out")
                                          or (res.get("exit_code") not in (None, 0))):
                blockers.append(
                    "`deepemhancer %s` failed or timed out, indicating a broken "
                    "import/runtime chain." % ("--version" if key == "version" else "-h"))
                break

    # ---- Non-fatal (partial) signals ------------------------------------- #
    if have_install and not exe.get("exists"):
        partials.append("Package metadata present but no `deepemhancer` on PATH; "
                        "entry point may be unavailable in this shell.")
    if not gpu.get("present"):
        partials.append("nvidia-smi not present: no NVIDIA GPU detected. GPU "
                        "execution cannot be confirmed; CPU-only mode is very "
                        "slow and must be explicitly accepted.")
    elif gpu.get("gpu_count", 0) == 0:
        partials.append("nvidia-smi present but reported no GPUs.")
    if tf_state == "not_run":
        partials.append("TensorFlow not probed (default). TF/GPU compatibility "
                        "is unverified; pass --tensorflow-probe on the target to test.")
    if not live.get("requested"):
        partials.append("Live `deepemhancer --version`/`-h` not run (default). "
                        "Exact installed flags/version unverified.")
    if models.get("files_present"):
        missing_opt = [f for f in OPTIONAL_MODEL_FILES
                       if not models["files_present"].get(f)]
        if missing_opt and models["all_required_present"]:
            partials.append("Optional model(s) missing: %s (needed only for "
                            "-m/--binaryMask mode 2)." % ", ".join(missing_opt))

    if blockers:
        return "blocked", blockers
    if partials:
        return "partial", partials
    return "ready", ["All probed required facts present; remember live success "
                     "only proves the import chain loaded, not map-processing "
                     "quality."]


# --------------------------------------------------------------------------- #
# Assemble the full report
# --------------------------------------------------------------------------- #
def build_report(args):
    host = collect_host_identity()
    python_info = collect_python()
    pkg = collect_package_version()
    exe = locate_executable(args.deepemhancer_path)
    gpu = probe_nvidia_smi()
    models = check_models(args.model_dir)

    tensorflow = {"state": "not_run",
                  "note": "Not probed by default; heavyweight (imports TF)."}
    if args.tensorflow_probe:
        tensorflow = probe_tensorflow(args.timeout)

    live_help = {"requested": False,
                 "note": "Not run by default; heavyweight (imports TF)."}
    if args.live_help:
        live_help = probe_live_help(exe, args.timeout)

    facts = {
        "host_identity": host,
        "python": python_info,
        "deepemhancer_package": pkg,
        "deepemhancer_executable": exe,
        "gpu_cuda": gpu,
        "models": models,
        "tensorflow": tensorflow,
        "live_help": live_help,
    }

    state, reasons = determine_state(facts)

    report = {
        "schema_version": SCHEMA_VERSION,
        "probe_version": PROBE_VERSION,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat(),
        "state": state,
        "state_reasons": reasons,
        "source_basis": {"commit": SOURCE_BASIS_COMMIT, "note": SOURCE_BASIS_NOTE},
        "probe_invocation": {
            "default_safe_run": not (args.live_help or args.tensorflow_probe),
            "live_help_requested": bool(args.live_help),
            "tensorflow_probe_requested": bool(args.tensorflow_probe),
            "timeout_seconds": args.timeout,
        },
    }
    report.update(facts)
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_json(report):
    return json.dumps(report, indent=2, sort_keys=False)


def _yn(value):
    return "yes" if value else "no"


def render_markdown(report):
    h = report["host_identity"]
    py = report["python"]
    pkg = report["deepemhancer_package"]
    exe = report["deepemhancer_executable"]
    gpu = report["gpu_cuda"]
    models = report["models"]
    tf = report["tensorflow"]
    live = report["live_help"]

    lines = []
    lines.append("# DeepEMhancer site config report (local / private)")
    lines.append("")
    lines.append("> Per-environment report generated by "
                 "`deepemhancer_env_probe.py`. **Private/local: never packaged "
                 "or committed** (see `.gitignore`); only "
                 "`site_config.template.md` ships. The home path is redacted.")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| created_at (UTC) | %s |" % report["created_at"])
    lines.append("| probe_version | %s |" % report["probe_version"])
    lines.append("| schema_version | %s |" % report["schema_version"])
    lines.append("| **state** | **%s** |" % report["state"].upper())
    lines.append("| source_basis | commit %s |" % report["source_basis"]["commit"])
    lines.append("| default safe run | %s |"
                 % _yn(report["probe_invocation"]["default_safe_run"]))
    lines.append("")

    lines.append("## State reasons")
    for reason in report["state_reasons"]:
        lines.append("- %s" % reason)
    lines.append("")

    lines.append("## Host identity")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| hostname | %s |" % h["hostname"])
    lines.append("| os_system | %s |" % h["os_system"])
    lines.append("| os_release | %s |" % h["os_release"])
    lines.append("| machine/arch | %s |" % h["machine"])
    lines.append("| is_linux | %s |" % _yn(h["is_linux"]))
    lines.append("| username redacted | %s |" % _yn(h["username_redacted"]))
    lines.append("")

    lines.append("## Python / environment")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| executable | %s |" % py["executable"])
    lines.append("| version | %s |" % py["version"])
    lines.append("| implementation | %s |" % py["implementation"])
    lines.append("| conda env active | %s |"
                 % _yn(py["env_indicators"]["conda_env_active"]))
    lines.append("| virtualenv active | %s |"
                 % _yn(py["env_indicators"]["virtualenv_active"]))
    managers = ", ".join(n for n, present in py["package_managers_present"].items()
                         if present) or "none detected"
    lines.append("| package managers | %s |" % managers)
    lines.append("")

    lines.append("## DeepEMhancer install")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| package metadata found | %s |" % _yn(pkg["found"]))
    lines.append("| package version | %s |" % (pkg.get("version") or "n/a"))
    lines.append("| executable source | %s |" % exe["source"])
    lines.append("| executable path | %s |" % (exe.get("path") or "n/a"))
    lines.append("| executable exists | %s |" % _yn(exe["exists"]))
    lines.append("")

    lines.append("## GPU / CUDA")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| nvidia-smi present | %s |" % _yn(gpu["present"]))
    lines.append("| gpu_count | %s |" % gpu["gpu_count"])
    lines.append("| gpus | %s |" % (", ".join(gpu["gpus"]) if gpu["gpus"] else "none"))
    lines.append("| CUDA_VISIBLE_DEVICES set | %s |"
                 % _yn(gpu["cuda_visible_devices_set"]))
    lines.append("")

    lines.append("## TensorFlow probe")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| state | %s |" % tf.get("state", "not_run"))
    lines.append("| version | %s |" % (tf.get("version") or "n/a"))
    if tf.get("gpus") is not None:
        lines.append("| GPUs seen by TF | %s |"
                     % (", ".join(tf["gpus"]) if tf["gpus"] else "none"))
    lines.append("")

    lines.append("## Models")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| default model dir | %s |" % models["default_model_dir"])
    lines.append("| default dir exists | %s |" % _yn(models["default_model_dir_exists"]))
    lines.append("| checked dir | %s |" % (models.get("checked_dir") or "n/a"))
    lines.append("| all required present | %s |" % _yn(models["all_required_present"]))
    if models.get("files_present"):
        for fname, present in models["files_present"].items():
            lines.append("| %s | %s |" % (fname, _yn(present)))
    if models.get("missing_required"):
        lines.append("| missing required | %s |"
                     % ", ".join(models["missing_required"]))
    lines.append("")

    lines.append("## Live help probe")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| requested | %s |" % _yn(live.get("requested")))
    if live.get("skipped"):
        lines.append("| skipped | %s |" % live["skipped"])
    if isinstance(live.get("version"), dict):
        v = live["version"]
        lines.append("| --version exit_code | %s |" % v.get("exit_code"))
        lines.append("| --version timed_out | %s |" % _yn(v.get("timed_out")))
    lines.append("")
    lines.append("_Heavyweight live calls (`deepemhancer --version`/`-h`, "
                 "TensorFlow) import the full TF/GPU stack; success proves only "
                 "that the import chain loaded, never that map processing will "
                 "succeed or improve a map._")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Read-only DeepEMhancer environment/config probe. Default "
                    "run performs no DeepEMhancer/TensorFlow/network/install "
                    "action.",
    )
    parser.add_argument("--deepemhancer-path", dest="deepemhancer_path",
                        default=None,
                        help="Path to a deepemhancer executable to record "
                             "(stat only; not invoked unless --live-help).")
    parser.add_argument("--model-dir", dest="model_dir", default=None,
                        help="Model directory or .hd5 file path to check "
                             "(stat only; never downloaded).")
    parser.add_argument("--live-help", dest="live_help", action="store_true",
                        help="OPT-IN heavyweight: run `deepemhancer --version` "
                             "and `-h` in an isolated, timed subprocess.")
    parser.add_argument("--tensorflow-probe", dest="tensorflow_probe",
                        action="store_true",
                        help="OPT-IN heavyweight: probe TensorFlow version/GPU "
                             "in an isolated, timed child process.")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Hard timeout (seconds) for any optional live "
                             "subprocess. Default 60.")
    parser.add_argument("--format", dest="fmt", choices=("json", "md"),
                        default="json", help="Output format. Default json.")
    parser.add_argument("--output", dest="output", default=None,
                        help="Write report to this file (must be in an existing "
                             "directory, e.g. configs/). Default: stdout.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = build_report(args)
    rendered = render_json(report) if args.fmt == "json" else render_markdown(report)

    if args.output:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        if not os.path.isdir(out_dir):
            sys.stderr.write(
                "Refusing to create directory '%s'. Create it first; this probe "
                "never makes directories.\n" % out_dir)
            return 2
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            if not rendered.endswith("\n"):
                handle.write("\n")
        sys.stderr.write("Wrote %s report to %s (state=%s)\n"
                         % (args.fmt, args.output, report["state"]))
    else:
        sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
