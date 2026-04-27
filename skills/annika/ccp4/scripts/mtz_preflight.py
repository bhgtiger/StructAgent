#!/usr/bin/env python3
"""mtz_preflight.py — column / FreeR / cell / symmetry checks before a CCP4 wrapper runs.

Usage:
    python scripts/mtz_preflight.py --mtz data.mtz --workflow refmac5 [--model model.pdb]

Workflows:
    refmac5    requires F + SIGF + a usable FreeR column
    phaser     requires F + SIGF (or I + SIGI)
    buccaneer  requires F + SIGF and phases (HLA/HLB/HLC/HLD or PHI/FOM)
    nautilus   same as buccaneer

Behaviour:
    - Prefers `gemmi` for structured access.
    - Falls back to parsing `mtzdump` text output. The fallback is intentionally
      narrow — `mtzdump` headings are stable but whitespace-sensitive; if you
      need to extend it, add a fixture first.
    - Prints findings to stdout and returns:
          0  all required checks passed (warnings allowed)
          1  one or more required checks failed
          2  invocation / IO error (file missing, etc.)
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import shutil
import subprocess
import sys
from typing import Iterable


WORKFLOWS = ("refmac5", "phaser", "buccaneer", "nautilus")


@dataclasses.dataclass
class MtzInfo:
    columns: list[tuple[str, str]]   # [(label, type), ...]
    cell: tuple[float, float, float, float, float, float] | None
    spacegroup: str | None
    free_fraction: float | None      # fraction of reflections with the test flag


# ---------------------------------------------------------------------------
# Reading the MTZ
# ---------------------------------------------------------------------------

def read_with_gemmi(path: str) -> MtzInfo | None:
    try:
        import gemmi  # type: ignore
    except ImportError:
        return None
    mtz = gemmi.read_mtz_file(path)
    cols = [(c.label, c.type) for c in mtz.columns]
    cell = (mtz.cell.a, mtz.cell.b, mtz.cell.c,
            mtz.cell.alpha, mtz.cell.beta, mtz.cell.gamma)
    sg = mtz.spacegroup.hm if mtz.spacegroup else None

    free_frac = None
    free_label = pick_free_column([c[0] for c in cols])
    if free_label is not None:
        try:
            arr = mtz.array_for_column(free_label)
            if arr.size:
                # Convention varies (CCP4: 0 is test; Phenix: 1 is test). Report
                # the smaller class as the "test set" so we capture either.
                a, b = (arr == 0).sum(), (arr == 1).sum()
                test = min(a, b) if a > 0 and b > 0 else max(a, b)
                free_frac = float(test) / float(arr.size)
        except Exception:
            free_frac = None
    return MtzInfo(columns=cols, cell=cell, spacegroup=sg, free_fraction=free_frac)


def find_ccp4_setup() -> str | None:
    explicit = os.environ.get("CCP4_SETUP")
    if explicit and os.path.isfile(explicit):
        return explicit
    import glob
    for pattern in (
        "/Applications/ccp4-*/bin/ccp4.setup-sh",
        "/opt/xtal/ccp4-*/bin/ccp4.setup-sh",
        os.path.expanduser("~/ccp4-*/bin/ccp4.setup-sh"),
    ):
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    return None


def read_with_mtzdump(path: str) -> MtzInfo:
    setup = None
    if not shutil.which("mtzdump"):
        setup = find_ccp4_setup()
        if not setup:
            raise SystemExit(
                "[FAIL] Neither gemmi nor mtzdump is available, and no "
                "ccp4.setup-sh was found. Run scripts/check_env.sh for fix guidance, "
                "set $CCP4_SETUP, or install gemmi (`pip install gemmi`)."
            )

    if setup:
        cmd = ["bash", "-lc", f'source "{setup}" >/dev/null 2>&1 && mtzdump HKLIN "{path}"']
    else:
        cmd = ["mtzdump", "HKLIN", path]
    proc = subprocess.run(
        cmd,
        input="HEAD\nEND\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[FAIL] mtzdump exited {proc.returncode}: {proc.stderr.strip()}")

    text = proc.stdout
    columns: list[tuple[str, str]] = []
    in_table = False
    labels_line: list[str] = []
    types_line: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "Column Labels" in line:
            in_table = True
            continue
        if in_table and line and not labels_line:
            labels_line = line.split()
            continue
        if in_table and line and labels_line and not types_line:
            # mtzdump prints "Column Types :" on its own line in some builds.
            if line.lower().startswith("column types"):
                continue
            types_line = line.split()
            break
    if labels_line and types_line and len(labels_line) == len(types_line):
        columns = list(zip(labels_line, types_line))

    cell = None
    sg = None
    cell_match = re.search(
        r"Cell Dimensions[^\n]*\n\s*([-+0-9.eE\s]+)", text
    )
    if cell_match:
        nums = cell_match.group(1).split()
        if len(nums) >= 6:
            try:
                cell = tuple(float(x) for x in nums[:6])  # type: ignore[assignment]
            except ValueError:
                cell = None
    sg_match = re.search(r"Space group[^\n]*:\s*([A-Za-z0-9 \-]+)", text)
    if sg_match:
        sg = sg_match.group(1).strip()

    return MtzInfo(columns=columns, cell=cell, spacegroup=sg, free_fraction=None)


def load_mtz(path: str) -> MtzInfo:
    info = read_with_gemmi(path)
    if info is not None:
        return info
    return read_with_mtzdump(path)


# ---------------------------------------------------------------------------
# Column heuristics
# ---------------------------------------------------------------------------

F_RE  = re.compile(r"^(F|Fobs|FP|F_obs|F-obs)$", re.IGNORECASE)
SF_RE = re.compile(r"^(SIGF|SIGFP|SIGFobs|SIGF_obs|sigF|sigFP)$", re.IGNORECASE)
I_RE  = re.compile(r"^(I|Iobs|IMEAN)$", re.IGNORECASE)
SI_RE = re.compile(r"^(SIGI|SIGIobs|SIGIMEAN)$", re.IGNORECASE)
FREE_RE = re.compile(r"^(FreeR_flag|FreeRflag|FREE|R-?free-?flags?)$", re.IGNORECASE)
HL_RE = re.compile(r"^HL[ABCD]$")
PHI_RE = re.compile(r"^(PHI|PHIB|PHIC)$", re.IGNORECASE)
FOM_RE = re.compile(r"^(FOM|FOMB|FOMC)$", re.IGNORECASE)


def find(labels: Iterable[str], pat: re.Pattern[str]) -> list[str]:
    return [lab for lab in labels if pat.match(lab)]


def pick_free_column(labels: Iterable[str]) -> str | None:
    for lab in labels:
        if FREE_RE.match(lab):
            return lab
    return None


# ---------------------------------------------------------------------------
# Per-workflow checks
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Finding:
    level: str   # OK | WARN | FAIL
    message: str


def check_amplitudes(labels: list[str]) -> tuple[list[Finding], str | None]:
    findings: list[Finding] = []
    fs = find(labels, F_RE)
    sfs = find(labels, SF_RE)
    if not fs:
        # Fall back to intensities — Refmac can scale them, but Refmac5
        # itself wants amplitudes. Be explicit about the gap.
        is_ = find(labels, I_RE)
        sis = find(labels, SI_RE)
        if is_ and sis:
            findings.append(Finding(
                "WARN",
                f"No F/SIGF columns; only intensities found ({is_[0]} / {sis[0]}). "
                "Run ctruncate to produce F/SIGF before Refmac5."
            ))
        else:
            findings.append(Finding("FAIL", "No F/SIGF or I/SIGI columns present."))
        return findings, None
    if len(fs) > 1 or len(sfs) > 1:
        findings.append(Finding(
            "WARN",
            f"Multiple amplitude candidates: F={fs}, SIGF={sfs}. "
            "Pass --labin explicitly with the right pair."
        ))
        return findings, None
    if not sfs:
        findings.append(Finding("FAIL", f"Found {fs[0]} but no SIGF partner."))
        return findings, None
    suggested = f"FP={fs[0]} SIGFP={sfs[0]}"
    findings.append(Finding("OK", f"Amplitudes: {fs[0]} / {sfs[0]}"))
    return findings, suggested


def check_freer(info: MtzInfo) -> tuple[list[Finding], str | None]:
    findings: list[Finding] = []
    labels = [lab for lab, _ in info.columns]
    free = pick_free_column(labels)
    if free is None:
        findings.append(Finding(
            "FAIL",
            "No FreeR-style column found. Generate flags explicitly with freerflag — "
            "skills never auto-create FreeR."
        ))
        return findings, None
    free_type = next(t for lab, t in info.columns if lab == free)
    if free_type != "I":
        findings.append(Finding(
            "WARN",
            f"FreeR column {free} has MTZ type {free_type}; expected I. "
            "Hand-built MTZ?"
        ))
    if info.free_fraction is not None:
        pct = info.free_fraction * 100.0
        if 3.0 <= pct <= 15.0:
            findings.append(Finding(
                "OK",
                f"FreeR column {free} present (test fraction ~{pct:.1f}%)."
            ))
        else:
            findings.append(Finding(
                "WARN",
                f"FreeR column {free} test fraction is {pct:.1f}% — "
                "outside the typical 3%–15% range; double-check."
            ))
    else:
        findings.append(Finding("OK", f"FreeR column {free} present."))
    return findings, f"FREE={free}"


def check_phases(labels: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    hl = find(labels, HL_RE)
    phi = find(labels, PHI_RE)
    fom = find(labels, FOM_RE)
    if len(hl) >= 4:
        findings.append(Finding("OK", f"HL coefficients present: {sorted(hl)}"))
    elif phi and fom:
        findings.append(Finding("OK", f"PHI/FOM phases present: {phi[0]} / {fom[0]}"))
    else:
        findings.append(Finding(
            "FAIL",
            "No HL[A-D] or PHI/FOM phase columns found — autobuild needs phases."
        ))
    return findings


def run_workflow_checks(info: MtzInfo, workflow: str) -> tuple[list[Finding], str | None]:
    labels = [lab for lab, _ in info.columns]
    parts: list[str] = []
    findings: list[Finding] = []

    if workflow == "refmac5":
        amp_f, suggested_amp = check_amplitudes(labels)
        findings.extend(amp_f)
        if suggested_amp:
            parts.append(suggested_amp)
        free_f, suggested_free = check_freer(info)
        findings.extend(free_f)
        if suggested_free:
            parts.append(suggested_free)

    elif workflow == "phaser":
        amp_f, suggested_amp = check_amplitudes(labels)
        findings.extend(amp_f)
        if suggested_amp:
            parts.append(suggested_amp)

    elif workflow in ("buccaneer", "nautilus"):
        amp_f, suggested_amp = check_amplitudes(labels)
        findings.extend(amp_f)
        if suggested_amp:
            parts.append(suggested_amp)
        findings.extend(check_phases(labels))

    suggested_labin = " ".join(parts) if parts else None
    return findings, suggested_labin


# ---------------------------------------------------------------------------
# Cell / symmetry consistency with a model
# ---------------------------------------------------------------------------

def read_model_cell(path: str) -> tuple[tuple[float, float, float, float, float, float] | None, str | None]:
    try:
        import gemmi  # type: ignore
    except ImportError:
        return None, None
    try:
        st = gemmi.read_structure(path)
    except Exception as exc:
        raise SystemExit(f"[FAIL] Could not read model: {path} ({exc})")
    cell = (st.cell.a, st.cell.b, st.cell.c, st.cell.alpha, st.cell.beta, st.cell.gamma) if st.cell else None
    sg = st.spacegroup_hm or None
    return cell, sg


def check_cell_match(info: MtzInfo, model_path: str) -> list[Finding]:
    findings: list[Finding] = []
    cell, sg = read_model_cell(model_path)
    if cell is None and sg is None:
        findings.append(Finding(
            "WARN",
            "gemmi not available — skipping MTZ/model cell + symmetry comparison."
        ))
        return findings
    if info.cell and cell:
        for axis, a, b in zip("a b c α β γ".split(), info.cell, cell):
            tol = 0.5
            if abs(a - b) > tol:
                findings.append(Finding(
                    "FAIL",
                    f"Cell {axis} mismatch: MTZ {a:.3f} vs model {b:.3f} (>|0.5|)."
                ))
        else:
            findings.append(Finding("OK", "MTZ and model cell agree within tolerance."))
    if info.spacegroup and sg:
        normalise = lambda s: re.sub(r"\s+", "", s)
        if normalise(info.spacegroup) != normalise(sg):
            findings.append(Finding(
                "FAIL",
                f"Space group mismatch: MTZ '{info.spacegroup}' vs model '{sg}'."
            ))
        else:
            findings.append(Finding("OK", f"Space group matches: {info.spacegroup}"))
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mtz", required=True, help="Path to MTZ file")
    p.add_argument("--workflow", required=True, choices=WORKFLOWS,
                   help="Which workflow's column requirements to check")
    p.add_argument("--model", help="Optional PDB/mmCIF for cell+symmetry comparison")
    args = p.parse_args()

    if not os.path.isfile(args.mtz):
        print(f"[FAIL] MTZ not found: {args.mtz}", file=sys.stderr)
        return 2
    if args.model and not os.path.isfile(args.model):
        print(f"[FAIL] Model not found: {args.model}", file=sys.stderr)
        return 2

    info = load_mtz(args.mtz)
    print(f"[MTZ]  {args.mtz}")
    print(f"[COLS] {len(info.columns)} columns")
    for lab, ty in info.columns:
        print(f"       {lab:20s} type={ty}")
    if info.cell:
        a, b, c, al, be, ga = info.cell
        print(f"[CELL] {a:.3f} {b:.3f} {c:.3f}  {al:.2f} {be:.2f} {ga:.2f}")
    if info.spacegroup:
        print(f"[SG]   {info.spacegroup}")

    findings, suggested = run_workflow_checks(info, args.workflow)
    if args.model:
        findings.extend(check_cell_match(info, args.model))

    failed = False
    for f in findings:
        print(f"[{f.level:4s}] {f.message}")
        if f.level == "FAIL":
            failed = True
    if suggested:
        print(f"[HINT] suggested --labin: \"{suggested}\"")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
