#!/usr/bin/env python3
"""validate_static.py -- offline checks for the cryofm skill (no GPU, no network, no CryoFM import).

    python3 tests/validate_static.py

1. SKILL.md frontmatter: name + quoted description, YAML-parsable (PyYAML if present, else a minimal check).
2. Every `cfm denoise|enhance` command line in SKILL.md, references/*.md and templates/* uses only flags from the
   live help capture (references/live_help_2026-10-08/) plus the launcher knobs, and every likelihood command
   carries --norm-grad; no --op appears twice on one command.
3. All scripts run `--help` (rc 0) under `python3 -I`.
4. mrcheader geometry reproduces the known cases (EMD-11638 92^3/8 patches, EMD-12042 176^3/125, EMD-29934 66^3/8,
   odd cube assert, small box fail).
5. inspect_map / check_cfm_output / restore_origin / build_cfm_command on synthetic MRC files in a temp dir.
6. Package hygiene for the public copy: configs/site_config.example.md present, configs/site_config.local.md git-ignored,
   `bash -n` on templates/*.sbatch.template, build_cfm_command --sbatch fills the template into a bash -n-clean job file.
7. No host-specific string (home paths, user/account/cluster/node/partition names of the validated site) outside
   configs/site_config.example.md. The tokens are assembled from fragments so this file carries none of them.
Exit 0 = all good, 1 = failures (listed).
"""
import glob
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import mrcheader as mh  # noqa: E402

FAILS = []
LOCAL_ONLY = ("configs/site_config.local.md",)   # git-ignored by design; mentioned in the docs, never shipped


def fail(msg):
    FAILS.append(msg)
    print("FAIL:", msg)


def ok(msg):
    print("ok  :", msg)


# 1. frontmatter
skill = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
if not skill.startswith("---\n"):
    fail("SKILL.md has no frontmatter")
else:
    fm = skill.split("---", 2)[1]
    try:
        import yaml  # type: ignore
        d = yaml.safe_load(fm)
        if not isinstance(d, dict) or "name" not in d or "description" not in d:
            fail("frontmatter lacks name/description")
        elif d["name"] != "cryofm":
            fail("frontmatter name != cryofm")
        else:
            ok("frontmatter parses (PyYAML) with name and description")
    except ImportError:
        if re.search(r'^name:\s*cryofm\s*$', fm, re.M) and re.search(r'^description:\s*"', fm, re.M):
            ok("frontmatter has name and a quoted description (PyYAML absent, minimal check)")
        else:
            fail("frontmatter missing name or quoted description")

# 2. flag whitelist
live = set()
for f in glob.glob(os.path.join(ROOT, "references", "live_help_2026-10-08", "*_sampling_help.txt")):
    live |= set(re.findall(r"(?<![\w-])(-{1,2}[a-z][a-z0-9-]*)", open(f).read()))
live |= {"--num_processes", "--main_process_port", "-h", "--help"}
if not live:
    fail("no live help capture found")
