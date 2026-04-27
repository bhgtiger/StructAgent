---
name: review-paper
description: Read academic review papers (PDF) and produce structured, critical digests. Use when asked to read, digest, summarize, or analyze a review article, scoping review, systematic review, or meta-analysis. Handles PDF extraction, review-type triage, field mapping, evidence auditing, and digest generation focused on synthesis quality rather than method validation.
---

# Review Paper

Read a review paper → extract → classify the review type → map the field → audit the evidence base → file a critical digest.

## Pipeline

``` 
PDF → pdf_split.py --compact (deterministic Python, ~1 sec)
  ├── Sectioned markdown (5-15k tokens)
  ├── Metadata (title, authors, DOI, journal, year, keywords)
  └── Figures → disk

Read the markdown → classify review type → produce digest (template below)
  + image tool for key summary figures/tables when needed
  → file digest to project digests/ folder
  → file to YAML database with structured claims / follow-up papers
```

**Default rule:** use our local deterministic extraction pipeline first (`pdf_split.py` → read markdown directly). Do **not** call the built-in `pdf` tool by default for normal review reading. Only use the built-in PDF tool as an explicit fallback when our extractor fails, the PDF is malformed in a way that breaks extraction, or there is a specific reason to compare outputs.

**Why:** the local pipeline is cheaper, more deterministic, closer to source text, and avoids quality loss from intermediate summarization.

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

## Step 2: Read and Classify

Read the extracted markdown fully. This is the core intelligence step — no intermediate LLM.

Do not add a built-in `pdf` tool pass as a routine cross-check. If you want a cross-check, there must be a concrete reason: extraction corruption, suspicious metadata, missing sections/figures, or an explicit comparison request from the user.

### First classify the review type

Before digesting, decide what kind of review this is:
- **Narrative review** — expert overview, broad synthesis, often no formal search protocol
- **Scoping review** — maps the literature landscape and coverage boundaries
- **Systematic review** — explicit search and inclusion/exclusion process
- **Meta-analysis** — quantitative pooling of study results
- **Perspective / opinion review** — selective synthesis used to argue a position
- **Tutorial review** — pedagogical overview rather than evidence-weighted synthesis

Record both:
- **Review type**
- **Classification confidence:** high / medium / low

If type is ambiguous, say so explicitly.

## Step 3: Read with the right objective

A method paper asks: **does this method work, and where does it fail?**

A review paper asks different questions:
- **How does this paper carve up the field?**
- **What literature does it privilege or ignore?**
- **Is the synthesis balanced, current, and evidence-anchored?**
- **What map does it give that primary papers alone do not?**
- **What should we read next to verify or deepen the claims?**

### Reading Strategy by Review Type

**Narrative reviews:** treat them as arguments, not measurements. Look for authorial bias, missing counterevidence, and selective framing.

**Scoping reviews:** judge breadth and map quality. Do not confuse coverage with evidence strength.

**Systematic reviews:** inspect search strategy, inclusion criteria, risk-of-bias handling, and whether the conclusions match the actual evidence.

**Meta-analyses:** inspect heterogeneity, pooling assumptions, non-independence, subgroup fishing, and whether a pooled estimate is being oversold.

**Perspective / opinion reviews:** useful for ideas, dangerous for consensus. Separate provocation from established evidence.

## Step 4: Digest

Produce a structured digest following the template. Save to: `<project>/digests/<YYYY-MM-DD>_<first_author>_<short_title>.md`

The digest should stay concise and decision-oriented. The point is not to restate the review chapter by chapter; the point is to capture the field map, the evidence stance, the likely distortions, and the reading list hidden inside the paper.

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
- **Paper type:** review
- **Review type:** narrative | scoping | systematic | meta-analysis | perspective | tutorial
- **Classification confidence:** high | medium | low

## TL;DR [ALWAYS]
{2-3 sentences. What field it reviews, whether the synthesis is useful, and whether it is trustworthy.}

## Scope [ALWAYS]
- **Covered topics:**
- **Excluded / under-covered topics:**
- **Time span of literature:**
- **Intended audience:**

## The Review's Frame [ALWAYS]
- **Central thesis:**
- **How the field is organized:**
- **Assumptions in that framing:**

## Claim Cards [ALWAYS]
{3-7 key claims max. Each claim must be a falsifiable or checkable sentence and must include:}
- **Claim:**
- **Evidence basis:** meta-analysis | systematic synthesis | scoping map | narrative synthesis | expert opinion
- **Support level:** strong | mixed | weak | speculative
- **Anchor citations / primary papers:**

## Evidence Base [ALWAYS]
- **Most-relied-on primary studies / groups:**
- **Balance across methods/labs:** balanced | skewed | heavily skewed
- **Contradictory evidence acknowledged?:** yes | partially | no
- **Search / inclusion method reported?:** yes | partially | no

## Critical Assessment [ALWAYS]
### Strengths
{What this review genuinely does well.}

### Weaknesses
{What it does poorly, overstates, or glosses over.}

### Biases / Distortions
{Lab bias, method evangelism, citation circle, temporal bias, publication bias, etc.}

