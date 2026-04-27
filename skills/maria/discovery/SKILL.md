---
name: discovery
description: Discover and prioritize new papers using Semantic Scholar + Maria's structured database. Use when asked to find more papers, expand a literature map, close database coverage gaps, harvest related papers from seed methods, or build a ranked reading queue for a topic.
---

# Discovery

Discovery is not generic search. It is a **gap-driven literature expansion workflow**.

Use this skill when the goal is to:
- find more papers in a topic area
- expand around known seed papers
- identify missing methods, benchmarks, validation papers, or applied follow-ups
- turn a project database into a ranked reading queue

## Principle

- **Semantic Scholar tools = discovery layer**
- **Project database = judgment layer**

Do not dump search results blindly. Every candidate must be interpreted against the current database: what is already covered, what is duplicated, and what real gap the paper would fill.

## Inputs

You need:
1. An active project or literature database
2. A topic, gap, or seed-paper set

## Tools (bundled)

All scripts live in this skill's `scripts/` directory. Resolve paths relative to the skill location.

- `scripts/s2_search.py` — targeted keyword/gap search
- `scripts/s2_recommend.py` — similar-paper expansion from strong seeds
- `scripts/s2_cite.py` — citation/reference neighborhood mining
- `scripts/s2_common.py` — shared utilities (API key loading, rate limiting, output formatting)

API key: reads from `S2_API_KEY` env var or `~/.s2_api_key` file.
Rate limit: 1 req/s (enforced by s2_common.py).
Requires: Python 3.10+, `requests` library.

## Workflow

### Step 0 — Define the gap first
Before searching, inspect the project/database summary and identify what is actually missing.

Typical gap types:
- method family undercovered
- benchmark/comparison papers missing
- applied follow-up papers missing
- validation logic present but constructive correction papers missing
- special-case domains undercovered (ligands, nucleic acids, membrane proteins, low resolution, heterogeneity)
- workflow integration missing between building / refinement / validation

Write the search objective in one sentence before running queries.

### Step 1 — Choose the right S2 mode

#### A. `s2_search.py` for directed gap hunting
Use when you know the missing topic.

Examples:
```bash
python3 scripts/s2_search.py \
  "cryo-EM model validation benchmark" --year 2018- --field Biology --limit 20 --format tsv
```

Best for:
- explicit subtopics
- recent methods
- benchmark hunting
- venue or year constrained searches

Useful filters:
- `--year 2020-`
- `--min-citations 20`
- `--open-access`
- `--sort citationCount:desc` for canonical papers
- `--sort publicationDate:desc` for newer work

#### B. `s2_recommend.py` for family expansion
Use when you already have a strong seed paper and want close neighbors.

```bash
python3 scripts/s2_recommend.py DOI:<doi> --limit 15 --format tsv
```

Best for:
- expanding around trusted core methods
- finding direct competitors
- surfacing follow-up papers the keyword search misses

Use strong seeds, not weak overview papers.

#### C. `s2_cite.py` for graph mining
Use when you want intellectual parents or downstream impact.

```bash
python3 scripts/s2_cite.py DOI:<doi> \
  --direction both --limit 20 --sort-citations --format tsv
```

Interpretation:
- **references** = foundations / prior art
- **citations** = influence / adoption / follow-ups
- **both** = local method neighborhood

This is often the most valuable mode for building coherent clusters rather than random search piles.

### Step 2 — Deduplicate against the database
Before reading anything, compare each candidate against the project database.

Minimum duplicate keys:
- DOI
- exact title
- near-title match if DOI missing

Rules:
- already indexed → skip
- same paper under variant title formatting → merge, do not reread
- review paper covering an already indexed method cluster → maybe keep, but mark as synthesis rather than novel method

### Step 3 — Triage, don’t hoard
Rank candidates before full reading.

Prioritize papers that do one or more of the following:
1. fill a known coverage gap
2. are benchmark or comparison papers
3. anchor an important method family
4. connect two existing clusters
5. represent applied evidence, not just another software overview

Down-rank papers that are:
- repetitive suite overviews
- thin application notes with no evaluation
- marketing-style method papers without real comparison
- low-signal duplicates of already indexed work

