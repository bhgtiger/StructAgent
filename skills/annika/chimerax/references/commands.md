# ChimeraX Command Reference

## Table of Contents
1. [Atom Specifiers](#atom-specifiers)
2. [Structure I/O](#structure-io)
3. [Fitting & Alignment](#fitting--alignment)
4. [Measurement](#measurement)
5. [Editing — Atoms & Bonds](#editing--atoms--bonds)
6. [Editing — Chains & Models](#editing--chains--models)
7. [Transforms](#transforms)
8. [Timeout Guidance](#timeout-guidance)
9. [Examples](#examples)

---

## Atom Specifiers

| Pattern | Meaning | Example |
|---------|---------|---------|
| `#N` | Model number N | `#1` |
| `#N.M` | Submodel | `#1.2` |
| `/C` | Chain C | `/A` |
| `:N` | Residue number N | `:42` |
| `:N-M` | Residue range | `:1-100` |
| `@name` | Atom name | `@CA` |
| `#1/A:42@CA` | Full spec | Model 1, chain A, res 42, atom CA |
| `#1/A,B` | Multiple chains | Chains A and B of model 1 |
| `solvent` | Built-in selector | All water molecules |
| `ligand` | Built-in selector | All ligands |
| `protein` | Built-in selector | All protein residues |
| `sel` | Current selection | Whatever is selected |
| `element.H` | By element | All hydrogens |

**Critical rules:**
- Chain IDs are **case-sensitive** (`/A` ≠ `/a`)
- Model numbers assigned sequentially by `open` — don't hardcode across open/delete sequences
- After `delete #1`, model `#2` does NOT renumber to `#1`
- Use `close all` before starting a new job to reset model numbering

---

## Structure I/O

| Command | Syntax | Notes |
|---------|--------|-------|
| `open` | `open /path/file.cif` | Also: `open 1abc` (fetch PDB), `open smiles:CCO`, `open /path/file.mrc` |
| `open` (explicit format) | `open /path/file.cif format mmcif` | Recommended: avoid format-guessing bugs |
| `save` | `save /path/out.cif` | Formats: `.cif`, `.pdb`, `.cxs` (session). Prefer `.cif` over `.pdb` |
| `save` (specific model) | `save /path/out.cif #1` | Save only model 1 |
| `close` | `close all` | Reset session; `close #2` closes specific model |
| `log save` | `log save /path/log.html` | Save ChimeraX log as HTML (audit trail) |

---

## Fitting & Alignment

| Command | Syntax | Capture returns | Timeout |
|---------|--------|-----------------|---------|
| `fitmap` | `fitmap #1 inMap #2` | `capture: true` → correlation, steps | 600s (large maps) |
| `fitmap` (with resolution) | `fitmap #1 inMap #2 resolution 4` | Map-in-map fitting | 600s |
| `fitmap` (global search) | `fitmap #1 inMap #2 search 100 placement sr` | Finds multiple fits | 600s+ |
| `matchmaker` | `matchmaker #1 to #2` | `capture: true` → RMSD per pair | 120s |
| `align` | `align #1/A:1-100@CA to #2/A:1-100@CA` | `capture: true` → rmsd, paired_rmsd | 30s |

**fitmap key parameters:**
- `resolution R` — generate density from atoms at resolution R (map-in-map fitting)
- `metric overlap|correlation|cam` — optimization metric
- `search N` — N random initial placements for global search
- `maxSteps N` — max optimization steps (default 2000)
- `logFits "/path/fits.csv"` — write fit results to CSV

**matchmaker vs align:**
- `matchmaker` = sequence-aware, for homologs (doesn't need pre-paired atoms)
- `align` = geometry-based, for explicit atom-to-atom correspondence

---

## Measurement

| Command | Syntax | Capture returns |
|---------|--------|-----------------|
| `measure distance` | `measure distance /A:45@CA /B:72@CA` | distance value |
| `measure rotation` | `measure rotation #1 #2` | rotation info |
| `measure correlation` | `measure correlation #1 #2` | map-map correlation |
| `measure buriedarea` | `measure buriedarea #1 with #2` | buried surface area |
| `measure sasa` | `measure sasa #1` | solvent-accessible surface area |
| `measure mapstats` | `measure mapstats #1` | map statistics |
| `measure mapvalues` | `measure mapvalues #1 atoms #2 attribute my_attr` | sample map at atom positions |
| `contacts` | `contacts #1 restrict #2 distance 4.0` | inter-model contacts |

---

## Editing — Atoms & Bonds

| Command | Syntax | Notes |
|---------|--------|-------|
| `delete` | `delete solvent` | Also: `delete /A`, `delete :42-50`, `delete element.H`, `delete ligand` |
| `addh` | `addh #1` | Key opts: `hbond true`, `inIsolation true`, `metalDist 3.95`, `template true` |
| `addcharge` | `addcharge #1 method am1-bcc` | Methods: `am1-bcc` (default), `gasteiger` |
| `dockprep` | `dockprep #1` | All-in-one: delete solvent/ions, complete sidechains, add H, add charges |
| `dockprep` (full) | `dockprep #1 delSolvent true delIons true delAltLocs true completeSideChains Dunbrack ah true ac true acMethod am1-bcc` | Explicit options |
| `swapaa` | `swapaa ARG /A:57` | Mutate residue to ARG |
| `swapaa` (criteria) | `swapaa TYR /A:42 criteria p` | Pick by prevalence only |
| `swapaa` (batch) | `swapaa /A:3-5,12 seq:LLYH` | Multiple mutations at once |
| `swapaa` (rebuild) | `swapaa same /A:88 preserve 30` | Rebuild same type within 30° chi tolerance |
| `bond` | `bond #1:100@C1 #1:100@O1` | Create a bond |
| `build modify` | `build modify sel O 2 geometry tetrahedral` | Change atom element/type |
| `build join bond` | `build join bond #1:29@oxt #2:1@h2 length 1.32` | Join two models with a bond |
| `build join peptide` | `build join peptide /A:C /B:N omega 180` | Join with peptide bond |
| `build start peptide` | `build start peptide "model" ADKLL -57,-47` | Build peptide from sequence |

**swapaa criteria letters:** `d` = density, `c` = clash, `h` = H-bond, `p` = prevalence. Default: `dchp`.
**swapaa rotamer libraries:** `Dunbrack` (default), `Dynameomics`, `Richardson.common`, `Richardson.mode`.

---

## Editing — Chains & Models

| Command | Syntax | Notes |
|---------|--------|-------|
| `changechains` | `changechains /A X` | Change chain A ID to X |
| `changechains` (swap) | `changechains #1 A,B B,A` | Swap chain IDs |
| `renumber` | `renumber /A start 1 relative false` | Renumber chain A from 1, consecutively |
| `renumber` (range) | `renumber /A:10-50 start 310` | Renumber specific range |
| `combine` | `combine #1,2 modelId 10 name complex close false` | Merge models into one |
| `combine` (retain IDs) | `combine #1,2 retainIds true` | Keep original chain IDs (fails on collisions) |
| `split` | `split #1` | Split by chain (default) |
| `split` (ligands) | `split #1 ligands` | Separate ligands into submodels |
| `altlocs clean` | `altlocs clean` | Delete all unused alternate conformations |
| `altlocs change` | `altlocs change B /A:42` | Switch to altloc B for residue 42 |

---

## Transforms

| Command | Syntax | Notes |
|---------|--------|-------|
| `move` | `move x 5 models #2` | Translate model 2 by 5Å along x |
| `move` (atoms) | `move z -2 atoms /A:45-60` | Move specific atoms (edits coordinates!) |
| `turn` | `turn y 90 models #2` | Rotate model 2 by 90° around y |
| `view` | `view #1` | Center view on model 1 |

---

## Timeout Guidance

| Command | Default timeout | When to increase |
|---------|----------------|------------------|
| `open` (local file) | 30s | Large maps (>1GB): 120s |
| `open` (fetch PDB) | 60s | Network issues |
| `fitmap` (local) | 120s | — |
| `fitmap` (search N>50) | 600s | Large maps + high search count: 1800s |
| `dockprep` | 300s | Very large structures (>10k residues) |
| `matchmaker` | 120s | Multiple chain pairs |
| `addh` | 120s | Large structures with metal sites |
| `addcharge` (am1-bcc) | 300s | Many nonstandard residues |
| All other commands | 60s | — |

---

## Examples

### Fetch PDB, prep for docking, save
```json
{
  "resultFile": "/tmp/cx_job/result.json",
  "commands": [
    "close all",
    "open 1abc",
    "dockprep #1 delSolvent true delIons true delAltLocs true ah true ac true",
    "save /tmp/cx_job/prepped.cif #1"
  ]
}
```

### Fit model into cryo-EM map
```json
{
  "resultFile": "/tmp/cx_job/result.json",
  "commands": [
    "close all",
    "open /data/model.cif",
    "open /data/map.mrc",
    {"cmd": "fitmap #1 inMap #2 resolution 3.5", "capture": true},
    "save /data/fitted.cif #1",
    "log save /tmp/cx_job/log.html"
  ]
}
```

### Superpose two structures
```json
{
  "resultFile": "/tmp/cx_job/result.json",
  "commands": [
    "close all",
    "open /data/ref.cif",
    "open /data/mobile.cif",
    {"cmd": "matchmaker #2 to #1", "capture": true},
    "save /data/aligned.cif #2"
  ]
}
```

### Edit model — delete chain, mutate, renumber, combine with ligand
```json
{
  "resultFile": "/tmp/cx_job/result.json",
  "commands": [
    "close all",
    "open /data/protein.cif",
    "delete solvent",
    "delete /C",
    "swapaa ARG /A:57 criteria p",
    "addh #1",
    "renumber /A start 1 relative false",
    "open /data/ligand.sdf",
    "combine #1,2 modelId 10 name complex close false",
    "save /data/final.cif #10"
  ]
}
```

### Complex analysis (standalone Python script)
For tasks needing loops/branching, write a standalone `.py` instead of using the wrapper:
```bash
"$CHIMERAX" --nogui --exit --script /path/to/interface_contacts.py complex.cif contacts.csv 4.0
```
