#!/usr/bin/env python3
from __future__ import annotations

import argparse

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
    parse_range_spec,
    parse_residue_spec,
    resolve_path,
    save_model,
)

SCRIPT_NAME = "classic_edit_primitives"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Phase A local editing primitive on a model and emit a JSON summary.")
    add_common_io_args(parser, require_output_model=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("delete-residue", help="Delete one residue: CHAIN:RESNO[:INSCODE]")
    p.add_argument("--residue", required=True)

    p = sub.add_parser("delete-range", help="Delete a residue range: CHAIN:START-END")
    p.add_argument("--range", required=True, dest="range_spec")

    p = sub.add_parser("copy-range", help="Copy a residue range from source chain to target chain")
    p.add_argument("--range", required=True, dest="range_spec")
    p.add_argument("--to-chain", required=True)
    p.add_argument("--source-model", help="Optional second model to copy from; default is the primary model")

    p = sub.add_parser("change-chain", help="Change chain ID for a whole chain or range")
    p.add_argument("--from-chain", required=True)
    p.add_argument("--to-chain", required=True)
    p.add_argument("--range", dest="range_spec", help="Optional CHAIN:START-END restriction; chain must match --from-chain")

    p = sub.add_parser("renumber-range", help="Renumber a residue range by an integer offset")
    p.add_argument("--range", required=True, dest="range_spec")
    p.add_argument("--offset", required=True, type=int)

    return parser


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        load_maps_from_args(args)
        before = model_summary(imol)
        op_report: dict[str, object]

        if args.command == "delete-residue":
            spec = parse_residue_spec(args.residue)
            coot.delete_residue(imol, spec.chain, spec.resno, spec.inscode)
            op_report = {"command": args.command, "residue": spec.to_dict()}

        elif args.command == "delete-range":
            rng = parse_range_spec(args.range_spec)
            coot.delete_residue_range(imol, rng.chain, rng.start, rng.end)
            op_report = {"command": args.command, "range": rng.to_dict()}

        elif args.command == "copy-range":
            rng = parse_range_spec(args.range_spec)
            src_imol = load_model(args.source_model) if args.source_model else imol
            status = int(coot.copy_residue_range(imol, args.to_chain, src_imol, rng.chain, rng.start, rng.end))
            op_report = {
                "command": args.command,
                "range": rng.to_dict(),
                "source_imol": int(src_imol),
                "target_imol": int(imol),
                "to_chain": args.to_chain,
                "status": status,
            }
            if status < 0:
                raise CootSkillError("copy_residue_range reported failure")

        elif args.command == "change-chain":
            use_range = 1 if args.range_spec else 0
            start_res = 0
            end_res = 0
            range_payload = None
            if args.range_spec:
                rng = parse_range_spec(args.range_spec)
                if rng.chain != args.from_chain:
                    raise CootSkillError("Range chain must match --from-chain for change-chain")
                start_res, end_res = rng.start, rng.end
                range_payload = rng.to_dict()
            coot.change_chain_id(imol, args.from_chain, args.to_chain, use_range, start_res, end_res)
            op_report = {
                "command": args.command,
                "from_chain": args.from_chain,
                "to_chain": args.to_chain,
                "range": range_payload,
            }

        elif args.command == "renumber-range":
            rng = parse_range_spec(args.range_spec)
            status = int(coot.renumber_residue_range(imol, rng.chain, rng.start, rng.end, args.offset))
            op_report = {"command": args.command, "range": rng.to_dict(), "offset": int(args.offset), "status": status}
            if status < 0:
                raise CootSkillError("renumber_residue_range reported failure")

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
            "operation": op_report,
            "after": model_summary(imol),
            "output_model": saved,
        }
        emit_report(report, args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
