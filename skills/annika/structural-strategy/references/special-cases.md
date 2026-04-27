# Special Cases

## Membrane Proteins
- Detergent/nanodisc density is NOT protein — don't model it
- Lipid densities near TM helices: model only with strong density + known binding sites
- Peripheral density is often ambiguous — err on the side of not modeling
- Use LipIDens-style analysis if lipid densities are strong enough

## Glycans / Post-Translational Modifications
- N-glycans: check Asn-X-Ser/Thr sequon before modeling
- Use Privateer for glycan conformation validation
- At >3Å: model at most 1-2 sugars of the glycan tree
- Core GlcNAc is usually visible; branching sugars rarely are

## Heterogeneity
- If density is blurred/weak → likely conformational heterogeneity, not just noise
- Options: 3DVA (cryoSPARC), cryoDRGN, RELION multi-body
- For modeling: pick the dominant state, note heterogeneity in deposition
- Don't model alternate conformations at >3Å (not enough resolution to justify)

## Low Resolution (>4Å)
- Backbone trace only — sidechains are unreliable
- Use secondary structure restraints heavily
- ISOLDE is essential (manual building nearly impossible)
- Expect high rotamer outlier rates — that's normal
- Focus on domain placement and overall architecture, not atomic details
- B-factors will be very high and poorly determined

## AlphaFold Models as Starting Points
- pLDDT < 50: delete these regions (disordered, will mislead fitting)
- pLDDT 50-70: keep but expect significant changes needed
- pLDDT > 90: usually reliable for backbone, sidechains may still be wrong
- Domain orientations are ALWAYS wrong in multi-domain predictions
- Loops connecting domains are unreliable regardless of pLDDT
- Use `alphafold pae` data if available for domain boundary identification

## Nucleic Acid-Protein Complexes
- Fit protein first, then nucleic acid (protein density is usually stronger)
- DNA/RNA conformation from AF is unreliable — always refit to density
- Expect non-canonical conformations (unwound, kinked, etc.)
- Use specialized tools (CryoREAD, EM2NA) for de novo NA building
- Base stacking at interfaces: verify with density, don't force canonical geometry

## Phosphorothioate DNA (PST, SC, AS, GS)

### The problem
- Non-standard DNA residues; most tools treat them as NON-POLYMER ligands
- Phenix RSR: no cross-residue backbone restraints (O3'-P-O5' angles scatter 82-153°)
- ISOLDE: OpenMM has no forcefield templates → instant crash ("Sim termination reason: None")
- Phenix eLBOW generates wrong restraints for nucleotide monomers (treats as isolated small molecules)
- Servalcat: "Link unidentified" — standard `p` link expects OP2 but PS residues use SP/S2P

### Working strategy: mutate-refine-mutate-back
1. Convert PS→standard DNA: PST→DT, SC→DC, AS→DA, GS→DG; rename SP/S2P→OP2 (element→O)
   - Removing S atoms entirely → missing OP2 errors
   - Renaming SP→OP1 → duplicates with existing OP1
2. Run Phenix RSR (full DNA backbone + base-pair + stacking restraints work correctly)
3. Convert back to PS residue names/atoms
4. Run Servalcat to fix P-S distances toward PS targets

### Servalcat angle workarounds
- Link CIF with `_chem_link` headers doesn't match → use `exte angle/dist` keywords via `--keyword_file`
- Standard `p` link references OP2 for angles/chirality; PS residues use SP/S2P — angles/torsions/chirality are NOT applied, only bond distances

### Practical notes
- `pdb_interpretation.max_reasonable_bond_distance = 100` needed for PS residues after ideal B-DNA grafting (inter-residue distances can exceed 50Å)
- AceDRG (CCP4 `~/ccp4-9/bin/acedrg`) generates Refmac-native ligand restraint CIFs for PS residues
- Local DNA auto-weighting can overfit badly for small PS windows (CC rises but clashscore explodes >600)

## Multi-Copy Complexes (NCS)
- Auto-detected NCS in Phenix is usually sufficient
- For homo-trimers (like PCNA): NCS restraints help but don't constrain
- Expect small differences between copies — that's biology, not error
- ISOLDE: NCS restraints ON by default for homo-multimers
