# ISOLDE Debugging Reference

## Table of Contents
1. [Silent Crash Debugging](#silent-crash-debugging)
2. [Template Matching Issues](#template-matching-issues)
3. [Ligand Template Verification](#ligand-template-verification)
4. [Common Failure Modes](#common-failure-modes)

---

## Silent Crash Debugging

When `isolde sim start` appears to succeed but `ih.simulation_running` is immediately `False` with "Sim termination reason: None":

### The Monkey-Patch (essential diagnostic tool)

```python
from isolde.openmm.sim_handler import SimHandler

_original_create = SimHandler._create_openmm_system

def _patched_create(self, *args, **kwargs):
    try:
        return _original_create(self, *args, **kwargs)
    except Exception as e:
        ff = self._forcefield
        top = self._topology
        try:
            assigned, ambiguous, unassigned = ff.assignTemplates(top)
            print("=== TEMPLATE ASSIGNMENT RESULTS ===")
            print(f"Assigned: {len(assigned)} residues")
            if ambiguous:
                print(f"AMBIGUOUS ({len(ambiguous)}):")
                for res, templates in ambiguous.items():
                    print(f"  {res.name} {res.id}: {[t.name for t in templates]}")
            if unassigned:
                print(f"UNASSIGNED ({len(unassigned)}):")
                for res, templates in unassigned.items():
                    print(f"  {res.name} {res.id}: {[t.name for t in templates]}")
        except Exception as e2:
            print(f"assignTemplates also failed: {e2}")
        raise

SimHandler._create_openmm_system = _patched_create
```

Run this BEFORE `isolde sim start`. The output tells you exactly which residues failed.

---

## Template Matching Issues

### HIS after PRO — Missing Backbone H

`addh` skips backbone H on residues following PRO. For HIS, missing H means no amber14 template (HID/HIE/HIP) matches.

**Detection:** In `unassigned` output, look for HIS residues.

**Fix:**
```python
import numpy as np

def add_backbone_h(session, residue, prev_residue):
    """Add backbone H to a residue missing it (e.g., after PRO)."""
    from chimerax.atomic import Element
    n = residue.find_atom("N")
    ca = residue.find_atom("CA")
    c_prev = prev_residue.find_atom("C")
    
    v1 = ca.coord - n.coord
    v1 /= np.linalg.norm(v1)
    v2 = c_prev.coord - n.coord
    v2 /= np.linalg.norm(v2)
    h_dir = -(v1 + v2)
    h_dir /= np.linalg.norm(h_dir)
    h_coord = n.coord + h_dir * 1.01
    
    h = residue.structure.new_atom("H", Element.get_element("H"))
    h.coord = h_coord
    residue.add_atom(h)
    residue.structure.new_bond(n, h)
```

### CYS Near Metals — Ambiguous Templates

CYS near metals may show as ambiguous (CYM/CYX/MC_CYF). ISOLDE's `cys_type()` checks SG bond count:
- 1 bond (only CB) → CYM (correct for metal coordination)
- SG–SG → CYX (disulfide)
- SG–H → CYS (protonated)

**Problem:** If you manually created a covalent bond from SG to a metal, bond count changes → wrong template selected → crash.

**Fix:** Never create covalent bonds to metals. Delete any manual metal bonds.

### C-terminal OXT

Residues with OXT have no amber14 template. Delete OXT:
```python
for a in model.atoms:
    if a.name == "OXT":
        a.delete()
```

### DNA Terminal OP3

5' terminal nucleotides with OP3 have no forcefield template.
```
delete #model/F:1@OP3
delete #model/G:1@OP3
```

---

## Ligand Template Verification

### Finding ISOLDE's Built-in Templates

```python
import zipfile, xml.etree.ElementTree as ET
from pathlib import Path
import isolde

# Find the template file
pkg_dir = Path(isolde.__file__).parent
mc_zip = pkg_dir / 'openmm' / 'amberff' / 'moriarty_and_case.zip'

with zipfile.ZipFile(mc_zip) as z:
    for name in z.namelist():
        if 'MC_ADP' in name:  # or whatever residue
            xml = z.read(name)
            root = ET.fromstring(xml)
            for res in root.iter('Residue'):
                atoms = [a.attrib['name'] for a in res.findall('Atom')]
                bonds = [(b.attrib['atomName1'], b.attrib['atomName2']) 
                         for b in res.findall('Bond')]
                print(f"Atoms ({len(atoms)}): {atoms}")
                print(f"Bonds ({len(bonds)}): {bonds}")
```

### ADP (MC_ADP) Template Requirements

Expected: 39 atoms (27 heavy + 12 H), 41 bonds.

After `addh`, common fixes needed:
| Fix | From | To |
|-----|------|----|
| Rename H5' | `H5'` | `H5'1` |
| Rename H5'' | `H5''` | `H5'2` |
| Delete spurious H | `H2B` on O2B | (delete) |
| Delete spurious bond | `O3A–O5'` | (delete) |

### Verification Script

```python
def verify_ligand(residue, expected_atoms, expected_bonds):
    """Verify a residue matches its ISOLDE template."""
    atom_names = sorted([a.name for a in residue.atoms])
    n_bonds = sum(1 for a in residue.atoms for b in a.bonds 
                  if b.other_atom(a) in residue.atoms) // 2
    
    missing = set(expected_atoms) - set(atom_names)
    extra = set(atom_names) - set(expected_atoms)
    
    ok = True
    if missing:
        print(f"MISSING atoms: {missing}")
        ok = False
    if extra:
        print(f"EXTRA atoms: {extra}")
        ok = False
    if n_bonds != expected_bonds:
        print(f"Bond count: {n_bonds} (expected {expected_bonds})")
        ok = False
    if ok:
        print(f"✅ {residue.name} matches template")
    return ok
```

---

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Sim termination reason: None" | Unparameterised residue | Use monkey-patch to find which residue |
| Sim starts, model drifts away | Map not associated (no MDFF forces) | Associate map via `nxmapset.add_nxmap_handler_from_volume()` |
| REST hangs indefinitely | Sent command during active sim | Use internal Python timer instead |
| Sim stops after a few seconds | Popup appeared, froze event loop | Run osascript popup handler |
| curl: connection refused | ChimeraX not running or REST not started | Bootstrap sequence |
| "No map fitting forces" warning | Map not associated with ISOLDE | Associate map (see above) |
| Port already in use | Previous ChimeraX didn't clean up | Use different port (9877) |
| HIP platform error | Wrong OpenMM platform | `ih.sim_params.platform = 'OpenCL'` |
| Sim explodes immediately | Bad geometry (huge clashes) | Try smaller selection first |