cmd_re = re.compile(r"^\s*(?:cfm|run)\s+(denoise|enhance)\b(.*)$")
checked = 0
for path in [os.path.join(ROOT, "SKILL.md")] + glob.glob(os.path.join(ROOT, "references", "*.md")) + glob.glob(os.path.join(ROOT, "templates", "*")):
    text = open(path, encoding="utf-8", errors="replace").read()
    # join backslash continuations
    text = re.sub(r"\\\n\s*", " ", text)
    in_text_fence = False
    for ln, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            info = line.strip()[3:].strip()
            in_text_fence = (not in_text_fence) and info == "text" if not in_text_fence else False
            continue
        if in_text_fence or line.lstrip().startswith("#"):
            continue   # quoted upstream help/errata (```text) and comments are not our commands
        m = cmd_re.match(line.replace("`", " "))
        if not m:
            continue
        sub, rest = m.group(1), m.group(2)
        rest = rest.split("#")[0].split("|")[0]
        rest = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", "X", rest).replace("<MODELS>", "X").replace("…", "").replace("...", "")
        try:
            toks = shlex.split(rest)
        except ValueError:
            toks = rest.split()
        flags = [t for t in toks if t.startswith("-") and not re.match(r"^-?\d", t)]
        bad = [t for t in flags if t.split("=")[0] not in live]
        if bad:
            fail(f"{os.path.relpath(path, ROOT)}:{ln}: unknown cfm flag(s) {bad}")
        if sub == "denoise" and "--norm-grad" not in flags and "--help" not in flags and "-h" not in flags and flags:
            fail(f"{os.path.relpath(path, ROOT)}:{ln}: cfm denoise command without --norm-grad")
        if sub == "enhance" and ("-i1" in flags) and "--norm-grad" not in flags:
            fail(f"{os.path.relpath(path, ROOT)}:{ln}: cfm enhance with half maps but without --norm-grad")
        if flags.count("--op") > 1:
            fail(f"{os.path.relpath(path, ROOT)}:{ln}: --op repeated (only the last list survives)")
        if sub == "denoise" and ("--output-tag" in flags or "--cfg-weight" in flags):
            fail(f"{os.path.relpath(path, ROOT)}:{ln}: cfm denoise with --output-tag/--cfg-weight (rejected)")
        checked += 1
ok(f"{checked} cfm command lines checked against {len(live)} live flags")

# 3. scripts --help
for s in sorted(glob.glob(os.path.join(SCRIPTS, "*.py"))):
    if os.path.basename(s) == "mrcheader.py":
        continue
    p = subprocess.run([sys.executable, "-I", s, "--help"], capture_output=True, text=True)
    if p.returncode != 0:
        fail(f"{os.path.basename(s)} --help rc {p.returncode}: {p.stderr[-200:]}")
    else:
        ok(f"{os.path.basename(s)} --help")

# 4. geometry
cases = [(256, 0.5332, 92, 8), (256, 1.029, 176, 125), (104, 0.96, 66, 8), (256, 1.06, 180, 125), (400, 1.0, 266, 512), (128, 1.5, 128, 27)]
for box, apix, S, patches in cases:
    s, _ = mh.rescaled_boxsize(box, apix)
    offs = mh.patch_offsets(s)
    n = len(offs) ** 3 if offs else None
    if s != S or n != patches:
        fail(f"geometry {box}@{apix}: got S={s}, patches={n}; expected {S}/{patches}")
    else:
        ok(f"geometry {box}^3 @ {apix} A -> {S}^3, {patches} patches")
if mh.patch_offsets(42) is not None:
    fail("box 42 should fail the min-box gate")
else:
    ok("box < 64 fails the min-box gate")


def write_mrc(path, nx, ny, nz, apix, nstart=(0, 0, 0), origin=(0.0, 0.0, 0.0), order=(1, 2, 3), with_data=True, mode=2):
    hdr = bytearray(1024)
    struct.pack_into("<10i", hdr, 0, nx, ny, nz, mode, *nstart, nx, ny, nz)
    struct.pack_into("<3f", hdr, 40, nx * apix, ny * apix, nz * apix)
    struct.pack_into("<3f", hdr, 52, 90.0, 90.0, 90.0)
    struct.pack_into("<3i", hdr, 64, *order)
    struct.pack_into("<3f", hdr, 76, -1.0, 1.0, 0.0)
    struct.pack_into("<2i", hdr, 88, 1, 0)
    struct.pack_into("<i", hdr, 108, 20140)
    struct.pack_into("<3f", hdr, 196, *origin)
    hdr[208:212] = b"MAP "
    hdr[212:216] = bytes([0x44, 0x44, 0x00, 0x00])
    struct.pack_into("<f", hdr, 216, 0.5)
    struct.pack_into("<i", hdr, 220, 1)
    hdr[224:304] = b"synthetic cryofm skill test".ljust(80)
    with open(path, "wb") as fh:
        fh.write(hdr)
        if with_data:
            fh.write(b"\x00" * (nx * ny * nz * 4))


