# Refresh the Namdinator skill

Use for self-update, release/tutorial refresh, or source audit. Edit the knowledge bundle and authorized copies; software installation, live computation, uploads and publishing are separate tasks. Resolve the package from the loaded `SKILL.md`, compare copies and preserve local configuration and populated lessons. The public source is [StructAgent](https://github.com/bhgtiger/StructAgent/tree/main/skills/annika/namdinator).

## Verified scope

Organization master is unchanged at 5814c9474a41f7cbcca785ce83027227073d656f (2019-10-16), checked 2026-09-07; releases list empty. No live runtime has ever been validated by this skill. June 2026 web snapshots were not renewed.

## Source map

| Purpose | Authoritative source | Owning reference / action |
|---|---|---|
| Repository/README | [Repository/README](https://github.com/namdinator/Namdinator_bash) | 01_source_map.md; 05_core_workflow.md |
| Exact head/date | [Exact head/date](https://api.github.com/repos/namdinator/Namdinator_bash/commits/master) | 01_source_map.md |
| Release status | [Release status](https://github.com/namdinator/Namdinator_bash/releases) | 01_source_map.md |
| Pinned generic CLI | [Pinned generic CLI](https://github.com/namdinator/Namdinator_bash/blob/5814c9474a41f7cbcca785ce83027227073d656f/Namdinator_Generic.sh) | 02_installation_environment.md; 03_cli_and_web_surface.md; 04_input_output_model.md |
| Live web index and linked manual/terms | [Live web index and linked manual/terms](https://namdinator.au.dk/) | 03_cli_and_web_surface.md; 09_privacy_license_safety.md |
| Scientific method paper | [Scientific method paper](https://doi.org/10.1107/S2052252519007619) | 05_core_workflow.md; 07_validation_outputs.md; 10_examples_and_evals.md |
| Phenix command migration | [Phenix command migration](https://phenix-online.org/version_docs/2.2.1-6174/CHANGES) | 02_installation_environment.md |

## Refresh procedure

1. Read the entrypoint and affected references/scripts. Preserve a before-diff outside the installable package. Keep the upstream documentation version, historical tested baseline and installed environment as three separate facts.
2. Compare org repository head, release list, README and generic script before changing the pinned baseline. Treat untested/site-local variants separately. Diff getopts, dependencies, model transformations, log parsers and output names. Verify the website independently; its backend need not match GitHub. TLS retrieval failures in this refresh leave current forms/manual/retention unverified: keep June snapshots historical and do not disable certificate checks. An unchanged Bash commit does not establish modern dependency compatibility.
3. Save selected page/source snapshots outside the skill with URL, retrieval date, HTTP/error status, content hash and claim-to-reference mapping. Record failed/partial retrievals. A working link or unchanged hash does not prove full coverage. Do not ship transcripts, datasets, raw HTML or run logs inside the package.
4. Edit the owning reference and correct contradictory entrypoint advice in place. Prefer short scenario → decision → verification guidance with direct links and version gates. Keep detailed refresh instructions here, loaded on demand. Preserve historical test evidence without turning it into current compatibility claims.
5. Rehearse CLI vs web temperature/step differences, ligand-loss warning, modern Phenix CC parsing and the corrected NPC1 fixture. Preserve the read-only advisory scope, no form submission, no model/map mutation and no live Namdinator execution. Updating knowledge does not remove those boundaries.
6. Run the available skill-creator `quick_validate.py` on this folder and check new local links, external sources and the diff. Record pre-existing failures separately. For documentation-only changes use static/routing checks; do not invent a new locally validated version. Synchronize only authorized copies, preserving private configuration/lessons, and report additions, tested scope and remaining gaps.

Example request: “Use $namdinator to refresh its releases and official tutorials, preserving the validated baseline and execution boundaries.”
