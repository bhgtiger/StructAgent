# Safety, privacy, and licensing

## TLS

Upstream's `install.sh` uses `wget --no-check-certificate` for the two
`yanglab.qd.sdu.edu.cn` downloads. **Do not copy it.**
`scripts/stage_cryoatom_weights.sh` uses `curl -fL` over a verified chain plus
exact byte-size checks, and `install/cryoatom.def` performs no download from
that host at all.

If TLS genuinely fails from a site, that is a diagnosis to make (missing CA
bundle, MITM proxy, expired chain), not a check to disable. Options in order:
fix the CA bundle, stage the files on a host where TLS validates and copy them
in, or ask the site's admins. Never normalise the bypass.

## Weight integrity

All six weight files are pinned by size and SHA-256 in
`<cache>/weights.pin.json`. The launcher size-checks them before every `build`;
`CRYOATOM_VERIFY_WEIGHTS=1` forces a full re-hash (~5.5 GiB read). Verify after
any copy, restore, filesystem migration, or quota incident — a truncated
checkpoint fails deep inside a GPU run, after the allocation is spent.

## Network at inference

With the cache staged, a run needs no outbound network. It is **not** sandboxed,
though — do not describe it as *provably* offline. If a site requires that
guarantee, run it inside the site's own network isolation and say that is where
the guarantee comes from.

## Licensing — surface these, do not paper over them

- Repository code is **MIT, © 2024 Baoquan Su**.
- **Model-weight licenses are separate and were not established here.**
  CryoAtom's own checkpoints, ESM-2, and RNA-FM each carry their own terms.
  Check before redistributing weights, mirroring them for a group, or publishing
  derived models under an assumed license.
- No full outbound-network audit of the package has been performed.
- The CryoAtom2 preprint's license does not authorise copying its text into this
  skill or into derived documentation.

For a shared cluster install, the mirroring question is real: staging weights
into a group-readable cache is redistribution to that group. Raise it once,
explicitly, and let the user decide.

## Cloud and data handling

- **Colab is not a harmless default.** Upstream offers a notebook; uploading
  unpublished, sensitive, controlled-access, or regulated maps and sequences is a
  distinct decision requiring its own retention/privacy assessment. If a local or
  cluster GPU exists, use it.
- Maps and sequences stay on the machine the user chose. Do not forward or upload
  them. Use placeholders in planning templates until the user supplies real
  paths, and then use those paths only for the run they authorised.
- Output trees can contain sequence-derived information. Treat them with the same
  care as the inputs.

## Reproducibility integrity

Do not relax the pinned dependency set to make a build succeed. If
`pytorch=2.1.0=py3.9_cuda11.8_cudnn8.7.0_0` has been pruned from the channel,
that is a genuine upstream reproducibility failure and should be reported as
one — with the exact solver error — rather than silently resolved to a different
build.

## Escalation

Name the unresolved gap and ask for an explicit decision. Do not route around it.
