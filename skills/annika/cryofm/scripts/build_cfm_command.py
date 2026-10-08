#!/usr/bin/env python3
"""build_cfm_command.py -- write a correct `cfm` command (and optionally a Slurm job) without the documented traps.

    python3 build_cfm_command.py denoise   --half1 H1 --half2 H2 --out OUT (--models DIR | --shorthand) [--mask M] [--seed 0]
    python3 build_cfm_command.py aniso     --half1 H1 --half2 H2 --out OUT --star particles.star [--fmask-threshold 10]
    python3 build_cfm_command.py nonuniform --half1 H1 --half2 H2 --out OUT [--nbands 64]
    python3 build_cfm_command.py inpaint   --half1 H1 --half2 H2 --out OUT --star particles.star
    python3 build_cfm_command.py emhancer  --map MAP --out OUT
    python3 build_cfm_command.py emready   --map MAP --out OUT
    python3 build_cfm_command.py enhance-posterior --style emhancer|emready --half1 H1 --half2 H2 [--map MAP] --out OUT [--op denoise|non-uniform]
      common: [--batch-size 4] [--no-bf16] [--num-timesteps 200] [--lamb-base 1000.0] [--cfg-weight W] [--num-processes N]
              [--no-check] [--extra "--debug ..."]
              [--sbatch JOBFILE [--account A] [--partition P] [--cpus N] [--mem 120G] [--time 01:00:00] [--node-tmp /tmp] [--site-env CMD]]

Rules enforced (from references/03, 04, 06): --norm-grad --use-lamb-w on every likelihood path; one --op list;
tag/CFG pairing per model; variant folder (not the repo root); absolute paths; new output dir; .mrc/.map extension;
header gates via inspect_map (unless --no-check); --num-timesteps a divisor of 1000 (warning); --mask always with
--bbox. --shorthand emits `--model-dir pretrain|emhancer|emready` for sites whose cfm launcher resolves those names
(otherwise --models DIR spells out the variant folder). Prints the command; with --sbatch also fills
templates/slurm_cfm.sbatch.template into a job file (unfilled <PLACEHOLDERS> are listed; the job refuses to run with them).
stdlib only.
"""
import argparse
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mrcheader as mh  # noqa: E402

MODES = ("denoise", "aniso", "nonuniform", "inpaint", "emhancer", "emready", "enhance-posterior")
STYLE = {"emhancer": {"dir": "cryofm2-emhancer", "tag": 1, "cfg": 2.0}, "emready": {"dir": "cryofm2-emready", "tag": 0, "cfg": 0.5}}


def die(msg):
    print("REFUSED: " + msg, file=sys.stderr)
    sys.exit(2)


def warn(msg, notes):
    notes.append("WARN: " + msg)


def absolute(p, what, notes):
    if p is None:
        return None
    if not os.path.isabs(p):
        warn(f"{what} '{p}' is not absolute; inside a container only absolute paths under bound trees are safe", notes)
    return p


