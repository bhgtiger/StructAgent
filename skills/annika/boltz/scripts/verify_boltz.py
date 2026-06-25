#!/usr/bin/env python3
"""Post-install verifier for Boltz.

Default checks are light and do not run a prediction:
  1. `boltz` console script resolves and `boltz --help` works.
  2. boltz + torch import; report versions and CUDA availability.
  3. Boltz-2 weights present in the cache.

`--fixture` additionally runs a tiny no-MSA prediction (Trp-cage, single-sequence
mode) to confirm the host can actually predict — this uses the GPU and writes a
structure into a temp dir. It is opt-in because it is a real compute action.

Usage:
  python verify_boltz.py
  python verify_boltz.py --env /soft/anaconda-new/envs/boltz2
  python verify_boltz.py --env /soft/anaconda-new/envs/boltz2 --fixture
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HOME = os.path.expanduser("~")
FIXTURE_YAML = """version: 1
sequences:
  - protein:
      id: A
      sequence: NLYIQWLKDGGPSSGRPPPS
      msa: empty
"""


def redact(s):
    return s.replace(HOME, "~") if isinstance(s, str) and HOME != "/" else s


def bins(env):
    if env:
        return os.path.join(env, "bin", "python"), os.path.join(env, "bin", "boltz")
    py = sys.executable
    from shutil import which
    return py, (which("boltz") or "boltz")


def run(cmd, timeout=900):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # noqa: BLE001
        return None, "", str(e)


def main():
    ap = argparse.ArgumentParser(description="Verify a Boltz install.")
    ap.add_argument("--env", default=None, help="conda env prefix to verify")
    ap.add_argument("--fixture", action="store_true",
                    help="also run a tiny no-MSA prediction (real GPU compute)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    py, boltz = bins(args.env)
    results = {"env": redact(args.env or "(current/PATH)"), "checks": {}}

    # 1. boltz --help
    rc, out, err = run([boltz, "--help"], timeout=120)
    results["checks"]["boltz_help"] = {"ok": rc == 0,
                                       "detail": "help printed" if rc == 0 else redact(err)}

    # 2. import boltz + torch
    rc, out, err = run([py, "-c",
        "import json,boltz,torch;"
        "print(json.dumps({'boltz':getattr(boltz,'__version__','?'),"
        "'torch':torch.__version__,'cuda':torch.cuda.is_available(),"
        "'cuda_build':torch.version.cuda,'ngpu':torch.cuda.device_count()}))"],
        timeout=180)
    if rc == 0 and out.strip():
        try:
            results["checks"]["imports"] = {"ok": True, **json.loads(out.strip().splitlines()[-1])}
        except Exception:  # noqa: BLE001
            results["checks"]["imports"] = {"ok": True, "detail": out.strip()[-200:]}
    else:
        results["checks"]["imports"] = {"ok": False, "detail": redact(err)[-300:]}

    # 3. weights
    cache = os.environ.get("BOLTZ_CACHE") or os.path.join(HOME, ".boltz")
    conf = os.path.join(cache, "boltz2_conf.ckpt")
    results["checks"]["weights"] = {"ok": os.path.isfile(conf),
                                    "cache": redact(cache),
                                    "boltz2_conf.ckpt": os.path.isfile(conf)}

    # 4. optional fixture
    if args.fixture:
        d = tempfile.mkdtemp(prefix="boltz_verify_")
        yml = os.path.join(d, "fixture.yaml")
        with open(yml, "w") as f:
            f.write(FIXTURE_YAML)
        rc, out, err = run([boltz, "predict", yml, "--out_dir", d,
                            "--recycling_steps", "1", "--sampling_steps", "25",
                            "--diffusion_samples", "1", "--output_format", "pdb",
                            "--seed", "42"], timeout=1800)
        produced = []
        for root, _, files in os.walk(d):
            for fn in files:
                if fn.endswith(".pdb"):
                    produced.append(os.path.join(root, fn))
        results["checks"]["fixture"] = {"ok": rc == 0 and bool(produced),
                                        "out_dir": redact(d),
                                        "pdb_written": [redact(p) for p in produced],
                                        "detail": "" if rc == 0 else redact(err)[-400:]}

    all_ok = all(v.get("ok") for v in results["checks"].values())
    results["PASS"] = all_ok

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("BOLTZ VERIFY —", "PASS" if all_ok else "FAIL", f"(env: {results['env']})")
        for name, v in results["checks"].items():
            print(f"  [{'ok' if v.get('ok') else 'XX'}] {name}: "
                  f"{ {k: x for k, x in v.items() if k != 'ok'} }")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
