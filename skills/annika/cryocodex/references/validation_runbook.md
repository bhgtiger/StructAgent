<!-- Copied into the cryocodex skill on 2026-11-24 from the evidence pack's sources/crosscheck/live_verification_checklist.md.
     Changes: citations into the pack's pinned clone were shortened to `<file>` (= the CryoCodex clone at the pin
     a35e73a), and R20's "On this Mac" reads "On the maintainer's machine". Every other `sources/...` path points into the evidence pack, which is not shipped with the skill
     (references/01_source_map.md section 3). "This project" below = that evidence-pack project folder. -->

> **How this skill uses this runbook.** It is the validation procedure for a GPU host. Run it once per host (R0–R16 are
> needed; optional steps as wanted), fill in `Observed:` and a status per step, then record the result in
> `configs/site_config.local.md` (state `VALIDATED` only if R11 and R12 pass) and anything surprising in `lessons.md`.
> All "Expected" values are derived from code and documents — **not observations** — until a host has run them.

# CryoCodex v1.0.0 — live-verification runbook for the GPU server (Task E)

Written 2026-11-24 (UTC) by Task E. **Nothing below has been run** (Task D skipped: no host with CryoCodex;
`plan/source_plan.md:68-69`). Every step's status is `NOT RUN` until the user runs it on the server and fills in
`Observed:`.

## What this validates
Every statement in `sources/crosscheck/cli_parity.md` and `sources/crosscheck/io_parity.md` that only a real install can
confirm (coverage table at the end): install per README, help texts, first-run weights download, weights identity,
argparse errors, input acceptance, the four outputs (grid, voxel size, origin, value ranges), `--keep_size` /
`--reverse_interpolation`, `--crop_check` behaviour without a terminal, GPU selection, and (optional) the Scipion plugin.

## Prerequisites (as claimed by the sources — none verified)
- **Linux + CUDA-enabled GPU + Python 3.11** (`README.md:113`); "Mainly tested on CentOS 7. For GPUs
  with limited memory, reduce the batch size using `-b`." (`README.md:115`); badges PyTorch 2.5.1,
  CUDA 12.4 (`README.md:8-9`).
- **Conda** — "Run these commands from the downloaded CryoCodex directory (Conda must be installed):"
  (`README.md:135`); `predict.sh` refuses to run without an executable `conda`
  (`predict.sh:57-63`).
- `git`, `curl` (`predict.sh:85`), outbound HTTPS to github.com, PyPI, `yanglab.qd.sdu.edu.cn`,
  `ftp.ebi.ac.uk`. PyPI's torch 2.5.1 CUDA wheels exist only for Linux x86_64 (`sources/source/install_environment.md:77-84`).
- No minimum driver, VRAM, RAM or disk is stated anywhere (`sources/web/hardware_and_platform_claims.md:36-38`); the paper
  capped GPU memory at 8 GB with batch 9 on an A800 (`sources/papers/2026_cheng_cryocodex.txt:796-802`). Downloads in this
  runbook: weights 470,938,660 B (`sources/web/evidence/weights_head_2026-11-24.txt:12`), torch wheel 906,474,467 B plus
  NVIDIA libraries (`sources/source/install_environment.md:82`, `sources/source/install_environment.md:149`), fixture 12,361,992 B
  (`sources/web/evidence/fixture_candidates_probe_2026-11-24.tsv:3`).
- Optional plugin section only: Scipion (`scipion-em>=3.8`, tested 3.8.3), `wget`
  (`sources/scipion_plugin/scipion-em-cryocodex/README.md:7-13`).

## Rules for the run
1. **Every output** (logs, header dumps, checksums, run directories) goes under `live/<host>_<YYYYMMDD>/` — `$LIVE`
   below. Afterwards copy `$LIVE` (without maps/weights) into this project's `sources/live/<host>_<YYYYMMDD>/` (R20).
2. Use only the public fixture (EMD-10387). Do not put private maps in this runbook's logs.
3. After each step write `Observed:` and a status: `PASS` (matches Expected) · `DIFFERS` (write what) · `FAIL` · `SKIPPED`.
4. Steps marked *optional* can be skipped; everything else is needed for the skill's command generation.
5. Run every block in **bash** (the blocks use `{ …; }` groups, the `time` keyword and `< <(…)` process substitution).
6. `CryoCodex` loads its checkpoint with `weights_only=False` (`predict.py:47`), i.e. full unpickling;
   R8 checks the downloaded file with `weights_only=True` **before** the first inference run.

---

### R0 — session variables (re-source after every reconnect)
```bash
export WORK="$HOME/cryocodex_live"     # change if $HOME is small; record free space in R1
export HOST="$(hostname -s)"; export DAY="$(date -u +%Y%m%d)"
export LIVE="$WORK/live/${HOST}_${DAY}"; export CC="$WORK/CryoCodex"
export FIX="$WORK/fixtures"; export RUNS="$LIVE/runs"
mkdir -p "$LIVE/tools" "$FIX" "$RUNS"
printf 'export WORK=%q HOST=%q DAY=%q LIVE=%q CC=%q FIX=%q RUNS=%q\n' \
  "$WORK" "$HOST" "$DAY" "$LIVE" "$CC" "$FIX" "$RUNS" > "$WORK/session.env"
echo "after a reconnect run:  source $WORK/session.env"
```
Expected: directories exist. — confirms nothing (setup). Status: NOT RUN

### R1 — host probe
```bash
{ date -u +%Y-%m-%dT%H:%M:%SZ; uname -a; head -5 /etc/os-release; ldd --version 2>&1 | head -1
  nproc; free -g; df -h "$WORK"
  nvidia-smi
  nvidia-smi --query-gpu=index,name,pci.bus_id,memory.total,memory.free,driver_version --format=csv
  echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES-<unset>}"
  conda --version; echo "CONDA_EXE=${CONDA_EXE-<unset>}"; command -v conda mamba micromamba
  git --version; curl --version | head -1
  command -v wget strace timeout script /usr/bin/time
} 2>&1 | tee "$LIVE/R01_host_probe.log"
```
Expected (from sources): Linux, an NVIDIA GPU visible to `nvidia-smi`, conda present (`README.md:113`,
`README.md:135`); x86_64 for the PyPI CUDA wheels (`sources/source/install_environment.md:77-84`); nothing
to compare driver/VRAM/RAM/disk against (`sources/web/hardware_and_platform_claims.md:36-38`) — record them. A conda found only
as a shell function needs `CONDA_EXE` exported (`predict.sh:58-59`). — confirms
`sources/source/install_environment.md:48-52`, `sources/web/hardware_and_platform_claims.md:11-15`. Status: NOT RUN