### Failure Modes [ALWAYS]
- **Outdatedness risk:** {is the field moving too fast for this review to still be reliable?}
- **What could mislead a reader:**
- **What must be checked in the primary literature:**

## Trust Verdict [ALWAYS]
- **Overall trust level:** high | medium | low
- **Why:** {2-4 concrete reasons only}

## Relevance to Project [ALWAYS when project active]
- **Significance:** high | medium | low — {why}
- **Useful concepts / taxonomy:**
- **Gaps it leaves:**

## Top 5 Next Papers to Read [ALWAYS]
{Pick five primary or otherwise decisive papers, not a vague bibliography dump. For each item include:}
1. **Paper:**
   - **Role:** foundational | best evidence | contrarian | methodologically sharp | best next-step for project
   - **Why this paper:**
   - **What claim from the review it helps verify/challenge:**
   - **Priority:** high | medium | low
2. **Paper:**
   - **Role:**
   - **Why this paper:**
   - **What claim from the review it helps verify/challenge:**
   - **Priority:**
3. **Paper:**
   - **Role:**
   - **Why this paper:**
   - **What claim from the review it helps verify/challenge:**
   - **Priority:**
4. **Paper:**
   - **Role:**
   - **Why this paper:**
   - **What claim from the review it helps verify/challenge:**
   - **Priority:**
5. **Paper:**
   - **Role:**
   - **Why this paper:**
   - **What claim from the review it helps verify/challenge:**
   - **Priority:**

## Connections [BEST-EFFORT]
- **Related to:** {other papers in project database}
- **Contradicts:** {if any}
- **Extends:** {if builds on prior work}

## Tags [ALWAYS]
{comma-separated keywords}

## Raw Notes [BEST-EFFORT]
{Key tables, review figures, notable omissions, useful quotations, and any follow-up leads worth preserving.}
```

## Hard Anti-Fluff Checks

A review digest is not acceptable unless these conditions are met:

1. **At least 3 claim cards** are present unless the review is extremely narrow.
2. **No major claim without evidence anchors.** If the review makes a claim but gives no real support, say so.
3. **At least one explicit missing piece or bias** must be named.
4. **Review type must shape trust.** Do not summarize a narrative review as if it were systematic evidence.
5. **Outdatedness must be checked.** If the review stops before a major shift in the field, warn clearly.
6. **Do not mistake popularity for evidence.** A highly cited narrative can still be weak.

## Common Failure Modes to Watch For

### Bias / incentive failures
- Citation laundering: authoritative language built on weak primary evidence
- Search-free selection bias disguised as expertise
- Overreliance on one lab, method family, or author network
- Failure to discuss negative or contradictory evidence
- Review as soft advertisement for a favored technique

### Outdatedness failures
- Literature window ends before major methodological or conceptual shifts
- Definitions or standards changed after publication
- Foundational cited papers later weakened, contradicted, or superseded

### Meta-analysis failures
- Pooling non-comparable studies
- Heterogeneity acknowledged but ignored in conclusions
- Multiple subgroup analyses used to rescue a weak main result
- Non-independence or double-counting of evidence

## Step 5: File to Database

After producing the digest, add the paper to the project's YAML database. Same filing rules as the paper-reader skill.

### Directory Layout

Same as paper-reader — see that skill for the full directory tree. Typical paths:
- Digest → `digests/YYYY-MM-DD_<author>_<short>.md`
- PDF → `papers_incoming/<key>.pdf`
- Extraction → `extractions/<author_year_short>/`
- YAML → `database_<collection>.yaml`

### YAML Schema

Same as paper-reader, but for reviews include:

```yaml
paper_type: review                   # Always "review" for this skill
# Add review subtype in tags, e.g.:
tags: ["narrative review", "cryo-EM", ...]
```

### Connection Rules

1. **Always use `key` strings** — the exact `key` field of the target paper
2. **Cross-database references are OK**
3. **Bidirectional when meaningful**
4. **Never use IDs, titles, or partial strings** — only exact `key` values

### Filing Checklist

1. **Copy PDF** to `papers_incoming/<key>.pdf`
2. **Write digest** to `digests/YYYY-MM-DD_<author>_<short>.md`
3. **Add YAML entry** with all required fields
4. **Update connections** — add the new paper's key to related existing entries' connection lists
5. **Verify** — run a quick check that all connection keys resolve to real entries

### ID Assignment

IDs may have gaps. Always assign `max(existing IDs across all collections) + 1`. Never reuse IDs.

### Review-Specific Handoff Notes

Minimum items to preserve from the digest into the YAML `maria_opinion` or tags:
- Review type (narrative / scoping / systematic / meta-analysis / perspective / tutorial)
- Trust verdict
- Top follow-up papers identified (add these as connections where they exist in DB)

## Principles

- **Treat reviews as lenses, not neutral truth.**
- **Separate what the review claims from what the evidence actually supports.**
- **A review with no explicit search method is not automatically bad, but it is less evidentially trustworthy.**
- **A scoping review maps a field; it does not necessarily weigh evidence.**
- **A narrative review can be insightful and still badly biased.**
- **Always extract the hidden reading list.** The best output from a review is often the set of primary papers worth reading next.
- **Be concise.** The digest should help someone decide what this review is good for, what it gets wrong, and where to go next.
