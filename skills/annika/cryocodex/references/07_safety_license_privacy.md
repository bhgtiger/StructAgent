# 07 — Network egress, pickled weights, licences, privacy

Facts from the code at `a35e73a` and the sources gathered on 2026-11-24. No legal advice: quote the texts, name the gaps.

## 1. What leaves the machine

| Route | Outbound | Inbound | Does the user's map leave the host? |
|---|---|---|---|
| `predict.sh` with weights already in place | nothing found in the code (no telemetry, update or version check; third-party libraries unverified — runbook R17) | — | **no** |
| `predict.sh`, first call without weights (anything but `-h`/`-h advanced`, incl. `--version`) | one HTTPS GET to `yanglab.qd.sdu.edu.cn` | `CryoCodex.pth`, 470,938,660 B, `curl -fL --retry 2` (`predict.sh:76-91`) | no |
| README install | github.com, the host's conda channels, PyPI | env (torch 2.5.1 + CUDA 12 wheels, ~1 GB+), clone | no |
| Colab notebook ("Online inference") | user's Colab session, PyPI, download.pytorch.org, GitHub, the lab server, jsdelivr (browser) | env + weights on the VM | **yes — uploaded to a Google Colab VM** |

**Offline / air-gapped hosts**: download the checkpoint once on a machine with access, copy it to
`<clone>/model_state_dicts/CryoCodex.pth`, check the size (and your recorded sha256), then `predict.sh` makes no
download attempt (it only tests "file exists and is non-empty", `predict.sh:77`).

## 2. The checkpoint is an unverified pickle

- No checksum, signature or version marker is published (README, LICENSE, release, lab page and preprint checked;
  `.sha256`/`.md5`/`SHA256SUMS` paths on the lab server return 404). The server ETag `"1c11f424-…"` is size-based
  (0x1c11f424 = 470938660), not a content hash.
- `predict.sh` checks only that the file is non-empty; `predict.py:47` loads it with
  `torch.load(..., weights_only=False)` — full unpickling, so code inside a tampered file would run.
- **Do, once per host, before the first inference** (runbook R7–R8): compare the size with 470,938,660 B; record
  `sha256sum` (probe `--hash`) in `configs/site_config.local.md` as `weights.sha256`; load it once with
  `torch.load(path, map_location="cpu", weights_only=True)` and expect a dict with key `model_state_dict`. If that safe
  load fails, stop and decide with the user before running CryoCodex.
- Compare the sha256 across hosts. A changed size, ETag or Last-Modified on the server means a new, unannounced file:
  treat it as a new version (re-validate).

## 3. Licences and terms (as published; 2026-11-24)

| Item | Terms | Say |
|---|---|---|
| CryoCodex code | MIT, "Copyright (c) 2026 Bin Cheng" (`LICENSE:1-3`) | "the code is MIT-licensed" |
| Adapted third-party code | VAR (`quant.py`), EMReady2 (`grid_utils.py` I/O + interpolation), model-angelo (`make_cubic`, auto-mask): all MIT (`THIRD_PARTY_NOTICES.md`) | — |
| Python dependencies | their own licences (not gathered) | "check the dependencies' licences yourself" |
| Weights `CryoCodex.pth` | **no terms published anywhere** (not in LICENSE, whose MIT text covers "this software and associated documentation files", nor anywhere else) | "no licence or terms for the weights are published; ask the authors (corresponding authors in the preprint) before redistributing, mirroring or commercial use". Never call them MIT, open, redistributable or free for commercial use |
| Preprint | CC BY-NC-ND 4.0, not peer reviewed | quote with attribution; no adapted or commercial reuse of the paper text |
| Benchmark lists and per-map results on the lab site | no terms stated | link, don't redistribute |
| EMDB maps (e.g. the EMD-10387 fixture) | EMDB's public terms; cite the entry | — |

Citation: the bioRxiv preprint (BibTeX in [01 §2](01_source_map.md)) plus the version/commit used.

## 4. Privacy wording for users

- "Run locally, CryoCodex does not send your map anywhere; its only network access is the one-time weights download."
- "The Colab notebook uploads your map to a Google-hosted machine under your Google account. Do not use it for
  unpublished, confidential or proprietary data." Never recommend it as a fallback for a missing GPU.
- Logs and run plans contain absolute paths and map names: keep them out of public files. `configs/site_config.local.md`
  is git-ignored; `lessons.md` ships publicly — no host names, user names, accounts, partitions or private map names.

## 5. Operational safety rails (summary of SKILL.md)

- Ask before every install, the weights download, and every GPU job — one action per approval.
- A new output directory per run; absolute paths; never write into another tool's project or environment.
- Not on login nodes (use the Slurm template); never `--crop_check True` outside an interactive terminal.
- Never install CryoCodex into a cryoSPARC, RELION or Scipion environment.
- Do not run `predict.sh --version` "just to check" on a host without weights — it downloads 471 MB first.