### R2 — clone, pin, file hashes
```bash
cd "$WORK" && git clone https://github.com/YangLab-SDU/CryoCodex.git 2>&1 | tee "$LIVE/R02_clone.log"
cd "$CC" && git checkout v1.0.0 2>&1 | tee -a "$LIVE/R02_clone.log"
{ git rev-parse HEAD 'v1.0.0^{commit}' origin/main; git cat-file -t v1.0.0; git ls-remote origin
  git log -1 --format='%H %cI %s'; git ls-tree HEAD predict.sh
  sha256sum predict.sh predict.py data_processor.py grid_utils.py crop_check.py VQUnet.py quant.py requirements.txt CryoCodex.ipynb
  ls -la predict.sh model_state_dicts/
} 2>&1 | tee "$LIVE/R02_pin.log"
```
The README clone step is `git clone https://github.com/YangLab-SDU/CryoCodex.git` + `cd CryoCodex`
(`README.md:128-131`); `git checkout v1.0.0` is added here to pin.
Expected (from sources): HEAD and tag = `a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17`, tag type `commit`
(`sources/crosscheck/evidence/pin_checks_2026-11-24.txt:3-9`); if `origin/main` ≠ that SHA, upstream moved after 2026-11-24 —
record it, keep the tag. Hashes equal `sources/source/evidence/file_sha256_v1.0.0.txt:2,6,15-17,19-22`. `predict.sh` mode
`100644` / `-rw-` (`sources/source/evidence/ls_tree_v1.0.0.txt:20`); `model_state_dicts/` holds only `.gitkeep`. — confirms
`sources/source/SNAPSHOT.md:13-24`, `sources/crosscheck/pin_consistency.md` P1–P12. Status: NOT RUN

### R3 — `chmod +x`, short help without conda
```bash
cd "$CC" && chmod +x predict.sh && git status --short | tee "$LIVE/R03_git_status.log"
{ env -u CONDA_EXE PATH=/usr/bin:/bin ./predict.sh -h; echo "exit=$?"; } 2>&1 | tee "$LIVE/R03_help_short.log"
diff <(sed -n '18,46p' predict.sh | sed 's/\$CRYOCODEX_PROG/predict.sh/') <(grep -v '^exit=' "$LIVE/R03_help_short.log") \
  && echo "HELP TEXT IDENTICAL TO HEREDOC" | tee -a "$LIVE/R03_help_short.log"
```
Expected (from sources): the heredoc of `predict.sh:17-47` with `$CRYOCODEX_PROG` = `predict.sh`
(`predict.sh:12`), `exit=0`, and it works with conda hidden from `PATH` because `-h` exits before the
conda lookup (`predict.sh:50-55`). `git status` will likely list `predict.sh` as modified (mode change;
git behaviour, UNVERIFIED). — confirms `sources/source/cli_reference_extracted.md:105-106`, cli_parity row `-h`. Status: NOT RUN

### R4 — environment exactly as the README says
```bash
cd "$CC"
conda env list | tee "$LIVE/R04_env_list_before.log"   # if cryocodex_env already exists: STOP — `conda create -y` would replace it;
                                                      # pick another name, `export CRYOCODEX_ENV=<name>`, and use that name in every
                                                      # later `conda run -n …` line of this runbook
{ conda create -y -n cryocodex_env python=3.11; echo "exit=$?"; } 2>&1 | tee "$LIVE/R04_conda_create.log"
{ conda run --no-capture-output -n cryocodex_env python -m pip install -r requirements.txt; echo "exit=$?"; } 2>&1 | tee "$LIVE/R04_pip_install.log"
df -h "$WORK" | tee -a "$LIVE/R04_pip_install.log"
```
Expected (from sources): the README commands (`README.md:137-141`) succeed; pip resolves `torch==2.5.1`
from PyPI with `nvidia-*-cu12` dependencies on Linux x86_64 (`sources/source/install_environment.md:77-84`); a `torchvision` is
pulled in by `timm` (`sources/source/install_environment.md:85-88`) — version UNVERIFIED, record it. — confirms
`sources/source/install_environment.md:151-153` (gap), contradictions C8. Status: NOT RUN

### R4b — `CRYOCODEX_ENV` / `CONDA_EXE` error paths (no download happens)
```bash
cd "$CC"
{ CRYOCODEX_ENV=cryocodex_does_not_exist ./predict.sh --version; echo "exit=$?"; } 2>&1 | tee "$LIVE/R04b_env_missing.log"
{ CONDA_EXE=/nonexistent/conda ./predict.sh --version; echo "exit=$?"; } 2>&1 | tee "$LIVE/R04b_conda_missing.log"
ls -la model_state_dicts/ | tee -a "$LIVE/R04b_conda_missing.log"
```
Expected (from sources): `ERROR: Cannot use 'cryocodex_does_not_exist'. Complete the README installation commands first.` and
`exit=1` (`predict.sh:8`, `predict.sh:69-73`); `ERROR: Conda was not found.
Install Conda and follow the README installation commands.` and `exit=1` (`predict.sh:59-63`);
`model_state_dicts/` still only `.gitkeep` (both checks precede the download, `predict.sh:69-77`).
The text of `conda run`'s own error for a missing env is UNVERIFIED. — confirms `sources/source/cli_reference_extracted.md:187-191`.
Status: NOT RUN

### R5 — package versions inside the env
```bash
cat > "$LIVE/tools/check_versions.py" <<'EOF'
import sys, importlib
print("python", sys.version.replace("\n", " "))
import torch
print("torch", torch.__version__, "| cuda_build", torch.version.cuda, "| cudnn", torch.backends.cudnn.version())
print("cuda_available", torch.cuda.is_available(), "| device_count", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    print("gpu", i, p.name, f"{p.total_memory / 2**30:.2f} GiB", f"cc {p.major}.{p.minor}")
for name in ["torchvision", "mrcfile", "numba", "einops", "timm", "numexpr", "numpy", "scipy", "tqdm", "PIL"]:
    try:
        print(name, getattr(importlib.import_module(name), "__version__", "?"))
    except Exception as exc:
        print(name, "IMPORT-ERROR", repr(exc))
EOF
conda run -n cryocodex_env python "$LIVE/tools/check_versions.py" 2>&1 | tee "$LIVE/R05_versions.log"
conda run -n cryocodex_env python -m pip freeze > "$LIVE/R05_pip_freeze.txt" 2>&1
conda run -n cryocodex_env python -m pip check 2>&1 | tee "$LIVE/R05_pip_check.log"
```
Expected (from sources): Python 3.11.x; `torch 2.5.1`, `mrcfile 1.5.4`, `numba 0.61.2`, `einops 0.8.1`, `timm 1.0.24`,
`numexpr 2.10.0`, `numpy 1.26.4`, `scipy 1.16.0`, `tqdm 4.67.1`, Pillow `>=10.1,<13`
(`requirements.txt:1-12`); `cuda_available True`; `cuda_build` `12.4` per the README badge
(`README.md:9`) — UNVERIFIED for the PyPI wheel. — confirms `sources/source/install_environment.md:92-105`,
contradictions C8. Status: NOT RUN

