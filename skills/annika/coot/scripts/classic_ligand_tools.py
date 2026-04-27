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

SCRIPT_NAME = "classic_ligand_tools"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a narrow Phase B ligand / monomer operation and emit a JSON summary."
    )
    add_common_io_args(parser, require_output_model=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-hets", help="List non-water HET groups and non-standard residue names")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("fetch-monomer", help="Fetch/build a monomer from the Coot dictionary")
    p.add_argument("--comp-id", required=True)
    p.add_argument("--idealised", action="store_true", help="Use get_monomer_from_dictionary idealised path")
    p.add_argument("--for-model", action="store_true", help="Use get_monomer_for_molecule against the loaded model")

    p = sub.add_parser("ligand-distortion", help="Return ligand distortion summary for one residue")
    p.add_argument("--residue", required=True)
    p.add_argument(
        "--unsafe-allow-linked-chemistry",
        action="store_true",
        help="Bypass the safety guard that blocks ligand-distortion on models with risky linked-chemistry residue types",
    )

    p = sub.add_parser("flip-ligand", help="Cycle ligand flip state for one residue")
    p.add_argument("--residue", required=True)

    p = sub.add_parser("read-dictionary", help="Read an external CIF dictionary file")
    p.add_argument("--cif", required=True)

    return parser


def _residue_name(imol: int, chain: str, resno: int, inscode: str) -> str | None:
    try:
        name = coot.residue_name(imol, chain, resno, inscode)
    except Exception:
        return None
    if name in (False, None, ""):
        return None
    return str(name)


RISKY_LINKED_CHEM_NAMES = {"SC", "AS", "GS", "PST"}


def _list_hets(imol: int, limit: int) -> dict[str, Any]:
    hets = coot.het_group_residues_py(imol)
    preview = []
    for spec in hets[: max(0, limit)]:
        if not isinstance(spec, (list, tuple)) or len(spec) < 3:
            continue
        chain, resno, inscode = spec[:3]
        preview.append(
            {
                "chain": str(chain),
                "resno": int(resno),
                "inscode": str(inscode or ""),
                "resname": _residue_name(imol, str(chain), int(resno), str(inscode or "")),
            }
        )
    return {
        "n_het_groups": len(hets) if isinstance(hets, (list, tuple)) else None,
        "het_preview": preview,
        "non_standard_residue_names": coot.non_standard_residue_names_py(imol),
    }


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        load_maps_from_args(args)
        before = model_summary(imol)

        if args.command == "list-hets":
            op = {"command": args.command, **_list_hets(imol, int(args.limit))}

        elif args.command == "fetch-monomer":
            comp_id = args.comp_id.upper().strip()
            if not comp_id:
                raise CootSkillError("Empty comp-id")
            if args.idealised:
                monomer_imol = int(coot.get_monomer_from_dictionary(comp_id, 1))
                mode = "get_monomer_from_dictionary"
            elif args.for_model:
                monomer_imol = int(coot.get_monomer_for_molecule(comp_id, imol))
                mode = "get_monomer_for_molecule"
            else:
                monomer_imol = int(coot.get_monomer(comp_id))
                mode = "get_monomer"
            if monomer_imol < 0:
                raise CootSkillError(f"Failed to fetch monomer for {comp_id}")
            op = {
                "command": args.command,
                "comp_id": comp_id,
                "mode": mode,
                "monomer_imol": monomer_imol,
                "comp_name": coot.comp_id_to_name_py(comp_id),
            }

        elif args.command == "ligand-distortion":
            spec = parse_residue_spec(args.residue)
            non_standard = set(coot.non_standard_residue_names_py(imol) or [])
            risky_present = sorted(non_standard & RISKY_LINKED_CHEM_NAMES)
            if risky_present and not args.unsafe_allow_linked_chemistry:
                raise CootSkillError(
                    "ligand-distortion is guarded off for this model because risky linked-chemistry residue types are present: "
                    + ", ".join(risky_present)
                    + ". Re-run only with --unsafe-allow-linked-chemistry if you explicitly want to probe it."
                )
            summary = coot.get_ligand_distortion_summary_info_py(imol, spec.to_py())
            op = {
                "command": args.command,
                "residue": spec.to_dict(),
                "resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
                "summary": summary,
                "safety_note": (
                    "unsafe linked-chemistry guard was bypassed explicitly" if risky_present else None
                ),
            }

        elif args.command == "flip-ligand":
            spec = parse_residue_spec(args.residue)
            before_name = _residue_name(imol, spec.chain, spec.resno, spec.inscode)
            result = coot.flip_ligand(imol, spec.chain, spec.resno)
            op = {
                "command": args.command,
                "residue": spec.to_dict(),
                "before_resname": before_name,
                "result": result,
                "after_resname": _residue_name(imol, spec.chain, spec.resno, spec.inscode),
            }

        elif args.command == "read-dictionary":
            cif = resolve_path(args.cif)
            status = int(coot.read_cif_dictionary(cif))
            if status < 0:
                raise CootSkillError(f"read_cif_dictionary reported failure for {cif}")
            op = {"command": args.command, "cif": cif, "status": status}

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
