---
name: paper-reader
description: Read academic papers (PDF) and produce structured digests. Use when asked to read, digest, summarize, or analyze a paper. Handles PDF extraction, section detection, metadata parsing, figure extraction, and digest generation following a structured template. Triggers on "read this paper", "digest this", "what does this paper say", or when a PDF path/URL is provided in the context of research work.
---

# Paper Reader

Read a paper → extract → digest → file.

## Pipeline

```
PDF → pdf_split.py --compact (deterministic Python, ~1 sec)
  ├── Sectioned markdown (5-15k tokens)
  ├── Metadata (title, authors, DOI, journal, year, keywords)
  └── Figures → disk

Read the markdown → produce digest (template below)
  + image tool for key figures when needed
  → file digest to project digests/ folder
```

**Default rule:** use our local deterministic extraction pipeline first (`pdf_split.py` → read markdown directly). Do **not** call the built-in `pdf` tool by default for normal paper reading. Only use the built-in PDF tool as an explicit fallback when our extractor fails, the PDF is malformed in a way that breaks extraction, or there is a specific reason to compare outputs.

**Why:** the local pipeline is cheaper, more deterministic, closer to source text, and avoids quality loss from intermediate summarization.

## Step 0: Duplicate Check

Before extracting, run the duplicate checker against the active project database:

```bash
python3 scripts/check_duplicate.py <pdf_path> <project_database_yaml_path>
```

- **Exit 0** → no duplicate, proceed to Step 1
- **Exit 1** → likely duplicate found. Stop and report to the user. Only proceed if they explicitly say "re-read" or "force"
- **Exit 2** → error (missing file, etc.). Warn but proceed — don't block on a broken check

This costs ~0 tokens (just PyMuPDF page-1 read + YAML parse) and prevents wasting 100k+ tokens re-digesting a paper that's already indexed.

## Step 1: Extract

Run the bundled extractor:

```bash
python3 scripts/pdf_split.py <pdf_path> --output-dir <project>/extractions/<paper_name> --compact
```

Flags:
- `--compact` — default for pipeline; drops references, acknowledgments, strips noise (~35-40% token savings)
- `--no-refs` — only drop references section
- `--no-figures` — skip figure extraction
- `--json` — also output JSON structure (for programmatic use)

Output: `<stem>_compact.md` (or `_extracted.md` without --compact), `figures/` dir.

If extraction fails or PyMuPDF is missing: `pip3 install PyMuPDF` then retry.

## Step 2: Read

Read the extracted markdown fully. This is the core intelligence step — no intermediate LLM.

Do not add a built-in `pdf` tool pass as a routine cross-check. If you want a cross-check, there must be a concrete reason: extraction corruption, suspicious metadata, missing sections/figures, or an explicit comparison request from the user.

For papers >15 pages, read in two passes:
1. Abstract, intro, results, discussion (get the story)
2. Methods in detail (get the protocol)

Use the `image` tool on extracted figures when they contain data (plots, charts, structural comparisons). Skip decorative figures.

## Step 3: Digest

Produce a structured digest following the template. Save to: `<project>/digests/<YYYY-MM-DD>_<first_author>_<short_title>.md`

### Reading Strategy by Paper Type

**Method papers:** Focus on what the method does, whether it works, and where it breaks. Scrutinize benchmarks for fair comparisons. Look for unstated failure modes.

**Empirical papers:** Focus on evidence quality. Check controls, sample sizes, statistical methods. Are conclusions proportional to evidence?

**Review papers:** Extract the taxonomy and landscape. Note which primary papers are leaned on most. Flag what's missing.

**Computational papers:** Focus on assumptions and their sensitivity. Is there experimental validation?

## Digest Template

All fields marked [ALWAYS] are mandatory. [BEST-EFFORT] fields filled when possible, marked "unknown" when not.