### R6 — `-h advanced` (needs the env, must not download)
```bash
cd "$CC"
{ ./predict.sh -h advanced; echo "exit=$?"; } 2>&1 | tee "$LIVE/R06_help_advanced.log"
ls -la model_state_dicts/ | tee -a "$LIVE/R06_help_advanced.log"
```
Expected (from sources): argparse help whose usage line names `predict.sh` (`predict.sh:11-13`,
`predict.py:156-158`), description `CryoCodex: cryo-EM map enhancement with local quality scores`
(`predict.py:159`), the options of `predict.py:161-184` incl. aliases `-a`, `-c`,
**no** `-m`/`--model_path` (`predict.py:185`); `exit=0`; `model_state_dicts/` unchanged because
`exec` happens before the checkpoint block (`predict.sh:65-67`). Paste the full text into the skill's
reference. — confirms `sources/source/cli_reference_extracted.md:107-109`, `sources/source/cli_reference_extracted.md:117-118`,
contradictions C3. Status: NOT RUN

### R7 — weights: server HEAD, then the first-run download triggered by `--version`
**Warning: the second command downloads ~471 MB**, because `--version` is not exempt from the download (contradictions C1).
If you prefer to fetch the file yourself, use R7-alt instead and expect no download message in the `--version` call.
```bash
cd "$CC"
curl -sI https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth | tee "$LIVE/R07_weights_head.txt"
{ time ./predict.sh --version; echo "exit=$?"; } 2>&1 | tee "$LIVE/R07_version_first_run.log"
ls -la model_state_dicts/ | tee -a "$LIVE/R07_version_first_run.log"
```
R7-alt (same flags as the launcher, `predict.sh:85-90`):
```bash
cd "$CC" && mkdir -p model_state_dicts && curl -fL --retry 2 -o model_state_dicts/CryoCodex.pth.part \
  https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth && mv model_state_dicts/CryoCodex.pth.part model_state_dicts/CryoCodex.pth
{ ./predict.sh --version; echo "exit=$?"; } 2>&1 | tee "$LIVE/R07_version_after_manual_download.log"
```
Expected (from sources): HEAD `HTTP/1.1 200 OK`, `Content-Length: 470938660`, `Last-Modified: Thu, 01 Oct 2026 02:13:30 GMT`,
`ETag: "1c11f424-65cbdf6493754"` (`sources/web/evidence/weights_head_2026-11-24.txt:6-12`) — any difference means the server
file changed since gathering: record and flag. `--version` (no checkpoint yet) prints
`Downloading the model weights to '<CC>/model_state_dicts/CryoCodex.pth' ...` (`predict.sh:84`), curl
progress, then `CryoCodex v1.0.0` (`predict.py:16`, `predict.py:161`),
`exit=0`, no `.part` left (`predict.sh:85-90`). — confirms
`sources/source/cli_reference_extracted.md:119-121`, `sources/source/models_data_dependencies.md:42-46`. Status: NOT RUN

### R8 — weights identity and safe-load check (before any inference)
```bash
cd "$CC"; W=model_state_dicts/CryoCodex.pth
{ stat -c '%s bytes  %y  %n' "$W"; sha256sum "$W"; md5sum "$W"
  [ "$(stat -c %s "$W")" = 470938660 ] && echo "SIZE MATCHES HEAD 2026-11-24" || echo "SIZE DIFFERS"; } | tee "$LIVE/R08_weights_identity.txt"
cat > "$LIVE/tools/check_ckpt.py" <<'EOF'
import sys, torch
c = torch.load(sys.argv[1], map_location="cpu", weights_only=True)
print("type", type(c).__name__, "| keys", sorted(c.keys()) if isinstance(c, dict) else None)
sd = c["model_state_dict"]
print("n_entries", len(sd), "| n_elements", sum(v.numel() for v in sd.values() if hasattr(v, "numel")))
EOF
{ conda run -n cryocodex_env python "$LIVE/tools/check_ckpt.py" "$W"; echo "exit=$?"; } 2>&1 | tee -a "$LIVE/R08_weights_identity.txt"
```
Expected (from sources): size 470938660 (`sources/web/evidence/weights_head_2026-11-24.txt:12`); there is **no published
checksum** to compare (`sources/web/license_and_terms.md:97-100`) — the SHA-256 printed here becomes the project's reference
value; the `weights_only=True` load returns a `dict` with key `model_state_dict` — the same check the Scipion installer requires
(`sources/scipion_plugin/scipion-em-cryocodex/cryocodex/scripts/install_runtime.py:83-86`). If this load fails, stop and decide
before running CryoCodex, which unpickles fully (`predict.py:47`). — confirms
`sources/source/models_data_dependencies.md:115-117`, `sources/web/license_and_terms.md:108-109`, contradictions C13.
Status: NOT RUN

### R9 — `--version` again, argparse and validation errors (no fixture, no GPU work)
```bash
cd "$CC"; E="$RUNS/r9_err"
{ ./predict.sh --version; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09a_version.log"
{ ./predict.sh -i /nonexistent.mrc -o "$E" --normal; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09b_bool_without_value.log"
{ ./predict.sh -i /nonexistent.mrc -o "$E" --normal yes; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09c_bool_bad_value.log"
{ ./predict.sh -i /nonexistent.mrc -o "$E" --normal True --keep_size True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09d_normal_keepsize.log"
{ ./predict.sh -i /nonexistent.mrc -o "$E" --normal True --crop_check True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09e_normal_cropcheck.log"
{ ./predict.sh -o "$E"; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09f_missing_i.log"
{ ./predict.sh -i /nonexistent.mrc -o "$E" --no_logo TRUE; echo "exit=$?"; } 2>&1 | tee "$LIVE/R09g_missing_file.log"
ls -la "$E" 2>&1 | tee -a "$LIVE/R09g_missing_file.log"
```
Expected (from sources):
- a: `CryoCodex v1.0.0`, `exit=0`, **no** download line (checkpoint now present, `predict.sh:77`).
- b: argparse "expected one argument" for `--normal`, `exit=2` (stdlib wording UNVERIFIED) — `type=parse_bool` takes one value
  (`predict.py:166`).
