#!/usr/bin/env python3
"""Static validator for the deepemhancer skill package (v1.0 contract).

Read-only. Checks package integrity and the binding properties of an
**executing, config-first, confirmation-gated** skill:
  * required files exist; SKILL.md has valid frontmatter + the config-first rule
    + the five config states + the confirmation/no-upload safety language;
  * across EVERY packaged Markdown file: no raw install / model-download /
    scheduler / chmod command appears inside a code fence — those mutating
    commands live only in the reviewed, consent-gated scripts, never as
    copy-paste guidance;
  * the corrected spelling `--cleaningStrength` never appears as guidance
    (the real flag is the misspelled `--cleaningStrengh`);
  * CLI exact-spellings and phantom/stale flags are handled in the CLI reference;
  * PACKAGING HYGIENE (hard): no *.local.md, no __pycache__/, no *.pyc under the
    packageable tree — privacy is enforced by physical absence, not .gitignore;
  * the probe is structurally safe (no top-level TensorFlow import, no os.system,
    timeouts + CUDA_VISIBLE_DEVICES) and determine_state() returns the right
    state for synthetic facts (non-Linux uninstalled -> blocked; provisioned
    Linux -> ready);
  * the runner/install scripts carry their safety properties (the runner says it
    never uploads maps and sets the GPU-growth policy; the install script is
    consent-gated and does not download models unless asked) and the Python
    scripts compile.

Exit code 0 = all checks passed, 1 = at least one failure.
"""

import importlib.util
import os
import re
import sys

# Importing the probe module (section 7) would normally write
# scripts/__pycache__/*.pyc — exactly an artifact the hygiene checks forbid.
# Disable bytecode writing so validation never re-creates the caches it catches.
sys.dont_write_bytecode = True

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "SKILL.md",
    "references/00_scope_and_trust.md",
    "references/01_source_map.md",
    "references/02_config_session_and_environment.md",
    "references/03_cli_reference.md",
    "references/04_inputs_outputs_models.md",
    "references/05_workflow_templates.md",
    "references/06_troubleshooting_and_decision_trees.md",
    "references/07_cryosparc_hpc_integration.md",
    "references/08_validation_and_limits.md",
    "references/09_installation_and_runtime.md",
    "scripts/deepemhancer_env_probe.py",
    "scripts/run_deepemhancer.sh",
    "scripts/setup_deepemhancer_env.sh",
    "scripts/patch_keras_contrib.py",
    "configs/site_config.template.md",
    "tests/validate_static.py",
    "eval/eval_cases.md",
    "eval/reference_answers.md",
    "eval/trigger_tests.md",
    "lessons.md",
    ".gitignore",
]

ALL_MARKDOWN = [rel for rel in REQUIRED_FILES if rel.endswith(".md")]

# Mutating commands that must NEVER appear inside a Markdown code fence, even in
# an executing skill: installs, the model download, scheduler submission, and
# chmod belong in the reviewed, consent-gated scripts — not as pasteable docs.
HARD_FORBIDDEN_IN_FENCE = [
    "pip install",
    "conda install",
    "deepemhancer --download",
    "sbatch ",
    "cryosparcm ",
    "chmod ",
]

results = []  # (ok: bool, message: str)


def check(ok, message):
    results.append((bool(ok), message))


def read(rel):
    with open(os.path.join(SKILL_ROOT, rel), encoding="utf-8") as handle:
        return handle.read()


def iter_fences(text):
    """Yield each ``` code-fence body."""
    inside = False
    body = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if not inside:
                inside = True
                body = []
            else:
                inside = False
                yield "\n".join(body)
            continue
        if inside:
            body.append(line)


# --------------------------------------------------------------------------- #
# 1. Required files exist
# --------------------------------------------------------------------------- #
for rel in REQUIRED_FILES:
    check(os.path.isfile(os.path.join(SKILL_ROOT, rel)), "exists: %s" % rel)


