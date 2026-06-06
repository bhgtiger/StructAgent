# 06 · Interoperability (RELION / cryoSPARC / napari-boxmanager)

crYOLO natively emits downstream-ready coordinate files. **VALIDATED against crYOLO 1.9.9**
(captured help + smoke run on a Linux + NVIDIA GPU host): a single prediction writes a
RELION-style `STAR/` folder, a native `CRYOSPARC/` coordinate-export folder, plus `EMAN/`,
`CBOX/`, and `DISTR/`. This reference states only what those captures and the smoke output
tree confirm; the one classic silent-failure point that is still unevidenced (coordinate
origin / y-flip across tools) is flagged as a verify-on-import caution, not omitted advice.

## What crYOLO writes (captured + smoke-confirmed)

Under the `-o`/`--output` folder, "All particle coordinates will be written there"
(captured help: `cryolo_predict.py.help.txt`). The on-disk tree from the smoke run
(the prediction `out/` folder) contains these subfolders:

- **`STAR/*.star`** — thresholded coordinates, **directly RELION-importable**. Confirmed
  column layout (read from `out/STAR/synth_0001.star`):

  ```
  data_

  loop_
  _rlnCoordinateX #1
  _rlnCoordinateY #2
  ```

  These are the standard RELION coordinate columns. (See ref 04 for the full file model.)
- **`CRYOSPARC/`** — a native cryoSPARC coordinate-export folder. The smoke prediction log
  emits `Write cryoSPARC coordinates` (`predict.log`, and
  the `CRYOSPARC/` dir is produced), so crYOLO writes a cryoSPARC-style coordinate export
  as part of every prediction.
- **`EMAN/*.box`** — thresholded boxes in EMAN1 `.box` format.
- **`CBOX/*.cbox`** — ALL detections (including below-threshold) with confidence and size;
  the re-thresholdable master output.
- **`DISTR/`** — distribution plots/data.

Note on empty folders: in the minimal non-filament smoke run, **both `CRYOSPARC/` and
`DISTR/` were created but empty** (`out/CRYOSPARC/`, `out/DISTR/`). Treat them as folders
crYOLO always creates, not as filament-only artifacts. (`VALIDATION_SUMMARY.md` describes
`DISTR/` as appearing for distribution/filament runs, but the on-disk minimal tree shows
both present — state them as always-created.) See ref 04 for the per-file format model.

## RELION import

The `STAR/*.star` files use `_rlnCoordinateX` / `_rlnCoordinateY` (confirmed above), which
is exactly the coordinate-column convention RELION reads for picked particles. A RELION
coordinate import therefore consumes the crYOLO `STAR/` output directly; you point
RELION's import/extract at the `.star` coordinate files matched per micrograph.

- Pixel size / box size for extraction are RELION-side parameters — set them from your data
  acquisition, not from the crYOLO box-size positional (which sets `model.anchors`; ref 03).
- **Verify-on-import caution (still unevidenced):** the captures do NOT state the coordinate
  **origin or y-flip** convention of crYOLO's `.star`/`.box`/`.cbox` outputs relative to a
  given RELION/cryoSPARC version. This is the classic silent particle-mislocation point.
  Before trusting a batch, do a one-micrograph round-trip: import the coordinates, overlay
  the extracted picks on the micrograph in the downstream tool, and confirm they land on
  particles (not y-mirrored). Do this once per tool/version pairing.

## cryoSPARC import

Two real paths, both grounded:

1. **Native `CRYOSPARC/` export.** crYOLO writes a cryoSPARC coordinate folder on every
   prediction (`Write cryoSPARC coordinates` in `predict.log`; `out/CRYOSPARC/` produced).
   This is crYOLO's own cryoSPARC-targeted output and is the intended hand-off for an
   "import particle coordinates"-style job.
2. **External picker via `cryosparc-tools`.** When you want crYOLO to run as a step inside a
   cryoSPARC pipeline, the standard pattern is a cryoSPARC external-picker job that shells
   out to `cryolo_predict.py` and feeds the resulting coordinates back. The crYOLO side of
   that is fully validated here (`cryolo_predict.py` flags and output layout, ref 03/04);
   the cryoSPARC `cryosparc-tools` external-job wiring is the cryoSPARC project's API and is
   not part of the crYOLO captures — treat its exact calls as cryoSPARC-side, not crYOLO.

Apply the same one-micrograph round-trip / y-flip check (above) on first use.

## napari-boxmanager and the box tools

These ship with crYOLO 1.9.9 (confirmed present in `_versions.txt` "which scripts" list):

- **`napari_boxmanager`** — napari-based box viewer/editor; the modern successor to the
  legacy boxmanager GUI.
- **`cryolo_gui.py boxmanager`** — the in-tree box manager; captured flags are
  `-i/--image_dir`, `-b/--box_dir`, `--wildcard` (captured help:
  `cryolo_gui.boxmanager.help.txt`). See ref 03.
- **`cryolo_boxmanager_legacy.py`** and **`cryolo_boxmanager_tools.py`** also exist
  (`_versions.txt`).

These read/write the same `.box`/`.cbox`/`.star` coordinate files described above, so they
are how you visually inspect or hand-edit picks between crYOLO and a downstream tool. Their
detailed per-tool launch flags beyond the captured `boxmanager` set are a remaining gap —
do not invent flags; run `--help` on the specific tool to confirm.

## Remaining gaps (genuine, not deferral)

- Coordinate **origin / y-flip** convention vs. a specific RELION/cryoSPARC version — not in
  any capture. Use the round-trip verification above instead of asserting it.
- Exact `cryosparc-tools` external-picker job code — cryoSPARC-side API, outside the crYOLO
  captures.
- `napari_boxmanager` / `cryolo_boxmanager_legacy.py` / `cryolo_boxmanager_tools.py` launch
  flags beyond the captured `cryolo_gui.py boxmanager` set — confirm with live `--help`.
