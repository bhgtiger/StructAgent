# Refresh the Coot skill

Use for self-update, release/tutorial refresh, or source audit. Edit the knowledge bundle and authorized copies; software installation, live computation, uploads and publishing are separate tasks. Resolve the package from the loaded `SKILL.md`, compare copies and preserve local configuration and populated lessons. The public source is [StructAgent](https://github.com/bhgtiger/StructAgent/tree/main/skills/annika/coot).

## Verified scope

Upstream non-prerelease 1.3.3 (2026-08-13), checked 2026-09-07. CCP4 update 016 packages 1.2. Existing local classic-lane observations were not rerun on 1.3.3.

## Source map

| Purpose | Authoritative source | Owning reference / action |
|---|---|---|
| Release tags and fixes | [Release tags and fixes](https://github.com/pemsley/coot/releases) | docs-and-source.md; version-specific routing |
| Machine-readable release dates/status | [Machine-readable release dates/status](https://api.github.com/repos/pemsley/coot/releases) | docs-and-source.md |
| Manual/classic scripting | [Manual/classic scripting](https://www2.mrc-lmb.cam.ac.uk/personal/pemsley/coot/web/docs/coot.html) | docs-and-source.md; architecture.md; affected classic scripts |
| Current tutorial/API discovery | [Current tutorial/API discovery](https://pemsley.github.io/coot/) | docs-and-source.md |
| Command-terminal language | [Command-terminal language](https://pemsley.github.io/coot/doc/command-reference.html) | docs-and-source.md; distinguish Python/Chapi/terminal |
| Worked building tutorial | [Worked building tutorial](https://pemsley.github.io/coot/blog/2023/05/05/coot-tutorial-in-2023.html) | docs-and-source.md |

## Refresh procedure

1. Read the entrypoint and affected references/scripts. Preserve a before-diff outside the installable package. Keep the upstream documentation version, historical tested baseline and installed environment as three separate facts.
2. Compare release notes for the installed branch with upstream and distributor packages. Follow changed tutorial and API links from the official index; inspect the matching release-tagged source before adding a callable. An API name in a release note proves neither a Python signature nor headless support. Historical local corpus paths are optional provenance; the public package must work without them.
3. Save selected page/source snapshots outside the skill with URL, retrieval date, HTTP/error status, content hash and claim-to-reference mapping. Record failed/partial retrievals. A working link or unchanged hash does not prove full coverage. Do not ship transcripts, datasets, raw HTML or run logs inside the package.
4. Edit the owning reference and correct contradictory entrypoint advice in place. Prefer short scenario → decision → verification guidance with direct links and version gates. Keep detailed refresh instructions here, loaded on demand. Preserve historical test evidence without turning it into current compatibility claims.
5. Rehearse manual ligand building, classic script export, a 1.3.3 mouse fix, and a terminal-command request. Keep explicit molecule IDs, active-map selection, output checks, and linked-chemistry crash guards. Documentation-only refreshes do not justify claiming new runtime coverage.
6. Run the available skill-creator `quick_validate.py` on this folder and check new local links, external sources and the diff. Record pre-existing failures separately. For documentation-only changes use static/routing checks; do not invent a new locally validated version. Synchronize only authorized copies, preserving private configuration/lessons, and report additions, tested scope and remaining gaps.

Example request: “Use $coot to refresh its releases and official tutorials, preserving the validated baseline and execution boundaries.”