with tempfile.TemporaryDirectory() as td:
    # odd cube and small box through inspect_map
    odd = os.path.join(td, "odd.mrc"); write_mrc(odd, 127, 127, 127, 1.0, with_data=False)
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "inspect_map.py"), odd], capture_output=True, text=True)
    (ok if p.returncode == 1 and "ODD" in p.stdout else fail)("inspect_map flags an odd cubic box (rc 1)")
    small = os.path.join(td, "small.mrc"); write_mrc(small, 64, 64, 64, 0.5, with_data=False)
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "inspect_map.py"), small], capture_output=True, text=True)
    (ok if p.returncode == 1 and "< 64 voxels" in p.stdout else fail)("inspect_map flags a sub-96 A box (rc 1)")
    # good pair + mismatch
    h1 = os.path.join(td, "half1.mrc"); h2 = os.path.join(td, "half2.mrc"); prim = os.path.join(td, "primary.mrc")
    write_mrc(h1, 8, 8, 8, 12.0, nstart=(77, 77, 110), with_data=True)   # tiny data, 96 A box -> S=64 -> 1 patch
    write_mrc(h2, 8, 8, 8, 12.0, nstart=(77, 77, 110), with_data=True)
    write_mrc(prim, 6, 6, 6, 12.0, with_data=True)
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "inspect_map.py"), h1, h2], capture_output=True, text=True)
    (ok if p.returncode == 0 and "placement is non-zero" in p.stdout else fail)("inspect_map passes an even 96 A pair and warns about NSTART")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "inspect_map.py"), h1, prim], capture_output=True, text=True)
    (ok if p.returncode == 1 and "same shape" in p.stdout else fail)("inspect_map flags a half-map/primary box mismatch")
    # build_cfm_command on the pair, refuses traps
    out = os.path.join(td, "out_new")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "denoise", "--half1", h1, "--half2", h2, "--out", out, "--shorthand", "--seed", "0"], capture_output=True, text=True)
    good = p.returncode == 0 and "--norm-grad --use-lamb-w" in " ".join(p.stdout.replace("\\\n", " ").split()) and "--model-dir pretrain" in p.stdout and "restore_origin" in p.stdout
    (ok if good else fail)("build_cfm_command denoise emits --norm-grad --use-lamb-w, pretrain shorthand, origin warning")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "emready", "--map", h1, "--out", out, "--shorthand"], capture_output=True, text=True)
    (ok if p.returncode == 0 and "--output-tag 0 --cfg-weight 0.5" in " ".join(p.stdout.replace("\\\n", " ").split()) else fail)("build_cfm_command emready pairs tag 0 with CFG 0.5")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "aniso", "--half1", h1, "--half2", h2, "--out", out, "--shorthand"], capture_output=True, text=True)
    (ok if p.returncode == 2 and "needs --star" in p.stderr else fail)("build_cfm_command refuses aniso without a STAR")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "denoise", "--half1", h1 + ".gz", "--half2", h2, "--out", out, "--shorthand"], capture_output=True, text=True)
    (ok if p.returncode == 2 and ".gz" in p.stderr else fail)("build_cfm_command refuses .gz inputs")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "denoise", "--half1", h1, "--half2", h2, "--out", out, "--shorthand", "--extra", "--op inpaint"], capture_output=True, text=True)
    (ok if p.returncode == 2 and "--op" in p.stderr else fail)("build_cfm_command refuses a second --op")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "denoise", "--half1", h1, "--half2", h2, "--out", out, "--shorthand", "--num-timesteps", "300"], capture_output=True, text=True)
    (ok if p.returncode == 0 and "does not divide 1000" in p.stdout else fail)("build_cfm_command warns on 300 steps")
    # restore_origin: output written like cfm (origin 0) on the same grid
    cfm_out = os.path.join(td, "half1_external_reconstruct.mrc"); write_mrc(cfm_out, 8, 8, 8, 12.0, with_data=True)
    reg = os.path.join(td, "half1_registered.mrc")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "restore_origin.py"), h1, cfm_out, reg], capture_output=True, text=True)
    hh = mh.read_header(reg) if os.path.exists(reg) else None
    (ok if p.returncode == 0 and hh and (hh["nxstart"], hh["nystart"], hh["nzstart"]) == (77, 77, 110) and mh.read_header(cfm_out)["nxstart"] == 0 else fail)("restore_origin copies NSTART into a new file and leaves the cfm output untouched")
    # restore_origin with a 3,2,1 reference: NSTART (161,147,141) CRS -> XYZ (141,147,161)
    ref321 = os.path.join(td, "ref321.mrc"); write_mrc(ref321, 8, 8, 8, 12.0, nstart=(161, 147, 141), order=(3, 2, 1), with_data=True)
    reg2 = os.path.join(td, "reg2.mrc")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "restore_origin.py"), ref321, cfm_out, reg2], capture_output=True, text=True)
    hh = mh.read_header(reg2) if os.path.exists(reg2) else None
    (ok if p.returncode == 0 and hh and (hh["nxstart"], hh["nystart"], hh["nzstart"]) == (141, 147, 161) else fail)("restore_origin permutes a 3,2,1 reference NSTART into XYZ")
    # restore_origin refuses a grid mismatch
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "restore_origin.py"), prim, cfm_out, os.path.join(td, "x.mrc")], capture_output=True, text=True)
    (ok if p.returncode != 0 and "not the same grid" in (p.stderr + p.stdout) else fail)("restore_origin refuses a grid mismatch")
    # check_cfm_output on a fake output dir
    od = os.path.join(td, "outdir"); os.makedirs(od)
    write_mrc(os.path.join(od, "half1_external_reconstruct.mrc"), 8, 8, 8, 12.0, with_data=True)
    write_mrc(os.path.join(od, "half2_external_reconstruct.mrc"), 8, 8, 8, 12.0, with_data=True)
    write_mrc(os.path.join(od, "avg_external_reconstruct.mrc"), 8, 8, 8, 12.0, with_data=True)
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "check_cfm_output.py"), od, "--input", h1, "--expect", "3"], capture_output=True, text=True)
    (ok if p.returncode == 0 and "non-zero placement" in p.stdout else fail)("check_cfm_output passes 3 outputs and warns about the input placement")
    with open(os.path.join(od, "avg_external_reconstruct.mrc"), "r+b") as fh:
        fh.truncate(1024 + 100)
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "check_cfm_output.py"), od, "--input", h1, "--expect", "3"], capture_output=True, text=True)
    (ok if p.returncode == 1 and "truncated" in p.stdout else fail)("check_cfm_output flags a truncated output")

