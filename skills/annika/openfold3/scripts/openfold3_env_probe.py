#!/usr/bin/env python3
"""Read-only host probe for the openfold3 skill (OpenFold3 + the Anthropic optimization kits).

Design contract (why this is safe to run anywhere):
  - Python 3.9+ standard library only. No third-party imports.
  - The DEFAULT run is read-only: no writes, no mkdir, no downloads, no network,
    and no in-process import of torch or openfold3. Package versions come from
    importlib.metadata / dist-info file names (metadata only, nothing imported).
  - Every external command (nvidia-smi, container runtimes' --version) runs in a
    subprocess with a timeout, stdin closed, in its own process group.
  - --hash (opt-in) reads the whole checkpoint (~2.3 GB) to compute its sha256.
  - --deep (opt-in) runs the installed OpenFold3 CLI or kit dry run in a timed
    subprocess. That MAY create cache files (see --help, "Deep mode").
  - $HOME is shown as ~ in the output unless --no-redact is given.

The machine running the agent is not assumed to be the OpenFold3 runtime. This
probe answers "what is here, and what may this host do?" so the skill can move
UNCONFIGURED -> PROBED -> VALIDATED on evidence. It never reports VALIDATED:
that needs a recorded GPU prediction on a public input.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

PROBE_VERSION = "1.0.0"

# Pinned facts (openfold-3@v0.5.0:openfold3/entry_points/parameters.py;
# uplifting-biomolecular-modeling@f4f62fa:openfold3_ob0/stock/PINS.json and openfold3/stock/PINS.json).
OB0_FILE = "of3-ob-2025-06-30-174k.pt"
OB0_BYTES = 2287872989
OB0_SHA256 = "bd43301c011d5f87580d3e8b548658869433e4488399feb03035ba248f8e29e4"
P2_155K_SHA256 = "3ae79a701f55dbc184002d010c92d347a35faabb981314c2fd1325211af40b77"
KNOWN_CKPTS = {
    OB0_FILE: ("openbind-2025-06-30-174k", "OpenBind-0 (default for openfold3 >=0.5.0)"),
    "of3-p2-155k.pt": ("openfold3-p2-155k", "preview-2 155k (legacy: openfold3 >=0.4,<0.4.4dev0 only)"),
    "of3-p2-145k.pt": ("openfold3-p2-145k", "preview-2 145k (legacy: openfold3 >=0.4,<0.4.4dev0 only)"),
    "of3_ft3_v1.pt": ("openfold3-p1", "preview-1 (legacy: openfold3 <0.4)"),
}
KNOWN_DIGESTS = {OB0_SHA256: "OpenBind-0 (of3-ob-2025-06-30-174k.pt)",
                 P2_155K_SHA256: "preview-2 155k (of3-p2-155k.pt)"}
KIT_PIN_VERSION = "0.5.0"

DEFAULT_CMDS = ["run_openfold", "setup_openfold", "openfold3-kit", "validate-openfold3-rocm"]
# Normalized distribution names (lower case, '-' and '.' -> '_'); cuequivariance* matched by prefix.
PACKAGES = ["openfold3", "openfold3_ob0_opt", "openfold3_opt", "opt_core", "torch", "triton",
            "deepspeed", "pytorch_lightning", "biotite", "rdkit"]
PKG_PREFIXES = ("cuequivariance",)
ENV_VARS = ["OPENFOLD_CACHE", "OPENFOLD3_OB0_CKPT", "OPENFOLD3_CKPT", "OPENFOLD3_OB0_OPT", "OPENFOLD3_OPT",
            "MODEL_OPT_JIT_ROOT", "TRITON_CACHE_DIR", "TORCH_EXTENSIONS_DIR", "XDG_CACHE_HOME", "TMPDIR",
            "OPENFOLD3_KIT_SIF", "CUDA_VISIBLE_DEVICES"]
# Kit switch families a stock process must not carry (openfold3_ob0/stock/PINS.json "stock_environment").
KIT_SWITCH_PREFIXES = ("OF3_", "OF3T_", "OF3O_", "OF3TP_", "BFTP_", "ROWPAIR_", "FPF_TRIMUL_V4_", "OPENFOLD3_OPT",
                       "OPENFOLD3_OB0_OPT", "CUBLAS_WORKSPACE_CONFIG", "CUDA_MPS_", "CUTLASS_PATH", "CUEQ_")
UPSTREAM_OWN_SWITCHES = ("OF3_TRITON_DYNAMIC_SHAPES", "OF3_TRITON_EXP2")
SLURM_VARS = ["SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_GPUS_ON_NODE", "SLURM_JOB_GPUS", "SLURM_GPUS",
              "SLURM_STEP_GPUS", "SLURM_CPUS_PER_TASK", "SLURM_NNODES"]
PREDICT_OPTIONS = ["--query-json", "--inference-ckpt-path", "--inference-ckpt-name", "--num-diffusion-samples",
                   "--num-model-seeds", "--runner-yaml", "--use-msa-server", "--use-templates", "--output-dir",
                   "--use_tf32"]
CONTAINER_RUNTIMES = ["apptainer", "singularity", "docker", "podman"]
WRAPPER_VARS = ["OPENFOLD3_KIT_SIF", "OPENFOLD_CACHE", "OPENFOLD3_OB0_CKPT", "OPENFOLD3_CKPT", "MODEL_OPT_JIT_ROOT"]
CACHE_VARS = {  # variable -> (library default when unset, what lands there)
    "TRITON_CACHE_DIR": ("~/.triton/cache", "Triton JIT kernels"),
    "TORCH_EXTENSIONS_DIR": ("~/.cache/torch_extensions", "torch C++/CUDA extension builds"),
    "XDG_CACHE_HOME": ("~/.cache", "the kit weights-digest memo and other tool caches"),
}
KIT_MIN_DRIVER = 570      # kit stack: CUDA 12.8
KIT_MIN_CC = (8, 0)
DOC_MIN_GPU_MIB = 32 * 1024
LOW_INODES = 100000

HOME = os.path.expanduser("~")
HOME_REAL = os.path.realpath(HOME)
_HOMES = sorted({h.rstrip(os.sep) for h in (HOME, HOME_REAL) if h and h.rstrip(os.sep)}, key=len, reverse=True)
# $HOME only as a whole path component: a home of <dir>/ab must not turn <dir>/abc into ~c.
_HOME_RE = re.compile(r"(?:%s)(?![\w.-])" % "|".join(re.escape(h) for h in _HOMES)) if _HOMES else None


# ------------------------------------------------------------------------------------------ helpers
def redact(obj):
    """Replace $HOME (and its realpath) with ~ in every string of a nested structure."""
    if isinstance(obj, str):
        return _HOME_RE.sub("~", obj) if _HOME_RE else obj
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def run(argv, timeout, merge=False):
    """Run a command with a timeout in its own process group; never raises."""
    t0 = time.monotonic()
    res = {"argv": list(argv), "rc": None, "out": "", "err": "", "elapsed_s": None, "timed_out": False,
           "error": None}
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT if merge else subprocess.PIPE,
                                universal_newlines=True, errors="replace", start_new_session=True)
    except (OSError, ValueError) as exc:
        res["error"] = str(exc)
        return res
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        res["timed_out"] = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        out, err = proc.communicate()
    res["rc"] = proc.returncode
    res["out"] = out or ""
    res["err"] = err or ""
    res["elapsed_s"] = round(time.monotonic() - t0, 2)
    return res


def norm_name(name):
    return re.sub(r"[-_.]+", "_", (name or "").strip().lower())


def wanted(norm):
    return norm in PACKAGES or norm.startswith(PKG_PREFIXES)


def under_home(path):
    if not path:
        return False
    rp = os.path.realpath(os.path.expanduser(path))
    for h in (HOME_REAL, os.path.abspath(HOME)):
        if h and h != os.sep and (rp == h or rp.startswith(h.rstrip(os.sep) + os.sep)):
            return True
    return False


def expand_home(value):
    """Expand ~, $HOME and ${HOME}; return None when other variables remain."""
    if value is None:
        return None
    v = value.strip().strip('"').strip("'")
    v = v.replace("${HOME}", HOME).replace("$HOME", HOME)
    v = os.path.expanduser(v)
    return None if "$" in v or not v else v


def parse_version(text):
    nums = re.findall(r"\d+", text or "")[:3]
    return tuple(int(n) for n in nums) if nums else None


def utc_mtime(path):
    try:
        return dt.datetime.fromtimestamp(os.stat(path).st_mtime, dt.timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return None


def read_text_head(path, limit=262144):
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit)
    except OSError:
        return None, False
    if b"\0" in data[:4096]:
        return None, True
    return data.decode("utf-8", "replace"), False


# ------------------------------------------------------------------------------------------ host
def probe_host():
    osr = None
    try:
        with open("/etc/os-release") as fh:
            for line in fh:
                if line.startswith("PRETTY_NAME="):
                    osr = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    if platform.system() == "Darwin":
        osr = "macOS " + (platform.mac_ver()[0] or "?")
    try:
        allowed = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        allowed = None
    libc = platform.libc_ver()
    return {"hostname": socket.gethostname(), "os": platform.system(), "os_release": osr,
            "kernel": platform.release(), "arch": platform.machine(), "cpu_count": os.cpu_count(),
            "cpus_allowed": allowed, "libc": "%s %s" % libc if libc[0] else None,
            "probe_python": sys.version.split()[0], "probe_executable": sys.executable}


def probe_scheduler():
    found = {name: shutil.which(cmd) for name, cmd in
             (("slurm", "sbatch"), ("pbs_or_sge", "qsub"), ("lsf", "bsub"), ("flux", "flux"))}
    present = [k for k, v in found.items() if v]
    env = {k: os.environ.get(k) for k in SLURM_VARS if os.environ.get(k) is not None}
    return {"schedulers": present, "in_slurm_job": "SLURM_JOB_ID" in os.environ, "slurm_env": env}


def probe_gpus(timeout):
    info = {"nvidia_smi": shutil.which("nvidia-smi"), "gpus": [], "error": None,
            "nvidia_device_nodes": os.path.exists("/dev/nvidiactl") or bool(glob.glob("/dev/nvidia[0-9]*"))}
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        info["apple_silicon"] = True
    if not info["nvidia_smi"]:
        return info
    fields = ["name", "memory.total", "driver_version", "compute_cap"]
    res = run([info["nvidia_smi"], "--query-gpu=" + ",".join(fields), "--format=csv,noheader,nounits"], timeout)
    if res["rc"] != 0 and "compute_cap" in res["out"] + res["err"]:  # older drivers lack compute_cap
        fields = fields[:3]
        res = run([info["nvidia_smi"], "--query-gpu=" + ",".join(fields), "--format=csv,noheader,nounits"],
                  timeout)
    if res["rc"] != 0:
        msg = (res["out"] + res["err"]).strip().splitlines()
        info["error"] = (msg[0] if msg else res["error"] or "nvidia-smi failed")[:200]
        return info
    for line in res["out"].strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 3:
            continue
        g = {"name": cols[0], "memory_mib": int(cols[1]) if cols[1].isdigit() else cols[1], "driver": cols[2]}
        if len(cols) >= 4:
            g["compute_cap"] = cols[3]
        info["gpus"].append(g)
    return info


def probe_runtimes(timeout, deep):
    """Container runtime versions. apptainer/singularity --version write nothing; rootless podman (and a
    docker CLI that is a podman shim) creates runtime directories even for --version, so docker/podman
    are only located in the read-only run and queried under --deep."""
    out = {}
    for name in CONTAINER_RUNTIMES:
        path = shutil.which(name)
        if not path:
            out[name] = None
            continue
        info = {"path": path, "version": None, "rc": None}
        text, _ = read_text_head(path, 4096)
        if name == "docker" and text and "podman" in text:
            info["podman_shim"] = True
        if name in ("docker", "podman") and not deep:
            info["version"] = "not queried (read-only run; --deep queries it)"
            out[name] = info
            continue
        res = run([path, "--version"], timeout)
        lines = (res["out"] or res["err"]).strip().splitlines()
        info["rc"] = res["rc"]
        info["version"] = lines[0][:120] if lines and res["rc"] == 0 else None
        out[name] = info
    return out


# ------------------------------------------------------------------------------------------ packages
def packages_current():
    try:
        from importlib import metadata as md
    except ImportError:
        return {"error": "importlib.metadata unavailable"}
    found = {}
    try:
        for dist in md.distributions():
            n = norm_name(dist.metadata.get("Name") if dist.metadata else "")
            if n and wanted(n) and n not in found:
                found[n] = dist.version
    except Exception as exc:  # noqa: BLE001 - a broken dist must not break the probe
        return {"error": "metadata scan failed: %s" % exc}
    return found


def packages_in_prefix(prefix):
    """Versions from *.dist-info directory names under an environment prefix (no execution)."""
    found = {}
    pats = [os.path.join(prefix, lib, "python3*", "site-packages", "*.dist-info")
            for lib in ("lib", "lib64")]
    for pat in pats:
        for d in sorted(glob.glob(pat)):
            base = os.path.basename(d)[:-len(".dist-info")]
            if "-" not in base:
                continue
            name, ver = base.split("-", 1)
            n = norm_name(name)
            if wanted(n) and n not in found:
                found[n] = ver
    return found


# ------------------------------------------------------------------------------------------ commands
def inspect_command(name):
    path = shutil.which(name) if os.sep not in name else (name if os.path.isfile(name) else None)
    if not path:
        return {"name": name, "found": False}
    d = {"name": name, "found": True, "path": path, "realpath": os.path.realpath(path),
         "executable": os.access(path, os.X_OK), "kind": "unknown"}
    text, binary = read_text_head(path)
    if binary:
        d["kind"] = "binary"
        return d
    if text is None:
        d["kind"] = "unreadable"
        return d
    first = text.splitlines()[0] if text else ""
    if first.startswith("#!"):
        d["shebang"] = first[2:].strip()[:200]
    if first.startswith("#!") and "python" in first:
        d["kind"] = "python-console-script"
        parts = first[2:].split()
        interp = parts[0] if parts else ""
        if os.path.basename(interp) == "env" and len(parts) > 1:
            interp = shutil.which(parts[-1]) or parts[-1]
        d["interpreter"] = interp
        if interp and os.path.isabs(interp):
            prefix = os.path.dirname(os.path.dirname(interp))
            d["env_prefix"] = prefix
            d["packages"] = packages_in_prefix(prefix)
        return d
    if first.startswith("#!") and re.search(r"\b(ba|z|k|da)?sh\b", first):
        d["kind"] = "shell-wrapper"
        d["mentions_runtime"] = [r for r in CONTAINER_RUNTIMES if re.search(r"\b%s\b" % r, text)]
        defaults = {}
        for var in WRAPPER_VARS:
            m = re.search(r"\$\{%s:?-([^}]*)\}" % re.escape(var), text)
            if m:
                defaults[var] = {"raw": m.group(1), "path": expand_home(m.group(1))}
        d["defaults"] = defaults
        d["sif_refs"] = sorted(set(re.findall(r"[\w./~${}-]+\.sif\b", text)))[:10]
        d["sets_cache_vars"] = [v for v in ("MODEL_OPT_JIT_ROOT", "TRITON_CACHE_DIR", "TORCH_EXTENSIONS_DIR",
                                            "XDG_CACHE_HOME") if re.search(r"(^|[\s;])%s=" % v, text, re.M)]
    return d


# ------------------------------------------------------------------------------------------ checkpoints
def kit_memo_lookup(path):
    """Look up a kit-cached digest (openfold3_ob0_opt/digest_memo.py key) read-only; never trusted as proof."""
    try:
        real = os.path.realpath(path)
        st = os.stat(real)
    except OSError:
        return None
    key = json.dumps([real, st.st_size, st.st_mtime_ns, st.st_ino])
    dirs = []
    for base in (os.environ.get("XDG_CACHE_HOME"), os.path.join(HOME, ".cache")):
        if base and os.path.join(base, "openfold3_ob0_opt") not in dirs:
            dirs.append(os.path.join(base, "openfold3_ob0_opt"))
    for d in dirs:
        memo = os.path.join(d, "weights_digests.json")
        try:
            with open(memo) as fh:
                table = json.load(fh)
        except (OSError, ValueError):
            continue
        entry = table.get(key) if isinstance(table, dict) else None
        if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
            return {"memo": memo, "sha256": entry["sha256"], "utc": entry.get("utc")}
    return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inspect_cache_root(path, source):
    info = {"path": path, "source": source, "exists": os.path.isdir(path)}
    if not info["exists"]:
        info["note"] = "absent: upstream predict creates it (mkdir) on first use"
        return info
    info["writable"] = os.access(path, os.W_OK)
    ptr = os.path.join(path, "ckpt_root")
    info["ckpt_root_present"] = os.path.isfile(ptr)
    param_dir = path
    if info["ckpt_root_present"]:
        try:
            with open(ptr) as fh:
                target = fh.read(4096).strip()
            info["ckpt_root_points_to"] = target
            param_dir = target or path
        except OSError as exc:
            info["ckpt_root_error"] = str(exc)
    else:
        info["note"] = "no ckpt_root pointer: a predict call without --inference-ckpt-path writes one here"
    info["param_dir"] = param_dir
    info["upstream_default_ckpt"] = os.path.join(param_dir, OB0_FILE)
    info["upstream_default_ckpt_exists"] = os.path.isfile(info["upstream_default_ckpt"])
    info["runner_yml_present"] = os.path.isfile(os.path.join(path, "runner.yml"))
    return info


def discover_checkpoints(args, commands):
    cands = []  # (source, path)

    def add(source, p):
        p = expand_home(p) if isinstance(p, str) else None
        if not p:
            return
        if os.path.isdir(p):
            for fname in KNOWN_CKPTS:
                fp = os.path.join(p, fname)
                if os.path.isfile(fp):
                    cands.append((source + " (dir)", fp))
            return
        cands.append((source, p))

    if args.ckpt:
        add("--ckpt", args.ckpt)
    for var in ("OPENFOLD3_OB0_CKPT", "OPENFOLD3_CKPT"):
        if os.environ.get(var):
            add("env " + var, os.environ[var])
    roots = []
    env_cache = os.environ.get("OPENFOLD_CACHE")
    roots.append((env_cache, "env OPENFOLD_CACHE") if env_cache else (os.path.join(HOME, ".openfold3"),
                                                                       "upstream default ~/.openfold3"))
    for c in commands:
        for var, val in (c.get("defaults") or {}).items():
            if var in ("OPENFOLD3_OB0_CKPT", "OPENFOLD3_CKPT") and val.get("path"):
                add("wrapper %s default %s" % (c["name"], var), val["path"])
            if var == "OPENFOLD_CACHE" and val.get("path"):
                roots.append((val["path"], "wrapper %s default OPENFOLD_CACHE" % c["name"]))
    cache_roots, seen_roots = [], set()
    for path, source in roots:
        path = expand_home(path)
        if not path or os.path.realpath(path) in seen_roots:
            continue
        seen_roots.add(os.path.realpath(path))
        info = inspect_cache_root(path, source)
        cache_roots.append(info)
        if info["exists"]:
            for d in {info["path"], info.get("param_dir") or info["path"]}:
                for fname in KNOWN_CKPTS:
                    fp = os.path.join(d, fname)
                    if os.path.isfile(fp):
                        cands.append(("%s param dir" % source, fp))

    merged, order = {}, []
    for source, p in cands:
        key = os.path.realpath(p)
        if key not in merged:
            merged[key] = {"path": p, "realpath": key, "sources": []}
            order.append(key)
        if source not in merged[key]["sources"]:
            merged[key]["sources"].append(source)
    ckpts = []
    for key in order:
        c = merged[key]
        p = c["path"]
        c["exists"] = os.path.isfile(p)
        base = os.path.basename(key)
        reg = KNOWN_CKPTS.get(base) or KNOWN_CKPTS.get(os.path.basename(p))
        c["registry_name"], c["label"] = (reg if reg else (None, "unknown file name"))
        if c["exists"]:
            size = os.path.getsize(p)
            c["bytes"] = size
            c["mtime_utc"] = utc_mtime(p)
            c["ob0_candidate"] = base == OB0_FILE or os.path.basename(p) == OB0_FILE or size == OB0_BYTES
            c["ob0_size_ok"] = size == OB0_BYTES if c["ob0_candidate"] else None
            memo = kit_memo_lookup(p)
            if memo:
                memo["matches"] = KNOWN_DIGESTS.get(memo["sha256"], "unknown digest")
                c["kit_memo_digest"] = memo
            if args.hash:
                t0 = time.monotonic()
                try:
                    digest = sha256_file(p)
                    c["sha256"] = digest
                    c["sha256_matches"] = KNOWN_DIGESTS.get(digest, "unknown digest")
                    c["hash_seconds"] = round(time.monotonic() - t0, 1)
                except OSError as exc:
                    c["hash_error"] = str(exc)
        ckpts.append(c)
    return ckpts, cache_roots


# ------------------------------------------------------------------------------------------ kit + image
def inspect_kit_dir(path):
    p = os.path.abspath(os.path.expanduser(path))
    info = {"path": p, "exists": os.path.isdir(p)}
    if not info["exists"]:
        return info
    if not os.path.isfile(os.path.join(p, "run.sh")):
        for sub in ("openfold3_ob0", "openfold3"):
            if os.path.isfile(os.path.join(p, sub, "run.sh")):
                info["descended_into"] = sub
                p = os.path.join(p, sub)
                info["path"] = p
                break
    run_sh = os.path.join(p, "run.sh")
    info["run_sh"] = os.path.isfile(run_sh)
    info["run_sh_executable"] = os.access(run_sh, os.X_OK) if info["run_sh"] else False
    info["configs"] = sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(p, "configs", "*.env")))
    info["common_opt_core"] = os.path.isdir(os.path.join(p, "..", "common", "opt_core"))
    pins_path = os.path.join(p, "stock", "PINS.json")
    info["pins_json"] = os.path.isfile(pins_path)
    if info["pins_json"]:
        try:
            with open(pins_path) as fh:
                pins = json.load(fh)
            w = pins.get("weights") or {}
            up = pins.get("upstream") or {}
            info["pins"] = {"openfold3_version": pins.get("openfold3_version"), "upstream_tag": up.get("tag"),
                            "upstream_commit": up.get("commit"), "weights_file": w.get("file"),
                            "weights_sha256": w.get("sha256"), "weights_bytes": w.get("bytes"),
                            "weights_env": w.get("path_env"),
                            "pinned_stack": {k: (pins.get("pinned_stack") or {}).get(k)
                                             for k in ("python", "torch", "cuda", "deepspeed",
                                                       "cuequivariance_torch")}}
        except (OSError, ValueError) as exc:
            info["pins_error"] = str(exc)
    ver = (info.get("pins") or {}).get("openfold3_version") or ""
    if ver.startswith("0.5") or os.path.basename(p) == "openfold3_ob0":
        info["flavour"] = "openfold3_ob0 (OpenFold3 0.5.0 + OpenBind-0; recommended)"
    elif ver.startswith("0.4") or os.path.basename(p) == "openfold3":
        info["flavour"] = "openfold3 (OpenFold3 0.4.1 + preview-2; legacy/reproducibility only)"
    else:
        info["flavour"] = "unrecognised"
    return info


def inspect_images(args, commands):
    cands = []
    if args.sif:
        cands.append(("--sif", args.sif))
    if os.environ.get("OPENFOLD3_KIT_SIF"):
        cands.append(("env OPENFOLD3_KIT_SIF", os.environ["OPENFOLD3_KIT_SIF"]))
    for c in commands:
        d = (c.get("defaults") or {}).get("OPENFOLD3_KIT_SIF")
        if d and d.get("path"):
            cands.append(("wrapper %s default" % c["name"], d["path"]))
    out, seen = [], {}
    for source, p in cands:
        p = expand_home(p)
        if not p:
            continue
        key = os.path.realpath(p)
        if key in seen:
            seen[key]["sources"].append(source)
            continue
        info = {"path": p, "sources": [source], "exists": os.path.isfile(p)}
        if info["exists"]:
            info["bytes"] = os.path.getsize(p)
            info["mtime_utc"] = utc_mtime(p)
            info["readable"] = os.access(p, os.R_OK)
        seen[key] = info
        out.append(info)
    return out


# ------------------------------------------------------------------------------------------ caches
def mount_of(path):
    best = ("", None)
    rp = os.path.realpath(path)
    try:
        with open("/proc/mounts") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mnt = parts[1].replace("\\040", " ")
                if (rp == mnt or rp.startswith(mnt.rstrip("/") + "/")) and len(mnt) > len(best[0]):
                    best = (mnt, parts[2])
    except OSError:
        return None, None
    return best


def fs_info(label, path):
    info = {"label": label, "path": path}
    if not path or not os.path.exists(path):
        info["exists"] = False
        return info
    try:
        st = os.statvfs(path)
    except OSError as exc:
        info["error"] = str(exc)
        return info
    mnt, fstype = mount_of(path)
    info.update({"exists": True, "mount": mnt, "fs_type": fstype,
                 "bytes_free": st.f_bavail * st.f_frsize, "inodes_total": st.f_files,
                 "inodes_free": st.f_favail})
    if st.f_files:
        info["inodes_free_pct"] = round(100.0 * st.f_favail / st.f_files, 2)
    return info


def cache_risks(env, commands, hpc):
    """Cache locations that would put JIT files under HOME. Unset variables are warnings on a
    scheduler host (typically inode-limited network homes) and notes elsewhere."""
    risks = []
    wrappers = [c for c in commands if c.get("kind") == "shell-wrapper"]
    mitigated = {v: [c["name"] for c in wrappers if v in (c.get("sets_cache_vars") or [])]
                 for v in list(CACHE_VARS) + ["MODEL_OPT_JIT_ROOT"]}
    tmp = env.get("TMPDIR")
    if tmp and under_home(tmp):
        risks.append({"var": "TMPDIR", "value": tmp, "severity": "warning",
                      "detail": "TMPDIR is under HOME: the kit's run.sh seeds JIT caches under "
                                "${TMPDIR}/model_opt_jit-uid<uid> when MODEL_OPT_JIT_ROOT is unset; "
                                "point TMPDIR at node-local scratch"})
    for var, (default, what) in CACHE_VARS.items():
        val = env.get(var)
        if val and under_home(val):
            risks.append({"var": var, "value": val, "severity": "warning",
                          "detail": "set to a path under HOME: JIT caches are hundreds to ~1000 small "
                                    "files per job; use node-local scratch"})
        elif not val:
            via = mitigated.get(var) or []
            if via:
                risks.append({"var": var, "value": None, "severity": "note",
                              "detail": "unset here; wrapper(s) %s mention it (they may set it, or leave it to the kit's "
                                        "configs/<card>.env under MODEL_OPT_JIT_ROOT): read the wrapper" % ", ".join(via)})
            else:
                kit_hint = ("" if var == "XDG_CACHE_HOME" else
                            " (kit route: set MODEL_OPT_JIT_ROOT instead; configs/<card>.env derives this from it)")
                risks.append({"var": var, "value": None, "severity": "warning" if hpc else "note",
                              "detail": "unset: %s go to the default %s under HOME; export it to node-local "
                                        "scratch on inode-limited homes%s" % (what, default, kit_hint)})
    jit = env.get("MODEL_OPT_JIT_ROOT")
    if jit and under_home(jit):
        risks.append({"var": "MODEL_OPT_JIT_ROOT", "value": jit, "severity": "warning",
                      "detail": "kit JIT root under HOME; use node-local scratch"})
    return risks


# ------------------------------------------------------------------------------------------ deep
def deep_run(args, commands, gpus):
    side_effects = ("Deep mode runs the installed CLI. It may create files: the cache directory "
                    "($OPENFOLD_CACHE, ckpt_root), Triton / torch-extension caches, the kit JIT root "
                    "(${TMPDIR:-/tmp}/model_opt_jit-uid<uid> when MODEL_OPT_JIT_ROOT is unset), the kit's "
                    "weights-digest memo ($XDG_CACHE_HOME/openfold3_ob0_opt/weights_digests.json, rewritten by "
                    "`check`), and wrapper-made cache directories. The kit `check` re-hashes the checkpoint "
                    "(~2.3 GB read).")
    kit_argv = None
    if args.kit_cli:
        c = next((x for x in commands if x["name"] == args.kit_cli), None)
        if c and c.get("found"):
            kit_argv = [c["path"]]
    elif args.kit_dir:
        run_sh = os.path.join(inspect_kit_dir(args.kit_dir)["path"], "run.sh")
        if os.path.isfile(run_sh):
            kit_argv = ["bash", run_sh]
    notes = []
    if kit_argv and args.card:
        argv = kit_argv + ["check", "--config", args.card, "--mode", args.mode]
        kind = "kit-check"
    else:
        if (args.kit_cli or args.kit_dir) and not args.card:
            notes.append("pass --card <a100|h100|h200|b200|b300> to run the kit dry run instead")
        if (args.kit_cli or args.kit_dir) and args.card and not kit_argv:
            notes.append("kit entry point not found; fell back to run_openfold predict --help")
        ro = next((x for x in commands if x["name"] == "run_openfold"), None)
        if not ro or not ro.get("found"):
            return {"kind": "skipped", "reason": "no run_openfold on PATH and no usable kit entry point",
                    "side_effects": side_effects, "notes": notes}
        argv = [ro["path"], "predict", "--help"]
        kind = "predict-help"
    sys.stderr.write("openfold3_env_probe: --deep: running %s (timeout %ss). %s\n"
                     % (" ".join(argv), args.timeout, side_effects))
    res = run(argv, args.timeout, merge=True)
    lines = [ln.rstrip()[:300] for ln in res["out"].splitlines()]
    key_re = re.compile(r"DRY-RUN|WEIGHTS|NOT ACTIVE|ACTIVE mode=|WARNING|[Ee]rror|Traceback|refus|"
                        r"no NVIDIA device|Usage:|RC=|exit ")
    out = {"kind": kind, "argv": argv, "rc": res["rc"], "elapsed_s": res["elapsed_s"],
           "timed_out": res["timed_out"], "error": res["error"], "head": lines[:25],
           "key_lines": [ln for ln in lines if key_re.search(ln)][:20], "side_effects": side_effects,
           "notes": notes}
    if kind == "predict-help":
        missing = [o for o in PREDICT_OPTIONS if o not in res["out"]]
        out["predict_options_missing"] = missing
        if res["rc"] == 0 and len(missing) == len(PREDICT_OPTIONS) and "--disable-cutlass-package-imports" in res["out"]:
            notes.append("help was taken over by the bundled cutlass_library argument parser (as bare "
                         "`run_openfold --help` is on GPU-visible nodes): capture `run_openfold predict --help` "
                         "on a CPU node of the same install")
        elif res["rc"] == 0 and missing:
            notes.append("predict --help lacks %s: CLI differs from v0.5.0; re-read the live help"
                         % ", ".join(missing))
    if kind == "kit-check" and res["rc"] == 0 and not gpus.get("gpus"):
        notes.append("rc 0 without a visible GPU: the dry run checked pins, weights and mode resolution; "
                     "it is not a GPU proof")
    if kind == "kit-check":
        joined = res["out"]
        out["weights_pinned"] = True if "WEIGHTS pinned" in joined else (False if "WEIGHTS unknown" in joined
                                                                          else None)
    return out


# ------------------------------------------------------------------------------------------ verdict
def build_verdict(r):
    reasons, blockers, warnings, notes = [], [], [], []
    cmds = {c["name"]: c for c in r["commands"]}
    runtime = []
    for c in r["commands"]:
        if c.get("found") and c["name"] != "validate-openfold3-rocm":
            runtime.append("%s on PATH (%s)" % (c["name"], c.get("kind")))
    of3_versions = {}
    if isinstance(r["packages"]["probe_interpreter"], dict) and r["packages"]["probe_interpreter"].get("openfold3"):
        of3_versions["probe interpreter"] = r["packages"]["probe_interpreter"]["openfold3"]
    for c in r["commands"]:
        v = (c.get("packages") or {}).get("openfold3")
        if v:
            of3_versions["env of %s" % c["name"]] = v
    for where, v in of3_versions.items():
        runtime.append("openfold3 %s in %s" % (v, where))
    kit = r.get("kit_dir")
    if kit and kit.get("run_sh"):
        runtime.append("kit checkout (%s)" % kit.get("flavour"))
    images = [i for i in r["images"] if i.get("exists")]
    for i in images:
        runtime.append("container image %s" % os.path.basename(i["path"]))
    kit_pkgs = ("openfold3_ob0_opt", "openfold3_opt")
    pkg_sets = [r["packages"]["probe_interpreter"] or {}] + [c.get("packages") or {} for c in r["commands"]]
    kit_names = {"openfold3-kit", r["args"].get("kit_cli")}
    kit_present = bool((kit and kit.get("run_sh")) or images
                       or any(cmds.get(n, {}).get("found") for n in kit_names if n)
                       or any(k in ps for ps in pkg_sets for k in kit_pkgs))

    for where, v in of3_versions.items():
        pv = parse_version(v)
        if pv and pv < (0, 5, 0):
            warnings.append("openfold3 %s (%s): legacy; OpenBind-0 needs >=0.5.0 (preview weights only)" % (v, where))
        elif pv and pv > (0, 5, 0):
            notes.append("openfold3 %s (%s) is newer than the kit pin %s: the kit refuses (rc 3); stock only"
                          % (v, where, KIT_PIN_VERSION))
    if kit and kit.get("exists") and not kit.get("run_sh"):
        warnings.append("--kit-dir has no run.sh (not an openfold3_ob0/ or openfold3/ kit directory)")
    if kit and kit.get("run_sh") and not kit.get("common_opt_core"):
        warnings.append("kit checkout lacks ../common/opt_core (the shared core run.sh install needs)")
    if kit and (kit.get("pins") or {}).get("weights_sha256") not in (None, OB0_SHA256):
        notes.append("kit pins a different checkpoint (%s): the legacy 0.4.1 kit" % kit["pins"].get("weights_file"))
    for i in r["images"]:
        if not i.get("exists"):
            warnings.append("container image not found: %s (from %s)" % (i["path"], ", ".join(i["sources"])))
    for c in r["commands"]:
        if c["name"] == r["args"].get("kit_cli") and not c.get("found"):
            warnings.append("kit CLI %s not on PATH" % c["name"])

    # GPU route
    gpus = r["gpu"]["gpus"]
    sched = r["scheduler"]["schedulers"]
    if gpus:
        for g in gpus:
            cc = parse_version(g.get("compute_cap", ""))
            if cc and cc[:2] < KIT_MIN_CC:
                msg = "GPU %s has compute capability %s < 8.0" % (g["name"], g.get("compute_cap"))
                (blockers if kit_present else warnings).append(
                    msg + (": the kit stack refuses it" if kit_present else ": stock bf16 path untested"))
            mem = g.get("memory_mib")
            if isinstance(mem, int) and mem < DOC_MIN_GPU_MIB:
                warnings.append("GPU %s has %d MiB: upstream docs ask for >=32 GB; only small inputs will fit"
                                % (g["name"], mem))
            drv = parse_version(g.get("driver", ""))
            if kit_present and drv and drv[0] < KIT_MIN_DRIVER:
                warnings.append("driver %s < %d: the kit stack (CUDA 12.8) needs a newer driver"
                                % (g.get("driver"), KIT_MIN_DRIVER))
        reasons.append("%d NVIDIA GPU(s) visible: %s" % (len(gpus), ", ".join(sorted({g["name"] for g in gpus}))))
    elif sched:
        notes.append("no GPU visible on this host; scheduler present (%s): submit predictions to a GPU node"
                     % ", ".join(sched))
    elif r["gpu"].get("apple_silicon"):
        warnings.append("Apple Silicon: upstream has an MPS environment, but it is slow, not validated by this "
                        "skill, and the kits do not support it")
        blockers.append("no CUDA GPU and no scheduler on this host")
    else:
        blockers.append("no NVIDIA GPU visible and no batch scheduler found: no GPU route from this host")

    # Checkpoints
    ck = r["checkpoints"]
    ob0 = [c for c in ck if c.get("exists") and c.get("ob0_candidate")]
    good = [c for c in ob0 if c.get("ob0_size_ok") and c.get("sha256_matches", KNOWN_DIGESTS[OB0_SHA256])
            == KNOWN_DIGESTS[OB0_SHA256]]
    for c in ck:
        if not c.get("exists"):
            warnings.append("checkpoint path does not exist: %s (from %s)" % (c["path"], ", ".join(c["sources"])))
        elif c.get("ob0_candidate") and not c.get("ob0_size_ok"):
            blockers.append("%s is %d bytes, OpenBind-0 is %d: truncated or a different file"
                            % (c["path"], c["bytes"], OB0_BYTES))
        if c.get("sha256") and c.get("ob0_candidate") and c["sha256"] != OB0_SHA256:
            blockers.append("sha256 of %s is not the OpenBind-0 digest (%s)" % (c["path"], c["sha256_matches"]))
        memo = c.get("kit_memo_digest")
        if memo and c.get("ob0_candidate") and memo["sha256"] != OB0_SHA256:
            warnings.append("kit memo records a non-OpenBind-0 digest for %s" % c["path"])
    if good:
        how = "sha256 verified" if any(c.get("sha256") == OB0_SHA256 for c in good) else "size matches; --hash to verify"
        reasons.append("OpenBind-0 checkpoint present (%s): %s" % (how, good[0]["path"]))
    elif ob0:
        pass  # size / digest blockers above already name the bad OpenBind-0 file
    elif any(c.get("exists") and not c.get("ob0_candidate") for c in ck):
        warnings.append("only legacy/unknown checkpoints found; preview weights are incompatible with openfold3 >=0.5.0")
        blockers.append("no OpenBind-0 checkpoint: v0.5.0 predict refuses without one")
    else:
        blockers.append("no OpenBind-0 checkpoint found: after confirmation run `setup_openfold` or kit "
                        "`run.sh install --weights DIR` (see references/02_install_and_environment.md)")
    for root in r["cache_roots"]:
        if root.get("runner_yml_present"):
            warnings.append("%s/runner.yml exists: upstream deep-merges it into EVERY predict call" % root["path"])

    # Environment
    armed = r["env"].get("OPENFOLD3_OB0_OPT")
    if armed and armed != "off":
        notes.append("OPENFOLD3_OB0_OPT=%s is set: a plain `run_openfold predict` here runs that kit mode, not stock"
                     % armed)
    if r["kit_switches_set"]:
        notes.append("kit switch variables set in this shell: %s (a stock run should carry none)"
                     % ", ".join(r["kit_switches_set"]))
    for risk in r["cache_risks"]:
        (warnings if risk["severity"] == "warning" else notes).append("%s: %s" % (risk["var"], risk["detail"]))
    for f in r["filesystems"]:
        if f.get("inodes_total") and (f["inodes_free"] < LOW_INODES or f.get("inodes_free_pct", 100) < 5):
            warnings.append("%s filesystem (%s) has few free inodes (%s free, %s%%)"
                            % (f["label"], f.get("mount"), f["inodes_free"], f.get("inodes_free_pct")))

    # Deep
    deep = r.get("deep")
    if runtime and not of3_versions and not deep:
        notes.append("openfold3 version not visible from here (wrapper / container install): --deep runs the "
                     "CLI; the image or env holds the version")
    if deep and deep.get("kind") != "skipped":
        if deep.get("timed_out"):
            blockers.append("deep %s timed out after %ss" % (deep["kind"], r["args"]["timeout"]))
        elif deep.get("rc") != 0:
            blockers.append("deep %s failed (rc %s); see deep.head" % (deep["kind"], deep.get("rc")))
        else:
            reasons.append("deep %s rc 0 in %ss" % (deep["kind"], deep.get("elapsed_s")))
            if deep.get("weights_pinned") is False:
                blockers.append("kit check reports the checkpoint is not the pinned OpenBind-0")
        notes.extend(deep.get("notes") or [])
    elif deep:
        warnings.append("deep run skipped: %s" % deep.get("reason"))

    if not runtime:
        state = "UNCONFIGURED"
        next_steps = ["No OpenFold3 runtime found (no CLI on PATH, no package, no kit checkout or image). "
                      "Plan an install route with the user (references/02_install_and_environment.md); "
                      "install only after explicit confirmation."]
    elif good and not blockers:
        state = "VALIDATED-CANDIDATE"
        next_steps = ["Record this report in configs/site_config.local.md as state PROBED (template: "
                      "configs/site_config.template.md).",
                      "Run one GPU prediction on a public example with --use-msa-server false and record it; only "
                      "then treat the host as VALIDATED (references/02_install_and_environment.md, GPU fixture)."]
        if not deep:
            next_steps.insert(0, "Optional: re-run with --deep (may create cache files) on the runtime host.")
    else:
        state = "PROBED"
        next_steps = ["Resolve the blockers above, then re-run this probe (references/10_troubleshooting.md)."]
    reasons = ["runtime: " + "; ".join(runtime)] + reasons if runtime else reasons
    return {"state": state, "reasons": reasons, "blockers": blockers, "warnings": warnings, "notes": notes,
            "next_steps": next_steps}


# ------------------------------------------------------------------------------------------ output
def print_human(r):
    p = print
    bar = "=" * 72
    p(bar)
    p("OPENFOLD3 ENVIRONMENT PROBE %s  (%s)" % (PROBE_VERSION, "DEEP run: see side effects below" if r.get("deep")
                                                 else "read-only; nothing written or downloaded"))
    p(bar)
    h = r["host"]
    p("host        : %s  %s (%s)  kernel %s  %s" % (h["hostname"], h["os"], h.get("os_release") or "?",
                                                    h["kernel"], h["arch"]))
    p("cpus        : %s total, %s allowed    probe python %s" % (h["cpu_count"], h.get("cpus_allowed"),
                                                                 h["probe_python"]))
    s = r["scheduler"]
    p("scheduler   : %s%s" % (", ".join(s["schedulers"]) or "none",
                              "  (inside Slurm job)" if s["in_slurm_job"] else ""))
    for k, v in s["slurm_env"].items():
        p("   %-22s %s" % (k, v))
    g = r["gpu"]
    p("")
    p("GPUs        : nvidia-smi %s" % ("found" if g["nvidia_smi"] else "not found"))
    for gi in g["gpus"]:
        p("   - %s  %s MiB  cc=%s  driver=%s" % (gi["name"], gi["memory_mib"], gi.get("compute_cap", "?"),
                                                gi["driver"]))
    if g.get("error"):
        p("   (no GPU usable here: %s)" % g["error"])
    p("containers  : " + ", ".join("%s=%s" % (k, (v or {}).get("version") or ("absent" if v is None else "error"))
                                   for k, v in r["container_runtimes"].items()))
    p("")
    p("Commands:")
    for c in r["commands"]:
        if not c.get("found"):
            p("   %-24s not found" % c["name"])
            continue
        extra = ""
        if c.get("kind") == "python-console-script":
            extra = " -> %s" % c.get("interpreter")
        elif c.get("kind") == "shell-wrapper" and c.get("mentions_runtime"):
            extra = " (wraps %s)" % "/".join(c["mentions_runtime"])
        p("   %-24s %s  [%s]%s" % (c["name"], c["path"], c.get("kind"), extra))
        if c.get("packages"):
            p("      env packages: %s" % ", ".join("%s=%s" % kv for kv in sorted(c["packages"].items())))
    pk = r["packages"]["probe_interpreter"]
    p("Probe-interpreter packages: %s" % (", ".join("%s=%s" % kv for kv in sorted(pk.items())) if pk else "none"))
    p("")
    p("Environment:")
    for k, v in r["env"].items():
        p("   %-22s %s" % (k, v if v is not None else "(unset)"))
    if r["kit_switches_set"]:
        p("   kit switches set     : %s" % ", ".join(r["kit_switches_set"]))
    p("")
    p("Cache roots (OPENFOLD_CACHE):")
    for c in r["cache_roots"]:
        p("   %s  [%s]  exists=%s" % (c["path"], c["source"], c["exists"]))
        if c["exists"]:
            p("      ckpt_root=%s  runner.yml=%s  default ckpt present=%s"
              % (c.get("ckpt_root_points_to", "absent"), c.get("runner_yml_present"),
                 c.get("upstream_default_ckpt_exists")))
    p("Checkpoints:")
    if not r["checkpoints"]:
        p("   (none found)")
    for c in r["checkpoints"]:
        p("   %s  [%s]" % (c["path"], "; ".join(c["sources"])))
        if not c["exists"]:
            p("      MISSING")
            continue
        size = "size OK" if c.get("ob0_size_ok") else ("SIZE MISMATCH" if c.get("ob0_candidate") else "not OB0")
        p("      %s  %d bytes (%s)" % (c["label"], c["bytes"], size))
        if c.get("sha256"):
            p("      sha256 %s -> %s (%.1fs)" % (c["sha256"], c["sha256_matches"], c.get("hash_seconds", 0)))
        if c.get("kit_memo_digest"):
            m = c["kit_memo_digest"]
            p("      kit memo digest (cached %s) -> %s" % (m.get("utc"), m["matches"]))
    if r.get("kit_dir"):
        k = r["kit_dir"]
        p("Kit checkout: %s  exists=%s run.sh=%s" % (k["path"], k["exists"], k.get("run_sh")))
        if k.get("run_sh"):
            pins = k.get("pins") or {}
            p("   flavour=%s  openfold3=%s  commit=%s" % (k.get("flavour"), pins.get("openfold3_version"),
                                                         (pins.get("upstream_commit") or "?")[:12]))
            p("   configs=%s  common/opt_core=%s" % (",".join(k.get("configs") or []) or "none",
                                                     k.get("common_opt_core")))
    for i in r["images"]:
        p("Image: %s  [%s]  exists=%s%s" % (i["path"], ", ".join(i["sources"]), i["exists"],
                                            "  %.2f GB" % (i["bytes"] / 1e9) if i.get("bytes") else ""))
    p("")
    p("Filesystems (statvfs is filesystem-wide, not your quota):")
    for f in r["filesystems"]:
        if not f.get("exists"):
            p("   %-16s %s (absent)" % (f["label"], f["path"]))
            continue
        p("   %-16s %s  [%s %s]  free %.1f GB, inodes free %s (%s%%)"
          % (f["label"], f["path"], f.get("fs_type"), f.get("mount"), f["bytes_free"] / 1e9,
             f.get("inodes_free"), f.get("inodes_free_pct", "?")))
    d = r.get("deep")
    if d:
        p("")
        p("Deep (%s): rc=%s elapsed=%ss timed_out=%s" % (d.get("kind"), d.get("rc"), d.get("elapsed_s"),
                                                          d.get("timed_out")))
        if d.get("argv"):
            p("   command: %s" % " ".join(d["argv"]))
        if d.get("predict_options_missing") is not None:
            p("   v0.5.0 predict options missing: %s" % (", ".join(d["predict_options_missing"]) or "none"))
        if d.get("weights_pinned") is not None:
            p("   kit WEIGHTS line: %s" % ("pinned" if d["weights_pinned"] else "NOT the pinned checkpoint"))
        for ln in d.get("key_lines") or d.get("head") or []:
            p("   | %s" % ln)
        p("   side effects: %s" % d.get("side_effects"))
    v = r["verdict"]
    p("")
    p(">> HOST VERDICT: %s  (host only; the session state is PROBED)" % v["state"])
    for label, key in (("reason", "reasons"), ("BLOCKER", "blockers"), ("warning", "warnings"), ("note", "notes"),
                       ("next", "next_steps")):
        for item in v[key]:
            p(">> %-8s %s" % (label + ":", item))


# ------------------------------------------------------------------------------------------ main
EPILOG = """\
What it reports
  host        hostname, OS, kernel, arch, CPUs; Slurm context (SLURM_JOB_ID, partition, GPU vars; informational)
  GPUs        nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap (absence handled)
  containers  apptainer / singularity --version; docker / podman located only (rootless podman writes
              runtime directories even for --version), their versions are queried under --deep
  commands    run_openfold, setup_openfold, openfold3-kit (conventional kit-wrapper name; image variable
              OPENFOLD3_KIT_SIF), validate-openfold3-rocm (+ --kit-cli NAME for other wrapper names):
              kind (python console script -> env packages from dist-info; shell wrapper -> container
              runtime used, ${VAR:-default} values for the image, cache and checkpoint)
  packages    openfold3, openfold3_ob0_opt, openfold3_opt, opt_core, torch, triton, deepspeed,
              pytorch_lightning, biotite, rdkit, cuequivariance* via importlib.metadata (nothing imported)
  env vars    OPENFOLD_CACHE OPENFOLD3_OB0_CKPT OPENFOLD3_CKPT OPENFOLD3_OB0_OPT OPENFOLD3_OPT MODEL_OPT_JIT_ROOT
              TRITON_CACHE_DIR TORCH_EXTENSIONS_DIR XDG_CACHE_HOME TMPDIR OPENFOLD3_KIT_SIF CUDA_VISIBLE_DEVICES,
              plus the names of any kit switch variables set (OF3_*, OF3O_*, OF3TP_*, OPENFOLD3_OB0_OPT*, ...)
  checkpoints --ckpt, $OPENFOLD3_OB0_CKPT, $OPENFOLD3_CKPT, wrapper defaults, and $OPENFOLD_CACHE (or
              ~/.openfold3) incl. its ckpt_root pointer and runner.yml; OpenBind-0 size must be 2287872989 bytes
              (sha256 bd43301c... with --hash); a kit digest memo, if present, is shown but never trusted
  kit         --kit-dir DIR: run.sh, stock/PINS.json (version, commit, weights pin), configs/*.env, ../common/opt_core
  image       --sif PATH or $OPENFOLD3_KIT_SIF or a wrapper default: exists, size, mtime
  caches      cache variables under $HOME or unset (library defaults ~/.triton/cache, ~/.cache/...), and
              statvfs free space / inodes for $HOME, $TMPDIR, the cache and JIT roots

Verdict
  UNCONFIGURED         no OpenFold3 runtime found here
  PROBED               runtime found; blockers or a missing/unverified checkpoint remain
  VALIDATED-CANDIDATE  runtime + OpenBind-0 checkpoint (size, or sha256 with --hash) + a GPU route, no blockers.
                       VALIDATED needs a recorded GPU prediction on a public input; this probe never claims it.
  A host without a GPU but with a batch scheduler gets a NOTE, not a blocker.

Deep mode (--deep, opt-in)
  Runs, in a timed subprocess: `<kit-cli> check --config CARD --mode MODE` when --card and --kit-cli (or
  --kit-dir) are given, else `run_openfold predict --help`. Records rc, elapsed time and the first lines.
  It MAY CREATE FILES: $OPENFOLD_CACHE and its ckpt_root, Triton / torch-extension / kit JIT caches (the kit
  JIT root defaults to ${TMPDIR:-/tmp}/model_opt_jit-uid<uid>), the kit weights-digest memo under
  $XDG_CACHE_HOME (check rewrites it), wrapper cache directories. The kit check re-hashes the checkpoint
  (~2.3 GB read). Deep mode also runs docker / podman --version (rootless podman creates runtime
  directories). Point TMPDIR / cache variables at node-local scratch first on inode-limited homes.
  kit check rc 0 on a GPU-less node is a dry run of pins/weights/mode, not a GPU proof.
  --deep writes nothing itself; the files above come from the tools it runs.

Exit codes: 0 probe completed (the verdict is in the output), 2 usage error.

Examples
  python3 openfold3_env_probe.py
  python3 openfold3_env_probe.py --json
  python3 openfold3_env_probe.py --kit-cli <KIT_WRAPPER> --ckpt <CKPT_PATH> --sif <IMAGE.sif>
  python3 openfold3_env_probe.py --deep --kit-cli <KIT_WRAPPER> --card a100
  python3 openfold3_env_probe.py --kit-dir <KIT_CHECKOUT>/openfold3_ob0 --hash
"""


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog="openfold3_env_probe.py",
        description="Read-only OpenFold3 / OpenFold3-kit environment probe for the openfold3 skill.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--ckpt", metavar="PATH", help="checkpoint file (or a directory holding it) to check")
    ap.add_argument("--hash", action="store_true",
                    help="sha256 every found checkpoint (reads ~2.3 GB each; opt-in)")
    ap.add_argument("--kit-dir", metavar="DIR", help="kit checkout (openfold3_ob0/ or the repository root)")
    ap.add_argument("--kit-cli", metavar="NAME", help="kit entry command on PATH (e.g. a site wrapper)")
    ap.add_argument("--sif", metavar="PATH", help="Apptainer/Singularity image to check")
    ap.add_argument("--deep", action="store_true",
                    help="run the installed CLI / kit dry run in a timed subprocess (MAY create cache files)")
    ap.add_argument("--card", metavar="CARD", help="kit --config card for --deep (a100 h100 h200 b200 b300)")
    ap.add_argument("--mode", default="exact", choices=["off", "exact", "fast", "big"],
                    help="kit mode for the --deep check (default: exact)")
    ap.add_argument("--timeout", type=int, default=240, help="--deep timeout in seconds (default 240)")
    ap.add_argument("--cmd-timeout", type=int, default=20,
                    help="timeout for nvidia-smi and --version calls (default 20)")
    ap.add_argument("--no-redact", action="store_true", help="show full paths instead of ~ for $HOME")
    args = ap.parse_args(argv)
    if args.timeout <= 0 or args.cmd_timeout <= 0:
        ap.error("timeouts must be positive")
    if args.card and not re.fullmatch(r"[A-Za-z0-9_.-]+", args.card):
        ap.error("--card takes a config name such as a100 or h100")
    if args.card and not args.deep:
        ap.error("--card is only used with --deep")
    return args


def main(argv=None):
    if sys.version_info < (3, 9):
        sys.stderr.write("openfold3_env_probe.py needs Python 3.9+\n")
        return 2
    args = parse_args(argv)
    names = list(DEFAULT_CMDS)
    if args.kit_cli and args.kit_cli not in names:
        names.append(args.kit_cli)
    commands = [inspect_command(n) for n in names]
    env = {k: os.environ.get(k) for k in ENV_VARS}
    switches = sorted(k for k in os.environ if k.startswith(KIT_SWITCH_PREFIXES) and k not in UPSTREAM_OWN_SWITCHES)
    gpu = probe_gpus(args.cmd_timeout)
    ckpts, cache_roots = discover_checkpoints(args, commands)
    fs_paths = [("HOME", HOME), ("TMPDIR", env.get("TMPDIR") or "/tmp")]
    for c in cache_roots:
        fs_paths.append(("OPENFOLD_CACHE", c["path"]))
    if env.get("MODEL_OPT_JIT_ROOT"):
        fs_paths.append(("MODEL_OPT_JIT_ROOT", env["MODEL_OPT_JIT_ROOT"]))
    seen, filesystems = set(), []
    for label, path in fs_paths:
        if path and (label, path) not in seen:
            seen.add((label, path))
            filesystems.append(fs_info(label, path))
    scheduler = probe_scheduler()
    report = {
        "probe": "openfold3_env_probe", "probe_version": PROBE_VERSION,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "mode": "deep" if args.deep else "read-only",
        "args": {"ckpt": args.ckpt, "hash": args.hash, "kit_dir": args.kit_dir, "kit_cli": args.kit_cli,
                 "sif": args.sif, "deep": args.deep, "card": args.card, "mode": args.mode,
                 "timeout": args.timeout},
        "host": probe_host(),
        "scheduler": scheduler,
        "gpu": gpu,
        "container_runtimes": probe_runtimes(args.cmd_timeout, args.deep),
        "commands": commands,
        "packages": {"probe_interpreter": packages_current()},
        "env": env,
        "kit_switches_set": switches,
        "cache_roots": cache_roots,
        "checkpoints": ckpts,
        "kit_dir": inspect_kit_dir(args.kit_dir) if args.kit_dir else None,
        "images": inspect_images(args, commands),
        "cache_risks": cache_risks(env, commands, bool(scheduler["schedulers"])),
        "filesystems": filesystems,
        "pins": {"openbind0_file": OB0_FILE, "openbind0_bytes": OB0_BYTES, "openbind0_sha256": OB0_SHA256,
                 "kit_openfold3_version": KIT_PIN_VERSION},
    }
    if args.deep:
        report["deep"] = deep_run(args, commands, gpu)
    report["verdict"] = build_verdict(report)
    if not args.no_redact:
        report = redact(report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
