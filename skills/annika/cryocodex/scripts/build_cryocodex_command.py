#!/usr/bin/env python3
"""build_cryocodex_command.py -- write a correct CryoCodex v1.0.0 `predict.sh` command (and optionally a Slurm job).

    python3 build_cryocodex_command.py -i MAP -o OUT_DIR [--home /abs/CryoCodex]
        [--normal True|False] [--keep_size True|False] [--reverse_interpolation True|False]
        [--crop_check True|False --interactive] [--no_logo True|False]
        [-n NAME] [-s STRIDE] [-b BATCH] [-g GPU_INDEX | --slurm]
        [--env CONDA_ENV_NAME] [--conda-exe /abs/conda] [--launcher /abs/site_launcher.sh] [--no-check] [--allow-existing-out]
        [--sbatch JOBFILE [--account A] [--partition P] [--cpus 8] [--mem 32G] [--time 01:00:00]
                          [--gres gpu:1] [--job-name NAME] [--site-env "source /abs/etc/profile.d/conda.sh"]]

CryoCodex options are given exactly as in the README (`--keep_size True`); the builder emits only spellings from
references/03 section 3 and REFUSES (exit 2): value-less booleans or values other than True/False; --normal True with
--keep_size True or --crop_check True; --crop_check True without --interactive (or with --slurm/--sbatch); stride
outside 1-44; batch < 1; a -g that is not one GPU index; an input name not ending in lower-case mrc/map; a header that
fails the gates (non-orthogonal cell, no MAP id, truncated file); --keep_size True when the 1 A box has an axis < 48;
code-only aliases (-a, -c, --in_map_path, ...), the hidden -m and options that do not exist. --slurm emits
-g "${CUDA_VISIBLE_DEVICES:-0}" (predict.py:82,194; verified 2026-11-24 on a Slurm node). Prints the command labelled
"template -- not run"; with --sbatch also fills templates/slurm_cryocodex.sbatch.template. stdlib only; runs nothing.
"""
import argparse
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mrcheader as mh  # noqa: E402

BARE = object()
BOOLS = ("--normal", "--reverse_interpolation", "--keep_size", "--crop_check", "--no_logo")
FORBIDDEN = {
    "-a": "code-only alias; write --reverse_interpolation True|False",
    "-c": "code-only alias; write --crop_check True|False",
    "--in_map_path": "use -i", "--out_dir": "use -o", "--out_name": "use -n", "--stride": "use -s",
    "--batch_size": "use -b", "--gpu": "use -g",
    "-m": "hidden option; predict.sh already passes -m <clone>/model_state_dicts/CryoCodex.pth",
    "--model_path": "hidden option; predict.sh already passes -m",
    "--cpu": "no CPU path (compute is cuda:0)", "--device": "no such option", "--threads": "no such option",
    "--fp16": "no such option", "--half": "no such option", "--half1": "single-map input only (process half maps one at a time)",
    "--half2": "single-map input only", "--half_map": "single-map input only", "--mask": "no mask input",
    "--resolution": "no resolution input", "--apix": "voxel size comes from the header", "--voxel_size": "voxel size comes from the header",
    "--mode": "use --normal True|False", "--fast": "fast mode is the default (--normal False)",
}
PLACEHOLDER_HOME = "/abs/path/to/CryoCodex"


def die(msg):
    print("REFUSED: " + msg, file=sys.stderr)
    sys.exit(2)


def prescan(argv):
    for i, t in enumerate(argv):
        key = t.split("=", 1)[0]
        if key in FORBIDDEN:
            die(f"{key}: {FORBIDDEN[key]} (references/03 section 4)")
        if "=" in t and key in BOOLS:
            die(f"{t}: write '{key} {t.split('=', 1)[1]}' (README form, a space, not '=')")


