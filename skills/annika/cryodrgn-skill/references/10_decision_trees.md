# 10 — Decision trees

Text trees for the choices the skill makes. They always start from the config
gate (T1): the read-only probe decides, per host, whether commands may be
emitted and run. Flags below are `[VALIDATED: cryoDRGN 4.2.1]` against the
captured live `--help` (a Linux + NVIDIA GPU host, 2026-06-06); the named help file is cited
on each branch. Commands that touch real data/compute carry
`[run-with-confirmation]`; only illustrative/destructive examples are `[not-run]`.

## T1 — The config gate (run this FIRST, every time)

```text
User asks anything machine-specific / a command / a workflow?
│
├─ Is there a report (configs/site_config.local.md or pasted) for THIS host?
│     ├─ no  → config_state = absent → general explanation only;
│     │         offer to run the read-only probe. STOP (fail closed).
│     └─ yes → is it current? (≤ TTL AND no staleness trigger)
│             ├─ no  → stale → treat as absent; ask to re-run probe. STOP.
│             └─ yes → read config_state:
│                   ├─ unknown → explain uncertainty; ask re-run/paste. STOP.
│                   ├─ blocked → explain blockage (e.g. no NVIDIA GPU, or a
│                   │            platform cryoDRGN does not support — see note);
│                   │            recommend a suitable host. NO concrete cmds.
│                   ├─ partial → concrete commands for captured-safe classes;
│                   │            execute simple ops with confirmation; suggest
│                   │            --live-help to resolve the rest.
│                   └─ ready   → concrete commands with the user's real paths;
│                                execute after explicit user confirmation.
```

Platform note (general, sourced — NOT a verdict on any one host): cryoDRGN's
packaging ships only `Operating System :: POSIX :: Linux`
[src: sources/source/cryodrgn_4.2.1/pyproject.toml] and the install docs require
a Linux workstation/cluster with NVIDIA GPUs. The probe turns this into a
per-host `config_state`; the skill never hardcodes a machine's outcome.

## T2 — cryoDRGN VAE (train_vae) vs cryoDRGN-AI (abinit)

```text
Do you have reliable consensus poses (a homogeneous C1 refinement in
RELION/cryoSPARC) for these particles?
│
├─ yes → heterogeneous reconstruction WITH known poses:
│        parse_pose_* + parse_ctf_*  →  train_vae --poses pose.pkl --ctf ctf.pkl
│        --zdim Z   [run-with-confirmation]
│        (train_vae REQUIRES --poses and --zdim; --ctf optional. Poses are fixed
│         unless you add --do-pose-sgd, a real flag that refines them by gradient
│         descent — defaults --pretrain 1, --emb-type quat, --pose-lr 0.0003.)
│        [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt]
│
└─ no / poses unreliable → ab initio (cryoDRGN-AI; pose search built in):
         abinit particles -o OUTDIR --zdim Z [--ctf ctf.pkl]   [run-with-confirmation]
         (abinit REQUIRES --zdim and does NOT take --poses; it has --load-poses
          only for resuming from a pose.<epoch>.pkl checkpoint, plus --ctf.)
         [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.abinit.help.txt]
```

Legacy hierarchical-pose models (cryoDRGN2): `abinit_het_old` / `abinit_homo_old`.
These also REQUIRE `--zdim`, default `--enc-dim/--dec-dim 256` (do NOT generalize
the 1024 train_vae default to them), and their own usage examples invoke them as
`abinit_het` / `abinit_homo`.
[VALIDATED: cryoDRGN 4.2.1 — cryodrgn.abinit_het_old.help.txt / cryodrgn.abinit_homo_old.help.txt]

## T3 — Box size: pilot vs high-resolution

