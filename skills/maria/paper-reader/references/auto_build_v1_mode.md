# `Auto_build_v1` Deposit-Blind Curation Mode (`KB-P1`–`KB-P5`, `KB-D3`)

When curating literature for `Auto_build_v1`, digests (`knowledge/literature/digests/<key>.md`) and cards (`knowledge/cards/`) are served into **live, deposit-blind structural biology runs (`Zone A`)**. Every artifact must obey strict byte caps, contamination guardrails, scratch storage separation, and two-session automatic review.

---

## 1. Storage Layout: Git Repo ($\le 15$ MB) vs. Scratch (`$AB_SCRATCH`)

Never store PDFs or `pdf_split.py` extraction directories inside the `Auto_build_v1` git repository:

- **External Scratch Storage (`$AB_SCRATCH/literature_raw/`):**
  - Raw PDFs: `$AB_SCRATCH/literature_raw/papers_incoming/<key>.pdf`
  - Extracted Markdown & figures: `$AB_SCRATCH/literature_raw/extractions/<key>/<key>_compact.md` + `figures/`
- **Git Repository (`Auto_build_v1/knowledge/`):**
  - Tier-2 YAML index: `knowledge/literature/database_structbio.yaml` (set `pdf: null`)
  - Tier-2 digests: `knowledge/literature/digests/<key>.md` ($\le 6,000$ B `fulltext`; $\le 1,200$ B `abstract`)
  - Cross-reference notes: `knowledge/literature/connections.md`
  - Tier-1 candidate cards: `knowledge/cards/candidates/SB-XXX-NNN.json`

---

## 2. Mandatory Deposit-Blind Phrasing Rules (Zone-A Guardrails)

All digests and YAML prose fields (`title`, `maria_opinion`, `tags`) must pass `scripts/validate_digest.py`, `answer_shaped()`, and threshold lint (`KB-P1`, `KB-P5`, `KB-P8`):

1. **Hard Byte Cap:**
   - `fulltext` digest $\le 6,000$ bytes (`wc -c < knowledge/literature/digests/<key>.md`).
   - `abstract` digest $\le 1,200$ bytes (cannot support `S1` cards).
2. **No Specific Residue Identifiers:**
   - Never quote example residue IDs (`Pro308`, `His202`, `Tyr174`, `Pro7`) or chain/residue notation (`A/247`, `B:562`, `chain B residue 250`) from a paper's case studies.
   - Generalize to *"an Xaa–Pro dipeptide"*, *"residue $i-1$ preceding a proline"*, or *"a surface glutamate side chain"*.
   - *Regex note:* The 3-letter amino acid + `\d{1,5}` check is **case-sensitive**, so lowercase English words like `met 3 criteria` and `his 2 trials` pass, whereas `Met3`, `Pro7`, or `PRO308` are refused.
3. **No Stoichiometry Shorthand Matching `<Res><digit>`:**
   - Write `Zn(Cys)4` or `ZnCys3His1`, never bare `Cys4` or `His1` (which trips the case-sensitive residue regex).
4. **Canonical Torsion Angles in Words:**
   - Write *"cis peptide bond (omega near zero degrees)"* or *"trans peptide bond (omega near 180 degrees)"*.
   - Never write numeric torsion equations (`omega = 0`, `omega = 180`, `chi1 = -60`, `phi = -60`).
5. **No Prescriptive Threshold Gate Language:**
   - Quote quantitative findings *as reported* with an exact locator (e.g., *"Hintze et al. [p. 1179, Table 1] define the Top8000 rotamer outlier contour at 0.3% for general residues"*).
   - Never write project gate prescriptions (`clashscore must be <= ...`, `require ... >= ...`, `accept only if ... < ...`).
6. **No Slash Tokens, Benchmark Target IDs, Absolute Paths, or Run References:**
   - Avoid tokens shaped like `[A-Za-z][A-Za-z0-9]?/-?\d+` (`B/4`, `s/2`, `P2/1`) in prose; hyphenated IDs (`G-08`, `K-0001`) are safe.
   - Never include any `target_id`, `deposit` PDB code, or `EMD-xxxxx` accession from `state/targets.jsonl`.
   - Never include absolute paths (`/gpfs/...`, `/home/...`, `/scratch/...`) or run references (`reports/target...`).

---

## 3. Two-Session Automatic Review Workflow (`KB-D3`)

Per owner ruling `KB-D3`, admission of digests and cards is **100% automatic** (no owner approval in the loop) and enforced by **two separate agent sessions**:

