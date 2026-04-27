#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

import coot
from classic_common import (
    CootSkillError,
    add_common_io_args,
    emit_report,
    fail,
    load_maps_from_args,
    load_model,
    model_summary,
    parse_args,
    parse_residue_spec,
    resolve_path,
    save_model,
)

SCRIPT_NAME = "classic_sidechain_fix"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a narrow Phase B rotamer / pep-flip / sidechain-fix operation and emit a JSON summary."
    )
    add_common_io_args(parser, require_output_model=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("score-rotamer", help="Score available rotamers for one residue against the active map")
    p.add_argument("--residue", required=True)
    p.add_argument("--altconf", default="")
    p.add_argument("--clash-flag", type=int, default=1)
    p.add_argument("--lowest-probability", type=float, default=0.0)

    p = sub.add_parser("auto-fit-rotamer", help="Map-backed rotamer autofit for one residue")
    p.add_argument("--residue", required=True)
    p.add_argument("--altconf", default="")
    p.add_argument("--clash-flag", type=int, default=1)
    p.add_argument("--lowest-probability", type=float, default=0.0)

    p = sub.add_parser("set-rotamer-number", help="Set one explicit rotamer by index")
    p.add_argument("--residue", required=True)
    p.add_argument("--altconf", default="")
    p.add_argument("--rotamer-number", required=True, type=int)

    p = sub.add_parser("set-rotamer-name", help="Set one explicit rotamer by name")
    p.add_argument("--residue", required=True)
    p.add_argument("--altconf", default="")
    p.add_argument("--rotamer-name", required=True)

    p = sub.add_parser("backrub", help="Run backrub rotamer search with autoaccept")
    p.add_argument("--residue", required=True)
    p.add_argument("--altconf", default="")

    p = sub.add_parser("pepflip", help="Apply peptide flip at one residue")
    p.add_argument("--residue", required=True)
    p.add_argument("--altconf", default="")

    p = sub.add_parser("crankshaft", help="Run crankshaft peptide optimization for one residue")
    p.add_argument("--residue", required=True)

    return parser


def _residue_name(imol: int, chain: str, resno: int, inscode: str) -> str | None:
    try:
        name = coot.residue_name(imol, chain, resno, inscode)
    except Exception:
        return None
    if name in (False, None, ""):
        return None
    return str(name)


def _require_active_map(maps: dict[str, Any]) -> int:
    imol_map = maps.get("active_refinement_map")
    if imol_map is None:
        raise CootSkillError("This operation needs an active refinement map")
    return int(imol_map)


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        maps = load_maps_from_args(args)
        before = model_summary(imol)
        spec = parse_residue_spec(args.residue)
        before_name = _residue_name(imol, spec.chain, spec.resno, spec.inscode)
        common = {
            "residue": spec.to_dict(),
            "before_resname": before_name,
        }

        if args.command == "score-rotamer":
            imol_map = _require_active_map(maps)
            n_rot = int(coot.n_rotamers(imol, spec.chain, spec.resno, spec.inscode))
            scores = coot.score_rotamers_py(
                imol,
                spec.chain,
                spec.resno,
                spec.inscode,
                args.altconf,
                imol_map,
                int(args.clash_flag),
                float(args.lowest_probability),
            )
            op = {
                "command": args.command,
                **common,
                "altconf": args.altconf,
                "active_map": imol_map,
                "n_rotamers": n_rot,
                "scores": scores,
            }

        elif args.command == "auto-fit-rotamer":
            imol_map = _require_active_map(maps)
            score = float(
                coot.auto_fit_best_rotamer(
                    imol,
                    spec.chain,
                    spec.resno,
                    spec.inscode,
                    args.altconf,
                    imol_map,
                    int(args.clash_flag),
                    float(args.lowest_probability),
                )
            )
            op = {
                "command": args.command,
                **common,
                "altconf": args.altconf,
                "active_map": imol_map,
                "clash_flag": int(args.clash_flag),
                "lowest_probability": float(args.lowest_probability),
                "result": score,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        elif args.command == "set-rotamer-number":
            status = int(
                coot.set_residue_to_rotamer_number(
                    imol, spec.chain, spec.resno, spec.inscode, args.altconf, int(args.rotamer_number)
                )
            )
            if status < 0:
                raise CootSkillError("set_residue_to_rotamer_number reported failure")
            op = {
                "command": args.command,
                **common,
                "altconf": args.altconf,
                "rotamer_number": int(args.rotamer_number),
                "status": status,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        elif args.command == "set-rotamer-name":
            status = int(
                coot.set_residue_to_rotamer_name(
                    imol, spec.chain, spec.resno, spec.inscode, args.altconf, args.rotamer_name
                )
            )
            if status < 0:
                raise CootSkillError("set_residue_to_rotamer_name reported failure")
            op = {
                "command": args.command,
                **common,
                "altconf": args.altconf,
                "rotamer_name": args.rotamer_name,
                "status": status,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        elif args.command == "backrub":
            imol_map = _require_active_map(maps)
            status = int(coot.backrub_rotamer(imol, spec.chain, spec.resno, spec.inscode, args.altconf))
            if status == 0:
                raise CootSkillError("backrub_rotamer reported failure even with an active refinement map")
            op = {
                 "active_map": imol_map,
                "command": args.command,
                **common,
                "altconf": args.altconf,
                "status": status,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        elif args.command == "pepflip":
            result = coot.pepflip(imol, spec.chain, spec.resno, spec.inscode, args.altconf)
            op = {
                "command": args.command,
                **common,
                "altconf": args.altconf,
                "result": result,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        elif args.command == "crankshaft":
            result = coot.crankshaft_peptide_rotation_optimization_py(imol, spec.to_py())
            op = {
                "command": args.command,
                **common,
                "result": result,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        else:
            raise CootSkillError(f"Unhandled command: {args.command}")

        saved = save_model(imol, args.output_model)
        report = {
            "ok": True,
            "script": SCRIPT_NAME,
            "inputs": {
                "model": resolve_path(args.model),
                "output_model": resolve_path(args.output_model),
            },
            "before": before,
            "operation": op,
            "after": model_summary(imol),
            "output_model": saved,
        }
        emit_report(report, args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