- c: `… error: argument --normal: expected True or False, got 'yes'`, `exit=2` (`predict.py:43`).
- d: `--keep_size is only available in fast mode, so it needs --normal False`, `exit=2` (`predict.py:191-192`).
- e: `--crop_check is only available in fast mode, so it needs --normal False`, `exit=2` (`predict.py:189-190`).
- f: argparse "the following arguments are required: -i/--in_map_path", `exit=2` (`predict.py:162`).
- g: `TRUE` accepted (case-insensitive, `predict.py:37-43`); then an mrcfile/OS error for the missing
  file (text UNVERIFIED), non-zero exit; `$E` was created before reading (`predict.py:80`).
— confirms `sources/source/cli_reference_extracted.md:288-294`, `sources/source/cli_reference_extracted.md:306-311`,
`sources/source/cli_reference_extracted.md:564`. Status: NOT RUN

### R10 — fixture EMD-10387 (public, 12.4 MB) and input header
```bash
cd "$FIX"
curl -fL -o emd_10387.map.gz https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-10387/map/emd_10387.map.gz
gzip -dc emd_10387.map.gz > emd_10387.map     # portable; CentOS 7's gzip has no -k
{ ls -l emd_10387.map.gz emd_10387.map; sha256sum emd_10387.map.gz emd_10387.map; } 2>&1 | tee "$LIVE/R10_fixture.log"
cat > "$LIVE/tools/mrc_dump.py" <<'EOF'
"""Header + value summary of MRC maps. Usage: python mrc_dump.py <map> [<map> ...]"""
import sys
import numpy as np
import mrcfile
for path in sys.argv[1:]:
    with mrcfile.open(path, mode="r", permissive=True) as m:
        h, d, vs = m.header, np.asarray(m.data, dtype=np.float64), m.voxel_size
        print(f"== {path}")
        print("mode", int(h.mode), "| nx ny nz", int(h.nx), int(h.ny), int(h.nz), "| data.shape(z,y,x)", d.shape)
        print("voxel_size_xyz", float(vs.x), float(vs.y), float(vs.z))
        print("cella_xyz", float(h.cella.x), float(h.cella.y), float(h.cella.z),
              "| cellb", float(h.cellb.alpha), float(h.cellb.beta), float(h.cellb.gamma))
        print("origin_xyz", float(h.origin.x), float(h.origin.y), float(h.origin.z),
              "| nxstart nystart nzstart", int(h.nxstart), int(h.nystart), int(h.nzstart))
        print("mapc mapr maps", int(h.mapc), int(h.mapr), int(h.maps))
        print("min max mean std", d.min(), d.max(), d.mean(), d.std())
        print("n_voxels", d.size, "| n_zero", int((d == 0).sum()), "| n_neg", int((d < 0).sum()), "| n_gt_1", int((d > 1).sum()))
        u = np.unique(d)
        print("n_unique", u.size, "| first_unique", u[:4].tolist())
        shell = np.ones(d.shape, bool); shell[2:-2, 2:-2, 2:-2] = False
        print("outer_2voxel_shell_max_abs", float(np.abs(d[shell]).max()))
EOF
conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" "$FIX/emd_10387.map" 2>&1 | tee "$LIVE/R10_input_header.txt"
```
Expected (from sources): `emd_10387.map.gz` = 12,361,992 B (`sources/web/evidence/fixture_candidates_probe_2026-11-24.tsv:3`);
EMDB metadata: 150×150×150, 1.043 Å, angles 90/90/90, start indices 0/0/0, axis order X/Y/Z, `size_kbytes` 13501,
min −0.059758537, max 0.14851397, mean 0.00022671334 (`sources/crosscheck/evidence/pin_checks_2026-11-24.txt:82-83`); derived
uncompressed size 13,501,024 B if the header has no extended header (`sources/crosscheck/evidence/pin_checks_2026-11-24.txt:84-85`,
UNVERIFIED). Header ORIGIN record: not in EMDB metadata — record it. Not in the training or validation lists
(`sources/crosscheck/evidence/pin_checks_2026-11-24.txt:78-81`). — confirms `sources/web/fixture_candidates.md:38`,
`sources/source/examples_fixtures.md:41`. Status: NOT RUN

### R11 — smoke run 1: defaults (fast mode, 1 Å output)
```bash
cd "$WORK"     # deliberately not the clone: the launcher resolves its own home (predict.sh:6-7)
OUT1="$RUNS/run1_default"
nvidia-smi --query-gpu=timestamp,index,memory.used,utilization.gpu --format=csv,noheader -l 1 > "$LIVE/R11_gpu_samples.csv" &
SAMPLER=$!
{ /usr/bin/time -v "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$OUT1"; echo "exit=$?"; } 2>&1 | tee "$LIVE/R11_run1.log"
kill $SAMPLER
ls -la "$OUT1" | tee "$LIVE/R11_run1_listing.txt"
conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" "$OUT1"/*.mrc 2>&1 | tee "$LIVE/R11_run1_headers.txt"
```
(Drop `/usr/bin/time -v` if R1 showed it is missing.)
Expected (from sources):
- Log: banner; `Improving … now, out_name:cryocodex` (`predict.py:81`); `# Rescale voxel size from [1.043
  1.043 1.043] to [1. 1. 1.]` (message at `grid_utils.py:187`; number formatting UNVERIFIED);
  `# Mask cropping complete`; `# Box cutting complete, start inference`; a tqdm bar; `saving` / `path: …` four times
  (`data_processor.py:56`, `data_processor.py:66`,
  `grid_utils.py:315`, `grid_utils.py:330`); `exit=0`.
- Listing: exactly `cryocodex.mrc`, `cryocodex_out_score.mrc`, `cryocodex_in_mask.mrc`, `cryocodex_in_score.mrc`
  (`README.md:331-338`; `predict.py:149-152`), no `round_*_check/`.
- Headers (all four identical geometry): float32 (MRC mode 2 expected; `grid_utils.py:318`); voxel 1.0
  (`README.md:329`); each axis between 48 and 156 (regridded size 156 derived,
  `sources/crosscheck/evidence/pin_checks_2026-11-24.txt:84-85`; padding to ≥ 48 `data_processor.py:59-61`;
  crop ±5 voxels `data_processor.py:41-44`); header origin 0, start indices = crop start
  (`grid_utils.py:320-329`, `data_processor.py:89`); `mapc mapr maps 1 2 3`.
