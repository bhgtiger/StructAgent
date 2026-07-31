# CryoAtom readiness report — template

Status: assessment only. It authorises no run, download, rebuild, or output
write. Each of those needs its own explicit confirmation.

## Request

- Intended use:
- Map / system description (no file contents needed):
- Evidence scope: verified on this host / recorded in the site config / static source inspection / documentation / paper context

## Configuration

```bash
python3 scripts/cryoatom_env_probe.py --validate-config <CONFIG_PATH>
```

- Config path:
- Profile / hostname it describes:
- Install route: container / native / module / preinstalled
- **State: ready / probed / stale / blocked / unknown**
- Reasons reported:

If the state is not `ready`, say what is missing and stop at the matching
section: install → `references/02_install_routes.md`; breakage →
`references/07_operations_and_troubleshooting.md` § Recovery.

## Version and evidence

- Expected: CryoAtom2 **2.1.1, commit `856e250…`** — an untagged master
  snapshot, not a tagged release. Tag `v2.1.0` is *behind* it; do not quote the
  two interchangeably.
- Observed on this host (`cryoatom --version`):
- Runtime verification for this request: [performed / not performed]
- v1 evidence: peer-reviewed, protein-focused.
- v2 protein/RNA/DNA evidence: unpinned, unreviewed preprint.

## Host readiness (paste real output)

```bash
cryoatom --version
python3 scripts/check_cryoatom_weights.py --cache <CACHE> --mode size
```

- Version observed:
- Weight cache (6 files, sizes ± SHA-256):
- GPU available with ≥14 GiB VRAM? [yes / no / not from this node] — partition:
- Running on a GPU node, not a login node? [yes / no]
- Fixture run recorded for this install? [yes / no] — job / GPU / elapsed:
- Verdict: **ready / not ready / not yet verified**

## Data and output boundary

- Output path proposed (must not exist yet):
- On scratch, not home? [yes / no]
- Reusing an existing directory? [must be **no**]
- Cloud/upload proposed? [must be **no**]
- Weight/dependency licenses reviewed for the intended downstream use? [yes / no]
  — repository code is MIT; CryoAtom checkpoint, ESM-2 and RNA-FM weight
  licenses are **not established**.

## Sequence inputs

- `-ps/-rs/-ds` (sequences in *this* map):
- `-pf/-nf` (search databases) — do they cover every sequence in the map?
  [yes / no / unknown] — an incomplete database degrades assignment silently,
  without erroring.

## Gates before this specific run

1. Explicit user confirmation for this run.
2. Readiness verified above, now — not remembered from earlier.
3. Fresh, non-existing output directory.
4. Realistic walltime, scaled from a fixture time by map size and chain count.
5. Agreement that the output confidence field is not experimental truth.
