#!/usr/bin/env python3
"""cryocodex_env_probe.py -- read-only CryoCodex v1.0.0 host probe with a readiness verdict (stdlib; creates and
downloads nothing; never calls predict.sh, so it can never trigger the 471 MB weights download).

    python3 cryocodex_env_probe.py [--home /abs/CryoCodex] [--env-name cryocodex_env] [--env-check] [--hash]
                                   [--out-root DIR] [--json] [--output FILE]

Run it ON THE NODE THAT WILL RUN CryoCodex (a login node and a GPU node differ). Checks: OS/arch, NVIDIA GPU via
nvidia-smi (name, memory, driver), CUDA_VISIBLE_DEVICES (predict.py:194 overwrites it with -g), host RAM, conda the way
predict.sh finds it (CONDA_EXE, else `conda` on PATH, must be executable; predict.sh:57-63), whether the env exists
(`conda env list --json`), the clone at --home (git HEAD vs the pin a35e73a, predict.sh executable, predict.py
version string), the checkpoint model_state_dicts/CryoCodex.pth (present, size 470,938,660 B, leftover .part), free
disk, and configs/site_config.local.md. --home defaults to `home:` in the site config.
  --env-check  runs `conda run -n ENV python -c ...` once: imports torch (reports version, CUDA build, cuda available,
               device) and the pinned packages. No download, no CryoCodex import.
  --hash       sha256 of the 471 MB checkpoint (ASK FIRST: reads the whole file); compared with the site record.
Verdicts: BLOCKED (not Linux, no NVIDIA GPU visible, or no executable conda) / NOT_INSTALLED (no clone or no env) /
PARTIAL (installed but something is missing or unchecked) / READY_TO_VALIDATE (all present, env imports torch with
CUDA). VALIDATED is never printed: only a passed fixture run (references/validation_runbook.md) recorded in
configs/site_config.local.md gives it. Exit 0 always (the verdict is the result), 2 on usage errors.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mrcheader as mh  # noqa: E402

SITE_CONFIG = os.path.join(os.path.dirname(HERE), "configs", "site_config.local.md")
PINNED_PKGS = {"torch": "2.5.1", "mrcfile": "1.5.4", "numba": "0.61.2", "einops": "0.8.1", "timm": "1.0.24",
               "numexpr": "2.10.0", "numpy": "1.26.4", "scipy": "1.16.0", "tqdm": "4.67.1"}
ENV_CHECK = r"""
import importlib, json, sys
r = {"python": sys.version.split()[0]}
try:
    import torch
    r["torch"] = torch.__version__; r["torch_cuda_build"] = torch.version.cuda
    r["cuda_available"] = torch.cuda.is_available(); r["device_count"] = torch.cuda.device_count()
    if r["cuda_available"] and r["device_count"]:
        p = torch.cuda.get_device_properties(0)
        r["device0"] = "%s %.1f GiB cc %d.%d" % (p.name, p.total_memory / 2**30, p.major, p.minor)
except Exception as e:
    r["torch_error"] = repr(e)[:300]
for n in ["mrcfile", "numba", "einops", "timm", "numexpr", "numpy", "scipy", "tqdm", "PIL", "torchvision"]:
    try:
        r[n] = getattr(importlib.import_module(n), "__version__", "?")
    except Exception as e:
        r[n] = "IMPORT-ERROR " + repr(e)[:120]
