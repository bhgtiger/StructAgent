#!/usr/bin/env python3
"""cryofm_env_probe.py -- read-only CryoFM2 host probe with a verdict (stdlib only; creates and downloads nothing).

    python3 cryofm_env_probe.py [--json] [--sif IMAGE.sif] [--weights-dir DIR] [--cfm NAME] [--hash] [--run-help]

Looks for: the node (hostname, Slurm job, GPUs via nvidia-smi, device nodes), a runnable `cfm` (PATH or --cfm), an
Apptainer image (--sif, $CRYOFM_SIF, or `runtime.image` in configs/site_config.local.md), the three pinned weight
folders (--weights-dir, $CRYOFM_WEIGHTS, parent of $CRYOFM_MODEL_DIR, or `weights.dir` in the site config),
caches/TMPDIR, and the skill's site config. Nothing is hard-coded for any host. --hash re-reads ~2 GB to verify the weights' sha256 (ask first). --run-help runs `cfm --help`
(spawns the container; fine on CPU nodes, takes seconds).

Verdicts: UNCONFIGURED (no cfm and no image/env), PROBED (something is missing or no GPU on this node),
VALIDATED-CANDIDATE (cfm + runtime + 3 pinned weight folders + GPU present). VALIDATED is never printed here:
only a passed GPU fixture recorded in configs/site_config.local.md gives it.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys

PIN = {
    "revision": "4e308f7f028af46ca2c7ee5af81e29775bc370dd",
    "variants": {
        "cryofm2-pretrain": (672397148, "8f10dc552fceedae8a3c574e9b9d259de7d1f5047f4f2107d9309fae9512f413"),
        "cryofm2-emhancer": (672409268, "96576420fe03fc93088b40fdb1e7f785d100e6ed49833050c961670bdfaee163"),
        "cryofm2-emready": (672409268, "77c1fa590eaee1906e8470d3659c981855a92fcf4e6a7817b48f0069cd6d2bca"),
    },
    "config_bytes": {"cryofm2-pretrain": 1148, "cryofm2-emhancer": 1240, "cryofm2-emready": 1237},
}
SITE_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "site_config.local.md")


def read_site_config(path):
    """Minimal reader for configs/site_config.local.md: top-level keys plus runtime.image/image_sha256/activation and
    weights.dir (first occurrence each; values end at the first ' #'). Returns {} when the file is absent."""
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
                if not line[0].isspace() and ":" in line:
                    key, _, val = line.partition(":")
                    section = key.strip()
                    val = val.split(" #")[0].strip()
                    if val and section in ("host", "state", "date_validated", "date_probed", "activation", "expires_when"):
                        out.setdefault(section, val)
                    continue
                key, _, val = line.strip().partition(":")
                key, val = key.strip(), val.split(" #")[0].strip()
                if section == "runtime" and key in ("image", "image_sha256") and val:
                    out.setdefault("runtime." + key, val)
                elif section == "weights" and key == "dir" and val:
                    out.setdefault("weights.dir", val)
    except OSError:
        pass
    return out


def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


def sha256_of(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def probe(a):
    r = {"probe_version": "1.1.0", "host": {}, "gpu": {}, "runtime": {}, "weights": {}, "env": {}, "site_config": {}, "blockers": [], "notes": []}
    site = read_site_config(SITE_CONFIG)
    # host
    r["host"] = {"hostname": socket.gethostname(), "os": platform.platform(), "python": platform.python_version(),
                 "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "slurm_partition": os.environ.get("SLURM_JOB_PARTITION"),
                 "cwd": os.getcwd()}
    # gpu
    dev_nodes = [d for d in ("/dev/nvidiactl", "/dev/nvidia0") if os.path.exists(d)]
    r["gpu"]["device_nodes"] = dev_nodes
    smi = shutil.which("nvidia-smi")
    r["gpu"]["nvidia_smi"] = smi
    gpus = []
    if smi:
        rc, out, err = run([smi, "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader"])
        if rc != 0:
            rc, out, err = run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
        if rc == 0 and out:
            for line in out.splitlines():
                parts = [x.strip() for x in line.split(",")]
                gpus.append({"name": parts[0], "memory": parts[1] if len(parts) > 1 else None,
                             "driver": parts[2] if len(parts) > 2 else None, "compute_cap": parts[3] if len(parts) > 3 else None})
        else:
            r["gpu"]["nvidia_smi_error"] = (err or out)[:200]
    r["gpu"]["devices"] = gpus
    r["gpu"]["cuda_visible_devices"] = os.environ.get("CUDA_VISIBLE_DEVICES")
    if not gpus:
        r["blockers"].append("no GPU visible on this node (login/CPU node?) — sampling needs a GPU node; --help and header checks are fine here")
    # runtime
    cfm = shutil.which(a.cfm) if a.cfm else shutil.which("cfm")
    r["runtime"]["cfm"] = cfm
    kind = None
    if cfm:
        try:
            with open(cfm, "rb") as fh:
                head = fh.read(4096).decode("utf-8", "replace")
            if "apptainer exec" in head or "singularity exec" in head:
                kind = "container-launcher"
                r["runtime"]["launcher_mentions_sif"] = [l.strip() for l in head.splitlines() if "SIF=" in l][:2]
                r["runtime"]["launcher_shorthand"] = "--model-dir pretrain|emhancer|emready" if "cryofm2-$_arg" in head or "cryofm2-" in head else None
            elif "python" in head[:200]:
                kind = "python-entrypoint"
            else:
                kind = "unknown-script"
        except OSError:
            kind = "unreadable"
    r["runtime"]["cfm_kind"] = kind
    r["runtime"]["cfm_relion"] = shutil.which("cfm-relion")
    r["runtime"]["apptainer"] = shutil.which("apptainer") or shutil.which("singularity")
    if r["runtime"]["apptainer"]:
        rc, out, _ = run([r["runtime"]["apptainer"], "--version"])
        r["runtime"]["apptainer_version"] = out if rc == 0 else None
    r["runtime"]["accelerate_on_path"] = shutil.which("accelerate")
    r["runtime"]["conda_prefix"] = os.environ.get("CONDA_PREFIX")
    sif, sif_src = None, None
    for src, cand in (("--sif", a.sif), ("env CRYOFM_SIF", os.environ.get("CRYOFM_SIF")), ("site config runtime.image", site.get("runtime.image"))):
        if cand:
            sif, sif_src = os.path.expanduser(cand), src
            break
    r["runtime"]["sif"] = sif
    r["runtime"]["sif_source"] = sif_src
    if sif:
        if os.path.exists(sif):
            r["runtime"]["sif_bytes"] = os.path.getsize(sif)
            if a.hash:
                r["runtime"]["sif_sha256"] = sha256_of(sif)
                if site.get("runtime.image_sha256"):
                    r["runtime"]["sif_sha256_matches_site_record"] = r["runtime"]["sif_sha256"] == site["runtime.image_sha256"]
        else:
            r["blockers"].append(f"image not found: {sif}")
    if not cfm and not sif and not r["runtime"]["conda_prefix"]:
        r["blockers"].append("no `cfm` on PATH and no image: CryoFM is not installed here (see references/02)")
    elif not cfm:
        hint = site.get("activation") or "see configs/site_config.local.md `activation:`"
        r["blockers"].append(f"no `cfm` on PATH (run the site activation first: {hint})")
    if a.run_help and cfm:
        rc, out, err = run([cfm, "--help"], timeout=300)
        r["runtime"]["cfm_help_rc"] = rc
        r["runtime"]["cfm_help_first_line"] = (out or err).splitlines()[0] if (out or err) else None
        if rc != 0:
            r["blockers"].append(f"`cfm --help` failed (rc {rc}): {(err or out)[-200:]}")
    # weights
    wdir, wsrc = None, None
    if a.weights_dir:
        wdir, wsrc = a.weights_dir, "--weights-dir"
    elif os.environ.get("CRYOFM_WEIGHTS"):
        wdir, wsrc = os.environ["CRYOFM_WEIGHTS"], "env CRYOFM_WEIGHTS"
    elif os.environ.get("CRYOFM_MODEL_DIR") and os.path.isdir(os.path.expanduser(os.environ["CRYOFM_MODEL_DIR"])):
        wdir, wsrc = os.path.dirname(os.path.abspath(os.path.expanduser(os.environ["CRYOFM_MODEL_DIR"]))), "parent of env CRYOFM_MODEL_DIR"
    elif site.get("weights.dir"):
        wdir, wsrc = site["weights.dir"], "site config weights.dir"
    wdir = os.path.expanduser(wdir) if wdir else None
    r["weights"]["dir"] = wdir
    r["weights"]["dir_source"] = wsrc
    ok_variants = 0
    if wdir and os.path.isdir(wdir):
        pin_file = os.path.join(os.path.dirname(wdir.rstrip("/")), "weights.pin.json")
        if os.path.exists(pin_file):
            try:
                with open(pin_file) as fh:
                    r["weights"]["pin_file"] = json.load(fh)
            except (OSError, ValueError):
                r["weights"]["pin_file"] = "unreadable"
        for v, (size, sha) in PIN["variants"].items():
            d = os.path.join(wdir, v)
            info = {"dir": d, "config_yaml": os.path.isfile(os.path.join(d, "config.yaml")),
                    "model_safetensors": os.path.isfile(os.path.join(d, "model.safetensors"))}
            if info["model_safetensors"]:
                info["bytes"] = os.path.getsize(os.path.join(d, "model.safetensors"))
                info["bytes_match_pin"] = info["bytes"] == size
                if a.hash:
                    info["sha256"] = sha256_of(os.path.join(d, "model.safetensors"))
                    info["sha256_match_pin"] = info["sha256"] == sha
            if info["config_yaml"]:
                info["config_bytes"] = os.path.getsize(os.path.join(d, "config.yaml"))
                info["config_bytes_match_pin"] = info["config_bytes"] == PIN["config_bytes"][v]
            good = info["config_yaml"] and info["model_safetensors"] and info.get("bytes_match_pin", False) and info.get("sha256_match_pin", True)
            info["ok"] = bool(good)
            ok_variants += int(bool(good))
            r["weights"][v] = info
        r["weights"]["variants_ok"] = ok_variants
        if ok_variants < 3:
            r["blockers"].append(f"only {ok_variants}/3 weight folders are complete and pin-sized under {wdir}")
    else:
        r["blockers"].append("weights folder not found (pass --weights-dir, set CRYOFM_WEIGHTS / CRYOFM_MODEL_DIR, or fill weights.dir in configs/site_config.local.md)")
    # env
    keys = ["TMPDIR", "HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "HF_HOME", "XDG_CACHE_HOME", "MPLCONFIGDIR", "TRITON_CACHE_DIR",
            "CUDA_VISIBLE_DEVICES", "CRYOFM_MODEL_DIR", "CRYOFM_HALF1_PORT", "CRYOFM_HALF2_PORT", "ACCELERATE_USE_CPU", "ACCELERATE_TORCH_DEVICE",
            "NCCL_DEBUG", "CFM_NO_NV", "CFM_FORCE_NV"]
    r["env"] = {k: os.environ.get(k) for k in keys if os.environ.get(k) is not None}
    home = os.path.expanduser("~")
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir and os.path.realpath(tmpdir).startswith(os.path.realpath(home)):
        r["notes"].append("TMPDIR is under $HOME: the launcher's caches would land in the (inode-limited) home; set a node-local TMPDIR")
    if os.environ.get("ACCELERATE_USE_CPU") or os.environ.get("ACCELERATE_TORCH_DEVICE"):
        r["notes"].append("ACCELERATE_USE_CPU / ACCELERATE_TORCH_DEVICE are set and override the device choice")
    # site config
    r["site_config"]["path"] = SITE_CONFIG if os.path.exists(SITE_CONFIG) else None
    for key in ("state", "date_validated", "host", "activation", "expires_when", "runtime.image", "weights.dir"):
        if site.get(key):
            r["site_config"][key] = site[key]
    # verdict
    if (not cfm) and (not sif) and (not r["runtime"]["conda_prefix"]):
        verdict = "UNCONFIGURED"
    elif r["blockers"]:
        verdict = "PROBED"
    else:
        verdict = "VALIDATED-CANDIDATE"
    r["verdict"] = {"state": verdict, "blockers": r["blockers"]}
    return r


def human(r):
    L = []
    h = r["host"]
    L.append(f"host     : {h['hostname']}  ({h['os']}; python {h['python']}; slurm job {h['slurm_job_id'] or 'none'} {h['slurm_partition'] or ''})")
    g = r["gpu"]
    if g["devices"]:
        for d in g["devices"]:
            L.append(f"gpu      : {d['name']}  {d['memory']}  driver {d['driver']}  cc {d.get('compute_cap')}")
    else:
        L.append(f"gpu      : none visible (device nodes {g['device_nodes'] or 'absent'}; nvidia-smi {'found' if g['nvidia_smi'] else 'absent'})")
    if g.get("cuda_visible_devices") is not None:
        L.append(f"           CUDA_VISIBLE_DEVICES={g['cuda_visible_devices']}")
    rt = r["runtime"]
    L.append(f"cfm      : {rt['cfm'] or 'NOT on PATH'}  kind {rt['cfm_kind']}" + (f"  shorthand {rt['launcher_shorthand']}" if rt.get("launcher_shorthand") else ""))
    L.append(f"cfm-relion: {rt['cfm_relion'] or 'absent'}   apptainer: {rt.get('apptainer_version') or rt['apptainer'] or 'absent'}   accelerate on PATH: {rt['accelerate_on_path'] or 'no'}")
    if rt.get("sif"):
        L.append(f"image    : {rt['sif']}  {rt.get('sif_bytes', 'MISSING')} B  (from {rt.get('sif_source')})" + (f"  sha256 {rt['sif_sha256'][:12]}… match={rt.get('sif_sha256_matches_site_record')}" if rt.get("sif_sha256") else ""))
    if rt.get("cfm_help_rc") is not None:
        L.append(f"cfm --help: rc {rt['cfm_help_rc']}  '{rt.get('cfm_help_first_line')}'")
    w = r["weights"]
    L.append(f"weights  : {w.get('dir') or 'NOT FOUND'}" + (f"  (from {w['dir_source']})" if w.get("dir_source") else "") + (f"  (pin file revision {w['pin_file'].get('revision','?')[:8]}, verified {w['pin_file'].get('verified')})" if isinstance(w.get("pin_file"), dict) else ""))
    for v in PIN["variants"]:
        if v in w:
            i = w[v]
            L.append(f"           {v:17s} config {'ok' if i['config_yaml'] else 'MISSING'}  weights {'ok' if i['model_safetensors'] else 'MISSING'}"
                     + (f" {i['bytes']} B {'=' if i.get('bytes_match_pin') else '!='} pin" if i.get("bytes") is not None else "")
                     + (f"  sha256 {'ok' if i.get('sha256_match_pin') else 'MISMATCH'}" if "sha256" in i else ""))
    if r["env"]:
        L.append("env      : " + " ".join(f"{k}={v}" for k, v in r["env"].items()))
    sc = r["site_config"]
    L.append(f"site cfg : {sc.get('path') or 'none (copy configs/site_config.template.md)'}" + (f"  state {sc.get('state')}  validated {sc.get('date_validated')}" if sc.get("state") else "") + (f"  activation: {sc['activation']}" if sc.get("activation") else ""))
    for n in r["notes"]:
        L.append(f"note     : {n}")
    for b in r["blockers"]:
        L.append(f"blocker  : {b}")
    L.append(f">> HOST VERDICT: {r['verdict']['state']}")
    L.append("   (VALIDATED is granted only by a passed GPU fixture recorded in configs/site_config.local.md)")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sif", help="Apptainer image to check (default: $CRYOFM_SIF, else runtime.image from configs/site_config.local.md)")
    ap.add_argument("--weights-dir", help="folder holding cryofm2-pretrain/ cryofm2-emhancer/ cryofm2-emready/ (default: $CRYOFM_WEIGHTS, parent of $CRYOFM_MODEL_DIR, else weights.dir from the site config)")
    ap.add_argument("--cfm", help="name of the cfm launcher on PATH (default cfm)")
    ap.add_argument("--hash", action="store_true", help="sha256 the image and the three weight files (~2 GB read; ask first)")
    ap.add_argument("--run-help", action="store_true", help="run `cfm --help` (spawns the runtime)")
    a = ap.parse_args(argv)
    r = probe(a)
    print(json.dumps(r, indent=1, default=str) if a.json else human(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
