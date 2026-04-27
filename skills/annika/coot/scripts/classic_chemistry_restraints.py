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
    resolve_path,
    save_model,
)

SCRIPT_NAME = "classic_chemistry_restraints"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a narrow Phase B chemistry / restraints operation and emit a JSON summary."
    )
    add_common_io_args(parser, require_output_model=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("monomer-restraints", help="Inspect monomer restraints known to Coot for one comp-id")
    p.add_argument("--comp-id", required=True)

    p = sub.add_parser("write-restraints-cif", help="Write a CIF restraint dictionary for one comp-id")
    p.add_argument("--comp-id", required=True)
    p.add_argument("--output-cif", required=True)

    p = sub.add_parser("generate-local-self-restraints", help="Generate local self restraints for one chain")
    p.add_argument("--chain", required=True)
    p.add_argument("--local-dist-max", type=float, default=4.5)

    p = sub.add_parser("add-extra-bond", help="Add one explicit extra bond restraint")
    p.add_argument("--chain-1", required=True)
    p.add_argument("--resno-1", required=True, type=int)
    p.add_argument("--inscode-1", default="")
    p.add_argument("--atom-1", required=True)
    p.add_argument("--altconf-1", default="")
    p.add_argument("--chain-2", required=True)
    p.add_argument("--resno-2", required=True, type=int)
    p.add_argument("--inscode-2", default="")
    p.add_argument("--atom-2", required=True)
    p.add_argument("--altconf-2", default="")
    p.add_argument("--distance", required=True, type=float)
    p.add_argument("--esd", required=True, type=float)

    sub.add_parser("clear-extra-restraints", help="Delete all extra restraints for the model")

    return parser


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        load_maps_from_args(args)
        before = model_summary(imol)

        if args.command == "monomer-restraints":
            comp_id = args.comp_id.upper().strip()
            op = {
                "command": args.command,
                "comp_id": comp_id,
                "restraints": coot.monomer_restraints_py(comp_id),
            }

        elif args.command == "write-restraints-cif":
            comp_id = args.comp_id.upper().strip()
            output_cif = resolve_path(args.output_cif)
            coot.write_restraints_cif_dictionary(comp_id, output_cif)
            op = {
                "command": args.command,
                "comp_id": comp_id,
                "output_cif": output_cif,
            }

        elif args.command == "generate-local-self-restraints":
            coot.generate_local_self_restraints(imol, args.chain, float(args.local_dist_max))
            coot.set_show_extra_restraints(imol, 1)
            op = {
                "command": args.command,
                "chain": args.chain,
                "local_dist_max": float(args.local_dist_max),
            }

        elif args.command == "add-extra-bond":
            coot.add_extra_bond_restraint(
                imol,
                args.chain_1,
                int(args.resno_1),
                args.inscode_1,
                args.atom_1,
                args.altconf_1,
                args.chain_2,
                int(args.resno_2),
                args.inscode_2,
                args.atom_2,
                args.altconf_2,
                float(args.distance),
                float(args.esd),
            )
            coot.set_show_extra_restraints(imol, 1)
            op = {
                "command": args.command,
                "bond": {
                    "a": {
                        "chain": args.chain_1,
                        "resno": int(args.resno_1),
                        "inscode": args.inscode_1,
                        "atom": args.atom_1,
                        "altconf": args.altconf_1,
                    },
                    "b": {
                        "chain": args.chain_2,
                        "resno": int(args.resno_2),
                        "inscode": args.inscode_2,
                        "atom": args.atom_2,
                        "altconf": args.altconf_2,
                    },
                    "distance": float(args.distance),
                    "esd": float(args.esd),
                },
            }

        elif args.command == "clear-extra-restraints":
            coot.delete_all_extra_restraints(imol)
            op = {"command": args.command}

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
