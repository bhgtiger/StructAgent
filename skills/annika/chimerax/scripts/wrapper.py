"""
ChimeraX job wrapper — runs inside ChimeraX via:
  ChimeraX --nogui --script wrapper.py job.json

Reads a job spec (JSON), executes commands sequentially via
chimerax.core.commands.run(), writes structured JSON results,
and prints a sentinel line for the calling agent to detect completion.

DO NOT RENAME this file. The SKILL.md and agent both expect "wrapper.py".
"""

import sys
import json
import os
import traceback

SENTINEL = "@@CHIMERAX_DONE@@"


# ---------------------------------------------------------------------------
# Return-value extractors for commands that produce useful structured output.
# Each takes the return value of run(session, cmd) and returns a JSON-safe dict.
# ---------------------------------------------------------------------------
def _extract_align(r):
    # align returns (matched_atoms, matched_to_atoms, rmsd, paired_rmsd, transform)
    if r is None:
        return None
    return {
        "matched_atoms": len(r[0]) if r[0] is not None else 0,
        "rmsd_angstrom": float(r[2]),
        "paired_rmsd_angstrom": float(r[3]),
    }


def _extract_fitmap(r):
    # fitmap returns a list of FitResult objects (or similar)
    if r is None:
        return None
    if isinstance(r, (list, tuple)) and len(r) > 0:
        # Try to get correlation from first fit result
        first = r[0]
        info = {}
        for attr in ("correlation", "average_map_value", "overlap", "steps"):
            if hasattr(first, attr):
                val = getattr(first, attr)
                if val is not None:
                    info[attr] = float(val) if not isinstance(val, int) else val
        if info:
            return info
    return {"raw": str(r)[:2000]}


def _extract_matchmaker(r):
    # matchmaker returns a list; each element contains alignment info
    if r is None:
        return None
    if isinstance(r, (list, tuple)):
        entries = []
        for item in r:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                entries.append({
                    "rmsd_angstrom": float(item[1]) if item[1] is not None else None,
                })
        if entries:
            return {"alignments": entries}
    return {"raw": str(r)[:2000]}


def _extract_measure(r):
    if r is None:
        return None
    if isinstance(r, (int, float)):
        return {"value": float(r)}
    return {"raw": str(r)[:2000]}


EXTRACTORS = {
    "align": _extract_align,
    "fitmap": _extract_fitmap,
    "matchmaker": _extract_matchmaker,
    "measure": _extract_measure,
}


def serialize_return(cmd_str, ret):
    """Best-effort structured extraction of command return values."""
    if ret is None:
        return None
    cmd_name = cmd_str.strip().split()[0].lower()
    for key, extractor in EXTRACTORS.items():
        if cmd_name.startswith(key):
            try:
                return extractor(ret)
            except Exception:
                break
    # Fallback
    return {"raw": str(ret)[:2000]}


def run_job(session, job_path):
    from chimerax.core.commands import run

    with open(job_path) as f:
        job = json.load(f)

    result_path = job.get("resultFile", job_path.replace(".json", "_result.json"))
    commands = job.get("commands", [])
    results = []
    aborted = False

    for i, spec in enumerate(commands):
        if isinstance(spec, str):
            spec = {"cmd": spec}
        cmd_str = spec["cmd"]
        capture = spec.get("capture", False)
        abort_on_fail = spec.get("abort", True)

        entry = {"i": i, "cmd": cmd_str}
        try:
            ret = run(session, cmd_str)
            entry["ok"] = True
            if capture and ret is not None:
                entry["return"] = serialize_return(cmd_str, ret)
        except Exception as e:
            entry["ok"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
            entry["traceback"] = traceback.format_exc()
            if abort_on_fail:
                aborted = True
                results.append(entry)
                break

        results.append(entry)

    output = {
        "ok": not aborted and all(r["ok"] for r in results),
        "n": len(results),
        "results": results,
    }

    # Atomic write
    tmp = result_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(output, f, indent=2, default=str)
    os.replace(tmp, result_path)

    # Sentinel on stdout — the exec caller greps for this.
    print(f"{SENTINEL}{result_path}")
    return output


# ---------------------------------------------------------------------------
# Entry point — session is injected by ChimeraX --script
# ---------------------------------------------------------------------------
try:
    idx = None
    for j, a in enumerate(sys.argv):
        if a.endswith("wrapper.py"):
            idx = j
            break
    if idx is None or idx + 1 >= len(sys.argv):
        print(f"{SENTINEL}ERROR:no_job_file", file=sys.stderr)
        raise SystemExit(1)
    job_path = sys.argv[idx + 1]
except Exception as e:
    print(f"{SENTINEL}ERROR:{e}", file=sys.stderr)
    raise SystemExit(1)

run_job(session, job_path)  # noqa: F821 — `session` injected by ChimeraX
raise SystemExit(0)
