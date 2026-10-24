# Digest Templates & YAML Schemas

Use the **`Auto_build_v1` Deposit-Blind templates** when curating into `knowledge/literature/` (`Zone A`), and the **Standard Mode templates** for general research projects.

---

## 1. `Auto_build_v1` Deposit-Blind Digest Template (`knowledge/literature/digests/<key>.md`)

- **Hard byte caps (`KB-P1`):**
  - `fulltext` digest: **$\le 6,000$ bytes** (`wc -c <= 6000`). Required for any source backing an `S1` card.
  - `abstract` digest: **$\le 1,200$ bytes** (`wc -c <= 1200`; metadata + verbatim abstract). Cannot back an `S1` card.
- **All `[ALWAYS]` sections and claim locators (`[p. X, Table Y / Fig. Z / §Y.Z]`) are mandatory.**

```markdown
# {Title}

## Metadata [ALWAYS]
- **Key:** `{key}`
- **Authors:** {authors}
- **Journal / Year:** {journal} ({year})
- **DOI:** `{doi}`
- **Paper type / Status:** `{paper_type}` / `{publication_status}`
- **Digest basis:** `fulltext` (or `abstract`)
- **Blocks / Topics:** `{blocks}` / `{topics}`

## TL;DR [ALWAYS]
{2-3 sentences: core physical principle or tool mechanism, what it establishes, and where it applies.}

## Key Quantitative & Method Claims (with Locators) [ALWAYS]
- **[p. X, Table Y / Fig. Z]:** {Falsifiable physical/stereochemical statement or tool behavior, quoting the paper's numbers *as reported*.}
- **[p. X, §Y.Z]:** {Second key claim + exact locator.}

## Protocol / Mechanism [ALWAYS]
- **Principle:** {How the method, metric, or stereochemical effect works.}
- **Parameters / Regimes:** {Resolution range, map regime (half-maps vs sharpened vs ML post-processed), or tool version assumptions.}

## Limitations, Contraindications & Competing Explanations [ALWAYS]
- **Failure modes / contraindications:** {When this method or metric misleads.}
- **Competing explanations:** {Other physical or refinement causes that produce the same symptom.}

## Connections [BEST-EFFORT]
- **Complements / Extends:** `{key_1}`, `{key_2}`
- **Contradicts:** `{key_3}` (if any)
```

---

## 2. `Auto_build_v1` Extended Tier-2 YAML Schema (`knowledge/literature/database_structbio.yaml`)

Preserves 100% of Maria's base schema and enums (`paper_type`, `significance`, `authors` list, `connections`), and adds the 9 `Auto_build_v1` Tier-2 fields (`KB-P1`):

```yaml
# REQUIRED — Maria base schema (enums unchanged)
id: 1                                           # Unique integer: max(existing IDs) + 1
key: stewart1990_cis_peptides                   # Exact snake_case key from manifest
title: "Occurrence and role of cis peptide bonds in protein structures"
authors: ["David E. Stewart", "Anupam Sarkar", "John E. Wampler"]
year: 1990
journal: "Journal of Molecular Biology"
doi: "10.1016/0022-2836(90)90159-J"
paper_type: empirical                           # method | empirical | review | benchmark | computational | theoretical | workshop_talk
significance: high                              # high | medium | low
tags: ["cis peptide", "proline isomerization", "backbone stereochemistry"]
digest: "digests/stewart1990_cis_peptides.md"   # Relative to knowledge/literature/
maria_opinion: "Foundational statistical baseline establishing ~5% cis occurrence for Xaa-Pro vs <0.05% for Xaa-nonPro."
connections: ["weiss1998_peptide_bonds", "jabs1999_nonpro_cis", "croll2015_cis_trans_errors"]

# REQUIRED — Auto_build_v1 Tier-2 extensions (KB-P1)
publication_status: peer_reviewed               # peer_reviewed | preprint | book | software_doc
digest_basis: fulltext                          # fulltext (<= 6,000 B) | abstract (<= 1,200 B; non-S1 only)
pdf: null                                       # Nullable (raw PDF archived in $AB_SCRATCH/literature_raw/papers_incoming/)
deposit_blind_safe: true                        # Must be boolean true for Zone-A literature
blocks: ["03_evaluate", "04_refine", "05_compare"]
problem_classes: ["cis_nonpro", "low_map_cc", "cbeta_deviation", "rama_outlier"]   # Canonical vocab only
topics: ["xaa_pro_isomer"]                      # Registered in knowledge/cards/topics.tsv
tools: []                                       # [] = tool-agnostic
verification:
  doi_resolved_on: "2026-10-23"
  title_matches: true
  checked_by: "crossref"
```

