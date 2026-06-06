# 07 · Safety, license, and privacy

Route **every** install / use / commercial / data question through this file.

## License — NOT legal advice

> **This is a plain-language summary of captured license text, not legal advice.** For any
> real licensing/commercial decision, read the official license in full and consult a
> qualified person. Direct commercial users to contact the crYOLO/SPHIRE authors via the
> official docs.

**Captured verbatim** from the dedicated license page,
<https://cryolo.readthedocs.io/en/stable/other/license.html>, fetched **2026-06-05**
(source pin `1.9.9` / `30039bde34d65c179541568b0c27f09916ac5652`):

> This is the SPHIRE-crYOLO Complimentary Science Software License Agreement, which applies
> to all software products available for download from the SPHIRE-crYOLO website(s), unless
> labeled as something other than complimentary.

> The Software is licensed for non-commercial academic and research purposes only. All
> software products available for download from associated website(s), unless labeled
> otherwise, are provided royalty free.

> Use of the software is permitted for lawful scientific research purposes only. It is
> explicitly prohibited to use the SPHIRE-crYOLO software or parts of it, whether modified
> or not, for commercial purposes or operational use.

> If you do not agree with our Complimentary Science Software License Agreement you must
> not use our software products - this Complimentary Science Software License Agreement
> will then not apply to you.

**What to tell the user:**

- crYOLO is under a **Complimentary Science Software License**: **non-commercial academic
  and research use only**, royalty-free.
- **Commercial purposes or operational use are explicitly prohibited.** Company/for-profit
  use is not covered by this license → **contact the authors** (path via the official
  docs) before any such use.
- This is a **summary, not legal advice**; the full license governs.
- The exact contact address/path is a **GAP** (not captured verbatim) — point the user to
  the official docs/license page rather than inventing contact details.

## Model / weight artifacts carry SEPARATE terms

- General models and pretrained weights (e.g., a `cryolo_model.h5`, JANNI general model
  `.h5`) may have **usage terms separate from the package license**, and their download
  provenance is a **GAP** (ref 05). Do not assume the package license covers a downloaded
  weight.
- **This skill ships no crYOLO code and no model weights, and never downloads them.** Never
  package, redistribute, or auto-download weights/models. If the user wants a model,
  point them to the official download page (capture its terms first).
- The validated smoke run used an **externally-provided** PhosaurusNet general model,
  `gmodel_phosnet_201912_N63.h5`, supplied from the user's own filesystem (it was loaded
  from a path the user pointed at; the validation run, crYOLO section; smoke
  command in `logs/cmdlogs/command_predict_20260606-131938.txt`).
  The skill **neither ships nor fetches** that file — it points to it only if the user
  provides it. Treat any such general-model weight as carrying its own separate terms.

## Privacy — local data and the config report

- **Micrographs, annotations, coordinates, and models are sensitive local project data.**
  The skill performs **no** upload, download, move, delete, or conversion of user data, and
  runs no crYOLO job on it, **without explicit per-action user confirmation**. Reading or
  acting on private data is gated on the user pointing the skill at it.
- The per-machine `configs/site_config.local.md` is **generated on each host** by running
  `scripts/cryolo_env_probe.py`; the repo **does not ship** a real machine report (the
  tracked file is a short not-shipped placeholder). When generated, it (and any
  `references/environment/local_env_probe_*.md`) contains hostname, paths, and env
  details. These are **local/private**:
  - The probe redacts the home directory to `~` and user path segments to `<user>`.
  - They are git-ignored (`skill/cryolo_skill/.gitignore`) and excluded from any shared /
    packaged copy of the skill.
  - **Never upload or commit them.** Do not paste their contents into external services.
- The probe never dumps the full environment — only an allowlist
  (`02_config_session_and_environment.md`).

## Operational safety (boundaries that always hold)

- **No blind installs, downloads, env modification, or network calls.** Never install
  system-level dependencies or fetch weights/models on the user's behalf without them asking.
- **crYOLO jobs (config / train / predict / evaluation) MAY be run** — but only after the
  per-machine probe returns a `supported` / `partial` verdict (see
  `02_config_session_and_environment.md`) **and** the user has explicitly confirmed. Run
  them in the project working directory, on the data and model the user points to. CLI
  behaviour is **VALIDATED against crYOLO 1.9.9** (captured live `--help`; end-to-end smoke
  in the validation run).
- **No acting on private data without confirmation.** Reading, converting, or picking on the
  user's micrographs/coordinates requires explicit per-action approval.
- **No auto-launch of the GUI / napari / boxmanager and no queue/HPC (SLURM) job submission
  unless the user explicitly asks for it.** Do not background-submit jobs on a cluster on
  your own initiative.
- **No guessing of license contact details** beyond the captures, and no guessing of any
  fact the captured help / smoke logs do not show. (Flags, config schema, positionals,
  coordinate-output formats, and the `out/` layout are now captured for 1.9.9 — use ref 03
  and ref 04 rather than guessing; only genuinely-unsourced items remain a gap.)

## When the user asks "can my company use crYOLO?"

1. Surface the non-commercial restriction (above) and that commercial/operational use is
   explicitly prohibited under this license.
2. Say it is a summary, **not legal advice**.
3. Tell them to contact the authors via the official docs/license page for commercial
   terms; do not invent an address.
4. Do not give a yes/no legal guarantee.
