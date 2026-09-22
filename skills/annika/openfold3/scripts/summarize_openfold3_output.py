#!/usr/bin/env python3
"""summarize_openfold3_output.py - read-only summary and completeness check of an OpenFold3 output tree.

Works on trees written by stock `run_openfold predict` (OpenFold3 v0.5.0 and 0.4.1 share the layout) and by the
Anthropic kits' `run.sh pred` (same layout, plus `_tp/`, `tp_predict.yml` and `*_structure_first.json` under
`--n_gpu`). Layout grounded in openfold-3@v0.5.0 (commit c4771653):
  openfold3/core/runners/writer.py          <out>/<query>/seed_<s>/<query>_seed_<s>_sample_<k>_{model.<fmt>,
                                            confidences.<json|npz>, confidences_aggregated.json}; summary.txt
  openfold3/core/utils/callbacks.py         <out>/<query>/seed_<s>/timing.json {"runtime_s"}; inference_query_set.json
  openfold3/entry_points/experiment_runner.py   experiment_config.json, model_config.json, msas/
  openfold3/core/metrics/sample_ranking.py  sample_ranking_score = 0.8 ipTM + 0.2 pTM + 0.5 disorder - 100 has_clash
                                            (weights: model_config.json confidence.sample_ranking.full_complex)

What it does (never writes, never imports OpenFold3, stdlib only, Python >= 3.9):
  * discovers every query directory (a directory holding seed_<int>/ subdirectories) under OUTPUT_DIR, so it
    accepts a run's --output-dir, a single query directory (then only that query is expected), or a parent
    holding several runs (kept apart);
  * parses every *_confidences_aggregated.json and prints one ranked table per query (all seeds pooled, ranked by
    sample_ranking_score as upstream defines it), plus timing.json runtimes;
  * flags missing / structure-only / extra files, recomputes the ranking formula (with the weights recorded in
    model_config.json when present) as a sanity check, reads summary.txt, experiment_config.json,
    model_config.json, inference_query_set.json and msas/ when present;
    --check-coords also rejects model files with nan/inf coordinates (the kit's counting rule);
  * completeness: queries x seeds x samples. --expect-samples / --expect-seeds / --expect-queries (or
    --query-json) set the expectation; without them, samples per seed default to the value recorded in
    model_config.json and queries to inference_query_set.json. Seeds are NOT inferred from the recorded config:
    `--num-model-seeds N` draws seeds that experiment_config.json / inference_query_set.json do not record.
    Without --expect-seeds the grand total is not checked (the verdict says so).

Usage:
  python3 summarize_openfold3_output.py OUT_DIR
  python3 summarize_openfold3_output.py OUT_DIR --expect-samples 5 --expect-seeds 1 --chains
  python3 summarize_openfold3_output.py OUT_DIR --query-json query.json --json > summary.json

Exit codes: 0 no problems found | 1 incomplete or problems found (missing/structure-only files, expectation
not met, no predictions) | 2 usage error (OUT_DIR missing, unreadable --query-json, bad option value).
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
import sys

SEED_DIR_RE = re.compile(r"^seed_(-?\d+)$")
SAMPLE_REST_RE = re.compile(r"^(\d+)_(.+)$")
SKIP_DIRS = {"msas", "_tp", "logs", "__pycache__"}
MODEL_SUFFIXES = ("model.cif", "model.cif.gz", "model.pdb")
FULL_CONF_SUFFIXES = ("confidences.json", "confidences.npz")
RUN_FILES = ("experiment_config.json", "model_config.json", "inference_query_set.json", "summary.txt")
RANK_WEIGHTS = {"iptm": 0.8, "ptm": 0.2, "disorder": 0.5, "has_clash": -100.0}
RANK_TOL = 5e-4
AGG_SCALARS = ("sample_ranking_score", "ptm", "iptm", "avg_plddt", "gpde", "disorder", "has_clash")


# ------------------------------------------------------------------------------------------------ helpers
def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def num(x):
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    return None


def is_nan(x):
    return isinstance(x, float) and math.isnan(x)


def fmt(x, nd=4):
    if x is None:
        return "-"
    if is_nan(x):
        return "nan"
    return f"{x:.{nd}f}"


def sort_key_int(s):
    try:
        return (0, int(s))
    except (TypeError, ValueError):
        return (1, str(s))


def bfactor_all_zero(path, max_atoms=400):
    """True when the first atoms of a structure file all carry B-factor 0.00 (the kit's structure-only
    placeholder: pLDDT is written into the B-factor column only after the confidence heads)."""
    opener = gzip.open if path.endswith(".gz") else open
    vals = []
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
            if path.endswith(".pdb"):
                for line in fh:
                    if line.startswith(("ATOM", "HETATM")):
                        vals.append(float(line[60:66]))
                        if len(vals) >= max_atoms:
                            break
            else:
                cols, in_loop, col = [], False, None
                for line in fh:
                    s = line.strip()
                    if s.startswith("_atom_site."):
                        in_loop = True
                        cols.append(s.split()[0])
                        continue
                    if in_loop and cols and col is None:
                        if "_atom_site.B_iso_or_equiv" not in cols:
                            return None
                        col = cols.index("_atom_site.B_iso_or_equiv")
                    if col is not None:
                        if not s or s.startswith(("#", "loop_", "_")):
                            break
                        parts = s.split()
                        if len(parts) > col:
                            vals.append(float(parts[col]))
                        if len(vals) >= max_atoms:
                            break
    except (OSError, ValueError):
        return None
    if not vals:
        return None
    return all(v == 0.0 for v in vals)


def coordinate_defect(path):
    """None when every atom coordinate parses as a finite float; else 'nan_coordinates' or 'unreadable:<Exc>'.
    Mirrors the kit's rule (a model file with a nan/inf coordinate is not counted as a structure)."""
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
            if path.endswith(".pdb"):
                for line in fh:
                    if line.startswith(("ATOM", "HETATM")):
                        for a, b in ((30, 38), (38, 46), (46, 54)):
                            if not math.isfinite(float(line[a:b])):
                                return "nan_coordinates"
                return None
            cols, idx = [], None
            for line in fh:
                s = line.strip()
                if s.startswith("_atom_site."):
                    cols.append(s.split()[0])
                    continue
                if cols and idx is None:
                    try:
                        idx = [cols.index(f"_atom_site.Cartn_{c}") for c in "xyz"]
                    except ValueError:
                        return None
                if idx is not None:
                    if not s or s.startswith(("#", "loop_", "_")):
                        break
                    parts = s.split()
                    for i in idx:
                        try:
                            if not math.isfinite(float(parts[i])):
                                return "nan_coordinates"
                        except (IndexError, ValueError):
                            return "nan_coordinates"
    except (OSError, ValueError) as exc:
        return f"unreadable:{type(exc).__name__}"
    return None


