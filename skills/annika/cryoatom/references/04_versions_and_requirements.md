# Version pin and hardware requirements

## The pin — read this before quoting any version fact

This package installs and describes **CryoAtom2 2.1.1, commit
`856e250df7b784b854b892f1b619d32d51188cef`, tree
`0058c0c68857b66962f9ad421756513e74de7518`** (commit date 2026-06-17, "Add
pre-hosted RNA-FM model download").

That is an **untagged master snapshot, not a tagged release**. The repository's
newest tag, `v2.1.0` (`10fd7f4be3722d6a1ea6646c69e93476014184ab`), is *behind*
this commit. Tags `v1.0.0` and `v2.0.0` both dereference to the same commit
(`e2a31f2b`), so no tag names this code — the 40-hex commit is the only honest
pin, and the tree hash is the content identity that catches a rewritten history
reusing the same commit id.

Practical consequence: statements pinned to `v2.1.0` and statements about a
`856e250` install are not interchangeable. The difference at `856e250` is
**weight acquisition** (a pre-hosted RNA-FM download), which this package
bypasses entirely — weights are staged out-of-band into an external cache. The
`cryoatom build` flag surface was verified identical between the two.

If you install a different revision, change `version.expected`,
`version.source_commit`, and `version.source_tree` in the site config *and* in
`install/cryoatom.def`, and re-verify the flag surface against
`references/03_cli_and_outputs.md`.

## Scientific version distinction

- **CryoAtom v1** — peer-reviewed, protein-focused method evidence.
- **CryoAtom2** — protein, RNA, DNA, and protein-nucleic-acid claims from an
  unpinned, unreviewed preprint.

Never call CryoAtom2's RNA/DNA claims peer reviewed, and never transfer a v1
result or limitation to a specific 2.1.1 runtime claim.

## Documented requirements

Upstream specifies Linux, Python 3.9, CUDA 11.8, PyTorch 2.1.0, **≥14 GiB GPU
memory** for inference, and ≥4 GiB disk for its own weights plus the ESM/RNA-FM
language-model weights. In practice the external cache is ~5.5 GiB and a
container image ~4.5 GiB.

## What a healthy install looks like

A correctly built environment reports, inside the runtime:

```
python 3.9.x · torch 2.1.0 · torch.version.cuda 11.8
esm, fm, mrcfile, pyhmmer, Bio, numpy, scipy all import
getp links cleanly (no unresolved shared libraries)
checkpoint directory present but EMPTY inside the image — weights are external
```

`install/cryoatom.def`'s `%test` block asserts all of that at build time and
fails the build otherwise. For a native install, run the same checks by hand.

## GPU sizing

| Situation | Guidance |
|---|---|
| ≥14 GiB VRAM | Meets the documented floor |
| 24–48 GiB (e.g. A100-40GB class) | Comfortable for typical maps; the public 7XHT fixture is small |
| <14 GiB | Below the documented requirement. Do not present it as workable |
| Large map, OOM | Move to a larger-VRAM GPU, or crop/mask the density with `-m`. Do not silently downsample the science |

`--device cpu` exists in the source. It is **not** evidence of usable CPU-only
performance, and no CPU-only timing is established here.

## Unsupported platforms

macOS (Intel or Apple Silicon), Windows without WSL+CUDA, and any host without
an NVIDIA GPU are not CryoAtom execution platforms. Docker presence, unified
memory, and a CPU code path are not substitutes. Say so plainly and offer a
supported host or a queue instead of a workaround.
