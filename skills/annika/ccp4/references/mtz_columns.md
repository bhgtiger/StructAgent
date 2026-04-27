# MTZ columns and FreeR conventions

## Required columns by workflow

| Workflow | Required columns | Optional / common variants |
| --- | --- | --- |
| Refmac5 (X-ray, amplitudes) | `F`, `SIGF`, `FREE` (R-free flag) | `Fobs`, `SIGFobs`, `FreeR_flag`, `R-free-flags` |
| Refmac5 (intensities → French-Wilson upstream) | `I`, `SIGI`, `FREE` | use `ctruncate` to produce F/SIGF first |
| Phaser MR | `F`, `SIGF` | `I`, `SIGI` accepted |
| Buccaneer / Nautilus | `F`, `SIGF`, plus phases (`HLA`/`HLB`/`HLC`/`HLD` or `PHI`/`FOM`) | `FWT`/`PHWT` for map-only inputs |

## FreeR conventions

- CCP4 convention: a single integer column (commonly `FreeR_flag`) where one value (often `0`) flags the test set. The MTZ column type is `I`.
- Phenix convention: a binary column (`R-free-flags`) where `1` is the test set. Type `I`.
- Column type `F` or `J` for FreeR is wrong and almost always a sign of a hand-built MTZ.

The MTZ preflight reports the column type and the apparent test-set fraction (typical: 5%–10%). Anything outside ~3%–15% should be treated as suspicious and surfaced to the user.

## Reading an MTZ in v1

`mtz_preflight.py` prefers `gemmi` (structured access to columns, types, cell, and symmetry):

```python
import gemmi
mtz = gemmi.read_mtz_file("data.mtz")
for col in mtz.columns:
    print(col.label, col.type)
print(mtz.cell, mtz.spacegroup.hm if mtz.spacegroup else None)
```

If `gemmi` is unavailable, it falls back to parsing `mtzdump`:

```text
echo -e "HEAD\nEND\n" | mtzdump HKLIN data.mtz
```

`mtzdump` prints column labels and types in a table; the parser is intentionally narrow (the table headings are stable, but `mtzdump` output is whitespace-sensitive — keep changes here small and add a fixture before touching it).

## Building a `--labin` string

The wrapper expects exactly the form Refmac5 wants in its `LABIN` keyword:

```text
FP=F SIGFP=SIGF FREE=FreeR_flag
```

Anomalous:

```text
F+=F(+) SIGF+=SIGF(+) F-=F(-) SIGF-=SIGF(-) FREE=FreeR_flag
```

The preflight prints a suggested `--labin` string when there is exactly one unambiguous candidate per role. When more than one candidate exists, it lists them and refuses to guess — copy the right one into your command.

## Cell and space-group checks

When both an MTZ and a model are supplied, the preflight compares:

- unit cell parameters (within 0.5 Å on lengths, 0.5° on angles by default);
- space group H-M symbol after normalising whitespace.

A mismatch is a `[FAIL]`, not a warning, because Refmac will accept the inputs and produce nonsense.
