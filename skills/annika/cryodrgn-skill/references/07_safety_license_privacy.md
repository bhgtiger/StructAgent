# 07 — Safety, license, privacy

## Safety boundaries (hard)

cryoDRGN 4.2.1 is **installed and VALIDATED end-to-end on GPU** (Linux + NVIDIA;
captured live `--help` + smoke log, 2026-06-06). On a host the probe reports `[config-state: ready]`, the
skill MAY emit concrete commands with the user's real paths and MAY run real
cryoDRGN jobs — including `train_vae`/`train_nn`, `abinit_*`, `analyze`,
`backproject_voxel`, `eval_*`, and the `dashboard`/`filter` UIs — **after explicit
user confirmation**. The remaining boundaries are scoped to genuine risk, not a
blanket no-execute ban:

- **No data exfiltration.** Never upload, transmit, or move the user's particle
  stacks, metadata, poses/CTF/`.pkl`, `config.yaml`, or volumes off the host, and
  never paste their contents to any external service. No unsolicited network calls.
- **No blind installs of system-level dependencies.** Do not silently run
  `pip install` / `conda` / `mamba create`, change CUDA/driver/system packages, or
  mutate an environment without showing the documented command and getting explicit
  confirmation first (see "No blind/auto install" below).
- **Confirm before running on real data/compute.** Any command that reads, writes,
  or computes on the user's real data carries `[run-with-confirmation]`; emit it,
  explain its effects and outputs, and run it only after the user says yes. Reserve
  `[not-run]` for illustrative or destructive examples (e.g. `cryodrgn_utils clean`,
  bulk deletes) that the skill should never auto-run.
- **License + privacy** obligations below always apply.

The **read-only probe** (`scripts/cryodrgn_env_probe.py`) remains allowlisted,
timeout-protected, writes only its report, and redacts the home directory; it is
safe to run unprompted to determine per-host support. The probe computes support
**per machine** — the skill stays generic and never hardcodes one host's verdict.

### No blind/auto install — even if asked

If the user asks the skill to "just install cryoDRGN," there is **no BLIND/auto
install**. *Describe* the documented install (Anaconda/conda env + `pip install
cryodrgn`) and run it only **after explicit confirmation** — never silently, and
never as a side effect of another request. Honor the sourced platform caveat:
cryoDRGN's `pyproject.toml` ships only the classifier
`Operating System :: POSIX :: Linux`
[src: `sources/source/cryodrgn_4.2.1/pyproject.toml`], and its installation docs
require a Linux workstation/cluster with NVIDIA GPUs. On a host the probe reports
`[config-state: blocked]`/`absent` for these reasons (e.g. non-Linux OS, no CUDA
GPU), say so as a probe-driven per-platform outcome — not as a verdict about any
specific machine.

## License

- **cryoDRGN is licensed GPLv3** (`LICENSE.txt` is the GNU GPL v3, 29 June 2007;
  `pyproject.toml` classifier
  `License :: OSI Approved :: GNU General Public License v3 (GPLv3)`)
  [src: `sources/source/cryodrgn_4.2.1/LICENSE.txt`,
  `sources/source/cryodrgn_4.2.1/pyproject.toml`].
- This skill **ships no cryoDRGN source, weights, or datasets** — only distilled
  references. Nothing here redistributes cryoDRGN code.
- GPLv3 has obligations for redistribution and derivative works. If the user asks
  about redistributing/modifying/commercializing cryoDRGN, give a **brief,
  not-legal-advice** pointer to the license text and recommend they consult the
  license / counsel. Do not opine definitively on license compliance.

## Privacy / private data

Treat the following as **local/private**; never upload, share, transmit, or move
them off the host, and never paste their contents to any external service:

- `configs/site_config.local.md` (host details, generated per-machine by the probe,
  not shipped; `.gitignore`d),
- particle stacks (`.mrcs`/`.mrc`), `.star`/`.cs` metadata, `.pkl` (pose/CTF/z/
  indices), `config.yaml`, generated volumes,
- cluster/scheduler/account details, real filesystem paths, usernames.

If a user asks the skill to "upload my particles so you can diagnose," **refuse**
and instead request a redacted error message, a header dump
(`cryodrgn_utils view_header`), or the probe report — diagnosis stays on the user's
host. This mirrors the "License/privacy" eval case (`tests/eval/eval_cases.md`).

The probe already redacts the home directory to `~` and never dumps all
environment variables; keep it that way in any future change.

## Scientific-integrity guardrails

- Do not invent live CLI behavior, flags, runtimes, or benchmark numbers. cryoDRGN
  4.2.1 behavior IS captured and `[VALIDATED: cryoDRGN 4.2.1]` against the live
  `--help` (cite the captured help file where a flag/default was confirmed, e.g.
  `cryodrgn.train_vae.help.txt`); label only **genuinely-uncaptured** or
  **version-divergent** behavior as a remaining gap. No fabricated benchmarks;
  always attach version + hardware context (`08_validation_and_benchmarks.md`).
- Do not make performance/accuracy claims beyond captured docs/papers, and always
  attach version + hardware context (`08_validation_and_benchmarks.md`).
- Do not recommend handedness/sign flips, index filters, or destructive
  re-processing as if certain — present them as checks to try, with the doc basis.
