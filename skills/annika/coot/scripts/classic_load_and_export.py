#!/usr/bin/env python3
from __future__ import annotations

import argparse

from classic_common import add_common_io_args, emit_report, fail, load_maps_from_args, load_model, map_stats, model_summary, parse_args, resolve_path, save_model

SCRIPT_NAME = "classic_load_and_export"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load a model plus optional maps/MTZ, set the active refinement map, and write a clean output model/report.")
    add_common_io_args(parser, require_output_model=False)
    return parser


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        maps = load_maps_from_args(args)
        saved = save_model(imol, args.output_model)
        report = {
            "ok": True,
            "script": SCRIPT_NAME,
            "inputs": {
                "model": resolve_path(args.model),
                "map": resolve_path(args.map),
                "diff_map": resolve_path(args.diff_map),
                "mtz": resolve_path(args.mtz),
                "refinement_map_choice": args.refinement_map,
            },
            "model": model_summary(imol),
            "maps": {
                "loaded": maps["loaded"],
                "active_refinement_map": maps["active_refinement_map"],
                "primary_stats": map_stats(maps["primary"]),
                "diff_stats": map_stats(maps["diff"]),
            },
            "output_model": saved,
        }
        emit_report(report, args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
