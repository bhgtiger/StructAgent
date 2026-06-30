# 00 — Scope, Trust Ladder, and Known Gaps

## What this skill is (and is not)

**Is:** a read-only advisor / command-planner / troubleshooter for Namdinator.
It explains the tool, judges suitability, plans local commands and web-form
submissions, preflights inputs and environment, and interprets outputs and logs.

**Is not:** an executor. It does not run Namdinator, does not submit the web
form, does not edit the user's files, and does not certify a model as correct or
publication-ready. See SKILL.md §0 for the boundary and §9 for the escalation
path to a future executor.

This split is deliberate. Namdinator is a 2019-era, untagged Bash pipeline with
a brittle dependency stack. The safe, useful, *honest* first version is advice;
execution requires a validated runtime that this project has not stood up.

## Source trust ladder

1. Live runtime behavior in the user's environment (captured `-h`, real run) —
   **the missing top of the ladder for this skill.**
2. Pinned source `namdinator/Namdinator_bash` @
   `5814c9474a41f7cbcca785ce83027227073d656f` (2019-10-16). Baseline for flags,
   defaults, output names, processing steps.
3. `namdinator.au.dk` form/manual/terms snapshots (2026-06-30) — web service
   fields/limits/privacy only.
4. Kidmose et al. 2019 (IUCrJ 6(4):526-531) — intended use, limitations,
   benchmark claims; not current exact syntax.
5. Historical repo `rukibuki/Namdinator` @ `f713537…` (2018-09-14) — older
   behavior; cite explicitly.
6. Dependency docs (VMD/NAMD/Phenix/Rosetta).
7. Community knowledge (thin — 0 GitHub issues found across both repos).
8. LLM memory — lowest; verify before asserting.

Rule of thumb: **exact flags / file behavior / current compatibility** belong to
source + live runtime. **Why and when to use it, and its limits** belong to the
paper. **Web-service fields, limits, and privacy** belong to the site snapshots.

## Known gaps and unverified claims — label these, never paper over them

| Gap / unverified item | Why it matters | Status |
|---|---|---|
| No live `./Namdinator_Generic.sh -h` captured | Exact help text, startup behavior, and any newer flags are unconfirmed. | Open — needs a real Linux host. |
| No validated fixture output tree | No ground-truth output names/layout/log formats beyond what the source writes. | Open — run the shipped fixture. |
| Repo ships `emd_6640.map/.mrc` but README says `emd_6644.mrc` | A wrong EMDB ID/resolution would poison example commands. | **Resolved 2026-06-30:** EMD-6640 = PDB 3JD8 = human NPC1 @ 4.43 Å (verified EMDB+RCSB); README `emd_6644` is a typo (unrelated entry, PDB 5JUP). See ref 10. |
| Local CIF / `.pdb.gz` support | Web UI accepts them; the CLI path is documented for PDB. Promising CIF/GZ locally is unverified. | Open — test on a real host. |
| Current dependency compatibility | Old code vs. modern VMD/NAMD/Phenix/Rosetta may break or change output parsing. | Open — validate pinned + modern versions separately. |
| Web backend API contract | Only the HTML/JS form was observed, never submitted. | Out of scope — do **not** build an API caller from observed HTML. |
| `water_molecules` field labeled "Implicit Solvent (GBIS)" | UI field name vs. label conflict; behavior unconfirmed. | Open — verify live before automating. |
| Supplementary benchmark table (full per-case data) | PMC PDF/supp endpoints returned a proof-of-work page; only main-text numbers captured. | Partial — main numbers known; full table not extracted. |
| Rosetta/Phenix license specifics for install advice | Affects what install path to recommend. | Open — link official licenses; do not assume redistribution rights. |

When a user's question lands on one of these, **say it is unverified and how to
verify it** (usually: capture `-h` / run the fixture on a real host). Do not fill
the gap with plausible-sounding invention.

## Versioning intent

`version: 0.1.0` = read-only advisor (v0). The roadmap (see the project plan):
v1 site-config-aware command generator, v2 read-only output/log parsers (after a
real fixture exists), v3 execution (only after a validated runtime). Do not let
this skill drift into v2/v3 behavior without the prerequisites in SKILL.md §9.
