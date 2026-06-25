#!/usr/bin/env python3
"""Read-only environment + state probe for the Boltz skill.

Design contract (why this is safe to run anywhere):
  - Standard library only. No third-party imports at module load.
  - Never writes, never mkdirs, never downloads. Pure inspection.
  - Default run does NOT import torch/boltz (cheap, side-effect free). The
    optional --deep run imports torch in a *separate*, time-limited subprocess
    so a broken CUDA stack can't hang or crash this probe.
  - $HOME is redacted to ~ in all text output so reports are shareable.

The point: the machine running the agent is not assumed to be the Boltz runtime.
This probe answers "what is here, and what is this host allowed to do?" so the
skill can move from UNCONFIGURED -> PROBED -> VALIDATED on solid ground.

Usage:
  python boltz_env_probe.py            # human-readable report
  python boltz_env_probe.py --json     # machine-readable JSON
  python boltz_env_probe.py --deep     # also import torch (timed subprocess)
  python boltz_env_probe.py --deep --timeout 60
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")


def redact(s):
    if not isinstance(s, str):
        return s
    return s.replace(HOME, "~") if HOME and HOME != "/" else s


def run(cmd, timeout=15):
    """Run a read-only command, return (rc, stdout, stderr) or (None,...)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # noqa: BLE001
        return None, "", str(e)


def boltz_version_in_env(env_path):
    """Read Boltz version from dist-info METADATA without importing anything."""
    for meta in glob.glob(
        os.path.join(env_path, "lib", "python3.*", "site-packages",
                     "boltz-*.dist-info", "METADATA")
    ):
        try:
            with open(meta, "r", errors="replace") as f:
                for line in f:
                    if line.startswith("Version:"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return None


def discover_envs():
    """Find candidate environments that contain a Boltz install. Read-only."""
    candidates = {}

    # 1. The interpreter currently running this probe.
    cur_prefix = sys.prefix
    candidates[cur_prefix] = "current-interpreter"

    # 2. conda/mamba environments, if available.
    conda = shutil.which("conda") or shutil.which("mamba")
    if conda:
        rc, out, _ = run([conda, "env", "list"])
        if rc == 0:
            for line in out.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.replace("*", " ").split()
                path = parts[-1] if parts else ""
                if path.startswith("/"):
                    candidates.setdefault(path, "conda")

    # 3. Common conda env roots, in case conda isn't on PATH.
    for root in (os.path.join(HOME, ".conda", "envs"),):
        if os.path.isdir(root):
            for name in os.listdir(root):
                p = os.path.join(root, name)
                if os.path.isdir(p):
                    candidates.setdefault(p, "conda-root-scan")

    found = []
    for path, source in candidates.items():
        binp = os.path.join(path, "bin", "boltz")
        ver = boltz_version_in_env(path)
        if os.path.exists(binp) or ver:
            found.append({
                "env_path": redact(path),
                "discovered_via": source,
                "boltz_bin": redact(binp) if os.path.exists(binp) else None,
                "boltz_version": ver,
            })
    return found


def inspect_cache():
    cache = os.environ.get("BOLTZ_CACHE") or os.path.join(HOME, ".boltz")
    info = {"path": redact(cache), "from_env_var": "BOLTZ_CACHE" in os.environ,
            "exists": os.path.isdir(cache), "weights": {}, "total_bytes": 0}
    if not info["exists"]:
        return info
    total = 0
    want = ["boltz2_conf.ckpt", "boltz2_aff.ckpt", "boltz1_conf.ckpt",
            "boltz1_aff.ckpt", "mols.tar"]
    for name in want:
        fp = os.path.join(cache, name)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp)
            info["weights"][name] = sz
            total += sz
    info["weights"]["mols_dir"] = os.path.isdir(os.path.join(cache, "mols"))
    try:
        for entry in os.scandir(cache):
            if entry.is_file():
                total = max(total, total)  # already counted key files
    except OSError:
        pass
    info["total_bytes"] = total
    return info


def inspect_gpu():
    info = {"nvidia_smi": False, "gpus": []}
    smi = shutil.which("nvidia-smi")
    if not smi:
        return info
    info["nvidia_smi"] = True
    rc, out, _ = run([smi, "--query-gpu=name,memory.total,driver_version,compute_cap",
                      "--format=csv,noheader"])
    if rc == 0:
        for line in out.strip().splitlines():
            cols = [c.strip() for c in line.split(",")]
            if len(cols) >= 3:
                g = {"name": cols[0], "memory_total": cols[1], "driver": cols[2]}
                if len(cols) >= 4:
                    g["compute_cap"] = cols[3]
                info["gpus"].append(g)
    return info