# 6. package hygiene (public copy)
if os.path.isfile(os.path.join(ROOT, "configs", "site_config.example.md")):
    ok("configs/site_config.example.md present (sanitized example)")
else:
    fail("configs/site_config.example.md missing")
gi = os.path.join(ROOT, ".gitignore")
gi_lines = [l.strip() for l in open(gi, encoding="utf-8")] if os.path.isfile(gi) else []
for local in LOCAL_ONLY:
    if local in gi_lines:
        ok(f"{local} is git-ignored")
    else:
        fail(f".gitignore does not list {local}")
    if os.path.exists(os.path.join(ROOT, local)):
        print(f"note: {local} is present (git-ignored; never publish it)")
for t in sorted(glob.glob(os.path.join(ROOT, "templates", "*.sbatch.template"))):
    p = subprocess.run(["bash", "-n", t], capture_output=True, text=True)
    (ok if p.returncode == 0 else fail)(f"{os.path.relpath(t, ROOT)} passes bash -n" + ("" if p.returncode == 0 else ": " + p.stderr[-200:]))
with tempfile.TemporaryDirectory() as td:
    h1 = os.path.join(td, "half1.mrc"); h2 = os.path.join(td, "half2.mrc")
    write_mrc(h1, 8, 8, 8, 12.0, with_data=True); write_mrc(h2, 8, 8, 8, 12.0, with_data=True)
    models = os.path.join(td, "cryofm-v2")
    for v in ("cryofm2-pretrain", "cryofm2-emhancer", "cryofm2-emready"):
        os.makedirs(os.path.join(models, v))
        for f in ("config.yaml", "model.safetensors"):
            open(os.path.join(models, v, f), "w").close()
    job = os.path.join(td, "job.sbatch")
    p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "build_cfm_command.py"), "denoise", "--half1", h1, "--half2", h2,
                        "--out", os.path.join(td, "out_new"), "--models", models, "--sbatch", job, "--account", "acct", "--partition", "part",
                        "--cpus", "18", "--mem", "120G", "--site-env", "true"], capture_output=True, text=True)
    txt = open(job).read() if os.path.exists(job) else ""
    q = subprocess.run(["bash", "-n", job], capture_output=True, text=True) if txt else None
    good = (p.returncode == 0 and q is not None and q.returncode == 0 and "--norm-grad --use-lamb-w" in " ".join(txt.replace("\\\n", " ").split())
            and os.path.join(models, "cryofm2-pretrain") in txt and "<ABS_INPUT_1>" not in txt and "#SBATCH --account=acct" in txt
            and "<ACCOUNT>" not in txt and "<GPU_PARTITION>" not in txt and "SITE_ENV_CMD=true" in txt)
    (ok if good else fail)("build_cfm_command --sbatch fills templates/slurm_cfm.sbatch.template (bash -n clean, command and paths in place)")
    if not good:
        print(p.stdout[-400:], p.stderr[-400:], (q.stderr if q else "")[-200:])