- Values: `_in_mask` `n_unique 2`, values `[0.0, 1.0]` (`predict.py:105`, `predict.py:151`);
  both scores `min ≥ 0` (`predict.py:146-147`) and `max ≤ 1` (tanh + blending, derived from
  `VQUnet.py:320`, `VQUnet.py:328`); enhanced map has many exact zeros (soft mask,
  `predict.py:110-115`); `outer_2voxel_shell_max_abs 0.0` for all four (derived from
  `grid_utils.py:371-394`).
- Resources: record peak `memory.used` from the CSV and `Maximum resident set size` from `/usr/bin/time`. Reference only: paper
  17.87 s for this map on an A800 capped at 8 GB, batch 9 (`sources/papers/2026_cheng_cryocodex_supp_data.txt:1319`,
  `sources/papers/2026_cheng_cryocodex.txt:796-802`).
— confirms `sources/source/input_output_formats.md:214-228`, `sources/source/input_output_formats.md:231-233`,
`sources/source/input_output_formats.md:241-247`, `sources/source/examples_fixtures.md:44`,
`sources/source/cli_reference_extracted.md:543-553`; io_parity IO3–IO6, IO12. Status: NOT RUN

### R12 — run 2: `--reverse_interpolation True --keep_size True` + alignment check
```bash
OUT2="$RUNS/run2_revinterp_keepsize"
{ "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$OUT2" --reverse_interpolation True --keep_size True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R12_run2.log"
ls -la "$OUT2" | tee "$LIVE/R12_run2_listing.txt"
conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" "$OUT2"/*.mrc 2>&1 | tee "$LIVE/R12_run2_headers.txt"
cat > "$LIVE/tools/align_check.py" <<'EOF'
"""Mean input density inside vs outside the predicted mask (same grid only). Usage: python align_check.py <input> <in_mask>"""
import sys
import numpy as np
import mrcfile
with mrcfile.open(sys.argv[1], permissive=True) as a, mrcfile.open(sys.argv[2], permissive=True) as b:
    da, db = np.asarray(a.data, np.float64), np.asarray(b.data, np.float64)
    print("shapes", da.shape, db.shape, "| axes_in", int(a.header.mapc), int(a.header.mapr), int(a.header.maps))
    if da.shape != db.shape:
        sys.exit("SHAPES DIFFER - check not applicable")
    inside, outside = da[db > 0.5], da[db <= 0.5]
    print("mask_fraction", inside.size / da.size, "| mean_inside", inside.mean(), "| mean_outside", outside.mean())
EOF
conda run -n cryocodex_env python "$LIVE/tools/align_check.py" "$FIX/emd_10387.map" "$OUT2/cryocodex_in_mask.mrc" 2>&1 | tee "$LIVE/R12_alignment.txt"
```
Expected (from sources): `# Filling the cropped away background back in, output grid is (156, 156, 156)`
(`predict.py:120`; 156 derived); `# Interpolating the outputs from the 1.0 Angstrom grid back to the
native voxel size …` and `# Output grid is now (150, 150, 150) at 1.04… Angstrom` (`predict.py:132-133`,
`predict.py:144`; 150 derived from `grid_utils.py:79-81`,
`sources/crosscheck/evidence/pin_checks_2026-11-24.txt:84-85`). Headers: 150³, voxel 1.043, start indices 0 0 0 (origin 0 needs no
shift, `grid_utils.py:138`; derived); `_in_mask` still `{0, 1}` (`predict.py:143`);
scores ≥ 0, `n_gt_1` may be > 0 (no upper clamp after cubic resampling, `predict.py:136-147`) — record
the max; scores and mask 0 outside the crop region (`predict.py:117-124`). Alignment: `mean_inside` clearly
larger than `mean_outside` (derived expectation; a similar value means the outputs are shifted). — confirms
`sources/source/input_output_formats.md:236`, `sources/source/input_output_formats.md:248-252`,
`sources/source/cli_reference_extracted.md:525-532`; contradictions C4, C11; io_parity IO7–IO9. Status: NOT RUN

### R12b — *optional*: `--keep_size True` on a crop thinner than 48 voxels
```bash
cat > "$LIVE/tools/make_variants.py" <<'EOF'
"""Write test variants of a map: a 40^3 sub-box and a non-orthogonal copy. Usage: python make_variants.py <in.map> <outdir>"""
import os, sys
import numpy as np
import mrcfile
src, out = sys.argv[1], sys.argv[2]
with mrcfile.open(src, permissive=True) as m:
    d = np.asarray(m.data, dtype=np.float32); vs = m.voxel_size
vox = (float(vs.x), float(vs.y), float(vs.z))
c = np.unravel_index(np.argmax(d), d.shape)
lo = [max(0, min(int(ci) - 20, n - 40)) for ci, n in zip(c, d.shape)]
sub = np.ascontiguousarray(d[lo[0]:lo[0] + 40, lo[1]:lo[1] + 40, lo[2]:lo[2] + 40])
with mrcfile.new(os.path.join(out, "small40.map"), overwrite=True) as m:
    m.set_data(sub); m.voxel_size = vox
with mrcfile.new(os.path.join(out, "nonortho.map"), overwrite=True) as m:
    m.set_data(d); m.voxel_size = vox; m.header.cellb.alpha = 60.0
print("wrote small40.map", sub.shape, "start", lo, "and nonortho.map")
EOF
conda run -n cryocodex_env python "$LIVE/tools/make_variants.py" "$FIX/emd_10387.map" "$FIX" 2>&1 | tee "$LIVE/R12b_variants.log"
{ "$CC/predict.sh" -i "$FIX/small40.map" -o "$RUNS/r12b_small_keep" --keep_size True --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R12b_small_keepsize.log"
{ "$CC/predict.sh" -i "$FIX/small40.map" -o "$RUNS/r12b_small_default" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R12b_small_default.log"
conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" "$RUNS/r12b_small_default"/*.mrc 2>&1 | tee -a "$LIVE/R12b_small_default.log"
```
Expected (from sources, code reading only): the 40³ map regrids to 41³ (floor(1.043·39)+1); the crop is padded to 48 per axis
(`data_processor.py:59-61`), so `restore_full_size` pastes a 48-voxel grid into a 41-voxel canvas
(`predict.py:67-72`) → a NumPy broadcast error with `--keep_size True`; without it, 48³ outputs at 1 Å.
UNVERIFIED. — confirms `sources/source/input_output_formats.md:238-239`; io_parity IO10. Status: NOT RUN

