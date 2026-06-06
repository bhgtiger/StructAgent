#!/usr/bin/env python3
"""
topaz_env_probe.py - Read-only environment / config-session probe for the Topaz skill.

WHAT THIS IS
    A read-only inspector that records enough of the local environment for the
    Topaz skill to give *safe* advice. It answers: which OS/arch is this, which
    Python/conda is active, is Topaz installed (and which version), is an NVIDIA
    GPU present, and -- crucially -- which compute devices *Topaz itself* can use.

WHAT THIS IS NOT (hard safety boundary)
    - It NEVER installs, upgrades, or removes anything.
    - It NEVER runs a Topaz compute job (train / extract / denoise / segment / ...).
    - It NEVER reads, moves, or uploads user micrographs / private project data.
    - It only writes to the single file you pass with --output (and stdout).

    The only subprocesses it may launch are inert metadata calls:
        topaz --version, topaz --help            (skippable with --no-topaz-exec)
        <pm> --version  (conda/mamba/micromamba/pip)
        nvidia-smi -L
        <python> -c "import torch; ..."          (ONLY with --check-torch)
    All are wrapped with timeouts and never raise out of the probe.

SOURCED DEVICE EVIDENCE
    The topaz_{cpu,cuda,mps}_supported fields are grounded in the Topaz source at
    the commit recorded in SOURCE_EVIDENCE below -- NOT inferred from PyTorch.
    Topaz's device dispatch (topaz/cuda.py set_device + .cuda() calls) is binary
    CUDA-or-CPU; there is no MPS / Apple-Silicon-GPU code path. A green
    torch.backends.mps.is_available() means the *framework* supports MPS, which is
    NOT evidence that Topaz uses it. See references/02_config_session_and_environment.md.

USAGE
    python3 topaz_env_probe.py --help
    python3 topaz_env_probe.py --output report.md
    python3 topaz_env_probe.py --output report.json --format json
    python3 topaz_env_probe.py --output report.md --check-torch
"""

import argparse
import datetime
import json
import os
import platform
import shutil
import socket
import subprocess
import sys

# ---------------------------------------------------------------------------
# Sourced evidence for Topaz device support. These are facts read out of the
# Topaz source tree at the pinned commit, NOT runtime inference. If a different
# Topaz version is detected at runtime, the probe downgrades these to "unknown".
# ---------------------------------------------------------------------------
SOURCE_EVIDENCE = {
    "repo_url": "https://github.com/tbepler/topaz",
    "commit": "58fe52370f4accb8215525df2ea8f2c7ee6d340a",
    "tag": "v0.3.20",
    "device_support": {
        # value, plus the source citation that justifies it
        "cpu": {
            "supported": True,
            "evidence": "topaz/cuda.py set_device() falls back to CPU; "
                        "--device -1 forces CPU; normalize defaults device=-1; "
                        "models load with map_location='cpu' (topaz/model/utils.py).",
        },
        "cuda": {
            "supported": True,
            "evidence": "topaz/cuda.py set_device() calls torch.cuda.set_device / "
                        "torch.cuda.is_available(); training.py/extract.py/denoise.py "
                        "use .cuda(); README Prerequisites: 'An Nvidia GPU with CUDA "
                        "support for GPU acceleration.'",
        },
        "mps": {
            "supported": False,
            "evidence": "No 'mps' or 'torch.backends.mps' reference anywhere in topaz/ "
                        "at this commit; device dispatch is binary CUDA-or-CPU "
                        "(topaz/cuda.py only consults torch.cuda). Apple-Silicon GPU "
                        "(MPS) is NOT used even if PyTorch reports it available.",
        },
    },
}

# Supported interpreter range declared by Topaz (setup.py python_requires).
TOPAZ_PYTHON_REQUIRES = ">=3.8,<=3.13"

# Default config time-to-live before a cheap re-probe is recommended.
DEFAULT_TTL_DAYS = 14

SUBPROCESS_TIMEOUT = 60  # seconds; topaz --help imports torch and can be slow