# 7. no host-specific strings in the public copy (tokens built from fragments; whole-word where marked)
HOST_TOKENS = [("/ho" + "me/xg" + "uo", False), ("xg" + "uo", True), ("nks" + "ei19360", False), ("struct" + "bio", False),
               ("snel" + "lius", False), ("in" + "t4", True), ("gc" + "n56", True), ("sr" + "v1", True), ("cbu" + "ild", True),
               ("/gp" + "fs", False), ("/scratch-" + "shared", False), ("/scratch-" + "local", False), ("surf_" + "snel", False),
               ("SYSTEM_" + "REPORT", False), ("acc" + "info", True), ("gpu_" + "a100", False), ("gpu_" + "h100", False),
               ("~/.claude/" + "skills", False), ("~/.codex/" + "skills", False)]
ALLOWED = {"configs/site_config.example.md"}
hits = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
    for fn in filenames:
        path = os.path.join(dirpath, fn)
        relp = os.path.relpath(path, ROOT).replace(os.sep, "/")
        if relp in ALLOWED or fn.endswith(".pyc"):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for ln, line in enumerate(text.splitlines(), 1):
            for tok, word in HOST_TOKENS:
                pat = (r"(?<![A-Za-z0-9_])" + re.escape(tok) + r"(?![A-Za-z0-9_])") if word else re.escape(tok)
                if re.search(pat, line, re.I):
                    hits.append(f"{relp}:{ln}: host-specific token #{HOST_TOKENS.index((tok, word)) + 1}")
for h in hits[:40]:
    fail(h)
if not hits:
    ok(f"no host-specific token ({len(HOST_TOKENS)} patterns) outside {', '.join(sorted(ALLOWED))}")

print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' FAILURE(S)'}")
sys.exit(1 if FAILS else 0)