# --------------------------------------------------------------------------- #
# 2. SKILL.md frontmatter + config-first rule + safety language
# --------------------------------------------------------------------------- #
skill = ""
try:
    skill = read("SKILL.md")
    fm = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
    check(fm is not None, "SKILL.md has YAML frontmatter block")
    if fm:
        front = fm.group(1)
        for key in ("name:", "description:", "version:"):
            check(key in front, "SKILL.md frontmatter has %s" % key)
        check("deepemhancer" in front.lower(),
              "SKILL.md description mentions DeepEMhancer")
        name_match = re.search(r"^name:\s*(\S+)", front, re.M)
        name = name_match.group(1) if name_match else ""
        # v1.0 uses the install-convention slug `deepemhancer` (no underscore),
        # so we can now enforce a hyphen-only slug.
        check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) is not None
              and "deepemhancer" in name,
              "SKILL.md name is a valid hyphen-slug containing 'deepemhancer' "
              "(got %r)" % name)
    low = skill.lower()
    check("config-first" in low, "SKILL.md states the config-first rule")
    check(("no current config" in low) or ("stale config" in low) or
          ("unknown" in low and "stale" in low),
          "SKILL.md first-response rule covers missing/stale config")
    for state in ("ready", "partial", "blocked", "unknown", "stale"):
        check(state in low, "SKILL.md documents state '%s'" % state)
    # Executing-skill safety contract: confirmation before mutating actions, and
    # the permanent no-upload/no-move rule on map data.
    check("confirm before" in low,
          "SKILL.md requires confirmation before mutating/heavyweight actions")
    check(all(w in low for w in ("install", "model download", "map run")),
          "SKILL.md enumerates the confirm-gated actions (install / model download / map run)")
    check(re.search(r"never\b.*\b(upload|copy|move|delete)", low) is not None,
          "SKILL.md states it never uploads/copies/moves/deletes user maps")
except Exception as exc:  # noqa
    check(False, "SKILL.md readable: %s" % exc)


# --------------------------------------------------------------------------- #
# 3. Forbidden-command absence in fences + global flag-spelling guard
#    (across ALL packaged Markdown).
# --------------------------------------------------------------------------- #
for rel in ALL_MARKDOWN:
    text = read(rel)
    for body in iter_fences(text):
        for bad in HARD_FORBIDDEN_IN_FENCE:
            check(bad not in body,
                  "%s: no forbidden command '%s' inside a code fence "
                  "(use the consent-gated scripts instead)" % (rel, bad.strip()))
    # The corrected/wrong spelling `--cleaningStrength` may appear ONLY on a line
    # that also shows the real misspelling `--cleaningStrengh` (a wrong-vs-right
    # contrast, e.g. the fail-condition example in reference_answers.md).
    for lineno, line in enumerate(text.splitlines(), 1):
        if "--cleaningStrength" in line and "--cleaningStrengh" not in line:
            check(False,
                  "%s:%d uses corrected spelling --cleaningStrength outside a "
                  "wrong-vs-right contrast (real flag is --cleaningStrengh)"
                  % (rel, lineno))


# --------------------------------------------------------------------------- #
# 4. CLI reference exact-spelling + phantom/stale flags
# --------------------------------------------------------------------------- #
cli = read("references/03_cli_reference.md")
check("--cleaningStrengh" in cli,
      "CLI ref uses exact misspelled flag --cleaningStrengh")
check("--cleaningStrength" not in cli,
      "CLI ref does NOT use the corrected spelling --cleaningStrength")
check("--deepLearningModelPath" in cli, "CLI ref has real flag --deepLearningModelPath")
for phantom in ("--deepLearningModelDir", "--precomputedModel"):
    check(phantom in cli, "CLI ref surfaces phantom/stale flag %s" % phantom)
# `-c` is only two chars; require it to be documented AS a phantom (same line),
# not just any incidental occurrence (e.g. `conda -c conda-forge`).
check(any("-c" in ln and re.search(r"phantom|no such option|not defined|not real", ln, re.I)
          for ln in cli.splitlines()),
      "CLI ref documents `-c` as a phantom (not an incidental occurrence)")
# Defaults/semantics most likely to be mis-paraphrased into a wrong command.
check("--batch_size" in cli and "`8`" in cli,
      "CLI ref documents -b/--batch_size default 8")
check("--gpuIds" in cli and re.search(r'`"0"`', cli) is not None
      and re.search(r"-1.{0,16}CPU", cli, re.I) is not None,
      'CLI ref documents -g default "0" and -g -1 = CPU')
check(re.search(r"-p option should not be provided", cli) is not None,
      "CLI ref documents the forced-tightTarget assertion(s)")
