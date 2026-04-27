# Refmac5 reference

## Wrapper interface (`scripts/run_refmac5.sh`)

```bash
bash scripts/run_refmac5.sh [--dry-run] [--force] \
  --xyzin model.pdb \
  --hklin data.mtz \
  --xyzout refined.pdb \
  --hklout refined.mtz \
  --preset xray_default | xray_jellybody | tls \
  --labin "FP=F SIGFP=SIGF FREE=FreeR_flag" \
  [--ncyc 10] \
  [--libin ligand.cif] \
  [--keyword-file extra.com] \
  [--tls-in tls.in]
```

Behaviour:

- `--xyzin`, `--hklin`, `--xyzout`, `--hklout`, `--labin`, and `--preset` are required.
- The wrapper sources the CCP4 setup, picks the preset Refmac keyword block, appends user-supplied `--keyword-file` content (verbatim, in a separate "user override" section so the diff is obvious), and runs `refmac5`.
- The generated keyword script is written to the run directory before execution. If `--dry-run`, it is written and the wrapper exits 0 without running `refmac5`.
- Refuses to overwrite `--xyzout`/`--hklout` unless `--force`.
- Logs `stdout` + `stderr` to `ccp4_runs/refmac5_<timestamp>/refmac5.log`.

## FreeR rule (do not silently auto-generate)

If the MTZ does not contain the column named in the `FREE=` token of `--labin`, the wrapper prints:

```text
[FAIL] FreeR column 'FreeR_flag' not present in data.mtz.
       Generate flags explicitly (skills never auto-create FreeR):
         bash scripts/run_ccp4.sh --stdin <(printf 'END\n') -- \
           freerflag HKLIN data.mtz HKLOUT data_with_free.mtz
       Then re-run with --hklin data_with_free.mtz.
```

`run_refmac5.sh` does not invoke `freerflag` itself.

## `--labin` requirement

`refmac5` needs `LABIN FP=... SIGFP=... FREE=...` keywords. The wrapper builds that line from `--labin`. The argument is required because column labels are highly project-specific — a heuristic that picks `F` over `Fobs` will silently corrupt downstream R-free statistics one day. The MTZ preflight prints a candidate `--labin` string when columns are unambiguous; copy it verbatim.

For anomalous data, `LABIN F+=... SIGF+=... F-=... SIGF-=...` is also accepted; pass it through `--labin` exactly as Refmac expects.

## Presets

- `presets/refmac5_xray_default.com` — restrained refinement, 10 macrocycles, automatic weight, isotropic ADP, no jelly-body, no TLS.
- `presets/refmac5_xray_jellybody.com` — adds `RIDG DIST SIGM 0.02` jelly-body restraints; useful at low resolution or with sparse data.
- `presets/refmac5_tls.com` — expects `--tls-in` and switches to a `REFI TYPE RESTrained` + `REFI TLSC <ncyc>` block. The wrapper does not auto-generate TLS group selections in v1.

Each preset is a plain Refmac keyword file. Open and edit with confidence; the wrapper never templates over user keywords without showing them.

## TLS

In v1 the wrapper accepts a user-supplied TLS file via `--tls-in`. It does not call `tlsanl` or auto-pick TLS groups. Strategy questions about whether to use TLS at this resolution belong in `structural-strategy/references/refinement.md`.

## Jelly-body

Jelly-body restraints are an option for low-resolution refinement; switch them on by selecting `--preset xray_jellybody`. The preset uses `RIDG DIST SIGM 0.02 DMAX 4.2`, which is a conservative starting point; users who want different sigma/distance cutoffs should pass `--keyword-file` with their own `RIDG` block.

## Ligand restraints

Pass `--libin ligand.cif` to load AceDRG-generated restraints. The wrapper logs the path and verifies the file is readable; it does not parse the residue code. If a residue code in the model is not present in either `$CLIBD_MON` or `--libin`, Refmac5 will abort — that is the right behaviour, and the preflight warns about it before you reach Refmac.

## Servalcat / refmacat

`refmacat` is the Servalcat-provided wrapper around Refmac5. It is not used by `run_refmac5.sh` in v1 because its argument surface differs and its keyword handling is its own contract. Invoke it explicitly through `run_ccp4.sh`:

```bash
bash scripts/run_ccp4.sh --dry-run --stdin keywords.com -- \
  refmacat --hklin data.mtz --xyzin model.pdb --hklout out.mtz --xyzout out.pdb
```

## Upstream documentation

- Refmac5 reference: <https://www.ccp4.ac.uk/html/refmac5.html>
- FreeR flags: <https://www.ccp4.ac.uk/html/freerflag.html>
- Servalcat: <https://servalcat.readthedocs.io/en/latest/overview.html>
