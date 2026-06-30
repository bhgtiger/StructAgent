# Namdinator site config — TEMPLATE (fill in per host; ships blank)

This skill is **not** configured for any specific machine. Copy this file to
`site_config.local.md` on whatever Linux host you eventually run Namdinator on,
fill in the real values, and keep it next to your runs. The skill can *read* a
filled-in copy to give more concrete advice — it still will not execute anything.

Leaving this blank is correct for general use. Do not commit a host-specific
filled-in copy back into the portable skill.

```yaml
# ---- identity ----
host:                 # hostname / cluster name
os:                   # e.g. Ubuntu 20.04  (Namdinator assumes Linux; lscpu used)
generated_at:        # ISO date you filled this in
filled_in_by:        # who

# ---- script ----
namdinator_repo:      # path to a clone of namdinator/Namdinator_bash
namdinator_commit:    # commit you are pinned to (baseline: 5814c9474a41f7cbcca785ce83027227073d656f)
entry_script:         # default: Namdinator_Generic.sh  (NOT Namdinator_current.sh unless this is the Aarhus site)

# ---- dependency stack (paths + versions actually present) ----
vmd:                  # path / version (documented: 1.93)
vmd_plugins:          # MDFF, ssrestraints, cispeptides, chirality, AutoPSF, multiplot present? versions?
namd2:                # path / version (documented: 2.12 CUDA)
cuda:                 # version (documented: >= 6.0)
phenix:               # path / version (documented: 1.13rc1)
rosetta:              # path / version (OPTIONAL; documented: 2016.32.58837) or "absent"
gnuplot:              # path / version
bc:                   # present? (used for scoring branch logic)

# ---- environment variables exported for runs ----
VMDMASTER:
NAMDMASTER:
PHENIX:
PHENIXMASTER:
PHENIXMASTERDIR:      # if set, script sources phenix_env.sh
ROSETTA_BIN:          # if unset, Rosetta validation columns become n/a

# ---- hardware ----
gpu:                  # model / CUDA capability
gpu_count:
cpu_cores:            # -n default comes from lscpu; override with -n off Linux
ram_gb:               # ~16 GB handled ~20,000 residues in the 2019 paper context

# ---- validation state of THIS host (be honest) ----
help_captured:        # have you run `./Namdinator_Generic.sh -h` and saved it?  yes/no
fixture_run_ok:       # have you completed a successful fixture run? yes/no + date
fixture_used:         # e.g. 3jd8.pdb + emd_6640.mrc @ <verified resolution>
notes:                # compatibility surprises, parsing breaks, patches applied
```

Until `help_captured` and `fixture_run_ok` are both yes on a host, treat all
command/flag/output claims as **source-derived, not runtime-verified** (see
`../references/00_scope_and_trust.md`).
