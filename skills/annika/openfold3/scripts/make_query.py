#!/usr/bin/env python3
"""make_query.py - build or check an OpenFold3 v0.5.0 inference query JSON (stdlib only).

This is a CONVENIENCE HELPER. The authoritative schema is the Pydantic model pinned at
openfold-3@v0.5.0 (commit c4771653c5d0a3ebb0b3af71b05efd64bc44ee86):
  openfold3/projects/of3_all_atom/config/inference_query_format.py
      InferenceQuerySet -> Query -> Chain / PocketConstraint
and the structure builder that consumes it:
  openfold3/core/data/primitives/structure/query.py
This file re-implements those rules with the Python standard library so a query can be
built and checked on any machine (login node, laptop) without the OpenFold3 environment.
If this helper and the pinned model ever disagree, the pinned model wins; re-check after
any OpenFold3 upgrade (see references/04_input_query_format.md and references/maintenance.md).

Modes
  build from flags  : --name NAME (--protein SEQ[:N] | --rna SEQ[:N] | --dna SEQ[:N]
                       | --ligand-smiles SMILES[:N] | --ligand-ccd CODE[:N]) ... [--out FILE]
  build from a spec : --spec SPEC.json|SPEC.tsv [--out FILE]
  check a file      : --validate QUERY.json [--strict] [--no-path-check] [--json]

Nothing is written unless --out is given (the JSON goes to stdout otherwise); an existing
--out file is never overwritten without --force. The built query is validated before output.

Exit codes: 0 ok (warnings allowed) | 1 invalid query (errors; or warnings with --strict)
            | 2 usage error (bad arguments, unreadable spec, refused overwrite).
Requires Python >= 3.9.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

PIN = "openfold-3@v0.5.0"

# ---- schema facts (pinned: inference_query_format.py, residues.py, dataset_config_components.py)
TOP_KEYS = {"queries", "seeds"}
QUERY_KEYS = {"query_name", "chains", "use_msas", "use_paired_msas", "use_main_msas",
              "covalent_bonds", "pocket_constraint"}
CHAIN_KEYS = {"molecule_type", "chain_ids", "description", "sequence", "non_canonical_residues",
              "smiles", "ccd_codes", "paired_msa_file_paths", "main_msa_file_paths",
              "template_alignment_file_path", "template_entry_chain_ids", "template_cif_paths",
              "template_cif_chain_ids", "sdf_file_path", "cyclic"}
POCKET_KEYS = {"ligand_chain_id", "pocket_residues", "max_distance"}
MOLECULE_TYPES = ["protein", "rna", "dna", "ligand"]          # MoleculeType IntEnum 0..3
POLYMERS = {"protein", "rna", "dna"}
ALPHABET = {"protein": set("ARNDCQEGHILKMFPSTWYVX"),         # PROTEIN_RESTYPE_1TO3 (X = UNK; no U)
            "dna": set("AGCTN"), "rna": set("AGCUN")}         # DNA/RNA_RESTYPE_1TO3
MSA_MOLTYPES = {"protein", "rna"}                             # MSASettings.moltypes default
# MSASettings defaults: a file is parsed only if its stem is a max_seq_counts key; main MSAs
# stack the aln_order stems (uniprot_hits feeds online pairing only); paired files use
# paired_msa_order.
MAIN_MSA_KEYS = {"uniref90_hits", "bfd_uniclust_hits", "bfd_uniref_hits", "cfdb_uniref30",
                 "cfdb_hits", "mgnify_hits", "rfam_hits", "rnacentral_hits", "nt_hits",
                 "nucleotide_collection_hits", "concat_cfdb_uniref100_filtered",
                 "mmseqs_colabfold", "colabfold_main"}                 # aln_order minus "dummy"
PAIRED_MSA_KEYS = {"colabfold_paired"}                                 # paired_msa_order
MSA_FILE_KEYS = MAIN_MSA_KEYS | PAIRED_MSA_KEYS | {"uniprot_hits"}     # max_seq_counts keys
MISPLACED_QUERY_FLAGS = {"use_msas", "use_paired_msas", "use_main_msas"}
KIT_BIG_GATE = 1401        # openfold3_ob0 modes.OF3O_GATE_DEFAULT; env OF3O_MIN_TOKENS
KIT_EXACT_GRAPH_CAP = 512  # openfold3_ob0 `exact` line graphs_max_tokens (polymer tokens)

# Heavy-atom (= token) counts, computed from the CCD shipped with the v0.5.0 runtime
# (biotite.structure.info). Ligands: all heavy atoms. Modified polymer residues: heavy atoms
# minus the CCD leaving atoms that the builder removes. Unknown codes are reported, not guessed.
CCD_LIGAND_TOKENS = {
    "MG": 1, "ZN": 1, "CA": 1, "NA": 1, "K": 1, "CL": 1, "MN": 1, "FE": 1, "FE2": 1, "CU": 1,
    "CO": 1, "NI": 1, "CD": 1, "IOD": 1, "BR": 1,
    "ATP": 31, "ADP": 27, "AMP": 23, "ANP": 31, "ACP": 31, "GTP": 32, "GDP": 28, "GNP": 32,
    "NAD": 44, "NAI": 44, "NAP": 48, "NDP": 48, "FAD": 53, "FMN": 31, "HEM": 43, "HEC": 43,
    "SAM": 27, "SAH": 26, "COA": 48, "ACO": 51, "PLP": 16, "TPP": 26, "BTN": 16,
    "NAG": 15, "NDG": 15, "MAN": 12, "BMA": 12, "GAL": 12, "GLC": 12, "FUC": 11, "SIA": 21,
    "SO4": 5, "PO4": 5, "GOL": 6, "EDO": 4, "ACT": 4, "PEG": 7, "STI": 37,
}
CCD_MODRES_TOKENS = {
    "SEP": 10, "TPO": 11, "PTR": 16, "MSE": 8, "HYP": 8, "MLY": 11, "M3L": 12, "ALY": 12,
    "CSO": 7, "SEC": 6, "PCA": 8, "KCX": 12, "NEP": 14, "ABA": 6,
    "PSU": 20, "5MC": 21, "5MU": 21, "1MA": 23, "2MG": 24, "7MG": 24, "OMC": 21, "OMG": 24,
    "6MA": 22, "8OG": 22,
}
CCD_CODE_RE = re.compile(r"^[A-Z0-9]{1,5}$")
QUERY_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class Report:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.notes: List[str] = []
        self.tokens: Dict[str, dict] = {}

    def err(self, where: str, msg: str) -> None:
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append("%s: %s" % (where, msg))

    def note(self, where: str, msg: str) -> None:
        self.notes.append("%s: %s" % (where, msg))


# ---------------------------------------------------------------- SMILES heavy-atom count
def smiles_heavy_atoms(smi: str) -> Optional[int]:
    """Approximate RDKit heavy-atom count of a SMILES (explicit [H]/[2H] and * not counted).
    Returns None when the string cannot be tokenised."""
    n, i, size = 0, 0, len(smi)
    while i < size:
        ch = smi[i]
        if ch == "[":
            j = smi.find("]", i)
            if j < 0:
                return None
            m = re.match(r"\d*([A-Z][a-z]?|[a-z][a-z]?|\*)", smi[i + 1:j])
            if not m:
                return None
            if m.group(1) not in ("H", "*"):
                n += 1
            i = j + 1
        elif smi.startswith(("Cl", "Br"), i):
            n, i = n + 1, i + 2
        elif ch in "BCNOPSFIbcnops":
            n, i = n + 1, i + 1
        elif ch == "%":
            i += 3
        else:
            i += 1
    return n


def smiles_problems(smi: str) -> List[str]:
    probs = []
    if smi.count("[") != smi.count("]"):
        probs.append("unbalanced [ ]")
    if smi.count("(") != smi.count(")"):
        probs.append("unbalanced ( )")
    bare = re.sub(r"\[[^\]]*\]", "", smi)
    labels = re.findall(r"%\d\d|\d", bare)
    odd = sorted({lab for lab in labels if labels.count(lab) % 2})
    if odd:
        probs.append("unclosed ring bond label(s) %s" % ",".join(odd))
    if re.search(r"\s", smi):
        probs.append("whitespace (RDKit stops parsing at the first space)")
    return probs


# ---------------------------------------------------------------- validation
def _as_list(value):
    return value if isinstance(value, list) else [value]


def _check_path(rep: Report, where: str, value, allow_dir: bool, check: bool,
                base_dir: str) -> List[str]:
    paths = []
    for p in _as_list(value):
        if not isinstance(p, str) or not p:
            rep.err(where, "path must be a non-empty string, got %r" % (p,))
            continue
        paths.append(p)
        if "<" in p and ">" in p:
            (rep.note if not check else rep.err)(where, "placeholder path not filled in: %s" % p)
            continue
        if not os.path.isabs(p):
            rep.warn(where, "relative path %r is resolved against the working directory of the "
                     "OpenFold3 process, not the JSON's folder; prefer absolute paths" % p)
        if not check:
            continue
        ok = os.path.isfile(p) or (allow_dir and os.path.isdir(p))
        if not ok:
            hint = ""
            if not os.path.isabs(p) and os.path.exists(os.path.join(base_dir, p)):
                hint = " (it exists relative to the JSON file; make it absolute)"
            rep.err(where, "path does not exist here%s: %s  [Pydantic FilePath%s checks "
                    "existence at load time; use --no-path-check when validating off-host]"
                    % (hint, p, "|DirectoryPath" if allow_dir else ""))
    return paths


def _check_msa_names(rep: Report, where: str, paths: List[str], check: bool,
                     paired: bool) -> None:
    """Default MSASettings slots (see MAIN_MSA_KEYS); files are only inspected on this host."""
    if not check or any("<" in p or p.endswith(".npz") for p in paths) \
            or not all(os.path.exists(p) for p in paths):
        return
    slot = PAIRED_MSA_KEYS if paired else MAIN_MSA_KEYS
    used = 0
    for p in paths:
        files = [os.path.join(p, f) for f in sorted(os.listdir(p))] if os.path.isdir(p) else [p]
        for f in files:
            stem, ext = os.path.splitext(os.path.basename(f))
            if ext not in (".a3m", ".sto"):
                if f == p:
                    rep.err(where, "MSA file must be .a3m, .sto or .npz: %s" % f)
            elif stem in slot:
                used += 1
            elif stem == "uniprot_hits" and not paired:
                rep.note(where, "uniprot_hits feeds online pairing only (not the main MSA)")
            elif stem in MSA_FILE_KEYS:
                rep.warn(where, "MSA file %r is parsed but unused: %s" % (f, (
                    "paired files must be named colabfold_paired.* (paired_msa_order)" if paired
                    else "not in aln_order, so not stacked into the main MSA")))
            else:
                rep.warn(where, "MSA file %r: stem %r is not a default max_seq_counts key, so it "
                         "is SKIPPED unless the runner YAML adds it "
                         "(dataset_config_kwargs.msa.max_seq_counts / aln_order)" % (f, stem))
    if not used and not paired:
        rep.err(where, "no .a3m/.sto file with a default aln_order stem (e.g. "
                "uniref90_hits.a3m): with default MSA settings the query fails at featurization "
                "(if your runner YAML adds the stems, re-run with --no-path-check)")


def _estimate_chain_tokens(mt: str, chain: dict) -> Tuple[int, List[str]]:
    """(model tokens per copy, unknown codes). Unknown codes count 1 (lower bound)."""
    unknown: List[str] = []
    if mt in POLYMERS:
        seq = chain.get("sequence") if isinstance(chain.get("sequence"), str) else ""
        ncr = chain.get("non_canonical_residues") or {}
        tok = len(seq)
        if isinstance(ncr, dict):
            for code in ncr.values():
                code = str(code)
                if code in CCD_MODRES_TOKENS:
                    tok += CCD_MODRES_TOKENS[code] - 1
                else:
                    unknown.append(code)
        return tok, unknown
    smi = chain.get("smiles")
    if isinstance(smi, str) and smi:
        n = smiles_heavy_atoms(smi)
        if n is None:
            return 0, ["SMILES"]
        return n, unknown
    ccd = chain.get("ccd_codes")
    if ccd is not None:
        code = str(_as_list(ccd)[0])
        if code in CCD_LIGAND_TOKENS:
            return CCD_LIGAND_TOKENS[code], unknown
        unknown.append(code)
    return 0, unknown


def _kit_polymer_tokens(chain: dict) -> int:
    """openfold3_ob0 inputs.query_polymer_tokens for one entry: residues x copies of chains whose
    molecule_type STRING is protein/rna/dna (ligand atoms and modified-residue atoms ignored)."""
    ids, seq = chain.get("chain_ids"), chain.get("sequence")
    copies = len(ids) if isinstance(ids, (list, tuple)) else 1
    if str(chain.get("molecule_type", "")).lower() in POLYMERS and isinstance(seq, str):
        return len(seq) * max(copies, 1)
    return 0


def validate_chain(rep: Report, where: str, chain, check_paths: bool, base_dir: str):
    if not isinstance(chain, dict):
        rep.err(where, "chain must be an object")
        return None, []
    for k in chain:
        if k not in CHAIN_KEYS:
            if k in MISPLACED_QUERY_FLAGS:
                rep.err(where, "%r is a QUERY-level field in v0.5.0 (Chain forbids extra keys: "
                        "'Extra inputs are not permitted'); move it next to \"chains\"" % k)
            elif k == "ligand_name":
                rep.err(where, "'ligand_name' exists only on upstream main, not in v0.5.0 "
                        "(Chain forbids extra keys)")
            else:
                rep.err(where, "unknown chain key %r (Chain forbids extra keys)" % k)
    mt_raw = chain.get("molecule_type")
    mt = None
    if mt_raw is None:
        rep.err(where, "missing required 'molecule_type'")
    elif isinstance(mt_raw, bool):
        rep.err(where, "molecule_type must be protein|rna|dna|ligand")
    elif isinstance(mt_raw, int) and 0 <= mt_raw <= 3:
        mt = MOLECULE_TYPES[mt_raw]
    elif isinstance(mt_raw, str) and mt_raw.lower() in MOLECULE_TYPES:
        mt = mt_raw.lower()
    else:
        rep.err(where, "invalid molecule_type %r (protein|rna|dna|ligand, case-insensitive)"
                % (mt_raw,))
    ids_raw = chain.get("chain_ids")
    ids: List[str] = []
    if ids_raw is None:
        rep.err(where, "missing required 'chain_ids'")
    else:
        for cid in _as_list(ids_raw):
            if not isinstance(cid, str) or not cid:
                rep.err(where, "chain id must be a non-empty string, got %r" % (cid,))
            else:
                ids.append(cid)
                if not re.match(r"^[A-Za-z0-9]+$", cid):
                    rep.warn(where, "chain id %r is not alphanumeric" % cid)
                elif len(cid) > 4:
                    rep.warn(where, "chain id %r is long; keep ids short (the optional "
                             "structure_format: pdb output holds 1 character)" % cid)
        if isinstance(ids_raw, list) and not ids_raw:
            rep.err(where, "chain_ids is empty (the schema accepts it; the entry is silently "
                    "dropped from the structure)")
    if "description" in chain and chain["description"] is not None \
            and not isinstance(chain["description"], str):
        rep.err(where, "description must be a string")
    if "cyclic" in chain and not isinstance(chain["cyclic"], bool):
        rep.warn(where, "cyclic should be a JSON boolean (true/false)")
    if "sdf_file_path" in chain and chain["sdf_file_path"] is not None:
        rep.err(where, "sdf_file_path is in the schema but the v0.5.0 builder raises "
                "NotImplementedError('SDF format for ligands is not yet supported.'); use smiles")
    seq = chain.get("sequence")
    if seq is not None and not isinstance(seq, str):
        rep.err(where, "sequence must be a string")
        seq = None
    ncr = chain.get("non_canonical_residues")
    ncr_pos = set()
    if ncr is not None:
        if not isinstance(ncr, dict):
            rep.err(where, "non_canonical_residues must be an object {\"<1-based pos>\": \"CCD\"}")
        else:
            for k, v in ncr.items():
                try:
                    pos = int(k)
                except (TypeError, ValueError):
                    rep.err(where, "non_canonical_residues key %r is not an integer" % (k,))
                    continue
                ncr_pos.add(pos)
                if not isinstance(v, str) or not CCD_CODE_RE.match(v):
                    rep.err(where, "non_canonical_residues[%s]=%r must be an upper-case CCD code"
                            % (k, v))
                if isinstance(seq, str) and not 1 <= pos <= len(seq):
                    rep.err(where, "non_canonical_residues position %d outside 1..%d (the "
                            "builder silently ignores it)" % (pos, len(seq)))
    if mt in POLYMERS:
        if not seq:
            rep.err(where, "%s chain needs a non-empty 'sequence'" % mt)
        else:
            bad = sorted({c for c in seq if not ("A" <= c <= "Z")})
            if bad:
                rep.err(where, "sequence has characters outside A-Z %r (no upper-casing or "
                        "stripping happens; they become unknown residues)" % "".join(bad))
            odd = sorted({c for i, c in enumerate(seq, 1)
                          if "A" <= c <= "Z" and c not in ALPHABET[mt] and i not in ncr_pos})
            if odd:
                extra = " (selenocysteine: use non_canonical_residues {\"<pos>\": \"SEC\"})" \
                    if mt == "protein" and "U" in odd else ""
                rep.warn(where, "letters %r are not in the v0.5.0 %s alphabet %s and become "
                         "unknown residues (UNK/N/DN)%s"
                         % ("".join(odd), mt, "".join(sorted(ALPHABET[mt])), extra))
        for k in ("smiles", "ccd_codes"):
            if chain.get(k) is not None:
                rep.warn(where, "%r is ignored on a %s chain" % (k, mt))
        if chain.get("cyclic") and mt != "protein":
            rep.note(where, "cyclic on a %s chain: only cyclic peptides are shown upstream" % mt)
    elif mt == "ligand":
        smi, ccd = chain.get("smiles"), chain.get("ccd_codes")
        if seq is not None:
            rep.err(where, "'sequence' on a ligand chain makes the v0.5.0 builder fail with "
                    "KeyError (the entity map keys the sequence); remove it")
        if ncr is not None:
            rep.warn(where, "non_canonical_residues is ignored on a ligand chain")
        if chain.get("cyclic"):
            rep.warn(where, "cyclic is for polymer chains; drop it on a ligand")
        if smi is None and ccd is None and chain.get("sdf_file_path") is None:
            rep.err(where, "ligand needs 'smiles' or 'ccd_codes' (builder: 'No valid molecule "
                    "specification found.')")
        if smi is not None and ccd is not None:
            rep.err(where, "give smiles OR ccd_codes, not both (v0.5.0 builder fails with "
                    "KeyError: the entity map keys the CCD code, the structure uses the SMILES)")
        if smi is not None:
            if not isinstance(smi, str) or not smi.strip():
                rep.err(where, "smiles must be a non-empty string")
            else:
                for p in smiles_problems(smi):
                    rep.err(where, "SMILES %s" % p)
                if "." in smi:
                    rep.warn(where, "multi-fragment SMILES ('.') puts several molecules in ONE "
                             "ligand chain; use one ligand chain per molecule")
        if ccd is not None:
            codes = _as_list(ccd)
            if not all(isinstance(c, str) for c in codes) or not codes:
                rep.err(where, "ccd_codes must be a string or a list of strings")
            else:
                if len(codes) > 1:
                    rep.err(where, "multiple ccd_codes raise NotImplementedError in v0.5.0 "
                            "('Multiple CCD codes for a single chain are not yet supported.')")
                for c in codes:
                    if not CCD_CODE_RE.match(c):
                        rep.err(where, "CCD code %r should be 1-5 upper-case letters/digits" % c)
    # MSA fields
    for key in ("main_msa_file_paths", "paired_msa_file_paths"):
        if chain.get(key) is not None:
            paths = _check_path(rep, "%s.%s" % (where, key), chain[key], True, check_paths,
                                base_dir)
            _check_msa_names(rep, "%s.%s" % (where, key), paths, check_paths,
                             key == "paired_msa_file_paths")
            if mt is not None and mt not in MSA_MOLTYPES:
                rep.warn(where, "%s on a %s chain is ignored (MSAs are used for protein and "
                         "RNA only)" % (key, mt))
    # templates
    aln, cifs, cif_ids = (chain.get("template_alignment_file_path"),
                          chain.get("template_cif_paths"), chain.get("template_cif_chain_ids"))
    if aln is not None:
        if isinstance(aln, list):
            rep.err(where, "template_alignment_file_path takes ONE path")
        else:
            _check_path(rep, where + ".template_alignment_file_path", aln, False, check_paths,
                        base_dir)
            if isinstance(aln, str) and os.path.splitext(aln)[1] not in (".sto", ".a3m", ".m8"):
                rep.warn(where, "template alignment should be .sto, .a3m or .m8")
    if cifs is not None:
        _check_path(rep, where + ".template_cif_paths", cifs, False, check_paths, base_dir)
    if aln is not None and cifs is not None:
        rep.err(where, "Cannot specify both 'template_alignment_file_path' and "
                "'template_cif_paths'")
    if cif_ids is not None:
        if cifs is None:
            rep.err(where, "'template_cif_chain_ids' can only be specified when "
                    "'template_cif_paths' is provided")
        elif len(_as_list(cif_ids)) != len(_as_list(cifs)):
            rep.err(where, "Length mismatch - %d CIF files but %d chain IDs specified"
                    % (len(_as_list(cifs)), len(_as_list(cif_ids))))
    if chain.get("template_entry_chain_ids") is not None:
        rep.note(where, "template_entry_chain_ids is normally auto-populated from the alignment")
    if (aln is not None or cifs is not None) and mt not in (None, "protein"):
        rep.warn(where, "templates are supported/tested for protein chains only")
    return mt, ids


def validate_query(rep: Report, name: str, q, check_paths: bool, base_dir: str) -> None:
    where = "queries[%s]" % name
    if not QUERY_KEY_RE.match(name):
        (rep.err if "/" in name or not name else rep.warn)(
            where, "query key becomes a directory and file prefix; use letters, digits, . _ -")
    if not isinstance(q, dict):
        rep.err(where, "query must be an object")
        return
    for k in q:
        if k not in QUERY_KEYS:
            rep.warn(where, "unknown query key %r is SILENTLY IGNORED by v0.5.0 (Query does not "
                     "forbid extras) - typo?" % k)
    if "query_name" in q:
        rep.note(where, "query_name is overwritten by the query key")
    for k in MISPLACED_QUERY_FLAGS:
        if k in q and not isinstance(q[k], bool):
            rep.warn(where, "%s should be a JSON boolean" % k)
    if q.get("use_msas") is False:
        rep.note(where, "use_msas=false gives EMPTY MSA features; upstream recommends the "
                 "query-only (dummy) MSA instead: omit MSA paths and run --use-msa-server false")
    if q.get("covalent_bonds") is not None:
        rep.warn(where, "covalent_bonds is accepted by the schema but NOT consumed anywhere in "
                 "v0.5.0 - the bonds are silently ignored")
    chains = q.get("chains")
    if not isinstance(chains, list) or not chains:
        rep.err(where, "'chains' must be a non-empty list (an empty list passes the schema, "
                "then the query fails at build)")
        return
    seen: Dict[str, int] = {}
    by_id: Dict[str, Tuple[str, dict]] = {}
    tokens = kit = 0
    unknown: List[str] = []
    for i, ch in enumerate(chains):
        mt, ids = validate_chain(rep, "%s.chains[%d]" % (where, i), ch, check_paths, base_dir)
        for cid in ids:
            if cid in seen:
                rep.err(where, "duplicate chain id %r (chains %d and %d): not rejected by the "
                        "schema; the builder silently merges both into one chain"
                        % (cid, seen[cid], i))
            seen[cid] = i
            if mt:
                by_id[cid] = (mt, ch)
        if mt and isinstance(ch, dict):
            t, unk = _estimate_chain_tokens(mt, ch)
            tokens += t * max(len(ids), 1)
            kit += _kit_polymer_tokens(ch)
            unknown += unk
    pc = q.get("pocket_constraint")
    if pc is not None:
        pw = where + ".pocket_constraint"
        if not isinstance(pc, dict):
            rep.err(pw, "must be ONE object (one constrained ligand per query)")
        else:
            for k in pc:
                if k not in POCKET_KEYS:
                    rep.err(pw, "unknown key %r (PocketConstraint forbids extra keys)" % k)
            lig = pc.get("ligand_chain_id")
            if not isinstance(lig, str):
                rep.err(pw, "ligand_chain_id (string) is required")
            elif lig not in by_id or by_id[lig][0] != "ligand":
                rep.err(pw, "pocket constraint ligand_chain_id %r does not match any ligand chain"
                        % lig)
            res = pc.get("pocket_residues")
            if not isinstance(res, list) or not res:
                rep.err(pw, "pocket_residues must contain at least one residue")
            else:
                for r in res:
                    if isinstance(r, dict):
                        r = [r.get("chain_id"), r.get("residue_id")]
                    if not isinstance(r, list) or len(r) != 2:
                        rep.err(pw, "pocket residue %r must be [chain_id, residue_id]" % (r,))
                        continue
                    cid, rid = r
                    try:
                        rid = int(rid)
                    except (TypeError, ValueError):
                        rep.err(pw, "residue_id %r is not an integer" % (rid,))
                        continue
                    if cid not in by_id:
                        rep.err(pw, "residue chain %r is not in this query" % (cid,))
                        continue
                    rmt, rch = by_id[cid]
                    n = len(rch.get("sequence") or "") if rmt in POLYMERS else 1
                    if not 1 <= rid <= n:
                        rep.err(pw, "residue %s:%d outside 1..%d (runtime: 'Pocket constraint "
                                "residue ... does not match any atoms')" % (cid, rid, n))
            md = pc.get("max_distance", 4.0)
            if isinstance(md, bool) or not isinstance(md, (int, float)) or md <= 0:
                rep.err(pw, "max_distance must be a positive number (default 4.0)")
    codes = sorted(set(unknown) - {"SMILES"})
    if codes:
        rep.note(where, "code(s) %s are not in this helper's table, so it cannot confirm they "
                 "exist in the CCD (an unknown code fails the query at build)" % ",".join(codes))
    rep.tokens[name] = {"tokens_est": tokens, "kit_polymer_tokens": kit,
                        "unknown_codes": sorted(set(unknown))}


def validate_doc(doc, check_paths: bool = True, base_dir: str = ".") -> Report:
    rep = Report()
    if not isinstance(doc, dict):
        rep.err("top", "the file must be a JSON object {\"queries\": {...}}")
        return rep
    for k in doc:
        if k not in TOP_KEYS:
            rep.warn("top", "unknown top-level key %r is ignored" % k)
    if "seeds" in doc:
        rep.warn("top", "'seeds' in the input is accepted but NOT used for inference; set seeds "
                 "with --num-model-seeds or the runner YAML")
    qs = doc.get("queries")
    if not isinstance(qs, dict):
        rep.err("top", "'queries' must be an object mapping query names to queries")
        return rep
    if not qs:
        rep.err("top", "'queries' is empty")
    for name, q in qs.items():
        validate_query(rep, str(name), q, check_paths, base_dir)
    return rep


def print_report(rep: Report, label: str, as_json: bool, strict: bool, stream) -> int:
    rc = 1 if rep.errors or (strict and rep.warnings) else 0
    if as_json:
        json.dump({"file": label, "schema": PIN, "ok": rc == 0, "errors": rep.errors,
                   "warnings": rep.warnings, "notes": rep.notes, "tokens": rep.tokens},
                  stream, indent=2)
        stream.write("\n")
        return rc
    for tag, items in (("ERROR", rep.errors), ("WARN", rep.warnings), ("NOTE", rep.notes)):
        for m in items:
            stream.write("%-5s %s\n" % (tag, m))
    for name, t in rep.tokens.items():
        line = "TOKENS %s: ~%d model tokens (kit polymer tokens %d)" % (
            name, t["tokens_est"], t["kit_polymer_tokens"])
        if t["unknown_codes"]:
            line += " + unknown size for %s (lower bound)" % ",".join(t["unknown_codes"])
        flags = []
        if t["kit_polymer_tokens"] > KIT_EXACT_GRAPH_CAP:
            flags.append("> %d: kit `exact` runs eager (no CUDA graph)" % KIT_EXACT_GRAPH_CAP)
        if t["kit_polymer_tokens"] >= KIT_BIG_GATE:
            flags.append(">= %d: kit `big` engages row blocks/host streaming" % KIT_BIG_GATE)
        stream.write(line + ("; " + "; ".join(flags) if flags else "") + "\n")
    if len(rep.tokens) > 1:
        big = max(rep.tokens.items(), key=lambda kv: kv[1]["tokens_est"])
        stream.write("BATCH %d queries, one forward pass each; largest %s (~%d tokens) sets "
                     "peak memory\n" % (len(rep.tokens), big[0], big[1]["tokens_est"]))
    stream.write("RESULT %s: %s (%d errors, %d warnings)%s\n" % (
        label, "OK" if rc == 0 else "INVALID", len(rep.errors), len(rep.warnings),
        " [--strict]" if strict and rep.warnings and not rep.errors else ""))
    return rc


# ---------------------------------------------------------------- building
def dump_compact(obj, ind: int = 0) -> str:
    """json.dumps(indent=2) but short scalar lists stay on one line (chain_ids, residues)."""
    pad = "  " * ind
    if isinstance(obj, dict) and obj:
        body = ",\n".join("%s  %s: %s" % (pad, json.dumps(k), dump_compact(v, ind + 1))
                          for k, v in obj.items())
        return "{\n%s\n%s}" % (body, pad)
    if isinstance(obj, list) and obj:
        flat = json.dumps(obj)
        if len(flat) <= 100 and not any(isinstance(x, dict) for x in obj):
            return flat
        body = ",\n".join("%s  %s" % (pad, dump_compact(v, ind + 1)) for v in obj)
        return "[\n%s\n%s]" % (body, pad)
    return json.dumps(obj)


class UsageError(Exception):
    pass


def chain_id_stream(used):
    letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    for a in letters:
        if a not in used:
            yield a
    for a in letters:
        for b in letters:
            if a + b not in used:
                yield a + b


def split_copies(value: str) -> Tuple[str, int]:
    head, sep, tail = value.rpartition(":")
    if sep and tail.isdigit() and head:
        n = int(tail)
        if n < 1:
            raise UsageError("copies must be >= 1 in %r" % value)
        return head, n
    return value, 1


def read_sequence(value: str) -> str:
    if value.startswith("@"):
        path = value[1:]
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            raise UsageError("cannot read sequence file %s: %s" % (path, exc))
        out, seen_header = [], False
        for ln in lines:
            if ln.startswith(">"):
                if seen_header and out:
                    break
                seen_header = True
                continue
            out.append(ln.strip())
        value = "".join(out)
    return re.sub(r"\s+", "", value)


def make_chain(kind: str, value, copies: int, extra: Optional[dict] = None) -> dict:
    kind = kind.lower().replace("-", "_")
    if kind in ("protein", "rna", "dna"):
        seq = read_sequence(str(value))
        if seq != seq.upper():
            sys.stderr.write("make_query: upper-cased a %s sequence (OpenFold3 does not)\n" % kind)
        chain = {"molecule_type": kind, "sequence": seq.upper()}
    elif kind in ("smiles", "ligand_smiles"):
        chain = {"molecule_type": "ligand", "smiles": str(value).strip()}
    elif kind in ("ccd", "ligand_ccd", "ion"):
        codes = [str(v).strip().upper() for v in value] if isinstance(value, list) \
            else str(value).strip().upper()
        chain = {"molecule_type": "ligand", "ccd_codes": codes}
    else:
        raise UsageError("unknown molecule kind %r (protein|rna|dna|smiles|ccd)" % kind)
    chain["_copies"] = copies
    if extra:
        chain.update(extra)
    return chain


def assign_chain_ids(chains: List[dict]) -> None:
    used = set()
    for ch in chains:
        if "chain_ids" in ch:
            used.update(_as_list(ch["chain_ids"]))
    gen = chain_id_stream(used)
    for ch in chains:
        copies = ch.pop("_copies", 1)
        if "chain_ids" not in ch:
            ids = [next(gen) for _ in range(copies)]
            ch["chain_ids"] = ids
            used.update(ids)


def order_chain(ch: dict) -> dict:
    first = ["molecule_type", "chain_ids", "description", "sequence", "non_canonical_residues",
             "smiles", "ccd_codes"]
    out = {k: ch[k] for k in first if k in ch}
    out.update({k: v for k, v in ch.items() if k not in out})
    return out


def query_from_parts(chains: List[dict], msa_dir: Optional[str], flags: dict,
                     pocket: Optional[dict]) -> dict:
    assign_chain_ids(chains)
    if msa_dir:
        for ch in chains:
            if ch["molecule_type"] in MSA_MOLTYPES and "main_msa_file_paths" not in ch:
                ch["main_msa_file_paths"] = os.path.abspath(
                    os.path.join(msa_dir, _as_list(ch["chain_ids"])[0]))
    q = {"chains": [order_chain(c) for c in chains]}
    q.update({k: v for k, v in flags.items() if v is not None})
    if pocket:
        q["pocket_constraint"] = pocket
    return q


def parse_pocket(lig: Optional[str], residues: Optional[str], dist: Optional[float]):
    if not lig and not residues:
        return None
    if not (lig and residues):
        raise UsageError("--pocket-ligand and --pocket-residues go together")
    res = []
    for item in residues.split(","):
        cid, sep, num = item.strip().partition(":")
        if not sep or not num.strip().isdigit():
            raise UsageError("pocket residue %r must look like A:42" % item)
        res.append([cid, int(num)])
    pc = {"ligand_chain_id": lig, "pocket_residues": res}
    if dist is not None:
        pc["max_distance"] = dist
    return pc


SPEC_VALUE_KEYS = ("type", "molecule_type", "sequence", "smiles", "ccd", "ccd_codes", "copies")


def _copies(value, where: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise UsageError("%s: copies must be an integer, got %r" % (where, value))
    if n < 1:
        raise UsageError("%s: copies must be >= 1" % where)
    return n


def queries_from_spec(path: str) -> Dict[str, dict]:
    """JSON spec: {"queries": [{"name", "chains": [{"type", "sequence"|"smiles"|"ccd",
    "copies"?, other chain fields?}], "msa_dir"?, "use_*_msas"?, "pocket_constraint"?}]}
    (or one such entry). TSV rows: query, type, value[, copies[, chain ids a,b]]."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise UsageError("cannot read spec %s: %s" % (path, exc))
    out: Dict[str, dict] = {}
    if path.lower().endswith(".json"):
        try:
            spec = json.loads(text)
        except ValueError as exc:
            raise UsageError("spec %s is not JSON: %s" % (path, exc))
        items = spec.get("queries") if isinstance(spec, dict) and "queries" in spec else [spec]
        if not isinstance(items, list):
            raise UsageError("JSON spec: 'queries' must be a LIST of {name, chains}")
        for item in items:
            if not isinstance(item, dict) or "name" not in item \
                    or not isinstance(item.get("chains"), list):
                raise UsageError("JSON spec entries need 'name' and a 'chains' list")
            name = str(item["name"])
            if name in out:
                raise UsageError("JSON spec: duplicate query name %r" % name)
            chains = []
            for c in item["chains"]:
                if not isinstance(c, dict):
                    raise UsageError("spec chain %r must be an object" % (c,))
                kind = c.get("type") or c.get("molecule_type") or ""
                if kind == "ligand":
                    kind = "smiles" if "smiles" in c else "ccd"
                value = c.get("sequence") or c.get("smiles") or c.get("ccd") or c.get("ccd_codes")
                if value is None:
                    raise UsageError("spec chain %r has no sequence/smiles/ccd" % (c,))
                # every other key is passed through; validation reports unknown ones
                extra = {k: v for k, v in c.items() if k not in SPEC_VALUE_KEYS}
                chains.append(make_chain(kind, value, _copies(c.get("copies", 1), name), extra))
            flags = {k: item.get(k) for k in MISPLACED_QUERY_FLAGS}
            out[name] = query_from_parts(chains, item.get("msa_dir"), flags,
                                         item.get("pocket_constraint"))
        return out
    grouped: Dict[str, List[dict]] = {}
    first_row = True
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = [c.strip() for c in line.split("\t")]
        if first_row and cols[0].lower() == "query":       # optional header row
            first_row = False
            continue
        first_row = False
        if len(cols) < 3:
            raise UsageError("%s:%d: need query, type, value (tab-separated)" % (path, lineno))
        where = "%s:%d" % (path, lineno)
        copies = _copies(cols[3], where) if len(cols) > 3 and cols[3] else 1
        extra = {"chain_ids": cols[4].split(",")} if len(cols) > 4 and cols[4] else None
        grouped.setdefault(cols[0], []).append(make_chain(cols[1], cols[2], copies, extra))
    if not grouped:
        raise UsageError("spec %s holds no rows" % path)
    for name, chains in grouped.items():
        out[name] = query_from_parts(chains, None, {}, None)
    return out


