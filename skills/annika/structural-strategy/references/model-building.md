# Model Building Strategies

## DNA/RNA Building

### From predicted models
- AF models predict protein well but DNA/RNA conformation is unreliable
- Expect unwound DNA in cryo-EM (not standard B-DNA)
- Trim DNA to density-supported residues only (0.5σ threshold at C4')
- Don't force standard geometry — let the density guide

### From scratch
- Use CryoREAD or EM2NA for de novo building if no template
- For DNA near proteins: superpose reference structure, extract DNA, local refine
- Local refine only for nucleic acids (global search → wrong pocket)
- Coot `ideal_nucleic_acid("DNA", "B", 0, sequence)` generates perfect B-DNA: chain A = input strand, chain B = complement (antiparallel). Good for terminal DNA rebuilding

### B-form quality gate
- Before accepting local duplex DNA updates: verify paired-window C1′–C1′ distances stay near ~10.5 Å
- Deviation from this indicates non-B-form or overfitting

### DNA SS restraints
- Auto-detected base pairs usually correct
- Verify C1'–C1' distances (~10.4Å for Watson-Crick)
- Stacking gaps = kink points → don't force stacking there

## Ligand Placement

### From reference structures
1. Find reference structure with same ligand + similar protein
2. Superpose reference chain → target chain
3. Extract ligand coordinates from superposed reference
4. Verify: is there density for the ligand? (map value > 0.3 at ligand atoms)
5. Place on dedicated chain (e.g. chain H)

6. For large cryo-EM cells (>400 Å), avoid `phenix.ligandfit`; reference transfer via ChimeraX matchmaker + Phenix RSR is more reliable when a homologous ligand structure exists. At ≥3 Å, density often cannot distinguish small-molecule orientation; use crystal chemistry/H-bond patterns plus density support.

### Novel ligand sites without a homolog
For inter-domain/inter-chain ligand sites with no homologous reference, use a **four-converging-lines orientation protocol** before committing to a modeled orientation:
1. Scan residue environments at each end of the elongated density (5 Å sample zones along the anchor axis) and match chemistry (e.g. aromatic stacking ↔ ring, positive cluster ↔ carboxylate tail).
2. Check biological channeling/substrate-flow logic: which ligand end should face which pocket chemistry.
3. Seed both plausible orientations by rigid transform, local fitmap, and density z-mean scoring.
4. Compare **per-atom CC on unrefined seeds** for both orientations to avoid “winner refined harder” bias.

Only run full ISOLDE+Phenix on both orientations if these lines disagree; if they agree, refine only the winner.

### Cryo-EM ligand docking with EMERALD
- Use Rosetta EMERALD when a small molecule must be docked directly into cryo-EM density and no trustworthy transferred pose exists.
- Best fit: ambiguous or novel sites where density should help choose among poses, but the binding-site model is already locally reasonable.
- Use **local binding-site resolution**, not the global map resolution; EMERALD is sensitive to `edensity::mapreso`.
- Generate ligand `.params` with GenFF / AM1-BCC charges before docking.
- Execution lives in the `emerald` skill; this file is strategy only.

### Speculative ligand contacts
If a proposed side-chain/ligand interaction is clash-free by rotamer scan but absent in the refined model, gate any restraint test with an omit-style real-space difference map first. A weak +2 to +3σ lobe can justify one weak single-pair restraint test; if short Phenix RSR still cannot move the side chain into contact, treat the interaction as **geometrically accessible but unoccupied** and keep the unrestrained model. Do not promote it to a modeled contact just because rotamers exist.

### Nucleotide ligands (ADP, ATP, GTP)
- Use CCD restraints: `phenix.elbow --chemical_component ADP --opt`
- For ISOLDE: ADP template expects specific H-atom naming (H5'1/H5'2, not H5'/H5'')
- Check for spurious atoms/bonds from addh

### Cofactors
- Place from homologous structure by superposition
- Verify density support before keeping
- Weak density (map < 0.1) → drop the ligand, note it

## Metal Ion Placement

### Strategy
- Place metals using coordination geometry from known motifs
- Calculate center of coordinating atoms (SG for CYS, NE2/ND1 for HIS, OE for GLU)
- Literature distances: Zn-SG 2.33Å, Zn-NE2 2.05Å, Zn-OE 1.95Å, Mg-O 2.05-2.10Å
- Always verify density at metal position

### Zinc sites
- Typical 4-coordinate tetrahedral: CYS, HIS, GLU/ASP
- L-Zn-L angles should be ~109.5°
- Use Phenix .edits restraints (tight sigma for close bonds, loose for distant)

### Magnesium sites
- Typically 6-coordinate octahedral
- Often coordinated by nucleotide phosphates + protein sidechains + waters
- Trans axes should be ~180°
- GHKL ATPases (PMS2/MLH1): use 1 Mg per ANP, not 2. Mg coordinates β/γ phosphate oxygens + conserved Asn OD1

### MG-phosphate clash in nucleotide ligands
- MG→PA clash (e.g., 1.77Å in ANP) is a triphosphate conformation issue, not Mg positioning
- The 4 coordinating oxygens surround PA geometrically; no Mg position satisfies all targets without PA clash
- Fix: rebuild ANP phosphate tail conformation

### Ambiguous density
- If density is weak at metal position: keep the metal but flag it
- If two metals are close: try modeling both, keep only those with clear density after refinement
- Water vs ion at >3Å: don't model ions unless coordination geometry is clear

## Coot Headless Operations

### Acceptance workaround (--no-graphics)
- Direct `c_accept_moving_atoms()` / `accept_regularizement()` are crash-prone in `coot --no-graphics`
- Safer path: enable **immediate replacement** and call **`accept_moving_atoms_py()`** after refine/move operations
- Output coordinates do change — always validate the refined region afterward

## Gap Filling

### When gaps appear
- After post-ISOLDE trimming: some residues removed create chain breaks
- Single-residue gaps from aggressive trimming

### Protocol
1. Identify gaps (breaks in chain continuity)
2. Restore missing residues from pre-trim model
3. Shift coordinates using flanking residue displacement
4. Run ISOLDE 2-5min to relax into density
5. Internal gaps <5 residues below threshold → KEEP (preserve continuity)
6. Internal gaps ≥5 residues → TRIM (not enough density support)
