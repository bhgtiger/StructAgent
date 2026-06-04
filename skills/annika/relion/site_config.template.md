---
name: relion-site-config
description: UNCONFIGURED template. Run scripts/configure_site.sh to generate the real per-host config before any environment-dependent action.
---

# Site config — UNCONFIGURED TEMPLATE

> ⚠️ **This is the generic template shipped with the skill. It is NOT a real configuration.**
> Before generating queue commands, launching jobs, or recommending MPI/GPU counts, configure this host:
>
> ```bash
> # from the skill directory:
> bash scripts/check_env.sh                                   # see what is installed (read-only)
> bash scripts/configure_site.sh --apply                      # generate site_config.md for THIS host
> bash scripts/configure_site.sh --apply --project /path/to/a/relion/project   # also scrape queue/scratch
> ```
>
> `configure_site.sh` auto-detects the RELION install, MPI/GPU/Python, interop tools, and scheduler, and
> (with `--project`) scrapes `qsub`/`qsubscript`/`queuename`/`scratch_dir` from a real `job.star`. It then
> overwrites this file. Fill any remaining `TODO` fields by hand.
>

Until you have run `configure_site.sh`, the skill must treat the following as **unknown** and ask the user:

| Field | Value |
|---|---|
| Host | `<run configure_site.sh>` |
| RELION version / binary dir | unknown — `check_env.sh` reports it |
| MPI launcher / GPU backend / GPU memory | unknown |
| Scheduler (`sbatch`/`qsub`/`bsub`) | unknown |
| Queue script / queuename / scratch dir | unknown — scrape from your own `job.star` |
| Interop tools (`csparc2star.py`, cryoDRGN env) | unknown |
| Permission level (read-only / generate / execute) | **assume read-only + generate (tiers R/G) until the user grants more** |

## Portability notes

- One `site_config.md` describes **one host**. When you move to a new machine, re-run `configure_site.sh --apply --save` there; `--save` also keeps a copy under `configs/<hostname>.md` so you accumulate a config per machine.
- Never hard-code paths from this file into generated scripts — read them from the active config or from the user's own `job.star`.
- If `site_config.md`'s `Host` does not match the current `hostname`, it is stale: re-run `configure_site.sh`.
