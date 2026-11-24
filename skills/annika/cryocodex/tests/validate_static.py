#!/usr/bin/env python3
"""validate_static.py -- offline checks for the cryocodex skill (no GPU, no network, no CryoCodex install).

    python3 tests/validate_static.py

1. SKILL.md frontmatter: name cryocodex, quoted description, no angle brackets, <= 1024 characters.
2. Every predict.sh command in SKILL.md, references/*.md (except the runbook, which tests error paths on purpose) and
   templates/* uses only allowlisted flags (references/03 section 3), True/False booleans, no fast-mode-only option with
   --normal True, no --crop_check True in templates, stride 1-44, batch >= 1, one GPU index.
3. All scripts print --help (rc 0) under python3 -I.
4. mrcheader geometry reproduces the derived cases (EMD-10387 150^3 @ 1.043 A -> 156^3 -> 150^3, 1000 windows; 432^3 @
   0.86 A -> 371^3, 21952 windows; 40^3 -> 41^3 padded to 48; stride 44 vs 45 gaps; the name gate).
5. inspect_map / build_cryocodex_command / check_outputs on synthetic MRC files in a temp dir (passes and refusals).
6. The filled Slurm job (build_cryocodex_command --sbatch) passes bash -n and runs end-to-end against a fake predict.sh
   and a fake conda; a job with --crop_check True in OPTS is refused.
7. cryocodex_env_probe verdict ladder with a fake Linux host (fake nvidia-smi and conda): BLOCKED / NOT_INSTALLED /
   PARTIAL / READY_TO_VALIDATE, never VALIDATED.
8. Package hygiene: links resolve, configs/site_config.local.md git-ignored, bash -n on templates, no evidence-pack
   paths into the clone, no host-specific strings (tokens assembled from fragments).
Exit 0 = all good, 1 = failures (listed).
"""
import argparse
import glob
import json
import os
import platform
import re
import shlex
import stat
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True          # keep __pycache__ out of the package
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import mrcheader as mh  # noqa: E402

FAILS = []
PY = [sys.executable, "-I", "-B"]


def fail(msg):
    FAILS.append(msg)
    print("FAIL:", msg)


def ok(msg):
    print("ok  :", msg)


def check(cond, msg):
    (ok if cond else fail)(msg)


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


# 1. frontmatter ------------------------------------------------------------------------------------------------------
skill = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
if not skill.startswith("---\n"):
    fail("SKILL.md has no frontmatter")
else:
    fm = skill.split("---", 2)[1]
    m = re.search(r'^description:\s*"(.*)"\s*$', fm, re.M)
    check(re.search(r"^name:\s*cryocodex\s*$", fm, re.M) is not None, "frontmatter name is cryocodex")
    check(m is not None, "frontmatter has a quoted one-line description")
    if m:
        d = m.group(1)
        check("<" not in d and ">" not in d, "description has no angle brackets")
        check(len(d) <= 1024, f"description length {len(d)} <= 1024")
    try:
        import yaml  # type: ignore
        y = yaml.safe_load(fm)
        check(isinstance(y, dict) and y.get("name") == "cryocodex", "frontmatter parses with PyYAML")
    except ImportError:
        pass

# 2. flag allowlist ---------------------------------------------------------------------------------------------------
ALLOW = {"-i", "-o", "-n", "-s", "-b", "-g", "--normal", "--reverse_interpolation", "--keep_size", "--crop_check",
         "--no_logo", "--version", "-h", "--help"}
BOOLS = {"--normal", "--reverse_interpolation", "--keep_size", "--crop_check", "--no_logo"}


