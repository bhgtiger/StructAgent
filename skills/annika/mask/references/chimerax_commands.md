# ChimeraX Command Cheat Sheet — Mask Workflow

## molmap (model → simulated map)
```
molmap <atomspec> <resolution> [gridSpacing <p>] [edgePadding <e>] [onGrid <#vol>]
```
- `gridSpacing` = output apix (Å). Set to target map's apix.
- `onGrid #1` skips the resample step at the end (already on target grid). **But** beware: `onGrid` uses the existing volume's box — if model lies outside, output is clipped.
- Examples:
  - `molmap /A 16 gridSpacing 1.06` — chain A at 16 Å, 1.06 Å/vox
  - `molmap /A:120-340 12 gridSpacing 1.06` — domain
  - `molmap sel 20` — current selection

## volume gaussian (smoothing / soft edge)
```
volume gaussian <#id> sDev <σ_Å>
```
- σ in **Å**, not voxels.
- Use early to denoise a map (σ = 2 × apix is typical).
- Use late to soften a binarized mask (σ = 5 × resolution).

## volume threshold (binarize / clamp)
```
volume threshold <#id> [minimum <v> set <out>] [maximum <v> setMaximum <out>]
```
Keywords are exactly: `minimum`, `set`, `maximum`, `setMaximum`. (`setMinimum` does **not** exist.)

- `minimum v set x` → values **<** v become **x**; values ≥ v unchanged.
- `maximum v setMaximum x` → values **>** v become **x**; values ≤ v unchanged.
- **Binarize at threshold t** — needs two calls (each produces a new volume):
  1. `volume threshold #X minimum t set 0`   → values < t → 0
  2. `volume threshold #Y maximum 0 setMaximum 1`   → values > 0 → 1
- ⚠ Each call produces a **new volume**. Track the new ID.

## Dilation (no native command — use a trick)
ChimeraX has no built-in mathematical morphology. To dilate a binary mask by ~d Å:
```
volume gaussian #X sDev <d>        # blur (smears the 1s outward)
volume threshold #Y minimum 0.25 set 0     # cut low-value tail
volume threshold #Z maximum 0 setMaximum 1 # re-binarize
```
Tuning: lower the threshold (0.1–0.3) for wider dilation, higher (0.4–0.5) for narrower.

## volume resample (onto target box/origin)
```
volume resample <#id> onGrid <#target>
```
- Use **always** before saving, even if model is in-frame. Guarantees CryoSPARC-acceptable box.

## volume copy / subtract / add
```
volume copy <#id>
volume subtract <#A> <#B> [minRMS false]
volume add <#A> <#B>
```
- `volume subtract` for the complementary subtraction mask. Negative results possible → clamp with `volume threshold #X maximum 0 set 0`.

## save
```
save <path> #<id>
```
- File extension determines format: use `.mrc`.

## Reset
```
close all
```
- Start every batch job with this. ChimeraX does **not** renumber after `close <id>`; only `close all` truly resets.

## Atomspec quick ref
| Spec | Meaning |
|---|---|
| `#1` | model 1, all atoms |
| `/A` | chain A in any model |
| `/A:120-340` | chain A residues 120–340 |
| `#2/A:120-340` | model 2, chain A, 120–340 |
| `/A,B,C` | chains A or B or C |
| `protein` | all protein residues |
| `nucleic` | all DNA/RNA |
| `sel` | current selection |

## Diagnostics
```
volume #1 settings    # print box, step, origin
vop                   # volume operations sub-command list
info models           # list models with ids
```
