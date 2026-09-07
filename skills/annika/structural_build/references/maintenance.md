# Update the structural-build workflow skill

Use when asked to refresh this orchestrator's software routes, versions or
tutorials. This is a workflow integration skill, so it has no single upstream
software version. Its scientific decision strategy remains separate.

## Source map

| Owner | Inspect |
|---|---|
| ChimeraX / AlphaFold retrieval | [Production metadata](https://www.rbvi.ucsf.edu/chimerax/data/release-info/production.json), [change log](https://www.rbvi.ucsf.edu/trac/ChimeraX/wiki/ChangeLog); use the chimerax skill for current version/commands. |
| ISOLDE | [Official documentation](https://tristanic.github.io/isolde/); use the isolde skill for the compatible ChimeraX/bundle pair, preflight and export. |
| Phenix | [Documentation](https://phenix-online.org/documentation/); phenix owns real-space/reciprocal-space refinement, LigandFit and validation details. |
| CCP4 / Servalcat / AceDRG | [CCP4 updates](https://www.ccp4.ac.uk/ccp4-9-0-updates/); use ccp4 for the suite and separately versioned components. |
| Rosetta EMERALD | [Method and code/data links](https://www.nature.com/articles/s41467-023-36732-5); emerald owns XML, resource and release compatibility. |
| Merizo | [Releases](https://github.com/psipred/Merizo/releases), [README/tutorial examples](https://github.com/psipred/Merizo), [parser/implementation](https://github.com/psipred/Merizo/blob/main/predict.py); see [Merizo integration](merizo.md). |

## Current review — 2026-09-07

Merizo latest tagged release is **v1.0.0 (2023-10-13)**, while inspected main
is **41d12fb84e6e8fdb586c2c859d12161dc7bb5bfd (2025-05-22)**.
The latter supplies the current integration notes; no new execution was tested.
Other tool versions belong to their owning skills and installed environments,
not a duplicated version table here.

## Refresh procedure

1. Compare repository/loaded copies and preserve a diff outside the skill.
   Read each relevant tool skill's maintenance/current-version notes; if it is
   unavailable, consult its official sources without inventing local paths.
2. Inspect actual release status and tutorial changes. Record URL, date,
   revision, retrieval status, hash and owning reference outside the package.
   Separate released, development, source-verified and host-tested behavior.
3. Trace each changed tool capability through the task router and data handoff.
   Check model/map coordinate frames, chain/residue identifiers, map origin,
   restraint formats, half-map use, GUI requirements and output preservation.
   Edit conflicting commands in place or delegate exact commands to the owner.
4. Review Merizo's README, parser and output code together. Check chain
   selection, iterative segmentation and residue-range parsing before using
   domain boundaries to edit a model. A tutorial threshold or duration is not a
   universal criterion for trimming, simulation or validation.
5. Keep the orchestrator compact; put tool mechanics in owner references.
   Run the available skill validator and local-path checks; rehearse
   domain fitting, ligand placement and self-update routing. The legacy
   structural_build identifier contains an underscore; report strict
   hyphen-only validator failures rather than silently renaming an installed
   skill during a documentation refresh.
6. Report changes and gaps, then synchronize authorized copies while preserving
   local lessons/configuration. Software upgrades, simulations and publishing
   require their own task scope; refreshing documentation needs no runtime probe.