### R13 — *optional*: normal mode
```bash
OUT3="$RUNS/run3_normal"
{ /usr/bin/time -v "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$OUT3" --normal True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R13_run3.log"
conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" "$OUT3"/*.mrc 2>&1 | tee "$LIVE/R13_run3_headers.txt"
```
Expected (from sources): `# Normal mode: keeping the whole map, no background cropping` (`data_processor.py:92`);
156³ at 1.0 Å with start indices 0 (derived); 10×10×10 = 1000 boxes in the tqdm total (derived,
`sources/crosscheck/evidence/pin_checks_2026-11-24.txt:85`); slower than R11 ("Slower than Fast mode",
`README.md:280-281`). — confirms `sources/source/cli_reference_extracted.md:464-466`,
`sources/source/input_output_formats.md:235`; io_parity IO11. Status: NOT RUN

R13b — *optional*: realistic size — the README's own example `7zki` = EMD-14763 (302.6 MB download, 432³ at 0.86 Å)
```bash
cd "$FIX" && curl -fL -o emd_14763.map.gz https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-14763/map/emd_14763.map.gz
gzip -dc emd_14763.map.gz > emd_14763.map && ls -l emd_14763.map.gz emd_14763.map | tee "$LIVE/R13b_fixture.log"
OUT4="$RUNS/run4_emd14763"
nvidia-smi --query-gpu=timestamp,index,memory.used,utilization.gpu --format=csv,noheader -l 1 > "$LIVE/R13b_gpu_samples.csv" &
SAMPLER=$!
{ /usr/bin/time -v "$CC/predict.sh" -i "$FIX/emd_14763.map" -o "$OUT4" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R13b_run4.log"
kill $SAMPLER
conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" "$OUT4"/*.mrc 2>&1 | tee "$LIVE/R13b_run4_headers.txt"
```
Expected (from sources): `emd_14763.map.gz` = 302,587,641 B (`sources/web/evidence/fixture_candidates_probe_2026-11-24.tsv:2`);
432³ at 0.86 Å, test-set map shown in the README images and the paper's Fig. 6 (`sources/web/fixture_candidates.md:14-30`);
paper run time 89.72 s on the capped A800 (`sources/web/fixture_candidates.md:29`). Gives a second point for peak GPU memory /
host RAM vs map size (G8). Delete the 0.3 GB map afterwards if disk is tight. Status: NOT RUN

### R14 — input-name acceptance (fails before any GPU work)
```bash
ln -sf "$FIX/emd_10387.map" "$FIX/emd_10387.ccp4"; ln -sf "$FIX/emd_10387.map" "$FIX/emd_10387.MRC"
{ "$CC/predict.sh" -i "$FIX/emd_10387.ccp4" -o "$RUNS/r14a" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R14a_ccp4.log"
{ "$CC/predict.sh" -i "$FIX/emd_10387.MRC"  -o "$RUNS/r14b" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R14b_upper_MRC.log"
{ "$CC/predict.sh" -i "$FIX/emd_10387.map.gz" -o "$RUNS/r14c" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R14c_gz.log"
```
Expected (from sources): each ends with `RuntimeError: File <path> is not a cryo-em density map file format.` and a non-zero exit
(`grid_utils.py:215`, `grid_utils.py:229-230`). — confirms
`sources/source/cli_reference_extracted.md:558`, `sources/source/input_output_formats.md:37-38`; io_parity IO1; contradictions C5, C6.
Status: NOT RUN