print("CRYOCODEX_ENV_CHECK " + json.dumps(r))
"""


def read_site_config(path):
    """Minimal reader for configs/site_config.local.md: top-level `key: value` lines and `weights.sha256`."""
    out = {}
    if not os.path.isfile(path):
        return out
    section = None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                if not line.strip() or line.lstrip().startswith(("#", "```")):
                    continue
                key, _, val = line.strip().partition(":")
                val = val.split(" #")[0].strip()
                if val.startswith("<") or " | " in val:
                    val = ""          # unfilled template placeholder or a list of choices
                if not line[0].isspace():
                    section = key.strip()
                    if val:
                        out.setdefault(section, val)
                elif section and val:
                    out.setdefault(f"{section}.{key.strip()}", val)
    except OSError:
        pass
    return out


def run(cmd, timeout=30, env=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


def sha256_of(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def git_head(home):
    rc, out, _ = run(["git", "-C", home, "rev-parse", "HEAD"]) if shutil.which("git") else (-1, "", "")
    if rc == 0 and re.fullmatch(r"[0-9a-f]{40}", out):
        return out, "git"
    try:   # no git binary: read .git/HEAD and the ref by hand
        head = open(os.path.join(home, ".git", "HEAD")).read().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            p = os.path.join(home, ".git", ref)
            if os.path.isfile(p):
                return open(p).read().strip(), ".git files"
            packed = os.path.join(home, ".git", "packed-refs")
            if os.path.isfile(packed):
                for line in open(packed):
                    if line.strip().endswith(ref):
                        return line.split()[0], ".git packed-refs"
        elif re.fullmatch(r"[0-9a-f]{40}", head):
            return head, ".git files (detached)"
    except OSError:
        pass
    return None, None


def meminfo():
    out = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                if k in ("MemTotal", "MemAvailable"):
                    out[k] = int(v.split()[0]) * 1024
    except OSError:
        pass
    return out


def probe(a):
    site = read_site_config(SITE_CONFIG)
    r = {"probe_version": "1.0.0", "pin": mh.PIN_COMMIT, "host": {}, "gpu": {}, "conda": {}, "clone": {}, "weights": {},
         "env_check": None, "disk": {}, "site_config": {}, "blockers": [], "install_gaps": [], "gaps": [], "notes": []}
    # host
    r["host"] = {"hostname": socket.gethostname(), "system": platform.system(), "machine": platform.machine(),
                 "platform": platform.platform(), "python": platform.python_version(),
                 "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "ram": meminfo()}
    if platform.system() != "Linux":
        r["blockers"].append(f"{platform.system()} host: CryoCodex needs Linux + a CUDA GPU (README; compute is cuda:0, predict.py:82). "
                             "Only header inspection and command drafting here.")
    elif platform.machine() not in ("x86_64", "AMD64"):
        r["gaps"].append(f"{platform.machine()} Linux: the README install pulls PyPI torch 2.5.1, whose CUDA wheels are x86_64 only; "
                         "unsupported/unknown here")
    # gpu
    smi = shutil.which("nvidia-smi")
    gpus = []
    if smi:
        rc, out, err = run([smi, "--query-gpu=index,name,memory.total,memory.free,driver_version", "--format=csv,noheader"])
        if rc == 0 and out:
            for line in out.splitlines():
                p = [x.strip() for x in line.split(",")]
                gpus.append({"index": p[0], "name": p[1] if len(p) > 1 else None, "memory_total": p[2] if len(p) > 2 else None,
                             "memory_free": p[3] if len(p) > 3 else None, "driver": p[4] if len(p) > 4 else None})
        else:
            r["gpu"]["nvidia_smi_error"] = (err or out)[:200]
    r["gpu"]["nvidia_smi"] = smi
    r["gpu"]["devices"] = gpus
    cvd = os.environ.get("CUDA_VISIBLE_DEVICES")
    r["gpu"]["cuda_visible_devices"] = cvd
    if not gpus and platform.system() == "Linux":
        r["blockers"].append("no NVIDIA GPU visible (nvidia-smi absent or lists none): run the probe on the GPU node; "
                             "a login/CPU node can only inspect headers and draft commands")
    if cvd is not None:
        r["notes"].append(f"CUDA_VISIBLE_DEVICES={cvd!r} is set: predict.py overwrites it with -g (default \"0\"); "
                          "pass -g \"${CUDA_VISIBLE_DEVICES:-0}\" under a scheduler (derived, runbook R16)")
    # conda as predict.sh finds it
    conda_exe = os.environ.get("CONDA_EXE") or shutil.which("conda")
    r["conda"]["exe"] = conda_exe
    r["conda"]["source"] = "CONDA_EXE" if os.environ.get("CONDA_EXE") else ("PATH" if conda_exe else None)
    r["conda"]["executable"] = bool(conda_exe and os.path.isfile(conda_exe) and os.access(conda_exe, os.X_OK))
    env_name = a.env_name or site.get("env") or "cryocodex_env"
    r["conda"]["env_name"] = env_name
    env_exists = None
    if r["conda"]["executable"]:
        rc, out, _ = run([conda_exe, "--version"])
        r["conda"]["version"] = out if rc == 0 else None
        rc, out, err = run([conda_exe, "env", "list", "--json"], timeout=90)
        if rc == 0:
            try:
                envs = json.loads(out).get("envs", [])
                r["conda"]["envs_found"] = len(envs)
                env_exists = any(os.path.basename(e.rstrip("/")) == env_name for e in envs)
            except ValueError:
                r["conda"]["env_list_error"] = "unparsable JSON"
        else:
            r["conda"]["env_list_error"] = (err or out)[:200]
        r["conda"]["env_exists"] = env_exists
        if env_exists is False:
            r["install_gaps"].append(f"conda env '{env_name}' not found (README: conda create -y -n cryocodex_env python=3.11; "
                                     "or set CRYOCODEX_ENV)")
        elif env_exists is None:
            r["gaps"].append("could not list conda envs; env presence unknown")
    else:
        msg = "no executable conda (CONDA_EXE unset and no `conda` executable on PATH; predict.sh:57-63)"
        if shutil.which("mamba") or shutil.which("micromamba"):
            msg += "; mamba/micromamba alone are not what predict.sh looks for"
        r["blockers"].append(msg + ". If conda is only a shell function, export CONDA_EXE=/abs/path/to/bin/conda")
    # clone
    home = a.home or site.get("home")
    r["clone"]["home"] = home
    r["clone"]["home_source"] = "--home" if a.home else ("site config home" if home else None)
    ck = None
    if not home:
        r["install_gaps"].append("no CryoCodex clone given (pass --home /abs/CryoCodex, or set home: in configs/site_config.local.md)")
    elif not os.path.isdir(home):
        r["install_gaps"].append(f"clone not found at {home}")
    else:
        ps = os.path.join(home, "predict.sh")
        py = os.path.join(home, "predict.py")
        r["clone"]["predict_sh"] = os.path.isfile(ps)
        r["clone"]["predict_sh_executable"] = os.path.isfile(ps) and os.access(ps, os.X_OK)
        r["clone"]["predict_py"] = os.path.isfile(py)
        if not (r["clone"]["predict_sh"] and r["clone"]["predict_py"]):
            r["install_gaps"].append(f"{home} does not look like a CryoCodex clone (predict.sh/predict.py missing)")
        else:
            if not r["clone"]["predict_sh_executable"]:
                r["gaps"].append("predict.sh is not executable (stored as 100644 in git): run `chmod +x predict.sh` in the clone")
            try:
                m = re.search(r'__version__\s*=\s*"([^"]+)"', open(py, encoding="utf-8", errors="replace").read())
                r["clone"]["predict_py_version"] = m.group(1) if m else None
            except OSError:
                r["clone"]["predict_py_version"] = None
            head, how = git_head(home)
            r["clone"]["head"], r["clone"]["head_via"] = head, how
            r["clone"]["at_pin"] = head == mh.PIN_COMMIT if head else None
            if head is None:
                r["gaps"].append("clone commit unknown (no .git): cannot confirm v1.0.0")
            elif head != mh.PIN_COMMIT:
                r["gaps"].append(f"clone HEAD {head[:12]} != pin {mh.PIN_COMMIT[:12]} (v1.0.0): `git checkout v1.0.0`, or re-review the skill")
            ck = os.path.join(home, "model_state_dicts", "CryoCodex.pth")
    # weights
    if ck:
        w = r["weights"]
        w["path"] = ck
        w["present"] = os.path.isfile(ck) and os.path.getsize(ck) > 0
        w["part_file"] = os.path.exists(ck + ".part")
        if w["part_file"]:
            r["notes"].append("a CryoCodex.pth.part file exists: an earlier download was interrupted")
        if w["present"]:
            w["bytes"] = os.path.getsize(ck)
            w["bytes_match_head"] = w["bytes"] == mh.WEIGHTS_BYTES
            if not w["bytes_match_head"]:
                r["gaps"].append(f"checkpoint is {w['bytes']} B, not {mh.WEIGHTS_BYTES} B (server HEAD 2026-11-24): partial or changed file")
            if a.hash:
                w["sha256"] = sha256_of(ck)
                rec = site.get("weights.sha256")
                if rec:
                    w["sha256_matches_site_record"] = (w["sha256"] == rec)
                    if not w["sha256_matches_site_record"]:
                        r["gaps"].append("checkpoint sha256 differs from the site record (weights.sha256): changed or corrupt file")
                else:
                    r["notes"].append("no published checksum exists; record this sha256 as weights.sha256 in configs/site_config.local.md")
        else:
            r["gaps"].append("no checkpoint at model_state_dicts/CryoCodex.pth: the next predict.sh call other than -h "
                             "(including --version) downloads 471 MB from yanglab.qd.sdu.edu.cn -- ask first, or place the file")
    # env check (optional, runs python inside the env)
    if a.env_check:
        if r["conda"]["executable"] and env_exists:
            rc, out, err = run([conda_exe, "run", "-n", env_name, "python", "-c", ENV_CHECK], timeout=600)
            res = None
            for line in out.splitlines():
                if line.startswith("CRYOCODEX_ENV_CHECK "):
                    try:
                        res = json.loads(line.split(" ", 1)[1])
                    except ValueError:
                        res = None
            r["env_check"] = res or {"error": (err or out)[-300:], "rc": rc}
            if res:
                mism = {k: (res.get(k), v) for k, v in PINNED_PKGS.items() if str(res.get(k, "")).split("+")[0] != v}
                res["pin_mismatch"] = mism
                if "torch_error" in res:
                    r["gaps"].append(f"torch does not import in '{env_name}': {res['torch_error'][:120]}")
                elif not res.get("cuda_available"):
                    r["gaps"].append(f"torch {res.get('torch')} (CUDA build {res.get('torch_cuda_build')}) sees no CUDA device "
                                     "in the env: driver too old for the wheel, or no GPU on this node")
                if mism:
                    r["gaps"].append("packages differ from requirements.txt pins: "
                                     + ", ".join(f"{k} {v[0]} (pin {v[1]})" for k, v in mism.items()))
                if not str(res.get("python", "")).startswith("3.11"):
                    r["notes"].append(f"env Python {res.get('python')}: the README uses 3.11 (3.12 untested)")
            else:
                r["gaps"].append(f"--env-check failed (rc {rc}); see env_check.error")
        else:
            r["env_check"] = {"skipped": "no executable conda or env missing"}
    elif not r["blockers"] and not r["install_gaps"]:
        r["gaps"].append("env not checked: re-run with --env-check (imports torch inside the env; no download)")
    # disk
    for label, path in (("home", home if home and os.path.isdir(home) else None), ("out_root", a.out_root)):
        if path and os.path.isdir(path):
            du = shutil.disk_usage(path)
            r["disk"][label] = {"path": path, "free_bytes": du.free}
    # site config
    r["site_config"]["path"] = SITE_CONFIG if os.path.exists(SITE_CONFIG) else None
    for k in ("host", "state", "date_probed", "date_validated", "home", "env", "expires_when", "weights.sha256"):
        if site.get(k):
            r["site_config"][k] = site[k]
    # verdict
    if r["blockers"]:
        v = "BLOCKED"
    elif r["install_gaps"]:
        v = "NOT_INSTALLED"
    elif r["gaps"]:
        v = "PARTIAL"
    else:
        v = "READY_TO_VALIDATE"
    r["verdict"] = v
    return r


def human(r):
    L = []
    h = r["host"]
    ram = h["ram"]
    L.append(f"host     : {h['hostname']}  {h['system']} {h['machine']}  python {h['python']}  slurm job {h['slurm_job_id'] or 'none'}"
             + (f"  RAM {mh.fmt_bytes(ram.get('MemTotal'))} total / {mh.fmt_bytes(ram.get('MemAvailable'))} available" if ram else ""))
    g = r["gpu"]
    if g["devices"]:
        for d in g["devices"]:
            L.append(f"gpu      : [{d['index']}] {d['name']}  total {d['memory_total']}  free {d['memory_free']}  driver {d['driver']}")
    else:
        L.append(f"gpu      : none visible (nvidia-smi {'found' if g['nvidia_smi'] else 'absent'})")
    if g.get("cuda_visible_devices") is not None:
        L.append(f"           CUDA_VISIBLE_DEVICES={g['cuda_visible_devices']}")
    c = r["conda"]
    L.append(f"conda    : {c.get('exe') or 'NOT FOUND'} ({c.get('source')}, executable {c.get('executable')}) {c.get('version') or ''}"
             f"  env '{c['env_name']}': {({True: 'present', False: 'MISSING', None: 'unknown'})[c.get('env_exists')]}")
    cl = r["clone"]
    if cl.get("home"):
        L.append(f"clone    : {cl['home']} ({cl['home_source']})  HEAD {(cl.get('head') or 'unknown')[:12]}"
                 f" {'= pin v1.0.0' if cl.get('at_pin') else '(pin a35e73a7)'}  predict.py version {cl.get('predict_py_version')}"
                 f"  predict.sh executable {cl.get('predict_sh_executable')}")
    else:
        L.append("clone    : not given (--home)")
    w = r["weights"]
    if w:
        L.append(f"weights  : {w['path']}  " + (f"{w['bytes']} B {'= HEAD size' if w['bytes_match_head'] else '!= 470938660'}" if w.get("present") else "MISSING")
                 + (f"  sha256 {w['sha256']}" if w.get("sha256") else "")
                 + (f"  site record {'match' if w['sha256_matches_site_record'] else 'MISMATCH'}" if "sha256_matches_site_record" in w else ""))
    ec = r["env_check"]
    if ec:
        if "torch" in ec or "torch_error" in ec:
            L.append(f"env check: python {ec.get('python')}  torch {ec.get('torch')} (CUDA build {ec.get('torch_cuda_build')})  "
                     f"cuda_available {ec.get('cuda_available')}  {ec.get('device0') or ''}"
                     + (f"  pin mismatches {ec['pin_mismatch']}" if ec.get("pin_mismatch") else "  packages = requirements.txt pins"))
        else:
            L.append(f"env check: {ec}")
    for k, d in r["disk"].items():
        L.append(f"disk     : {k} {d['path']} free {mh.fmt_bytes(d['free_bytes'])}")
    sc = r["site_config"]
    L.append(f"site cfg : {sc.get('path') or 'none (copy configs/site_config.template.md to configs/site_config.local.md)'}"
             + (f"  state {sc['state']}" if sc.get("state") else ""))
    for n in r["notes"]:
        L.append(f"note     : {n}")
    for b in r["blockers"]:
        L.append(f"blocker  : {b}")
    for b in r["install_gaps"]:
        L.append(f"install  : {b}")
    for b in r["gaps"]:
        L.append(f"gap      : {b}")
    L.append(f">> HOST VERDICT: {r['verdict']}")
    L.append("   (never VALIDATED from a probe: that needs the fixture run of references/validation_runbook.md on this host)")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--home", help="absolute path of the CryoCodex clone (default: home: in configs/site_config.local.md)")
    ap.add_argument("--env-name", help="conda env name (default: env: in the site config, else cryocodex_env)")
    ap.add_argument("--env-check", action="store_true", help="import torch and the pinned packages inside the env (no download)")
    ap.add_argument("--hash", action="store_true", help="sha256 of the 471 MB checkpoint (ask first)")
    ap.add_argument("--out-root", help="directory where outputs will go (reports free space)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--output", help="also write the report to this file (refuses to overwrite)")
    a = ap.parse_args(argv)
    if a.home and not os.path.isabs(a.home):
        print("usage error: --home must be an absolute path", file=sys.stderr)
        return 2
    r = probe(a)
    text = json.dumps(r, indent=1, default=str) if a.json else human(r)
    print(text)
    if a.output:
        if os.path.exists(a.output):
            print(f"not written: {a.output} exists", file=sys.stderr)
            return 2
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
