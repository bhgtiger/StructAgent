# Boundaries and v1 scope

## What this skill owns

Execution of named CCP4 CLI binaries:

- **v1 wrappers**: `refmac5` (via `run_refmac5.sh`), `acedrg` (via `run_acedrg.sh`).
- **v1 dispatcher**: `run_ccp4.sh` for any other CCP4 binary the user names explicitly — `freerflag`, `cad`, `mtzdump`, `sftools`, `pdbset`, `pdbcur`, plus the deferred binaries below when invoked explicitly.
- **v1 preflight**: `mtz_preflight.py` for column / FreeR / cell / symmetry checks before refinement and autobuild workflows.

## What this skill does NOT do

- **Strategic decisions** ("Refmac5 or `phenix.refine`?", "TLS yes/no?", "MR before density modification?") → `structural-strategy`.
- **Coot scripted runs** (Refmac-from-Coot recipes, ligand fitting, water picking) → `coot`. Coot ships with the CCP4 distribution but is governed by its own skill.
- **Phenix CLI** (`phenix.refine`, `phenix.elbow`, `phenix.real_space_refine`, `phenix.molprobity`) → `phenix`. Refmac5/AceDRG/Phaser are CCP4-owned even when a Phenix workflow could solve the same problem.
- **ChimeraX-driven fitting** (rigid-body fitmap, ISOLDE) → `chimerax`.
- **PDB-REDO**: not a local CCP4 CLI binary — out of scope.
- **ARP/wARP, SHELX**: licensing and install vary; out of v1 unless and until the team confirms a target environment.
- **CCP4 Cloud** headless jobs: a separate transport / auth surface; if needed, give it its own reference, do not graft it onto local wrappers.
- **Auto-generation of FreeR flags inside refinement**: forbidden. See SKILL.md "Failure contract".

## Deferred to later versions

These binaries are listed in the trigger description so the skill is invoked when a user names them, but no dedicated wrapper exists in v1. Use `run_ccp4.sh` to execute them.

| Binary | Workflow | Notes |
| --- | --- | --- |
| `phaser` | molecular replacement | Many decision branches; needs an MR-specific preflight before a wrapper is worthwhile. |
| `molrep` | molecular replacement | Smaller surface than Phaser; could land alongside the Phaser wrapper. |
| `cbuccaneer` | autobuild (X-ray) | Note `cbuccaneer`, not `buccaneer`; needs a phase-column preflight. |
| `cnautilus` | autobuild (nucleic acids) | Note `cnautilus`, not `nautilus`. |
| `aimless`, `pointless`, `ctruncate` | data reduction | Worth a dedicated data-processing slice; sequencing matters. |
| `privateer` | carbohydrate validation | Explicit trigger only; no implicit invocation. |
| `servalcat`, `refmacat` | crystallographic / SPA refinement | Servalcat covers crystallography and cryo-EM SPA; treat as user-invoked through `run_ccp4.sh` until an explicit need lands. |

## Neighbour skill updates (do after v1 lands)

- `structural-strategy/references/refinement.md` — when to pick Refmac5, Servalcat/refmacat, or `phenix.refine`.
- `structural-strategy/references/model-building.md` (or `fitting.md`) — MR / autobuild entry points: Phaser, Molrep, Buccaneer, Nautilus.
- `phenix/SKILL.md` — one-line note that Refmac5/AceDRG/Phaser are CCP4-owned.
- `coot/SKILL.md` — preserve "run Refmac from Coot" recipes there, but note that standalone `refmac5` CLI execution belongs to `ccp4`.

Do not move Coot recipes here just because Coot ships inside the CCP4 distribution.

## Open questions (carry forward)

1. CCP4 9.0.x only, or do we need to support 8.x? Current CCP4 downloads list 9.0.x as the supported release; the macOS package on 2026-04-25 was v9.0.015 dated 2026-04-17.
2. Where will redistributable MTZ/PDB fixtures come from for integration tests?
3. Should `servalcat` get a dedicated v1.1 wrapper, or stay dispatcher-only?
4. Headless CCP4 Cloud jobs — separate skill / reference, if at all.
5. ARP/wARP and SHELX licensing/install assumptions for the target users.