check(re.search(r"--deepLearningModelDir[^\n]*(stale|NOT real|not real|never)",
                cli, re.I) is not None
      or re.search(r"(stale|NOT real|not real)[^\n]*--deepLearningModelDir", cli, re.I)
      is not None,
      "CLI ref marks --deepLearningModelDir as stale/not-real")
check("961f028ca609017990de4473ab368cf1787e8282" in cli,
      "CLI ref cites the pinned commit")


# --------------------------------------------------------------------------- #
# 5. Local-config exclusion (privacy/packaging)
# --------------------------------------------------------------------------- #
gitignore = read(".gitignore")
check("configs/site_config.local.md" in gitignore,
      ".gitignore excludes configs/site_config.local.md")
template = read("configs/site_config.template.md")
check("site_config.local.md" in template and
      re.search(r"never (packaged|commit)|git-ignored|not.*package", template, re.I)
      is not None,
      "template states local config is private/never packaged")
cfg_ref = read("references/02_config_session_and_environment.md")
check("site_config.local.md" in cfg_ref and
      re.search(r"never packaged|git-ignored|gitignore|not.*packag", cfg_ref, re.I)
      is not None,
      "references/02 states local config is git-ignored/never packaged")
check("site_config.local.md" in skill,
      "SKILL.md mentions the private local config")


# --------------------------------------------------------------------------- #
# 5b. Packaging hygiene — HARD enforcement (privacy by physical absence).
# --------------------------------------------------------------------------- #
local_md_hits, pycache_dir_hits, pyc_file_hits = [], [], []
for dirpath, dirnames, filenames in os.walk(SKILL_ROOT):
    for dname in dirnames:
        if dname == "__pycache__":
            pycache_dir_hits.append(
                os.path.relpath(os.path.join(dirpath, dname), SKILL_ROOT))
    for fname in filenames:
        rel_hit = os.path.relpath(os.path.join(dirpath, fname), SKILL_ROOT)
        if fname.endswith(".local.md"):
            local_md_hits.append(rel_hit)
        if fname.endswith(".pyc"):
            pyc_file_hits.append(rel_hit)

check(not local_md_hits,
      "no *.local.md in packageable tree (found: %s)"
      % (", ".join(sorted(local_md_hits)) or "none"))
check(not pycache_dir_hits,
      "no __pycache__/ in packageable tree (found: %s)"
      % (", ".join(sorted(pycache_dir_hits)) or "none"))
check(not pyc_file_hits,
      "no *.pyc in packageable tree (found: %s)"
      % (", ".join(sorted(pyc_file_hits)) or "none"))
check(not os.path.isfile(os.path.join(SKILL_ROOT, "configs", "site_config.local.md")),
      "configs/site_config.local.md is absent from the packageable tree")
check(os.path.isfile(os.path.join(SKILL_ROOT, "configs", "site_config.template.md")),
      "configs/site_config.template.md present (the only config that ships)")


# --------------------------------------------------------------------------- #
# 6. Probe structural safety (still read-only by default)
# --------------------------------------------------------------------------- #
probe_src = read("scripts/deepemhancer_env_probe.py")
check(re.search(r"^\s*import tensorflow", probe_src, re.M) is None,
      "probe has NO top-level `import tensorflow`")
check("os.system(" not in probe_src, "probe does not use os.system")
check("shell=True" not in probe_src, "probe does not use shell=True subprocesses")
check("timeout=" in probe_src, "probe passes timeout= to subprocesses")
check("CUDA_VISIBLE_DEVICES" in probe_src,
      "probe sets CUDA_VISIBLE_DEVICES for live calls")
check("def determine_state" in probe_src, "probe defines determine_state()")
check("def build_report" in probe_src, "probe defines build_report()")
check(("importlib.metadata" in probe_src) or ("import importlib.metadata" in probe_src),
      "probe prefers importlib.metadata for version")
check("nvidia-smi" in probe_src, "probe prefers nvidia-smi for GPU")
check("deepemhancer --download" not in probe_src,
      "probe never invokes the model-download flag")


