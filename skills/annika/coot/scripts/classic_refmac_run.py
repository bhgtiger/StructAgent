#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import coot_utils

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from classic_common import CootSkillError, emit_report, fail, parse_args, resolve_path

SCRIPT_NAME = "classic_refmac_run.py"

try:  # optional but very useful for mmCIF header repair
    import gemmi  # type: ignore
except Exception:  # pragma: no cover - runtime-dependent
    gemmi = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a conservative Refmac job from within Coot.")
    parser.add_argument("--model", required=True, help="Input coordinate model (.pdb/.cif/.mmcif)")
    parser.add_argument("--output-model", required=True, help="Output coordinate model written by Refmac")
    parser.add_argument("--report-json", help="Optional JSON report path")
    parser.add_argument("--work-dir", help="Optional work directory for logs/intermediate files")
    parser.add_argument("--log", help="Optional explicit Refmac log path")
    parser.add_argument("--libin", action="append", default=[], help="Optional ligand/dictionary CIF passed as LIBIN. Repeatable.")
    parser.add_argument("--keyword", action="append", default=[], help="Extra Refmac keyword line. Repeatable.")
    parser.add_argument("--ncycle", type=int, default=0, help="Refmac NCYCLE value. Default: 0 for safe smoke tests.")
    parser.add_argument("--make-hout", choices=["yes", "no"], default="yes", help="Whether to ask Refmac to write hydrogens (MAKE HOUT).")
    parser.add_argument("--ensure-cell-from", help="Optional reference model to copy cell/spacegroup from when the input header is unusable.")
    parser.add_argument("--force-spacegroup", help="Optional space group override applied only during header repair.")
    parser.add_argument("--keep-prepared-input", action="store_true", help="Keep the header-repaired temporary input model when one is created.")
    return parser


def _is_bad_cell(structure: Any) -> bool:
    try:
        cell = structure.cell
        return (cell.a <= 1.01 or cell.b <= 1.01 or cell.c <= 1.01)
    except Exception:
        return True


def maybe_prepare_input(model_path: str, ensure_cell_from: str | None, force_spacegroup: str | None, work_dir: Path) -> tuple[str, dict[str, Any]]:
    info: dict[str, Any] = {
        "original_model": model_path,
        "prepared_model": model_path,
        "header_repaired": False,
        "repair_reason": None,
        "gemmi_available": gemmi is not None,
    }
    if not ensure_cell_from:
        return model_path, info
    if gemmi is None:
        raise CootSkillError("--ensure-cell-from requires gemmi, but gemmi is not available in this runtime")

    src = gemmi.read_structure(model_path)
    if not _is_bad_cell(src) and not force_spacegroup:
        return model_path, info

    ref = gemmi.read_structure(ensure_cell_from)
    src.cell = ref.cell
    src.spacegroup_hm = force_spacegroup or ref.spacegroup_hm or "P 1"
    prepared = work_dir / (Path(model_path).stem + "_prepared_for_refmac.cif")
    src.make_mmcif_document().write_file(str(prepared))
    info.update({
        "prepared_model": str(prepared),
        "header_repaired": True,
        "repair_reason": "missing_or_placeholder_cell_header",
        "copied_cell_from": ensure_cell_from,
        "spacegroup": src.spacegroup_hm,
        "cell": {
            "a": src.cell.a,
            "b": src.cell.b,
            "c": src.cell.c,
            "alpha": src.cell.alpha,
            "beta": src.cell.beta,
            "gamma": src.cell.gamma,
        },
    })
    return str(prepared), info


def _default_log_path(work_dir: Path, output_model: str) -> Path:
    return work_dir / (Path(output_model).stem + ".refmac.log")


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        model = resolve_path(args.model)
        output_model = resolve_path(args.output_model)
        assert model is not None and output_model is not None
        if not Path(model).exists():
            raise CootSkillError(f"Model file not found: {model}")
        work_dir = Path(resolve_path(args.work_dir) if args.work_dir else str(Path(output_model).parent)).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        log_path = Path(resolve_path(args.log) if args.log else str(_default_log_path(work_dir, output_model))).resolve()
        libins = [resolve_path(x) for x in args.libin]
        for lib in libins:
            if lib and not Path(lib).exists():
                raise CootSkillError(f"LIBIN file not found: {lib}")

        prepared_input, prep_info = maybe_prepare_input(
            model_path=model,
            ensure_cell_from=resolve_path(args.ensure_cell_from),
            force_spacegroup=args.force_spacegroup,
            work_dir=work_dir,
        )

        cmd_args = ["XYZIN", prepared_input, "XYZOUT", output_model]
        for lib in libins:
            if lib:
                cmd_args.extend(["LIBIN", lib])

        data_lines = [f"MAKE HOUT {args.make_hout.upper()}", f"NCYCLE {int(args.ncycle)}"]
        data_lines.extend(args.keyword)
        data_lines.append("END")

        status = coot_utils.popen_command("refmac5", cmd_args, data_lines, str(log_path), False)

        output_exists = Path(output_model).exists()
        output_size = Path(output_model).stat().st_size if output_exists else 0
        log_exists = log_path.exists()
        log_tail = []
        if log_exists:
            try:
                log_tail = log_path.read_text(errors="ignore").splitlines()[-40:]
            except Exception:
                log_tail = []

        report = {
            "ok": status == 0 and output_exists and output_size > 0,
            "script": SCRIPT_NAME,
            "inputs": {
                "model": model,
                "output_model": output_model,
                "libin": libins,
                "ncycle": int(args.ncycle),
                "make_hout": args.make_hout,
                "keyword": list(args.keyword),
                "ensure_cell_from": resolve_path(args.ensure_cell_from),
                "force_spacegroup": args.force_spacegroup,
            },
            "prepared_input": prep_info,
            "refmac": {
                "status": status,
                "log": str(log_path),
                "log_exists": log_exists,
                "output_model_exists": output_exists,
                "output_model_size": output_size,
                "log_tail": log_tail,
            },
        }
        emit_report(report, args.report_json)

        if prep_info.get("header_repaired") and not args.keep_prepared_input:
            try:
                Path(str(prep_info["prepared_model"])).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
