#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from typing import Any

import coot
from classic_common import (
    CootSkillError,
    add_common_io_args,
    emit_report,
    fail,
    load_maps_from_args,
    load_model,
    map_stats,
    model_summary,
    parse_args,
    resolve_path,
    save_model,
)

SCRIPT_NAME = "classic_density_candidates"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a narrow Phase C density-candidate operation for waters / peaks / blobs / coordination triage and emit a JSON summary."
    )
    add_common_io_args(parser, require_output_model=False)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("find-blobs", help="Report blob candidates near the model from the active/selected map")
    p.add_argument("--cutoff", type=float, default=1.0, help="Blob cutoff in map sigma units")
    p.add_argument("--limit", type=int, default=25, help="Maximum number of candidates to report")

    p = sub.add_parser("map-peaks", help="Report map peak candidates around the model from the selected map")
    p.add_argument("--sigma", type=float, default=3.0, help="Peak threshold in sigma")
    p.add_argument("--negative-also", action="store_true", help="Include negative peaks where supported")
    p.add_argument("--limit", type=int, default=25, help="Maximum number of candidates to report")

    p = sub.add_parser("peaks-near-point", help="Report map peaks within a radius of one point")
    p.add_argument("--sigma", type=float, default=3.0, help="Peak threshold in sigma")
    p.add_argument("--x", type=float, required=True)
    p.add_argument("--y", type=float, required=True)
    p.add_argument("--z", type=float, required=True)
    p.add_argument("--radius", type=float, required=True)
    p.add_argument("--limit", type=int, default=25, help="Maximum number of candidates to report")

    p = sub.add_parser("find-waters", help="Run Coot water finding and report the created/updated waters")
    p.add_argument("--sigma-cutoff", type=float, default=1.0, help="Water-search sigma cutoff")
    p.add_argument(
        "--new-waters-molecule",
        action="store_true",
        help="Create waters in a new molecule instead of modifying the loaded model",
    )
    p.add_argument("--move-around-protein", action="store_true", help="Repack waters around the protein after water finding")
    p.add_argument("--renumber", action="store_true", help="Renumber waters consecutively after water finding")
    p.add_argument(
        "--output-model",
        help="Optional output path for the resulting waters molecule if --new-waters-molecule is used, otherwise the updated model",
    )

    p = sub.add_parser("check-waters", help="Flag suspicious waters by B-factor / map-score / distance heuristics")
    p.add_argument("--b-factor-limit", type=float, default=60.0)
    p.add_argument("--map-sigma-limit", type=float, default=1.5)
    p.add_argument("--min-dist", type=float, default=2.4)
    p.add_argument("--max-dist", type=float, default=3.2)
    p.add_argument("--part-occ-contact", action="store_true")
    p.add_argument("--zero-occ", action="store_true")
    p.add_argument(
        "--combine",
        choices=["and", "or"],
        default="and",
        help="How to combine the water-check criteria",
    )
    p.add_argument("--limit", type=int, default=25, help="Maximum number of flagged waters to report")

    p = sub.add_parser("prune-waters", help="Delete suspicious waters using the same water-check heuristics")
    p.add_argument("--b-factor-limit", type=float, default=60.0)
    p.add_argument("--map-sigma-limit", type=float, default=1.5)
    p.add_argument("--min-dist", type=float, default=2.4)
    p.add_argument("--max-dist", type=float, default=3.2)
    p.add_argument("--part-occ-contact", action="store_true")
    p.add_argument("--zero-occ", action="store_true")
    p.add_argument("--combine", choices=["and", "or"], default="and")
    p.add_argument("--renumber", action="store_true", help="Renumber waters after pruning")
    p.add_argument("--output-model", help="Optional output path for the pruned model")

    p = sub.add_parser("highly-coordinated-waters", help="Report waters/metals with high local coordination")
    p.add_argument("--coordination-number", type=int, default=4)
    p.add_argument("--dist-max", type=float, default=3.2)
    p.add_argument(
        "--target-molecule",
        choices=["model", "refinement-map"],
        default="model",
        help="Inspect the loaded model (usual case) or, rarely, the active refinement-map molecule id",
    )
    p.add_argument("--limit", type=int, default=25, help="Maximum number of candidates to report")

    p = sub.add_parser("ion-site-report", help="Local ion/coordination triage around one xyz point")
    p.add_argument("--x", type=float, required=True)
    p.add_argument("--y", type=float, required=True)
    p.add_argument("--z", type=float, required=True)
    p.add_argument("--radius", type=float, default=4.0)
    p.add_argument("--sigma", type=float, default=3.0, help="Peak threshold in sigma")
    p.add_argument("--blob-cutoff", type=float, default=1.0)
    p.add_argument("--coordination-number", type=int, default=4)
    p.add_argument("--dist-max", type=float, default=3.2)
    p.add_argument("--limit", type=int, default=25)

    return parser


