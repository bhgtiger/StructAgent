# Trigger tests

When the skill SHOULD activate, when it should NOT, and the first move it must make
(always the config gate — `references/10_decision_trees.md` T1).

## Should trigger

| # | User utterance | First move |
|---|---|---|
| 1 | "How do I run cryoDRGN `train_vae` here?" | config gate; if absent → offer probe, no command. On a `ready` host emit the concrete `train_vae` command with the user's paths, labeled. |
| 2 | "Can this machine run cryoDRGN?" | config gate; read/run probe; report ready/partial/blocked. |
| 3 | "Parse my RELION star poses for cryoDRGN." | config gate; then `parse_pose_star` command (labeled), run on a `ready` host after explicit confirmation. |
| 4 | "What's the difference between cryoDRGN and cryoDRGN-AI / `abinit`?" | general explanation (no machine specifics needed); may answer pre-config. |
| 5 | "Downsample my particles to 128 with cryodrgn." | config gate; then `downsample` command (labeled), run on a `ready` host after explicit confirmation. |
| 6 | "cryodrgn analyze epoch numbering looks off by one." | explain 1-based indexing (4.2.1 help: "epoch number N ... 1-based"); confirm version via report. |
| 7 | "Set up cryoDRGN heterogeneous reconstruction from a cryoSPARC refinement." | config gate; then workflow A overview (labeled commands). |
| 8 | "Why is my cryoDRGN map mirrored / inverted?" | handedness/sign troubleshooting (ref 09); checks, not certainties. |
| 9 | "Install cryoDRGN for me." | no blind install; offer the documented install and run it only after explicit user confirmation (Linux + NVIDIA GPU caveat). |
| 10 | "Plan a D=128 pilot then D=256 high-res run." | config gate; decision tree T3 + workflow A (labeled). |

## Should NOT trigger (or hand off)

| # | Utterance | Why |
|---|---|---|
| A | "Reconstruct my homogeneous map in RELION/cryoSPARC." | not cryoDRGN (unless heterogeneity/cryoDRGN named). |
| B | "Explain VAEs in general." | generic ML; not cryoDRGN-specific. |
| C | "Write a SLURM script for my cluster." | run the config gate for that server first; emit a SLURM template once its support is known (capture its probe report before tuning lanes/partitions). |
| D | "Train a generic PyTorch model." | unrelated to cryoDRGN. |

## Invariants every triggered response must honor

- Run the **config gate first**; fail closed on absent/stale/unknown.
- Never emit an unlabeled runnable command; every command carries
  `[config-state: <ready|partial|blocked|absent|stale|unknown>]` plus a validation tag
  `[VALIDATED: cryoDRGN 4.2.1]` citing the captured help file where the flags were confirmed
  (e.g. `cryodrgn.train_vae.help.txt`). Add `[run-with-confirmation]` on any command that
  touches real data/compute; reserve `[not-run]` for illustrative/destructive examples only.
- No blind installs/uploads; run cryoDRGN / launch dashboard or filter / submit jobs only on
  a `ready` host after explicit user confirmation.
- Never upload/move/delete user data; treat `.mrcs`/`.star`/`.cs`/`.pkl`/outputs as private.
- Cite sources (`references/01_source_map.md`) and cite the captured 4.2.1 live help
  (the captured `*.help.txt` files, captured 2026-06-06 on a Linux + NVIDIA GPU host) as the realized
  #1 trust source — commands are `[VALIDATED: cryoDRGN 4.2.1]`, not live-unverified.
