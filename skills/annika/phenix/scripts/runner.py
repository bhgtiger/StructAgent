#!/usr/bin/env python3
"""Phenix refinement runner for OpenClaw.

Usage:
  runner.py --lane xray --model m.pdb --data d.mtz [--ligands l1.cif l2.cif] [options]
  runner.py --lane em   --model m.pdb --map map.mrc --resolution 3.2 [options]

Creates a timestamped job directory, stages inputs, builds a final PHIL,
runs Phenix, collects outputs, writes provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PRESETS_DIR = SKILL_DIR / "presets"
RUNS_DIR = Path(os.environ.get("PHENIX_RUNS_DIR", "runs/phenix"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def short_id() -> str:
    import random, string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def sha256_file(path: Path, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
            if max_bytes and f.tell() >= max_bytes:
                break
    return h.hexdigest()


def stage_input(src: Path, dest_dir: Path, copy: bool = True) -> Path:
    dest = dest_dir / src.name
    if copy:
        shutil.copy2(src, dest)
    else:
        dest.symlink_to(src.resolve())
    return dest


def find_phenix_env() -> str | None:
    env_var = os.environ.get("PHENIX_ENV_SH")
    if env_var and Path(env_var).exists():
        return env_var
    # common macOS locations
    for pattern in ["/Applications/phenix-*/phenix_env.sh",
                    os.path.expanduser("~/phenix-*/phenix_env.sh")]:
        import glob
        hits = sorted(glob.glob(pattern), reverse=True)
        if hits:
            return hits[0]
    return None


def run_phenix(cmd: str, phenix_env: str, cwd: Path, logs_dir: Path, timeout: int = 7200) -> dict:
    full_cmd = f'source "{phenix_env}" && cd "{cwd}" && {cmd}'
    stdout_path = logs_dir / "stdout.log"
    stderr_path = logs_dir / "stderr.log"
    t0 = time.time()
    with open(stdout_path, "w") as fout, open(stderr_path, "w") as ferr:
        proc = subprocess.run(
            ["bash", "-lc", full_cmd],
            stdout=fout, stderr=ferr, timeout=timeout
        )
    elapsed = time.time() - t0
    return {
        "command": full_cmd,
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 1),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


# ---------------------------------------------------------------------------
# PHIL builder
# ---------------------------------------------------------------------------

def build_final_phil(args, params_dir: Path, staged_inputs: dict) -> Path:
    parts = []

    # 1) preset
    preset_name = args.preset or (f"{'xray' if args.lane == 'xray' else 'em'}_default")
    preset_path = PRESETS_DIR / f"{preset_name}.phil"
    if preset_path.exists():
        parts.append(preset_path.read_text())
        shutil.copy2(preset_path, params_dir / "preset.phil")

    # 2) user overrides (structured)
    overrides = []
    if args.lane == "xray":
        if args.strategy:
            overrides.append(f"refinement.refine.strategy = {args.strategy}")
        if args.macro_cycles:
            overrides.append(f"main.number_of_macro_cycles = {args.macro_cycles}")
        if args.nproc:
            overrides.append(f"nproc = {args.nproc}")
        if args.ordered_solvent:
            overrides.append("main.ordered_solvent = True")
        if args.labels:
            overrides.append(f'xray_data.labels = "{args.labels}"')
        if args.rfree_label:
            overrides.append(f'xray_data.r_free_flags.label = "{args.rfree_label}"')
        if args.twin_law:
            overrides.append(f'xray_data.twin_law = "{args.twin_law}"')
        if args.output_prefix:
            overrides.append(f"output.prefix = {args.output_prefix}")
    else:  # em
        if args.resolution:
            overrides.append(f"resolution = {args.resolution}")
        if args.macro_cycles:
            overrides.append(f"macro_cycles = {args.macro_cycles}")
        if args.nproc:
            overrides.append(f"nproc = {args.nproc}")
        if args.run_steps:
            overrides.append(f"run = {args.run_steps}")
        if args.output_prefix:
            overrides.append(f"output.prefix = {args.output_prefix}")

    if overrides:
        user_phil = "\n".join(overrides) + "\n"
        (params_dir / "user.phil").write_text(user_phil)
        parts.append(user_phil)

    # 3) expert overrides (raw PHIL, logged prominently)
    if args.expert_phil:
        expert_path = Path(args.expert_phil)
        if expert_path.exists():
            expert_text = expert_path.read_text()
            (params_dir / "expert.phil").write_text(expert_text)
            parts.append(expert_text)

    final_text = "\n".join(parts)
    final_path = params_dir / "final.phil"
    final_path.write_text(final_text)
    return final_path


# ---------------------------------------------------------------------------
# Output collection
# ---------------------------------------------------------------------------

def collect_outputs(outputs_dir: Path, logs_dir: Path, lane: str) -> dict:
    result = {"files": [], "primary": {}, "metrics": {}}

    # list all output files
    for f in sorted(outputs_dir.iterdir()):
        if f.is_file():
            result["files"].append({"name": f.name, "size": f.stat().st_size})

    # find primary outputs
    pdbs = sorted(outputs_dir.glob("*.pdb"))
    if pdbs:
        result["primary"]["refined_model"] = pdbs[-1].name
    mtzs = sorted(outputs_dir.glob("*.mtz"))
    if mtzs:
        result["primary"]["refined_data"] = mtzs[-1].name
    logs = sorted(outputs_dir.glob("*.log"))
    if logs:
        result["primary"]["phenix_log"] = logs[-1].name

    # parse metrics from log
    log_text = ""
    for lp in [logs_dir / "stdout.log"] + list(outputs_dir.glob("*.log")):
        if lp.exists():
            log_text += lp.read_text(errors="replace")

    if lane == "xray":
        import re
        m = re.search(r"R-work\s*=\s*([0-9.]+)", log_text)
        if m: result["metrics"]["r_work"] = float(m.group(1))
        m = re.search(r"R-free\s*=\s*([0-9.]+)", log_text)
        if m: result["metrics"]["r_free"] = float(m.group(1))
    else:
        import re
        for pat, key in [
            (r"ramachandran.*?outliers?\s*[:=]\s*([0-9.]+)", "ramachandran_outliers"),
            (r"rotamer.*?outliers?\s*[:=]\s*([0-9.]+)", "rotamer_outliers"),
            (r"bond\s*(?:rmsd|rms)\s*[:=]\s*([0-9.]+)", "bond_rmsd"),
            (r"angle\s*(?:rmsd|rms)\s*[:=]\s*([0-9.]+)", "angle_rmsd"),
        ]:
            m = re.search(pat, log_text, re.IGNORECASE)
            if m:
                result["metrics"][key] = float(m.group(1))

    return result


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def write_provenance(job_dir: Path, args, phenix_env: str, staged: dict,
                     run_result: dict, outputs_summary: dict) -> Path:
    prov = {
        "job_id": job_dir.name,
        "lane": args.lane,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "phenix_env": phenix_env,
        "environment": {k: v for k, v in os.environ.items() if k.startswith("PHENIX")},
        "inputs": staged,
        "command": run_result["command"],
        "returncode": run_result["returncode"],
        "elapsed_seconds": run_result["elapsed_seconds"],
        "outputs_summary": outputs_summary,
    }
    prov_dir = job_dir / "provenance"
    prov_dir.mkdir(exist_ok=True)
    prov_path = prov_dir / "job.json"
    prov_path.write_text(json.dumps(prov, indent=2))

    # rerun script
    rerun = prov_dir / "rerun.sh"
    rerun.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{run_result['command']}\n")
    rerun.chmod(0o755)

    return prov_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Phenix refinement runner")
    parser.add_argument("--lane", required=True, choices=["xray", "em"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", help="MTZ file (X-ray)")
    parser.add_argument("--map", help="MRC/CCP4 map (cryo-EM)")
    parser.add_argument("--resolution", type=float, help="Resolution (required for EM maps)")
    parser.add_argument("--ligands", nargs="*", default=[], help="Ligand CIF files")
    parser.add_argument("--preset", help="PHIL preset name (e.g., xray_default, em_conservative)")
    parser.add_argument("--strategy", help="Refinement strategy (X-ray)")
    parser.add_argument("--macro-cycles", type=int)
    parser.add_argument("--nproc", type=int)
    parser.add_argument("--ordered-solvent", action="store_true")
    parser.add_argument("--labels", help="F,SIGF labels (X-ray)")
    parser.add_argument("--rfree-label", help="FreeR flag label (X-ray)")
    parser.add_argument("--twin-law", help="Twin law (X-ray, expert)")
    parser.add_argument("--run-steps", help="run= steps (EM, e.g., minimization_global+morphing)")
    parser.add_argument("--output-prefix", help="Output prefix")
    parser.add_argument("--expert-phil", help="Path to expert PHIL overrides file")
    parser.add_argument("--validate", action="store_true", help="Run validation after refinement")
    parser.add_argument("--timeout", type=int, default=7200, help="Timeout in seconds")
    args = parser.parse_args()

    # Validate lane-specific requirements
    if args.lane == "xray" and not args.data:
        print("ERROR: --data (MTZ) required for X-ray lane", file=sys.stderr)
        return 1
    if args.lane == "em" and not args.map:
        print("ERROR: --map (MRC/CCP4) required for EM lane", file=sys.stderr)
        return 1
    if args.lane == "em" and not args.resolution:
        print("ERROR: --resolution required for EM lane (unless refining vs MTZ map coeffs)", file=sys.stderr)
        return 1

    # Find Phenix
    phenix_env = find_phenix_env()
    if not phenix_env:
        print("ERROR: Cannot find phenix_env.sh. Set PHENIX_ENV_SH env var.", file=sys.stderr)
        return 1

    # Create job directory
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_id = f"{ts}-{args.lane}-{short_id()}"
    if not args.output_prefix:
        args.output_prefix = job_id
    job_dir = RUNS_DIR / job_id
    inputs_dir = job_dir / "inputs"
    params_dir = job_dir / "params"
    logs_dir = job_dir / "logs"
    outputs_dir = job_dir / "outputs"
    reports_dir = job_dir / "reports"
    for d in [inputs_dir, params_dir, logs_dir, outputs_dir, reports_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Stage inputs (copy — maps typically <500MB per user)
    staged = {}
    model_staged = stage_input(Path(args.model), inputs_dir)
    staged["model"] = {"original": args.model, "staged": str(model_staged),
                       "sha256": sha256_file(model_staged)}

    if args.data:
        data_staged = stage_input(Path(args.data), inputs_dir)
        staged["data"] = {"original": args.data, "staged": str(data_staged),
                          "sha256": sha256_file(data_staged)}
    if args.map:
        map_staged = stage_input(Path(args.map), inputs_dir)
        staged["map"] = {"original": args.map, "staged": str(map_staged),
                         "sha256": sha256_file(map_staged)}

    ligand_staged = []
    for lig in args.ligands:
        ls = stage_input(Path(lig), inputs_dir)
        ligand_staged.append(ls)
        staged.setdefault("ligands", []).append({
            "original": lig, "staged": str(ls), "sha256": sha256_file(ls)
        })

    # Build PHIL
    final_phil = build_final_phil(args, params_dir, staged)

    # Build command
    if args.lane == "xray":
        positional = [f'"{inputs_dir / Path(args.model).name}"',
                      f'"{inputs_dir / Path(args.data).name}"']
        for ls in ligand_staged:
            positional.append(f'"{ls}"')
        positional.append(f'"{final_phil}"')
        cmd = f"phenix.refine {' '.join(positional)}"
    else:
        positional = [f'"{inputs_dir / Path(args.model).name}"',
                      f'"{inputs_dir / Path(args.map).name}"']
        for ls in ligand_staged:
            positional.append(f'"{ls}"')
        positional.append(f'"{final_phil}"')
        cmd = f"phenix.real_space_refine {' '.join(positional)}"

    print(f"Job: {job_id}")
    print(f"Lane: {args.lane}")
    print(f"Command: {cmd}")
    print(f"Working dir: {outputs_dir}")

    # Run
    run_result = run_phenix(cmd, phenix_env, outputs_dir, logs_dir, args.timeout)
    print(f"Exit code: {run_result['returncode']}")
    print(f"Elapsed: {run_result['elapsed_seconds']}s")

    # Collect outputs
    outputs_summary = collect_outputs(outputs_dir, logs_dir, args.lane)
    (reports_dir / "summary.json").write_text(json.dumps(outputs_summary, indent=2))

    # Optional validation
    if args.validate and run_result["returncode"] == 0:
        refined_model = outputs_summary["primary"].get("refined_model")
        if refined_model:
            refined_path = outputs_dir / refined_model
            if args.lane == "xray":
                val_cmd = f'phenix.molprobity "{refined_path}"'
            else:
                val_cmd = f'phenix.validation_cryoem "{refined_path}" "{inputs_dir / Path(args.map).name}" resolution={args.resolution}'
            print(f"Running validation: {val_cmd}")
            run_phenix(val_cmd, phenix_env, outputs_dir, logs_dir, timeout=1800)

    # Provenance
    prov_path = write_provenance(job_dir, args, phenix_env, staged, run_result, outputs_summary)
    print(f"Provenance: {prov_path}")
    print(f"Summary: {reports_dir / 'summary.json'}")

    # Print key metrics
    if outputs_summary["metrics"]:
        print("\n--- Key Metrics ---")
        for k, v in outputs_summary["metrics"].items():
            print(f"  {k}: {v}")

    return run_result["returncode"]


if __name__ == "__main__":
    raise SystemExit(main())
