# Refresh the CCP4 skill

Use for self-update, release/tutorial refresh, or source audit. Edit the knowledge bundle and authorized copies; software installation, live computation, uploads and publishing are separate tasks. Resolve the package from the loaded `SKILL.md`, compare copies and preserve local configuration and populated lessons. The public source is [StructAgent](https://github.com/bhgtiger/StructAgent/tree/main/skills/annika/ccp4).

## Verified scope

CCP4 9.0.017 (2026-08-05); update table retrieved 2026-09-07. Component versions are independent. No new local execution baseline was established.

## Source map

| Purpose | Authoritative source | Owning reference / action |
|---|---|---|
| Suite patches/platform differences | [Suite patches/platform differences](https://www.ccp4.ac.uk/ccp4-9-0-updates/) | install.md; ligands.md; mtz_columns.md |
| Installation and updater | [Installation and updater](https://download.ccp4.ac.uk/doc/installation.html) | install.md; preserve setup discovery and explicit override |
| Named CLI manual index | [Named CLI manual index](https://www.ccp4.ac.uk/html/) | refmac5.md; mtz_columns.md; ligands.md |
| AceDRG practical task | [AceDRG practical task](https://cloud.ccp4.ac.uk/manuals/html-taskref/doc.task.MakeLigand.html) | ligands.md |
| Servalcat releases/source | [Servalcat releases/source](https://github.com/keitaroyam/servalcat) | ligands.md; boundaries.md; explicit named-tool requests only |

## Refresh procedure

1. Read the entrypoint and affected references/scripts. Preserve a before-diff outside the installable package. Keep the upstream documentation version, historical tested baseline and installed environment as three separate facts.
2. Read the suite table down to its last update, including dates and platform columns. Check affected binary versions separately and compare changes to the wrapper interface. Review AceDRG chemistry/link examples and MTZ/FreeR handling; newer GUI task defaults do not change the named CLI contract. Installation-page TLS failed in the direct snapshot fetch (browser copy was readable); do not infer every platform was reverified.
3. Save selected page/source snapshots outside the skill with URL, retrieval date, HTTP/error status, content hash and claim-to-reference mapping. Record failed/partial retrievals. A working link or unchanged hash does not prove full coverage. Do not ship transcripts, datasets, raw HTML or run logs inside the package.
4. Edit the owning reference and correct contradictory entrypoint advice in place. Prefer short scenario → decision → verification guidance with direct links and version gates. Keep detailed refresh instructions here, loaded on demand. Preserve historical test evidence without turning it into current compatibility claims.
5. Rehearse an AceDRG charge-state question, an mmCIF conversion failure and a Refmac request with missing FreeR labels. Preserve explicit labels, no silent FreeR generation, dry-run and overwrite guards.
6. Run the available skill-creator `quick_validate.py` on this folder and check new local links, external sources and the diff. Record pre-existing failures separately. For documentation-only changes use static/routing checks; do not invent a new locally validated version. Synchronize only authorized copies, preserving private configuration/lessons, and report additions, tested scope and remaining gaps.

Example request: “Use $ccp4 to refresh its releases and official tutorials, preserving the validated baseline and execution boundaries.”
