# Annika software skill refresh — 2026-09-07

Reviewed all 23 folders under `skills/annika`. Updated 21 software or software
workflow skills, including the already refreshed CryoSPARC reference. Skipped
`annika-log` (project logging) and `structural-strategy` (scientific decision
strategy); neither owns a software release or executable interface.

## Pattern taken from CryoSPARC

The preceding CryoSPARC update (repository commit `b25e0e0`) already provides
a compact entrypoint, on-demand references, a source-specific
`references/maintenance.md`, release/tutorial review, evidence storage outside
the skill, validation, and synchronization of authorized copies.

This refresh adds that maintenance route to the other 20 software/workflow
skills. Each guide names its own upstream sources and affected references.
Self-update means maintaining software knowledge; runtime probes, installations,
weight/data downloads, scientific jobs and publishing retain their task scope.
The instructions preserve existing authorization and local configuration.

## Verified software and substantive changes

All dates below are documentation/source checks on 2026-09-07. They are not
new runtime validation dates. The linked maintenance references contain primary
source URLs, release dates, pins and verification limits.

| Skill | Verified upstream scope | Result |
|---|---|---|
| [Boltz](../skills/annika/boltz/references/maintenance.md) | v2.2.1; June GPU baseline preserved | Compared current prediction guide; clarified model-specific sampling defaults and tutorial/MSA reuse checks. |
| [CCP4](../skills/annika/ccp4/references/maintenance.md) | 9.0.017 | Separated suite/component/dictionary versions; updated installation and ligand guidance. |
| [ChimeraX](../skills/annika/chimerax/references/maintenance.md) | Production 1.12 | Distinguished development Python/NumPy changes; checked fitting/export tutorials and coordinate handling. |
| [ColabFold](../skills/annika/colabfold/references/maintenance.md) | v1.6.2; newer main notebook separate | Added Pallas/compile/cache guidance and OpenFold3 notebook discovery without claiming AF3 runtime support. |
| [Coot](../skills/annika/coot/references/maintenance.md) | Standalone 1.3.3; CCP4 bundle separate | Updated tutorial/source discovery and terminal/Python/Chapi distinctions; repaired malformed YAML. |
| [CryoAtom](../skills/annika/cryoatom/references/maintenance.md) | Released v2.1.0; retained untagged 2.1.1 pin | Added official example routing and release provenance; kept image/source evidence separate. |
| [CryoAtom advisor](../skills/annika/cryoatom-advisor/references/maintenance.md) | Static v2.1.0 pin | Added partial-sequence omission and absent timing-log caveats; removed an accidental host assertion. |
| [cryoDRGN](../skills/annika/cryodrgn-skill/references/maintenance.md) | Stable 4.3.1; tested 4.2.1 preserved | Updated dashboard, WarpTools/CTF and tutorial guidance; corrected old beta-only wording. |
| [crYOLO](../skills/annika/cryolo-skill/references/maintenance.md) | Changelog top 1.9.9 | Added current tutorial routing, model/filter matching and CBOX selection guidance. |
| [CryoSPARC](../skills/annika/cryosparc/references/maintenance.md) | 5.0.7; tools 5.0.3 | Rechecked release/tutorial/workflow indices; retained the preceding refresh, corrected residual v4.6 wording and added cached-release conflict handling. |
| [DAQplugin](../skills/annika/daqplugin/references/maintenance.md) | Toolshed 1.0.7; GitHub artifact 1.0.1; source 1.0.8 | Separated channels; updated backend detection and residue-plot workflow. |
| [DeepEMhancer](../skills/annika/deepemhancer-skill/references/maintenance.md) | 0.17; source pin unchanged | Corrected documented masked-input normalization exceptions and decision guidance. |
| [EMERALD](../skills/annika/emerald/references/maintenance.md) | Rosetta numbered release 3.15 | Corrected minimum-version claims, XML/confidence descriptions and documented unsupported seed behavior. |
| [ISOLDE](../skills/annika/isolde/references/maintenance.md) | 1.12.1 macOS; 1.12.0 Linux/Windows, with ChimeraX 1.12.x | Added public preflight/status/validation/tutorial guidance; made historical chemistry workarounds conditional. |
| [Mask](../skills/annika/mask/references/maintenance.md) | ChimeraX 1.12 and current CryoSPARC v5 docs | Corrected padding units, Gaussian/cosine distinction, molmap recommendations, filtering and negative clamp guidance. |
| [ModelAngelo](../skills/annika/modelangelo/references/maintenance.md) | v1.0.18; main matches tag | Added current tutorial routing and nucleotide-omission checks; removed installation-path assumptions. |
| [Namdinator](../skills/annika/namdinator/references/maintenance.md) | Untagged source `5814c947` unchanged | Preserved advisory scope; flagged legacy Phenix command/output parsing and incomplete hosted-service verification. |
| [Phenix](../skills/annika/phenix/references/maintenance.md) | Official 2.2.1-6174, 2026-09-03 | Corrected cryo-EM LigandFit support; qualified historical ADP, reference-model, helix and flip advice. |
| [RELION](../skills/annika/relion/references/maintenance.md) | Stable 5.0.1; 5.1.0 prerelease | Updated compiler/GPU caveats and version-gated amyloid/tomography guidance. |
| [Structural build](../skills/annika/structural_build/references/maintenance.md) | Owner-tool versions; Merizo v1.0.0 versus newer source | Added Merizo chain/range/occupancy handoff and corrected stale Phenix/ISOLDE instructions. |
| [Topaz](../skills/annika/topaz-skill/references/maintenance.md) | 0.3.20 | Routed to pinned notebooks instead of stale ReadTheDocs; added preload and API caveats. |