# --------------------------------------------------------------------------- #
# 7. determine_state() semantics (import the probe module)
# --------------------------------------------------------------------------- #
def load_probe():
    path = os.path.join(SKILL_ROOT, "scripts", "deepemhancer_env_probe.py")
    spec = importlib.util.spec_from_file_location("deepemhancer_env_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def facts(is_linux, have_pkg, have_exe, gpu_count, tf_state, models_ok,
          live_ok=None, model_is_file=False):
    files = {
        "deepEMhancer_tightTarget.hd5": models_ok,
        "deepEMhancer_wideTarget.hd5": models_ok,
        "deepEMhancer_highRes.hd5": models_ok,
        "deepEMhancer_masked.hd5": models_ok,
    }
    live = {"requested": live_ok is not None}
    if live_ok is not None:
        code = 0 if live_ok else 1
        live["version"] = {"exit_code": code, "timed_out": False}
        live["help"] = {"exit_code": code, "timed_out": False}
    return {
        "host_identity": {"os_system": "Linux" if is_linux else "Darwin",
                          "is_linux": is_linux, "machine": "x86_64"},
        "deepemhancer_package": {"found": have_pkg},
        "deepemhancer_executable": {"exists": have_exe},
        "gpu_cuda": {"present": gpu_count > 0, "gpu_count": gpu_count},
        "models": {
            "all_required_present": models_ok,
            "checked_dir_is_file": model_is_file,
            "checked_dir": "~/models" if (models_ok or model_is_file) else None,
            "gating_file_present": models_ok or model_is_file,
            "default_model_dir": "~/.local/share/deepEMhancerModels/production_checkpoints",
            "files_present": files,
            "missing_required": [] if models_ok else ["deepEMhancer_tightTarget.hd5"],
        },
        "tensorflow": {"state": tf_state},
        "live_help": live,
    }


try:
    probe = load_probe()
    state, _ = probe.determine_state(
        facts(is_linux=False, have_pkg=False, have_exe=False, gpu_count=0,
              tf_state="not_run", models_ok=False))
    check(state == "blocked", "determine_state: non-Linux/uninstalled -> blocked (got %s)" % state)

    state, _ = probe.determine_state(
        facts(is_linux=True, have_pkg=True, have_exe=True, gpu_count=1,
              tf_state="ok", models_ok=True, live_ok=True))
    check(state == "ready", "determine_state: provisioned Linux host -> ready (got %s)" % state)

    state, _ = probe.determine_state(
        facts(is_linux=True, have_pkg=True, have_exe=True, gpu_count=0,
              tf_state="not_run", models_ok=True))
    check(state == "partial", "determine_state: untested runtime -> partial (got %s)" % state)

    state, _ = probe.determine_state(
        facts(is_linux=True, have_pkg=True, have_exe=True, gpu_count=1,
              tf_state="ok", models_ok=False))
    check(state == "blocked", "determine_state: missing models -> blocked (got %s)" % state)

    state, _ = probe.determine_state(
        facts(is_linux=True, have_pkg=True, have_exe=True, gpu_count=1,
              tf_state="failed", models_ok=True))
    check(state == "blocked", "determine_state: TF failure -> blocked (got %s)" % state)

    # Missing host identity -> unknown.
    f_unknown = facts(is_linux=True, have_pkg=True, have_exe=True, gpu_count=1,
                      tf_state="ok", models_ok=True, live_ok=True)
    f_unknown["host_identity"]["os_system"] = ""
    state, _ = probe.determine_state(f_unknown)
    check(state == "unknown", "determine_state: missing host OS -> unknown (got %s)" % state)

    # A freshly computed report must NEVER emit 'stale' (a skill-level judgement).
    for f_ in (facts(False, False, False, 0, "not_run", False),
               facts(True, True, True, 1, "ok", True, live_ok=True),
               facts(True, True, True, 0, "not_run", True),
               facts(True, True, True, 1, "failed", True)):
        s_, _ = probe.determine_state(f_)
        check(s_ != "stale", "determine_state never emits 'stale' (got %s)" % s_)
except Exception as exc:  # noqa
    check(False, "determine_state semantic checks ran: %s" % exc)


# --------------------------------------------------------------------------- #
# 8. No-quantitative-generalization + heavyweight + Apache + CryoSPARC notes
# --------------------------------------------------------------------------- #
limits = read("references/08_validation_and_limits.md")
check(re.search(r"(?:not|never)[\s\*]*generaliz|no quantitative generaliz",
                limits, re.I) is not None,
      "validation ref forbids generalizing paper benchmarks")
scope = read("references/00_scope_and_trust.md")
check("Apache" in scope, "scope ref states Apache 2.0 license")
check(re.search(r"heavyweight", scope, re.I) is not None,
      "scope ref carries the heavyweight-call warning")