def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd, timeout=SUBPROCESS_TIMEOUT):
    """Run a command read-only. Never raises. Returns dict with ok/code/out/err."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "out": proc.stdout.decode("utf-8", "replace").strip(),
            "err": proc.stderr.decode("utf-8", "replace").strip(),
        }
    except FileNotFoundError:
        return {"ok": False, "code": None, "out": "", "err": "not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": None, "out": "", "err": "timeout"}
    except Exception as exc:  # never let a probe crash the run
        return {"ok": False, "code": None, "out": "", "err": "error: %s" % exc}


def detect_os():
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "arch": platform.machine(),
        "platform": platform.platform(),
        "is_apple_silicon": platform.system() == "Darwin" and platform.machine() == "arm64",
    }
    if platform.system() == "Darwin":
        sw = _run(["sw_vers", "-productVersion"])
        info["macos_version"] = sw["out"] if sw["ok"] else "unknown"
    return info


def detect_shell():
    return {
        "SHELL": os.environ.get("SHELL", "unknown"),
        "TERM": os.environ.get("TERM", "unknown"),
    }


def detect_package_managers():
    pms = {}
    for pm in ("conda", "mamba", "micromamba", "pip", "pip3"):
        path = shutil.which(pm)
        pms[pm] = {"available": path is not None, "path": path}
    pms["active_conda_env"] = os.environ.get("CONDA_DEFAULT_ENV")
    pms["conda_prefix"] = os.environ.get("CONDA_PREFIX")
    return pms


def detect_python():
    ver = "%d.%d.%d" % sys.version_info[:3]
    in_range = (3, 8) <= sys.version_info[:2] <= (3, 13)
    return {
        "executable": sys.executable,
        "version": ver,
        "version_info": list(sys.version_info[:3]),
        "active_env": os.environ.get("CONDA_DEFAULT_ENV") or os.environ.get("VIRTUAL_ENV"),
        "topaz_python_requires": TOPAZ_PYTHON_REQUIRES,
        "in_topaz_supported_range": in_range,
    }


def detect_topaz(topaz_path=None, run_exec=True):
    """Detect a Topaz install. Filesystem detection first; optionally probe --version/--help."""
    result = {
        "installed": False,
        "executable": None,
        "version": None,
        "version_matches_source_evidence": None,
        "help_captured": False,
        "subcommands_captured": [],
        "import_metadata": None,
        "detection_method": None,
        "notes": [],
    }

    exe = topaz_path or shutil.which("topaz")
    if exe and os.path.exists(exe):
        result["executable"] = exe
        result["detection_method"] = "explicit path" if topaz_path else "PATH (shutil.which)"
        result["installed"] = True
    else:
        # Fall back to importable package metadata without importing torch-heavy modules.
        meta = _python_package_version("topaz")
        if meta:
            result["installed"] = True
            result["detection_method"] = "importlib.metadata (topaz-em package)"
            result["import_metadata"] = meta
        else:
            result["notes"].append("No 'topaz' on PATH and no topaz-em package metadata found.")
            return result

    if run_exec and result["executable"]:
        ver = _run([result["executable"], "--version"])
        if ver["ok"] or ver["out"] or ver["err"]:
            # argparse --version prints to stdout; some builds to stderr
            result["version"] = (ver["out"] or ver["err"] or "").strip() or None
        helpres = _run([result["executable"], "--help"])
        if helpres["ok"] and helpres["out"]:
            result["help_captured"] = True
            result["subcommands_captured"] = _parse_subcommands(helpres["out"])
        elif helpres["err"] == "timeout":
            result["notes"].append("topaz --help timed out (it imports torch); skipped.")
    elif not run_exec:
        result["notes"].append("--no-topaz-exec set: did not invoke topaz --version/--help.")

    # Compare detected version against sourced evidence version.
    if result["version"]:
        v = result["version"].replace("topaz", "").strip()
        result["version_matches_source_evidence"] = (v == SOURCE_EVIDENCE["tag"].lstrip("v"))
    return result


def _python_package_version(pkg_import_name):
    """Best-effort, import-light package metadata lookup. Returns version str or None."""
    try:
        import importlib.metadata as im
        for dist_name in ("topaz-em", "topaz"):
            try:
                return im.version(dist_name)
            except Exception:
                continue
    except Exception:
        pass
    return None


# Known subcommands for the pinned/validated Topaz release. Used (a) as a
# whitelist to keep _parse_subcommands from emitting group headers/description
# words, and (b) as a fallback when the help layout cannot be parsed.
# Source: captured live help `topaz.help.txt` for topaz 0.3.20 lists, under grouped
# headers: Particle picking {train, segment, extract, precision_recall_curve};
# Image processing {downsample, normalize, preprocess, denoise, denoise3d};
# File utilities {convert, split, particle_stack, train_test_split}; GUI {gui};
# [Deprecated] {scale_coordinates}.
# The remaining names below {boxes_to_coordinates, star_to_coordinates,
# coordinates_to_star, coordinates_to_boxes, coordinates_to_eman2_json,
# star_particles_threshold} are real callable `topaz <cmd>` subcommands that are
# HIDDEN from the grouped `topaz --help` output but verified to run
# (`topaz <cmd> --help` succeeds on 0.3.20). They are included so the probe reports
# the full callable surface, not only the help-listed commands.
KNOWN_SUBCOMMANDS = (
    # Particle picking
    "train", "segment", "extract", "precision_recall_curve",
    # Image processing
    "downsample", "normalize", "preprocess", "denoise", "denoise3d",
    # File utilities
    "convert", "split", "particle_stack", "train_test_split",
    # GUI
    "gui",
    # Deprecated
    "scale_coordinates", "boxes_to_coordinates", "star_to_coordinates",
    "coordinates_to_star", "coordinates_to_boxes", "coordinates_to_eman2_json",
    "star_particles_threshold",
)


def _parse_subcommands(help_text):
    """Extract real subcommand names from `topaz --help`.

    The 0.3.20 help groups commands ("Particle picking:", "Image processing:",
    ...) and each command is INDENTED under its group, e.g.

        commands:
          Particle picking:
            train                      train 2D region classifier ...
            segment                    segment images using ...

    Continuation lines of a description are indented even further. A naive
    "first token on every captured line" parser (the old behaviour) wrongly
    emitted group headers ("Particle", "Image", "File") and the first word of
    wrapped description lines ("by", "boxes_to_coordinates" mid-sentence, ...).

    Strategy: only accept a line whose first whitespace-separated token is a
    known 0.3.20 subcommand (KNOWN_SUBCOMMANDS). This both filters group
    headers/description noise and keeps the captured list matching
    topaz.help.txt exactly. Unknown-but-plausible command tokens (a future
    Topaz adding a subcommand) are still surfaced when they sit directly under
    a group header and look like a command token, so the probe does not silently
    hide new commands.
    """
    known = set(KNOWN_SUBCOMMANDS)
    subs = []
    capture = False
    in_group = False
    for line in help_text.splitlines():
        raw = line.rstrip("\n")
        low = raw.strip().lower()
        if low.startswith("commands:") or low.startswith("<command>"):
            capture = True
            continue
        if not capture:
            continue
        stripped = raw.strip()
        if not stripped:
            continue
        # A group header line ends with ':' and has no description column,
        # e.g. "Particle picking:", "[Deprecated]:". Mark that we are now
        # inside a group whose next indented lines are real commands.
        if stripped.endswith(":"):
            in_group = True
            continue
        token = stripped.split()[0]
        if token in ("optional", "positional", "usage", "options"):
            continue
        if token in known:
            subs.append(token)
        elif in_group and (token.replace("_", "").isalnum()):
            # New/unknown command token sitting directly under a group header:
            # accept it but only if it is the start of a command row (the help
            # aligns descriptions in a second column, so a real command row has
            # two-plus whitespace before the description).
            if "  " in stripped[len(token):]:
                subs.append(token)
        # Lines that don't start with a known command and aren't a fresh group
        # header are description continuations -> ignore.
    if not subs:
        # Help layout unparseable but topaz is the pinned release: fall back to
        # the known command set rather than reporting an empty list.
        subs = list(KNOWN_SUBCOMMANDS)
    return sorted(set(subs))


def detect_nvidia():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"nvidia_smi": "missing", "gpus": []}
    res = _run([smi, "-L"])
    if res["ok"]:
        gpus = [g for g in res["out"].splitlines() if g.strip()]
        return {"nvidia_smi": "available", "gpus": gpus}
    return {"nvidia_smi": "error", "gpus": [], "error": res["err"]}


def detect_torch(check_torch, python_exe):
    """Optionally probe torch CUDA/MPS in an ISOLATED subprocess (never imported in-process)."""
    if not check_torch:
        return {
            "checked": False,
            "torch_available": "not_checked",
            "torch_version": None,
            "cuda_available": "not_checked",
            "mps_available": "not_checked",
            "note": "Run with --check-torch to probe. torch is imported only in a "
                    "separate subprocess to isolate side effects (GPU context init). "
                    "CUDA-build caveat: the default PyPI torch is now a CUDA-13 (cu130) "
                    "wheel and reports cuda=False on a CUDA-12.x driver; if that happens "
                    "pin a cu12x build (e.g. torch==2.9.1+cu128). "
                    "[smoke]",
        }
    snippet = (
        "import json\n"
        "out={'torch_available':False,'torch_version':None,"
        "'cuda_available':False,'mps_available':False}\n"
        "try:\n"
        "    import torch\n"
        "    out['torch_available']=True\n"
        "    out['torch_version']=torch.__version__\n"
        "    out['cuda_available']=bool(torch.cuda.is_available())\n"
        "    try:\n"
        "        out['mps_available']=bool(torch.backends.mps.is_available())\n"
        "    except Exception:\n"
        "        out['mps_available']=False\n"
        "except Exception as e:\n"
        "    out['error']=str(e)\n"
        "print(json.dumps(out))\n"
    )
    res = _run([python_exe, "-c", snippet], timeout=SUBPROCESS_TIMEOUT)
    if res["ok"] and res["out"]:
        try:
            data = json.loads(res["out"].splitlines()[-1])
            data["checked"] = True
            data["note"] = (
                "torch.backends.mps.is_available() reports the FRAMEWORK only. "
                "Topaz does not dispatch to MPS (see topaz_mps_supported). "
                "If cuda_available is False but an NVIDIA GPU is present, the most "
                "common cause is a CUDA-13 (cu130) torch wheel on a CUDA-12.x driver; "
                "pin a cu12x build (e.g. torch==2.9.1+cu128). [smoke]"
            )
            return data
        except Exception:
            pass
    return {
        "checked": True,
        "torch_available": "missing",
        "torch_version": None,
        "cuda_available": "unknown",
        "mps_available": "unknown",
        "note": "torch not importable in %s (%s)." % (python_exe, res["err"] or "no output"),
    }


def derive_device_support(topaz):
    """Return Topaz device support grounded in sourced evidence (true/false/unknown)."""
    ev = SOURCE_EVIDENCE["device_support"]
    # If a topaz version was detected and it does NOT match our evidence commit,
    # we cannot claim the sourced facts hold -> unknown with a note.
    detected = topaz.get("version")
    mism = (
        detected is not None
        and topaz.get("version_matches_source_evidence") is False
    )

    def val(flag):
        if mism:
            return "unknown"
        return ev[flag]["supported"]

    return {
        "topaz_cpu_supported": val("cpu"),
        "topaz_cuda_supported": val("cuda"),
        "topaz_mps_supported": val("mps"),
        "evidence_commit": SOURCE_EVIDENCE["commit"],
        "evidence_tag": SOURCE_EVIDENCE["tag"],
        "evidence": {k: ev[k]["evidence"] for k in ev},
        "version_caveat": (
            "Detected Topaz version differs from sourced evidence (%s); device "
            "facts set to 'unknown' pending re-grounding." % SOURCE_EVIDENCE["tag"]
            if mism else None
        ),
    }


def derive_usability(devsupport, nvidia, torch_info):
    """Which sourced-supported devices are actually USABLE on this machine right now."""
    cuda_supported = devsupport["topaz_cuda_supported"] is True
    nvidia_present = nvidia.get("nvidia_smi") == "available"
    torch_cuda = torch_info.get("cuda_available")
    cuda_usable = cuda_supported and nvidia_present and (torch_cuda is True or torch_cuda == "not_checked")
    return {
        "cpu_usable_here": devsupport["topaz_cpu_supported"] is True,
        "cuda_usable_here": bool(cuda_usable) if nvidia_present else False,
        "cuda_usable_note": (
            "No NVIDIA GPU detected (nvidia-smi missing): Topaz will run on CPU only."
            if not nvidia_present else
            "NVIDIA GPU detected; confirm torch CUDA build with --check-torch."
        ),
        "mps_usable_here": False,
        "mps_usable_note": "Topaz has no MPS code path; Apple-Silicon GPU is unused regardless of PyTorch.",
    }


def compute_validation(topaz, python_info, devsupport, usability):
    blocked = []
    notes = []
    if not topaz["installed"]:
        status = "partial"
        blocked.append("concrete_command_generation_with_real_paths")
        blocked.append("topaz_job_execution")
        notes.append("Topaz not installed ON THIS MACHINE: do not emit concrete "
                     "commands with the user's real paths or run jobs here until it "
                     "is installed. The skill's CLI facts are still VALIDATED against "
                     "topaz 0.3.20 (captured live help) and may be used for guidance; "
                     "see configs/site_config.template.md and install per "
                     "references/02_config_session_and_environment.md.")
    elif topaz["installed"] and not topaz.get("version"):
        status = "partial"
        blocked.append("version_specific_claims")
        notes.append("Topaz detected but version not captured.")
    else:
        status = "valid"

    if not python_info["in_topaz_supported_range"]:
        notes.append("Active Python %s is outside Topaz supported range %s; an install "
                     "into this interpreter may fail or be unsupported."
                     % (python_info["version"], TOPAZ_PYTHON_REQUIRES))

    if not usability["cuda_usable_here"]:
        blocked.append("cuda_acceleration")
        notes.append("CUDA acceleration unavailable here; only CPU workflows apply. "
                     "CPU denoise/extract are feasible; CPU training is slow.")
    return status, blocked, notes


def build_report(args):
    started = _now_utc()
    os_info = detect_os()
    shell = detect_shell()
    pms = detect_package_managers()
    python_info = detect_python()
    topaz = detect_topaz(topaz_path=args.topaz, run_exec=not args.no_topaz_exec)
    nvidia = detect_nvidia()
    torch_info = detect_torch(args.check_torch, sys.executable)
    devsupport = derive_device_support(topaz)
    usability = derive_usability(devsupport, nvidia, torch_info)
    status, blocked, vnotes = compute_validation(topaz, python_info, devsupport, usability)

    stale_after = started + datetime.timedelta(days=DEFAULT_TTL_DAYS)

    report = {
        "schema": "topaz_skill.site_config/v1",
        "generated_at": _iso(started),
        "generated_by": "topaz_env_probe.py",
        "probe_is_read_only": True,
        "hostname": socket.gethostname(),
        "project_path": args.project_path,
        "os": os_info,
        "shell": shell,
        "package_managers": pms,
        "python": python_info,
        "topaz": topaz,
        "devices": {
            "nvidia": nvidia,
            "torch": torch_info,
            "topaz_cpu_supported": devsupport["topaz_cpu_supported"],
            "topaz_cuda_supported": devsupport["topaz_cuda_supported"],
            "topaz_mps_supported": devsupport["topaz_mps_supported"],
            "device_support_evidence": devsupport,
            "usability_here": usability,
        },
        "source_snapshot": {
            "repo_url": SOURCE_EVIDENCE["repo_url"],
            "commit_or_tag": SOURCE_EVIDENCE["tag"],
            "commit": SOURCE_EVIDENCE["commit"],
            "fetched_at": "2026-06-05",
        },
        "validation_status": status,
        "stale_after": _iso(stale_after),
        "staleness_policy": (
            "Re-run this probe before concrete advice if: now > stale_after (%d-day TTL); "
            "OR topaz executable path/version changed; OR active Python/conda env changed; "
            "OR OS/GPU/driver state changed; OR the user switches target project path."
            % DEFAULT_TTL_DAYS
        ),
        "blocked_capabilities": sorted(set(blocked)),
        "notes": vnotes,
        "safety": {
            "installed_anything": False,
            "ran_topaz_compute_job": False,
            "touched_user_data": False,
            "wrote_files": [args.output] if args.output else [],
        },
    }
    return report


def render_markdown(r):
    L = []
    A = L.append
    A("# Topaz site config (auto-probed)")
    A("")
    A("> Read-only environment probe output. No installs, no Topaz jobs, no user data touched.")
    A("")
    A("- **generated_at:** %s" % r["generated_at"])
    A("- **hostname:** %s" % r["hostname"])
    A("- **project_path:** %s" % (r["project_path"] or "(none given)"))
    A("- **validation_status:** **%s**" % r["validation_status"])
    A("- **stale_after:** %s" % r["stale_after"])
    A("")
    A("## OS / shell")
    o = r["os"]
    A("- system: %s %s (%s)" % (o["system"], o.get("macos_version", o["release"]), o["arch"]))
    A("- apple_silicon: %s" % o["is_apple_silicon"])
    A("- shell: %s" % r["shell"]["SHELL"])
    A("")
    A("## Python / package managers")
    p = r["python"]
    A("- python: %s  (`%s`)" % (p["version"], p["executable"]))
    A("- active_env: %s" % (p["active_env"] or "(none)"))
    A("- in Topaz supported range %s: **%s**" % (p["topaz_python_requires"], p["in_topaz_supported_range"]))
    pm = r["package_managers"]
    A("- conda: %s | mamba: %s | micromamba: %s | pip: %s"
      % (pm["conda"]["available"], pm["mamba"]["available"],
         pm["micromamba"]["available"], pm["pip"]["available"]))
    A("")
    A("## Topaz install")
    t = r["topaz"]
    A("- **installed:** **%s**" % t["installed"])
    A("- executable: %s" % (t["executable"] or "(none)"))
    A("- version: %s" % (t["version"] or "(unknown)"))
    A("- help_captured: %s | subcommands: %s"
      % (t["help_captured"], ", ".join(t["subcommands_captured"]) or "(none)"))
    for n in t.get("notes", []):
        A("- note: %s" % n)
    A("")
    A("## Devices  (sourced evidence, not PyTorch inference)")
    d = r["devices"]
    A("- **topaz_cpu_supported:** %s" % d["topaz_cpu_supported"])
    A("- **topaz_cuda_supported:** %s" % d["topaz_cuda_supported"])
    A("- **topaz_mps_supported:** %s  <- Apple-Silicon GPU is NOT used by Topaz" % d["topaz_mps_supported"])
    A("- nvidia-smi: %s (%d GPU(s))" % (d["nvidia"]["nvidia_smi"], len(d["nvidia"]["gpus"])))
    tinfo = d["torch"]
    A("- torch: available=%s cuda=%s mps=%s"
      % (tinfo.get("torch_available"), tinfo.get("cuda_available"), tinfo.get("mps_available")))
    u = d["usability_here"]
    A("- cuda_usable_here: %s (%s)" % (u["cuda_usable_here"], u["cuda_usable_note"]))
    A("- mps_usable_here: %s (%s)" % (u["mps_usable_here"], u["mps_usable_note"]))
    A("- evidence commit: %s (%s)" % (d["device_support_evidence"]["evidence_commit"],
                                      d["device_support_evidence"]["evidence_tag"]))
    A("")
    A("## Validation / blocked capabilities")
    A("- validation_status: **%s**" % r["validation_status"])
    if r["blocked_capabilities"]:
        A("- blocked_capabilities:")
        for b in r["blocked_capabilities"]:
            A("  - %s" % b)
    else:
        A("- blocked_capabilities: (none)")
    for n in r["notes"]:
        A("- note: %s" % n)
    A("")
    A("- staleness_policy: %s" % r["staleness_policy"])
    A("")
    A("## Source snapshot")
    s = r["source_snapshot"]
    A("- %s @ %s (%s), fetched %s" % (s["repo_url"], s["commit_or_tag"], s["commit"][:12], s["fetched_at"]))
    A("")
    return "\n".join(L)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="topaz_env_probe.py",
        description="Read-only environment/config probe for the Topaz skill. "
                    "Never installs anything and never runs a Topaz compute job.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Device support fields are grounded in Topaz source at %s (%s), not "
               "inferred from PyTorch MPS availability."
               % (SOURCE_EVIDENCE["tag"], SOURCE_EVIDENCE["commit"][:12]),
    )
    parser.add_argument("--output", metavar="PATH", default=None,
                        help="write the report to PATH (also printed to stdout)")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown",
                        help="output format (default: markdown)")
    parser.add_argument("--project-path", metavar="PATH", default=None,
                        help="optional target project directory to record (not scanned)")
    parser.add_argument("--check-torch", action="store_true",
                        help="probe torch CUDA/MPS in an isolated subprocess "
                             "(default: OFF; avoids importing torch). Note: a "
                             "CUDA-13/cu130 torch wheel reports cuda=False on a "
                             "CUDA-12.x driver; pin a cu12x build if so.")
    parser.add_argument("--topaz", metavar="PATH", default=None,
                        help="explicit path to the topaz executable (default: search PATH)")
    parser.add_argument("--no-topaz-exec", action="store_true",
                        help="do NOT invoke topaz --version/--help; detect by filesystem only")
    args = parser.parse_args(argv)

    report = build_report(args)

    if args.format == "json":
        text = json.dumps(report, indent=2, sort_keys=False)
    else:
        text = render_markdown(report)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            sys.stderr.write("[topaz_env_probe] wrote %s (%s)\n" % (args.output, args.format))
        except Exception as exc:
            sys.stderr.write("[topaz_env_probe] ERROR writing %s: %s\n" % (args.output, exc))
            print(text)
            return 1

    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
