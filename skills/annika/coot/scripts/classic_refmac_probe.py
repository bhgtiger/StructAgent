#!/usr/bin/env python3
"""Probe Refmac availability from inside Coot.

Purpose
-------
- verify that the local Coot build exposes the Refmac integration functions
- verify that the external `refmac5` executable is actually discoverable from
  the Coot runtime environment
- optionally load a model and report the per-molecule `refmac_name()` stub

Usage
-----
Preferred classic lane:
  coot --no-graphics --no-state-script --script classic_refmac_probe.py

If passing args through coot is awkward, set COOT_SKILL_ARGS, e.g.:
  COOT_SKILL_ARGS='--model input.pdb --report-json probe.json' \
    coot --no-graphics --no-state-script --script classic_refmac_probe.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import coot
import coot_utils

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from classic_common import (
    CootSkillError,
    emit_report,
    fail,
    load_model,
    parse_args,
    resolve_path,
)

SCRIPT_NAME = "classic_refmac_probe.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe Refmac availability from inside Coot")
    parser.add_argument("--model", help="Optional input coordinate model path for refmac_name(imol) probe")
    parser.add_argument("--report-json", help="Optional JSON report path")
    return parser


def probe_function(name: str) -> dict[str, Any]:
    obj = getattr(coot, name, None)
    return {
        "present": obj is not None,
        "callable": callable(obj),
        "doc": (getattr(obj, "__doc__", "") or "").strip() if obj is not None else None,
    }


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)

    try:
        report: dict[str, Any] = {
            "ok": True,
            "script": SCRIPT_NAME,
            "coot_refmac_functions": {
                "refmac_name": probe_function("refmac_name"),
                "execute_refmac_real": probe_function("execute_refmac_real"),
                "add_refmac_extra_restraints": probe_function("add_refmac_extra_restraints"),
                "refmac_parameters_py": probe_function("refmac_parameters_py"),
            },
            "executable_resolution": {
                "command_in_path_qm_refmac5": coot_utils.command_in_path_qm("refmac5"),
                "find_exe_refmac5": coot_utils.find_exe("refmac5", "CBIN", "CCP4_BIN", "PATH"),
            },
            "model_probe": None,
        }

        if args.model:
            model_path = resolve_path(args.model)
            assert model_path is not None
            if not Path(model_path).exists():
                raise CootSkillError(f"Model file not found: {model_path}")
            imol = load_model(model_path)
            refmac_stub = None
            refmac_stub_error = None
            try:
                refmac_stub = coot.refmac_name(imol)
            except Exception as exc:  # pragma: no cover - runtime-specific
                refmac_stub_error = {"type": type(exc).__name__, "message": str(exc)}
            report["model_probe"] = {
                "model": model_path,
                "imol": int(imol),
                "refmac_name": refmac_stub,
                "refmac_name_error": refmac_stub_error,
            }

        emit_report(report, report_json=args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, report_json=args.report_json)


if __name__ == "__main__":
    main()
