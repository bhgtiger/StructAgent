# Fitting Strategies

## Rigid-Body Fitting (Global)

### Standard protocol
1. Center model on map (center of mass → center of volume)
2. Run fitmap with high rotation samples: `fitmap search 500 placement r`
3. Local refinement: `fitmap` (no search)
4. Quality check: ≥60% atoms in density → pass

5. For AlphaFold oligomers/octamers, use: Merizo segmentation → centered global rotation search → mask-based chain selection → per-domain local refit → linker bridging → assembly → ISOLDE polish. Always center model COM on map center before rotation search.

### When standard fails
- Increase to 1000 rotation samples
- Try manual placement first (if you know roughly where it goes)
- For elongated molecules: try fitting largest domain first, then extend

### Convergence criteria
- avg map value should increase monotonically through fitting steps
- % atoms in density: >60% after global, >80% after domain fitting, >85% after ISOLDE

## Domain Fitting

### When to use
- Multi-domain proteins where global fit puts some domains in wrong density
- AlphaFold models where domain orientations are wrong (common)
- Any model where CC is decent globally but bad locally

### Protocol (from PCNA project)
1. Run Merizo on fitted model → get domain boundaries
2. For each domain:
   - Open fresh copy of model
   - Delete non-domain residues
   - `fitmap search 100 radius 5` + local `fitmap`
   - Record the position delta (model.position before vs after)
3. Apply all transforms to the complete original model
4. Interpolate transforms for linker residues (SLERP + LERP)

### Critical rules
- **NEVER extract domains and reassemble** → loses linkers + unassigned residues
- Discontinuous domains (e.g. E:487-570+669-756) are fitted as single unit
- DNA/RNA: local refine only (global search → wrong density pocket)
- Reject any domain fit with shift > 30Å (use identity transform instead)
- Skip small domains (<50 residues) for independent fitting

- At ~4 Å, independently fitted linkers can break domain junctions. If linker drift is >10° from the oligomer/octamer pose, keep/use oligomer-derived linker coordinates instead.

### AF oligomer fitting pipeline
- For AlphaFold oligomers: **Merizo segmentation → centered global rotation search → mask-based chain selection → per-domain local refit → linker bridging → assembly → ISOLDE polish** is the preferred pattern.
- Always center the model COM on the map center before the rotation search; otherwise fitmap can waste samples on translation error.
- For linker/domain junctions near ~4 Å resolution, independent linker fitting can drift and break junctions. If a linker fit drifts >10° from the oligomer pose, keep the oligomer-derived linker instead.

### Resolution-scaled approach (from ISOLDE skill design)
- Displacement < 1× resolution → ISOLDE handles the remaining shift
- Displacement > 1× resolution → per-domain rigid-body fit needed first
- Always measure displacement after fitting to decide next step

## Flexible Fitting (ISOLDE)

### When ISOLDE is the right choice
- After rigid-body fitting, when local regions still don't match density
- Backbone register errors
- AlphaFold models with wrong loop conformations
- Any region where manual building would take too long

### Strategy
- Start with short runs (5-10 min) and check
- Don't run >15 min without checkpointing
- Use targeted selection for local fixes: `isolde sim start sel`
- For global flexible fitting: 10min default, monitor every 30s

### Local DNA patch strategy
- For weak local DNA density (e.g., single base-pair windows): short ISOLDE local MDFF (3 min) followed by gentle local Phenix cleanup outperforms Phenix-only local refinement
- Especially effective for regions where Phenix auto-weighting overfits

### What ISOLDE can't fix
- Completely wrong chain trace (need to rebuild)
- Missing density (can't fit into nothing)
- Sequence register errors >5 residues (need manual intervention + Coot)