def check_map(p, what, notes, require_exists):
    ext = os.path.splitext(p)[1].lower()
    if ext not in mh.ACCEPTED_EXT:
        die(f"{what} '{p}' has extension '{ext}': cfm accepts only .mrc/.map (gunzip .map.gz first)")
    if os.path.exists(p):
        try:
            h = mh.read_header(p)
        except (OSError, mh.HeaderError) as e:
            die(f"{what}: cannot read MRC header ({e})")
        g = mh.cryofm_geometry(h)
        if not g["axis_ok"]:
            die(f"{what}: axis order {g['axis_order']} is not supported by cfm")
        if g["odd_cube_assert"]:
            die(f"{what}: odd cubic box {g['dims']} hits `assert iz % 2 == 0`; pad to an even box first")
        if not g["min_box_ok"]:
            die(f"{what}: resampled box {g['resampled_edge']} < 64 voxels (box*apix < ~96 A)")
        if g["placement_nonzero"]:
            warn(f"{what} has non-zero NSTART/ORIGIN -> run restore_origin.py on the outputs", notes)
        if g["band_limit_note"]:
            warn(f"{what} pixel {g['apix']:.3f} A < 1.5 A -> outputs band-limited at ~3 A (consider --spectral-mixing, see 04 §3)", notes)
        return h, g
    if require_exists:
        die(f"{what} '{p}' does not exist")
    warn(f"{what} '{p}' not found here; header gates skipped", notes)
    return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=MODES)
    ap.add_argument("--half1"); ap.add_argument("--half2"); ap.add_argument("--map")
    ap.add_argument("--out", required=True, help="NEW output directory (absolute)")
    ap.add_argument("--models", help="folder containing cryofm2-pretrain/ cryofm2-emhancer/ cryofm2-emready/")
    ap.add_argument("--shorthand", action="store_true", help="emit --model-dir pretrain|emhancer|emready (for sites whose cfm launcher resolves these names)")
    ap.add_argument("--style", choices=list(STYLE), help="for enhance-posterior")
    ap.add_argument("--op", choices=["denoise", "non-uniform"], default="denoise", help="likelihood for enhance-posterior")
    ap.add_argument("--star", help="RELION particle STAR (aniso / inpaint)")
    ap.add_argument("--mask", help="solvent mask on the input grid (adds --bbox)")
    ap.add_argument("--fmask-threshold", type=float, default=10.0)
    ap.add_argument("--nbands", type=int, default=64)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--no-bf16", action="store_true")
    ap.add_argument("--num-timesteps", type=int, default=200)
    ap.add_argument("--lamb-base", type=float, default=1000.0)
    ap.add_argument("--cfg-weight", type=float, help="override the style default (emhancer 2.0, emready 0.5)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--num-processes", type=int, help="multi-GPU via accelerate (written as --num_processes)")
    ap.add_argument("--log", action="store_true", default=True, help="add --log-file-path OUT/run.log (default on)")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--extra", default="", help="extra tokens appended verbatim, e.g. \"--debug --spectral-mixing\"")
    ap.add_argument("--no-check", action="store_true", help="skip header gates / existence checks")
    ap.add_argument("--sbatch", help="write a Slurm job file to this path (filled from templates/slurm_cfm.sbatch.template)")
    ap.add_argument("--account", help="--sbatch: Slurm account (else the <ACCOUNT> placeholder stays)")
    ap.add_argument("--partition", help="--sbatch: GPU partition (else <GPU_PARTITION> stays)")
    ap.add_argument("--cpus", help="--sbatch: CPUs for one GPU's share (example site: 18 per A100 40 GB, 16 per H100)")
    ap.add_argument("--mem", help="--sbatch: memory for one GPU's share (example site: 120G per A100, 160G per H100)")
    ap.add_argument("--time", default="01:00:00", help="--sbatch: walltime (default 01:00:00)")
    ap.add_argument("--node-tmp", default="/tmp", help="--sbatch: node-local scratch root for TMPDIR (default /tmp)")
    ap.add_argument("--site-env", default="", help="--sbatch: command that puts cfm on PATH inside the job, e.g. 'source /abs/activate.sh'")
    a = ap.parse_args(argv)
    notes = []
    likelihood = a.mode in ("denoise", "aniso", "nonuniform", "inpaint", "enhance-posterior")
    # model dir
    if a.mode in ("denoise", "aniso", "nonuniform", "inpaint"):
        variant = "cryofm2-pretrain"
    elif a.mode in ("emhancer", "emready"):
        variant = STYLE[a.mode]["dir"]
    else:
        if not a.style:
            die("enhance-posterior needs --style emhancer|emready")
        variant = STYLE[a.style]["dir"]
    if a.shorthand:
        model_dir = variant.replace("cryofm2-", "")
    elif a.models:
        if os.path.basename(a.models.rstrip("/")) in ("cryofm2-pretrain", "cryofm2-emhancer", "cryofm2-emready"):
            die("--models must be the PARENT folder of the variant folders, not a variant folder")
        model_dir = os.path.join(a.models, variant)
        if not a.no_check and os.path.isdir(a.models) and not (os.path.isfile(os.path.join(model_dir, "config.yaml")) and os.path.isfile(os.path.join(model_dir, "model.safetensors"))):
            die(f"{model_dir} lacks config.yaml + model.safetensors")
    else:
        die("give --models DIR (parent of the variant folders) or --shorthand (sites with a resolving launcher)")
    # inputs
    if a.mode in ("denoise", "aniso", "nonuniform", "inpaint", "enhance-posterior"):
        if not (a.half1 and a.half2):
            die(f"{a.mode} needs both half maps (--half1 --half2); with one map only `emhancer`/`emready` (style, no data term) is possible")
    if a.mode in ("emhancer", "emready") and not a.map:
        die(f"{a.mode} needs --map")
    if a.mode in ("emhancer", "emready") and (a.half1 or a.half2):
        die("style modes take --map only; for style + data term use enhance-posterior --style …")
    if a.mode in ("aniso", "inpaint") and not a.star:
        die(f"{a.mode} needs --star (RELION particle STAR with poses); without it `inpaint` fails inside starfile.read(None)")
    hs = {}
    for what, p in (("half1", a.half1), ("half2", a.half2), ("map", a.map)):
        if p:
            absolute(p, what, notes)
            if not a.no_check:
                hs[what] = check_map(p, what, notes, require_exists=False)
    if not a.no_check and hs.get("half1", (None,))[0] and hs.get("half2", (None,))[0]:
        g1, g2 = hs["half1"][1], hs["half2"][1]
        if g1["dims"] != g2["dims"]:
            die(f"half maps differ in box {g1['dims']} vs {g2['dims']} (ValueError 'All volumes must have the same shape')")
        if abs(g1["apix"] - g2["apix"]) > 0.005:
            warn(f"half-map pixel sizes differ ({g1['apix']:.4f} vs {g2['apix']:.4f}); cfm uses half1's", notes)
    if not a.no_check and hs.get("map", (None,))[0] and hs.get("half1", (None,))[0]:
        gm, g1 = hs["map"][1], hs["half1"][1]
        if gm["dims"] != g1["dims"] or abs(gm["apix"] - g1["apix"]) > 0.005:
            die(f"--map {gm['dims']} @ {gm['apix']:.4f} does not match half1 {g1['dims']} @ {g1['apix']:.4f} (cfm enhance checks this; EMDB primary maps often differ: use a half map as -i)")
    if a.star:
        absolute(a.star, "star", notes)
        if not a.star.lower().endswith(".star"):
            die("--star must be a .star file")
    if a.mask:
        absolute(a.mask, "mask", notes)
        if not a.no_check and os.path.exists(a.mask):
            hm = mh.read_header(a.mask)
            dims = (hm["nx"], hm["ny"], hm["nz"])
            if len(set(dims)) != 1:
                die(f"mask {dims} is not cubic: masks are not padded and fail the cubic assert")
            ref = hs.get("half1", (None,))[0] or hs.get("map", (None,))[0]
            if ref is not None and (ref["nx"], ref["ny"], ref["nz"]) != dims:
                die(f"mask box {dims} != input box {(ref['nx'], ref['ny'], ref['nz'])}: the mask must be on the input grid")
    absolute(a.out, "out", notes)
    if os.path.exists(a.out) and os.listdir(a.out):
        die(f"output dir {a.out} exists and is not empty: use a NEW directory (same stems overwrite silently)")
    if 1000 % a.num_timesteps:
        warn(f"--num-timesteps {a.num_timesteps} does not divide 1000: posterior paths integrate only {1000 // a.num_timesteps * a.num_timesteps / 1000:.2f} of the flow (use 50, 100, 125, 200, 250, 500)", notes)
    if a.num_timesteps > 1000:
        die("--num-timesteps > 1000 raises ValueError in FMScheduler")
    if a.batch_size < 1:
        die("--batch-size must be >= 1")
    # assemble
    sub = "denoise" if a.mode in ("denoise", "aniso", "nonuniform", "inpaint") else "enhance"
    cmd = ["cfm", sub]
    if a.num_processes:
        cmd += ["--num_processes", str(a.num_processes)]
        warn("multi-GPU splits patches only; per-GPU memory is unchanged; results may differ slightly; untested on the validated site", notes)
        if "--fsc-weighting" in a.extra:
            die("--fsc-weighting with --num_processes > 1 risks a barrier hang (03 §4)")
    if a.map:
        cmd += ["-i", a.map]
    if a.half1:
        cmd += ["-i1", a.half1, "-i2", a.half2]
    cmd += ["-o", a.out, "--model-dir", model_dir]
    if a.mode in ("emhancer", "emready", "enhance-posterior"):
        st = STYLE[a.mode if a.mode != "enhance-posterior" else a.style]
        cfg = a.cfg_weight if a.cfg_weight is not None else st["cfg"]
        cmd += ["--output-tag", str(st["tag"]), "--cfg-weight", repr(float(cfg))]
        if a.cfg_weight is not None:
            lo, hi = (1.5, 3.0) if st["tag"] == 1 else (0.3, 0.7)
            if not (lo <= a.cfg_weight <= hi):
                warn(f"--cfg-weight {a.cfg_weight} is outside the documented range {lo}-{hi} for this style", notes)
    if a.mode == "denoise":
        cmd += ["--op", "denoise"]
    elif a.mode == "aniso":
        cmd += ["--op", "denoise", "inpaint", "--data-starfile-path", a.star, "--fmask-threshold", repr(float(a.fmask_threshold))]
    elif a.mode == "inpaint":
        cmd += ["--op", "inpaint", "--data-starfile-path", a.star, "--fmask-threshold", repr(float(a.fmask_threshold))]
        warn("inpaint alone imposes the noisy observed coefficients exactly (no denoising); the λ flags are inert", notes)
    elif a.mode == "nonuniform":
        cmd += ["--op", "non-uniform", "--nbands", str(a.nbands)]
        warn("non-uniform needs ~64 MiB host RAM per patch per process; batch > 1 sums the weights over the batch", notes)
    elif a.mode == "enhance-posterior":
        cmd += ["--op", a.op]
        if a.op == "non-uniform":
            cmd += ["--nbands", str(a.nbands)]
    if likelihood:
        cmd += ["--norm-grad", "--use-lamb-w", "--lamb-base", repr(float(a.lamb_base))]
        if a.mode == "inpaint":
            pass
    if a.mask:
        cmd += ["--mask-path", a.mask, "--bbox"]
    if a.num_timesteps != 200:
        cmd += ["--num-timesteps", str(a.num_timesteps)]
    if a.batch_size != 4:
        cmd += ["--batch-size", str(a.batch_size)]
    if not a.no_bf16:
        cmd += ["--bf16"]
    if a.seed is not None:
        if sub == "enhance":
            warn("--seed is ignored by cfm enhance (no seeding on those paths)", notes)
        cmd += ["--seed", str(a.seed)]
    if not a.no_log:
        cmd += ["--log-file-path", os.path.join(a.out, "run.log")]
        notes.append("NOTE: --log-file-path needs the output dir to exist before the run (the job template creates it)")
    if a.extra:
        extra = shlex.split(a.extra)
        if "--op" in extra:
            die("do not pass --op in --extra: a second --op replaces the first (the quick-start trap)")
        if any(t in extra for t in ("--output-tag", "--cfg-weight")) and sub == "denoise":
            die("--output-tag/--cfg-weight are rejected by cfm denoise")
        cmd += extra
    # evidence level
    v = "VALIDATED on the example site (A100 40 GB, job 27772096, 2026-10-08; configs/site_config.example.md) — your host needs its own fixture run"
    validated = {"denoise": v, "emhancer": v, "emready": v}
    level = validated.get(a.mode, "UNTESTED on the validated site (static code reading only) — first run needs the user's explicit go-ahead and a small test")
    if a.mask or a.num_processes or (a.mode == "denoise" and a.extra):
        level = "UNTESTED combination on the validated site (mask/bbox, multi-GPU or extra flags were never run there)"
    # patches / walltime estimate
    est = None
    g = (hs.get("half1") or hs.get("map") or (None, None))[1]
    if g and g.get("patches"):
        halves = 2 if a.half1 and not a.map else 1
        import math
        batches = math.ceil(g["patches"] / a.batch_size) * halves
        steps_factor = a.num_timesteps / 200
        est = f"{g['patches']} patches -> {batches} batch(es) total at batch {a.batch_size}; ~{max(2, math.ceil(batches * 0.95 * steps_factor + 2))} min on an A100 (54 s per 4-patch batch at 200 steps measured)"
    def wrap(tokens, per_line=2):
        """group flag+value pairs (and bare flags) and put `per_line` groups on each continuation line"""
        groups, i = [], 0
        while i < len(tokens):
            t = tokens[i]
            if t.startswith("-") and i + 1 < len(tokens) and (not tokens[i + 1].startswith("-") or re.match(r"^-\d", tokens[i + 1])):
                j = i + 2
                while j < len(tokens) and not tokens[j].startswith("-"):   # nargs="+" values (--op denoise inpaint)
                    j += 1
                groups.append(tokens[i:j]); i = j
            else:
                groups.append([t]); i += 1
        lines, cur = [], []
        for g in groups:
            cur.append(" ".join(shlex.quote(x) for x in g))
            if len(cur) == per_line:
                lines.append(" ".join(cur)); cur = []
        if cur:
            lines.append(" ".join(cur))
        return " \\\n    ".join(lines)
    line = " ".join(shlex.quote(t) for t in cmd[:2]) + " \\\n    " + wrap(cmd[2:])
    print("# cryofm skill: generated command")
    print("# evidence level: " + level)
    if est:
        print("# sizing: " + est)
    for n in notes:
        print("# " + n)
    print(line)
    if a.sbatch:
        here = os.path.dirname(os.path.abspath(__file__))
        skill_dir = os.path.dirname(here)
        tpl = os.path.join(skill_dir, "templates", "slurm_cfm.sbatch.template")
        with open(tpl) as fh:
            txt = fh.read()
        fills = {"<ABS_INPUT_1>": a.half1 or a.map, "<ABS_INPUT_2>": a.half2 or "", "<SKILL_DIR>": skill_dir,
                 "<NODE_LOCAL_TMP>": a.node_tmp, "<JOB_NAME>": a.mode, "<TIME>": a.time}
        for ph, val in (("<ACCOUNT>", a.account), ("<GPU_PARTITION>", a.partition), ("<CPUS>", a.cpus), ("<MEM>", a.mem)):
            if val:
                fills[ph] = val
        for ph, val in fills.items():
            txt = txt.replace(ph, val)
        txt = txt.replace('MODEL="<MODELS>/cryofm2-pretrain"', "MODEL=" + shlex.quote(model_dir), 1)
        txt = re.sub(r'^OUT=.*$', "OUT=" + shlex.quote(a.out), txt, count=1, flags=re.M)
        if a.site_env:
            txt = txt.replace('SITE_ENV_CMD=""', "SITE_ENV_CMD=" + shlex.quote(a.site_env), 1)
        # swap the template's example command block for the generated command
        c0 = txt.index("# ---- the command")
        c1 = txt.index("rc=$?", c0)
        txt = txt[:c0] + "# ---- the command (generated by build_cfm_command.py; evidence level: " + level + ")\n" + line + "\n" + txt[c1:]
        txt = txt.replace("#SBATCH --export=NONE\n", "#SBATCH --export=NONE\n# generated by build_cfm_command.py -- review, then: sbatch --export=NONE " + a.sbatch + "\n", 1)
        with open(a.sbatch, "w") as fh:
            fh.write(txt)
        left = sorted(set(re.findall(r"<[A-Z_]+>", txt)))
        print(f"# wrote job file {a.sbatch} (review it; submit only with the user's go-ahead)")
        if left:
            print("# still to fill by hand: " + " ".join(left) + "  (the job refuses to run with placeholders in its settings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
