# Boltz site config — TEMPLATE

Copy to `site_config.local.md` (git-ignored) and fill from a fresh
`scripts/boltz_env_probe.py` run on the target host. One file per host. This is
the warm-start memory so a new session doesn't re-derive the environment — but it
**expires**: if the host/env/install changed, re-probe and rewrite.

```yaml
host:            <hostname>
date_probed:     <YYYY-MM-DD>
state:           <UNCONFIGURED | PROBED | VALIDATED>   # see SKILL.md state table

boltz:
  env_path:      <conda env prefix, e.g. /opt/conda/envs/boltz2>
  run_prefix:    <how to invoke, e.g. "conda run -n boltz2" or "<env>/bin/boltz">
  version:       <e.g. 2.2.1>
  python:        <e.g. 3.10.x>

compute:
  torch:         <e.g. 2.10.0+cu128>
  cuda_build:    <e.g. 12.8>
  gpus:          <e.g. 2x RTX 2080 Ti, 11 GB>
  compute_cap:   <e.g. 7.5>
  kernels_ok:    <true|false>          # false -> add --no_kernels
  cpu_only:      <true|false>

cache:
  BOLTZ_CACHE:   <path or "(unset -> ~/.boltz)">
  weights_present: <true|false>        # boltz2_conf.ckpt etc.

msa:
  default_strategy: <use_msa_server | custom | empty>
  msa_server_url:   <default https://api.colabfold.com | custom>
  privacy_note:     <e.g. "no confidential seqs to public server">

notes: |
  <anything host-specific: queue/sbatch wrapper, scratch dir for out_dir,
   known-good fixture command, VRAM ceilings observed, etc.>
```