```markdown
# {Title}

## Metadata [ALWAYS]
- **Authors:**
- **Journal/Preprint:**
- **Year:**
- **DOI/URL:**
- **Read date:** {YYYY-MM-DD}
- **Project:** {project_name}
- **Paper type:** method | empirical | review | computational | theoretical

## TL;DR [ALWAYS]
{2-3 sentences. What they did, what they found, does it hold up.}

## The Claim [ALWAYS]
{What the paper says it contributes. Their framing, not your assessment.}

## Protocol [ALWAYS]
### Principle
{Core theory/concept behind the method or approach.}

### Workflow
{What they did, step by step. Tools, order, key parameters.}

### Limitations & Failure Modes [ALWAYS]
- **Acknowledged by authors:** {what they mention}
- **Observed:** {what you notice}
- **Failure modes:** {when would this NOT work?}

## Reproducibility [BEST-EFFORT]
- **Data availability:** deposited / on request / not mentioned
- **Code/software:** link or not mentioned
- **Key parameters reported:** yes / partially / no
- **Sample sizes:** reported / buried / inadequate

## Evaluation [ALWAYS]
### Internal Validity
{Does the evidence support THEIR conclusions?}

### External Validity [BEST-EFFORT]
{How generalizable? Tested on one system or many?}

## Relevance to Project [ALWAYS when project active]
- **Significance:** high / medium / low — {why}
- **What it changes:**
- **Gaps it leaves:**

## Connections [BEST-EFFORT]
- **Related to:** {other papers in project database}
- **Contradicts:** {if any}
- **Extends:** {if builds on prior work}

## Tags [ALWAYS]
{comma-separated keywords}

## Raw Notes [BEST-EFFORT]
{Specific numbers, key figures, notable quotes worth remembering.}
```

## Step 4: File to Database

After producing the digest, add the paper to the project's YAML database. This completes the pipeline — no separate "database skill" needed for filing.

### Directory Layout

Each project database lives under its own root (e.g. `~/Documents/Maria_projects/database/`). Typical structure:

```
database/
├── database_<collection>.yaml    # Master index (one or more collections)
├── digests/                       # Individual paper digests
│   └── YYYY-MM-DD_<author>_<short>.md
├── extractions/                   # pdf_split.py output
│   └── <author_year_short>/
│       ├── <stem>_compact.md
│       └── figures/
├── papers_incoming/               # Archived source PDFs
│   └── <author_year_short>.pdf
└── connections.md                 # Optional cross-reference notes
```

Paths are relative to the project database root. Do not hardcode absolute paths in the YAML.

### YAML Schema

Each entry in the `papers` list:

```yaml
# REQUIRED fields
id: 74                              # Integer, unique. Assign max(existing IDs) + 1
key: author_year_short_descriptor    # Unique snake_case key. Format: <first_author>_<year>_<short_descriptor>
title: "Full paper title"
authors: ["First Author", "Second Author"]
year: 2024
journal: "Journal Name"
doi: "10.xxxx/xxxxx"
paper_type: method                   # One of: method | empirical | review | benchmark | computational | theoretical | workshop_talk
significance: high                   # One of: high | medium | low
tags: ["keyword1", "keyword2"]
digest: "digests/YYYY-MM-DD_author_short.md"   # Relative path from DB root
maria_opinion: "1-2 sentence assessment"        # Your honest take
connections: []                      # List of keys (see Connection Rules below)

# OPTIONAL fields
pdf: "papers_incoming/author_year_short.pdf"    # Relative path to archived PDF
s2_paper_id: "abc123"               # Semantic Scholar ID if known
```

### Connection Rules

1. **Always use `key` strings** — the exact `key` field of the target paper (e.g. `croll_2018_isolde_physically_realistic_environment`)
2. **Cross-database references are OK** — a paper in `database_structural_model_building.yaml` can reference a key in `database_structural_biology.yaml`
3. **Bidirectional when meaningful** — if A connects to B, B should connect to A (but don't force it for trivial links)
4. **Never use IDs, titles, or partial strings** — only exact `key` values

### Filing Checklist

1. **Copy PDF** to `papers_incoming/<key>.pdf`
2. **Write digest** to `digests/YYYY-MM-DD_<author>_<short>.md`
3. **Add YAML entry** with all required fields
4. **Update connections** — add the new paper's key to related existing entries' connection lists
5. **Verify** — run a quick check that all connection keys resolve to real entries

### ID Assignment

IDs may have gaps (papers can be removed). Always assign `max(existing IDs across all collections) + 1`. Never reuse IDs.

### Allowed Values Reference

| Field | Allowed Values |
|-------|---------------|
| `paper_type` | `method`, `empirical`, `review`, `benchmark`, `computational`, `theoretical`, `workshop_talk` |
| `significance` | `high`, `medium`, `low` |

## Principles

- **Read the full paper.** If you only read the abstract, say so.
- **Be critical.** Flag weak stats, overclaimed conclusions, unfair comparisons.
- **Separate reporting from opinion.** "The Claim" = their words. "Evaluation" = your assessment.
- **Every method has failure modes.** If you can't find any, that's a flag about your understanding.
- **Project context shapes the digest.** Weight attention toward project-relevant aspects.
