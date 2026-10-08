# Lessons (date · lesson · evidence)

Append things learned the hard way; keep each entry short with an evidence pointer. Never add host names, user names,
accounts, partitions or local paths: this file ships in the public package (site-only lessons belong in a site copy).

- 2026-10-08 · **Never call `relion_wrapper.py --help` (or `cfm-relion --help`) by hand.** Without `LOCAL_RANK`/`RANK`
  the wrapper relaunches itself under `accelerate launch`; on a GPU-less staging node accelerate's simple launcher
  sets neither variable, so the chain never ends. Observed: repeated `[relion_wrapper.py] Launching with all available
  GPUs` / `accelerate launch --main_process_port 29500 /opt/cryofm/relion/relion_wrapper.py --help`, `Command …
  died with <Signals.SIGKILL: 9>` from `timeout`, then `OSError: [Errno 107] Transport endpoint is not connected`
  as the squashfuse mount was torn down. Read references/03 and 07 instead; the wrapper has no help screen.
  · this skill's build session, a CPU-only staging node of the validated site
- 2026-10-08 · `cfm denoise --help` really prints only the stub; the module help (`python -m
  cryofm.projects.cryofm2.uncond_sampling --help`) works on a CPU node inside the image in ~10 s (torch import).
  · live capture, references/live_help_2026-10-08/
- 2026-10-08 · `starfile` has no `__version__`; version it from `pip-freeze.txt` (0.5.13), not `import starfile`.
  · live check inside cryofm2.sif
- 2026-10-08 · A sub-1.5 Å input gives a whole-spectrum CC of only ≈0.30 between output and input; that is the 3 Å
  band limit, not a failure — compare after low-passing both to ≥ 3.5 Å (0.986 on the fixture). · job 27772406
- 2026-10-08 · The docs' memory table matched the A100 measurement (21 G vs 21 443 MiB at batch 4 + bf16), so the
  table can be trusted for sizing on 40 GB cards. · job 27772096
- 2026-10-08 · The denoised half maps of the fixture have exactly the input halves' FSC per shell: the outputs are
  not independent half maps, as the static reading predicted. · job 27772406, lowpass_cc.py
