#!/usr/bin/env python3
"""Shared helpers for Phase A classic Coot scripts.

These helpers are intentionally conservative:
- prefer documented classic/python-callable Coot functions
- keep selection syntax simple and explicit
- emit compact JSON reports for downstream agent use

Shared conventions (Phase A)
----------------------------
Input model
  --model PATH                      required coordinate input (.pdb/.cif/.ent/.res)

Input map/data
  --map PATH                        optional CCP4/CNS-style map
  --diff-map PATH                   optional difference map
  --mtz PATH                        optional MTZ instead of --map
  --f-col NAME --phi-col NAME       required with --mtz for primary map
  --weight-col NAME                 optional MTZ weight column for primary map
  --diff-f-col NAME --diff-phi-col NAME
                                    optional MTZ columns for explicit difference map
  --diff-weight-col NAME            optional MTZ weight column for explicit diff map
  --refinement-map {primary,diff,none}
                                    default: primary

Selection syntax
  Single residue: CHAIN:RESNO[:INSCODE]     examples: A:42   A:42:B
  Residue range:  CHAIN:START-END           example:  A:42-47

Output
  --output-model PATH               optional updated coordinate output
  --report-json PATH                optional machine-readable JSON report

Invocation
  Preferred during development:     python3 script.py ...
  Classic Coot lane:                coot --no-graphics --no-state-script --script script.py
  If passing argv through coot is awkward, set COOT_SKILL_ARGS to a shell-style argument string.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import coot


class CootSkillError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResidueSpec:
    chain: str
    resno: int
    inscode: str = ""

    def to_py(self) -> list[Any]:
        return [self.chain, int(self.resno), self.inscode]

    def to_dict(self) -> dict[str, Any]:
        return {"chain": self.chain, "resno": int(self.resno), "inscode": self.inscode}

    def label(self) -> str:
        return f"{self.chain}:{self.resno}{(':'+self.inscode) if self.inscode else ''}"


@dataclass(frozen=True)
class ResidueRange:
    chain: str
    start: int
    end: int

    def normalized(self) -> "ResidueRange":
        if self.start <= self.end:
            return self
        return ResidueRange(self.chain, self.end, self.start)

    def to_dict(self) -> dict[str, Any]:
        n = self.normalized()
        return {"chain": n.chain, "start": int(n.start), "end": int(n.end)}

    def label(self) -> str:
        n = self.normalized()
        return f"{n.chain}:{n.start}-{n.end}"


def _argv_from_env_or_sys() -> list[str]:
    env = os.environ.get("COOT_SKILL_ARGS", "").strip()
    if env:
        return shlex.split(env)
    argv = sys.argv[1:]
    if argv[:1] == ["--"]:
        return argv[1:]
    return argv


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    return parser.parse_args(_argv_from_env_or_sys())


def add_common_io_args(parser: argparse.ArgumentParser, *, require_output_model: bool = False) -> None:
    parser.add_argument("--model", required=True, help="Input coordinate model path")
    parser.add_argument("--map", help="Optional primary CCP4/CNS map")
    parser.add_argument("--diff-map", help="Optional difference map")
    parser.add_argument("--mtz", help="Optional MTZ for map generation")
    parser.add_argument("--f-col", help="Primary map F column (required with --mtz unless only auto-read is desired)")
    parser.add_argument("--phi-col", help="Primary map PHI column (required with --mtz unless only auto-read is desired)")
    parser.add_argument("--weight-col", default="", help="Optional primary map weight column")
    parser.add_argument("--diff-f-col", help="Difference map F column")
    parser.add_argument("--diff-phi-col", help="Difference map PHI column")
    parser.add_argument("--diff-weight-col", default="", help="Optional difference map weight column")
    parser.add_argument(
        "--refinement-map",
        choices=["primary", "diff", "none"],
        default="primary",
        help="Which loaded map to mark as active refinement map",
    )
    parser.add_argument("--output-model", required=require_output_model, help="Output coordinates path")
    parser.add_argument("--report-json", help="Optional JSON report path")


def ensure_parent(path: str | os.PathLike[str] | None) -> None:
    if not path:
        return
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def resolve_path(path: str | None) -> str | None:
    if not path:
        return None
    return str(Path(path).expanduser().resolve())


def emit_report(report: dict[str, Any], report_json: str | None = None) -> None:
    text = json.dumps(report, indent=2, sort_keys=True)
    if report_json:
        ensure_parent(report_json)
        Path(report_json).expanduser().resolve().write_text(text + "\n")
    print(text)


def fail(script_name: str, exc: Exception, report_json: str | None = None, extra: dict[str, Any] | None = None) -> None:
    report = {
        "ok": False,
        "script": script_name,
        "error": {"type": type(exc).__name__, "message": str(exc)},
    }
    if extra:
        report.update(extra)
    emit_report(report, report_json=report_json)
    raise SystemExit(1)


def parse_residue_spec(text: str) -> ResidueSpec:
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise CootSkillError(f"Invalid residue spec '{text}'. Use CHAIN:RESNO[:INSCODE].")
    chain = parts[0].strip()
    if not chain:
        raise CootSkillError(f"Invalid residue spec '{text}': missing chain.")
    try:
        resno = int(parts[1])
    except ValueError as exc:
        raise CootSkillError(f"Invalid residue spec '{text}': residue number must be integer.") from exc
    inscode = parts[2] if len(parts) == 3 else ""
    return ResidueSpec(chain=chain, resno=resno, inscode=inscode)


def parse_range_spec(text: str) -> ResidueRange:
    try:
        chain, body = text.split(":", 1)
        start_s, end_s = body.split("-", 1)
        rng = ResidueRange(chain=chain.strip(), start=int(start_s), end=int(end_s)).normalized()
    except Exception as exc:
        raise CootSkillError(f"Invalid range spec '{text}'. Use CHAIN:START-END.") from exc
    if not rng.chain:
        raise CootSkillError(f"Invalid range spec '{text}': missing chain.")
    return rng


def load_model(model_path: str) -> int:
    model_path = resolve_path(model_path)
    assert model_path is not None
    if not Path(model_path).exists():
        raise CootSkillError(f"Model file not found: {model_path}")
    imol = coot.handle_read_draw_molecule(model_path)
    if imol < 0 or not coot.is_valid_model_molecule(imol):
        raise CootSkillError(f"Failed to load model: {model_path}")
    return imol


def _intvector_to_list(v: Any) -> list[int]:
    try:
        return [int(x) for x in v]
    except TypeError:
        return []


def load_maps_from_args(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {"primary": None, "diff": None, "active_refinement_map": None, "loaded": []}

    if args.map and args.mtz:
        raise CootSkillError("Use either --map/--diff-map or --mtz, not both in one call.")

    if args.map:
        primary = coot.read_ccp4_map(resolve_path(args.map), 0)
        if primary < 0:
            raise CootSkillError(f"Failed to load map: {args.map}")
        result["primary"] = int(primary)
        result["loaded"].append({"kind": "primary", "imol": int(primary), "source": resolve_path(args.map)})
        if args.diff_map:
            diff = coot.read_ccp4_map(resolve_path(args.diff_map), 1)
            if diff < 0:
                raise CootSkillError(f"Failed to load difference map: {args.diff_map}")
            result["diff"] = int(diff)
            result["loaded"].append({"kind": "diff", "imol": int(diff), "source": resolve_path(args.diff_map)})
    elif args.mtz:
        mtz_path = resolve_path(args.mtz)
        assert mtz_path is not None
        if not Path(mtz_path).exists():
            raise CootSkillError(f"MTZ file not found: {mtz_path}")
        if args.f_col and args.phi_col:
            primary = coot.make_and_draw_map(mtz_path, args.f_col, args.phi_col, args.weight_col or "", 1 if args.weight_col else 0, 0)
            if primary < 0:
                raise CootSkillError(f"Failed to make primary map from MTZ: {mtz_path}")
            result["primary"] = int(primary)
            result["loaded"].append({
                "kind": "primary",
                "imol": int(primary),
                "source": mtz_path,
                "f_col": args.f_col,
                "phi_col": args.phi_col,
                "weight_col": args.weight_col or None,
            })
        else:
            made = _intvector_to_list(coot.auto_read_make_and_draw_maps(mtz_path))
            if made:
                result["primary"] = int(made[0])
                result["loaded"].append({"kind": "primary", "imol": int(made[0]), "source": mtz_path, "mode": "auto"})
                if len(made) > 1:
                    result["diff"] = int(made[1])
                    result["loaded"].append({"kind": "diff", "imol": int(made[1]), "source": mtz_path, "mode": "auto"})
        if args.diff_f_col and args.diff_phi_col:
            diff = coot.make_and_draw_map(mtz_path, args.diff_f_col, args.diff_phi_col, args.diff_weight_col or "", 1 if args.diff_weight_col else 0, 1)
            if diff < 0:
                raise CootSkillError(f"Failed to make difference map from MTZ: {mtz_path}")
            result["diff"] = int(diff)
            result["loaded"].append({
                "kind": "diff",
                "imol": int(diff),
                "source": mtz_path,
                "f_col": args.diff_f_col,
                "phi_col": args.diff_phi_col,
                "weight_col": args.diff_weight_col or None,
            })

    target = None
    if args.refinement_map == "primary":
        target = result["primary"]
    elif args.refinement_map == "diff":
        target = result["diff"]
    elif args.refinement_map == "none":
        target = None

    if target is not None:
        rv = coot.set_imol_refinement_map(int(target))
        if rv < 0:
            raise CootSkillError(f"Failed to set refinement map to molecule {target}")
        result["active_refinement_map"] = int(target)
    else:
        current = int(coot.imol_refinement_map())
        result["active_refinement_map"] = current if current >= 0 else None

    return result


def save_model(imol: int, output_path: str | None) -> dict[str, Any] | None:
    if not output_path:
        return None
    output_path = resolve_path(output_path)
    assert output_path is not None
    ensure_parent(output_path)
    suffix = Path(output_path).suffix.lower()
    if suffix == ".pdb":
        status = int(coot.write_pdb_file(imol, output_path))
    else:
        status = int(coot.save_coordinates(imol, output_path))
    out_file = Path(output_path)
    if not out_file.exists() or out_file.stat().st_size == 0:
        raise CootSkillError(f"Failed to write coordinates to {output_path}")
    return {"path": output_path, "status": status, "bytes": int(out_file.stat().st_size)}


def chain_ids(imol: int) -> list[str]:
    raw = coot.get_chain_ids_py(imol)
    if raw is False or raw is None:
        return []
    return [str(x) for x in raw]


def residues_in_chain(imol: int, chain: str) -> list[ResidueSpec]:
    raw = coot.all_residues_with_serial_numbers_py(imol)
    if raw is False or raw is None:
        return []
    out: list[ResidueSpec] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 4:
            serial_no, chain_id, resno, inscode = item[:4]
            if str(chain_id) == chain:
                out.append(ResidueSpec(chain=str(chain_id), resno=int(resno), inscode=str(inscode or "")))
    out.sort(key=lambda r: (r.resno, r.inscode))
    return out


def residues_for_range(imol: int, rng: ResidueRange) -> list[ResidueSpec]:
    r = rng.normalized()
    all_res = residues_in_chain(imol, r.chain)
    return [res for res in all_res if r.start <= res.resno <= r.end]


def residue_specs_for_range(imol: int, rng: ResidueRange) -> list[list[Any]]:
    return [r.to_py() for r in residues_for_range(imol, rng)]


def map_stats(imol_map: int | None) -> dict[str, Any] | None:
    if imol_map is None:
        return None
    if not coot.is_valid_map_molecule(int(imol_map)):
        return None
    stats = coot.map_statistics_py(int(imol_map))
    sigma = coot.map_sigma_py(int(imol_map))
    mean = coot.map_mean_py(int(imol_map))
    out: dict[str, Any] = {"imol": int(imol_map)}
    if stats not in (False, None) and isinstance(stats, (list, tuple)) and len(stats) >= 4:
        out.update({"mean": float(stats[0]), "sigma": float(stats[1]), "skew": float(stats[2]), "kurtosis": float(stats[3])})
    else:
        if mean not in (False, None):
            out["mean"] = float(mean)
        if sigma not in (False, None):
            out["sigma"] = float(sigma)
    return out


def model_summary(imol: int) -> dict[str, Any]:
    chains = chain_ids(imol)
    return {
        "imol": int(imol),
        "name": str(coot.molecule_name(imol) or ""),
        "chain_ids": chains,
        "n_chains": int(coot.n_chains(imol)),
        "n_residues": int(coot.n_residues(imol)),
        "valid_model": bool(coot.is_valid_model_molecule(imol)),
    }


def first_existing_range(imol: int, chain: str) -> ResidueRange | None:
    residues = residues_in_chain(imol, chain)
    if not residues:
        return None
    return ResidueRange(chain=chain, start=min(r.resno for r in residues), end=max(r.resno for r in residues))
