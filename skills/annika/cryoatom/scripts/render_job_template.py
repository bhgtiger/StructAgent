#!/usr/bin/env python3
"""Fill a {{PLACEHOLDER}} job template from the site config.

  python3 render_job_template.py templates/run_cryoatom.sbatch.template \
      --set MAP=/data/map.mrc --set OUTPUT_DIR=/scratch/$USER/run_2026 \
      --output ~/run_cryoatom.sbatch

Values come from the site config (see --config resolution below), overridden by
--set KEY=VALUE. Placeholders that cannot be resolved are LEFT IN PLACE and
listed on stderr, so an unfinished job script is obvious rather than silently
wrong. --strict turns that into a non-zero exit.

A template may declare which placeholders are allowed to stay empty with a line

    # render-optional: PROTEIN_FASTA RNA_FASTA DNA_FASTA

Those resolve to an empty string when nothing supplies them, and never fail
--strict.

Config resolution: --config, else $CRYOATOM_SKILL_CONFIG, else
${XDG_CONFIG_HOME:-~/.config}/cryoatom-skill/site-config.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
OPTIONAL_DIRECTIVE = re.compile(r"^\s*#\s*render-optional:\s*(.+)$", re.MULTILINE)
SCHEDULER_DIRECTIVE = re.compile(r"^\s*#\s*render-scheduler:\s*(\S+)", re.MULTILINE)


def template_scheduler(text):
    """The scheduler a template's directives are written for, if it declares one."""
    match = SCHEDULER_DIRECTIVE.search(text)
    return match.group(1).strip().lower() if match else None


def optional_keys(text):
    """Keys a template declares as safe to leave empty."""
    keys = set()
    for match in OPTIONAL_DIRECTIVE.finditer(text):
        keys.update(k.strip() for k in match.group(1).replace(",", " ").split())
    return keys


def config_path(explicit=None):
    if explicit:
        return os.path.expanduser(explicit)
    env = os.environ.get("CRYOATOM_SKILL_CONFIG")
    if env:
        return os.path.expanduser(env)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(base, "cryoatom-skill", "site-config.json")


def mapping_from_config(cfg):
    """Site config -> template variables. Only non-empty values are offered."""
    inst = cfg.get("install") or {}
    sched = cfg.get("scheduler") or {}
    paths = cfg.get("paths") or {}
    weights = cfg.get("weights") or {}
    version = cfg.get("version") or {}
    raw = {
        "PROFILE": cfg.get("profile"),
        "ACCOUNT": sched.get("account"),
        "GPU_PARTITION": sched.get("gpu_partition"),
        "BUILD_PARTITION": sched.get("build_partition") or sched.get("gpu_partition"),
        "GPU_FLAG": sched.get("gpu_flag"),
        "CPUS_PER_TASK": sched.get("cpus_per_task"),
        "MEMORY_GB": sched.get("memory_gb"),
        "WALLTIME": sched.get("default_time"),
        "SCHEDULER_TYPE": sched.get("type"),
        "SCRATCH_ROOT": sched.get("scratch_root"),
        "RESULTS_ROOT": paths.get("results_root") or sched.get("scratch_root"),
        "LOG_DIR": paths.get("log_dir"),
        "FIXTURE_DIR": paths.get("fixture_dir"),
        "BUILD_TMP_ROOT": paths.get("build_tmp_root") or sched.get("scratch_root"),
        "LAUNCHER": inst.get("launcher"),
        "IMAGE_PATH": inst.get("image_path"),
        "CONTAINER_RUNTIME": inst.get("container_runtime"),
        "WEIGHTS_CACHE": weights.get("cache_root"),
        "EXPECTED_VERSION": version.get("expected"),
        "EXTRA_DIRECTIVES": "\n".join(sched.get("extra_directives") or []),
    }
    return {k: str(v) for k, v in raw.items() if v not in (None, "")}


def render(text, mapping):
    """Return (rendered_text, required_missing, optional_blank)."""
    optional = optional_keys(text)
    missing, blanked = [], []

    def sub(match):
        key = match.group(1)
        if key in mapping:
            return mapping[key]
        if key in optional:
            blanked.append(key)
            return ""
        missing.append(key)
        return match.group(0)

    return PLACEHOLDER.sub(sub, text), sorted(set(missing)), sorted(set(blanked))