```text
What is the goal of THIS run?
│
├─ first pass / sanity / particle filtering / very large dataset (>300k)
│     → downsample to D=128 (and/or a particle subset); small zdim (e.g. 8);
│       ~25 epochs; cheap, fast, used to find junk.
│
└─ high-resolution heterogeneity after a clean pilot
      → downsample to D=256 (max recommended); train on kept particles
        (--ind indices.pkl); consider --multigpu for D=256; ~25→50 epochs.
Inputs larger than 256 should be downsampled to 256 (README / install docs).
downsample -D must be EVEN ("New box size in pixels, must be even").
[VALIDATED: cryoDRGN 4.2.1 — cryodrgn.downsample.help.txt; box-size guidance: README/install docs]
```

## T4 — Which parser (poses/CTF source)

```text
Where did the refinement come from?
│
├─ RELION .star  → parse_pose_star (positional input; --outpkl PKL, alias -o)
│                  + parse_ctf_star (positional star; -o O)
│                  Only -D and --Apix are optional overrides if missing from the
│                  file; parse_ctf_star also takes --kv --cs -w --ps --png.
│  [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.parse_pose_star.help.txt / cryodrgn.parse_ctf_star.help.txt]
│
├─ cryoSPARC .cs → parse_pose_csparc (positional input; -D required, -o PKL;
│                  flags --abinit / --hetrefine; NO --Apix)
│                  + parse_ctf_csparc (positional cs; -o O; optional -D --Apix --png)
│  [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.parse_pose_csparc.help.txt / cryodrgn.parse_ctf_csparc.help.txt]
│
└─ already phase-flipped images → a CTF .pkl is not strictly required:
   train_vae --ctf is OPTIONAL, and a phase-flip utility exists
   (cryodrgn_utils phase_flip mrcs ctf_params -o OUT.mrcs).
   [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt / cryodrgn_utils.phase_flip.help.txt]
Broken .mrcs paths inside a .star/.cs → add --datadir <dir>.
```

## T5 — zdim (latent dimension) sizing — heuristic, confirm with developers

```text
How much heterogeneity / how exploratory?
│
├─ quick look / mostly homogeneous     → small zdim (e.g. 1–8)
├─ typical heterogeneous exploration   → zdim ~8 (a common default in docs examples)
└─ rich/continuous motions             → larger zdim, but watch overfitting + interpretability
Always pilot at D=128 first; compare 25 vs 50 epochs for convergence.
(zdim choice is a modeling decision — present as guidance, not a guarantee.)
NOTE: --zdim is a REQUIRED argument for train_vae, abinit, and train_dec — there
is no default; you must pass an integer.
[VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt / cryodrgn.abinit.help.txt / cryodrgn.train_dec.help.txt]
```

## T6 — "Map looks wrong" triage (see 09 for detail)

```text
What's wrong with the volume?
│
├─ contrast inverted (protein light vs dark) → cryoDRGN INVERTS the data sign by
│     default; if your stack is already in the non-inverted convention, pass
│     --uninvert-data ("Do not invert data sign") to train_vae / backproject_voxel
│     / abinit. It is a "do NOT invert" toggle, not an "invert it for me" switch.
│  [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.train_vae.help.txt / cryodrgn.backproject_voxel.help.txt / cryodrgn.abinit.help.txt; see ref 09]
├─ mirrored vs your reference (handedness) → flip the OUTPUT volume:
│     cryodrgn_utils flip_hand input.mrc -o flipped.mrc (--outmrc / -o; defaults
│     to <name>_flipped.mrc).   [VALIDATED: cryoDRGN 4.2.1 — cryodrgn_utils.flip_hand.help.txt]
├─ too noisy from a quick check → use more images (backproject_voxel --first N,
│     or train on the full stack).   [VALIDATED: cryoDRGN 4.2.1 — cryodrgn.backproject_voxel.help.txt]
└─ latent is one blob / junk → filter junk (--ind), train longer, or reconsider
      poses (switch to abinit).
```

On a probe-`ready` host the skill emits these commands with the user's real
paths and runs them only after explicit confirmation; on `partial` it runs the
captured-safe ops with confirmation; on `blocked`/`absent`/`stale`/`unknown` it
stays general and fails closed (T1). Destructive or illustrative examples remain
`[not-run]`.
