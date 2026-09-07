# Refresh the Phenix skill

Use for self-update, release/tutorial refresh, or source audit. Edit the knowledge bundle and authorized copies; software installation, live computation, uploads and publishing are separate tasks. Resolve the package from the loaded `SKILL.md`, compare copies and preserve local configuration and populated lessons. The public source is [StructAgent](https://github.com/bhgtiger/StructAgent/tree/main/skills/annika/phenix).

## Verified scope

Official 2.2.1-6174, installer dated 2026-09-03, verified 2026-09-07. The changelog heading says August 2026; cached home/index views initially still showed 2.2. Local observations labeled 2.0 remain historical.

## Source map

| Purpose | Authoritative source | Owning reference / action |
|---|---|---|
| Official vs nightly build/date | [Official vs nightly build/date](https://www.phenix-online.org/download/nightly_builds.cgi) | phenix_cli_reference.md |
| Version index cross-check | [Version index cross-check](https://www.phenix-online.org/download/get_versions.cgi) | phenix_cli_reference.md |
| Pinned release changes | [Pinned release changes](https://phenix-online.org/version_docs/2.2.1-6174/CHANGES) | phenix_cli_reference.md; conflicting entrypoint caveats |
| Current changes discovery | [Current changes discovery](https://phenix-online.org/documentation/CHANGES) | follow new release into version_docs |
| RSR manual/examples/video | [RSR manual/examples/video](https://phenix-online.org/documentation/reference/real_space_refine.html) | phenix_cli_reference.md; EM presets if verified |
| LigandFit input and tutorial examples | [LigandFit input and tutorial examples](https://phenix-online.org/documentation/reference/ligandfit.html) | phenix_cli_reference.md; ligand workflow |
| Reciprocal-space manual | [Reciprocal-space manual](https://phenix-online.org/documentation/reference/refinement.html) | phenix_cli_reference.md; X-ray presets if verified |

## Refresh procedure

1. Read the entrypoint and affected references/scripts. Preserve a before-diff outside the installable package. Keep the upstream documentation version, historical tested baseline and installed environment as three separate facts.
2. Open the build table and actual release changelog, not only the homepage or a cached excerpt. Record the full build number and separate nightly/development status from official release. Compare PHIL defaults, replacement/deprecated commands, map formats, validation output and tutorial examples. For ligand workflows inspect map_in and resolution rather than carrying forward an X-ray-only assumption. If documentation sources conflict, use release-specific sources and label the unresolved discrepancy; an online schema is still not the installed schema.
3. Save selected page/source snapshots outside the skill with URL, retrieval date, HTTP/error status, content hash and claim-to-reference mapping. Record failed/partial retrievals. A working link or unchanged hash does not prove full coverage. Do not ship transcripts, datasets, raw HTML or run logs inside the package.
4. Edit the owning reference and correct contradictory entrypoint advice in place. Prefer short scenario → decision → verification guidance with direct links and version gates. Keep detailed refresh instructions here, loaded on demand. Preserve historical test evidence without turning it into current compatibility claims.
5. Rehearse map-input LigandFit, RSR with a custom run strategy, a historical Phenix 2.0 failure and cryo-EM validation export. Keep X-ray and EM lanes separate and wrapper dashed options separate from native PHIL. Inspect scripts/runner.py and preset diffs without running refinement; execution validation needs a separately authorized fixture.
6. Run the available skill-creator `quick_validate.py` on this folder and check new local links, external sources and the diff. Record pre-existing failures separately. For documentation-only changes use static/routing checks; do not invent a new locally validated version. Synchronize only authorized copies, preserving private configuration/lessons, and report additions, tested scope and remaining gaps.

Example request: “Use $phenix to refresh its releases and official tutorials, preserving the validated baseline and execution boundaries.”