def self_test():
    failures = []
    text = ("# render-optional: EXTRA\n#SBATCH -A {{ACCOUNT}}\n"
            "#SBATCH -p {{GPU_PARTITION}}\nmap={{MAP}}\nextra={{EXTRA}}\n")
    out, missing, blanked = render(text, {"ACCOUNT": "acct1", "GPU_PARTITION": "gpu"})
    if "acct1" not in out or "-p gpu" not in out:
        failures.append("substitution failed")
    if missing != ["MAP"]:
        failures.append("expected MAP to be reported missing, got %s" % missing)
    if template_scheduler("# render-scheduler: slurm\n") != "slurm":
        failures.append("scheduler directive not parsed")
    if template_scheduler("nothing here") is not None:
        failures.append("absent scheduler directive must be None")
    if blanked != ["EXTRA"] or "extra=\n" not in out:
        failures.append("declared-optional placeholder must resolve to empty, got %s" % blanked)
    if "{{MAP}}" not in out:
        failures.append("unresolved required placeholders must stay visible")
    cfg = {"profile": "p", "scheduler": {"account": "a", "gpu_partition": "g",
                                         "cpus_per_task": 18, "memory_gb": None},
           "install": {"launcher": "/bin/true"}, "weights": {"cache_root": "/c"},
           "paths": {}, "version": {"expected": "2.1.1"}}
    m = mapping_from_config(cfg)
    if m.get("CPUS_PER_TASK") != "18" or "MEMORY_GB" in m:
        failures.append("config mapping must stringify values and drop empty ones")
    if m.get("RESULTS_ROOT") is not None and "RESULTS_ROOT" in m:
        failures.append("RESULTS_ROOT must stay unset when neither source has a value")
    print(json.dumps({"self_test": "ok" if not failures else "failed",
                      "failures": failures}, indent=2))
    return 0 if not failures else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", nargs="?", help="template file with {{PLACEHOLDER}} tokens")
    ap.add_argument("--config", help="site config path")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override or supply a value (repeatable)")
    ap.add_argument("--output", help="write here (default: stdout)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on an unresolved placeholder or a scheduler mismatch")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.template:
        ap.error("template is required")

    mapping = {}
    path = config_path(args.config)
    if os.path.isfile(path):
        try:
            with open(path) as fh:
                mapping.update(mapping_from_config(json.load(fh)))
        except (OSError, ValueError) as exc:
            print("warning: could not read site config %s: %s" % (path, exc),
                  file=sys.stderr)
    else:
        print("warning: no site config at %s; only --set values will resolve" % path,
              file=sys.stderr)

    for item in args.set:
        if "=" not in item:
            ap.error("--set expects KEY=VALUE, got %r" % item)
        key, value = item.split("=", 1)
        mapping[key.strip()] = value

    with open(args.template) as fh:
        text = fh.read()

    # A Slurm template filled with a site's PBS/LSF values is not a job script.
    want_sched = template_scheduler(text)
    have_sched = (mapping.get("SCHEDULER_TYPE") or "").lower()
    if want_sched and have_sched and want_sched != have_sched:
        print("SCHEDULER MISMATCH: this template is written for %s, but the site config "
              "says %s. Its directives will not work as written — port them "
              "(references/02_install_routes.md ~ Non-Slurm schedulers) before submitting."
              % (want_sched, have_sched), file=sys.stderr)
        if args.strict:
            return 4

    rendered, missing, blanked = render(text, mapping)

    if args.output:
        out = os.path.expanduser(args.output)
        if os.path.exists(out) and not args.force:
            print("refusing to overwrite %s (use --force)" % out, file=sys.stderr)
            return 2
        with open(out, "w") as fh:
            fh.write(rendered)
        print("wrote %s" % out, file=sys.stderr)
    else:
        sys.stdout.write(rendered)

    if blanked:
        print("optional placeholders left empty: %s" % ", ".join(blanked), file=sys.stderr)
    if missing:
        print("UNRESOLVED placeholders (fill them in before submitting): %s"
              % ", ".join(missing), file=sys.stderr)
        return 3 if args.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
