# Coot Lessons Learned

## Distilled 2026-03-27

- **Headless acceptance crash workaround:** on this local build, direct acceptance calls like `c_accept_moving_atoms()` / `accept_regularizement()` are crash-prone in `coot --no-graphics` (GL/HUD code paths). A safer scripted path is:
  1) enable **immediate replacement**
  2) run the refine/move operation
  3) call **`accept_moving_atoms_py()`**
  This avoids the hard crash and produces a real coordinate change, but still treat results as **experimental** and validate the refined region.

- **Ligand distortion can hard-abort on linked chemistry:** `get_ligand_distortion_summary_info_py()` / “ligand-distortion” may hard-abort on mixed linked-chemistry models (e.g., phosphorothioate DNA residue types like `SC`). Guard behind an explicit unsafe flag and/or skip on risky models.

- **Water checking/pruning requires an active map:** `check_waters_baddies()` / `delete_checked_waters_baddies()` are not safe to run mapless; require an active map and a model that already contains waters.

- **Servalcat boxed/shifted map vs original EM map mismatch:** Servalcat outputs (maps/MTZ) may be in a trimmed box / shifted coordinate frame. When evaluating peak density for waters/ions, prefer the **original EM map** in the same frame as the model you’re inspecting, or explicitly account for origin shifts.

- **macOS crash dialog is a red flag:** if a smoke test leaves a macOS “Python quit unexpectedly” dialog, treat that execution path as unsafe-by-default for routine testing and switch to safer wrapper/batch paths.

## Distilled 2026-04-11

- **Coot 1.1 (GTK4) screenshot:** use the GUI menu **File → Save Screenshot…** (or **File → Screenshot**, depending on build) to save a PNG of the current GL view. In the Python console, `screendump_image("shot.png")` also works.
