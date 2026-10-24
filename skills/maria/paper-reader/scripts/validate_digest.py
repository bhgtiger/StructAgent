#!/usr/bin/env python3
"""
validate_digest.py — Deterministic validator for paper-reader digests and YAML entries.

Enforces Auto_build_v1 (KB-P1..P5, KB-P8) and Maria base schema rules:
  1. Digest byte caps: <= 6,000 B for fulltext, <= 1,200 B for abstract.
  2. Digest structure & mandatory [ALWAYS] locators in Key Quantitative & Method Claims.
  3. Zone-A contamination & phrasing regexes:
     - answer_shaped() patterns: slash tokens (A/247, B/4), explicit chain/residue phrases,
       numeric torsion prescriptions (omega = 0, chi1 = -60), EMDB IDs (EMD-12345, emd12345),
       and case-sensitive 3-letter residue IDs (Pro308, Pro7, Cys4; allows 'met 3', 'his 2', 'Zn(Cys)4').
     - Benchmark target/deposit/EMDB IDs from state/targets.jsonl.
     - Absolute filesystem paths (/gpfs/..., /home/..., /scratch/...).
     - Prescriptive threshold gate phrasing (must be >= ..., accept only if ... < ...).
     - Run-derived references (reports/target..., run IDs).
  4. YAML schema validation: Maria base fields + enums and Auto_build_v1 Tier-2 extensions.

Usage:
    python3 scripts/validate_digest.py --digest knowledge/literature/digests/<key>.md [--basis fulltext|abstract] [--key <key>]
    python3 scripts/validate_digest.py --yaml knowledge/literature/database_structbio.yaml [--key <key>]
    python3 scripts/validate_digest.py <digest.md_or_database.yaml> [...]
    python3 scripts/validate_digest.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

# ── Byte Caps (KB-P1) ────────────────────────────────────────────────────────
BYTE_CAPS = {
    "fulltext": 6000,
    "abstract": 1200,
}

# ── Allowed Enums & Vocabularies (KB-P1, KB-P2) ─────────────────────────────
ALLOWED_PAPER_TYPES = {
    "method",
    "empirical",
    "review",
    "benchmark",
    "computational",
    "theoretical",
    "workshop_talk",
}

ALLOWED_SIGNIFICANCE = {"high", "medium", "low"}

ALLOWED_PUBLICATION_STATUS = {
    "peer_reviewed",
    "preprint",
    "book",
    "software_doc",
}

ALLOWED_DIGEST_BASIS = {"fulltext", "abstract"}

ALLOWED_BLOCKS = {
    "01_resource",
    "02_build",
    "03_evaluate",
    "04_refine",
    "05_compare",
    "ab-ligand",
}

CANONICAL_PROBLEM_CLASSES = {
    "rotamer_outlier",
    "rama_outlier",
    "clash",
    "low_map_cc",
    "cbeta_deviation",
    "bond_outlier",
    "angle_outlier",
    "cis_nonpro",
    "omega_twisted",
    "asn_gln_his_flip",
    "chain_break",
    "missing_sidechain",
    "register_shift",
    "unaccounted_density",
    "cablam_outlier",
    "coverage_gap",
    "ligand_geometry",
    "ligand_density",
}

NON_CANONICAL_CLASS_HINTS = {
    "cis_peptide": "use 'cis_nonpro' (or 'low_map_cc', 'cbeta_deviation', 'rama_outlier' + topic 'xaa_pro_isomer' for silent trans-Pro)",
    "twisted_peptide": "use 'omega_twisted'",
    "local_cc_drop": "use 'low_map_cc'",
    "overbuilt_loop": "use 'low_map_cc' (NOT 'coverage_gap')",
    "ligand_coordination": "use 'ligand_geometry'",
    "completeness_gap": "use 'coverage_gap'",
}

INITIAL_TOPICS = {
    "tracer_complementarity",
    "prediction_prior",
    "dictionary_conflict",
    "xaa_pro_isomer",
    "restraint_pricing",
    "external_restraints",
    "overfitting",
    "cc_metrics",
    "resolvability",
    "map_regime",
    "electron_scattering",
    "carboxylate_scattering",
    "radiation_damage",
    "metal_coordination",
    "his_tautomer_metal",
    "restraint_dictionary",
    "atom_naming",
    "ncs_donor",
    "model_bias",
    "copy_stoichiometry",
    "map_scale_strain",
}

# Fallback target/deposit identifiers from Auto_build_v1/state/targets.jsonl
FALLBACK_TARGET_IDS = {
    "emd17522", "emd17735", "emd24188", "emd29982", "emd39117",
    "emd42108", "emd42391", "emd44302", "emd44497", "emd53974",
    "emd60057", "emd60057_c4", "emd64587", "emd64830", "emd65146",
    "emd65437", "emd70562", "emd75874",
}

FALLBACK_DEPOSITS = {
    "11NX", "7N5F", "8GF9", "8P79", "8PKD", "8UBX", "8UN2", "8YBE",
    "8ZFD", "9B77", "9BFI", "9OKF", "9RHR", "9UXN", "9V82", "9VKY", "9VXP",
}

# ── Zone-A Contamination & Phrasing Regexes (KB-P1, KB-P5, KB-P8) ────────────

# 3-letter amino acid codes (TitleCase and UPPERCASE only — case-sensitive so
# lowercase English words 'met 3 criteria' and 'his 2 trials' pass).
AA3_CODES = (
    "Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val|Sec|Pyl|Asx|Glx|"
    "ALA|ARG|ASN|ASP|CYS|GLN|GLU|GLY|HIS|ILE|LEU|LYS|MET|PHE|PRO|SER|THR|TRP|TYR|VAL|SEC|PYL|ASX|GLX"
)

ANSWER_SHAPED_PATTERNS = [
    # 1. Original pattern 1: slash chain/residue or ratio token (A/247, B/4, s/2, P2/1)
    # Note: [/:-] widening is intentionally NOT used so G-08, K-0001, L-0001 pass.
    (
        re.compile(r"\b[A-Za-z][A-Za-z0-9]?/-?\d+\b"),
        "slash chain/residue token (e.g. A/247, B/4, P2/1)",
    ),
    # 1b. Single-letter chain + colon + residue number (A:247, B:562)
    (
        re.compile(r"\b[A-Za-z]:-?\d{1,5}\b"),
        "colon chain:residue identity (e.g. A:247, B:562)",
    ),
    # 2. Original pattern 2: explicit chain + residue phrase
    (
        re.compile(r"\bchains?\s+[A-Za-z0-9]{1,2}\s+residues?\s+-?\d+", re.IGNORECASE),
        "explicit chain/residue identity",
    ),
    # 3. Original pattern 3: numeric torsion equation (omega = 0, chi1 = -60)
    (
        re.compile(r"\b(chi\s*[1-4]|omega|phi|psi)\s*[=:]\s*-?\d", re.IGNORECASE),
        "numeric torsion equation (write canonical angles in words, e.g. 'omega near zero degrees')",
    ),
    # 4. KB-P5 addition 1: EMDB accession
    (
        re.compile(r"\b(?:EMD-\d{4,6}|emd-?\d{4,6})\b"),
        "EMDB identifier",
    ),
    # 5. KB-P5 addition 2: Case-sensitive 3-letter residue + 1..5 digits (Pro308, Pro7, Cys4)
    (
        re.compile(rf"\b(?:{AA3_CODES})[-\s]?\d{{1,5}}\b"),
        "specific residue identifier or bare stoichiometry (e.g. Pro308, Pro7, Cys4; use Zn(Cys)4 for stoichiometry)",
    ),
]

ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s\"'`(=])(/(?:gpfs|home|scratch|tmp|projects|var|Users|opt|etc|root)/\S+)"
)

THRESHOLD_LINT_PATTERNS = [
    (
        re.compile(
            r"\b(?:must(?:\s+be)?|require[sd]?|gate[sd]?|floor|accept\s+only\s+if)\b"
            r"[^.\n;]{0,50}?(?:<=|>=|<|>|==|=)\s*-?\d",
            re.IGNORECASE,
        ),
        "prescriptive threshold/gate phrasing (quote paper numbers 'as reported' instead)",
    ),
    (
        re.compile(
            r"\b(?:clashscore|rotamer_outliers(?:_pct)?|rama_favored|rama_outliers(?:_pct)?|"
            r"cbeta_deviations|bond_rmsd|angle_rmsd|bond_rmsz|angle_rmsz|molprobity_score|"
            r"q_score|atom_inclusion_all|cc_mask|emringer)\b"
            r"[^.\n;]{0,40}?\b(?:must|require[sd]?|gate[sd]?|floor|accept\s+only\s+if)\b",
            re.IGNORECASE,
        ),
        "project readiness/geometry metric paired with prescriptive gate language",
    ),
]

RUN_DERIVED_PATTERNS = [
    (
        re.compile(r"\breports/target\S*", re.IGNORECASE),
        "run-derived target report reference (KB-P8)",
    ),
    (
        re.compile(r"\b202\d{5}T\d{4}_emd\d+\S*"),
        "campaign run identifier (KB-P8)",
    ),
]

LOCATOR_RE = re.compile(
    r"(?:\bp\.?\s*\d+|\bpp\.?\s*\d+|\bpage\s+\d+|\bTable\s+\d+|\bFig(?:ure)?\.?\s*\d+|\b§\s*\d+|\bSection\s+\d+|\bEq(?:uation)?\.?\s*\d+|\babstract\b)",
    re.IGNORECASE,
)

DOI_URL_RE = re.compile(r"https?://doi\.org/\S+|10\.\d{4,9}/\S+")


def load_target_identifiers(targets_jsonl: Path | None = None) -> tuple[set[str], set[str]]:
    """Load target_ids and deposit PDB codes from state/targets.jsonl if available."""
    target_ids = set(FALLBACK_TARGET_IDS)
    deposits = set(FALLBACK_DEPOSITS)

    candidates = []
    if targets_jsonl:
        candidates.append(targets_jsonl)
    else:
        # Auto-discover from current working directory or known Auto_build_v1 location
        cwd = Path.cwd().resolve()
        for parent in [cwd, *cwd.parents]:
            cand = parent / "state" / "targets.jsonl"
            if cand.is_file():
                candidates.append(cand)
                break
        default_ab = Path("/gpfs/home3/xguo/projects/Auto_build_v1/state/targets.jsonl")
        if default_ab.is_file():
            candidates.append(default_ab)

    for path in candidates:
        if path and path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("record") == "target":
                        if row.get("target_id"):
                            target_ids.add(str(row["target_id"]))
                        if row.get("deposit"):
                            deposits.add(str(row["deposit"]).upper())
                        if row.get("emdb"):
                            target_ids.add(str(row["emdb"]))
                break
            except Exception:
                pass

    return target_ids, deposits


def check_zone_a_text(
    text: str,
    context_label: str = "text",
    targets_jsonl: Path | None = None,
) -> list[str]:
    """Run all Zone-A contamination and phrasing checks on a text string."""
    errors: list[str] = []
    if not text:
        return errors

    # Mask out raw DOI strings before slash-token matching so DOIs never false-positive
    text_no_doi = DOI_URL_RE.sub(" ", text)

    for idx, (pattern, desc) in enumerate(ANSWER_SHAPED_PATTERNS):
        haystack = text_no_doi if idx == 0 else text
        match = pattern.search(haystack)
        if match:
            errors.append(
                f"{context_label}: Zone-A answer_shaped() violation — {desc}: {match.group(0)!r}"
            )

    # Check absolute paths
    path_match = ABSOLUTE_PATH_RE.search(text)
    if path_match:
        errors.append(
            f"{context_label}: Zone-A violation — absolute filesystem path: {path_match.group(1)!r}"
        )

    # Check threshold lint
    for pattern, desc in THRESHOLD_LINT_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(
                f"{context_label}: Zone-A threshold lint violation — {desc}: {match.group(0)!r}"
            )

    # Check run-derived patterns
    for pattern, desc in RUN_DERIVED_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(
                f"{context_label}: Zone-A violation — {desc}: {match.group(0)!r}"
            )

    # Check benchmark target_ids and deposit PDB IDs
    target_ids, deposits = load_target_identifiers(targets_jsonl)
    for tid in sorted(target_ids):
        if re.search(rf"\b{re.escape(tid)}\b", text, re.IGNORECASE):
            errors.append(
                f"{context_label}: Zone-A violation — benchmark target identifier {tid!r} from state/targets.jsonl"
            )
            break

    for dep in sorted(deposits):
        if re.search(rf"\b{re.escape(dep)}\b", text, re.IGNORECASE):
            errors.append(
                f"{context_label}: Zone-A violation — benchmark deposit PDB ID {dep!r} from state/targets.jsonl"
            )
            break

    return errors


def _extract_digest_basis_from_markdown(text: str) -> str | None:
    """Detect digest_basis from the digest's Metadata section if present."""
    m = re.search(r"-\s*\*\*Digest basis:\*\*\s*`?(fulltext|abstract)`?", text, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return None


def _extract_key_from_markdown(text: str) -> str | None:
    """Extract Key from the digest's Metadata section if present."""
    m = re.search(r"-\s*\*\*Key:\*\*\s*`?([a-z0-9_]+)`?", text)
    if m:
        return m.group(1)
    return None


def validate_digest_markdown(
    text: str,
    *,
    basis: str | None = None,
    expected_key: str | None = None,
    filepath: Path | None = None,
    mode: str = "auto_build_v1",
    targets_jsonl: Path | None = None,
) -> list[str]:
    """Validate a digest Markdown string against byte caps, locators, and Zone-A rules."""
    errors: list[str] = []
    label = str(filepath) if filepath else "digest"

    byte_len = len(text.encode("utf-8"))
    if byte_len == 0:
        return [f"{label}: digest is empty (0 bytes)"]

    detected_basis = _extract_digest_basis_from_markdown(text)
    effective_basis = basis or detected_basis or "fulltext"
    if effective_basis not in BYTE_CAPS:
        errors.append(f"{label}: invalid digest basis {effective_basis!r} (expected fulltext or abstract)")
        effective_basis = "fulltext"

    if mode == "auto_build_v1":
        cap = BYTE_CAPS[effective_basis]
        if byte_len > cap:
            errors.append(
                f"{label}: byte size {byte_len} B exceeds {effective_basis} hard cap of {cap} B"
            )

        # Filename & Key consistency
        md_key = _extract_key_from_markdown(text)
        key_to_check = expected_key or md_key
        if expected_key and md_key and expected_key != md_key:
            errors.append(
                f"{label}: Metadata Key {md_key!r} does not match expected key {expected_key!r}"
            )
        if filepath and key_to_check and filepath.name != f"{key_to_check}.md":
            errors.append(
                f"{label}: digest filename {filepath.name!r} must be '{key_to_check}.md' in Auto_build_v1 mode"
            )

        # Required sections check
        headings = [
            re.sub(r"\s*\[(?:ALWAYS|BEST-EFFORT)\]\s*$", "", line.lstrip("#").strip())
            for line in text.splitlines()
            if line.startswith("## ")
        ]
        headings_lower = [h.lower() for h in headings]

        required_prefixes = ["metadata", "tl;dr", "key quantitative & method claims"]
        if effective_basis == "fulltext":
            required_prefixes.extend([
                "protocol / mechanism",
                "limitations, contraindications & competing explanations",
            ])

        for req in required_prefixes:
            if not any(h.startswith(req) for h in headings_lower):
                errors.append(f"{label}: missing required section '## {req.title()}'")

        # Check mandatory locators in Key Quantitative & Method Claims
        claims_sec_match = re.search(
            r"^##\s+Key Quantitative & Method Claims[^\n]*\n(.*?)(?=^##\s+|\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if claims_sec_match:
            claims_body = claims_sec_match.group(1)
            bullets = [
                line.strip()
                for line in claims_body.splitlines()
                if line.strip().startswith("- ") or line.strip().startswith("* ")
            ]
            if not bullets:
                errors.append(
                    f"{label}: '## Key Quantitative & Method Claims' must contain at least one bulleted claim"
                )
            for idx, bullet in enumerate(bullets, 1):
                if effective_basis == "fulltext" and not LOCATOR_RE.search(bullet):
                    errors.append(
                        f"{label}: claim bullet #{idx} lacks a mandatory page/section/table/figure locator "
                        f"(e.g. [p. X, Table Y / Fig. Z / §Y.Z]): {bullet[:80]!r}"
                    )

        # Zone-A contamination & phrasing rules
        errors.extend(check_zone_a_text(text, context_label=label, targets_jsonl=targets_jsonl))

    return errors


def validate_yaml_entry(
    entry: dict,
    *,
    mode: str = "auto_build_v1",
    yaml_dir: Path | None = None,
    all_keys: set[str] | None = None,
    strict_connections: bool = False,
    targets_jsonl: Path | None = None,
) -> list[str]:
    """Validate a single YAML database entry."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return ["YAML entry is not a mapping/dict"]

    key = entry.get("key") or f"id={entry.get('id', '?')}"
    label = f"yaml[{key}]"

    # 1. Maria base required fields
    base_required = [
        "id",
        "key",
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "paper_type",
        "significance",
        "tags",
        "digest",
        "maria_opinion",
        "connections",
    ]
    for req in base_required:
        if req not in entry:
            errors.append(f"{label}: missing required base field {req!r}")

    if "id" in entry and (not isinstance(entry["id"], int) or isinstance(entry["id"], bool)):
        errors.append(f"{label}: 'id' must be an integer, got {entry['id']!r}")

    if "key" in entry:
        if not isinstance(entry["key"], str) or not re.fullmatch(r"[a-z0-9_]+", entry["key"]):
            errors.append(f"{label}: 'key' must be snake_case alphanumeric, got {entry['key']!r}")

    if "title" in entry and (not isinstance(entry["title"], str) or not entry["title"].strip()):
        errors.append(f"{label}: 'title' must be a non-empty string")

    if "authors" in entry:
        if not isinstance(entry["authors"], list) or not entry["authors"] or not all(
            isinstance(a, str) and a.strip() for a in entry["authors"]
        ):
            errors.append(f"{label}: 'authors' must be a non-empty list of strings")

    if "year" in entry and (not isinstance(entry["year"], int) or isinstance(entry["year"], bool)):
        errors.append(f"{label}: 'year' must be an integer, got {entry['year']!r}")

    if "journal" in entry and (not isinstance(entry["journal"], str) or not entry["journal"].strip()):
        errors.append(f"{label}: 'journal' must be a non-empty string")

    if "paper_type" in entry and entry["paper_type"] not in ALLOWED_PAPER_TYPES:
        errors.append(
            f"{label}: invalid 'paper_type' {entry['paper_type']!r}; allowed: {sorted(ALLOWED_PAPER_TYPES)}"
        )

    if "significance" in entry and entry["significance"] not in ALLOWED_SIGNIFICANCE:
        errors.append(
            f"{label}: invalid 'significance' {entry['significance']!r}; allowed: {sorted(ALLOWED_SIGNIFICANCE)}"
        )

    if "tags" in entry:
        if not isinstance(entry["tags"], list) or not all(isinstance(t, str) for t in entry["tags"]):
            errors.append(f"{label}: 'tags' must be a list of strings")

    if "maria_opinion" in entry and (
        not isinstance(entry["maria_opinion"], str) or not entry["maria_opinion"].strip()
    ):
        errors.append(f"{label}: 'maria_opinion' must be a non-empty string")

    if "connections" in entry:
        if not isinstance(entry["connections"], list):
            errors.append(f"{label}: 'connections' must be a list of key strings")
        else:
            for conn in entry["connections"]:
                if not isinstance(conn, str) or not re.fullmatch(r"[a-z0-9_]+", conn):
                    errors.append(
                        f"{label}: connection {conn!r} must be an exact snake_case key (never an ID or title)"
                    )
                elif strict_connections and all_keys is not None and conn not in all_keys:
                    errors.append(f"{label}: connection key {conn!r} not found in database")

    # 2. Auto_build_v1 Tier-2 extensions (KB-P1)
    if mode == "auto_build_v1":
        ab_required = [
            "publication_status",
            "digest_basis",
            "pdf",
            "deposit_blind_safe",
            "blocks",
            "problem_classes",
            "topics",
            "tools",
            "verification",
        ]
        for req in ab_required:
            if req not in entry:
                errors.append(f"{label}: missing required Auto_build_v1 field {req!r}")

        pub_status = entry.get("publication_status")
        if pub_status is not None and pub_status not in ALLOWED_PUBLICATION_STATUS:
            errors.append(
                f"{label}: invalid 'publication_status' {pub_status!r}; allowed: {sorted(ALLOWED_PUBLICATION_STATUS)}"
            )

        if pub_status != "software_doc":
            doi = entry.get("doi")
            if not isinstance(doi, str) or not doi.strip():
                errors.append(f"{label}: 'doi' must be a non-empty string for {pub_status!r}")

        digest_basis = entry.get("digest_basis")
        if digest_basis is not None and digest_basis not in ALLOWED_DIGEST_BASIS:
            errors.append(
                f"{label}: invalid 'digest_basis' {digest_basis!r}; allowed: {sorted(ALLOWED_DIGEST_BASIS)}"
            )

        if "deposit_blind_safe" in entry and entry["deposit_blind_safe"] is not True:
            errors.append(f"{label}: 'deposit_blind_safe' must be boolean true for Zone-A literature")

        if "pdf" in entry and entry["pdf"] is not None:
            if not isinstance(entry["pdf"], str) or entry["pdf"].startswith("/") or ".." in entry["pdf"]:
                errors.append(f"{label}: 'pdf' must be null or a clean relative path, got {entry['pdf']!r}")

        if "key" in entry and "digest" in entry:
            expected_digest_rel = f"digests/{entry['key']}.md"
            if entry["digest"] != expected_digest_rel:
                errors.append(
                    f"{label}: 'digest' must be {expected_digest_rel!r} in Auto_build_v1 mode, got {entry['digest']!r}"
                )

        if "blocks" in entry:
            if not isinstance(entry["blocks"], list) or not entry["blocks"]:
                errors.append(f"{label}: 'blocks' must be a non-empty list")
            else:
                for b in entry["blocks"]:
                    if b not in ALLOWED_BLOCKS:
                        errors.append(
                            f"{label}: invalid block {b!r}; allowed: {sorted(ALLOWED_BLOCKS)}"
                        )

        if "problem_classes" in entry:
            if not isinstance(entry["problem_classes"], list):
                errors.append(f"{label}: 'problem_classes' must be a list")
            else:
                for pc in entry["problem_classes"]:
                    if pc not in CANONICAL_PROBLEM_CLASSES:
                        hint = NON_CANONICAL_CLASS_HINTS.get(pc, "")
                        hint_str = f" ({hint})" if hint else ""
                        errors.append(
                            f"{label}: non-canonical problem_class {pc!r}{hint_str}; "
                            f"must be from state/vocab/problem_classes.tsv"
                        )

        if "topics" in entry:
            if not isinstance(entry["topics"], list) or not all(
                isinstance(t, str) and re.fullmatch(r"[a-z0-9_]+", t) for t in entry["topics"]
            ):
                errors.append(f"{label}: 'topics' must be a list of snake_case topic strings")

        if "tools" in entry:
            if not isinstance(entry["tools"], list) or not all(isinstance(t, str) for t in entry["tools"]):
                errors.append(f"{label}: 'tools' must be a list of strings ([] for tool-agnostic)")

        if "verification" in entry:
            ver = entry["verification"]
            if not isinstance(ver, dict):
                errors.append(f"{label}: 'verification' must be a mapping/dict")
            else:
                for vkey in ("doi_resolved_on", "title_matches", "checked_by"):
                    if vkey not in ver:
                        errors.append(f"{label}: 'verification' missing key {vkey!r}")
                if "title_matches" in ver and not isinstance(ver["title_matches"], bool):
                    errors.append(f"{label}: 'verification.title_matches' must be a boolean")
                if "checked_by" in ver and (
                    not isinstance(ver["checked_by"], str) or not ver["checked_by"].strip()
                ):
                    errors.append(f"{label}: 'verification.checked_by' must be a non-empty string")

        # Zone-A check over YAML prose fields
        prose_blob = " | ".join(
            str(entry.get(k, ""))
            for k in ("title", "maria_opinion")
            if entry.get(k)
        )
        if isinstance(entry.get("tags"), list):
            prose_blob += " | " + " ".join(str(t) for t in entry["tags"])
        errors.extend(check_zone_a_text(prose_blob, context_label=label, targets_jsonl=targets_jsonl))

        # Validate linked digest file if yaml_dir is known and file exists
        if yaml_dir and isinstance(entry.get("digest"), str):
            digest_path = yaml_dir / entry["digest"]
            if digest_path.is_file():
                d_text = digest_path.read_text(encoding="utf-8")
                errors.extend(
                    validate_digest_markdown(
                        d_text,
                        basis=digest_basis if digest_basis in ALLOWED_DIGEST_BASIS else "fulltext",
                        expected_key=entry.get("key"),
                        filepath=digest_path,
                        mode=mode,
                        targets_jsonl=targets_jsonl,
                    )
                )

    return errors


def validate_yaml_file(
    yaml_path: Path,
    *,
    key_filter: str | None = None,
    mode: str = "auto_build_v1",
    strict_connections: bool = False,
    targets_jsonl: Path | None = None,
) -> list[str]:
    """Validate a YAML literature database file."""
    if not yaml_path.is_file():
        return [f"{yaml_path}: file not found"]

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{yaml_path}: invalid YAML syntax: {exc}"]

    if isinstance(raw, list):
        papers = raw
    elif isinstance(raw, dict):
        if "papers" in raw and isinstance(raw["papers"], list):
            papers = raw["papers"]
        elif "key" in raw and "title" in raw:
            papers = [raw]
        else:
            return [f"{yaml_path}: expected top-level 'papers' list or list of entry mappings"]
    else:
        return [f"{yaml_path}: empty or invalid YAML root"]

    errors: list[str] = []
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    all_keys = {p.get("key") for p in papers if isinstance(p, dict) and isinstance(p.get("key"), str)}

    matched_filter = False
    for entry in papers:
        if not isinstance(entry, dict):
            errors.append(f"{yaml_path}: non-dict entry in papers list")
            continue
        eid = entry.get("id")
        ekey = entry.get("key")
        if isinstance(eid, int):
            if eid in seen_ids:
                errors.append(f"{yaml_path}: duplicate id {eid}")
            seen_ids.add(eid)
        if isinstance(ekey, str):
            if ekey in seen_keys:
                errors.append(f"{yaml_path}: duplicate key {ekey!r}")
            seen_keys.add(ekey)

        if key_filter and ekey != key_filter:
            continue
        matched_filter = True

        # Auto-detect mode if 'auto'
        entry_mode = mode
        if mode == "auto":
            has_ab_fields = any(
                k in entry for k in ("deposit_blind_safe", "publication_status", "digest_basis", "blocks")
            )
            entry_mode = "auto_build_v1" if has_ab_fields else "standard"

        errors.extend(
            validate_yaml_entry(
                entry,
                mode=entry_mode,
                yaml_dir=yaml_path.parent,
                all_keys=all_keys,
                strict_connections=strict_connections,
                targets_jsonl=targets_jsonl,
            )
        )

    if key_filter and not matched_filter:
        errors.append(f"{yaml_path}: key {key_filter!r} not found in database")

    return errors


def run_self_tests() -> int:
    """Run built-in unit tests for KB-P1..P5 and §4 guardrails."""
    failures = 0

    def expect_pass(desc: str, errs: list[str]):
        nonlocal failures
        if errs:
            print(f"FAIL (expected pass): {desc}\n  Errors: {errs}")
            failures += 1
        else:
            print(f"PASS: {desc}")

    def expect_fail(desc: str, errs: list[str], substr: str = ""):
        nonlocal failures
        if not errs:
            print(f"FAIL (expected error, got none): {desc}")
            failures += 1
        elif substr and not any(substr in e for e in errs):
            print(f"FAIL (expected {substr!r} in {errs}): {desc}")
            failures += 1
        else:
            print(f"PASS (refused as expected): {desc}")

    # 1. KB-P1 / KB-P5 passing prose fixtures
    passing_phrases = [
        "The model met 3 criteria across his 2 trials without overfitting.",
        "See claim K-0001 and gotcha G-08 for tetrahedral Zn(Cys)4 coordination.",
        "A cis peptide bond has omega near zero degrees, whereas trans has omega near 180 degrees.",
        "Stewart et al. [p. 256, Table 2] report ~5% cis occurrence for Xaa-Pro vs <0.05% for Xaa-nonPro.",
    ]
    for phrase in passing_phrases:
        expect_pass(f"Allowed prose: {phrase!r}", check_zone_a_text(phrase))

    # 2. KB-P1 / KB-P5 refused prose fixtures
    refused_phrases = [
        ("Target EMDB ID emd44497", "EMD"),
        ("Target deposit 8P79", "8P79"),
        ("Slash residue identity A/247", "slash"),
        ("Slash token B/4", "slash"),
        ("Slash token P2/1", "slash"),
        ("Colon residue identity B:562", "colon"),
        ("Residue Pro308", "residue identifier"),
        ("Single-digit residue Pro7", "residue identifier"),
        ("Bare stoichiometry Cys4", "residue identifier"),
        ("Numeric torsion omega = 0", "numeric torsion"),
        ("Numeric torsion chi1 = -60", "numeric torsion"),
        ("Absolute path /gpfs/home3/xguo/scratch/test.pdf", "absolute filesystem path"),
        ("Prescriptive gate clashscore must be <= 5.0", "threshold"),
        ("Run report reference reports/target14_summary.md", "run-derived"),
    ]
    for phrase, expected_sub in refused_phrases:
        expect_fail(f"Refused prose: {phrase!r}", check_zone_a_text(phrase), expected_sub)

    # 3. Valid fulltext digest
    valid_digest = """# Occurrence and role of cis peptide bonds in protein structures

## Metadata [ALWAYS]
- **Key:** `stewart1990_cis_peptides`
- **Authors:** David E. Stewart, Anupam Sarkar, John E. Wampler
- **Journal / Year:** Journal of Molecular Biology (1990)
- **DOI:** `10.1016/0022-2836(90)90159-J`
- **Paper type / Status:** `empirical` / `peer_reviewed`
- **Digest basis:** `fulltext`
- **Blocks / Topics:** `["03_evaluate", "04_refine", "05_compare"]` / `["xaa_pro_isomer"]`

## TL;DR [ALWAYS]
Surveys high-resolution protein crystal structures to establish the baseline frequency of cis peptide bonds (omega near zero degrees) vs trans peptide bonds (omega near 180 degrees).

## Key Quantitative & Method Claims (with Locators) [ALWAYS]
- **[p. 256, Table 2]:** Across 154 non-redundant proteins, Xaa-Pro peptide bonds occur in the cis conformation at ~5.2% frequency, whereas Xaa-nonPro cis bonds occur at <0.05%.
- **[p. 258, §3.2]:** Unrestrained refinement at medium-to-low resolution systematically under-detects Xaa-Pro cis isomers when initialized in the trans state.

## Protocol / Mechanism [ALWAYS]
- **Principle:** Statistical survey of peptide omega torsion angles in curated crystallographic models.
- **Parameters / Regimes:** High-resolution crystallographic reference set; applies to backbone evaluation across all map regimes.

## Limitations, Contraindications & Competing Explanations [ALWAYS]
- **Failure modes / contraindications:** Early PDB cohort includes unrefined or lower-resolution entries that undercount genuine cis-nonPro sites.
- **Competing explanations:** Local low map-model correlation or C-beta deviation near a proline can also arise from crystal-packing/map disorder or register shifts.

## Connections [BEST-EFFORT]
- **Complements / Extends:** `weiss1998_peptide_bonds`, `jabs1999_nonpro_cis`, `croll2015_cis_trans_errors`
"""
    expect_pass(
        "Valid deposit-blind fulltext digest",
        validate_digest_markdown(
            valid_digest,
            basis="fulltext",
            expected_key="stewart1990_cis_peptides",
            filepath=Path("knowledge/literature/digests/stewart1990_cis_peptides.md"),
        ),
    )

    # 4. Digest exceeding byte cap
    oversized = valid_digest + ("\n" + "A" * 6000)
    expect_fail(
        "Oversized fulltext digest (> 6000 B)",
        validate_digest_markdown(oversized, basis="fulltext"),
        "exceeds fulltext hard cap",
    )

    # 5. Digest missing locator in claims
    no_locator_digest = valid_digest.replace("- **[p. 256, Table 2]:**", "- **Finding:**")
    expect_fail(
        "Digest claim missing locator",
        validate_digest_markdown(no_locator_digest, basis="fulltext"),
        "lacks a mandatory page/section/table/figure locator",
    )

    # 6. Valid Auto_build_v1 YAML entry
    valid_entry = {
        "id": 1,
        "key": "stewart1990_cis_peptides",
        "title": "Occurrence and role of cis peptide bonds in protein structures",
        "authors": ["David E. Stewart", "Anupam Sarkar", "John E. Wampler"],
        "year": 1990,
        "journal": "Journal of Molecular Biology",
        "doi": "10.1016/0022-2836(90)90159-J",
        "paper_type": "empirical",
        "significance": "high",
        "tags": ["cis peptide", "proline isomerization", "backbone stereochemistry"],
        "digest": "digests/stewart1990_cis_peptides.md",
        "maria_opinion": "Foundational statistical baseline establishing ~5% cis occurrence for Xaa-Pro vs <0.05% for Xaa-nonPro.",
        "connections": ["weiss1998_peptide_bonds", "jabs1999_nonpro_cis", "croll2015_cis_trans_errors"],
        "publication_status": "peer_reviewed",
        "digest_basis": "fulltext",
        "pdf": None,
        "deposit_blind_safe": True,
        "blocks": ["03_evaluate", "04_refine", "05_compare"],
        "problem_classes": ["cis_nonpro", "low_map_cc", "cbeta_deviation", "rama_outlier"],
        "topics": ["xaa_pro_isomer"],
        "tools": [],
        "verification": {
            "doi_resolved_on": "2026-10-23",
            "title_matches": True,
            "checked_by": "crossref",
        },
    }
    expect_pass("Valid Auto_build_v1 YAML entry", validate_yaml_entry(valid_entry, mode="auto_build_v1"))

    # 7. Invalid problem_class (e.g., cis_peptide instead of cis_nonpro)
    bad_entry = dict(valid_entry, problem_classes=["cis_peptide"])
    expect_fail(
        "Non-canonical problem_class 'cis_peptide'",
        validate_yaml_entry(bad_entry, mode="auto_build_v1"),
        "non-canonical problem_class",
    )

    print(f"\nSelf-test complete: {failures} failure(s).")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate paper-reader digests and YAML database entries (standard and Auto_build_v1 modes)."
    )
    parser.add_argument("paths", nargs="*", help="Digest .md or database .yaml files to validate")
    parser.add_argument("--digest", "-d", help="Path to digest Markdown file")
    parser.add_argument("--yaml", "-y", help="Path to YAML database file")
    parser.add_argument("--key", "-k", help="Expected paper key (or filter key in YAML)")
    parser.add_argument(
        "--basis",
        choices=["fulltext", "abstract"],
        help="Digest basis for byte-cap check (default: auto-detected from digest or fulltext)",
    )
    parser.add_argument(
        "--mode",
        choices=["auto_build_v1", "standard", "auto"],
        default="auto_build_v1",
        help="Validation mode (default: auto_build_v1)",
    )
    parser.add_argument(
        "--strict-connections",
        action="store_true",
        help="Require all connection keys to exist within the same YAML file",
    )
    parser.add_argument(
        "--targets-jsonl",
        type=Path,
        help="Optional path to Auto_build_v1 state/targets.jsonl",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in unit tests for Zone-A regexes, byte caps, and YAML schema",
    )
    args = parser.parse_args()

    if args.self_test:
        return run_self_tests()

    digest_files: list[Path] = []
    yaml_files: list[Path] = []

    if args.digest:
        digest_files.append(Path(args.digest))
    if args.yaml:
        yaml_files.append(Path(args.yaml))
    for p_str in args.paths:
        p = Path(p_str)
        if p.suffix.lower() in {".yaml", ".yml"}:
            yaml_files.append(p)
        else:
            digest_files.append(p)

    if not digest_files and not yaml_files:
        parser.print_help()
        return 2

    all_errors: list[str] = []

    for d_path in digest_files:
        if not d_path.is_file():
            all_errors.append(f"{d_path}: file not found")
            continue
        text = d_path.read_text(encoding="utf-8")
        errs = validate_digest_markdown(
            text,
            basis=args.basis,
            expected_key=args.key,
            filepath=d_path,
            mode="auto_build_v1" if args.mode == "auto" else args.mode,
            targets_jsonl=args.targets_jsonl,
        )
        all_errors.extend(errs)
        if not errs:
            byte_len = len(text.encode("utf-8"))
            print(f"OK: {d_path} ({byte_len} bytes)")

    for y_path in yaml_files:
        errs = validate_yaml_file(
            y_path,
            key_filter=args.key,
            mode=args.mode,
            strict_connections=args.strict_connections,
            targets_jsonl=args.targets_jsonl,
        )
        all_errors.extend(errs)
        if not errs:
            print(f"OK: {y_path}" + (f" [key={args.key}]" if args.key else ""))

    if all_errors:
        print(f"\nVALIDATION FAILED ({len(all_errors)} error(s)):", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
