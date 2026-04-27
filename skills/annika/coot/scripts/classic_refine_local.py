#!/usr/bin/env python3
from __future__ import annotations

import argparse

import coot
from classic_common import (
    CootSkillError,
    ResidueRange,
    add_common_io_args,
    emit_report,
    fail,
    load_maps_from_args,
    load_model,
    map_stats,
    model_summary,
    parse_args,
    parse_range_spec,
    residue_specs_for_range,
    resolve_path,
    save_model,
)

SCRIPT_NAME = "classic_refine_local"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local residue-range refinement or rigid-body fitting against the active refinement map.")
    add_common_io_args(parser, require_output_model=True)
    parser.add_argument("--range", required=True, dest="range_spec", help="Residue range in CHAIN:START-END form")
    parser.add_argument("--altconf", default="", help="Optional altconf for refine-zone-like calls")
    parser.add_argument(
        "--mode",
        choices=["refine", "rigid-body"],
        default="refine",
        help="refine = refine_residues_py over the selected range; rigid-body = rigid_body_refine_by_residue_ranges_py",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        maps = load_maps_from_args(args)
        if maps["active_refinement_map"] is None:
            raise CootSkillError("No active refinement map is available. Load a map/MTZ or set --refinement-map appropriately.")
        before = model_summary(imol)
        rng: ResidueRange = parse_range_spec(args.range_spec)
        residue_specs = residue_specs_for_range(imol, rng)
        if not residue_specs:
            raise CootSkillError(f"No residues found for selected range {rng.label()}")

        old_immediate = None
        accept_result = {
            "attempted": False,
            "method": None,
            "reason": None,
        }
        if hasattr(coot, "refinement_immediate_replacement_state") and hasattr(coot, "set_refinement_immediate_replacement"):
            old_immediate = int(coot.refinement_immediate_replacement_state())
            coot.set_refinement_immediate_replacement(1)

        try:
            if args.mode == "refine":
                result = coot.refine_residues_py(imol, residue_specs)
            elif args.mode == "rigid-body":
                result = coot.rigid_body_refine_by_residue_ranges_py(imol, [[rng.chain, rng.start, rng.end]])
            else:
                raise CootSkillError(f"Unhandled refinement mode: {args.mode}")

            if hasattr(coot, "accept_moving_atoms_py"):
                accept_result = {
                    "attempted": True,
                    "method": "accept_moving_atoms_py",
                    "result": coot.accept_moving_atoms_py(),
                }
            else:
                accept_result = {
                    "attempted": False,
                    "method": None,
                    "reason": "accept_moving_atoms_py not available in this runtime",
                }
        finally:
            if old_immediate is not None:
                coot.set_refinement_immediate_replacement(old_immediate)

        saved = save_model(imol, args.output_model)
        report = {
            "ok": True,
            "script": SCRIPT_NAME,
            "inputs": {
                "model": resolve_path(args.model),
                "output_model": resolve_path(args.output_model),
                "range": rng.to_dict(),
                "mode": args.mode,
                "altconf": args.altconf,
            },
            "before": before,
            "map": {
                "active_refinement_map": maps["active_refinement_map"],
                "stats": map_stats(maps["active_refinement_map"]),
            },
            "selection": {
                "n_residues": len(residue_specs),
                "residues": residue_specs,
            },
            "result": result,
            "accept_result": accept_result,
            "after": model_summary(imol),
            "output_model": saved,
        }
        emit_report(report, args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
