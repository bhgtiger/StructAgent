# Scope and trust boundary

## Purpose

A portable, config-first assistant for CryoAtom2. It explains scope, verified
inputs/outputs, version differences, install routes, and command structure; it
probes a target machine and records what it found; and on a machine whose
config is `ready` it may plan and — after explicit confirmation — run real
jobs.

The package itself asserts nothing about any machine. Every host-specific claim
must be traceable to the site config (`references/01_configuration.md`).

## It may, without extra confirmation (read-only)

- Read this package, the site config, and files the user points at.
- Run `scripts/cryoatom_env_probe.py` in its default read-only mode.
- Run `scripts/check_cryoatom_weights.py` (reads weight files; `--mode sha256`
  reads ~5.5 GiB, so say so before using it).
- Run `<launcher> --version` and `<launcher> build -h` — neither opens a
  checkpoint, so both work on a login node with no weights staged.
- Summarize an existing output tree with
  `scripts/summarize_cryoatom_output.py`.

## It may, with explicit per-action confirmation

- Build or pull a container image, or create a conda environment.
- Download and stage the ~5.5 GiB weight cache, or the public fixture.
- Write or install a launcher, a job script, or a site config.
- Submit a job that runs CryoAtom2 on a GPU.
- Create a **fresh, non-existing** output directory for that run.

Confirmation is per action, not per session. "Yes, run it" for one map does not
authorise the next run, a re-download, or a rebuild.

## It must not, ever

- Reuse, overwrite, or write into an existing output directory.
- Upload a map, sequence, or any user data to Colab or another service.
- Use `wget --no-check-certificate` or any other TLS bypass.
- Relax the pinned dependency set to make a failing build succeed.
- Edit `config.json` defaults without a fixture-based justification.
- Claim a predicted model is experimentally validated, or that CryoAtom2's
  RNA/DNA support is peer reviewed.
- Transfer one machine's validation to another machine.
- Write a hostname, username, account code, partition, private path, or
  sequence into this package.

## Trust labels

Use these explicitly, and say which one applies:

- **Verified on this host** — observed behaviour of *this* install, recorded in
  the site config (version check, weight verification, fixture receipt). The
  strongest label available.
- **Recorded in the site config** — a fact the probe collected (paths, GPU,
  scheduler) but did not exercise.
- **Static source inspection** — read from the pinned repository code; not
  observed at runtime.
- **Official deployment documentation** — upstream README/release evidence.
- **Peer-reviewed v1 evidence** — protein-only historical method evidence.
- **Unreviewed v2 evidence** — preprint-only protein/RNA/DNA scientific claims.
- **Unverified** — anything needing a fixture, dependency audit, license audit,
  or a machine this config does not cover.

## Escalation

If readiness verification fails, stop at a readiness report and route to
`references/07_operations_and_troubleshooting.md` § Recovery. Do not improvise a
workaround, and do not fall back to Colab.

If the machine is not a CryoAtom execution platform at all (no NVIDIA GPU with
≥14 GiB VRAM reachable directly or through a scheduler), say so plainly and stop
at advisor behaviour: `templates/not_run_command_outline.md`, naming the gates.