### Session 1: Curator / Author Agent
1. Check duplicates against `knowledge/literature/database_structbio.yaml`:
   ```bash
   python3 scripts/check_duplicate.py "$AB_SCRATCH/literature_raw/papers_incoming/<key>.pdf" knowledge/literature/database_structbio.yaml
   ```
2. Extract Markdown with `[p. N]` page markers and figures to scratch:
   ```bash
   python3 scripts/pdf_split.py "$AB_SCRATCH/literature_raw/papers_incoming/<key>.pdf" \
     --output-dir "$AB_SCRATCH/literature_raw/extractions/<key>" --compact
   ```
3. Read `$AB_SCRATCH/literature_raw/extractions/<key>/<key>_compact.md` in full and inspect data figures.
4. Write `knowledge/literature/digests/<key>.md` ($\le 6,000$ B) with mandatory `[p. X, Table Y / Fig. Z / §Y.Z]` locators and append/update the entry in `knowledge/literature/database_structbio.yaml`.
5. Run deterministic validation before handing off:
   ```bash
   python3 scripts/validate_digest.py \
     --digest knowledge/literature/digests/<key>.md \
     --yaml knowledge/literature/database_structbio.yaml \
     --key <key>
   ```

### Session 2: Independent Reviewer Agent (`reviewer != author`)
1. Must run in an **independent agent session** (different model or fresh session, never the author session).
2. Run deterministic checks (`scripts/validate_digest.py`, `ab-kb lit check`, `ab-kb verify`).
3. Audit every quantitative and method claim in `knowledge/literature/digests/<key>.md` (and any candidate card `knowledge/cards/candidates/SB-XXX-NNN.json`) against the stated `[p. N]` / Table / Figure locators in `$AB_SCRATCH/literature_raw/extractions/<key>/<key>_compact.md`.
4. Compute and sign the acyclic receipt (`payload_sha256` over canonical sorted-key UTF-8 JSON excluding `reviewer`, `reviewed_on`, `review_receipt_sha256`) so the artifact can be bound in a release manifest.

---

## 4. Stage `K0` Priority Queue: 21 Release-1 Sources

Digest these 21 ★ sources first to back the 8 Release-1 seed cards:

- **`SB-TRC-001` (Tracer complementarity):**
  - `jamali2024_modelangelo` (`10.1038/s41586-024-07215-4`)
  - `su2025_cryoatom` (`10.1038/s41594-025-01713-3`)
  - `su2026_cryoatom2` (`10.65215/ltspreprints.2026.04.14.000185`)
- **`SB-DICT-001` (CDL vs. single-target dictionaries):**
  - `berkholz2009_cdl` (`10.1016/j.str.2009.08.012`)
  - `engh1991_parameters` (`10.1107/S0108767391001071`)
  - `nicholls2018_ccpem_fitting` (`10.1107/S2059798318007313`)
- **`SB-PEP-001` & `SB-PEP-002` (*Cis*-nonPro & silent *trans*-built *cis*-Pro):**
  - `croll2015_cis_trans_errors` (`10.1107/S1399004715000826`)
  - `stewart1990_cis_peptides` (`10.1016/0022-2836(90)90159-J`)
  - `weiss1998_peptide_bonds` (`10.1038/1368`)
  - `jabs1999_nonpro_cis` (`10.1006/jmbi.1998.2459`)
  - `lovell2003_rama_cbeta` (`10.1002/prot.10286`)
- **`SB-ROT-001` (Rotamer contours & backward-fit side chains):**
  - `williams2018_molprobity` (`10.1002/pro.3330`)
  - `hintze2016_rotamer_distributions` (`10.1002/prot.25039`)
  - `headd2009_autofix` (`10.1007/s10969-008-9045-8`)
- **`SB-RSR-001` (Coordinate restraint pricing vs. grid search):**
  - `afonine2018_rsr` (`10.1107/S2059798318006551`)
- **`SB-CC-001` (CC metrics, Q-score, EMRinger, overfitting):**
  - `afonine2018_validation` (`10.1107/S2059798318009324`)
  - `pintilie2020_qscore` (`10.1038/s41592-020-0731-1`)
  - `barad2015_emringer` (`10.1038/nmeth.3541`)
  - `lawson2021_validation` (`10.1038/s41592-020-01051-w`)
  - `scheres2012_overfitting` (`10.1038/nmeth.2115`)
- **`SB-MET-002` (Tetrahedral Zn coordination & false disulfides):**
  - `touw2016_zn` (`10.1107/S2059798316013036`)