check(re.search(r"never\b.*\b(upload|move|delete|transmit)", scope, re.I) is not None,
      "scope ref states the never-touch-map-data rule")
cryo = read("references/07_cryosparc_hpc_integration.md")
check(re.search(r"separate.*conda|conda.*separate", cryo, re.I) is not None,
      "cryosparc ref warns about separate conda env")
check(re.search(r"path.*symmetr|same.*path.*(master|worker)", cryo, re.I) is not None,
      "cryosparc ref warns about master/worker path symmetry")


# --------------------------------------------------------------------------- #
# 9. Executing-skill scripts carry their safety properties
# --------------------------------------------------------------------------- #
runner = read("scripts/run_deepemhancer.sh")
check(re.search(r"never\b.*\b(upload|copy|move|delete)", runner, re.I) is not None,
      "run_deepemhancer.sh documents that it never uploads/moves map data")
check("TF_FORCE_GPU_ALLOW_GROWTH" in runner,
      "run_deepemhancer.sh sets the GPU-memory-growth policy")
check("deepemhancer" in runner and ("exec " in runner),
      "run_deepemhancer.sh execs deepemhancer with the passed args")

setup = read("scripts/setup_deepemhancer_env.sh")
check(("--yes" in setup) and re.search(r"read\s+-r?\s*-p|Proceed\?", setup) is not None,
      "setup script is consent-gated (interactive prompt + --yes)")
# Enforcement, not token presence: a non-affirmative answer must actually abort.
check(re.search(r"\|\|\s*\{[^}]*(Aborted|exit)", setup) is not None,
      "setup aborts on a non-affirmative answer (|| { ... exit })")
# The model download must sit inside the DOWNLOAD_MODELS guard. Its executable
# call comes AFTER the guard; the only earlier mention is the help comment.
_guard = setup.find('"$DOWNLOAD_MODELS" -eq 1')
_dl_call = setup.rfind("deepemhancer --download")
check(_guard != -1 and _dl_call != -1 and _dl_call > _guard,
      "setup runs `deepemhancer --download` only inside the DOWNLOAD_MODELS guard")
check(re.search(r"DOWNLOAD_MODELS=0", setup) is not None and
      "--download-models" in setup,
      "setup defaults to no model download unless --download-models is given")

# Behavioral guard for the load-bearing invariant: the EXECUTING scripts must
# process maps in place and never transmit/copy/move/delete data. Scan both for
# outbound-transfer/destructive verbs (word-boundary, to avoid matching e.g.
# "perform"). The model-weights download is allowlisted (not map data).
for rel in ("scripts/run_deepemhancer.sh", "scripts/setup_deepemhancer_env.sh"):
    scan = read(rel).replace("deepemhancer --download", "")
    for verb in (r"\bscp\b", r"\bsftp\b", r"\brsync\b", r"\bcurl\b", r"\bwget\b",
                 r"\brclone\b", r"\bnc\b", r"(?<![\w-])cp\s", r"(?<![\w-])mv\s",
                 r"(?<![\w-])rm\s"):
        check(re.search(verb, scan) is None,
              "%s: no outbound-transfer/destructive verb /%s/ (maps processed in place)"
              % (rel, verb))

# Python scripts compile.
for rel in ("scripts/deepemhancer_env_probe.py", "scripts/patch_keras_contrib.py",
            "tests/validate_static.py"):
    try:
        compile(read(rel), rel, "exec")
        check(True, "compiles: %s" % rel)
    except SyntaxError as exc:
        check(False, "compiles: %s (%s)" % (rel, exc))

# The patch helper is idempotent (re-runnable without harm).
patch = read("scripts/patch_keras_contrib.py")
check(re.search(r"idempotent|Already patched", patch, re.I) is not None,
      "patch_keras_contrib.py is idempotent")


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
passed = sum(1 for ok, _ in results if ok)
failed = [msg for ok, msg in results if not ok]

print("validate_static.py — deepemhancer skill (v1.0)")
print("passed: %d / %d" % (passed, len(results)))
if failed:
    print("\nFAILURES:")
    for msg in failed:
        print("  [FAIL] %s" % msg)
    sys.exit(1)
print("ALL CHECKS PASSED")
sys.exit(0)
