# RELION 3D-classification → cryoSPARC round-trip (portable automation)

Config-driven tools to take a **focused RELION 3D classification of a cryoSPARC
local-refinement region**, split the particles by class, and re-refine each class in
cryoSPARC — **without re-importing particle stacks**, so poses + CTF stay native.

This is the executable companion to the cryoSPARC skill reference
`references/28_relion_class3d_roundtrip.md` (the workflow narrative, parameter
rationale, and validation). The *metadata semantics* of the bridge live in
`references/27_relion_interop.md`. The RELION-side binary commands are owned by the
**relion** skill, by leg: csparc2star `.cs`→`.star` + the `.mrcs` requirement in
`16_interop_cryosparc.md`; `relion_image_handler` downsample in `03_cli_inventory.md`;
`relion_mask_create --width_soft_edge` mask soften in `09_mask_postprocess_localres.md`;
focused `relion_refine --K --skip_align --tau2_fudge` Class3D in `07_initialmodel_class3d.md`.

These scripts ship UNCONFIGURED. Nothing is hard-coded to a host, project, or
dataset — you supply all of that in one JSON config.

## Install / prerequisites

- A `cryosparc-tools` interpreter whose version matches your master (record it in
  the cryoSPARC skill's `site_config.md`). Run every script with that interpreter,
  e.g. `/path/to/cs-tools-venv/bin/python`.
- `pyem`'s `csparc2star.py` on PATH (for the cryoSPARC→RELION conversion step).
- RELION on PATH (for downsample / mask / classification).
- `numpy` (already in the cryosparc-tools env).

## Credentials (mandatory)

Account email + password come **only** from the environment and are never written
to any file or echoed back:

```bash
export CRYOSPARC_EMAIL='you@lab.org'
export CRYOSPARC_PASSWORD='...'      # typed at the shell, never committed
```

The **instance license id** is not a personal secret — it goes in the config
`instance.license` (copy it from your `site_config.md`). If your tools build no
longer needs `license=`, set it to `null`.

## Configure

```bash
cp roundtrip.example.json roundtrip.json
$EDITOR roundtrip.json     # fill instance/project/workspace/source_job/paths
```

| Config key | Meaning |
|---|---|
| `instance.{license,host,port}` | from your cryoSPARC `site_config.md` (the example's `port: 39000` is cryoSPARC's default base port — confirm it against your own `site_config.md`) |
| `project` / `workspace` | `P###` / `W###` you want the new jobs in |
| `source_job` | the cryoSPARC **Local Refinement** the RELION classification came from (supplies particles + volume + mask) |
| `source_outputs` | output group names on `source_job` (defaults: particles/volume/mask — verify with `inspect`) |
| `keep_classes` | RELION class numbers to keep (drop junk classes) |
| `force_gs_resplit` | force a fresh, balanced gold-standard split on per-class subset refines; leave `true` unless you have a specific reason to reuse the inherited split |
| `assignment_npz` | output of `map_relion_classes.py` (the uid↔class map) |
| `work_dir` | where `built_jobs.tsv` / `nu_jobs.tsv` are written |
| `local_refine.clone_params_from_source` | reuse the source local-refine's params verbatim (recommended) |
| `local_refine.params_override` | dict merged on top of the cloned params |
| `nu_refine.enabled` + `whole_mol_ref` | optional per-class whole-molecule NU refine against a consensus map (e.g. the parent refinement) |
| `lane` | default queue lane (or leave null and export `CS_LANE`) |

## Workflow

```
cryoSPARC source local-refine (J_src)
  └─ csparc2star.py  ───────────────►  particles STAR   (relion skill)
       └─ relion_prep.py  ──────────►  .mrcs farm + absolute paths
            └─ relion_image_handler ─►  downsample (relion skill)
                 └─ relion_refine ───►  focused Class3D (--skip_align, high T)   (relion skill)
                      └─ map_relion_classes.py ─►  class_assign_uid.npz
                           └─ cs_roundtrip.py inspect / build / queue / nurefine
```

### 1. cryoSPARC → RELION particles (relion skill owns the binaries)

```bash
# from the cryoSPARC project root so relative .mrc paths resolve:
csparc2star.py J_src/J_src_particles.cs J_src/J_src_passthrough_particles.cs \
  --boxsize <BOX> particles.star

# make them RELION-loadable (.mrcs farm + absolute, location-independent paths):
python relion_prep.py --in particles.star \
  --cs-project-root /abs/CS-project/ \
  --symlink-dir /abs/relion_proj/JXXX_class3d/Particles \
  --out particles_abs.star

# (optional) downsample for classification, e.g. 400 -> 128:
relion_image_handler --i particles_abs.star --o particles_ds128 \
  --new_box 128 --rescale_angpix <new_apix>     # writes particles_ds128.star + *_ds128.mrcs
```

Re-soften the cryoSPARC (hard 0/1) focus mask for RELION focused classification:
```bash
relion_mask_create --i mask_rescaled.mrc --o mask_soft.mrc \
  --ini_threshold 0.5 --extend_inimask 3 --width_soft_edge 6
```

### 2. Focused RELION classification (relion skill)

Reuse the cryoSPARC poses (`--skip_align`), high `--tau2_fudge` to force real splits.
See `references/28_relion_class3d_roundtrip.md` for the validated command and the
T-too-low collapse / distinctness-check rationale.

### 3. Map classes back to cryoSPARC uids

```bash
python map_relion_classes.py --config roundtrip.json \
  --data-star /abs/relion_proj/JXXX_class3d/Class3D/run_it025_data.star \
  --strip-suffix _ds128 \
  --out /abs/relion_proj/JXXX_class3d/class_assign_uid.npz
```

Joins on (stack-stem, within-stack index) → cryoSPARC `uid`; **aborts on any
unmatched** particle. Use `--by order` only if the RELION rows are a strict
1:1 order-preserving descendant of the source job.

### 4. Push back into cryoSPARC

```bash
python cs_roundtrip.py inspect  --config roundtrip.json   # read-only: counts + overlap
python cs_roundtrip.py build    --config roundtrip.json   # external subsets + Local Refines (no compute)
python cs_roundtrip.py queue    --config roundtrip.json --confirm   # queue them (needs a lane)
python cs_roundtrip.py nurefine --config roundtrip.json --confirm   # per-class whole-mol NU refine
python cs_roundtrip.py verify   --config roundtrip.json   # post-run count + GS split check
```

## Gotcha: gold-standard split on subset refines

Always force a fresh GS split on subset refines. A class subset inherits the
consensus `alignments3D/split` column through passthrough metadata, and that split
is often imbalanced for the subset. With `refine_gs_resplit=False`, cryoSPARC may
cull particles from the oversized half to balance the halves. The tools set
`refine_gs_resplit=True` by default via `force_gs_resplit`; keep that default unless
you are deliberately reusing the inherited split. After queued jobs finish, run
`cs_roundtrip.py verify --config roundtrip.json` and check that particle loss is
small and the split ratio is near 1:1.

## Safety

- `inspect` is read-only. `build`/`nurefine` create jobs in `building` status — **no
  compute** until you queue.
- Nothing queues without `--confirm` **and** a resolvable lane (`lane` in config or
  `CS_LANE` env). `queue`/`nurefine` without `--confirm` print a dry-run.
- Multi-user instance: only ever name a `project`/`workspace` that is yours.

## Files

| File | Role |
|---|---|
| `rt_common.py` | shared config/connect/assignment helpers (env-only credentials) |
| `cs_roundtrip.py` | `inspect` / `build` / `queue` / `nurefine` / `verify` subcommands |
| `map_relion_classes.py` | RELION Class3D data.star → `uid`↔`cls` npz |
| `relion_prep.py` | `.mrcs` symlink farm + absolute-path rewrite (no binaries) |
| `roundtrip.example.json` | config template (copy to `roundtrip.json`, edit) |
