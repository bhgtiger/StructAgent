#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

import coot
from classic_common import (
    CootSkillError,
    ResidueSpec,
    add_common_io_args,
    chain_ids,
    emit_report,
    fail,
    load_maps_from_args,
    load_model,
    model_summary,
    parse_args,
    parse_range_spec,
    parse_residue_spec,
    resolve_path,
    residues_for_range,
    save_model,
)

SCRIPT_NAME = "classic_mutate"

AA_1TO3 = {
    "A": "ALA",
    "R": "ARG",
    "N": "ASN",
    "D": "ASP",
    "C": "CYS",
    "Q": "GLN",
    "E": "GLU",
    "G": "GLY",
    "H": "HIS",
    "I": "ILE",
    "L": "LEU",
    "K": "LYS",
    "M": "MET",
    "F": "PHE",
    "P": "PRO",
    "S": "SER",
    "T": "THR",
    "W": "TRP",
    "Y": "TYR",
    "V": "VAL",
    "U": "SEC",
    "O": "PYL",
    "X": "UNK",
}

DNA_1TO3 = {"A": "DA", "C": "DC", "G": "DG", "T": "DT", "X": "DU"}
RNA_1TO3 = {"A": "A", "C": "C", "G": "G", "U": "U", "T": "U", "X": "U"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a narrow Phase B mutation / sequence-repair workflow on a model and emit a JSON summary."
    )
    add_common_io_args(parser, require_output_model=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mutate-residue", help="Mutate one explicit residue to a target residue/base type")
    p.add_argument("--residue", required=True, help="Residue spec CHAIN:RESNO[:INSCODE]")
    p.add_argument("--target", required=True, help="Target residue type; 3-letter protein code or explicit base code")
    p.add_argument(
        "--polymer",
        choices=["auto", "protein", "dna", "rna"],
        default="auto",
        help="Mutation lane for target interpretation; auto prefers protein mutate() unless target looks nucleotide-like",
    )

    p = sub.add_parser("mutate-range", help="Mutate a contiguous residue range from a one-letter sequence string")
    p.add_argument("--range", required=True, dest="range_spec", help="Residue range CHAIN:START-END")
    p.add_argument("--sequence", required=True, help="One-letter sequence; length must match range length")
    p.add_argument(
        "--polymer",
        choices=["protein", "dna", "rna"],
        default="protein",
        help="Interpretation for one-letter sequence",
    )

    p = sub.add_parser("assign-sequence", help="Assign a chain sequence annotation without mutating coordinates")
    p.add_argument("--chain", required=True)
    p.add_argument(
        "--unsafe-allow-ambiguous-chain-assignment",
        action="store_true",
        help="Bypass the current runtime safety guard for chain-targeted sequence assignment",
    )
    seq_src = p.add_mutually_exclusive_group(required=True)
    seq_src.add_argument("--sequence", help="Sequence text")
    seq_src.add_argument("--sequence-file", help="Sequence/alignment file")
    p.add_argument(
        "--format",
        choices=["auto", "plain", "fasta", "pir"],
        default="auto",
        help="Sequence text format; auto uses plain for --sequence and file-based alignment for --sequence-file",
    )

    p = sub.add_parser("align-and-mutate", help="Align a chain to a target sequence and apply mutations")
    p.add_argument("--chain", required=True)
    p.add_argument("--sequence", required=True, help="Target sequence string (FASTA/plain accepted by Coot)")
    p.add_argument("--renumber", action="store_true", help="Let Coot renumber residues during alignment/mutation")

    p = sub.add_parser("apply-pir", help="Associate and apply a PIR alignment to one chain")
    p.add_argument("--chain", required=True)
    pir_src = p.add_mutually_exclusive_group(required=True)
    pir_src.add_argument("--pir", help="PIR alignment text")
    pir_src.add_argument("--pir-file", help="PIR alignment file")

    return parser


def _residue_name(imol: int, spec: ResidueSpec) -> str | None:
    try:
        name = coot.residue_name(imol, spec.chain, spec.resno, spec.inscode)
    except Exception:
        return None
    if name in (False, None, ""):
        return None
    return str(name)


def _polymer_target_code(polymer: str, code: str) -> str:
    text = code.strip().upper()
    if not text:
        raise CootSkillError("Target residue code is empty")
    if polymer == "protein":
        if len(text) == 1:
            if text not in AA_1TO3:
                raise CootSkillError(f"Unsupported protein one-letter code: {text}")
            return AA_1TO3[text]
        return text
    if polymer == "dna":
        if len(text) == 1:
            if text not in DNA_1TO3:
                raise CootSkillError(f"Unsupported DNA one-letter code: {text}")
            return DNA_1TO3[text]
        return text
    if polymer == "rna":
        if len(text) == 1:
            if text not in RNA_1TO3:
                raise CootSkillError(f"Unsupported RNA one-letter code: {text}")
            return RNA_1TO3[text]
        return text
    raise CootSkillError(f"Unhandled polymer type: {polymer}")


def _auto_polymer_from_target(target: str) -> str:
    text = target.strip().upper()
    if text in {"A", "C", "G", "U", "DA", "DC", "DG", "DT"}:
        if text.startswith("D"):
            return "dna"
        if text == "U":
            return "rna"
    return "protein"


def _mutate_one(imol: int, spec: ResidueSpec, target: str, polymer: str) -> dict[str, Any]:
    before_name = _residue_name(imol, spec)
    use_polymer = _auto_polymer_from_target(target) if polymer == "auto" else polymer
    target_code = _polymer_target_code(use_polymer, target)
    if use_polymer == "protein":
        status = int(coot.mutate(imol, spec.chain, spec.resno, spec.inscode, target_code))
    else:
        status = int(coot.mutate_base(imol, spec.chain, spec.resno, spec.inscode, target_code))
    after_name = _residue_name(imol, spec)
    if status != 1:
        raise CootSkillError(f"Mutation failed for {spec.label()} -> {target_code}")
    return {
        "residue": spec.to_dict(),
        "before": before_name,
        "after": after_name,
        "target": target_code,
        "polymer": use_polymer,
        "status": status,
    }


def _mutate_range(imol: int, range_spec: str, sequence: str, polymer: str) -> dict[str, Any]:
    rng = parse_range_spec(range_spec)
    residues = residues_for_range(imol, rng)
    seq = "".join(sequence.split()).upper()
    if not residues:
        raise CootSkillError(f"No residues found for selected range {rng.label()}")
    if len(residues) != len(seq):
        raise CootSkillError(
            f"Sequence length ({len(seq)}) does not match residue count ({len(residues)}) in {rng.label()}"
        )
    mutations = []
    for spec, code in zip(residues, seq):
        mutations.append(_mutate_one(imol, spec, code, polymer))
    return {
        "range": rng.to_dict(),
        "polymer": polymer,
        "sequence": seq,
        "n_mutations": len(mutations),
        "mutations": mutations,
    }


def _assign_sequence(imol: int, args: argparse.Namespace) -> dict[str, Any]:
    if args.chain not in chain_ids(imol):
        raise CootSkillError(f"Chain '{args.chain}' not found in model")
    if not args.unsafe_allow_ambiguous_chain_assignment:
        raise CootSkillError(
            "assign-sequence is currently guarded off on this runtime because chain-targeted assignment behaved ambiguously in smoke tests. Re-run only with --unsafe-allow-ambiguous-chain-assignment if you explicitly want to probe it."
        )
    if args.sequence_file:
        status = coot.assign_sequence_from_file(imol, resolve_path(args.sequence_file))
        return {
            "chain": args.chain,
            "mode": "assign_sequence_from_file",
            "sequence_file": resolve_path(args.sequence_file),
            "status": status,
            "safety_note": "unsafe ambiguous chain-assignment guard was bypassed explicitly",
        }

    assert args.sequence is not None
    fmt = args.format
    seq = args.sequence.strip()
    if not seq:
        raise CootSkillError("Sequence text is empty")
    if fmt == "auto":
        fmt = "plain"
    if fmt == "plain":
        status = coot.assign_sequence_from_string(imol, args.chain, seq)
        mode = "assign_sequence_from_string"
    elif fmt == "fasta":
        status = coot.assign_fasta_sequence(imol, args.chain, seq)
        mode = "assign_fasta_sequence"
    elif fmt == "pir":
        status = coot.assign_pir_sequence(imol, args.chain, seq)
        mode = "assign_pir_sequence"
    else:
        raise CootSkillError(f"Unhandled sequence format: {fmt}")
    return {
        "chain": args.chain,
        "mode": mode,
        "format": fmt,
        "sequence": seq,
        "status": status,
        "safety_note": "unsafe ambiguous chain-assignment guard was bypassed explicitly",
    }


def _align_and_mutate(imol: int, chain: str, sequence: str, renumber: bool) -> dict[str, Any]:
    if chain not in chain_ids(imol):
        raise CootSkillError(f"Chain '{chain}' not found in model")
    status = coot.align_and_mutate(imol, chain, sequence.strip(), 1 if renumber else 0)
    return {
        "chain": chain,
        "sequence": sequence.strip(),
        "renumber": bool(renumber),
        "status": status,
    }


def _apply_pir(imol: int, chain: str, pir: str | None, pir_file: str | None) -> dict[str, Any]:
    if chain not in chain_ids(imol):
        raise CootSkillError(f"Chain '{chain}' not found in model")
    if pir_file:
        resolved = resolve_path(pir_file)
        coot.associate_pir_alignment_from_file(imol, chain, resolved)
        source = {"mode": "file", "pir_file": resolved}
    else:
        text = (pir or "").strip()
        if not text:
            raise CootSkillError("PIR alignment text is empty")
        coot.associate_pir_alignment(imol, chain, text)
        source = {"mode": "text", "pir": text}
    status = coot.apply_pir_alignment(imol, chain)
    return {"chain": chain, "status": status} | source


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    try:
        imol = load_model(args.model)
        load_maps_from_args(args)
        before = model_summary(imol)

        if args.command == "mutate-residue":
            op = {
                "command": args.command,
                **_mutate_one(imol, parse_residue_spec(args.residue), args.target, args.polymer),
            }
        elif args.command == "mutate-range":
            op = {"command": args.command, **_mutate_range(imol, args.range_spec, args.sequence, args.polymer)}
        elif args.command == "assign-sequence":
            op = {"command": args.command, **_assign_sequence(imol, args)}
        elif args.command == "align-and-mutate":
            op = {"command": args.command, **_align_and_mutate(imol, args.chain, args.sequence, args.renumber)}
        elif args.command == "apply-pir":
            op = {"command": args.command, **_apply_pir(imol, args.chain, args.pir, args.pir_file)}
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
