# 01 — Source Map: where every claim comes from

Cite the origin of any behavioral claim. The two repos differ at the behavior
level, so "Namdinator does X" is incomplete without "(repo@commit)".

## Primary sources

| Source | Identifier | Use it for |
|---|---|---|
| Baseline repo | `github.com/namdinator/Namdinator_bash` @ `5814c9474a41f7cbcca785ce83027227073d656f` (2019-10-16, branch `master`, GPL-3.0, Shell) | Default for flags, defaults, output filenames, processing steps. Key script `Namdinator_Generic.sh`. |
| Historical repo | `github.com/rukibuki/Namdinator` @ `f713537b3972fdaf1206a7788e405fdc00bcb545` (2018-09-14, GPL-3.0) | Older behavior. User named it explicitly; keep as evidence. Do **not** use as baseline unless asked to target that exact older repo. |
| Web service | `https://namdinator.au.dk` (home/form/manual/download/about/terms, snapshots 2026-06-30) | Web fields, limits, privacy, web-user guidance. Home page showed "Total successful runs: 17955". |
| Method paper | Kidmose et al. 2019, IUCrJ 6(4):526-531, DOI `10.1107/S2052252519007619`, PMCID `PMC6608625` (CC BY) | Intended use, limitations, benchmark claims, parameter heuristics. |

The web download page points users to `https://github.com/namdinator/`, which is
why the organization repo (not the personal one) is the baseline.

## Baseline repo file layout

- `README.md` — short install/run guidance; warns to use `Namdinator_Generic.sh`
  rather than untested variants.
- `Namdinator_Generic.sh` — generic Bash entry point for non-local setups
  (**default target for this skill**).
- `Namdinator_current.sh` — center-local version with module loads (Aarhus
  site-specific; don't recommend generically).
- `Untested_Namdinator_versions/` — explicitly not recommended by README.
- Fixture: `3jd8.pdb`, `emd_6640.map`, `emd_6640.mrc` (README says
  `emd_6644.mrc`, now confirmed as a typo; EMD-6640 + PDB 3JD8 are human NPC1
  at 4.43 Å; see ref 10).

## Baseline vs. historical: behavior-level differences

`namdinator/Namdinator_bash` is **not** just a metadata move from
`rukibuki/Namdinator`. Compared with the historical repo it:

- updates contacts in `README.md`;
- adds `top_all36_carb.rtf` (carbohydrate topology);
- adds *untested* versions for glycans, MTZ, and unit-cell handling;
- changes post-MD processing in `Namdinator_Generic.sh`:
  - removes the older `sed` B-factor rewrite on `last_frame_his.pdb`;
  - uses `phenix.pdbtools modify.adp.set_b_iso`;
  - runs ADP-only `phenix.real_space_refine` on input and last-frame models;
  - handles `.map` input for VMD CCC checks via an `.mrc` symlink;
  - parses `CC_mask` from `phenix.map_model_cc` logs (older code keyed on
    `CC_volume`/`masked` patterns).

Implication: a claim taken from the historical repo (e.g. older B-factor or CC
parsing) may be wrong for the baseline. Always say which repo a behavioral claim
comes from.

## Trust notes

- Exact CLI/output behavior → source + live runtime, **not** the paper.
- Intended scientific use + benchmark evidence → Kidmose et al. 2019.
- Current web form/limits/privacy → `namdinator.au.dk` snapshots.
- Community evidence is thin; do not rely on GitHub issues for troubleshooting
  coverage (0 issues observed in both repos).
