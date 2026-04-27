# CCP4 install and setup discovery

## Setup script

CCP4 distributes a Bash setup script that exports `CCP4`, `CLIBD`, `CLIBD_MON`, `CCP4_SCR`, `BINSORT_SCR`, etc., and prepends the CCP4 `bin/` to `PATH`. Source it once per shell:

```bash
source /Applications/ccp4-9.0/bin/ccp4.setup-sh
```

Other common locations:

- `/Applications/ccp4-<version>/bin/ccp4.setup-sh` (macOS, official installer)
- `/opt/xtal/ccp4-<version>/bin/ccp4.setup-sh` (Linux convention)
- `$HOME/ccp4-<version>/bin/ccp4.setup-sh` (per-user install)

The CCP4 docs also document `/path/to/ccp4-<version>/start` as a Bash entry point. `ccp4.setup-sh` is the form the wrappers expect; if a user has only `start`, point them at `start` and have them set `CCP4_SETUP=/path/to/ccp4-<version>/bin/ccp4.setup-sh` once it exists.

## Environment probe order

`scripts/check_env.sh` and `scripts/run_ccp4.sh` resolve the setup script in this order:

1. `$CCP4_SETUP` if exported.
2. `/Applications/ccp4-*/bin/ccp4.setup-sh` (newest version glob).
3. `/opt/xtal/ccp4-*/bin/ccp4.setup-sh`.
4. `$HOME/ccp4-*/bin/ccp4.setup-sh`.

The first match wins. If multiple versions are installed and the user wants a specific one, set `CCP4_SETUP` explicitly.

## Required env vars after sourcing

```text
$CCP4         — root of the install
$CLIBD        — data files (symmetry, atomic form factors, …)
$CLIBD_MON    — monomer library root used by Refmac5 and AceDRG
$CCP4_SCR     — scratch directory (writable!)
$PATH         — must contain $CCP4/bin
```

`check_env.sh` prints these and the CCP4 version/update level.

## Capability groups probed by check_env.sh

The skill reports per-workflow capability rather than one global pass/fail, so a missing optional binary does not break unrelated workflows.

| Group | Required binaries | Used by |
| --- | --- | --- |
| core refinement | refmac5, mtzdump, freerflag, cad | run_refmac5.sh, run_ccp4.sh |
| ligands | acedrg | run_acedrg.sh |
| molecular replacement | phaser, molrep | (deferred wrappers) |
| autobuild | cbuccaneer, cnautilus | (deferred wrappers) |
| data reduction | aimless, pointless, ctruncate | (deferred wrappers) |
| optional helpers | sftools, pdbset, pdbcur, privateer, servalcat, gemmi | preflight, ad-hoc |

`refmacat` is a Servalcat-flavoured wrapper around `refmac5`; treat it as optional v1 and let the user invoke it explicitly through `run_ccp4.sh`.

## Fix guidance printed on failure

When the setup script is not found, `check_env.sh` prints:

1. Install CCP4 from <https://www.ccp4.ac.uk/download/>.
2. Or set `CCP4_SETUP` to the absolute path of `ccp4.setup-sh`, e.g.

   ```bash
   export CCP4_SETUP="$HOME/ccp4-9.0/bin/ccp4.setup-sh"
   ```

3. If only `/path/to/ccp4-<version>/start` exists, source that for an interactive shell and ask the maintainer to provide `bin/ccp4.setup-sh`.