class Entry(argparse.Action):
    """Keep --protein/--rna/--dna/--ligand-* in command-line order (chain ids follow it)."""

    def __call__(self, parser, ns, values, option_string=None):
        entries = getattr(ns, "entries", None) or []
        entries.append((self.dest, values))
        ns.entries = entries


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="make_query.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Build or validate an OpenFold3 v0.5.0 query JSON (convenience helper; the "
                    "pinned Pydantic model is authoritative).",
        epilog="""examples (templates - adapt paths):
  make_query.py --name ubq --protein @ubiquitin.fasta          # JSON to stdout
  make_query.py --name ras_gtp --protein @hras.fasta --ligand-ccd GTP --ligand-ccd MG --out ras.json
  make_query.py --name dimer --protein SEQ:2 --ligand-smiles 'c1ccccc1' --out q.json
  make_query.py --name lig --protein @t4l.fasta --ligand-smiles c1ccccc1 \\
      --pocket-ligand B --pocket-residues A:84,A:99,A:153 --out q.json
  make_query.py --name het --protein @a.fasta --protein @b.fasta --msa-dir /abs/msas --out q.json
  make_query.py --spec batch.tsv --out batch.json
  make_query.py --validate q.json [--strict] [--no-path-check] [--json]
Chain ids are assigned A, B, C ... in command-line order (copies take consecutive ids).
SEQ may be @file (first FASTA record, or plain text); sequences are upper-cased. A trailing
:N means N copies (append :1 to a SMILES that itself ends in :digits). --msa-dir DIR maps
each protein/RNA entry to DIR/<its first chain id>.
TSV spec rows: query<TAB>type<TAB>value[<TAB>copies[<TAB>chain ids a,b]]; rows sharing a query
name form one query; type = protein|rna|dna|smiles|ccd; optional header row "query ...".
JSON spec: {"queries": [{"name": "q1", "chains": [{"type": "protein", "sequence": "...",
"copies": 2}, {"type": "ccd", "ccd": "ATP"}], "msa_dir": "/abs", "use_paired_msas": false}]};
other chain fields (chain_ids, non_canonical_residues, cyclic, ...) are passed through.
Nothing is written without --out; an existing --out needs --force.
Exit codes: 0 ok, 1 invalid query, 2 usage error.""")
    g = p.add_argument_group("build")
    g.add_argument("--name", help="query key (becomes the output sub-directory and file prefix)")
    for opt, dest, hlp in (("--protein", "protein", "protein sequence[:copies]"),
                           ("--rna", "rna", "RNA sequence[:copies]"),
                           ("--dna", "dna", "DNA sequence (one strand)[:copies]"),
                           ("--ligand-smiles", "smiles", "ligand SMILES[:copies]"),
                           ("--ligand-ccd", "ccd", "ligand/ion CCD code[:copies], e.g. ATP, MG:2")):
        g.add_argument(opt, dest=dest, action=Entry, metavar="VALUE", help=hlp)
    g.add_argument("--msa-dir", help="precomputed MSAs: DIR/<chain id>/ per protein/RNA entry")
    g.add_argument("--no-msas", action="store_true", help="query-level use_msas=false "
                   "(empty MSA features; discouraged upstream)")
    g.add_argument("--no-main-msas", action="store_true", help="query-level use_main_msas=false")
    g.add_argument("--no-paired-msas", action="store_true",
                   help="query-level use_paired_msas=false")
    g.add_argument("--pocket-ligand", help="ligand chain id for pocket_constraint")
    g.add_argument("--pocket-residues", help="comma list CHAIN:RESNUM (1-based), e.g. A:84,A:99")
    g.add_argument("--pocket-max-distance", type=float, help="Angstrom, default 4.0")
    g.add_argument("--spec", help="build from a JSON or TSV spec instead of flags")
    g.add_argument("--out", help="write the JSON here (otherwise print to stdout)")
    g.add_argument("--force", action="store_true", help="allow overwriting --out")
    v = p.add_argument_group("validate")
    v.add_argument("--validate", metavar="FILE", help="check an existing query JSON")
    v.add_argument("--strict", action="store_true",
                   help="treat warnings as errors (also when building)")
    v.add_argument("--no-path-check", action="store_true",
                   help="do not require MSA/template paths to exist on this machine and skip "
                        "MSA file-name checks (also when building)")
    v.add_argument("--json", action="store_true", help="machine-readable validation report")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    entries = getattr(args, "entries", None) or []
    try:
        flag_build = [o for o, v in (("--msa-dir", args.msa_dir), ("--no-msas", args.no_msas),
                                     ("--no-main-msas", args.no_main_msas),
                                     ("--no-paired-msas", args.no_paired_msas),
                                     ("--pocket-ligand", args.pocket_ligand),
                                     ("--pocket-residues", args.pocket_residues),
                                     ("--pocket-max-distance", args.pocket_max_distance))
                      if v]
        if args.validate:
            if entries or args.spec or args.name or args.out or flag_build:
                raise UsageError("--validate cannot be combined with build options")
            try:
                with open(args.validate, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except OSError as exc:
                raise UsageError("cannot read %s: %s" % (args.validate, exc))
            except ValueError as exc:
                doc, bad_json = None, exc
            if doc is None:
                rep = Report()
                rep.err("top", "not valid JSON: %s" % bad_json)
            else:
                rep = validate_doc(doc, not args.no_path_check,
                                   os.path.dirname(os.path.abspath(args.validate)))
            return print_report(rep, args.validate, args.json, args.strict, sys.stdout)
        if args.spec:
            if entries or args.name or flag_build:
                raise UsageError("--spec cannot be combined with --name, molecule or query "
                                 "flags (put them in the spec): %s" % " ".join(flag_build))
            queries = queries_from_spec(args.spec)
        else:
            if not args.name:
                raise UsageError("--name is required (or use --spec / --validate); see --help")
            if not entries:
                raise UsageError("give at least one --protein/--rna/--dna/--ligand-* entry")
            chains = []
            for dest, value in entries:
                val, copies = split_copies(value)
                chains.append(make_chain(dest, val, copies))
            flags = {"use_msas": False if args.no_msas else None,
                     "use_main_msas": False if args.no_main_msas else None,
                     "use_paired_msas": False if args.no_paired_msas else None}
            pocket = parse_pocket(args.pocket_ligand, args.pocket_residues,
                                  args.pocket_max_distance)
            queries = {args.name: query_from_parts(chains, args.msa_dir, flags, pocket)}
    except UsageError as exc:
        sys.stderr.write("make_query: usage error: %s\n" % exc)
        return 2
    doc = {"queries": queries}
    rep = validate_doc(doc, not args.no_path_check, os.getcwd())
    rc = print_report(rep, args.out or "<stdout>", False, args.strict, sys.stderr)
    for name, q in queries.items():
        for ch in q["chains"]:
            what = str(ch.get("sequence") or ch.get("smiles") or ch.get("ccd_codes"))
            sys.stderr.write("CHAIN %s %s %s: %s\n" % (name, ",".join(_as_list(ch["chain_ids"])),
                             ch["molecule_type"], (what[:40] + "...") if len(what) > 43 else what))
    if rc != 0:
        sys.stderr.write("make_query: not written (fix the errors above)\n")
        return rc
    text = dump_compact(doc) + "\n"
    if not args.out:
        sys.stdout.write(text)
        return 0
    if os.path.exists(args.out) and not args.force:
        sys.stderr.write("make_query: usage error: %s exists (use --force)\n" % args.out)
        return 2
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        sys.stderr.write("make_query: usage error: cannot write %s: %s\n" % (args.out, exc))
        return 2
    sys.stderr.write("make_query: wrote %s\n" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
