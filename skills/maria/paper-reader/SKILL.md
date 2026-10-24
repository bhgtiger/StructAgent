---
name: paper-reader
description: "Academic paper PDF extraction, structured digest authoring, and YAML database filing (standard and Auto_build_v1 deposit-blind modes)."
---

# Paper Reader

Deterministic PDF-to-Markdown extraction (`[p. N]` page markers + figures) → full-text reading → structured digest → YAML database filing → deterministic validation.

## Core Rules

- **Use `scripts/pdf_split.py --compact` first**, then read `<stem>_compact.md` directly. Use the built-in PDF viewer only as a fallback when extraction fails or is visibly corrupted.
- **Select the target mode before writing:**
  - **Standard Mode:** General research projects (`<project>/digests/YYYY-MM-DD_<first_author>_<short_title>.md`; PDFs and extractions under `<project>/database/`).
  - **`Auto_build_v1` Deposit-Blind Mode (Zone A):** Live-runtime structural biology literature base (`knowledge/literature/digests/<key>.md` $\le 6,000$ B; raw PDFs and extractions in `$AB_SCRATCH/literature_raw/`; extended YAML schema; Zone-A regex phrasing rules; 2-session review).

## Workflow

### Step 0: Duplicate Check

```bash
python3 scripts/check_duplicate.py <pdf_path> <database_yaml_path>
```

- **Exit 0:** No duplicate, proceed.
- **Exit 1:** Duplicate detected — stop unless explicitly told to re-read/force.
- **Exit 2:** Missing file or YAML error — warn and proceed if creating a new database.

### Step 1: Extract Markdown & Figures (`[p. N]` Markers)

```bash
# Standard mode:
python3 scripts/pdf_split.py <pdf_path> --output-dir <project>/extractions/<paper_name> --compact

# Auto_build_v1 mode (keep PDFs/extractions in $AB_SCRATCH to respect the 15 MB git repo cap):
python3 scripts/pdf_split.py "$AB_SCRATCH/literature_raw/papers_incoming/<key>.pdf" \
  --output-dir "$AB_SCRATCH/literature_raw/extractions/<key>" --compact
```

- Outputs `<stem>_compact.md` with `[p. N]` page markers on section headers and inline page boundaries, plus `figures/`.
- Flags: `--compact` (default; drops refs/acknowledgments), `--no-refs`, `--no-figures`, `--json`.

### Step 2: Read & Inspect Figures

- Read `<stem>_compact.md` in full (for papers >15 pages: pass 1 = Abstract/Intro/Results/Discussion; pass 2 = Methods).
- Inspect data figures (`figures/fig_p*.png`) with the image viewer when they carry plots, tables, or structural comparisons. Skip decorative figures.

### Step 3: Author Digest

Load [`references/templates_and_schemas.md`](references/templates_and_schemas.md) for the exact Markdown template:

- **Standard Mode:** Save to `<project>/digests/YYYY-MM-DD_<first_author>_<short_title>.md`.
- **`Auto_build_v1` Deposit-Blind Mode:** Save to `knowledge/literature/digests/<key>.md` and enforce all 6 Zone-A rules (details in [`references/auto_build_v1_mode.md`](references/auto_build_v1_mode.md)):
  1. **Hard byte cap (`KB-P1`):** `fulltext` $\le 6,000$ bytes (`wc -c`); `abstract` $\le 1,200$ bytes (`abstract` digests cannot back `S1` cards).
  2. **Mandatory locators (`[ALWAYS]`, `KB-P2`):** Every bullet in `## Key Quantitative & Method Claims (with Locators)` must cite `[p. X, Table Y / Fig. Z / §Y.Z]`.
  3. **No residue or chain identifiers (`KB-P5`):** Never write `Pro308`, `His202`, `Pro7`, `A/247`, `B:562`, or `chain B residue 250`. Generalize to *"an Xaa–Pro dipeptide"* or *"a surface glutamate side chain"*. (Case-sensitive 3-letter AA + `\d{1,5}` allows lowercase `met 3 criteria` and `his 2 trials`.)
  4. **Stoichiometry formatting (`KB-P5`):** Write `Zn(Cys)4` or `ZnCys3His1`, never bare `Cys4` or `His1`.
  5. **Torsion angles & reported numbers (`KB-P5`):** Write canonical angles in words (*"omega near zero degrees"*, *"omega near 180 degrees"*), never `omega = 0` or `chi1 = -60`. Quote numbers *as reported* with locators; never write prescriptive gate language (`must be <= ...`, `accept only if ...`).
  6. **No slash tokens, target IDs, absolute paths, or run refs (`KB-P1`, `KB-P8`):** Avoid `B/4`, `s/2`, `P2/1` in prose (`G-08` and `K-0001` are safe). Never include `state/targets.jsonl` PDB/EMDB IDs (`emd44497`, `8P79`), `/gpfs/...` or `/home/...` paths, or `reports/target...` references.

### Step 4: File to YAML Database & Validate

Add the paper entry to the YAML database following the schema in [`references/templates_and_schemas.md`](references/templates_and_schemas.md):

- Assign `id: max(existing IDs) + 1` (never reuse IDs).
- Use exact snake_case `key` strings in `connections` (bidirectional when meaningful; never IDs or titles).
- In `Auto_build_v1` mode (`knowledge/literature/database_structbio.yaml`), include all Maria base fields plus `publication_status`, `digest_basis`, `pdf: null`, `deposit_blind_safe: true`, `blocks`, canonical `problem_classes` (`state/vocab/problem_classes.tsv`), `topics` (`knowledge/cards/topics.tsv`), `tools`, and `verification`.
- Run the deterministic validator before finishing:
  ```bash
  python3 scripts/validate_digest.py \
    --digest knowledge/literature/digests/<key>.md \
    --yaml knowledge/literature/database_structbio.yaml \
    --key <key>
  ```

### Step 5 (`Auto_build_v1` `KB-D3`): Two-Session Automatic Review

- **Session 1 (Curator / Author):** Extracts PDF, writes `digests/<key>.md` and YAML entry, optionally drafts `knowledge/cards/candidates/SB-XXX-NNN.json`, and runs `scripts/validate_digest.py`.
- **Session 2 (Independent Reviewer, `reviewer != author`):** A separate agent session runs `scripts/validate_digest.py`, `ab-kb lit check`, and `ab-kb verify`, verifies every cited `[p. X, Table Y / Fig. Z]` locator against `$AB_SCRATCH/literature_raw/extractions/<key>/<key>_compact.md`, and signs the acyclic `review_receipt_sha256`.

## References & Scripts

- [`references/templates_and_schemas.md`](references/templates_and_schemas.md) — Standard & `Auto_build_v1` digest templates, YAML schemas, and canonical vocabularies.
- [`references/auto_build_v1_mode.md`](references/auto_build_v1_mode.md) — Scratch storage layout, Zone-A phrasing checklist, 2-session review protocol, and Stage `K0` 21-paper queue.
- `scripts/pdf_split.py` — Deterministic PyMuPDF extractor emitting `[p. N]` page markers and figures.
- `scripts/check_duplicate.py` — Pre-read title fuzzy-match duplicate checker.
- `scripts/validate_digest.py` — Deterministic validator for byte caps, mandatory locators, YAML schema, and Zone-A regexes (`--self-test` for unit tests).