### Step 4 — Batch by function
Group the final shortlist into buckets:
- structure building
- refinement
- validation
- integrated workflows
- special cases (ligands, nucleic acids, low resolution, membrane proteins, heterogeneity)

The goal is to build interpretable batches, not a flat queue.

### Step 5 — Hand off to paper reading
Once shortlisted, pass papers into the normal reading pipeline:
- primary paper → `paper-reader`
- review/tutorial/systematic review → `review-paper`

Do not replace reading with search metadata.

### Step 6 — Update the database and gap map
After reading, update:
- project database entry
- connections/edge structure
- cluster-level gaps
- seed list for future recommendation runs

Discovery is iterative: each read changes the next query.

## Search Strategy Templates

### Find canonical papers in an area
```bash
python3 scripts/s2_search.py \
  "cryo-EM real-space refinement" --year 2015- --min-citations 30 \
  --sort citationCount:desc --limit 20 --format tsv
```

### Find recent papers in an area
```bash
python3 scripts/s2_search.py \
  "cryo-EM model building" --year 2022- --sort publicationDate:desc \
  --limit 20 --format tsv
```

### Expand from a seed paper
```bash
python3 scripts/s2_recommend.py \
  DOI:<doi> --limit 15 --format tsv
```

### Mine the neighborhood around a method paper
```bash
python3 scripts/s2_cite.py DOI:<doi> \
  --direction both --limit 20 --sort-citations --format tsv
```

## Output Expectations

A good discovery pass should produce:
- a **search objective**
- a **candidate list** with duplicates removed
- a **ranked shortlist**
- a short statement of **why these papers matter**
- explicit **next reading batch** recommendations

## Standards

- Search with intent, not curiosity.
- Prefer graph expansion around strong seeds over vague keyword wandering.
- Benchmark papers are usually more valuable than another tool announcement.
- Do not confuse citation count with quality.
- The database decides relevance; the API only proposes candidates.

## Lessons from Initial Discovery Runs (2026-03-31)

These findings came from the first real test of this workflow against the structural model building database (then 64 papers).

### What works
- **Citation/reference graph is clearly the best discovery path** for this literature. Start from a trusted seed already in the database, expand via `s2_cite.py --direction both`, dedup, promote cluster-filling papers.
- Raw keyword search is alive but noisy — too many generic structure papers. Use it for directed gap hunting only, not bulk discovery.
- The best candidates tend to surface from 2–3 strong seeds, not from wide keyword sweeps.

### Typical gap categories (structural biology literature)
- ChimeraX / ISOLDE applied literature (thin beyond core method papers)
- Validation benchmarks (many tool papers, not enough head-to-head comparisons)
- Constructive validation / automated rebuilding vs. expert rebuilding
- End-to-end workflow comparisons (build → refine → validate pipeline papers)
- Special cases: ligands, nucleic acids, membrane proteins, low resolution, heterogeneity

### Recommended seed families for structural model building
- **Refinement**: Afonine 2018 (PHENIX real-space), Murshudov 2011/2016 (REFMAC5/Servalcat)
- **Validation**: Barad 2015 (EMRinger), Pintilie 2025 (Q-score), MolProbity
- **AI building**: Jamali 2024 (ModelAngelo), Terashi 2023 (DeepMainmast)

### Tiering heuristic
- **Tier 1**: fills a known cluster gap, has benchmark data, or connects two existing clusters
- **Tier 2**: promising but weakly cited, too new, or overlaps existing coverage
- **Skip**: repetitive suite overviews, thin application notes, marketing-style papers

## Gap Snapshot Template

When starting a discovery pass, write a snapshot like this before searching:

```markdown
# Gap Snapshot — [date]

Source: [database name], [N] papers, [M] clusters

## Identified Gaps
- [gap 1: what's missing and why it matters]
- [gap 2]
...

## Discovery Priorities (ranked)
1. [highest priority gap to fill]
2. ...

## Search Strategy
- Seeds: [which papers to expand from]
- Modes: [search / recommend / cite — which and why]
- Filters: [year range, citation floor, etc.]
```

This snapshot goes into the project folder (not the skill). It anchors the search and makes triage decisions traceable.