### Allowed Vocabularies (`Auto_build_v1`)

- **`paper_type`:** `method`, `empirical`, `review`, `benchmark`, `computational`, `theoretical`, `workshop_talk`
- **`significance`:** `high`, `medium`, `low`
- **`publication_status`:** `peer_reviewed`, `preprint`, `book`, `software_doc`
- **`digest_basis`:** `fulltext`, `abstract`
- **`blocks`:** `01_resource`, `02_build`, `03_evaluate`, `04_refine`, `05_compare`, `ab-ligand`
- **`problem_classes` (canonical `state/vocab/problem_classes.tsv` only — never mint new classes):**
  `rotamer_outlier`, `rama_outlier`, `clash`, `low_map_cc`, `cbeta_deviation`, `bond_outlier`, `angle_outlier`, `cis_nonpro`, `omega_twisted`, `asn_gln_his_flip`, `chain_break`, `missing_sidechain`, `register_shift`, `unaccounted_density`, `cablam_outlier`, `coverage_gap`, `ligand_geometry`, `ligand_density`
  - *Required canonical mappings (`KB-P2`):*
    - `cis_peptide` $\rightarrow$ `cis_nonpro` (or `low_map_cc`, `cbeta_deviation`, `rama_outlier` + topic `xaa_pro_isomer` for silent *trans*-built *cis*-Pro)
    - `twisted_peptide` $\rightarrow$ `omega_twisted`
    - `local_cc_drop` $\rightarrow$ `low_map_cc`
    - `overbuilt_loop` $\rightarrow$ `low_map_cc` (never `coverage_gap`)
    - `ligand_coordination` $\rightarrow$ `ligand_geometry`
    - `completeness_gap` $\rightarrow$ `coverage_gap`
- **`topics` (initial set in `knowledge/cards/topics.tsv`; open vocabulary per `KB-D2`):**
  `tracer_complementarity`, `prediction_prior`, `dictionary_conflict`, `xaa_pro_isomer`, `restraint_pricing`, `external_restraints`, `overfitting`, `cc_metrics`, `resolvability`, `map_regime`, `electron_scattering`, `carboxylate_scattering`, `radiation_damage`, `metal_coordination`, `his_tautomer_metal`, `restraint_dictionary`, `atom_naming`, `ncs_donor`, `model_bias`, `copy_stoichiometry`, `map_scale_strain`

---

## 3. Standard Mode Digest Template (`<project>/digests/YYYY-MM-DD_<first_author>_<short_title>.md`)

```markdown
# {Title}

## Metadata [ALWAYS]
- **Authors:**
- **Journal/Preprint:**
- **Year:**
- **DOI/URL:**
- **Read date:** {YYYY-MM-DD}
- **Project:** {project_name}
- **Paper type:** method | empirical | review | benchmark | computational | theoretical | workshop_talk

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
{Specific numbers [p. X, Table Y / Fig. Z], key figures, notable quotes worth remembering.}
```

---

## 4. Standard Mode YAML Schema & Layout

### Standard Directory Layout
```text
database/
├── database_<collection>.yaml    # Master index
├── digests/
│   └── YYYY-MM-DD_<author>_<short>.md
├── extractions/
│   └── <author_year_short>/
│       ├── <stem>_compact.md
│       └── figures/
├── papers_incoming/
│   └── <author_year_short>.pdf
└── connections.md
```

### Standard YAML Entry
```yaml
id: 74                              # Unique integer: max(existing IDs) + 1
key: author_year_short_descriptor   # Unique snake_case key
title: "Full paper title"
authors: ["First Author", "Second Author"]
year: 2024
journal: "Journal Name"
doi: "10.xxxx/xxxxx"
paper_type: method                  # method | empirical | review | benchmark | computational | theoretical | workshop_talk
significance: high                  # high | medium | low
tags: ["keyword1", "keyword2"]
digest: "digests/YYYY-MM-DD_author_short.md"
maria_opinion: "1-2 sentence assessment"
connections: []                     # Exact key strings only (bidirectional when meaningful)
pdf: "papers_incoming/author_year_short.pdf"
s2_paper_id: "abc123"
```