def _xyz_dict(x: float, y: float, z: float) -> dict[str, float]:
    return {"x": float(x), "y": float(y), "z": float(z)}


def _distance(xyz1: dict[str, float], xyz2: dict[str, float]) -> float:
    return math.sqrt(
        (xyz1["x"] - xyz2["x"]) ** 2 + (xyz1["y"] - xyz2["y"]) ** 2 + (xyz1["z"] - xyz2["z"]) ** 2
    )


def _limit_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return items[: max(0, int(limit))]


def _normalize_blob_candidates(raw: Any, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        xyz, volume = item[0], item[1]
        if not isinstance(xyz, (list, tuple)) or len(xyz) < 3:
            continue
        out.append({"xyz": _xyz_dict(xyz[0], xyz[1], xyz[2]), "volume_a3": float(volume)})
    out.sort(key=lambda x: x["volume_a3"], reverse=True)
    return _limit_items(out, limit)


def _normalize_model_peak_candidates(raw: Any, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        height, xyz = item[0], item[1]
        if not isinstance(xyz, (list, tuple)) or len(xyz) < 3:
            continue
        out.append({"height": float(height), "xyz": _xyz_dict(xyz[0], xyz[1], xyz[2])})
    out.sort(key=lambda x: abs(x["height"]), reverse=True)
    return _limit_items(out, limit)


def _normalize_point_peak_candidates(raw: Any, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 4:
            continue
        x, y, z, height = item[:4]
        out.append({"height": float(height), "xyz": _xyz_dict(x, y, z)})
    out.sort(key=lambda x: abs(x["height"]), reverse=True)
    return _limit_items(out, limit)


def _atom_spec_to_dict(atom_spec: Any) -> dict[str, Any]:
    return {
        "chain": str(getattr(atom_spec, "chain_id", "") or ""),
        "resno": int(getattr(atom_spec, "res_no", 0)),
        "inscode": str(getattr(atom_spec, "ins_code", "") or ""),
        "atom_name": str(getattr(atom_spec, "atom_name", "") or "").strip(),
        "alt_conf": str(getattr(atom_spec, "alt_conf", "") or ""),
        "annotation": str(getattr(atom_spec, "string_user_data", "") or ""),
    }


def _normalize_water_baddies(raw: Any, limit: int) -> list[dict[str, Any]]:
    if raw in (False, None):
        return []
    out = []
    for item in list(raw):
        out.append(_atom_spec_to_dict(item))
    return _limit_items(out, limit)


def _summarize_coordination(raw: Any, limit: int) -> dict[str, Any]:
    if raw in (False, None):
        return {"waters": [], "metals": [], "raw": raw}
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return {"waters": [], "metals": [], "raw": raw}

    def normalize_entries(entries: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(entries, (list, tuple)):
            return out
        for item in entries:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            centre, neighbours = item[0], item[1]
            entry: dict[str, Any] = {
                "centre": centre,
                "n_neighbours": len(neighbours) if isinstance(neighbours, (list, tuple)) else None,
            }
            if isinstance(centre, (list, tuple)) and len(centre) >= 3:
                entry["centre_xyz"] = _xyz_dict(centre[0], centre[1], centre[2])
            entry["neighbours"] = list(neighbours)[:10] if isinstance(neighbours, (list, tuple)) else neighbours
            out.append(entry)
        out.sort(key=lambda x: (x.get("n_neighbours") or 0), reverse=True)
        return _limit_items(out, limit)

    return {"waters": normalize_entries(raw[0]), "metals": normalize_entries(raw[1])}


def _filter_coordination_to_point(summary: dict[str, Any], point: dict[str, float], radius: float, limit: int) -> dict[str, Any]:
    def filt(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for entry in entries:
            xyz = entry.get("centre_xyz")
            if not xyz:
                continue
            d = _distance(xyz, point)
            if d <= radius:
                out.append(entry | {"distance_to_query": d})
        out.sort(key=lambda x: x["distance_to_query"])
        return _limit_items(out, limit)

    return {"waters": filt(summary.get("waters", [])), "metals": filt(summary.get("metals", []))}


def _choose_map_imol(command: str, maps: dict[str, Any], *, diff_required: bool = False) -> int:
    target = maps.get("diff") if diff_required else maps.get("active_refinement_map")
    if target is None or not coot.is_valid_map_molecule(int(target)):
        if diff_required:
            raise CootSkillError(f"{command} requires a valid difference map. Load one with --diff-map or MTZ diff columns.")
        raise CootSkillError(f"{command} requires an active valid map. Load a map or MTZ and keep --refinement-map at a valid choice.")
    return int(target)


def _water_check_flags(args: argparse.Namespace) -> tuple[float, float, float, float, int, int, int]:
    return (
        float(args.b_factor_limit),
        float(args.map_sigma_limit),
        float(args.min_dist),
        float(args.max_dist),
        1 if args.part_occ_contact else 0,
        1 if args.zero_occ else 0,
        1 if args.combine == "and" else 0,
    )


def _find_or_choose_water_imol(imol: int) -> int:
    water_chain = coot.water_chain_py(imol)
    if water_chain not in (False, None, ""):
        return int(imol)
    raise CootSkillError("The loaded model does not appear to contain a water chain. Provide a model/waters file that already contains waters.")


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        maps = load_maps_from_args(args)
        before = model_summary(imol)
        output_model_info = None

        if args.command == "find-blobs":
            map_imol = _choose_map_imol(args.command, maps)
            raw = coot.find_blobs_py(imol, map_imol, float(args.cutoff))
            candidates = _normalize_blob_candidates(raw, int(args.limit))
            op = {
                "command": args.command,
                "map_imol": map_imol,
                "map_stats": map_stats(map_imol),
                "cutoff": float(args.cutoff),
                "n_candidates": len(candidates),
                "candidates": candidates,
                "note": "Blob candidates are density-only; they are not chemically interpreted here.",
            }

        elif args.command == "map-peaks":
            map_imol = _choose_map_imol(args.command, maps)
            raw = coot.map_peaks_around_molecule_py(map_imol, float(args.sigma), 1 if args.negative_also else 0, imol)
            candidates = _normalize_model_peak_candidates(raw, int(args.limit))
            op = {
                "command": args.command,
                "map_imol": map_imol,
                "map_stats": map_stats(map_imol),
                "sigma": float(args.sigma),
                "negative_also": bool(args.negative_also),
                "n_candidates": len(candidates),
                "candidates": candidates,
                "note": "Peak candidates are map-local maxima/minima around the model only; this script does not classify them as water/ion/ligand automatically.",
            }

        elif args.command == "peaks-near-point":
            map_imol = _choose_map_imol(args.command, maps)
            raw = coot.map_peaks_near_point_py(
                map_imol, float(args.sigma), float(args.x), float(args.y), float(args.z), float(args.radius)
            )
            candidates = _normalize_point_peak_candidates(raw, int(args.limit))
            op = {
                "command": args.command,
                "map_imol": map_imol,
                "map_stats": map_stats(map_imol),
                "sigma": float(args.sigma),
                "point": _xyz_dict(args.x, args.y, args.z),
                "radius": float(args.radius),
                "n_candidates": len(candidates),
                "candidates": candidates,
            }

        elif args.command == "find-waters":
            map_imol = _choose_map_imol(args.command, maps)
            before_n = int(coot.graphics_n_molecules())
            coot.execute_find_waters_real(map_imol, imol, 1 if args.new_waters_molecule else 0, float(args.sigma_cutoff))
            after_n = int(coot.graphics_n_molecules())

            affected_imol = imol
            created = []
            if args.new_waters_molecule and after_n > before_n:
                new_indices = list(range(before_n, after_n))
                created = [
                    {
                        "imol": int(i),
                        "name": str(coot.molecule_name(i) or ""),
                        "summary": model_summary(i) if coot.is_valid_model_molecule(i) else None,
                    }
                    for i in new_indices
                ]
                model_like = [i for i in new_indices if coot.is_valid_model_molecule(i)]
                if model_like:
                    affected_imol = int(model_like[-1])

            moved = None
            if args.move_around_protein:
                moved = int(coot.move_waters_to_around_protein(affected_imol))
            if args.renumber:
                coot.renumber_waters(affected_imol)
            if args.output_model:
                output_model_info = save_model(affected_imol, args.output_model)

            water_chain = None
            try:
                water_chain = coot.water_chain_py(affected_imol)
            except Exception:
                water_chain = None

            op = {
                "command": args.command,
                "map_imol": map_imol,
                "map_stats": map_stats(map_imol),
                "sigma_cutoff": float(args.sigma_cutoff),
                "new_waters_molecule": bool(args.new_waters_molecule),
                "move_around_protein": bool(args.move_around_protein),
                "moved_count": moved,
                "renumber": bool(args.renumber),
                "created_molecules": created,
                "affected_imol": int(affected_imol),
                "affected_summary": model_summary(affected_imol),
                "water_chain": water_chain if water_chain not in (False, None, "") else None,
                "note": "This reports the created/updated waters molecule; it does not claim the waters are chemically final.",
            }

        elif args.command == "check-waters":
            map_imol = _choose_map_imol(args.command, maps)
            water_imol = _find_or_choose_water_imol(imol)
            flags = _water_check_flags(args)
            raw = coot.check_waters_baddies(water_imol, *flags)
            flagged = _normalize_water_baddies(raw, int(args.limit))
            op = {
                "command": args.command,
                "map_imol": map_imol,
                "water_imol": int(water_imol),
                "water_summary": model_summary(water_imol),
                "criteria": {
                    "b_factor_limit": float(args.b_factor_limit),
                    "map_sigma_limit": float(args.map_sigma_limit),
                    "min_dist": float(args.min_dist),
                    "max_dist": float(args.max_dist),
                    "part_occ_contact": bool(args.part_occ_contact),
                    "zero_occ": bool(args.zero_occ),
                    "combine": args.combine,
                },
                "n_flagged": len(flagged),
                "flagged_waters": flagged,
                "note": "This is a heuristic water triage report, not a chemistry-complete decision. It expects a model that already contains waters and an active map.",
            }

        elif args.command == "prune-waters":
            map_imol = _choose_map_imol(args.command, maps)
            water_imol = _find_or_choose_water_imol(imol)
            before_res = int(coot.n_residues(water_imol))
            flags = _water_check_flags(args)
            raw = coot.check_waters_baddies(water_imol, *flags)
            flagged = _normalize_water_baddies(raw, 100000)
            coot.delete_checked_waters_baddies(water_imol, *flags)
            if args.renumber:
                coot.renumber_waters(water_imol)
            after_res = int(coot.n_residues(water_imol))
            if args.output_model:
                output_model_info = save_model(water_imol, args.output_model)
            op = {
                "command": args.command,
                "map_imol": map_imol,
                "water_imol": int(water_imol),
                "criteria": {
                    "b_factor_limit": float(args.b_factor_limit),
                    "map_sigma_limit": float(args.map_sigma_limit),
                    "min_dist": float(args.min_dist),
                    "max_dist": float(args.max_dist),
                    "part_occ_contact": bool(args.part_occ_contact),
                    "zero_occ": bool(args.zero_occ),
                    "combine": args.combine,
                },
                "n_flagged_before_delete": len(flagged),
                "n_residues_before": before_res,
                "n_residues_after": after_res,
                "n_deleted_estimate": max(0, before_res - after_res),
                "renumber": bool(args.renumber),
                "flagged_preview": _limit_items(flagged, 25),
                "affected_summary": model_summary(water_imol),
                "note": "Deletion is heuristic; re-check density and chemistry afterward. It expects a model that already contains waters and an active map.",
            }

        elif args.command == "highly-coordinated-waters":
            target_imol = imol
            if args.target_molecule == "refinement-map":
                target_imol = _choose_map_imol(args.command, maps)
            raw = coot.highly_coordinated_waters_py(target_imol, int(args.coordination_number), float(args.dist_max))
            summary = _summarize_coordination(raw, int(args.limit))
            op = {
                "command": args.command,
                "target_molecule": args.target_molecule,
                "target_imol": int(target_imol),
                "coordination_number": int(args.coordination_number),
                "dist_max": float(args.dist_max),
                "waters": summary["waters"],
                "metals": summary["metals"],
                "note": "This is a coordination-style triage report only; it is not autonomous ion assignment.",
            }

        elif args.command == "ion-site-report":
            point = _xyz_dict(args.x, args.y, args.z)
            map_imol = _choose_map_imol(args.command, maps)
            peak_raw = coot.map_peaks_near_point_py(
                map_imol, float(args.sigma), float(args.x), float(args.y), float(args.z), float(args.radius)
            )
            peaks = _normalize_point_peak_candidates(peak_raw, int(args.limit))

            blob_raw = coot.find_blobs_py(imol, map_imol, float(args.blob_cutoff))
            blobs = []
            for item in _normalize_blob_candidates(blob_raw, 100000):
                d = _distance(item["xyz"], point)
                if d <= float(args.radius):
                    blobs.append(item | {"distance_to_query": d})
            blobs.sort(key=lambda x: x["distance_to_query"])
            blobs = _limit_items(blobs, int(args.limit))

            coord_raw = coot.highly_coordinated_waters_py(imol, int(args.coordination_number), float(args.dist_max))
            coord_summary = _summarize_coordination(coord_raw, 100000)
            local_coord = _filter_coordination_to_point(coord_summary, point, float(args.radius), int(args.limit))

            op = {
                "command": args.command,
                "map_imol": map_imol,
                "map_stats": map_stats(map_imol),
                "point": point,
                "radius": float(args.radius),
                "sigma": float(args.sigma),
                "blob_cutoff": float(args.blob_cutoff),
                "coordination_number": int(args.coordination_number),
                "dist_max": float(args.dist_max),
                "peak_candidates": peaks,
                "blob_candidates": blobs,
                "local_highly_coordinated_waters": local_coord["waters"],
                "local_highly_coordinated_metals": local_coord["metals"],
                "note": "This is local ion-site triage only: density peaks + blob context + existing high-coordination sites near the query point.",
            }

        else:
            raise CootSkillError(f"Unhandled command: {args.command}")

        report = {
            "ok": True,
            "script": SCRIPT_NAME,
            "inputs": {
                "model": resolve_path(args.model),
                "map": resolve_path(getattr(args, "map", None)),
                "diff_map": resolve_path(getattr(args, "diff_map", None)),
                "mtz": resolve_path(getattr(args, "mtz", None)),
                "refinement_map": getattr(args, "refinement_map", None),
                "output_model": resolve_path(getattr(args, "output_model", None)),
            },
            "before": before,
            "operation": op,
            "after": model_summary(imol),
            "output_model": output_model_info,
        }
        emit_report(report, args.report_json)
    except Exception as exc:
        fail(SCRIPT_NAME, exc, args.report_json)


if __name__ == "__main__":
    main()
