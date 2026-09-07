# Refresh the EMERALD / Rosetta skill

Use for self-update, release/tutorial refresh, or source audit. Edit the knowledge bundle and authorized copies; software installation, live computation, uploads and publishing are separate tasks. Resolve the package from the loaded `SKILL.md`, compare copies and preserve local configuration and populated lessons. The public source is [StructAgent](https://github.com/bhgtiger/StructAgent/tree/main/skills/annika/emerald).

## Verified scope

Rosetta latest numbered release 3.15 (2025-09-09), checked 2026-09-07; no independent EMERALD version. This is documentation coverage, not a locally tested 3.15 protocol.

## Source map

| Purpose | Authoritative source | Owning reference / action |
|---|---|---|
| Numbered release vs snapshots | [Numbered release vs snapshots](https://downloads.rosettacommons.org/downloads/academic/) | install.md |
| New protocols/build changes | [New protocols/build changes](https://docs.rosettacommons.org/docs/latest/Release-Notes) | install.md; xml_template.md |
| Method and actual code/data links | [Method and actual code/data links](https://www.nature.com/articles/s41467-023-36732-5) | cli_reference.md; xml_template.md |
| Maintainer correction of old minimum | [Maintainer correction of old minimum](https://forum.rosettacommons.org/node/11748) | install.md; entrypoint prerequisite caveat |
| Current mover implementation/schema | [Current mover implementation/schema](https://github.com/RosettaCommons/rosetta/blob/main/source/src/protocols/ligand_docking/GALigandDock/GALigandDock.cc) | xml_template.md; pin installed release before using signatures |
| Tutorial versus historical capture discovery | [Tutorial versus historical capture discovery](https://docs.rosettacommons.org/demos/latest/Home) | follow actual protocol links, never guess paths |

## Refresh procedure

1. Read the entrypoint and affected references/scripts. Preserve a before-diff outside the installable package. Keep the upstream documentation version, historical tested baseline and installed environment as three separate facts.
2. Check numbered releases and development snapshots separately. Follow the paper’s real supplementary/code links and compare density-skeleton initialization, site definition, scoring, stage schedule and independent-trajectory confidence against the bundled template. A generic density score is not proof of the complete EMERALD protocol. Read installed mover schema before claiming XML options work. The guessed public/EMERALD demo URL was unavailable, and current protocol-capture assets were not validated; keep this gap explicit.
3. Save selected page/source snapshots outside the skill with URL, retrieval date, HTTP/error status, content hash and claim-to-reference mapping. Record failed/partial retrievals. A working link or unchanged hash does not prove full coverage. Do not ship transcripts, datasets, raw HTML or run logs inside the package.
4. Edit the owning reference and correct contradictory entrypoint advice in place. Prefer short scenario → decision → verification guidance with direct links and version gates. Keep detailed refresh instructions here, loaded on demand. Preserve historical test evidence without turning it into current compatibility claims.
5. Rehearse a 2023.06 missing-option failure, a seed-PDB request and a confidence interpretation. Inspect what run_emerald.sh actually assembles: check_env.sh is a presence probe, not a version/schema validator. Preserve output and input guards. If scripts/XML change, add an offline argument/schema check; do not run docking or install Rosetta for a documentation refresh.
6. Run the available skill-creator `quick_validate.py` on this folder and check new local links, external sources and the diff. Record pre-existing failures separately. For documentation-only changes use static/routing checks; do not invent a new locally validated version. Synchronize only authorized copies, preserving private configuration/lessons, and report additions, tested scope and remaining gaps.

Example request: “Use $emerald to refresh its releases and official tutorials, preserving the validated baseline and execution boundaries.”