def boolval(name, v):
    if v is None:
        return None
    if v is BARE:
        die(f"bare {name}: CryoCodex needs an explicit value, '{name} True' or '{name} False' (parse_bool, predict.py:37-43)")
    if v.strip().lower() == "true":
        return "True"
    if v.strip().lower() == "false":
        return "False"
    die(f"{name} {v!r}: only True or False are accepted (parse_bool rejects 1/0/yes/no; predict.py:37-43)")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    prescan(argv)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("-i", dest="map", required=True, help="input map (uncompressed; name ends in lower-case mrc/map)")
    ap.add_argument("-o", dest="out", required=True, help="output directory (use a NEW one per run)")
    ap.add_argument("--home", help="absolute path of the CryoCodex clone (default: a placeholder; the command is then a template)")
    for b in BOOLS:
        ap.add_argument(b, nargs="?", const=BARE, default=None, metavar="True|False")
    ap.add_argument("--interactive", action="store_true", help="the user will type at a terminal (required for --crop_check True)")
    ap.add_argument("-n", dest="name", help="output base name (default cryocodex)")
    ap.add_argument("-s", dest="stride", type=int, help="sliding-window stride, 1-44 (default 12)")
    ap.add_argument("-b", dest="batch", type=int, help="windows per GPU batch, >= 1 (default 9)")
    ap.add_argument("-g", dest="gpu", help="ONE GPU index as listed by nvidia-smi (default 0)")
    ap.add_argument("--slurm", action="store_true", help='use the scheduler GPU: -g "${CUDA_VISIBLE_DEVICES:-0}"')
    ap.add_argument("--env", help="conda env name if not cryocodex_env (prefixes CRYOCODEX_ENV=...)")
    ap.add_argument("--conda-exe", help="absolute path of conda if it is not on PATH as an executable (prefixes CONDA_EXE=...)")
    ap.add_argument("--launcher", help="site route: a wrapper that runs predict.py with the same options (used instead of <home>/predict.sh)")
    ap.add_argument("--no-check", action="store_true", help="skip reading the input header")
    ap.add_argument("--allow-existing-out", action="store_true", help="allow an output dir that already holds outputs with this -n (they are overwritten)")
    ap.add_argument("--sbatch", metavar="JOBFILE", help="also write a filled copy of templates/slurm_cryocodex.sbatch.template")
    ap.add_argument("--account"); ap.add_argument("--partition"); ap.add_argument("--cpus"); ap.add_argument("--mem")
    ap.add_argument("--time"); ap.add_argument("--job-name"); ap.add_argument("--site-env", help="command that makes an executable conda visible in the job")
    ap.add_argument("--gres", help="request the GPU as '#SBATCH --gres=<value>' (e.g. gpu:1) instead of '--gpus=1'; must ask for ONE GPU")
    a = ap.parse_args(argv)

    notes = []
    normal = boolval("--normal", a.normal)
    keep = boolval("--keep_size", a.keep_size)
    rev = boolval("--reverse_interpolation", a.reverse_interpolation)
    crop = boolval("--crop_check", a.crop_check)
    nologo = boolval("--no_logo", a.no_logo)
    batch_mode = a.slurm or bool(a.sbatch)

    if normal == "True" and keep == "True":
        die("--keep_size True is fast-mode only; with --normal True predict.py stops with parser.error (predict.py:191-192)")
    if normal == "True" and crop == "True":
        die("--crop_check True is fast-mode only; with --normal True predict.py stops with parser.error (predict.py:189-190)")
    if crop == "True" and batch_mode:
        die("--crop_check True waits for terminal input (crop_check.py:415-450); never in Slurm/batch jobs")
    if crop == "True" and not a.interactive:
        die("--crop_check True blocks on terminal input with no timeout; add --interactive only if the user will type at a terminal")
    if a.stride is not None and not (1 <= a.stride <= mh.MAX_SAFE_STRIDE):
        die(f"-s {a.stride}: keep the stride within 1-44 (0 crashes; > 44 leaves voxels no window covers, grid_utils.py:383-393)")
    if a.batch is not None and a.batch < 1:
        die(f"-b {a.batch}: batch must be >= 1 (0 divides by zero in get_batch_slices)")
    if a.batch is not None and a.batch > mh.DEFAULT_BATCH:
        notes.append(f"WARN: -b {a.batch} > 9: the only memory data point is batch 9 within 8 GB on an A800 (preprint); larger needs more VRAM (not measured)")
    if a.gpu is not None and batch_mode:
        die('-g with --slurm/--sbatch: the job passes the scheduler GPU itself (-g "${CUDA_VISIBLE_DEVICES:-0}")')
    if a.gpu is not None and not re.fullmatch(r"\d+", a.gpu):
        die(f"-g {a.gpu!r}: exactly one GPU index (CryoCodex computes on cuda:0 only; no multi-GPU or CPU path)")
    if a.name is not None and (not a.name or "/" in a.name or "\\" in a.name):
        die(f"-n {a.name!r}: a plain base name without slashes")
    name = a.name or "cryocodex"

    ok, why = mh.name_gate(a.map)
    if not ok:
        die(f"-i {a.map}: {why}")
    for what, p in (("-i", a.map), ("-o", a.out)):
        if not os.path.isabs(p):
            if batch_mode:
                die(f"{what} {p!r} must be an absolute path in a batch job")
            notes.append(f"WARN: {what} {p!r} is relative: it resolves against the directory you start predict.sh from")

    if not a.no_check:
        if os.path.exists(a.map):
            try:
                h = mh.read_header(a.map)
            except (OSError, mh.HeaderError) as e:
                die(f"-i {a.map}: cannot read the MRC header ({e})")
            g = mh.geometry(h, a.stride or mh.DEFAULT_STRIDE, a.batch or mh.DEFAULT_BATCH)
            if not g["orthogonal"]:
                die(f"-i {a.map}: cell angles {h['cellb']} are not 90/90/90 -> '# Input grid is not orthogonal. EXIT.' (no outputs)")
            if not g["mapid_ok"]:
                die(f"-i {a.map}: no 'MAP ' id in the header; mrcfile refuses it")
            if not g["axis_ok"]:
                die(f"-i {a.map}: axis order ({h['mapc']},{h['mapr']},{h['maps']}) is not a permutation of 1,2,3")
            if g["size_ok"] is False:
                die(f"-i {a.map}: file shorter than the header implies (truncated download?)")
            if not g["voxel_ok"]:
                die(f"-i {a.map}: voxel size 0 in the header")
            if g["positive_density_header"] is False:
                die(f"-i {a.map}: header DMAX <= 0 (no positive density): the percentile normalisation fails")
            if keep == "True" and g["small_axis"]:
                die(f"--keep_size True with a 1 A box {g['dims_1A']} that has an axis < 48: the padded 48-voxel crop does not fit "
                    "the canvas (predict.py:67-72, data_processor.py:59-61; verified: ValueError, exit 1). Drop --keep_size.")
            notes.append(f"input: {g['dims_xyz']} @ {tuple(round(v, 4) for v in h['voxel'])} A -> 1 A box {g['dims_1A']}; "
                         f"normal mode {g['windows_normal']} windows (~{mh.fmt_bytes(g['ram_normal_bytes'])} host RAM, rough); "
                         "fast mode crops first (less)")
            if keep == "True":
                same = g["keep_size_box"] == g["dims_xyz"]
                if rev == "True":
                    notes.append(f"expected box: {g['keep_size_reverse_box']} at the input voxel size (derived)")
                else:
                    notes.append(f"expected box: {g['keep_size_box']} at 1.0 A (derived)"
                                 + ("" if same else " -- NOT the input box; add --reverse_interpolation True to return to the input voxel size"))
            if g["both_origin_fields"]:
                notes.append("WARN: header ORIGIN and NSTART are both non-zero; CryoCodex adds both (other programs may not)")
        else:
            notes.append(f"NOTE: {a.map} not found here; header gates skipped (run scripts/inspect_map.py on the host that has it)")

    if os.path.isdir(a.out):
        existing = [s for s in mh.OUTPUT_SUFFIXES if os.path.exists(os.path.join(a.out, f"{name}{s}.mrc"))]
        if existing and not a.allow_existing_out:
            die(f"-o {a.out} already holds outputs named {name}*: CryoCodex overwrites them silently; use a NEW directory")
        if os.listdir(a.out):
            notes.append(f"WARN: -o {a.out} is not empty")

    home = a.home or PLACEHOLDER_HOME
    template = a.home is None
    if a.home:
        if not os.path.isabs(a.home):
            die(f"--home {a.home!r} must be absolute")
        if os.path.isdir(a.home):
            if not os.path.isfile(os.path.join(a.home, "predict.py")):
                notes.append(f"WARN: {a.home}/predict.py not found: is this the CryoCodex clone?")
            elif not a.launcher and not os.access(os.path.join(a.home, "predict.sh"), os.X_OK):
                notes.append(f"WARN: {a.home}/predict.sh is not executable: run 'chmod +x predict.sh' in the clone (README step)")
            ck = os.path.join(a.home, "model_state_dicts", "CryoCodex.pth")
            if not (os.path.isfile(ck) and os.path.getsize(ck) > 0):
                notes.append("WARN: no weights at model_state_dicts/CryoCodex.pth: the first run DOWNLOADS 471 MB from "
                             "yanglab.qd.sdu.edu.cn (no checksum). Ask the user first, or place the file (references/02 section 4).")
            elif os.path.getsize(ck) != mh.WEIGHTS_BYTES:
                notes.append(f"WARN: weights are {os.path.getsize(ck)} B, not {mh.WEIGHTS_BYTES} B (HEAD 2026-11-24): partial or changed file")
        else:
            notes.append(f"NOTE: --home {a.home} not found here (fine if the command is for another host)")

    if a.launcher:
        if not os.path.isabs(a.launcher):
            die(f"--launcher {a.launcher!r} must be absolute")
        if a.env or a.conda_exe:
            die("--env/--conda-exe apply to predict.sh (conda run); a site launcher chooses its own env")
        if os.path.exists(a.launcher) and not os.access(a.launcher, os.X_OK):
            notes.append(f"WARN: {a.launcher} is not executable")
    env_prefix = []
    if a.conda_exe:
        env_prefix.append(f"CONDA_EXE={shlex.quote(a.conda_exe)}")
    if a.env:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.env):
            die(f"--env {a.env!r}: not a plain conda env name")
        env_prefix.append(f"CRYOCODEX_ENV={a.env}")

    opts = []          # options beyond -i/-o/-n/-g (shared with the sbatch OPTS array)
    if normal is not None:
        opts += ["--normal", normal]
    if rev is not None:
        opts += ["--reverse_interpolation", rev]
    if keep is not None:
        opts += ["--keep_size", keep]
    if crop is not None:
        opts += ["--crop_check", crop]
    if a.stride is not None:
        opts += ["-s", str(a.stride)]
    if a.batch is not None:
        opts += ["-b", str(a.batch)]

    runner = a.launcher or os.path.join(home, "predict.sh")
    cmd = env_prefix + [shlex.quote(runner), "-i", shlex.quote(a.map), "-o", shlex.quote(a.out)]
    if a.name is not None:
        cmd += ["-n", shlex.quote(name)]
    cmd += opts
    if a.slurm:
        cmd += ["-g", '"${CUDA_VISIBLE_DEVICES:-0}"']
    elif a.gpu is not None:
        cmd += ["-g", a.gpu]
    if nologo is not None:
        cmd += ["--no_logo", nologo]
    line = " ".join(cmd)

    print("# template -- not run here. CryoCodex v1.0.0 (a35e73a); options verified on the 2026-11-24 validation host;"
          " run it only on a host whose site config says VALIDATED (or after the runbook)."
          + (" Replace /abs/path/to/CryoCodex (or pass --home)." if template else ""))
    print(line)
    mode = "normal mode (whole map)" if normal == "True" else "fast mode (background cropped)"
    grid = "input voxel size" if rev == "True" else "1.0 A grid"
    print(f"# {mode}; outputs on the {grid}: {name}.mrc, {name}_out_score.mrc, {name}_in_mask.mrc, {name}_in_score.mrc")
    check = ["python3", os.path.join("scripts", "check_outputs.py"), shlex.quote(a.out), "-n", shlex.quote(name), "--input", shlex.quote(a.map)]
    if normal == "True":
        check.append("--normal")
    if keep == "True":
        check.append("--keep-size")
    if rev == "True":
        check.append("--reverse-interpolation")
    print("# after the run: " + " ".join(check))
    for n in notes:
        print("# " + n)

    if a.sbatch:
        tpl = os.path.join(SKILL_DIR, "templates", "slurm_cryocodex.sbatch.template")
        if os.path.exists(a.sbatch):
            die(f"--sbatch {a.sbatch} exists; choose a new job file name")
        if not a.home:
            die("--sbatch needs --home (the clone path on the cluster)")
        txt = open(tpl, encoding="utf-8").read()
        job = a.job_name or re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.splitext(os.path.basename(a.map))[0])[:40]
        subs = {"<CRYOCODEX_HOME>": a.home, "<ABS_INPUT_MAP>": a.map, "<SKILL_DIR>": SKILL_DIR, "<JOB_NAME>": job}
        for key, val in (("<ACCOUNT>", a.account), ("<GPU_PARTITION>", a.partition), ("<CPUS>", a.cpus), ("<MEM>", a.mem), ("<TIME>", a.time)):
            if val:
                subs[key] = val
        for k, v in subs.items():
            txt = txt.replace(k, v)
        # optional directives the user did not give: disable them (##SBATCH is ignored by sbatch) instead of
        # leaving a placeholder; many sites need no account, and --mem is only a node filter on some clusters
        for key, flag in (("<ACCOUNT>", "--account"), ("<MEM>", "--mem")):
            txt = re.sub(r"^#SBATCH " + re.escape(flag) + "=" + re.escape(key) + r"\s*$",
                         f"##SBATCH {flag}=  (not set; pass {flag} to the builder if your site needs it)",
                         txt, flags=re.M)
        if a.gres:
            if not re.fullmatch(r"gpu(:[A-Za-z0-9_.-]+)?:1", a.gres):
                die(f"--gres {a.gres!r}: request exactly one GPU, e.g. gpu:1 or gpu:a100:1")
            txt = re.sub(r"^#SBATCH --gpus=1\s*$", f"#SBATCH --gres={a.gres}", txt, count=1, flags=re.M)
        txt = re.sub(r'^OUT=".*$', f'OUT={shlex.quote(a.out)}   # NEW directory for this run', txt, count=1, flags=re.M)
        txt = re.sub(r'^OUT_NAME=".*$', f'OUT_NAME={shlex.quote(name)}', txt, count=1, flags=re.M)
        if a.site_env:
            txt = re.sub(r'^SITE_ENV_CMD="".*$', "SITE_ENV_CMD=" + shlex.quote(a.site_env), txt, count=1, flags=re.M)
        if a.launcher:
            txt = re.sub(r'^RUNNER=".*$', "RUNNER=" + shlex.quote(a.launcher) + "   # site launcher (same options as predict.sh)",
                         txt, count=1, flags=re.M)
        if a.env:
            txt = re.sub(r'^export CRYOCODEX_ENV=".*$', f'export CRYOCODEX_ENV="{a.env}"', txt, count=1, flags=re.M)
        txt = re.sub(r"^OPTS=\(\).*$", "OPTS=(" + " ".join(shlex.quote(o) for o in opts) + ")", txt, count=1, flags=re.M)
        txt = re.sub(r"^CHECK_OPTS=\(\).*$", "CHECK_OPTS=(" + " ".join(check[7:]) + ")", txt, count=1, flags=re.M)
        if a.conda_exe:
            txt = txt.replace('[ -n "$SITE_ENV_CMD" ] && eval "$SITE_ENV_CMD"',
                              '[ -n "$SITE_ENV_CMD" ] && eval "$SITE_ENV_CMD"\nexport CONDA_EXE=' + shlex.quote(a.conda_exe))
        with open(a.sbatch, "w", encoding="utf-8") as fh:
            fh.write(txt)
        left = sorted(set(re.findall(r"<[A-Z_]+>", txt)))
        print(f"# wrote {a.sbatch} (bash -n it, show templates/run_plan.md, ask, then sbatch)"
              + (f"; still to fill: {', '.join(left)}" if left else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