# ------------------------------------------------------------------------------------------------ discovery
def has_seed_children(path):
    try:
        return any(SEED_DIR_RE.match(d) and os.path.isdir(os.path.join(path, d)) for d in os.listdir(path))
    except OSError:
        return False


def find_query_dirs(root):
    """Directories that hold seed_<int>/ subdirectories. msas/, _tp/ (kit rank copies) and logs/ are not entered
    unless they hold seed_<int>/ themselves (a query that happens to be named like them)."""
    found = []
    for cur, dirs, _files in os.walk(root):
        if any(SEED_DIR_RE.match(d) for d in dirs):
            found.append(cur)
        dirs[:] = sorted(d for d in dirs if not SEED_DIR_RE.match(d)
                         and (d not in SKIP_DIRS or has_seed_children(os.path.join(cur, d))))
    return sorted(found)


def scan_seed_dir(qname, seed, sdir):
    """Classify every file of one seed directory."""
    prefix = f"{qname}_seed_{seed}_"
    samples, extras, per_seed = {}, [], []
    timing = None
    for f in sorted(os.listdir(sdir)):
        p = os.path.join(sdir, f)
        if os.path.isdir(p):
            extras.append(f + "/")
            continue
        if f == "timing.json":
            d, err = load_json(p)
            timing = num(d.get("runtime_s")) if isinstance(d, dict) else None
            if err:
                extras.append(f + " (unreadable)")
            continue
        if f in (f"{qname}_seed_{seed}_batch.pt", f"{qname}_seed_{seed}_latent_output.pt"):
            per_seed.append(f)
            continue
        if not f.startswith(prefix + "sample_"):
            extras.append(f)
            continue
        m = SAMPLE_REST_RE.match(f[len(prefix + "sample_"):])
        if not m:
            extras.append(f)
            continue
        k, kind = int(m.group(1)), m.group(2)
        rec = samples.setdefault(k, {"sample": k, "model": [], "aggregated": None, "full": [], "sidecar": None})
        if kind in MODEL_SUFFIXES:
            rec["model"].append(f)
        elif kind == "confidences_aggregated.json":
            rec["aggregated"] = f
        elif kind in FULL_CONF_SUFFIXES:
            rec["full"].append(f)
        elif kind == "structure_first.json":
            rec["sidecar"] = f
        else:
            extras.append(f)
    return samples, extras, per_seed, timing