## Validation and remaining limits

- The standard skill-creator validator passes **22 of 23** Annika skills
  (**20 of 21** updated skills). The remaining failure is the pre-existing
  `structural_build` identifier: strict Codex validation requires hyphens.
  Its name/folder were preserved to avoid changing installed references.
- Repaired existing malformed or oversized frontmatter where touched. Moved
  package-specific metadata under supported `metadata` without changing its
  values. The cryoDRGN static validator now accepts that layout and its legacy
  top-level equivalent.
- Offline checks passed: Boltz static validation, ColabFold and CryoAtom package
  validators/self-tests, cryoDRGN static validation, and DeepEMhancer static
  validation. New/changed local Markdown links resolve; the diff passes
  whitespace checks. Independent reviews checked release evidence and
  cross-skill routing/chemistry consistency.
- No scientific software was installed, upgraded or run. Existing local
  validation claims and runtime pins were preserved. Most changes are Markdown;
  the only Python change is the cryoDRGN package validator.
- Namdinator's current hosted form/terms could not be verified because direct
  retrieval failed TLS validation. Its older snapshots remain historical.
  DeepEMhancer weight availability was not tested.
- EMERALD's existing seed wrapper assembles conflicting inputs and does not
  configure the intended XML initial pool. It is explicitly unsupported pending
  a tested repair. Historical ISOLDE monitored scripts still require adaptation
  before 1.12 execution; mask defaults were documented, not recalibrated.

Release-page caches sometimes lagged direct upstream data (notably Phenix and
ColabFold). Explicit releases, official build tables and APIs resolved those
disagreements. Source snapshots, hashes, failures, claim mappings, before/after
entrypoint sizes and validation results were saved in the external maintenance
workspace; they are not runtime dependencies or installable skill content.

## Future use

Invoke an individual skill with a request such as:
“Update this skill's software versions and official tutorials, preserving
historical test evidence.” Its entrypoint routes to its own maintenance guide.
For a collection refresh, enumerate the requested folders, skip non-software
skills, partition disjoint owners, and review cross-tool handoffs after merging
the edits. Synchronize reviewed files only into the requested repository or
authorized installations, preserving each installation's configuration.