def commands_in(path):
    """Yield (line_no, command_text, in_template) for predict.sh invocations: fenced bash blocks, template lines, and
    inline code spans that start with a predict.sh path."""
    text = open(path, encoding="utf-8", errors="replace").read()
    is_tpl = os.sep + "templates" + os.sep in path and not path.endswith(".md")
    joined = re.sub(r"\\\n\s*", " ", text)
    fence = None
    for ln, line in enumerate(joined.splitlines(), 1):
        st = line.strip()
        if st.startswith("```"):
            fence = None if fence is not None else (st[3:].strip() or "plain")
            continue
        if fence == "text":
            continue
        if is_tpl or fence in ("bash", "sh", "plain"):
            code = line.split(" #")[0] if not st.startswith("#") else ""
            if "predict.sh" in code and not code.strip().startswith(("case", "[", "echo", "grep")):
                yield ln, code, is_tpl
            continue
        for span in re.findall(r"`([^`]*predict\.sh[^`]*)`", line):
            if re.match(r"^\s*(\S*/)?predict\.sh\s+-", span) or re.match(r"^\s*\S+=\S+\s+\S*predict\.sh", span):
                yield ln, span, False


def normalise(cmd):
    cmd = re.sub(r'\$\{(\w+)\[@\]\+"\$\{\1\[@\]\}"\}', "", cmd)        # ${ARR[@]+"${ARR[@]}"} -> nothing
    cmd = re.sub(r"\$\{[^}]*\}", "X", cmd)
    cmd = re.sub(r"\$\w+", "X", cmd)
    cmd = re.split(r"\s(?:\||<|2>&1|>)\s?", cmd)[0]
    cmd = cmd.split("predict.sh", 1)[1].lstrip("\"'")
    try:
        return shlex.split(cmd)
    except ValueError:
        return cmd.split()


checked = 0
docs = [os.path.join(ROOT, "SKILL.md")] + sorted(glob.glob(os.path.join(ROOT, "references", "*.md"))) + sorted(glob.glob(os.path.join(ROOT, "templates", "*")))
for path in docs:
    if path.endswith("validation_runbook.md"):
        continue
    rel = os.path.relpath(path, ROOT)
    for ln, cmd, is_tpl in commands_in(path):
        toks = normalise(cmd)
        flags = [t for t in toks if t.startswith("-") and not re.match(r"^-\d", t)]
        bad = [t for t in flags if t not in ALLOW]
        if bad:
            fail(f"{rel}:{ln}: flag(s) not in the allowlist {bad}: {cmd.strip()[:100]}")
        vals = {}
        for i, t in enumerate(toks):
            if t in BOOLS:
                v = toks[i + 1] if i + 1 < len(toks) else ""
                vals[t] = v
                if v not in ("True", "False"):
                    fail(f"{rel}:{ln}: {t} without True/False (got {v!r})")
            if t == "-s" and i + 1 < len(toks) and toks[i + 1].isdigit() and not (1 <= int(toks[i + 1]) <= 44):
                fail(f"{rel}:{ln}: stride {toks[i + 1]} outside 1-44")
            if t == "-b" and i + 1 < len(toks) and toks[i + 1].isdigit() and int(toks[i + 1]) < 1:
                fail(f"{rel}:{ln}: batch {toks[i + 1]} < 1")
            if t == "-g" and i + 1 < len(toks) and not re.fullmatch(r"\d+|X|N", toks[i + 1]):
                fail(f"{rel}:{ln}: -g {toks[i + 1]!r} is not one GPU index")
        if vals.get("--normal") == "True" and ("True" in (vals.get("--keep_size"), vals.get("--crop_check"))):
            fail(f"{rel}:{ln}: --normal True with a fast-mode-only option")
        if vals.get("--crop_check") == "True" and (is_tpl or re.search(r"sbatch|nohup|srun", cmd)):
            fail(f"{rel}:{ln}: --crop_check True in a batch context")
        checked += 1
check(checked >= 15, f"{checked} predict.sh command lines checked against the allowlist")

# 3. scripts --help ---------------------------------------------------------------------------------------------------
for s in sorted(glob.glob(os.path.join(SCRIPTS, "*.py"))):
    if os.path.basename(s) == "mrcheader.py":
        continue
    p = run(PY + [s, "--help"])
    check(p.returncode == 0 and "usage" in p.stdout.lower(), f"{os.path.basename(s)} --help")