def read_run_files(run_dir):
    """Run-level files written at the top of an --output-dir."""
    info = {"present": [], "summary": None, "fallback_summaries": [], "recorded": {}, "msas": None, "kit": {},
            "query_names": None, "single_sequence_chains": [], "notes": []}
    for name in RUN_FILES:
        if os.path.isfile(os.path.join(run_dir, name)):
            info["present"].append(name)
    try:
        top = sorted(os.listdir(run_dir))
    except OSError:
        top = []
    info["fallback_summaries"] = [f for f in top if re.match(r"^fallback_summary_rank_\d+\.txt$", f)]
    ld = os.path.join(run_dir, "logs")
    info["error_logs"] = sorted(os.path.join("logs", f) for f in (os.listdir(ld) if os.path.isdir(ld) else [])
                                if re.match(r"^predict_err_rank\d+\.log$", f))

    sp = os.path.join(run_dir, "summary.txt")
    if os.path.isfile(sp):
        try:
            with open(sp, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
        except OSError:
            txt = ""
        s = {"status": None, "processed": None, "successful": None, "failed": None, "failed_queries": []}
        m = re.search(r"PREDICTION SUMMARY \(([^)]*)\)", txt)
        s["status"] = m.group(1).strip() if m else None
        for key, pat in (("processed", r"Total Queries Processed:\s*(\d+)"),
                         ("successful", r"Successful Queries:\s*(\d+)"),
                         ("failed", r"Failed Queries:\s*(\d+)")):
            m = re.search(pat, txt)
            s[key] = int(m.group(1)) if m else None
        m = re.search(r"\nFailed Queries:\s*([^\n]+)", txt)
        if m and not re.match(r"^\d+\s*$", m.group(1)):
            s["failed_queries"] = [q.strip() for q in m.group(1).split(",") if q.strip()]
        info["summary"] = s

    ec, _ = load_json(os.path.join(run_dir, "experiment_config.json"))
    if isinstance(ec, dict):
        ow = ec.get("output_writer_settings") or {}
        es = ec.get("experiment_settings") or {}
        info["recorded"].update({
            "structure_format": ow.get("structure_format"),
            "write_full_confidence_scores": ow.get("write_full_confidence_scores"),
            "full_confidence_output_format": ow.get("full_confidence_output_format"),
            "use_msa_server": es.get("use_msa_server"),
            "use_templates": es.get("use_templates"),
            "skip_existing": es.get("skip_existing"),
            "seeds_recorded": es.get("seeds"),
            "checkpoint_name": ec.get("inference_ckpt_name"),
            "checkpoint_file": os.path.basename(str(ec.get("inference_ckpt_path") or "")) or None,
        })
    mc, _ = load_json(os.path.join(run_dir, "model_config.json"))
    if isinstance(mc, dict):
        try:
            info["recorded"]["samples_per_seed"] = int(mc["architecture"]["shared"]["diffusion"]["no_full_rollout_samples"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            fc = mc["confidence"]["sample_ranking"]["full_complex"]
            w = {"iptm": num(fc["iptm_weight"]), "ptm": num(fc["ptm_weight"]),
                 "disorder": num(fc["disorder_weight"]), "has_clash": num(fc["has_clash_weight"])}
            if all(v is not None for v in w.values()):
                w["has_clash"] = -w["has_clash"]  # upstream subtracts has_clash_weight * has_clash
                info["recorded"]["ranking_weights"] = w
        except (KeyError, TypeError):
            pass
    iq, _ = load_json(os.path.join(run_dir, "inference_query_set.json"))
    if isinstance(iq, dict) and isinstance(iq.get("queries"), dict):
        info["query_names"] = sorted(iq["queries"])
        for qn, q in iq["queries"].items():
            for ch in (q or {}).get("chains") or []:
                paths = (ch or {}).get("main_msa_file_paths") or []
                if any("/dummy/" in str(p).replace("\\", "/") for p in paths):
                    info["single_sequence_chains"].append(f"{qn}:{','.join(map(str, ch.get('chain_ids') or []))}")

    md = os.path.join(run_dir, "msas")
    if os.path.isdir(md):
        # msas/<msa-run>/{main,paired,template,mappings,dummy}; raw ColabFold records go to msas/raw/<msa-run>/
        runs = sorted(d for d in os.listdir(md) if d != "raw" and os.path.isdir(os.path.join(md, d)))
        kinds = {"raw"} if os.path.isdir(os.path.join(md, "raw")) else set()
        for r in runs:
            for sub in ("main", "paired", "template", "mappings", "dummy", "raw"):
                if os.path.isdir(os.path.join(md, r, sub)):
                    kinds.add(sub)
        info["msas"] = {"run_dirs": len(runs), "contents": sorted(kinds)}

    tp = os.path.join(run_dir, "_tp")
    if os.path.isdir(tp):
        info["kit"]["rank_logs"] = sorted(f for f in os.listdir(tp) if re.match(r"^rank\d+\.log$", f))
    if os.path.isfile(os.path.join(run_dir, "tp_predict.yml")):
        info["kit"]["tp_predict_yml"] = True
    return info


# ------------------------------------------------------------------------------------------------ analysis
def analyse_query(qdir, run_info, args):
    qname = os.path.basename(os.path.normpath(qdir))
    problems, warnings = [], []
    seeds = {}
    rows = []
    rec = run_info["recorded"]
    full_expected = rec.get("write_full_confidence_scores")
    fmt_expected = rec.get("structure_format")
    weights = rec.get("ranking_weights") or RANK_WEIGHTS
    formula = " ".join(f"{'+' if w >= 0 else '-'} {abs(w):g} {k}" for k, w in weights.items()).lstrip("+ ")
    sidecars = 0
    for d in sorted(os.listdir(qdir), key=lambda x: sort_key_int(x[5:]) if x.startswith("seed_") else (2, x)):
        m = SEED_DIR_RE.match(d)
        p = os.path.join(qdir, d)
        if not os.path.isdir(p):
            if not d.startswith("."):
                warnings.append(f"extra file in query dir: {d}")
            continue
        if not m:
            if d not in SKIP_DIRS:
                warnings.append(f"extra directory in query dir: {d}/")
            continue
        seed = m.group(1)
        samples, extras, per_seed, timing = scan_seed_dir(qname, seed, p)
        seeds[seed] = {"timing_s": timing, "samples": sorted(samples), "extra_files": extras, "per_seed_files": per_seed}
        foreign = sorted({mm.group(1) for mm in (re.match(rf"^(.+)_seed_{re.escape(seed)}_sample_\d+_", e) for e in extras) if mm})
        if foreign:
            problems.append(f"seed_{seed}: sample files named for query {foreign} inside directory '{qname}' "
                            "(renamed or moved directory? upstream names both after the query key)")
        if extras:
            shown = ", ".join(extras[:5]) + (f" ... {len(extras) - 5} more" if len(extras) > 5 else "")
            warnings.append(f"seed_{seed}: {len(extras)} extra/unrecognised file(s): {shown}")
        if timing is None:
            warnings.append(f"seed_{seed}: timing.json missing or unreadable")
        if not samples:
            problems.append(f"seed_{seed}: no sample files for query '{qname}'")
        idx = sorted(samples)
        if idx and idx != list(range(1, len(idx) + 1)):
            warnings.append(f"seed_{seed}: sample indices not contiguous from 1: {idx}")
        for k in idx:
            s = samples[k]
            if s["sidecar"]:
                sidecars += 1
            tag = f"seed_{seed} sample_{k}"
            model = s["model"][0] if s["model"] else None
            if len(s["model"]) > 1:
                warnings.append(f"{tag}: several structure files {s['model']} (mixed runs in one output dir?)")
            if model and fmt_expected and not model.endswith("model." + fmt_expected):
                warnings.append(f"{tag}: {model} does not match recorded structure_format={fmt_expected}")
            row = {"query": qname, "seed": seed, "sample": k, "model": model, "aggregated": s["aggregated"],
                   "full_confidences": s["full"][0] if s["full"] else None, "status": "ok"}
            if s["sidecar"]:
                side, _ = load_json(os.path.join(p, s["sidecar"]))
                if isinstance(side, dict) and side.get("confidence_written") is False:
                    row["status"] = "structure_only"
                    problems.append(f"{tag}: kit sidecar says confidence_written=false (structure-only; B-factor column 0.00)")
            if not model:
                row["status"] = "no_model"
                problems.append(f"{tag}: confidence files present but no *_model.(cif|cif.gz|pdb)")
            elif args.check_coords:
                defect = coordinate_defect(os.path.join(p, model))
                if defect:
                    row["status"] = "bad_coordinates"
                    problems.append(f"{tag}: {model} rejected ({defect})")
            if not s["aggregated"]:
                if row["status"] == "ok":
                    row["status"] = "no_confidence"
                    zero = bfactor_all_zero(os.path.join(p, model)) if model else None
                    hint = " (B-factors all 0.00: structure-only placeholder)" if zero else ""
                    problems.append(f"{tag}: {model} has no _confidences_aggregated.json{hint}")
            else:
                agg, err = load_json(os.path.join(p, s["aggregated"]))
                if err or not isinstance(agg, dict):
                    row["status"] = "bad_confidence"
                    problems.append(f"{tag}: unreadable aggregated confidences ({err})")
                else:
                    for key in AGG_SCALARS:
                        row[key] = num(agg.get(key))
                    missing = [key for key in AGG_SCALARS if key not in agg]
                    if missing:
                        warnings.append(f"{tag}: aggregated JSON lacks {missing}")
                    for key in ("chain_ptm", "chain_pair_iptm", "bespoke_iptm"):
                        row[key] = agg.get(key) if isinstance(agg.get(key), dict) else {}
                    parts = [row.get(k2) for k2 in weights]
                    if all(v is not None and not is_nan(v) for v in parts) and row.get("sample_ranking_score") is not None:
                        recomputed = sum(weights[k2] * row[k2] for k2 in weights)
                        row["ranking_recomputed"] = round(recomputed, 6)
                        if not is_nan(row["sample_ranking_score"]) and abs(recomputed - row["sample_ranking_score"]) > RANK_TOL:
                            warnings.append(f"{tag}: sample_ranking_score {row['sample_ranking_score']} != {formula} "
                                            f"= {recomputed:.6f} (weights differ from the recorded/default ones?)")
                    if any(is_nan(row.get(k2)) for k2 in AGG_SCALARS if row.get(k2) is not None):
                        warnings.append(f"{tag}: NaN in aggregated confidences")
                if not s["full"] and full_expected is not False:
                    warnings.append(f"{tag}: no full *_confidences.(json|npz) (write_full_confidence_scores off?)")
            rows.append(row)

    def rankable(r):
        v = r.get("sample_ranking_score")
        return r["status"] == "ok" and v is not None and not is_nan(v)

    def rkey(r):
        ok = rankable(r)
        return (0 if ok else 1, -(r["sample_ranking_score"] if ok else 0.0), sort_key_int(r["seed"]), r["sample"])

    ranked = sorted(rows, key=rkey)
    n = 0
    for r in ranked:
        if rankable(r):
            n += 1
            r["rank"] = n
        else:
            r["rank"] = None
    top = ranked[0] if ranked and ranked[0].get("rank") == 1 else None
    if top:
        ties = [r for r in ranked[1:] if r.get("sample_ranking_score") == top["sample_ranking_score"]]
        if ties:
            warnings.append(f"top ranking score tied by {len(ties)} other sample(s); order falls back to seed, sample")
    complete = [r for r in rows if r["status"] == "ok"]
    return {"query": qname, "dir": qdir, "seeds": seeds, "n_seeds": len(seeds),
            "samples_per_seed": {s: len(v["samples"]) for s, v in seeds.items()},
            "n_structures": sum(1 for r in rows if r["model"]), "n_complete": len(complete),
            "kit_structure_first_sidecars": sidecars,
            "ranked": ranked, "top": top, "problems": problems, "warnings": warnings}


def completeness(run_info, queries, args, expected_names):
    """queries x seeds x samples, counted as the kit's exit rule counts (a model file with its confidences)."""
    rec = run_info["recorded"]
    exp_samples = args.expect_samples if args.expect_samples is not None else rec.get("samples_per_seed")
    samples_src = "--expect-samples" if args.expect_samples is not None else ("model_config.json" if exp_samples else None)
    exp_seeds = args.expect_seeds
    problems = []
    found_names = sorted(q["query"] for q in queries)
    missing_q = sorted(set(expected_names or []) - set(found_names)) if expected_names is not None else []
    for q in missing_q:
        problems.append(f"query {q}: no output directory")
    for q in queries:
        if exp_seeds is not None and q["n_seeds"] != exp_seeds:
            (problems if q["n_seeds"] < exp_seeds else q["warnings"]).append(
                f"query {q['query']}: {q['n_seeds']} seed dir(s), expected {exp_seeds}")
        if exp_samples:
            for s, n in q["samples_per_seed"].items():
                ok = sum(1 for r in q["ranked"] if r["seed"] == s and r["status"] == "ok")
                if ok < exp_samples:
                    problems.append(f"query {q['query']} seed_{s}: {ok}/{exp_samples} complete samples")
                elif n > exp_samples:
                    q["warnings"].append(f"seed_{s}: {n} samples > expected {exp_samples} (mixed runs in one dir?)")
    n_queries = args.expect_queries if args.expect_queries is not None else (
        len(expected_names) if expected_names is not None else len(queries))
    exp_total = None
    if exp_samples and exp_seeds is not None:
        exp_total = n_queries * exp_seeds * exp_samples
    found_total = sum(q["n_complete"] for q in queries)
    if exp_total is not None and found_total < exp_total:
        problems.append(f"incomplete: {found_total}/{exp_total} structures with confidences (queries x seeds x samples)")
    if args.expect_queries is not None and len(queries) < args.expect_queries:
        problems.append(f"{len(queries)} query dir(s) found, expected {args.expect_queries}")
    return {"expected_queries": n_queries, "expected_seeds": exp_seeds, "expected_samples": exp_samples,
            "samples_source": samples_src, "expected_total": exp_total, "complete_structures": found_total,
            "missing_queries": missing_q, "problems": problems}


# ------------------------------------------------------------------------------------------------ output
def print_text(report, args):
    out = sys.stdout.write
    out(f"OpenFold3 output summary: {report['root']}\n")
    for run in report["runs"]:
        info = run["run_files"]
        out(f"\n== run: {run['run_dir']}\n")
        out(f"   run files : {', '.join(info['present']) or 'none (partial tree: predictions only)'}\n")
        s = info.get("summary")
        if s:
            fq = f"; failed: {', '.join(s['failed_queries'])}" if s["failed_queries"] else ""
            out(f"   summary.txt: {s['status']} processed={s['processed']} ok={s['successful']} failed={s['failed']}{fq}\n")
        if info["fallback_summaries"]:
            out(f"   distributed fallback summaries: {', '.join(info['fallback_summaries'])} (a rank timed out)\n")
        if info.get("error_logs"):
            out(f"   error logs: {', '.join(info['error_logs'])} (tracebacks of failed queries)\n")
        rec = info["recorded"]
        if rec:
            keys = ("structure_format", "full_confidence_output_format", "write_full_confidence_scores", "samples_per_seed",
                    "use_msa_server", "use_templates", "checkpoint_name", "checkpoint_file")
            out("   recorded  : " + " ".join(f"{k}={rec.get(k)}" for k in keys if k in rec) + "\n")
        if info["msas"]:
            out(f"   msas/     : {info['msas']['run_dirs']} run dir(s), contents={','.join(info['msas']['contents']) or '-'}\n")
        if info["single_sequence_chains"]:
            out(f"   NOTE single-sequence (dummy MSA) chains: {', '.join(info['single_sequence_chains'])} "
                "-> expect low confidence; not comparable with MSA runs\n")
        if info["kit"]:
            out(f"   kit files : {json.dumps(info['kit'])}\n")
        for q in run["queries"]:
            nseeds = q["n_seeds"]
            spp = sorted(set(q["samples_per_seed"].values()))
            tim = ", ".join(f"seed_{s} {fmt(v['timing_s'], 1)} s" for s, v in q["seeds"].items())
            out(f"\n   query {q['query']}: {nseeds} seed(s) x {spp if len(spp) != 1 else spp[0]} sample(s); "
                f"{q['n_complete']}/{q['n_structures']} structures with confidences; timing: {tim or '-'}\n")
            if q["kit_structure_first_sidecars"]:
                out(f"     kit structure-first sidecars: {q['kit_structure_first_sidecars']}\n")
            hdr = f"     {'rank':>4} {'seed':>11} {'smp':>3} {'ranking':>8} {'pTM':>6} {'ipTM':>6} {'pLDDT':>6} {'gPDE':>6} {'disord':>6} {'clash':>5}  model\n"
            out(hdr)
            rows = q["ranked"] if args.top is None else q["ranked"][: args.top]
            for r in rows:
                clash = r.get("has_clash")
                out(f"     {r['rank'] if r['rank'] is not None else '-':>4} {r['seed']:>11} {r['sample']:>3} "
                    f"{fmt(r.get('sample_ranking_score')):>8} {fmt(r.get('ptm')):>6} {fmt(r.get('iptm')):>6} "
                    f"{fmt(r.get('avg_plddt'), 2):>6} {fmt(r.get('gpde'), 3):>6} {fmt(r.get('disorder'), 3):>6} "
                    f"{('-' if clash is None else ('nan' if is_nan(clash) else int(clash))):>5}  "
                    f"{r['model'] or '-'}{'' if r['status'] == 'ok' else '  [' + r['status'] + ']'}\n")
            if args.top is not None and len(q["ranked"]) > args.top:
                out(f"     ... {len(q['ranked']) - args.top} more\n")
            top = q["top"]
            if top:
                mono = len(top.get("chain_ptm") or {}) == 1
                out(f"     top: seed_{top['seed']}/{top['model']}"
                    f"{'  (single chain: ipTM is 0 by construction; ranking = 0.2 pTM + 0.5 disorder)' if mono else ''}\n")
                if args.chains:
                    cp = top.get("chain_ptm") or {}
                    out("     top chain_ptm: " + (", ".join(f"{k}={fmt(num(v), 3)}" for k, v in cp.items()) or "-") + "\n")
                    pairs = sorted(((num(v) or 0.0, k) for k, v in (top.get("chain_pair_iptm") or {}).items()), reverse=True)
                    shown = pairs[: args.max_pairs]
                    out("     top chain_pair_iptm (highest first): " +
                        (", ".join(f"{k}={fmt(v, 3)}" for v, k in shown) or "-") +
                        (f" ... {len(pairs) - len(shown)} more" if len(pairs) > len(shown) else "") + "\n")
            for w in q["warnings"]:
                out(f"     warn: {w}\n")
            for p in q["problems"]:
                out(f"     PROBLEM: {p}\n")
        c = run["completeness"]
        out(f"\n   completeness: queries={c['expected_queries']} seeds={c['expected_seeds'] if c['expected_seeds'] is not None else '? (pass --expect-seeds)'} "
            f"samples={c['expected_samples'] if c['expected_samples'] else '?'}"
            f"{' (' + c['samples_source'] + ')' if c['samples_source'] else ''} -> "
            f"{c['complete_structures']}/{c['expected_total'] if c['expected_total'] is not None else '?'} structures with confidences\n")
        for p in c["problems"]:
            out(f"   PROBLEM: {p}\n")
    for w in report["warnings"]:
        out(f"\nwarn: {w}\n")
    if report["exit_code"] != 0:
        verdict = "INCOMPLETE / PROBLEMS"
    elif all(r["completeness"]["expected_total"] is not None for r in report["runs"]):
        verdict = "COMPLETE"
    else:
        verdict = "NO PROBLEMS FOUND (grand total not checked: pass --expect-seeds / --expect-samples)"
    out(f"\nverdict: {verdict} (exit {report['exit_code']})\n")


def json_safe(x):
    """NaN / inf -> None so that --json output is strict JSON."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    return x


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only summary and completeness check of an OpenFold3 output tree.")
    ap.add_argument("output_dir", help="a run's --output-dir, one query directory, or a parent of several runs")
    ap.add_argument("--expect-samples", type=int, default=None, help="diffusion samples per seed (default: model_config.json)")
    ap.add_argument("--expect-seeds", type=int, default=None, help="seed directories per query (not inferred)")
    ap.add_argument("--expect-queries", type=int, default=None, help="number of queries (default: inference_query_set.json)")
    ap.add_argument("--query-json", default=None, help="the query JSON that was run: its query names are expected")
    ap.add_argument("--top", type=int, default=None, help="print only the N best samples per query")
    ap.add_argument("--chains", action="store_true", help="print chain_ptm / chain_pair_iptm of each query's top sample")
    ap.add_argument("--max-pairs", type=int, default=10, help="chain pairs shown with --chains (default 10)")
    ap.add_argument("--check-coords", action="store_true",
                    help="also read every model file and reject nan/inf coordinates (slower on large trees)")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.output_dir)
    if not os.path.isdir(root):
        sys.stderr.write(f"error: {args.output_dir} is not a directory\n")
        return 2
    for n, lo in (("expect_samples", 1), ("expect_seeds", 1), ("expect_queries", 1), ("top", 1), ("max_pairs", 0)):
        v = getattr(args, n)
        if v is not None and v < lo:
            sys.stderr.write(f"error: --{n.replace('_', '-')} must be >= {lo}\n")
            return 2
    qj_names = None
    if args.query_json:
        d, err = load_json(args.query_json)
        if err or not isinstance(d, dict) or not isinstance(d.get("queries"), dict):
            sys.stderr.write(f"error: cannot read queries from {args.query_json} ({err or 'no top-level queries map'})\n")
            return 2
        qj_names = sorted(d["queries"])

    qdirs = find_query_dirs(root)
    runs = {}
    for qd in qdirs:
        runs.setdefault(os.path.dirname(qd), []).append(qd)
    report = {"root": root, "runs": [], "warnings": [], "exit_code": 0}
    if not qdirs:
        report["warnings"].append("no query directories (with seed_<int>/ subdirectories) found")
        report["exit_code"] = 1
    if len(runs) > 1:
        report["warnings"].append(f"{len(runs)} separate runs found; they are ranked separately - do not rank across "
                                  "runs, modes, cards or MSA settings")
    any_problem = not qdirs
    for run_dir in sorted(runs):
        info = read_run_files(run_dir)
        queries = [analyse_query(qd, info, args) for qd in runs[run_dir]]
        expected_names = qj_names if qj_names is not None else info["query_names"]
        if info.get("recorded", {}).get("skip_existing") and qj_names is None:
            expected_names = None  # skip_existing drops finished queries from inference_query_set.json
        if qj_names is None and runs[run_dir] == [root]:
            expected_names = [os.path.basename(root)]  # OUTPUT_DIR is one query directory: its siblings are not expected
        comp = completeness(info, queries, args, expected_names)
        if info["summary"] and (info["summary"].get("failed") or 0) > 0:
            comp["problems"].append(f"summary.txt reports {info['summary']['failed']} failed quer(y/ies)")
        if info["summary"] and info["summary"].get("status") and info["summary"]["status"] != "COMPLETE":
            comp["problems"].append(f"summary.txt status {info['summary']['status']}")
        if info["fallback_summaries"]:
            comp["problems"].append("fallback_summary_rank_*.txt present: a distributed run did not finish cleanly")
        if info["error_logs"]:
            comp["problems"].append(f"per-query failures logged (OOM / exceptions; the call may still exit 0): "
                                    f"{', '.join(info['error_logs'])}")
        if any(q["problems"] for q in queries) or comp["problems"]:
            any_problem = True
        rel = os.path.relpath(run_dir, root)
        report["runs"].append({"run_dir": "." if rel == "." else rel, "run_files": info, "queries": queries,
                               "completeness": comp})
    report["exit_code"] = 1 if any_problem else 0
    if args.json:
        json.dump(json_safe(report), sys.stdout, indent=2, default=str, allow_nan=False)
        sys.stdout.write("\n")
    else:
        print_text(report, args)
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
