#!/usr/bin/env python3
"""Probe a machine for CryoAtom2 readiness and emit / validate a site config.

Read-only by default. It inspects host identity, container runtimes, the
scheduler, visible GPUs, the launcher, and the external weight cache. It runs
nothing from CryoAtom unless --live-version is given, and that only executes
`<launcher> --version`, which never opens a checkpoint.

  probe and print a verdict (writes nothing):
      python3 cryoatom_env_probe.py --route container --image /path/cryoatom.sif

  write a site config:
      python3 cryoatom_env_probe.py ... --output ~/.config/cryoatom-skill/site-config.json

  re-check an existing config against the machine you are on:
      python3 cryoatom_env_probe.py --validate-config ~/.config/cryoatom-skill/site-config.json

Exit codes: 0 ready, 1 probed, 2 stale, 3 blocked, 4 unknown (no/unreadable
config). An argparse usage error also exits 2, but prints usage to stderr and
no JSON, so the two are distinguishable.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys

SCHEMA_VERSION = "1.0"
PROBE_VERSION = "1.0"

EXPECTED_VERSION = "2.1.1"
SOURCE_COMMIT = "856e250df7b784b854b892f1b619d32d51188cef"
SOURCE_TREE = "0058c0c68857b66962f9ad421756513e74de7518"

IN_IMAGE_BINARY = "/opt/conda/envs/CryoAtom2/bin/cryoatom"
IN_IMAGE_CHECKPOINT_DIR = (
    "/opt/conda/envs/CryoAtom2/lib/python3.9/site-packages/CryoAtom2/checkpoint"
)

MIN_VRAM_GIB = 14

# The six weight files and their exact byte sizes, observed at the pinned
# revision. Sizes are upstream facts, not host facts.
WEIGHT_FILES = [
    ("checkpoint/RUNet.pth", 151641598),
    ("checkpoint/CryoNet.pth", 847721570),
    ("checkpoint/CryoNet_no_seq.pth", 771564842),
    ("torch/hub/checkpoints/RNA-FM_pretrained.pth", 1194424423),
    ("torch/hub/checkpoints/esm2_t33_650M_UR50D.pt", 2604537549),
    ("torch/hub/checkpoints/esm2_t33_650M_UR50D-contact-regression.pt", 3687),
]

CONTAINER_RUNTIMES = ("apptainer", "singularity", "podman", "docker")
STATE_EXIT = {"ready": 0, "probed": 1, "stale": 2, "blocked": 3, "unknown": 4}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def run(cmd, timeout=30):
    """Run a short command, return (rc, stdout, stderr). Never raises."""
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def parse_version_output(text):
    """'CryoAtom 2.1.1' / 'cryoatom, version 2.1.1' -> '2.1.1'."""
    for token in (text or "").replace(",", " ").split():
        cleaned = token.strip().lstrip("vV")
        parts = cleaned.split(".")
        if len(parts) >= 2 and all(p.isdigit() for p in parts):
            return cleaned
    return None


def host_matches(hostname, patterns):
    if not patterns:
        return True
    return any(fnmatch.fnmatch(hostname, p) for p in patterns)


# --------------------------------------------------------------------------
# detection
# --------------------------------------------------------------------------
def default_host_patterns(hostname):
    """The probe runs on one node; a cluster has many. Default to this host plus
    its domain, so a config generated on a login node still describes the compute
    nodes. Override with --host-pattern when that is too wide or too narrow."""
    patterns = [hostname]
    labels = hostname.split(".")
    if len(labels) >= 3:
        patterns.append("*." + ".".join(labels[1:]))
    return patterns


def detect_host():
    hostname = socket.gethostname()
    return {
        "hostname": hostname,
        "patterns": default_host_patterns(hostname),
        "os": platform.system(),
        "os_release": _os_release_name(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
    }


def _os_release_name():
    try:
        with open("/etc/os-release") as fh:
            for line in fh:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def detect_container_runtimes():
    found = {}
    for name in CONTAINER_RUNTIMES:
        path = shutil.which(name)
        if not path:
            continue
        rc, out, _ = run([path, "--version"], timeout=20)
        found[name] = {"path": path, "version": out if rc == 0 else None}
    return found


def detect_scheduler(preference="auto"):
    table = [
        ("slurm", "sbatch", "--gpus=1"),
        ("pbs", "qsub", "-l select=1:ngpus=1"),
        ("lsf", "bsub", '-gpu "num=1"'),
    ]
    # `qsub` is PBS Pro, OpenPBS, Torque or SGE depending on the site, and their
    # GPU syntax differs. The flag below is the PBS Pro form: treat it as a
    # starting point to confirm, not a detected fact.
    if preference not in ("auto", None):
        for kind, submit, gpu_flag in table:
            if kind == preference:
                return {"type": kind, "submit_command": shutil.which(submit) or submit,
                        "gpu_flag": gpu_flag, "detected_from": "--scheduler %s" % preference,
                        "gpu_flag_confirmed": False}
        return {"type": preference, "submit_command": None, "gpu_flag": None,
                "detected_from": "--scheduler %s" % preference, "gpu_flag_confirmed": False}
    for kind, submit, gpu_flag in table:
        path = shutil.which(submit)
        if path:
            return {"type": kind, "submit_command": path, "gpu_flag": gpu_flag,
                    "detected_from": "%s on PATH" % submit, "gpu_flag_confirmed": False}
    return {"type": "local", "submit_command": None, "gpu_flag": None,
            "detected_from": "no submit command on PATH", "gpu_flag_confirmed": False}


def detect_gpus():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"gpu_visible": False, "gpus": [], "nvidia_smi": None,
                "note": "nvidia-smi not on PATH"}
    rc, out, err = run(
        [smi, "--query-gpu=name,memory.total,driver_version",
         "--format=csv,noheader,nounits"], timeout=30)
    if rc != 0 or not out:
        return {"gpu_visible": False, "gpus": [], "nvidia_smi": smi,
                "note": (err or "nvidia-smi returned no devices")[:200]}
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            mib = int(float(parts[1]))
        except ValueError:
            mib = None
        gpus.append({"name": parts[0], "memory_mib": mib, "driver": parts[2]})
    return {"gpu_visible": bool(gpus), "gpus": gpus, "nvidia_smi": smi, "note": None}


def inspect_weights(cache_root, pin_file=None, mode="size"):
    """Presence/size (and optionally SHA-256) of the six weight files."""
    result = {
        "cache_root": cache_root,
        "pin_file": pin_file,
        "files": {},
        "complete": False,
        "mismatched": [],
        "missing": [],
        "verified_mode": None,
    }
    if not cache_root:
        return result

    pin = None
    if pin_file and os.path.isfile(pin_file):
        try:
            with open(pin_file) as fh:
                pin = json.load(fh).get("files", {})
        except (OSError, ValueError):
            pin = None

    ok = True
    for rel, want_bytes in WEIGHT_FILES:
        path = os.path.join(cache_root, rel)
        entry = {"present": False, "bytes": None, "expected_bytes": want_bytes,
                 "sha256": None, "status": "missing"}
        if pin and rel in pin:
            entry["expected_bytes"] = pin[rel].get("bytes", want_bytes)
            entry["expected_sha256"] = pin[rel].get("sha256")
        if os.path.isfile(path):
            entry["present"] = True
            entry["bytes"] = os.path.getsize(path)
            if entry["bytes"] != entry["expected_bytes"]:
                entry["status"] = "size-mismatch"
                result["mismatched"].append(rel)
                ok = False
            else:
                entry["status"] = "ok"
                if mode == "sha256":
                    entry["sha256"] = sha256_of(path)
                    want_sha = entry.get("expected_sha256")
                    if want_sha and entry["sha256"] != want_sha:
                        entry["status"] = "sha256-mismatch"
                        result["mismatched"].append(rel)
                        ok = False
        else:
            result["missing"].append(rel)
            ok = False
        result["files"][rel] = entry

    result["complete"] = ok
    result["verified_mode"] = mode if cache_root else None
    return result


def live_version(launcher, timeout=180):
    """`<launcher> --version` — never opens a checkpoint, safe on a login node."""
    if not launcher or not os.path.isfile(launcher):
        return None, "launcher not found"
    rc, out, err = run([launcher, "--version"], timeout=timeout)
    if rc != 0:
        return None, (err or out or "non-zero exit")[:300]
    return parse_version_output(out), None


# --------------------------------------------------------------------------
# config skeleton and state machine
# --------------------------------------------------------------------------
def default_config():
    return {
        "schema_version": SCHEMA_VERSION,
        "profile": None,
        "generated_at": None,
        "generated_by": "cryoatom_env_probe.py " + PROBE_VERSION,
        "host": {"hostname": None, "patterns": [], "os": None, "os_release": None,
                 "kernel": None, "architecture": None},
        "install": {
            "route": "container",
            "container_runtime": None,
            "container_runtime_version": None,
            "container_runtimes_available": {},
            "image_path": None,
            "image_sha256": None,
            "image_observed_sha256": None,
            "no_mount_hostfs": False,
            "extra_binds": [],
            "launcher": None,
            "launcher_executable": False,
            "in_image_binary": IN_IMAGE_BINARY,
            "in_image_checkpoint_dir": IN_IMAGE_CHECKPOINT_DIR,
            "conda_env_prefix": None,
            "module_load": None,
        },
        "version": {
            "expected": EXPECTED_VERSION,
            "observed": None,
            "source_commit": SOURCE_COMMIT,
            "source_tree": SOURCE_TREE,
            "checked_at": None,
            "check_error": None,
        },
        "weights": {"cache_root": None, "pin_file": None, "files": {},
                    "complete": False, "verified_mode": None,
                    "missing": [], "mismatched": []},
        "compute": {"gpu_visible": False, "gpus": [],
                    "min_vram_gib_required": MIN_VRAM_GIB,
                    "meets_vram_requirement": None, "note": None},
        "scheduler": {"type": "local", "submit_command": None, "account": None,
                      "gpu_partition": None, "build_partition": None,
                      "gpu_flag": None, "cpus_per_task": None, "memory_gb": None,
                      "default_time": "04:00:00", "scratch_root": None,
                      "extra_directives": [], "detected_from": None,
                      "gpu_flag_confirmed": False},
        "paths": {"results_root": None, "fixture_dir": None, "log_dir": None,
                  "build_tmp_root": None},
        "validation": {"state": "unknown", "reasons": [], "fixture_validated": False,
                       "fixture_job": None, "fixture_elapsed_s": None,
                       "validated_gpu": None, "validated_at": None, "evidence": []},
    }


def compute_state(cfg, hostname=None):
    """Pure function: (state, reasons). Severity order blocked > stale > probed."""
    blocked, stale, gaps = [], [], []

    host = cfg.get("host", {})
    install = cfg.get("install", {})
    version = cfg.get("version", {})
    weights = cfg.get("weights", {})
    compute = cfg.get("compute", {})
    sched = cfg.get("scheduler", {})
    valid = cfg.get("validation", {})

    if (host.get("os") or "") != "Linux":
        blocked.append("host OS is %r; CryoAtom2 requires Linux" % host.get("os"))

    if hostname is not None and not host_matches(hostname, host.get("patterns") or []):
        stale.append("hostname %r matches none of the config patterns %s"
                     % (hostname, host.get("patterns")))

    route = install.get("route")
    if route == "container":
        runtime = install.get("container_runtime")
        if not runtime:
            blocked.append("container route selected but no container runtime found")
        image = install.get("image_path")
        if not image:
            blocked.append("container route selected but install.image_path is unset")
        elif runtime in ("apptainer", "singularity") and not os.path.isfile(image):
            # docker/podman take a store reference (name:tag, name@sha256:...),
            # which is not a path and must not be stat'ed.
            blocked.append("container image file not found: %s" % image)
        want_sha = install.get("image_sha256")
        got_sha = install.get("image_observed_sha256")
        if want_sha and got_sha and want_sha != got_sha:
            stale.append("image sha256 differs from the recorded one (rebuild?)")
    elif route == "native":
        prefix = install.get("conda_env_prefix")
        if not prefix:
            blocked.append("native route selected but install.conda_env_prefix is unset")
        elif not os.path.isfile(os.path.join(prefix, "bin", "cryoatom")):
            blocked.append("no cryoatom entry point under %s/bin" % prefix)
    elif route in ("module", "preinstalled"):
        if not install.get("launcher") and not install.get("module_load"):
            blocked.append("%s route needs install.launcher or install.module_load" % route)
    else:
        blocked.append("unknown install.route %r" % route)

    launcher = install.get("launcher")
    if not launcher:
        gaps.append("no launcher recorded; install scripts/cryoatom_launcher.sh and re-probe")
    elif not os.path.isfile(launcher):
        blocked.append("launcher not found: %s" % launcher)
    elif not os.access(launcher, os.X_OK):
        blocked.append("launcher is not executable: %s" % launcher)

    observed = version.get("observed")
    expected = version.get("expected")
    if not observed:
        gaps.append("version not verified at runtime; re-run with --live-version")
    elif expected and observed != expected:
        stale.append("installed version %s != expected %s" % (observed, expected))

    if not weights.get("cache_root"):
        blocked.append("no weight cache configured; see references/02_install_routes.md §5")
    elif weights.get("missing"):
        blocked.append("weight cache incomplete: missing %s"
                       % ", ".join(weights["missing"][:6]))
    elif weights.get("mismatched"):
        stale.append("weight cache mismatch: %s" % ", ".join(weights["mismatched"][:6]))
    elif not weights.get("complete"):
        gaps.append("weight cache not verified")

    fixture_ok = bool(valid.get("fixture_validated"))
    gpus = compute.get("gpus") or []
    meets = compute.get("meets_vram_requirement")
    need = compute.get("min_vram_gib_required") or MIN_VRAM_GIB
    # A scheduler can hand out GPUs by partition/queue OR by generic resource,
    # so either is evidence that a GPU is reachable from this submit host.
    queue_gpu = bool(sched.get("gpu_partition")) or (
        sched.get("type") not in (None, "local") and bool(sched.get("gpu_flag")))

    if compute.get("gpu_visible") and meets is False and not queue_gpu:
        # Directly attached GPUs, none big enough, and no queue to reach a
        # bigger one. A fixture receipt cannot make this host adequate.
        biggest = max((g.get("memory_mib") or 0) for g in gpus) if gpus else 0
        blocked.append("largest visible GPU has %d MiB; CryoAtom2 documents >= %d GiB"
                       % (biggest, need))
    elif not compute.get("gpu_visible") and not queue_gpu:
        blocked.append("no NVIDIA GPU visible and no GPU partition or GPU resource flag "
                       "configured; this host cannot reach a GPU")
    elif fixture_ok:
        pass  # a passed fixture run on a reachable GPU is the strongest evidence
    elif compute.get("gpu_visible") and meets:
        gaps.append("no fixture run recorded; run the public fixture before claiming ready")
    else:
        gaps.append("no GPU visible from this node, but the scheduler is configured to "
                    "reach one (%s); no fixture run is recorded yet"
                    % (sched.get("gpu_partition") or sched.get("gpu_flag")))

    if blocked:
        return "blocked", blocked + stale + gaps
    if stale:
        return "stale", stale + gaps
    if gaps:
        return "probed", gaps
    return "ready", []


# --------------------------------------------------------------------------
# probe assembly
# --------------------------------------------------------------------------
def build_config(args):
    cfg = default_config()
    cfg["profile"] = args.profile or socket.gethostname()
    cfg["generated_at"] = now_iso()
    cfg["host"] = detect_host()
    if args.host_pattern:
        cfg["host"]["patterns"] = list(args.host_pattern)

    runtimes = detect_container_runtimes()
    inst = cfg["install"]
    inst["container_runtimes_available"] = runtimes
    inst["route"] = args.route

    if args.route == "container":
        chosen = args.container_runtime
        if chosen in (None, "auto"):
            chosen = next((n for n in CONTAINER_RUNTIMES if n in runtimes), None)
        inst["container_runtime"] = chosen
        if chosen and chosen in runtimes:
            inst["container_runtime_version"] = runtimes[chosen]["version"]
    inst["image_path"] = args.image
    inst["image_sha256"] = args.image_sha256
    inst["no_mount_hostfs"] = bool(args.no_mount_hostfs)
    inst["extra_binds"] = list(args.extra_bind or [])
    inst["launcher"] = args.launcher
    inst["conda_env_prefix"] = args.conda_env_prefix
    inst["module_load"] = args.module_load
    if args.launcher:
        inst["launcher_executable"] = (os.path.isfile(args.launcher)
                                       and os.access(args.launcher, os.X_OK))
    if args.image and args.hash_image and os.path.isfile(args.image):
        inst["image_observed_sha256"] = sha256_of(args.image)

    cfg["version"]["expected"] = args.expected_version
    if args.live_version:
        observed, err = live_version(args.launcher)
        cfg["version"]["observed"] = observed
        cfg["version"]["check_error"] = err
        cfg["version"]["checked_at"] = now_iso()

    cache = args.weights_cache
    pin = args.pin_file or (os.path.join(cache, "weights.pin.json") if cache else None)
    winfo = inspect_weights(cache, pin, args.verify_weights)
    cfg["weights"] = {"cache_root": cache, "pin_file": pin, "files": winfo["files"],
                      "complete": winfo["complete"], "verified_mode": winfo["verified_mode"],
                      "missing": winfo["missing"], "mismatched": winfo["mismatched"]}

    gpu = detect_gpus()
    need_mib = MIN_VRAM_GIB * 1024
    meets = None
    if gpu["gpus"]:
        meets = any((g.get("memory_mib") or 0) >= need_mib for g in gpu["gpus"])
    cfg["compute"] = {"gpu_visible": gpu["gpu_visible"], "gpus": gpu["gpus"],
                      "min_vram_gib_required": MIN_VRAM_GIB,
                      "meets_vram_requirement": meets, "note": gpu["note"]}

    sched = detect_scheduler(args.scheduler)
    cfg["scheduler"].update(sched)
    for key, value in (("account", args.account), ("gpu_partition", args.gpu_partition),
                       ("build_partition", args.build_partition),
                       ("cpus_per_task", args.cpus_per_task),
                       ("memory_gb", args.memory_gb),
                       ("scratch_root", args.scratch_root)):
        if value is not None:
            cfg["scheduler"][key] = value
    if args.gpu_flag:
        cfg["scheduler"]["gpu_flag"] = args.gpu_flag
    if args.default_time:
        cfg["scheduler"]["default_time"] = args.default_time

    cfg["paths"] = {"results_root": args.results_root,
                    "fixture_dir": args.fixture_dir or (
                        os.path.join(cache, "fixture") if cache else None),
                    "log_dir": args.log_dir,
                    "build_tmp_root": args.build_tmp_root}

    if args.record_fixture:
        cfg["validation"]["fixture_validated"] = True
        cfg["validation"]["fixture_job"] = args.fixture_job
        cfg["validation"]["fixture_elapsed_s"] = args.fixture_elapsed_s
        cfg["validation"]["validated_gpu"] = args.fixture_gpu
        cfg["validation"]["validated_at"] = now_iso()
        cfg["validation"]["evidence"].append(
            "public fixture EMD-33198/7XHT run recorded by --record-fixture")

    state, reasons = compute_state(cfg, hostname=cfg["host"]["hostname"])
    cfg["validation"]["state"] = state
    cfg["validation"]["reasons"] = reasons
    return cfg


def revalidate(path, verify_mode="size", hash_image=False):
    with open(path) as fh:
        cfg = json.load(fh)
    if cfg.get("schema_version") != SCHEMA_VERSION:
        return cfg, "unknown", ["unsupported schema_version %r (expected %s)"
                                % (cfg.get("schema_version"), SCHEMA_VERSION)]

    inst = cfg.setdefault("install", {})
    launcher = inst.get("launcher")
    if launcher:
        inst["launcher_executable"] = (os.path.isfile(launcher)
                                       and os.access(launcher, os.X_OK))
    # The recorded container runtime may not exist on the machine we are on now.
    runtimes = detect_container_runtimes()
    inst["container_runtimes_available"] = runtimes
    if inst.get("route") == "container":
        recorded = inst.get("container_runtime")
        if recorded and recorded not in runtimes:
            inst["container_runtime"] = None      # compute_state -> blocked
    if hash_image and inst.get("image_path") and os.path.isfile(inst["image_path"]):
        inst["image_observed_sha256"] = sha256_of(inst["image_path"])

    w = cfg.setdefault("weights", {})
    winfo = inspect_weights(w.get("cache_root"), w.get("pin_file"), verify_mode)
    w.update({"files": winfo["files"], "complete": winfo["complete"],
              "verified_mode": winfo["verified_mode"],
              "missing": winfo["missing"], "mismatched": winfo["mismatched"]})

    gpu = detect_gpus()
    need_mib = MIN_VRAM_GIB * 1024
    meets = any((g.get("memory_mib") or 0) >= need_mib for g in gpu["gpus"]) if gpu["gpus"] else None
    cfg.setdefault("compute", {}).update(
        {"gpu_visible": gpu["gpu_visible"], "gpus": gpu["gpus"],
         "meets_vram_requirement": meets, "note": gpu["note"]})

    state, reasons = compute_state(cfg, hostname=socket.gethostname())
    # --full must show the verdict computed NOW, not the one stored at write time.
    validation = cfg.setdefault("validation", {})
    validation["state"] = state
    validation["reasons"] = reasons
    validation["revalidated_at"] = now_iso()
    return cfg, state, reasons


def summarize(cfg, state, reasons, written=None):
    inst = cfg.get("install", {})
    return {
        "state": state,
        "reasons": reasons,
        "profile": cfg.get("profile"),
        "hostname": cfg.get("host", {}).get("hostname"),
        "route": inst.get("route"),
        "container_runtime": inst.get("container_runtime"),
        "launcher": inst.get("launcher"),
        "image_path": inst.get("image_path"),
        "version_expected": cfg.get("version", {}).get("expected"),
        "version_observed": cfg.get("version", {}).get("observed"),
        "weights_cache": cfg.get("weights", {}).get("cache_root"),
        "weights_complete": cfg.get("weights", {}).get("complete"),
        "weights_missing": cfg.get("weights", {}).get("missing"),
        "gpus": cfg.get("compute", {}).get("gpus"),
        "scheduler": cfg.get("scheduler", {}).get("type"),
        "gpu_partition": cfg.get("scheduler", {}).get("gpu_partition"),
        "fixture_validated": cfg.get("validation", {}).get("fixture_validated"),
        "config_written": written,
    }


def write_config(cfg, path, force):
    path = os.path.expanduser(path)
    if os.path.exists(path) and not force:
        raise SystemExit("refusing to overwrite existing config %s (use --force)" % path)
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, mode=0o700)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(cfg, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------
def self_test():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    check(len(WEIGHT_FILES) == 6, "weight table must list six files")
    check(parse_version_output("CryoAtom 2.1.1") == "2.1.1", "version parse (plain)")
    check(parse_version_output("cryoatom, version 2.1.1") == "2.1.1", "version parse (comma)")
    check(parse_version_output("no version here") is None, "version parse (absent)")
    check(host_matches("gcn12.local", ["gcn*", "login*"]), "glob match")
    check(not host_matches("other.example", ["gcn*"]), "glob non-match")
    check(host_matches("anything", []), "empty pattern list matches")

    def cfg_ready():
        c = default_config()
        c["host"].update({"hostname": "h1", "patterns": ["h1"], "os": "Linux"})
        c["install"].update({"route": "preinstalled", "launcher": sys.executable,
                             "launcher_executable": True})
        c["version"]["observed"] = EXPECTED_VERSION
        c["weights"].update({"cache_root": "/tmp/cache", "complete": True,
                             "missing": [], "mismatched": []})
        c["compute"].update({"gpu_visible": True, "meets_vram_requirement": True,
                             "gpus": [{"name": "X", "memory_mib": 40960, "driver": "1"}]})
        c["validation"]["fixture_validated"] = True
        return c

    state, reasons = compute_state(cfg_ready(), hostname="h1")
    check(state == "ready", "expected ready, got %s (%s)" % (state, reasons))

    c = cfg_ready(); c["version"]["observed"] = None
    check(compute_state(c, "h1")[0] == "probed", "missing live version -> probed")

    c = cfg_ready(); c["version"]["observed"] = "2.0.0"
    check(compute_state(c, "h1")[0] == "stale", "version drift -> stale")

    c = cfg_ready(); c["weights"]["missing"] = ["checkpoint/RUNet.pth"]
    check(compute_state(c, "h1")[0] == "blocked", "missing weight -> blocked")

    c = cfg_ready(); c["weights"]["mismatched"] = ["checkpoint/RUNet.pth"]
    check(compute_state(c, "h1")[0] == "stale", "weight mismatch -> stale")

    c = cfg_ready(); c["host"]["os"] = "Darwin"
    check(compute_state(c, "h1")[0] == "blocked", "non-Linux -> blocked")

    c = cfg_ready()
    check(compute_state(c, "other-host")[0] == "stale", "hostname mismatch -> stale")

    # login node: no GPU visible, GPU partition configured, no fixture yet
    c = cfg_ready()
    c["compute"].update({"gpu_visible": False, "gpus": [], "meets_vram_requirement": None})
    c["validation"]["fixture_validated"] = False
    c["scheduler"]["gpu_partition"] = "gpu"
    state, reasons = compute_state(c, "h1")
    check(state == "probed", "submit host -> probed, got %s" % state)
    check(any("scheduler is configured to reach one" in r for r in reasons),
          "submit-host reason present, got %s" % reasons)

    # same submit host, GPU selected by generic resource rather than partition
    c["scheduler"].update({"gpu_partition": None, "type": "slurm", "gpu_flag": "--gres=gpu:1"})
    check(compute_state(c, "h1")[0] == "probed", "gres-only submit host -> probed")

    # once the fixture has run there, it is ready
    c["validation"]["fixture_validated"] = True
    check(compute_state(c, "h1")[0] == "ready", "submit host + fixture -> ready")

    # no GPU anywhere: a fixture receipt must NOT rescue it
    c["scheduler"].update({"gpu_partition": None, "gpu_flag": None, "type": "local"})
    check(compute_state(c, "h1")[0] == "blocked",
          "no GPU, no queue, even with a fixture -> blocked")

    # small GPU, no queue: blocked with or without a fixture receipt
    for fixture in (False, True):
        c = cfg_ready()
        c["validation"]["fixture_validated"] = fixture
        c["scheduler"].update({"gpu_partition": None, "gpu_flag": None, "type": "local"})
        c["compute"].update({"gpus": [{"name": "small", "memory_mib": 8192, "driver": "1"}],
                             "meets_vram_requirement": False})
        check(compute_state(c, "h1")[0] == "blocked",
              "GPU under 14 GiB (fixture=%s) -> blocked" % fixture)

    # small local GPU but a queue that reaches a real one: not blocked
    c = cfg_ready()
    c["validation"]["fixture_validated"] = True
    c["compute"].update({"gpus": [{"name": "small", "memory_mib": 8192, "driver": "1"}],
                         "meets_vram_requirement": False})
    c["scheduler"]["gpu_partition"] = "gpu"
    check(compute_state(c, "h1")[0] == "ready", "small local GPU + GPU queue + fixture -> ready")

    # container route without an image
    c = cfg_ready()
    c["install"].update({"route": "container", "container_runtime": "apptainer",
                         "image_path": None})
    check(compute_state(c, "h1")[0] == "blocked", "container route without image -> blocked")

    # weight inspection against an empty directory reports every file missing
    winfo = inspect_weights("/nonexistent-cryoatom-cache")
    check(len(winfo["missing"]) == 6 and not winfo["complete"], "empty cache -> 6 missing")

    print(json.dumps({"self_test": "ok" if not failures else "failed",
                      "failures": failures}, indent=2))
    return 0 if not failures else 1


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile")
    ap.add_argument("--route", choices=("container", "native", "module", "preinstalled"),
                    default="container")
    ap.add_argument("--container-runtime", choices=CONTAINER_RUNTIMES + ("auto",),
                    default="auto")
    ap.add_argument("--image", help="container image path")
    ap.add_argument("--image-sha256", help="expected image SHA-256")
    ap.add_argument("--hash-image", action="store_true",
                    help="hash the image now (multi-GiB read)")
    ap.add_argument("--launcher", help="absolute path to the cryoatom launcher")
    ap.add_argument("--conda-env-prefix", help="native route: conda env prefix")
    ap.add_argument("--module-load", help="module route: the module load line")
    ap.add_argument("--no-mount-hostfs", action="store_true",
                    help="record that the container needs --no-mount hostfs")
    ap.add_argument("--extra-bind", action="append",
                    help="site filesystem the container must see (repeatable)")
    ap.add_argument("--weights-cache", help="external weight cache root")
    ap.add_argument("--pin-file", help="weights.pin.json (defaults to <cache>/weights.pin.json)")
    ap.add_argument("--verify-weights", choices=("size", "sha256"), default="size")
    ap.add_argument("--expected-version", default=EXPECTED_VERSION)
    ap.add_argument("--live-version", action="store_true",
                    help="run `<launcher> --version` (opens no checkpoint)")
    ap.add_argument("--scheduler", default="auto",
                    choices=("auto", "local", "slurm", "pbs", "lsf"))
    ap.add_argument("--account")
    ap.add_argument("--gpu-partition")
    ap.add_argument("--build-partition")
    ap.add_argument("--gpu-flag")
    ap.add_argument("--cpus-per-task", type=int)
    ap.add_argument("--memory-gb", type=int)
    ap.add_argument("--default-time")
    ap.add_argument("--scratch-root")
    ap.add_argument("--results-root")
    ap.add_argument("--fixture-dir")
    ap.add_argument("--log-dir")
    ap.add_argument("--build-tmp-root")
    ap.add_argument("--host-pattern", action="append",
                    help="hostname glob this config may describe (repeatable)")
    ap.add_argument("--record-fixture", action="store_true",
                    help="record that the public fixture run passed on this install")
    ap.add_argument("--fixture-job")
    ap.add_argument("--fixture-gpu")
    ap.add_argument("--fixture-elapsed-s", type=int)
    ap.add_argument("--output", help="write the site config here")
    ap.add_argument("--force", action="store_true", help="overwrite an existing config")
    ap.add_argument("--validate-config", help="re-check an existing config on this host")
    ap.add_argument("--full", action="store_true", help="print the whole config, not a summary")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.validate_config:
        path = os.path.expanduser(args.validate_config)
        if not os.path.isfile(path):
            print(json.dumps({"state": "unknown",
                              "reasons": ["config not found: %s" % path]}, indent=2))
            return STATE_EXIT["unknown"]
        try:
            cfg, state, reasons = revalidate(path, args.verify_weights, args.hash_image)
        except ValueError as exc:
            print(json.dumps({"state": "unknown",
                              "reasons": ["config is not valid JSON: %s" % exc]}, indent=2))
            return STATE_EXIT["unknown"]
        out = cfg if args.full else summarize(cfg, state, reasons)
        print(json.dumps(out, indent=2, sort_keys=True))
        return STATE_EXIT.get(state, 4)

    cfg = build_config(args)
    state = cfg["validation"]["state"]
    reasons = cfg["validation"]["reasons"]
    written = write_config(cfg, args.output, args.force) if args.output else None
    out = cfg if args.full else summarize(cfg, state, reasons, written)
    print(json.dumps(out, indent=2, sort_keys=True))
    return STATE_EXIT.get(state, 4)


if __name__ == "__main__":
    sys.exit(main())