# 4. geometry ---------------------------------------------------------------------------------------------------------
v = mh.f32(156.45 / 150)
check(mh.regrid_dims((150,) * 3, (v,) * 3) == (156,) * 3, "EMD-10387 150^3 @ 1.043 A -> 156^3 at 1 A")
check(mh.reverse_dims((156,) * 3, (v,) * 3) == (150,) * 3, "156^3 at 1 A -> 150^3 at 1.043 A (reverse interpolation)")
check(mh.window_starts(156) == [0, 12, 24, 36, 48, 60, 72, 84, 96, 108] and mh.window_count((156,) * 3) == 1000, "156^3, stride 12 -> 1000 windows")
v2 = mh.f32(0.86)
d2 = mh.regrid_dims((432,) * 3, (v2,) * 3)
check(d2 == (371,) * 3 and mh.window_count(d2) == 21952, "EMD-14763 432^3 @ 0.86 A -> 371^3, 21952 windows")
check(mh.regrid_dims((40,) * 3, (v,) * 3) == (41,) * 3 and mh.padded((41,) * 3) == (48,) * 3 and mh.window_count((41,) * 3) == 1, "40^3 -> 41^3 padded to 48^3, 1 window")
check(mh.regrid_dims((100, 90, 80), (1.0, 1.0, 1.0)) == (100, 90, 80), "1.0 A voxel: no resampling")
check(mh.interior_gaps(156, 44) == [] and mh.interior_gaps(156, 45) != [], "stride 44 covers every interior voxel, 45 leaves gaps")
check(mh.uncovered_voxels_per_axis(156, 12) == [0, 1, 154, 155], "outer 2 voxels per side never covered")
check(mh.reverse_skipped((1.0, 1.0, 1.0)) and not mh.reverse_skipped((v,) * 3), "reverse interpolation skipped only for 1.0 A input")
gates = {"a/emd_1.map": True, "a/x.mrc": True, "a/x_map": True, "a/x.MRC": False, "a/x.ccp4": False, "a/x.mrc.gz": False, "a/x.mrcs": False}
check(all(mh.name_gate(k)[0] == want for k, want in gates.items()), "name gate: endswith map/mrc, case-sensitive")
check(mh.BYTES_PER_WINDOW == 2211840, "2.2 MB host RAM per window (4 outputs + 1 input, float32)")


# 5. synthetic round trips --------------------------------------------------------------------------------------------
def write_mrc(path, nx, ny, nz, apix, nstart=(0, 0, 0), origin=(0.0, 0.0, 0.0), angles=(90.0, 90.0, 90.0), values=None,
              dmin=-0.05, dmax=0.15, truncate=False):
    hdr = bytearray(1024)
    struct.pack_into("<10i", hdr, 0, nx, ny, nz, 2, *nstart, nx, ny, nz)
    struct.pack_into("<3f", hdr, 40, nx * apix, ny * apix, nz * apix)
    struct.pack_into("<3f", hdr, 52, *angles)
    struct.pack_into("<3i", hdr, 64, 1, 2, 3)
    struct.pack_into("<3f", hdr, 76, dmin, dmax, 0.0)
    struct.pack_into("<i", hdr, 108, 20140)
    struct.pack_into("<3f", hdr, 196, *origin)
    hdr[208:212] = b"MAP "
    hdr[212:216] = bytes([0x44, 0x44, 0, 0])
    struct.pack_into("<f", hdr, 216, 0.1)
    n = nx * ny * nz
    with open(path, "wb") as fh:
        fh.write(hdr)
        if values is None:
            fh.write(b"\x00" * (4 * n if not truncate else 100))
        else:
            fh.write(struct.pack("<%df" % n, *values(nx, ny, nz)))


