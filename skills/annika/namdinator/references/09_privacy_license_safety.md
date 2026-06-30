# 09 — Privacy, License, and Execution Safety

## Web-service privacy (gate web use on this)

The terms page at `https://namdinator.au.dk/terms` states that uploaded and
processed data are **stored on the Namdinator servers for 14 days** before
automatic deletion, reachable through a **randomized link** with a "remove from
site" button. The privacy policy link points to Aarhus University's general
privacy page (the site's own `/privacy` path returned a 404 during capture).

**Skill rule — ask before recommending web use:** is the model/map **public or
safe to upload?** If the data are unpublished, embargoed, proprietary,
patient-derived, regulated, or otherwise sensitive, **recommend local planning
instead** and state plainly that web use means a third-party server holds the
data for up to 14 days. This is a user decision; surface it, never make it for
them by quietly producing a web-upload plan.

Also: the upload JS rejects filenames with spaces or characters like `( ) # &` —
recommend simple ASCII names.

## Licenses

- **Namdinator** source repos are **GPL-3.0**.
- **Kidmose et al. 2019** is **CC BY** (via PMC).
- Dependencies carry their own terms and are **not freely redistributable**:
  - **Rosetta** — RosettaCommons license / download workflow.
  - **Phenix** — its own download/license terms.
  - **VMD / NAMD** — their own license/download terms.

This skill ships **no** Namdinator code, **no** third-party binaries, and **no**
map/model data. When advising installation, point the user to each tool's
official channel; never assume redistribution rights or bundle binaries.

## Execution-safety rules (for any FUTURE executor — not this version)

This version does not execute. If a later version (v3) ever runs Namdinator, it
must:

- require **explicit user confirmation** before each run;
- write only to a **dedicated output directory**; never overwrite the input
  model or map;
- capture stdout/stderr and the generated scripts;
- record exact tool **versions** and the environment variables used;
- state that the output is **not publication-ready** without manual inspection;
- never auto-submit the web form or call the web backend (the backend contract
  is unknown; only the HTML/JS form was observed, never submitted).

Until a validated Linux runtime and a captured fixture exist (SKILL §9), keep to
read-only advice and say so rather than improvising execution.
