# Lessons (cryodrgn-skill)

Running log of what was learned building/operating this skill. Append-only;
newest first. Keep entries source-grounded.

## 1.0.0 (2026-06-06) — first installed + validated release

- **Config-first must fail closed.** The single biggest risk is advising before
  the environment is known. The gate (`references/02`) treats absent/stale/unknown
  identically: general explanation + offer the probe, nothing machine-specific.
  The probe never emits `absent`/`stale` — those are the skill's job when no
  current report exists.
- **Label discipline is mechanical, not vibes.** Every command template carries a
  `[config-state: <ready|partial|blocked|absent|stale|unknown>]` tag and, where the
  exact flags were confirmed against captured live help, a `[VALIDATED: cryoDRGN 4.2.1]`
  tag citing the help filename (e.g. `cryodrgn.train_vae.help.txt`). Commands that
  touch real data/compute carry `[run-with-confirmation]`; `[not-run]` is reserved
  only for illustrative or destructive examples the skill must never auto-run. The
  old `[live-unverified]` label is retired — live help is captured, so flags are
  VALIDATED, not unverified. Inline command *mentions* are backticked (not standalone
  lines) so they aren't mistaken for emittable templates.
- **The probe is read-only by construction.** A structural allowlist (`_is_allowed`)
  plus a `FORBIDDEN_TOKENS` guard, timeouts, home-dir redaction, and no env dump.
  cryoDRGN subcommand help is the only cryoDRGN invocation and is always terminated
  by `-h`, so the probe itself starts no compute. Negative tests (`pip install`,
  `conda create`, `cryodrgn train_vae`, `curl`, bare `nvidia-smi`) are refused. The
  probe stays read-only and generic; *acting* on its verdict (emitting concrete
  commands, and on a `ready` host running real jobs after explicit user confirmation)
  is the skill's job, governed by the `references/02` capability table.
- **The probe verdict is per-host; never hardcode one machine.** The probe computes
  support for whatever host it runs on. cryoDRGN officially targets Linux + NVIDIA
  GPUs (`pyproject` classifier `Operating System :: POSIX :: Linux`
  [src: `sources/source/cryodrgn_4.2.1/pyproject.toml`]; installation docs require a
  Linux workstation/cluster with NVIDIA GPUs), so a non-Linux or GPU-less host gets
  `blocked` and the skill recommends a suitable Linux+NVIDIA target before any
  concrete planning. State these as general, sourced, probe-driven per-platform facts
  — never as "this machine is blocked."
- **cryoDRGN 4.2.1 is installed and VALIDATED end-to-end on Linux+NVIDIA.** On a
  Linux + NVIDIA GPU host (a dedicated cryoDRGN 4.2.1 conda env, py3.10),
  **torch 2.9.1+cu128, cuda True** (`_version.txt`). The probe
  reports `config_state = ready`. A relion31 dataset (D=256, 5 ptcls, angles+CTF+optics)
  ran through `downsample` → `parse_pose_star` → `parse_ctf_star` →
  `backproject_voxel` → `train_vae` → `analyze` → `cryodrgn_utils view_header`
  (the validation run).
- **Live `--help` captured for every subcommand; flags are VALIDATED.** All 23
  `cryodrgn` + 25 `cryodrgn_utils` subcommands have captured `-h`. Key corrections
  threaded through the refs:
  - `parse_pose_star` output is `--outpkl PKL` (with `-o` as alias), positional `input`;
    only `-D`/`--Apix` are optional overrides (`cryodrgn.parse_pose_star.help.txt`).
  - `backproject_voxel` output is `--outdir OUTDIR` (with `-o` alias), requires `--poses`,
    optional `--ctf`; half-maps + FSC are DEFAULT (suppress with `--no-half-maps`/
    `--no-fsc-vals`) (`cryodrgn.backproject_voxel.help.txt`).
  - `eval_vol` config flag is `-c YAML`/`--config YAML` — it is the run's `config.yaml`,
    and the live help literally prints `YAML` (`cryodrgn.eval_vol.help.txt`).
  - `write_cs` is **deprecated (v3.4.1) and is a thin delegate to `filter_cs`**: its
    `main()` prints a deprecation warning then calls `filter_cs_main(args)`
    (`sources/source/cryodrgn_4.2.1/cryodrgn/commands_utils/write_cs.py`:
    `from cryodrgn.commands_utils.filter_cs import main as filter_cs_main`). Its `--help`
    *description* ("Create a CryoSparc `.cs` ... from a particle stack") is stale — the
    positional accepts only `.cs` (`write_cs.help.txt`: `particles  Input particles (.cs)`),
    and `filter_cs` requires a `.cs`, subsets by `--ind`, and ignores `--ctf`/`--datadir`/
    `--poses` (`cryodrgn_utils.filter_cs.help.txt`). So **use `filter_cs` to filter an
    existing `.cs`**; neither util builds a `.cs` from a `.mrcs`/`.star` (that comes from
    cryoSPARC). LESSON: when help-description text conflicts with the source, the source
    wins — do not "upgrade" a deprecated delegate into a functional writer on the strength
    of a stale one-line description. (The original VALIDATION_SUMMARY "delegates to
    filter_cs" note was correct.)
  - `parse_relion` is RELION v5 TOMOGRAM→2D-coords only
    (`-t tomograms.star -p particles.star --tilt-dim W H`), NOT a general RELION parser
    (`cryodrgn_utils.parse_relion.help.txt`).
- **Output layout is captured ground truth.** `train_vae`/abinit workdir =
  `config.yaml`, `run.log`, `weights.pkl`, `weights.N.pkl`, `z.pkl`, `z.N.pkl`,
  `analyze.N/` (analysis auto-runs on the final epoch unless `--no-analysis`).
  `backproject_voxel --outdir DIR` = `backproject.mrc`, `half_map_a.mrc`,
  `half_map_b.mrc`, `fsc-plot.png`, `fsc-vals.txt`
  (src: the validation run).
- **Version drift is real; report a range.** `pyproject` `requires-python` is
  `>=3.10` (unbounded); README says 3.10–3.13; docs say tested 3.10–3.12 (3.13
  mentioned). Effective torch cap `<2.10.0`. The validated env ran py3.10 +
  torch 2.9.1+cu128. Never assert one exact supported Python; flag out-of-range.

## Open follow-ups (later versions)

- File paper digests before any quantitative/benchmark claim (`references/08`).
- Pin a docs-source repo (or versioned export) instead of date-stamped GitBook pages.
- Re-pin target version when moving past 4.2.1 (beta `4.3.0-b2` already exists).
- Probe reporting cleanups: `mamba --version` value contains an embedded newline
  ("mamba 1.5.1\nconda 23.7.4"); `pip` detection resolves to the user-site pip
  rather than the active env's pip (cosmetic) — per
  the validation run (Probe defects found).