def blob(fill_in, fill_out=0.0):
    def f(nx, ny, nz):
        out = []
        for z in range(nz):
            for y in range(ny):
                for x in range(nx):
                    if min(x, y, z, nx - 1 - x, ny - 1 - y, nz - 1 - z) < 2:
                        out.append(0.0)
                    elif abs(x - nx // 2) < nx // 4 and abs(y - ny // 2) < ny // 4 and abs(z - nz // 2) < nz // 4:
                        out.append(fill_in)
                    else:
                        out.append(fill_out)
        return out
    return f


def fake_outputs(d, dims, apix, nstart, mask_in=1.0, score=0.8, name="cryocodex"):
    os.makedirs(d, exist_ok=True)
    for suf, fi, fo in (("", 0.5, 0.0), ("_out_score", score, 0.1), ("_in_mask", mask_in, 0.0), ("_in_score", score, 0.1)):
        vals = blob(fi, fo)
        flat = vals(*dims)
        write_mrc(os.path.join(d, f"{name}{suf}.mrc"), *dims, apix, nstart=nstart, values=blob(fi, fo), dmin=min(flat), dmax=max(flat))


INSPECT = os.path.join(SCRIPTS, "inspect_map.py")
BUILD = os.path.join(SCRIPTS, "build_cryocodex_command.py")
CHECK = os.path.join(SCRIPTS, "check_outputs.py")
with tempfile.TemporaryDirectory() as td:
    fix = os.path.join(td, "emd_fake.map"); write_mrc(fix, 150, 150, 150, 1.043)
    p = run(PY + [INSPECT, fix])
    check(p.returncode == 0 and "156x156x156" in p.stdout and "1000 windows" in p.stdout and "150x150x150 at 1.0430" in p.stdout,
          "inspect_map: 150^3 @ 1.043 A passes, 1 A box 156^3, 1000 windows, keep+reverse 150^3")
    no = os.path.join(td, "nonortho.mrc"); write_mrc(no, 64, 64, 64, 1.0, angles=(90.0, 90.0, 120.0))
    p = run(PY + [INSPECT, no])
    check(p.returncode == 1 and "not orthogonal" in p.stdout, "inspect_map flags a non-orthogonal cell (rc 1)")
    up = os.path.join(td, "upper.MRC"); write_mrc(up, 64, 64, 64, 1.0)
    p = run(PY + [INSPECT, up])
    check(p.returncode == 1 and "case-sensitive" in p.stdout, "inspect_map flags an upper-case .MRC (rc 1)")
    tr = os.path.join(td, "trunc.mrc"); write_mrc(tr, 64, 64, 64, 1.0, truncate=True)
    p = run(PY + [INSPECT, tr])
    check(p.returncode == 1 and "truncated" in p.stdout, "inspect_map flags a truncated file (rc 1)")
    sm = os.path.join(td, "small40.map"); write_mrc(sm, 40, 40, 40, 1.043)
    p = run(PY + [INSPECT, sm])
    check(p.returncode == 0 and "padded to 48" in p.stdout, "inspect_map notes the 48-voxel padding of a small map")
    neg = os.path.join(td, "neg.mrc"); write_mrc(neg, 64, 64, 64, 1.0, dmin=-1.0, dmax=-0.1)
    p = run(PY + [INSPECT, neg])
    check(p.returncode == 1 and "no positive density" in p.stdout, "inspect_map flags a map without positive density")

    # builder: good commands
    p = run(PY + [BUILD, "-i", fix, "-o", os.path.join(td, "new_out")])
    lines = [l for l in p.stdout.splitlines() if not l.startswith("#")]
    check(p.returncode == 0 and lines and lines[0].endswith(f"-i {fix} -o {os.path.join(td, 'new_out')}") and "template -- not run" in p.stdout,
          "builder: default command, labelled template -- not run")
    p = run(PY + [BUILD, "-i", fix, "-o", "/abs/out", "--keep_size", "True", "--reverse_interpolation", "true", "-b", "4"])
    check(p.returncode == 0 and "--reverse_interpolation True --keep_size True -b 4" in p.stdout and "(150, 150, 150)" in p.stdout,
          "builder: keep_size + reverse_interpolation, booleans normalised to True, expected box 150^3")
    p = run(PY + [BUILD, "-i", "/abs/in.mrc", "-o", "/abs/out", "--slurm", "--home", "/opt/CryoCodex"])
    check(p.returncode == 0 and '-g "${CUDA_VISIBLE_DEVICES:-0}"' in p.stdout, 'builder --slurm emits -g "${CUDA_VISIBLE_DEVICES:-0}"')
    # builder: refusals
    refusals = {
        "bare boolean": ["--normal"],
        "yes as boolean": ["--normal", "yes"],
        "--normal=True": ["--normal=True"],
        "normal + keep_size": ["--normal", "True", "--keep_size", "True"],
        "normal + crop_check": ["--normal", "True", "--crop_check", "True"],
        "crop_check without --interactive": ["--crop_check", "True"],
        "crop_check with --slurm": ["--crop_check", "True", "--interactive", "--slurm"],
        "stride 45": ["-s", "45"], "stride 0": ["-s", "0"], "batch 0": ["-b", "0"],
        "multi-GPU -g": ["-g", "0,1"], "-g cpu": ["-g", "cpu"], "-g with --slurm": ["-g", "1", "--slurm"],
        "alias -a": ["-a", "True"], "alias -c": ["-c", "True"], "long alias --stride": ["--stride", "12"],
        "hidden -m": ["-m", "/x.pth"], "nonexistent --half1": ["--half1", "h.mrc"], "nonexistent --cpu": ["--cpu"],
        "-n with slash": ["-n", "a/b"],
    }
    for label, extra in refusals.items():
        p = run(PY + [BUILD, "-i", fix, "-o", os.path.join(td, "o_ref")] + extra)
        check(p.returncode == 2 and "REFUSED" in p.stderr, f"builder refuses: {label}")
    for label, path in (("upper-case .MRC", up), (".map.gz", fix + ".gz"), (".ccp4", os.path.join(td, "x.ccp4")), ("non-orthogonal", no)):
        p = run(PY + [BUILD, "-i", path, "-o", os.path.join(td, "o_ref")])
        check(p.returncode == 2 and "REFUSED" in p.stderr, f"builder refuses input: {label}")
    p = run(PY + [BUILD, "-i", sm, "-o", os.path.join(td, "o_ref"), "--keep_size", "True"])
    check(p.returncode == 2 and "< 48" in p.stderr, "builder refuses --keep_size True for a 1 A box axis < 48")
    ex = os.path.join(td, "existing"); fake_outputs(ex, (8, 8, 8), 1.0, (0, 0, 0))
    p = run(PY + [BUILD, "-i", fix, "-o", ex])
    check(p.returncode == 2 and "overwrites" in p.stderr, "builder refuses an output dir that already holds outputs")

    # check_outputs
    good = os.path.join(td, "run_default"); fake_outputs(good, (60, 56, 52), 1.0, (40, 44, 48))
    p = run(PY + [CHECK, good, "--input", fix, "--stats"])
    check(p.returncode == 0 and "fast-mode crop" in p.stdout and "lies inside" in p.stdout, "check_outputs passes a consistent fast-mode output set")
    kr = os.path.join(td, "run_keeprev"); fake_outputs(kr, (150, 150, 150), 1.043, (0, 0, 0), score=1.05)
    p = run(PY + [CHECK, kr, "--input", fix, "--keep-size", "--reverse-interpolation"])
    check(p.returncode == 0 and "= expected" in p.stdout and "> 1" in p.stdout, "check_outputs: keep+reverse box 150^3 ok, notes scores > 1")
    p = run(PY + [CHECK, kr, "--input", fix, "--keep-size"])
    check(p.returncode == 1 and "!= expected (156, 156, 156)" in p.stdout, "check_outputs: --keep_size alone expects the 156^3 1 A box")
    bm = os.path.join(td, "run_badmask"); fake_outputs(bm, (60, 56, 52), 1.0, (40, 44, 48), mask_in=0.7)
    p = run(PY + [CHECK, bm, "--input", fix, "--stats"])
    check(p.returncode == 1 and "binary" in p.stdout, "check_outputs flags a non-binary mask")
    os.remove(os.path.join(bm, "cryocodex_in_score.mrc"))
    p = run(PY + [CHECK, bm])
    check(p.returncode == 1 and "missing cryocodex_in_score.mrc" in p.stdout, "check_outputs flags a missing output")
    with open(os.path.join(good, "cryocodex.mrc"), "r+b") as fh:
        fh.truncate(2000)
    p = run(PY + [CHECK, good])
    check(p.returncode == 1 and "partial write" in p.stdout, "check_outputs flags a truncated output")
    em = os.path.join(td, "run_empty"); os.makedirs(os.path.join(em, "round_1_check"))
    with open(os.path.join(em, "run.log"), "w") as fh:
        fh.write("Improving x now\nRuntimeError: Crop inspection needs terminal input.\n")
    p = run(PY + [CHECK, em])
    check(p.returncode == 1 and "round_*_check" in p.stdout and "terminal" in p.stdout, "check_outputs explains an aborted --crop_check run from the log")

    # 6. filled Slurm job, end to end against fakes --------------------------------------------------------------------
    cc = os.path.join(td, "CryoCodex"); os.makedirs(os.path.join(cc, "model_state_dicts"))
    with open(os.path.join(cc, "model_state_dicts", "CryoCodex.pth"), "wb") as fh:
        fh.write(b"x")
    fake_predict = r'''#!/bin/bash
# fake predict.sh for tests: records its arguments and writes four small outputs like CryoCodex would
out=""; name="cryocodex"; args=("$@")
while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift ;; -n) name="$2"; shift ;; esac; shift; done
echo "ARGS: ${args[*]}"
read -t 1 line && echo "STDIN NOT EMPTY"
python3 -I "$FAKE_WRITER" "$out" "$name" && for s in "" _out_score _in_mask _in_score; do echo "path: $out/$name$s.mrc"; done
'''
    with open(os.path.join(cc, "predict.sh"), "w") as fh:
        fh.write(fake_predict)
    os.chmod(os.path.join(cc, "predict.sh"), 0o755)
    writer = os.path.join(td, "fake_writer.py")
    with open(writer, "w") as fh:
        fh.write("import sys\nsys.path.insert(0, %r)\nimport validate_static_helpers as h\nh.fake_outputs(sys.argv[1], (60, 56, 52), 1.0, (40, 44, 48), name=sys.argv[2])\n" % td)
    with open(os.path.join(td, "validate_static_helpers.py"), "w") as fh:
        import inspect as _inspect
        fh.write("import os, struct\n" + _inspect.getsource(write_mrc) + _inspect.getsource(blob) + _inspect.getsource(fake_outputs))
    bindir = os.path.join(td, "bin"); os.makedirs(bindir)
    conda = os.path.join(bindir, "conda")
    with open(conda, "w") as fh:
        fh.write("#!/bin/sh\nexit 0\n")
    os.chmod(conda, 0o755)
    job = os.path.join(td, "job.sbatch")
    outj = os.path.join(td, "out_job")
    p = run(PY + [BUILD, "-i", fix, "-o", outj, "--home", cc, "--sbatch", job, "--account", "acct", "--partition", "gpu",
                  "--cpus", "8", "--mem", "16G", "--time", "00:30:00", "--site-env", f"export CONDA_EXE={conda}", "-b", "4"])
    txt = open(job).read() if os.path.exists(job) else ""
    q = run(["bash", "-n", job]) if txt else None
    check(p.returncode == 0 and q is not None and q.returncode == 0 and "#SBATCH --account=acct" in txt and "OPTS=(-b 4)" in txt
          and not re.search(r"<[A-Z_]+>", txt), "builder --sbatch fills the template (bash -n clean, no placeholders left)")
    env = dict(os.environ, FAKE_WRITER=writer, CUDA_VISIBLE_DEVICES="3", PYTHONDONTWRITEBYTECODE="1")
    env.pop("SLURM_JOB_ID", None)
    r = run(["bash", job], env=env, timeout=300)
    log = r.stdout + r.stderr
    check(r.returncode == 0 and "ARGS: -i " in log and "-g 3 --no_logo True -b 4" in log and "OUTPUT CHECK: OK" in log
          and "STDIN NOT EMPTY" not in log, "filled job runs end to end: -g from CUDA_VISIBLE_DEVICES, stdin closed, outputs checked")
    if r.returncode != 0:
        print(log[-1500:])
    r = run(["bash", job], env=env, timeout=60)
    check(r.returncode == 2 and "not empty" in r.stderr, "job refuses a non-empty output directory")
    bad = txt.replace("OPTS=(-b 4)", "OPTS=(--crop_check True)").replace(outj, outj + "_2")
    with open(job + "2", "w") as fh:
        fh.write(bad)
    r = run(["bash", job + "2"], env=env, timeout=60)
    check(r.returncode == 2 and "--crop_check True needs a terminal" in r.stderr, "job refuses --crop_check True in OPTS")
    r = run(["bash", job + "2"], env=dict(env, CUDA_VISIBLE_DEVICES="0,1"), timeout=60)
    check(r.returncode == 2, "job refuses (crop_check or several GPUs) before running")
    two = txt.replace(outj, outj + "_3")
    with open(job + "3", "w") as fh:
        fh.write(two)
    r = run(["bash", job + "3"], env=dict(env, CUDA_VISIBLE_DEVICES="0,1"), timeout=60)
    check(r.returncode == 2 and "several GPUs" in r.stderr, "job refuses more than one visible GPU")

    # 7. probe verdict ladder (fake Linux host) ----------------------------------------------------------------------
    import cryocodex_env_probe as probe_mod
    fbin = os.path.join(td, "fakebin"); os.makedirs(fbin)
    with open(os.path.join(fbin, "nvidia-smi"), "w") as fh:
        fh.write("#!/bin/sh\necho '0, NVIDIA A100-SXM4-40GB, 40960 MiB, 40000 MiB, 550.54.15'\n")
    envs_file = os.path.join(td, "envs.json")
    with open(os.path.join(fbin, "conda"), "w") as fh:
        fh.write('#!/bin/sh\ncase "$1" in\n --version) echo "conda 24.9.2";;\n env) cat "%s";;\n'
                 ' run) echo \'CRYOCODEX_ENV_CHECK {"python": "3.11.10", "torch": "2.5.1+cu124", "torch_cuda_build": "12.4",'
                 ' "cuda_available": true, "device_count": 1, "device0": "A100", "mrcfile": "1.5.4", "numba": "0.61.2",'
                 ' "einops": "0.8.1", "timm": "1.0.24", "numexpr": "2.10.0", "numpy": "1.26.4", "scipy": "1.16.0",'
                 ' "tqdm": "4.67.1", "PIL": "11.0.0", "torchvision": "0.20.1"}\';;\nesac\n' % envs_file)
    for f in ("nvidia-smi", "conda"):
        os.chmod(os.path.join(fbin, f), 0o755)
    home = os.path.join(td, "cc_home"); os.makedirs(os.path.join(home, "model_state_dicts")); os.makedirs(os.path.join(home, ".git"))
    open(os.path.join(home, "predict.sh"), "w").close(); os.chmod(os.path.join(home, "predict.sh"), 0o755)
    with open(os.path.join(home, "predict.py"), "w") as fh:
        fh.write('__version__ = "1.0.0"\n')
    with open(os.path.join(home, ".git", "HEAD"), "w") as fh:
        fh.write(mh.PIN_COMMIT + "\n")
    saved = (platform.system, platform.machine, dict(os.environ))
    try:
        platform.system = lambda: "Linux"
        platform.machine = lambda: "x86_64"
        os.environ["PATH"] = fbin + os.pathsep + "/usr/bin:/bin"
        os.environ["CONDA_EXE"] = os.path.join(fbin, "conda")
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        A = lambda **k: argparse.Namespace(**dict(dict(home=home, env_name=None, env_check=False, hash=False, out_root=None), **k))  # noqa: E731
        with open(envs_file, "w") as fh:
            json.dump({"envs": ["/opt/conda"]}, fh)
        v1 = probe_mod.probe(A())["verdict"]
        with open(envs_file, "w") as fh:
            json.dump({"envs": ["/opt/conda", "/opt/conda/envs/cryocodex_env"]}, fh)
        v2 = probe_mod.probe(A(env_check=True))["verdict"]
        with open(os.path.join(home, "model_state_dicts", "CryoCodex.pth"), "wb") as fh:
            fh.truncate(mh.WEIGHTS_BYTES)            # sparse file of the published size; nothing is downloaded
        r3 = probe_mod.probe(A(env_check=True))
        v4 = probe_mod.probe(A())["verdict"]
        platform.system = lambda: "Darwin"
        v5 = probe_mod.probe(A(env_check=True))["verdict"]
    finally:
        platform.system, platform.machine = saved[0], saved[1]
        os.environ.clear(); os.environ.update(saved[2])
    check(v1 == "NOT_INSTALLED", f"probe: env missing -> NOT_INSTALLED (got {v1})")
    check(v2 == "PARTIAL", f"probe: weights missing -> PARTIAL (got {v2})")
    check(r3["verdict"] == "READY_TO_VALIDATE", f"probe: all present + env check -> READY_TO_VALIDATE (got {r3['verdict']}; gaps {r3['gaps']})")
    check(v4 == "PARTIAL", f"probe: env not checked -> PARTIAL (got {v4})")
    check(v5 == "BLOCKED", f"probe: macOS -> BLOCKED (got {v5})")
src = open(os.path.join(SCRIPTS, "cryocodex_env_probe.py")).read()
check('"VALIDATED"' not in src.replace('"VALIDATED is', ""), "probe source never assigns a VALIDATED verdict")

# 8. hygiene ----------------------------------------------------------------------------------------------------------
missing = []
for path in [os.path.join(ROOT, "SKILL.md")] + glob.glob(os.path.join(ROOT, "references", "*.md")) + glob.glob(os.path.join(ROOT, "templates", "*.md")):
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", open(path, encoding="utf-8").read()):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path), target))) and "site_config.local.md" not in target:
            missing.append(f"{os.path.relpath(path, ROOT)} -> {target}")
check(not missing, "all relative links resolve" + (f": {missing}" if missing else ""))
gi = [l.strip() for l in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8")]
check("configs/site_config.local.md" in gi, ".gitignore lists configs/site_config.local.md")
for t in sorted(glob.glob(os.path.join(ROOT, "templates", "*.template"))):
    p = run(["bash", "-n", t])
    check(p.returncode == 0, f"bash -n {os.path.relpath(t, ROOT)}")
TOKENS = [("/Us" + "ers/", False), ("x." + "guo", False), ("next" + "cloud", False), ("mac_" + "mini", False),
          ("Maria_" + "projects", False), ("sources/source/" + "CryoCodex", False), ("~/.claude/" + "skills", False),
          ("~/.codex/" + "skills", False), ("bhg" + "tiger", False)]
hits = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
    for fn in filenames:
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT)
        if fn.endswith((".pyc", ".pdf", ".tsv")) or fn == "MANIFEST.tsv":
            hits.append(f"{rel}: evidence-pack-like file shipped")
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for ln, line in enumerate(text.splitlines(), 1):
            for tok, _ in TOKENS:
                if tok in line:
                    hits.append(f"{rel}:{ln}: forbidden token #{TOKENS.index((tok, _)) + 1}")
for h in hits[:30]:
    fail(h)
if not hits:
    ok(f"no host-specific or evidence-pack token ({len(TOKENS)} patterns) and no evidence files in the package")

print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' FAILURE(S)'}")
sys.exit(1 if FAILS else 0)
