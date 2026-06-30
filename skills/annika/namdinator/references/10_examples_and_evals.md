# 10 — Examples, Fixtures, and Benchmark Cases

## Repository fixture (shipped in the baseline repo)

`namdinator/Namdinator_bash` @ `5814c947` ships:

- `3jd8.pdb` — PDB model, ID 3JD8.
- `emd_6640.map`, `emd_6640.mrc` — CCP4 electron-density maps.

**Fixture identity (verified 2026-06-30 via EMDB + RCSB APIs):** the model is
**PDB 3JD8** and the map is **EMD-6640** — full-length human NPC1 (Niemann–Pick
C1) at **4.43 Å** (EMDB/RCSB records; the EMDB title rounds it to "4.4 Å"). The
README's `emd_6644.mrc` is a **confirmed typo**: EMD-6644 is an unrelated
deposition (a viral IRES on the ribosome, PDB 5JUP, 3.3 Å). The shipped
filenames (`emd_6640.map` / `emd_6640.mrc`) are the correct ones; only the
README prose is wrong.

Smoke command (use the verified resolution):

```bash
./Namdinator_Generic.sh -p 3jd8.pdb -m emd_6640.mrc -r 4.43 -x
```

This remains a *candidate* — the identity and resolution are verified, but the
run itself has **not** been executed on a validated host in this project. Capture
`-h` and complete the run before treating its output as a fixture (ref 00).

## Paper benchmark (Kidmose et al. 2019) — numbers to preserve

39 deposited cryo-EM model/map pairs:

- **34/39 improved** on **at least one** of CC, clashscore, Ramachandran
  outliers (permissive criterion).
- CC: **22 improved, 11 unchanged, 6 deteriorated**.
- Clashscore: **17 improved, 18 similar, 4 deteriorated**.
- Ramachandran outliers: **23 reduced, 12 identical, 4 increased**.
- Five all-metric non-improvements (high-res full-atom): **6b44, 5ni1, 5sy1,
  5n9y, 3j9c**.

Cases worth citing as decision lessons:

- **6eny / EMDB-3906** — polyalanine peptide-loading-complex model: CC improved
  and Ramachandran outliers dropped, but clashscore **worsened** after full-atom
  conversion. Lesson: single metrics mislead; judge the balance (ref 07).
- **5o9g / EMD-3765** — systematic deposition shift caught quickly by Namdinator
  (rigid-body-shift example).
- **1ake → simulated 4ake map** — ~60,000 steps gave a large CC increase in a
  noise-free simulated map. Don't extrapolate the magnitude to real, noisy maps.
- **CorA, 3jcf/EMD-6551 → 3jch/EMD-6553** — needed a two-step low-pass strategy:
  low-pass (~20 Å) map + low G-scale + many steps, then original map + high
  G-scale + many steps (ref 06).

## Worked decision examples (how this skill should answer)

**A. "I have model.pdb and a 3.5 Å cryo-EM map; should I run Namdinator and
what command?"** → Verdict: suitable if the model is roughly docked and has no
critical ligands to preserve. Mode: local (or web if data are public). Preflight:
confirm docking; note HETATM removal; check VMD/NAMD2/Phenix present. Command:
`./Namdinator_Generic.sh -p model.pdb -m map.mrc -r 3.5 -x` (–x: Phenix RSR
recommended for cryo-EM). Watch-outs: ligands dropped; inspect all metrics, not
just CC. After: take `last_frame_rsr.pdb` if its metrics are better; inspect.

**B. "Can I upload my unpublished map to namdinator.au.dk?"** → Stop at the
privacy gate: web uploads are stored ~14 days server-side. For unpublished data,
recommend local planning instead. Don't produce a web-upload plan.

**C. "My model has a bound ligand and a metal."** → Warn that non-ATOM records
are removed by default and `-l` is unreliable / conflicts with `-x`. Plan: run
default, reinsert ligand/metal manually afterward and validate separately; or use
a tool better suited to keeping them (coot/phenix). Don't promise preservation.

**D. "A domain is rotated ~70° out of the density."** → A single default run
won't fix a large rigid rotation. Split into domains, manually rotate into
density (chimerax/coot), then run domain-wise or on the recombined model;
consider the two-step low-pass strategy (ref 06).

**E. "2.6 Å, already a good full-atom model with minor issues — worth it?"** →
Low expected benefit (this is the paper's non-improver regime). Suggest targeted
manual fixing + Phenix validation first; if tried, don't expect big gains and
watch for metric regressions.

**F. "Run died with 'Bad global bond count.'"** → Inspect the model after HETATM
removal in VMD/AutoPSF; remove problematic residues / fix connectivity; re-run.
Don't invent an unverified fix (ref 08).

## Note on these evals

`tests/eval_cases.md` and `tests/reference_answers.md` formalize cases A–F for
validating the skill. They check **read-only advisory behavior** — the skill
should produce the verdict/plan/warnings, and must **not** run anything.