def deep_torch(env, timeout):
    """Import torch in a separate, timed subprocess. Opt-in only."""
    py = os.path.join(
        next((e for e in (env or "").split(os.pathsep) if e), sys.prefix),
        "bin", "python") if env else sys.executable
    if not os.path.exists(py):
        py = sys.executable
    code = (
        "import json,torch;"
        "d={'torch':torch.__version__,'cuda_build':torch.version.cuda,"
        "'cuda_available':torch.cuda.is_available(),"
        "'device_count':torch.cuda.device_count()};"
        "d['gpus']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())];"
        "d['compute_capability']=[list(torch.cuda.get_device_capability(i)) "
        "for i in range(torch.cuda.device_count())];"
        "print(json.dumps(d))"
    )
    rc, out, err = run([py, "-c", code], timeout=timeout)
    if rc == 0 and out.strip():
        try:
            return {"python": redact(py), **json.loads(out.strip().splitlines()[-1])}
        except Exception:  # noqa: BLE001
            return {"python": redact(py), "error": "could not parse torch output"}
    return {"python": redact(py), "error": redact(err or "torch import failed")}


def verdict(envs, cache):
    has_boltz = any(e.get("boltz_version") or e.get("boltz_bin") for e in envs)
    conf = cache.get("weights", {}).get("boltz2_conf.ckpt")
    if has_boltz and conf:
        return ("VALIDATED-CANDIDATE",
                "Boltz install + Boltz-2 weights present. Run scripts/verify_boltz.py "
                "(or a tiny fixture) to confirm before treating the host as VALIDATED.")
    if has_boltz:
        return ("PROBED",
                "Boltz installed but Boltz-2 weights not found in cache. First run will "
                "download them (a few GB) to the cache path.")
    return ("UNCONFIGURED",
            "No Boltz install found. Use scripts/install_boltz.sh --yes (after "
            "confirming) or `pip install boltz[cuda] -U` in a Python 3.10-3.12 env.")


def main():
    ap = argparse.ArgumentParser(description="Read-only Boltz environment probe.")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--deep", action="store_true",
                    help="import torch in a timed subprocess (opt-in)")
    ap.add_argument("--env", default=None,
                    help="env prefix for --deep (default: current interpreter)")
    ap.add_argument("--timeout", type=int, default=45, help="--deep timeout (s)")
    args = ap.parse_args()

    report = {
        "platform": sys.platform,
        "probe_python": sys.version.split()[0],
        "boltz_envs": discover_envs(),
        "cache": inspect_cache(),
        "gpu": inspect_gpu(),
        "BOLTZ_CACHE": os.environ.get("BOLTZ_CACHE", "(unset -> ~/.boltz)"),
    }
    state, advice = verdict(report["boltz_envs"], report["cache"])
    report["state"] = state
    report["advice"] = advice
    if args.deep:
        report["deep_torch"] = deep_torch(args.env, args.timeout)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    p = print
    p("=" * 64)
    p("BOLTZ ENVIRONMENT PROBE  (read-only; nothing was written/downloaded)")
    p("=" * 64)
    p(f"platform        : {report['platform']}")
    p(f"probe python    : {report['probe_python']}")
    p(f"BOLTZ_CACHE     : {report['BOLTZ_CACHE']}")
    p("")
    p("Boltz installs found:")
    if not report["boltz_envs"]:
        p("  (none)")
    for e in report["boltz_envs"]:
        p(f"  - {e['env_path']}  boltz={e['boltz_version']}  via={e['discovered_via']}")
    p("")
    c = report["cache"]
    p(f"Weights cache   : {c['path']}  exists={c['exists']}")
    if c["exists"]:
        for k, v in c["weights"].items():
            if isinstance(v, bool):
                p(f"    {k}: {v}")
            else:
                p(f"    {k}: {v/1e9:.2f} GB")
    p("")
    g = report["gpu"]
    p(f"nvidia-smi      : {g['nvidia_smi']}")
    for gi in g["gpus"]:
        cc = gi.get("compute_cap", "?")
        p(f"  - {gi['name']}  {gi['memory_total']}  cc={cc}  driver={gi['driver']}")
    if g["gpus"]:
        ccs = [gi.get("compute_cap") for gi in g["gpus"]]
        if any(cc and cc.startswith(("6.", "7.0", "7.2")) for cc in ccs if cc):
            p("  note: pre-Turing GPU(s); if kernels error, try --no_kernels.")
    if args.deep:
        p("")
        p(f"deep torch      : {json.dumps(report['deep_torch'])}")
    p("")
    p(f">> STATE: {report['state']}")
    p(f">> {report['advice']}")


if __name__ == "__main__":
    main()
