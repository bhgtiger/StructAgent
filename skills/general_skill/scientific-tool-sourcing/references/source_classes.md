# Source classes: what to collect, where it goes, what goes wrong

Default priorities are for a skill that generates commands or parses outputs; adjust them
in the source plan. **P0** = blocks a trustworthy skill · **P1** = needed before broad use ·
**P2** = nice to have · **Out** = deliberately not collected (list it and say why).
"Pitfall" lines come from earlier skill projects (see `../examples/past_runs.md`).

## 1. Identity and canonical upstream — P0
Which repo/site is the real upstream? Check org, maintainers, PyPI/conda/bioconda names,
the paper's code-availability statement, and forks/mirrors.
- Record: canonical URL, package names, latest release, latest pre-release, default-branch
  HEAD, and which one the skill will target (usually the latest *release*; label `main`/
  `master` as "unreleased").
- Pitfall: the repo a user hands you may be a fork or an old mirror (Namdinator). Version
  badges, tags and `pyproject.toml` can disagree (cryoAtom) — record all three.

## 2. Pinned source code / machine-readable schema — P0 for software, APIs, databases
→ `sources/source/` (Task A). Clone with `--filter=blob:none`; check out the pinned tag.
- Record the **commit**, not the tag object: `git rev-parse <tag>^{commit}` (cryodrgn mixed
  them up). Add clone date, tag date, SPDX license.
- Extract every entry point and option verbatim with `file:line`; for APIs, the
  OpenAPI/GraphQL/DB schema at a pinned version.
- Pitfall: one clone per repo. Do not copy a repo twice or keep big test data
  (Namdinator raw store reached 185 MB from two duplicate clones plus map files).

## 3. Official documentation — P0
→ `sources/web/` (Task C). Prefer the docs *source* in the repo (rank 3 on the trust ladder)
over the rendered site (rank 4), but capture both if the rendered site is what users read.
- Record which version `/stable/` or `/latest/` resolved to on the fetch date.
- Keep a text copy of every page; keep raw HTML only when < ~2 MB (GitBook pages reached
  2.1 MB each in cryodrgn).
- Pitfall: rendered tutorials use aliases or wrapper commands that are not real CLI names
  (ModelAngelo); README help text goes stale (cryodrgn batch-size 8 vs 16 in code).

## 4. Live behavior — P0 for command-generating skills (Task D, optional during gathering)
`--version`, `--help` for every subcommand, `import pkg; pkg.__version__`, `/version`
endpoint, one real API request/response. → `sources/live/`.
- Live `--help` is the tiebreaker that resolves docs-vs-source defaults (boltz).
- It needs a host where the tool is already installed and the user's OK. If there is none,
  Task E writes `crosscheck/live_verification_checklist.md` instead. This is not optional.
- Pitfall: captures made on the server stayed on the server or in scratch (boltz,
  cryodrgn). Live evidence goes into the project's `sources/live/`, with host and date.

## 5. Data models and file formats — P0 if the skill reads or writes scientific data
Field schemas, label dictionaries (e.g. STAR/mmCIF tags), units, coordinate and orientation
conventions, ontologies. Prefer the parser/writer code (`file:line`) over prose.
→ `sources/source/input_output_formats.md`; format specs from standards bodies → `sources/web/`.

## 6. Models, weights, reference databases — P0 when the tool needs them
Name, URL, size, SHA-256 if published, license, access gate (registration, Hugging Face
contact gate), the env var or flag that points to them, download command. **Never
download.** → `sources/source/models_data_dependencies.md` + `sources/web/license_and_terms.md`.
- Pitfall: weight licensing stayed an open P0 in cryoAtom; gated vs public weights differed
  between releases in OpenFold 3.

## 7. Examples and fixtures — P1 (P0 before diagnostic or write features)
Small public inputs with expected outputs, known-failing cases, test commands. Catalog;
download only if small (< 50 MB) and the license allows.
- Verify accession IDs (EMDB/PDB/UniProt…) against the database. Namdinator's README had
  emd_6644 for 6640.

## 8. Environment and deployment — P0 for execution-capable skills
OS/arch, GPU/CUDA/driver, MPI, scheduler, containers, module systems, license servers,
memory/VRAM statements. Two hosts matter. The **gathering host** (probe it with
`scripts/probe_gathering_host.sh`) usually is not the **target runtime**. Record both, and
never assume the target from the gathering host.

## 9. Papers and literature — P1 (P0 for method-decision skills)
Roles: primary method, release/update, benchmark, protocol, review (context only),
dataset, standard. Papers justify *why/when*; they are never the authority for flags,
defaults or file names.
- Check the local paper databases first (the `database` skill), then fetch open-access PDFs.
  Use the `paper-reader` skill for digests (locate it; do not hardcode its path).
- Check every PDF really is one (`build_manifest.py` flags HTML saved as `.pdf`: PMC
  proof-of-work pages in Namdinator). Resolve relative links against the page's final URL
  (cryoAtom 404). If every route is blocked, ask the user to drop the PDF into
  `sources/papers/incoming/` and record a gap. Do not save a DOI and call it read (boltz).

## 10. Talks, tutorials, videos — P2 by default (P1 when docs are thin)
For expert heuristics and common mistakes only. Every operational claim needs a raw
transcript line with a timestamp.
- Transcripts: official captions, or `yt-dlp --skip-download --write-subs --write-auto-subs
  --sub-langs en <url>` if `yt-dlp` exists on the gathering host (do not install it
  unasked). NotebookLM is a manual step the user runs. Its summaries are navigation aids,
  never evidence, unless traced to transcript text.
- → `sources/videos/<date>_<slug>_{metadata,transcript_raw,claim_check}.md`.
- Earlier projects listed videos and never gathered them. Either do it or mark it `Out`
  with a reason.

## 11. Community and support — P1
GitHub issues (the issues endpoint also returns PRs: filter `pull_request`), Discussions,
official forums/mailing lists, HPC site notes. Cluster into failure-mode themes with dated
links. Lower trust: a workaround in an issue is not a supported fix.
→ `sources/community/`.

## 12. License, terms, privacy, data egress — P0
Software license; weights/data terms; API/database ToS and rate limits; citation
requirements; export or clinical restrictions; and **default network calls** (MSA/structure
servers, telemetry, license checks) that send user data off the machine, with the flag that
disables each. OpenFold 3 sent sequences to api.colabfold.com by default.
→ `sources/web/license_and_terms.md`, `sources/source/external_calls_and_egress.md`.

## 13. Wrappers, forks, plugins, integrations — P1 when they exist (Task B)
Optimized forks or vendor kits, GUI plugins, pipeline wrappers (cryoSPARC external jobs,
RELION schemes, Scipion/CCP-EM plugins), HPC modules. Check parity against upstream: pins,
vendored-code identity, passthrough limits, changed defaults, exit codes.
Interop formats with neighbouring tools (e.g. STAR/CS conversions) belong here too.

## Targets without public source code
Closed databases/APIs, commercial or GUI-only software, instruments:
- Class 2 becomes "API reference + machine-readable schema" or "scripting/macro reference".
- Class 4 (live behavior) moves up to the top of the trust ladder. Capture real
  responses or GUI/macro outputs as fixtures (with user approval).
- Class 12 usually dominates: licence servers, EULAs, rate limits, data-use agreements.
- Say plainly in the plan that there is no source tier. Do not invent one.
