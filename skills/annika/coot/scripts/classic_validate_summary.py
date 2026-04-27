#!/usr/bin/env python3
from __future__ import annotations

import argparse
from math import isnan

import coot
from classic_common import (
    CootSkillError,
    add_common_io_args,
    chain_ids,
    emit_report,
    fail,
    load_maps_from_args,
    load_model,
    map_stats,
    model_summary,
    parse_args,
    parse_range_spec,
    residues_for_range,
    residues_in_chain,
    resolve_path,
)

SCRIPT_NAME = "classic_validate_summary"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a compact validation summary for a model, optionally focused on a selected range and/or map-backed density scores.")
    add_common_io_args(parser, require_output_model=False)
    parser.add_argument("--range", dest="range_spec", help="Optional focus range in CHAIN:START-END form")
    parser.add_argument("--chain", help="Optional focus chain if --range is not given")
    parser.add_argument("--worst-n", type=int, default=10, help="How many worst residues to keep in summary lists")
    parser.add_argument("--density-threshold", type=float, default=0.5, help="Flag residues with density score below this threshold")
    parser.add_argument("--probe-dots", help="Optional precomputed Probe dots file for clash scoring")
    return parser


def _normalize_rama_payload(payload):
    if payload in (False, None):
        return None
    if not isinstance(payload, (list, tuple)) or len(payload) < 6:
        return {"raw": payload}
    per_residue = []
    for item in payload[5]:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            continue
        residue_spec = item[1]
        if not isinstance(residue_spec, (list, tuple)) or len(residue_spec) < 3:
            continue
        per_residue.append({
            "chain": str(residue_spec[0]),
            "resno": int(residue_spec[1]),
            "inscode": str(residue_spec[2] or ""),
            "phi": float(item[0][0]) if isinstance(item[0], (list, tuple)) and len(item[0]) >= 2 else None,
            "psi": float(item[0][1]) if isinstance(item[0], (list, tuple)) and len(item[0]) >= 2 else None,
            "score": float(item[2]),
            "neighbors": list(item[3]) if isinstance(item[3], (list, tuple)) else None,
        })
    return {
        "overall_score": float(payload[0]),
        "n_residues": int(payload[1]),
        "non_secondary_score": float(payload[2]),
        "n_non_secondary_residues": int(payload[3]),
        "n_zero_score_residues": int(payload[4]),
        "per_residue": per_residue,
    }


def _selected_residues(imol: int, chain: str | None, range_spec: str | None):
    if range_spec:
        rng = parse_range_spec(range_spec)
        return residues_for_range(imol, rng)
    if chain:
        return residues_in_chain(imol, chain)
    out = []
    for ch in chain_ids(imol):
        out.extend(residues_in_chain(imol, ch))
    return out


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        maps = load_maps_from_args(args)
        model = model_summary(imol)
        selected = _selected_residues(imol, args.chain, args.range_spec)
        if not selected:
            raise CootSkillError("Selected validation scope contains no residues")

        rama = _normalize_rama_payload(coot.all_molecule_ramachandran_score_py(imol))
        rotamer = coot.all_molecule_rotamer_score_py(imol)
        rotamer_summary = None
        if rotamer not in (False, None) and isinstance(rotamer, (list, tuple)) and len(rotamer) >= 2:
            rotamer_summary = {"overall_score": float(rotamer[0]), "n_rotamer_residues": int(rotamer[1])}

        selected_keys = {(r.chain, r.resno, r.inscode) for r in selected}
        worst_rama = []
        if rama and isinstance(rama, dict) and "per_residue" in rama:
            worst_rama = sorted(
                [r for r in rama["per_residue"] if (r["chain"], r["resno"], r["inscode"]) in selected_keys],
                key=lambda x: x["score"],
            )[: max(1, args.worst_n)]

        density = None
        active_map = maps["active_refinement_map"]
        if active_map is not None:
            per_res = []
            for res in selected:
                score = float(coot.density_score_residue_py(imol, res.to_py(), active_map))
                entry = res.to_dict() | {"score": None if isnan(score) else score}
                if entry["score"] is not None and entry["score"] < args.density_threshold:
                    entry["flag"] = "below_threshold"
                per_res.append(entry)
            finite = [x for x in per_res if x["score"] is not None]
            density = {
                "active_map": int(active_map),
                "map_stats": map_stats(active_map),
                "threshold": float(args.density_threshold),
                "n_scored": len(finite),
                "n_below_threshold": sum(1 for x in finite if x["score"] < args.density_threshold),
                "worst_residues": sorted(finite, key=lambda x: x["score"])[: max(1, args.worst_n)],
            }

        probe = None
        if args.probe_dots:
            probe = {
                "probe_available": bool(coot.probe_available_p_py()),
                "dots_file": resolve_path(args.probe_dots),
                "score": coot.probe_clash_score_py(resolve_path(args.probe_dots)),
            }

        report = {
            "ok": True,
            "script": SCRIPT_NAME,
            "inputs": {
                "model": resolve_path(args.model),
                "chain": args.chain,
                "range": parse_range_spec(args.range_spec).to_dict() if args.range_spec else None,
                "worst_n": int(args.worst_n),
                "density_threshold": float(args.density_threshold),
            },
            "model": model,
            "scope": {
                "n_selected_residues": len(selected),
                "selected_preview": [r.to_dict() for r in selected[: max(1, min(10, args.worst_n))]],
            },
            "ramachandran": None if rama is None else {
                "overall_score": rama.get("overall_score"),
                "n_residues": rama.get("n_residues"),
                "non_secondary_score": rama.get("non_secondary_score"),
                "n_non_secondary_residues": rama.get("n_non_secondary_residues"),
                "n_zero_score_residues": rama.get("n_zero_score_residues"),
                "worst_residues": worst_rama,
            },
            "rotamer": rotamer_summary,
            "density": density,
            "probe": probe,
        }
        emit_report(report, args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
