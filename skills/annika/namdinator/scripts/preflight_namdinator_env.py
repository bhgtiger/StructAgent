#!/usr/bin/env python3
"""
preflight_namdinator_env.py — READ-ONLY Namdinator dependency probe.

Purpose
    Inventory whether the tools Namdinator needs are present on THIS host and,
    where cheap and safe, their versions — so a user can answer "could this
    machine, in principle, run Namdinator?". It does NOT prove a working run;
    only a live fixture run does that.

What it does (and refuses to do)
    * Only inspects PATH (shutil.which) and runs a few *known-safe, fast*
      `--version`-style commands.
    * NO installs, NO downloads, NO network calls, NO Namdinator jobs, NO file
      writes except the optional --output report you ask for.
    * Deliberately does NOT execute `vmd` or `namd2`: invoking VMD can launch a
      GUI / block, and NAMD2 startup is not a safe no-op. For those, presence on
      PATH is reported; version is left to a human.

Usage
    python3 preflight_namdinator_env.py                      # markdown to stdout
    python3 preflight_namdinator_env.py --format json
    python3 preflight_namdinator_env.py --output report.md   # also write a file

Exit code is always 0 (this is a report, not a gate). Read the verdict, not $?.

Documented target stack (see references/02_installation_environment.md):
    VMD 1.93 (+MDFF/AutoPSF/ssrestraints/cispeptides/chirality/multiplot),
    NAMD2 2.12 CUDA, CUDA >= 6.0, Phenix 1.13rc1, Rosetta 2016.32.58837 (opt),
    gnuplot, bc, lscpu (Linux). This probe checks presence, not exact versions.
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys

# (name, kind, requirement, run_version, version_argv)
# kind: 'bin' generic | 'phenix' | 'os'
# requirement: 'required' | 'recommended' | 'linux_default'
# run_version=False means: report presence only, do NOT execute it.
#
# HARD requirements = the generic script exits if these are missing. Verified
# against Namdinator_Generic.sh@5814c947: VMD (lines 63-72), NAMD2 (75-94), and
# Phenix (`which phenix` -> exit 1 at lines 479-489) ALL hard-exit. Phenix is
# required even without -x (used for map info, ADP/B-factor, CC, validation).
# The script also calls phenix.real_space_refine for ADP processing before the
# optional -x coordinate-refinement branch, so it is not merely "required_for_-x".
# gnuplot (clashscore plot) and bc (Rosetta-scoring branch) do not gate startup;
# lscpu only supplies the -n default on Linux and is substitutable with -n.
CHECKS = [
    ("vmd",                      "bin",    "required",        False, None),
    ("namd2",                    "bin",    "required",        False, None),
    ("phenix",                   "phenix", "required",        False, None),
    ("phenix.show_map_info",     "phenix", "required",        False, None),
    ("phenix.reduce",            "phenix", "required",        False, None),
    ("phenix.pdbtools",          "phenix", "required",        False, None),
    ("phenix.real_space_refine", "phenix", "required",        False, None),
    ("phenix.map_model_cc",      "phenix", "required",        False, None),
    ("phenix.ramalyze",          "phenix", "required",        False, None),
    ("phenix.rotalyze",          "phenix", "required",        False, None),
    ("phenix.cbetadev",          "phenix", "required",        False, None),
    ("phenix.clashscore",        "phenix", "required",        False, None),
    ("phenix.version",           "phenix", "recommended",     True,  ["phenix.version"]),
    ("gnuplot",                  "bin",    "recommended",     True,  ["gnuplot", "--version"]),
    ("bc",                       "bin",    "recommended",     True,  ["bc", "--version"]),
    ("lscpu",                    "os",     "linux_default",   False, None),
]

ROSETTA_HINTS = ["score_jd2", "per_residue_energies", "ROSETTA_BIN"]


def safe_version(argv):
    """Run a known-safe version command with a short timeout. Read-only."""
    try:
        out = subprocess.run(
            argv, capture_output=True, text=True, timeout=8,
        )
        text = (out.stdout or out.stderr or "").strip().splitlines()
        return text[0].strip() if text else "(no version output)"
    except FileNotFoundError:
        return None
    except Exception as exc:  # timeout, permissions, etc. — never fatal
        return f"(version probe failed: {exc.__class__.__name__})"


def probe():
    osname = platform.system()
    report = {
        "host": platform.node(),
        "os": osname,
        "os_release": platform.release(),
        "is_linux": osname == "Linux",
        "tools": [],
        "rosetta": {},
        "warnings": [],
        "verdict": "",
    }

    if osname != "Linux":
        report["warnings"].append(
            f"OS is {osname}, not Linux. Namdinator's `-n` default uses `lscpu` "
            "(Linux-only); the unmodified script is not expected to run here. "
            "Plan on a Linux host or patch core handling and pass -n explicitly."
        )

    for name, kind, req, run_ver, argv in CHECKS:
        path = shutil.which(name)
        entry = {"name": name, "kind": kind, "requirement": req,
                 "present": path is not None, "path": path, "version": None}
        if path and run_ver and argv:
            entry["version"] = safe_version(argv)
        report["tools"].append(entry)

    # Rosetta is optional and named many ways; just hint at presence.
    rosetta_found = any(shutil.which(h) for h in ("score_jd2", "per_residue_energies"))
    import os
    report["rosetta"] = {
        "optional": True,
        "ROSETTA_BIN_set": bool(os.environ.get("ROSETTA_BIN")),
        "score_binaries_on_path": rosetta_found,
        "note": "If ROSETTA_BIN is unset, Rosetta validation columns become n/a (this is fine).",
    }

    # Environment variables Namdinator may use.
    report["env_vars"] = {
        v: os.environ.get(v) for v in
        ("VMDMASTER", "NAMDMASTER", "PHENIX", "PHENIXMASTER",
         "PHENIXMASTERDIR", "ROSETTA_BIN")
    }

    # Verdict: the generic script HARD-exits if VMD, NAMD2, or the base Phenix
    # command is missing, and later depends on the listed phenix.* tools even
    # without -x. gnuplot/bc/lscpu do not gate startup.
    have = {t["name"]: t["present"] for t in report["tools"]}
    hard = [t["name"] for t in report["tools"] if t["requirement"] == "required"]
    missing_hard = [n for n in hard if not have.get(n)]
    missing_recommended = [t["name"] for t in report["tools"]
                           if t["requirement"] == "recommended" and not t["present"]]
    lscpu_missing = not have.get("lscpu")

    if missing_hard:
        report["verdict"] = (
            "NOT runnable: the generic script hard-exits if any of VMD, NAMD2, or "
            "Phenix/required Phenix tools are missing. Missing here: "
            f"{', '.join(missing_hard)}. Phenix is required even without -x "
            "(used for map info, ADP/B-factor processing, model-map CC, and "
            "validation)."
        )
    else:
        notes = []
        if missing_recommended:
            notes.append(
                f"optional helpers missing ({', '.join(missing_recommended)}): "
                "gnuplot only affects the clashscore-vs-frame plot; bc only the "
                "Rosetta-scoring branch — neither blocks a run"
            )
        if lscpu_missing:
            notes.append("lscpu absent (normal off Linux): pass `-n <cores>` explicitly")
        phenix_env = any(report["env_vars"].get(v) for v in ("PHENIX", "PHENIXMASTER", "PHENIXMASTERDIR"))
        if not phenix_env:
            notes.append(
                "PHENIX/PHENIXMASTER/PHENIXMASTERDIR not set; the script's -x "
                "branch additionally checks PHENIXMASTERDIR even when Phenix "
                "commands are on PATH"
            )
        report["verdict"] = (
            "Hard-required stack present (VMD, NAMD2, Phenix commands). This does NOT prove a "
            "working run — capture `./Namdinator_Generic.sh -h` and complete a "
            "fixture run to validate. Rosetta is optional."
            + (" Notes: " + "; ".join(notes) + "." if notes else "")
        )
    return report


def to_markdown(r):
    lines = []
    lines.append("# Namdinator environment preflight (read-only)\n")
    lines.append(f"- host: `{r['host']}`")
    lines.append(f"- os: `{r['os']} {r['os_release']}` (linux: {r['is_linux']})\n")
    lines.append(f"**Verdict:** {r['verdict']}\n")
    if r["warnings"]:
        lines.append("**Warnings:**")
        for w in r["warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    lines.append("| Tool | Requirement | Present | Path | Version |")
    lines.append("|---|---|:--:|---|---|")
    for t in r["tools"]:
        lines.append(
            f"| `{t['name']}` | {t['requirement']} | "
            f"{'yes' if t['present'] else 'NO'} | "
            f"{t['path'] or '—'} | {t['version'] or '—'} |"
        )
    lines.append("")
    rb = r["rosetta"]
    lines.append(
        f"- Rosetta (optional): ROSETTA_BIN set = {rb['ROSETTA_BIN_set']}, "
        f"score binaries on PATH = {rb['score_binaries_on_path']}. {rb['note']}"
    )
    set_vars = {k: v for k, v in r["env_vars"].items() if v}
    lines.append(f"- Env vars set: {set_vars if set_vars else 'none of the Namdinator-related vars are set'}")
    lines.append("")
    lines.append("> Read-only probe. No installs/downloads/network/jobs were performed. "
                 "Presence ≠ a validated run. See references/02_installation_environment.md.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Read-only Namdinator dependency probe.")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--output", help="also write the report to this path")
    args = ap.parse_args()

    r = probe()
    text = json.dumps(r, indent=2) if args.format == "json" else to_markdown(r)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
