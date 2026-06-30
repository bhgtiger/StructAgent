# 06 — Parameter Decision Tree

Start from defaults and justify every change. These are **heuristics** from the
paper/manual/README; exact numerical effects depend on the case and on a live
run this skill has not performed. Defaults are the baseline CLI values (ref 03).

## Default starting point (most cryo-EM cases)

```bash
./Namdinator_Generic.sh -p model.pdb -m map.mrc -r <resolution> -x
```

- `-x` (extra Phenix coordinate real-space refinement) is recommended by
  README/manual for many cryo-EM cases and gives `last_frame_rsr.pdb`. Drop it
  only if the user explicitly wants the raw MD frame or has the base Phenix
  commands on PATH but not the `PHENIXMASTERDIR`/`phenix_env.sh` setup required
  by the script's `-x` branch.
- Everything else default: `-g 0.3`, `-s 20000`, `-e 2000`, `-t/-f 300`,
  `-c 5`, `-b 20`, vacuum (no `-i`), HETATM removed (no `-l`).

## Knobs, and when to turn them

| Want / symptom | Change | Reasoning / caution |
|---|---|---|
| Run unstable; "atoms moving too fast" | **lower `-g`** (e.g. 0.3→0.1) and/or **raise `-e`** | Less aggressive map pull + more minimization stabilizes the start. Also re-check input geometry (ref 08). |
| Fit barely moves; model needs a stronger pull | **raise `-g`** carefully (e.g. 0.3→0.5–1.0) | Higher G-scale pulls harder but can distort geometry and destabilize — increase gradually and watch clashscore/Rama. |
| Larger conformational change needed | **raise `-s`** (toward 100000–500000) | Help suggests `20000–500000` for large changes. **Web caps at 200000**, so very long runs are local-only. |
| Geometry slightly poor, willing to pay time | add **`-i`** (GBIS implicit solvent) | May modestly improve geometry, but **~7× slower**. Usually not worth it for routine runs. |
| Model has ligands/metals/waters | think hard before **`-l`** | `-l` *often fails* (AutoPSF) and conflicts with `-x`. Prefer: run default (HETATM dropped) then **reinsert manually**, or use a different tool. Never promise `-l` keeps them. |
| Non-default temperature | `-t` / `-f` | Rarely needed. Note CLI default 300 K vs. web 298 K. |
| Off-Linux / specific core count | set `-n` explicitly | Default uses `lscpu` (Linux-only). |
| Higher resolution, want more Phenix cycles | `-c` (default 5; web UI caps at 5) | Diminishing returns. Whether the local script actually benefits from `-c` > 5 is **unverified** (no live run); don't assume it helps. Validate the result regardless. |

## Hard-case strategy (large motion / poor convergence)

From the paper's examples:

- **Two-step low-pass strategy (CorA, 3jcf/EMD-6551 → 3jch/EMD-6553):** first run
  against a **low-pass-filtered map (~20 Å)** with **low G-scale** and **many
  steps** to let big domains move without shredding geometry; then run against
  the **original map** with **higher G-scale** and **many steps** to refine.
- **Large rotations (>~40–45°):** split the model into domains, manually rotate
  each into density (ChimeraX/Coot), then run Namdinator domain-wise or on the
  recombined model. A single default run will not solve a big rigid rotation.
- **Simulated / noise-free maps (1ake → 4ake map):** long runs (~60,000 steps)
  can produce large CC gains; real maps are noisier, so don't extrapolate the
  magnitude.

## Guardrails

- Change **one knob at a time** so you can attribute the effect.
- MDFF is **stochastic** — for important cases, repeat and inspect, don't trust a
  single trajectory.
- More aggressive parameters trade geometry for fit. Always read clashscore,
  Ramachandran, and rotamers alongside CC (ref 07), not CC alone.