R14d — *optional*: non-orthogonal header (needs `nonortho.map` from R12b's `make_variants.py`):
```bash
{ "$CC/predict.sh" -i "$FIX/nonortho.map" -o "$RUNS/r14d" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R14d_nonortho.log"
ls -la "$RUNS/r14d" 2>&1 | tee -a "$LIVE/R14d_nonortho.log"
```
Expected (from sources): `# Input grid is not orthogonal. EXIT.` then bare `exit()` → `exit=0` and no maps
(`grid_utils.py:160-167`; exit code UNVERIFIED). — confirms `sources/source/cli_reference_extracted.md:559`,
`sources/source/cli_reference_extracted.md:576`; io_parity IO2. Status: NOT RUN

R14e — *optional*: does a user `-m` override the launcher's `-m`?
```bash
{ "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r14e" -m /nonexistent/CryoCodex.pth --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R14e_model_override.log"
```
Expected (from sources): argparse keeps the last occurrence, so the user path wins → a file-not-found error from `torch.load`
after preprocessing (`predict.sh:94`, `predict.py:87`); if the run instead
completes normally, the launcher's `-m` won. UNVERIFIED. — confirms `sources/source/cli_reference_extracted.md:181-183`,
`sources/source/cli_reference_extracted.md:575`. Status: NOT RUN

### R15 — `--crop_check` without a terminal (why the skill never uses it in batch)
```bash
# a) does `conda run --no-capture-output` forward stdin at all?
{ echo hello | conda run --no-capture-output -n cryocodex_env python -c 'import sys; print("stdin:", repr(sys.stdin.read()))'; echo "exit=$?"; } 2>&1 | tee "$LIVE/R15a_conda_run_stdin.log"
# b) closed stdin (EOF)
{ timeout 600 "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r15b_eof" --crop_check True --no_logo True < /dev/null; echo "exit=$?"; } 2>&1 | tee "$LIVE/R15b_crop_eof.log"
ls -laR "$RUNS/r15b_eof" 2>&1 | tee -a "$LIVE/R15b_crop_eof.log"
# c) stdin open but silent (typical batch wrapper) — killed after 180 s
{ timeout 180 "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r15c_hang" --crop_check True --no_logo True < <(sleep 240); echo "exit=$?"; } 2>&1 | tee "$LIVE/R15c_crop_open_stdin.log"
pgrep -af "$CC/predict.py" | tee -a "$LIVE/R15c_crop_open_stdin.log"   # if anything is listed: pkill -f "$CC/predict.py"
```
Expected (from sources): (a) prints `stdin: 'hello\n'` if conda forwards stdin — UNVERIFIED, conda-version dependent.
(b) after preprocessing, the prompt `[Enter] Continue without changes  |  [e] Edit bounds: ` then
`RuntimeError: Crop inspection needs terminal input.`, non-zero exit, no maps, and `round_1_check/projections_top_0p1pct.png`
+ `projections_top_1pct.png` left behind (deletion only happens on continue) (`crop_check.py:84-87`,
`crop_check.py:386`, `crop_check.py:402`, `crop_check.py:415-450`).
(c) if (a) showed forwarding: no output after the prompt until `timeout` kills it, `exit=124` → a batch job would hang forever;
if (a) showed no forwarding: same `RuntimeError` as (b) quickly. — confirms `sources/source/cli_reference_extracted.md:147-148`,
`sources/source/cli_reference_extracted.md:423-428`; contradictions C2. Status: NOT RUN

R15d — *optional*, interactive terminal only (records a typescript):
```bash
script -q -c "\"$CC/predict.sh\" -i \"$FIX/emd_10387.map\" -o \"$RUNS/r15d_interactive\" --crop_check True --no_logo True" "$LIVE/R15d_interactive.typescript"
# at the prompt: open the PNGs listed, then press Enter (or type c + Enter)
ls -la "$RUNS/r15d_interactive" | tee "$LIVE/R15d_listing.txt"
```
Expected (from sources): Enter or `c` → `No changes made. Continuing with the current crop bounds.` and
`=========== Crop check completed ===========`, `round_*_check/` deleted, inference continues, four maps written
(`crop_check.py:417-423`). — confirms `sources/source/cli_reference_extracted.md:416-418`,
`sources/source/cli_reference_extracted.md:423-424`. Status: NOT RUN

R15e — guard the skill should apply to any generated batch script (no run needed):
```bash
grep -nE -- '(--crop_check|[[:space:]]-c)[[:space:]=]+[Tt][Rr][Uu][Ee]' /path/to/generated_job.sh \
  && echo "REFUSE: interactive --crop_check in a batch script" || echo "OK: no --crop_check True"
```
Status: NOT RUN

### R16 — GPU selection
R16a — single-GPU hosts too: does `-g` (set after `import torch`) take effect?
```bash
{ "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r16a_nogpu" -g "" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R16a_no_visible_gpu.log"
```
Expected (from sources): `-g ""` sets `CUDA_VISIBLE_DEVICES=""` (`predict.py:194`) → no visible device →
preprocessing completes, then a torch error at `torch.load(..., map_location=cuda:0)` (`predict.py:47`,
`predict.py:82`, `predict.py:87`); error text UNVERIFIED — record it (it is the
"no usable GPU" message the skill should recognise). If the run **succeeds**, the late `CUDA_VISIBLE_DEVICES` assignment is not
honoured — a major finding. — confirms `sources/source/cli_reference_extracted.md:326-328`,
`sources/source/cli_reference_extracted.md:340-342`. Status: NOT RUN

R16b — *optional*, hosts with ≥ 2 GPUs: is a preset `CUDA_VISIBLE_DEVICES` overwritten?
```bash
nvidia-smi --query-compute-apps=timestamp,gpu_bus_id,pid,used_memory --format=csv,noheader -l 1 > "$LIVE/R16b_gpu_apps.csv" &
S=$!
{ CUDA_VISIBLE_DEVICES=1 "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r16b_cvd1_default_g" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R16b_cvd1_default_g.log"
{ "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r16b_g1" -g 1 --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R16b_g1.log"
kill $S; nvidia-smi --query-gpu=index,pci.bus_id --format=csv | tee -a "$LIVE/R16b_gpu_apps.csv"
```
Expected (from sources): first run lands on the GPU with index 0 (preset `1` replaced by the default `-g "0"`); second run on
index 1 (`predict.py:82`, `predict.py:182`, `predict.py:194`).
— confirms `sources/source/cli_reference_extracted.md:324-334`; contradictions C20. Status: NOT RUN

R16c — *optional*, Slurm sites: inside a 1-GPU allocation (`srun --gres=gpu:1 --pty bash`), record
`echo "$CUDA_VISIBLE_DEVICES"; nvidia-smi -L`, then run R11 once with `-g "$CUDA_VISIBLE_DEVICES"` and once without `-g`; note
which physical GPU each used (R16b sampler). Expected: not stated anywhere — UNVERIFIED; decides the skill's Slurm template.
Status: NOT RUN

### R17 — *optional*: network egress during inference (weights present)
```bash
command -v strace && { strace -f -e trace=connect -o "$LIVE/R17_strace_connect.txt" \
  "$CC/predict.sh" -i "$FIX/emd_10387.map" -o "$RUNS/r17_egress" --no_logo True; echo "exit=$?"; } 2>&1 | tee "$LIVE/R17_egress.log"
grep -E 'AF_INET6?' "$LIVE/R17_strace_connect.txt" | tee -a "$LIVE/R17_egress.log"
```
Expected (from sources): no `AF_INET`/`AF_INET6` connections from the Python process — the CLI makes no network call once the
weights exist (`sources/source/external_calls_and_egress.md:10-13`); third-party libraries UNVERIFIED. Status: NOT RUN

### R18 — *optional*: author result for the same map (6.5 MB, regression reference)
```bash
cd "$FIX" && curl -fLO https://yanglab.qd.sdu.edu.cn/CryoCodex/benchmark/results/emd_10387.zip
{ ls -l emd_10387.zip; sha256sum emd_10387.zip; unzip -l emd_10387.zip; } 2>&1 | tee "$LIVE/R18_author_zip.log"
mkdir -p "$FIX/author_10387" && unzip -o -d "$FIX/author_10387" emd_10387.zip
find "$FIX/author_10387" -name '*.mrc' -o -name '*.map' | xargs conda run -n cryocodex_env python "$LIVE/tools/mrc_dump.py" 2>&1 | tee -a "$LIVE/R18_author_zip.log"
```
Expected (from sources): size 6,514,577 B (`sources/web/evidence/fixture_candidates_probe_2026-11-24.tsv:3`); contents UNVERIFIED
(`sources/web/fixture_candidates.md:63-64`). Compare grid/voxel/origin and value ranges with R11; whether the paper's results were
made with the released checkpoint is unknown (`sources/web/fixture_candidates.md:68`). Status: NOT RUN

### R19 — *optional*: Scipion plugin (only if the user wants the Scipion route)
```bash
scipion3 python -m pip install scipion-em-cryocodex==0.3.2 2>&1 | tee "$LIVE/R19_pip.log"
# To avoid a second 471 MB download, first add to scipion.conf [PLUGINS]:  CRYOCODEX_MODEL = <CC>/model_state_dicts/CryoCodex.pth
scipion3 installb cryocodex-1.0.0 2>&1 | tee "$LIVE/R19_installb.log"
find "$HOME" -maxdepth 6 -name cryocodex-installed.json 2>/dev/null | head -3 | tee "$LIVE/R19_marker_path.txt"   # site-specific; if empty, search Scipion's software/em dir (avoid find / on cluster filesystems)
cat "$(head -1 "$LIVE/R19_marker_path.txt")" | tee "$LIVE/R19_marker.json"
scipion3 inspect cryocodex 2>&1 | tee "$LIVE/R19_inspect.log"
scipion3 test cryocodex.tests.test_protocol.TestCryoCodexIntegration 2>&1 | tee "$LIVE/R19_test_integration.log"
CRYOCODEX_TEST_GPU=1 CRYOCODEX_TEST_MAP="$FIX/emd_10387.map" scipion3 test cryocodex.tests.test_protocol.TestCryoCodexGPU 2>&1 | tee "$LIVE/R19_test_gpu.log"
```
Commands from `sources/scipion_plugin/scipion-em-cryocodex/README.md:20-21`, `sources/scipion_plugin/scipion-em-cryocodex/README.md:64-67`,
`sources/scipion_plugin/scipion-em-cryocodex/README.md:72`; test gates from `sources/scipion_plugin/scipion-em-cryocodex/cryocodex/tests/test_protocol.py:72-89`; the GPU test runs normal mode,
batch 1, stride 24, `reverseInterpolation=True` (`sources/scipion_plugin/scipion-em-cryocodex/cryocodex/tests/test_protocol.py:92-95`).
Expected (from sources): installer creates a private `conda-env` with Python 3.11, installs `requirements.txt`, copies or downloads
the model, runs `predict.py --version` and the `weights_only=True` check, writes `cryocodex-installed.json` with `source_commit`,
`source_tag`, `python`, `model_sha256` (`sources/scipion_plugin/scipion-em-cryocodex/cryocodex/scripts/install_runtime.py:59-95`);
`model_sha256` must equal the R8 SHA-256; the marker is recorded, not verified (`sources/scipion_plugin/plugin_reference.md:39`).
GUI crop review and output-origin display need a manual check in the Scipion GUI (`sources/scipion_plugin/verification.md:32-35`).
Status: NOT RUN

### R20 — package the evidence and copy it back
On the server:
```bash
cd "$WORK/live"
tar --exclude='*.mrc' --exclude='*.map' --exclude='*.pth' --exclude='*.part' --exclude='*.gz' --exclude='*.zip' \
    -czf "${HOST}_${DAY}_evidence.tgz" "${HOST}_${DAY}" && ls -l "${HOST}_${DAY}_evidence.tgz"
```
On the maintainer's machine (`<PROJECT>` = the evidence-pack project folder):
```bash
scp '<server>:~/cryocodex_live/live/<host>_<YYYYMMDD>_evidence.tgz' '<PROJECT>/sources/live/'
cd '<PROJECT>/sources/live' && tar -xzf '<host>_<YYYYMMDD>_evidence.tgz'   # → sources/live/<host>_<YYYYMMDD>/
```
Then write `sources/live/<host>_<YYYYMMDD>/RESULTS.md`: one line per step `R<n>: PASS|DIFFERS|FAIL|SKIPPED — note`, plus the
R8 SHA-256 and the R5 version list. Status: NOT RUN

---

## Coverage: claims that only a live run can confirm

| Claim (where stated) | Step |
|---|---|
| `-h` prints the heredoc without conda (cli_parity `-h`) | R3 |
| `-h advanced` text; needs env; no download; `-m` hidden (cli_parity `-h advanced`; C3) | R6 |
| `--version` triggers the first-run download; prints `CryoCodex v1.0.0` (cli_parity `--version`; C1) | R7, R9a |
| README install works; torch CUDA build and torchvision version (C8) | R4, R5 |
| `CRYOCODEX_ENV` / `CONDA_EXE` are read; their error texts (cli_parity env rows) | R4b, R1 |
| Weights size, SHA-256, `weights_only=True` loadability (C13) | R7, R8 |
| Value-less / invalid booleans and fast-mode-only checks fail with exit 2 (cli_parity booleans; Never-emit list) | R9b–R9e |
| Required `-i`; case-insensitive booleans; missing-file error text | R9f, R9g |
| `-i` suffix rule (`.ccp4`, `.MRC`, `.gz` rejected) (cli_parity `-i`; io_parity IO1; C5, C6) | R14a–c |
| Non-orthogonal exit status (io_parity IO2) | R14d |
| User `-m` vs launcher `-m` (cli_parity `-m`) | R14e |
| Default outputs: names, float32, 1 Å, crop box, start-index origin, value ranges, zero shell (io_parity IO3–IO6) | R11 |
| Peak GPU memory at `-b 9`, host RAM (cli_parity `-b`; io_parity IO12) | R11 |
| `--keep_size` + `--reverse_interpolation` box/voxel/origin; scores > 1; mask binary; alignment (C4, C11; IO7–IO9) | R12 |
| `--keep_size` with a crop < 48 voxels (IO10) | R12b |
| Normal mode box and message (IO11) | R13 |
| Resource scaling on a realistic map (README example `7zki`) | R13b |
| `conda run` stdin forwarding; `--crop_check` EOF error / hang; PNGs left behind (cli_parity `--crop_check`; C2) | R15a–c |
| Interactive crop check continue path, folders deleted | R15d |
| `-g` takes effect after `import torch`; no-GPU error text (cli_parity `-g`, `CUDA_VISIBLE_DEVICES`) | R16a |
| Preset `CUDA_VISIBLE_DEVICES` overwritten; `-g 1` selects GPU 1 (C20) | R16b, R16c |
| No network egress with weights present | R17 |
| Agreement with the authors' published result for EMD-10387 | R18 |
| Scipion plugin install/test; marker SHA = R8 SHA | R19 |
| Stride > 44 leaves uncovered voxels (C12) | not scheduled (optional: rerun R11 with `-s 46` and look for zero planes) |
| Plugin origin rule vs upstream when ORIGIN and start are both non-zero (C10) | not scheduled (needs a crafted map) |

## Gaps / unknowns
- Not covered by any step: C10 (crafted map needed), C12 (optional `-s 46` rerun), the Colab notebook (out of scope: map egress
  to Google; `sources/source/external_calls_and_egress.md:44-46`), macOS/CPU behaviour (no GPU server can show it).
- Several expected values are **derived** (156/150 voxel boxes, 1000 boxes, zero outer shell, alignment means); a mismatch is a
  finding about the derivation as much as about CryoCodex.
- Exact message formatting (NumPy array printing, tqdm, argparse wording, torch/mrcfile errors) is unknown until R6–R16 run.
- The location of Scipion's software directory and whether `CRYOCODEX_MODEL` in `scipion.conf` is honoured by `installb`
  (`sources/scipion_plugin/scipion-em-cryocodex/cryocodex/__init__.py:77-78`) are site-specific / UNVERIFIED.
- Disk needed for the conda env + CUDA wheels is not stated anywhere; R1/R4 record free space before/after.
