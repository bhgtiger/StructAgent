#!/usr/bin/env python3
"""Static self-check for the openfold3 skill package (stdlib only, Python >= 3.9; no OpenFold3 needed).

Checks structure and hygiene, not model behaviour:
  files       required package files exist; no __pycache__ / *.pyc left in the package
  frontmatter SKILL.md keys, name == folder name (hyphen-case), description length and characters,
              agents/openai.yaml name; SKILL.md line count
  references  every references/*.md is routed from SKILL.md and stays under --max-ref-lines
  links       every relative markdown link in every .md file resolves inside the package
  paths       every package path in code spans and code blocks (references/, scripts/, templates/, configs/,
              evals/, tests/, agents/) and every bare reference file name (NN_name.md) resolves
  json        every *.json parses; query templates have a "queries" object
  scripts     py_compile (into a temporary directory), Python 3.9 grammar, stdlib-only imports, `--help` exits 0
  queries     scripts/make_query.py --validate --no-path-check passes on every templates/queries/*.json
  sbatch      `bash -n` on every templates/*.sbatch.template
  evals       evals/evals.json schema; one reference answer per eval; trigger lists present
  privacy     generic patterns (home paths, cluster file-system roots, e-mail addresses, private IPv4, secrets)
              plus the optional --deny-file tokens, over every file's content and path

The public validator carries no private strings. Site- or person-specific tokens go in a deny-file kept OUTSIDE the
package, one per line: a plain line is a case-insensitive substring; `word:TOKEN` matches TOKEN as a whole word;
`re:PATTERN` is a case-insensitive regular expression; blank lines and lines starting with '#' are ignored.

Usage:
  python3 tests/validate_static.py [--root DIR] [--deny-file FILE] [--max-ref-lines N] [--no-exec] [--json]
Exit: 0 all checks passed (warnings allowed), 1 at least one failure, 2 usage error.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import glob
import importlib.util
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER = {"name", "description", "homepage", "license", "allowed-tools", "user-invocable", "metadata"}
DESC_MIN, DESC_MAX = 100, 1024
SKILL_MD_MAX_LINES = 500
DEFAULT_MAX_REF_LINES = 320
MIN_TRIGGER_ITEMS = 5
MIN_EVALS_WARN = 10

REQUIRED_FILES = [
    "SKILL.md", "lessons.md", "agents/openai.yaml",
    "configs/site_config.template.md", "configs/site_config.example.md",
    "references/00_scope_and_trust.md", "references/01_source_map.md",
    "references/02_install_and_environment.md", "references/03_cli_reference.md",
    "references/04_input_query_format.md", "references/05_core_workflows.md",
    "references/06_kit_modes_and_multigpu.md", "references/07_msa_templates_weights.md",
    "references/08_outputs_and_confidence.md", "references/09_validation_and_benchmarks.md",
    "references/10_troubleshooting.md", "references/11_decision_trees.md", "references/maintenance.md",
    "scripts/openfold3_env_probe.py", "scripts/make_query.py", "scripts/summarize_openfold3_output.py",
    "templates/slurm_predict.sbatch.template", "templates/queries/README.md",
    "evals/evals.json", "evals/reference_answers.md", "tests/trigger_tests.md", "tests/validate_static.py",
]

# Package directories whose paths are checked when they appear in code spans or code blocks.
PACKAGE_DIRS = ("references", "scripts", "templates", "configs", "evals", "tests", "agents")
# Paths that look like package paths but belong to upstream OpenFold3 or the kit (documented, not shipped here).
EXTERNAL_PREFIXES = ("scripts/snakemake_msa/", "scripts/data_preprocessing/")
EXTERNAL_SUFFIXES = (".env",)          # configs/<card>.env are kit card files
# Files that are git-ignored by design: mentioned in the docs, never shipped.
LOCAL_ONLY = ("configs/site_config.local.md",)
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}

PATH_TOKEN_RE = re.compile(r"(?<![\w./~$-])((?:%s)/(?:[^\s`'\"()\[\],;|{}]|\{[^{}\s`]*\})*)" % "|".join(PACKAGE_DIRS))
BARE_REF_RE = re.compile(r"(?<![\w./-])(\d\d_[a-z0-9_]+\.md|maintenance\.md)(?![\w-])")
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
FENCE_RE = re.compile(r"^(\s*)(```|~~~)")


def _alt(*words):
    return "(?:" + "|".join(words) + ")"


# Generic privacy patterns. Built from fragments so this file never contains the literal strings it hunts for.
GENERIC_PRIVACY = [
    ("home directory path", re.compile(r"(?<![\w.-])/" + _alt("ho" + "me", "Us" + "ers") + r"/")),
    ("cluster file-system root", re.compile(r"(?<![\w.-])/" + _alt("gp" + "fs", "lus" + "tre", "scr" + "atch") + r"(?![A-Za-z])")),
    ("e-mail address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")),
    ("private IPv4 address", re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")),
    ("private key block", re.compile("-----BEGIN " + r"(?:[A-Z]+ )*" + "PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("AWS access key id", re.compile(r"\bAK" + r"IA[0-9A-Z]{16}\b")),
    ("API secret key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b")),
    ("Slurm job output file", re.compile(r"\bslurm-\d{5,}\.out\b")),
]
EMAIL_ALLOWED_DOMAINS = ("example.com", "example.org", "example.net")


class Report:
    def __init__(self):
        self.results = []

    def add(self, status, check, message):
        self.results.append({"status": status, "check": check, "message": message})

    def ok(self, check, message):
        self.add("PASS", check, message)

    def warn(self, check, message):
        self.add("WARN", check, message)

    def fail(self, check, message):
        self.add("FAIL", check, message)

    def count(self, status):
        return sum(1 for r in self.results if r["status"] == status)


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def scrub(text, root):
    """Make subprocess output package-relative so reports can be shared without local paths."""
    for base in {os.path.realpath(root), os.path.abspath(root)}:
        text = text.replace(base + os.sep, "").replace(base, ".")
    return text


def bytecode_files(root):
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        out.update(rel(root, os.path.join(dirpath, f)) for f in filenames if f.endswith((".pyc", ".pyo")))
    return out


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def walk_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def is_binary(path):
    """True for files that are not UTF-8 text (whole file read: package files are small)."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return True
    if b"\0" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


# ----------------------------------------------------------------------------------------------- frontmatter --
def parse_frontmatter(text):
    """Return (dict, error). Minimal YAML subset: key: value, quoted values, and block scalars (> >- | |-)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "SKILL.md does not start with a '---' frontmatter line"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter is not closed by a second '---' line"
    data, key, style, buf = {}, None, None, []

    def flush():
        if key is not None and style is not None:
            data[key] = ("\n" if style.startswith("|") else " ").join(buf).strip()

    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1].isspace():
            if key is None:
                return None, "indented frontmatter line before any key"
            if style is None:  # plain multi-line scalar
                data[key] = (data[key] + " " + raw.strip()).strip()
            else:
                buf.append(raw.strip())
            continue
        flush()
        if ":" not in raw:
            return None, "frontmatter line without a key: %r" % raw
        k, v = raw.split(":", 1)
        key, v = k.strip(), v.strip()
        style, buf = None, []
        if v in (">", ">-", ">+", "|", "|-", "|+"):
            style = v
            data[key] = ""
        else:
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            data[key] = v
    flush()
    return data, None


def check_frontmatter(root, rep):
    path = os.path.join(root, "SKILL.md")
    if not os.path.isfile(path):
        return ""
    text = read_text(path)
    fm, err = parse_frontmatter(text)
    if err:
        rep.fail("frontmatter", err)
        return text
    extra = sorted(set(fm) - ALLOWED_FRONTMATTER)
    if extra:
        rep.fail("frontmatter", "unexpected key(s): %s (allowed: %s)" % (", ".join(extra), ", ".join(sorted(ALLOWED_FRONTMATTER))))
    folder = os.path.basename(os.path.normpath(root))
    name = fm.get("name", "")
    if not name:
        rep.fail("frontmatter", "missing name")
    elif not SKILL_NAME_RE.match(name) or len(name) > 64:
        rep.fail("frontmatter", "name %r is not hyphen-case (a-z, 0-9, single hyphens, <= 64 chars)" % name)
    elif name != folder:
        rep.fail("frontmatter", "name %r != folder name %r" % (name, folder))
    else:
        rep.ok("frontmatter", "name %r == folder name" % name)
    desc = fm.get("description", "")
    if not desc:
        rep.fail("frontmatter", "missing or empty description")
    else:
        if len(desc) > DESC_MAX:
            rep.fail("frontmatter", "description is %d chars (max %d)" % (len(desc), DESC_MAX))
        elif len(desc) < DESC_MIN:
            rep.warn("frontmatter", "description is only %d chars; it may not trigger reliably" % len(desc))
        else:
            rep.ok("frontmatter", "description length %d/%d chars" % (len(desc), DESC_MAX))
        if "<" in desc or ">" in desc:
            rep.fail("frontmatter", "description contains angle brackets")
    n_lines = len(text.splitlines())
    if n_lines > SKILL_MD_MAX_LINES:
        rep.fail("frontmatter", "SKILL.md has %d lines (max %d)" % (n_lines, SKILL_MD_MAX_LINES))
    else:
        rep.ok("frontmatter", "SKILL.md %d lines (max %d)" % (n_lines, SKILL_MD_MAX_LINES))
    agents = os.path.join(root, "agents", "openai.yaml")
    if os.path.isfile(agents):
        m = re.search(r"^name:\s*['\"]?([^'\"\s#]+)", read_text(agents), re.M)
        if not m:
            rep.fail("frontmatter", "agents/openai.yaml has no top-level name")
        elif m.group(1) != folder:
            rep.fail("frontmatter", "agents/openai.yaml name %r != folder name %r" % (m.group(1), folder))
        else:
            rep.ok("frontmatter", "agents/openai.yaml name matches")
    return text


# ------------------------------------------------------------------------------------------ files, references --
def check_required(root, rep):
    missing = [p for p in REQUIRED_FILES if not os.path.isfile(os.path.join(root, p))]
    for p in missing:
        rep.fail("files", "missing required file %s" % p)
    if not missing:
        rep.ok("files", "all %d required files present" % len(REQUIRED_FILES))
    junk = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        junk += [rel(root, os.path.join(dirpath, d)) + "/" for d in dirnames if d == "__pycache__"]
        junk += [rel(root, os.path.join(dirpath, f)) for f in filenames if f.endswith((".pyc", ".pyo"))]
    if junk:
        rep.fail("files", "bytecode left in the package: %s" % ", ".join(sorted(junk)[:10]))
    else:
        rep.ok("files", "no __pycache__ or *.pyc in the package")


def check_references(root, skill_text, max_lines, rep):
    refs = sorted(glob.glob(os.path.join(root, "references", "*.md")))
    if not refs:
        rep.fail("references", "no references/*.md found")
        return
    bad = 0
    for path in refs:
        r = rel(root, path)
        if r not in skill_text:
            rep.fail("references", "%s is not routed from SKILL.md" % r)
            bad += 1
        n = len(read_text(path).splitlines())
        if n > max_lines:
            rep.fail("references", "%s has %d lines (max %d): split it or tighten it" % (r, n, max_lines))
            bad += 1
    if not bad:
        longest = max(len(read_text(p).splitlines()) for p in refs)
        rep.ok("references", "%d references routed from SKILL.md; longest %d lines (max %d)" % (len(refs), longest, max_lines))


# -------------------------------------------------------------------------------------------- links and paths --
def split_code(text):
    """Return (prose_with_fences_blanked, list of (line_no, code_text)) for code blocks and inline code spans."""
    prose_lines, code = [], []
    fence = None
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(2)
            prose_lines.append("")
            continue
        if fence is not None:
            if line.strip().startswith(fence):
                fence = None
            else:
                code.append((i, line))
            prose_lines.append("")
            continue
        prose_lines.append(line)
        for span in re.findall(r"`([^`\n]+)`", line):
            code.append((i, span))
    return "\n".join(prose_lines), code


def expand_braces(token):
    m = re.search(r"\{([^{}]*)\}", token)
    if not m:
        return [token]
    out = []
    for part in m.group(1).split(","):
        out.extend(expand_braces(token[:m.start()] + part + token[m.end():]))
    return out


def path_exists(root, token):
    if any(ch in token for ch in "*?["):
        return bool(glob.glob(os.path.join(root, token)))
    return os.path.exists(os.path.join(root, token))


def check_links_and_paths(root, rep):
    md_files = [p for p in walk_files(root) if p.endswith(".md")]
    n_links = n_paths = 0
    broken = []
    root_real = os.path.realpath(root)
    for path in md_files:
        r = rel(root, path)
        text = read_text(path)
        prose, code = split_code(text)
        # relative markdown links (outside code)
        for ln, line in enumerate(prose.splitlines(), 1):
            for target in LINK_RE.findall(re.sub(r"`[^`\n]*`", "", line)):
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                n_links += 1
                t = target.split("#", 1)[0]
                dest = os.path.realpath(os.path.join(os.path.dirname(path), t))
                if not (dest == root_real or dest.startswith(root_real + os.sep)):
                    broken.append("%s:%d link %r leaves the package" % (r, ln, target))
                elif not os.path.exists(dest):
                    broken.append("%s:%d link %r does not resolve" % (r, ln, target))
        # package paths and bare reference names inside code spans / blocks
        for ln, snippet in code:
            for token in PATH_TOKEN_RE.findall(snippet):
                token = token.rstrip(".:,;")
                if "<" in token or ">" in token or "…" in token or "..." in token:
                    continue
                if token.startswith(EXTERNAL_PREFIXES) or token.endswith(EXTERNAL_SUFFIXES):
                    continue
                if token in LOCAL_ONLY:
                    continue
                n_paths += 1
                for cand in expand_braces(token):
                    if not path_exists(root, cand):
                        broken.append("%s:%d path `%s` not found in the package" % (r, ln, cand))
            for name in BARE_REF_RE.findall(snippet):
                n_paths += 1
                if not os.path.isfile(os.path.join(root, "references", name)):
                    broken.append("%s:%d reference `%s` not found in references/" % (r, ln, name))
    for b in broken:
        rep.fail("links", b)
    if not broken:
        rep.ok("links", "%d relative links and %d package paths in %d markdown files resolve" % (n_links, n_paths, len(md_files)))


# ------------------------------------------------------------------------------------------------------ json --
def check_json(root, rep):
    n = 0
    for path in walk_files(root):
        if not path.endswith(".json"):
            continue
        r = rel(root, path)
        n += 1
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            rep.fail("json", "%s does not parse: %s" % (r, exc))
            continue
        if r.startswith("templates/queries/") and not isinstance(data.get("queries") if isinstance(data, dict) else None, dict):
            rep.fail("json", "%s has no top-level \"queries\" object" % r)
    if n and not any(x["check"] == "json" and x["status"] == "FAIL" for x in rep.results):
        rep.ok("json", "%d JSON files parse" % n)


# --------------------------------------------------------------------------------------------------- scripts --
def _stdlib_dirs():
    dirs = set()
    for key in ("stdlib", "platstdlib"):
        p = sysconfig.get_paths().get(key)
        if p:
            dirs.add(os.path.realpath(p))
    return dirs


def _is_stdlib(name, local_names, stdlib_dirs):
    if name in local_names or name == "__future__" or name in sys.builtin_module_names:
        return True
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return False
    if spec is None:
        return False
    if spec.origin in ("built-in", "frozen"):
        return True
    locations = [spec.origin] if spec.origin else []
    locations += list(spec.submodule_search_locations or [])
    if not locations:
        return False
    for loc in locations:
        real = os.path.realpath(loc)
        if "site-packages" in real or "dist-packages" in real:
            return False
        if not any(real == d or real.startswith(d + os.sep) for d in stdlib_dirs):
            return False
    return True


def _guarded_import_nodes(tree):
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            catches = set()
            for h in node.handlers:
                names = []
                if h.type is None:
                    names = ["*"]
                elif isinstance(h.type, ast.Name):
                    names = [h.type.id]
                elif isinstance(h.type, ast.Tuple):
                    names = [e.id for e in h.type.elts if isinstance(e, ast.Name)]
                catches.update(names)
            if catches & {"*", "ImportError", "ModuleNotFoundError", "Exception", "BaseException"}:
                for stmt in node.body:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, (ast.Import, ast.ImportFrom)):
                            guarded.add(id(sub))
    return guarded


def check_scripts(root, rep, run_exec):
    scripts = sorted(glob.glob(os.path.join(root, "scripts", "*.py")) + glob.glob(os.path.join(root, "tests", "*.py")))
    local_names = {os.path.splitext(os.path.basename(p))[0] for p in scripts}
    stdlib_dirs = _stdlib_dirs()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="of3_validate_") as tmp:
        for i, path in enumerate(scripts):
            r = rel(root, path)
            problems = []
            try:
                py_compile.compile(path, cfile=os.path.join(tmp, "c%d.pyc" % i), doraise=True)
            except py_compile.PyCompileError as exc:
                problems.append("py_compile: %s" % exc.msg.strip().splitlines()[-1])
            source = read_text(path)
            tree = None
            try:
                tree = ast.parse(source, filename=r, feature_version=(3, 9))
            except SyntaxError as exc:
                problems.append("not Python 3.9 grammar: line %s: %s" % (exc.lineno, exc.msg))
            if tree is not None:
                guarded = _guarded_import_nodes(tree)
                nonstd = set()
                for node in ast.walk(tree):
                    if id(node) in guarded:
                        continue
                    if isinstance(node, ast.Import):
                        mods = [a.name.split(".")[0] for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                        mods = [node.module.split(".")[0]]
                    else:
                        continue
                    nonstd.update(m for m in mods if not _is_stdlib(m, local_names, stdlib_dirs))
                if nonstd:
                    problems.append("non-stdlib import(s): %s" % ", ".join(sorted(nonstd)))
            if run_exec and not problems:
                try:
                    proc = subprocess.run([sys.executable, path, "--help"], cwd=tmp, env=env, timeout=60,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    if proc.returncode != 0 or not proc.stdout.strip():
                        problems.append("`--help` exited %d: %s" % (proc.returncode, scrub((proc.stderr or proc.stdout).strip()[-200:], root)))
                except subprocess.TimeoutExpired:
                    problems.append("`--help` timed out after 60 s")
            if problems:
                for p in problems:
                    rep.fail("scripts", "%s: %s" % (r, p))
            else:
                rep.ok("scripts", "%s compiles (3.9 grammar, stdlib imports)%s" % (r, "; --help ok" if run_exec else ""))


def check_query_templates(root, rep):
    helper = os.path.join(root, "scripts", "make_query.py")
    queries = sorted(glob.glob(os.path.join(root, "templates", "queries", "*.json")))
    if not os.path.isfile(helper) or not queries:
        rep.warn("queries", "make_query.py or templates/queries/*.json missing; query validation skipped")
        return
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    bad = 0
    for q in queries:
        try:
            proc = subprocess.run([sys.executable, helper, "--validate", q, "--no-path-check"], cwd=root, env=env,
                                  timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        except subprocess.TimeoutExpired:
            rep.fail("queries", "%s: make_query.py --validate timed out" % rel(root, q))
            bad += 1
            continue
        if proc.returncode != 0:
            tail = scrub(proc.stdout + proc.stderr, root).strip().splitlines()[-3:]
            rep.fail("queries", "%s: make_query.py --validate rc %d: %s" % (rel(root, q), proc.returncode, " | ".join(tail)))
            bad += 1
    if not bad:
        rep.ok("queries", "%d query templates pass make_query.py --validate --no-path-check" % len(queries))
    readme = os.path.join(root, "templates", "queries", "README.md")
    if os.path.isfile(readme):
        text = read_text(readme)
        unlisted = [os.path.basename(q) for q in queries if os.path.basename(q) not in text]
        if unlisted:
            rep.warn("queries", "templates/queries/README.md does not list: %s" % ", ".join(unlisted))


def check_sbatch(root, rep):
    templates = sorted(glob.glob(os.path.join(root, "templates", "*.sbatch.template")))
    if not templates:
        rep.warn("sbatch", "no templates/*.sbatch.template found")
        return
    bash = shutil.which("bash")
    if not bash:
        rep.warn("sbatch", "bash not found; `bash -n` skipped")
        return
    for t in templates:
        proc = subprocess.run([bash, "-n", t], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if proc.returncode:
            rep.fail("sbatch", "%s: bash -n rc %d: %s" % (rel(root, t), proc.returncode, scrub(proc.stderr.strip(), root)[-300:]))
        else:
            rep.ok("sbatch", "%s passes bash -n" % rel(root, t))


# ----------------------------------------------------------------------------------------------------- evals --
def _check_items(items, where, field, rep):
    if not isinstance(items, list) or not items:
        rep.fail("evals", "%s: %s must be a non-empty list" % (where, field))
        return
    for j, it in enumerate(items):
        if not (isinstance(it, dict) and isinstance(it.get("text"), str) and it["text"].strip()
                and isinstance(it.get("type"), str) and it["type"].strip()):
            rep.fail("evals", "%s: %s[%d] needs non-empty 'text' and 'type'" % (where, field, j))


def check_evals(root, rep):
    folder = os.path.basename(os.path.normpath(root))
    path = os.path.join(root, "evals", "evals.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        rep.fail("evals", "evals/evals.json unreadable: %s" % exc)
        return
    before = rep.count("FAIL")
    if not isinstance(data, dict):
        rep.fail("evals", "evals.json top level must be an object")
        return
    if data.get("skill_name") != folder:
        rep.fail("evals", "skill_name %r != folder name %r" % (data.get("skill_name"), folder))
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        rep.fail("evals", "evals.json needs a non-empty 'evals' list")
        return
    ids, names = set(), set()
    for k, ev in enumerate(evals):
        where = "evals[%d]" % k
        if not isinstance(ev, dict):
            rep.fail("evals", "%s is not an object" % where)
            continue
        eid, name = ev.get("id"), ev.get("name")
        if not isinstance(eid, int) or isinstance(eid, bool) or eid in ids:
            rep.fail("evals", "%s: id must be a unique integer (got %r)" % (where, eid))
        ids.add(eid)
        if not isinstance(name, str) or not SKILL_NAME_RE.match(name) or name in names:
            rep.fail("evals", "%s: name must be unique kebab-case (got %r)" % (where, name))
        names.add(name)
        where = "eval %s (%s)" % (eid, name)
        for field, minimum in (("prompt", 20), ("expected_output", 40)):
            v = ev.get(field)
            if not isinstance(v, str) or len(v.strip()) < minimum:
                rep.fail("evals", "%s: %s must be a string of >= %d chars" % (where, field, minimum))
        if "context" in ev and not isinstance(ev["context"], str):
            rep.fail("evals", "%s: context must be a string" % where)
        files = ev.get("files", [])
        if not isinstance(files, list):
            rep.fail("evals", "%s: files must be a list" % where)
        else:
            for f in files:
                if not isinstance(f, str) or not (os.path.exists(os.path.join(root, f)) or os.path.exists(os.path.join(root, "evals", f))):
                    rep.fail("evals", "%s: input file %r not found" % (where, f))
        _check_items(ev.get("assertions"), where, "assertions", rep)
        _check_items(ev.get("must_not"), where, "must_not", rep)
        refs = ev.get("references")
        if not isinstance(refs, list) or not refs:
            rep.fail("evals", "%s: references must be a non-empty list of package paths" % where)
        else:
            for p in refs:
                if not isinstance(p, str) or not os.path.exists(os.path.join(root, p)):
                    rep.fail("evals", "%s: reference %r not found in the package" % (where, p))
    if len(evals) < MIN_EVALS_WARN:
        rep.warn("evals", "only %d evals (suggest >= %d)" % (len(evals), MIN_EVALS_WARN))
    # reference answers: one '## <id> — <name>' heading per eval
    ra = os.path.join(root, "evals", "reference_answers.md")
    if os.path.isfile(ra):
        heads = {}
        for m in re.finditer(r"^##\s+(\d+)\s*[—–-]+\s*([a-z0-9-]+)\s*$", read_text(ra), re.M):
            heads[int(m.group(1))] = m.group(2)
        for ev in evals:
            if isinstance(ev, dict) and isinstance(ev.get("id"), int):
                got = heads.get(ev["id"])
                if got is None:
                    rep.fail("evals", "reference_answers.md has no '## %d — %s' section" % (ev["id"], ev.get("name")))
                elif got != ev.get("name"):
                    rep.fail("evals", "reference_answers.md section %d is %r, evals.json says %r" % (ev["id"], got, ev.get("name")))
        extra = sorted(set(heads) - ids)
        if extra:
            rep.warn("evals", "reference_answers.md has sections for unknown eval ids: %s" % extra)
    if rep.count("FAIL") == before:
        rep.ok("evals", "evals.json schema ok (%d evals, each with assertions, must_not, references; answers matched)" % len(evals))


def check_triggers(root, rep):
    path = os.path.join(root, "tests", "trigger_tests.md")
    if not os.path.isfile(path):
        return
    sections, current = {}, None
    for line in read_text(path).splitlines():
        if line.startswith("#"):
            low = line.lower()
            current = ("neg" if "should-not-trigger" in low else "pos" if "should-trigger" in low else None)
            if current:
                sections.setdefault(current, 0)
            continue
        if current and re.match(r"^\s*[-*]\s+\S", line):
            sections[current] += 1
    ok = True
    for key, label in (("pos", "should-trigger"), ("neg", "should-not-trigger")):
        n = sections.get(key)
        if n is None:
            rep.fail("triggers", "tests/trigger_tests.md has no '%s' section" % label)
            ok = False
        elif n < MIN_TRIGGER_ITEMS:
            rep.fail("triggers", "'%s' has %d prompts (need >= %d)" % (label, n, MIN_TRIGGER_ITEMS))
            ok = False
    if ok:
        rep.ok("triggers", "%d should-trigger and %d should-not-trigger prompts" % (sections["pos"], sections["neg"]))


# --------------------------------------------------------------------------------------------------- privacy --
def load_deny_file(path):
    rules = []
    with open(path, "r", encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("re:"):
                pat, label = line[3:], "deny-file line %d (regex)" % n
            elif line.startswith("word:"):
                pat, label = r"(?<![A-Za-z0-9])" + re.escape(line[5:]) + r"(?![A-Za-z0-9])", "deny-file line %d (word)" % n
            else:
                pat, label = re.escape(line), "deny-file line %d" % n
            rules.append((label, re.compile(pat, re.I)))
    return rules


def gitignore_covers(root, relpath):
    """True if a .gitignore in the package root or an ancestor (up to the repository root) ignores relpath."""
    here = os.path.realpath(root)
    target = os.path.join(os.path.realpath(root), relpath)
    while True:
        gi = os.path.join(here, ".gitignore")
        if os.path.isfile(gi):
            sub = os.path.relpath(target, here).replace(os.sep, "/")
            base = os.path.basename(sub)
            for raw in read_text(gi).splitlines():
                pat = raw.strip()
                if not pat or pat.startswith(("#", "!")):
                    continue
                pat = pat.lstrip("/")
                if pat.startswith("**/"):
                    pat = pat[3:]
                if fnmatch.fnmatch(sub, pat) or ("/" not in pat and fnmatch.fnmatch(base, pat)):
                    return True
        if os.path.isdir(os.path.join(here, ".git")):
            return False
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


def check_privacy(root, deny_rules, rep):
    rules = list(GENERIC_PRIVACY) + list(deny_rules)
    skip = set()
    for local in LOCAL_ONLY:
        covered = gitignore_covers(root, local)
        if os.path.exists(os.path.join(root, local)):
            if covered:
                rep.warn("privacy", "%s is present (git-ignored): not scanned; never publish it" % local)
                skip.add(local)
            else:
                rep.fail("privacy", "%s is present and NOT git-ignored: remove it or ignore it before publishing" % local)
        elif not covered:
            rep.warn("privacy", "no .gitignore rule covers %s (add one before a site copy is made)" % local)
    hits, scanned = [], 0
    for path in walk_files(root):
        r = rel(root, path)
        if r in skip:
            continue
        for label, rx in rules:
            if rx.search(r):
                hits.append("%s: file path matches %s" % (r, label))
        if is_binary(path):
            continue
        scanned += 1
        for ln, line in enumerate(read_text(path).splitlines(), 1):
            for label, rx in rules:
                for m in rx.finditer(line):
                    if label == "e-mail address" and m.group(0).lower().endswith(EMAIL_ALLOWED_DOMAINS):
                        continue
                    hits.append("%s:%d %s" % (r, ln, label))   # the matched text is not echoed
                    break
    for h in hits[:200]:
        rep.fail("privacy", h)
    if len(hits) > 200:
        rep.fail("privacy", "... %d more privacy hits" % (len(hits) - 200))
    if not hits:
        rep.ok("privacy", "%d files clean: %d generic patterns%s" % (
            scanned, len(GENERIC_PRIVACY), (" + %d deny-file tokens" % len(deny_rules)) if deny_rules else " (no --deny-file)"))


# ------------------------------------------------------------------------------------------------------ main --
def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Static self-check for the openfold3 skill package (stdlib only).")
    ap.add_argument("--root", default=os.path.dirname(here), help="package root (default: the parent of tests/)")
    ap.add_argument("--deny-file", help="file of private tokens to deny (kept OUTSIDE the package)")
    ap.add_argument("--max-ref-lines", type=int, default=DEFAULT_MAX_REF_LINES,
                    help="maximum lines per references/*.md (default %d)" % DEFAULT_MAX_REF_LINES)
    ap.add_argument("--no-exec", action="store_true", help="skip subprocess checks (--help runs, query validation, bash -n)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isfile(os.path.join(root, "SKILL.md")):
        print("usage error: %s has no SKILL.md" % root, file=sys.stderr)
        return 2
    deny_rules = []
    if args.deny_file:
        deny = os.path.realpath(args.deny_file)
        if not os.path.isfile(deny):
            print("usage error: deny-file not found: %s" % args.deny_file, file=sys.stderr)
            return 2
        if deny.startswith(os.path.realpath(root) + os.sep):
            print("usage error: the deny-file must live outside the package (it holds private tokens)", file=sys.stderr)
            return 2
        try:
            deny_rules = load_deny_file(deny)
        except (OSError, re.error) as exc:
            print("usage error: cannot use deny-file: %s" % exc, file=sys.stderr)
            return 2

    rep = Report()
    bytecode_before = bytecode_files(root)
    check_required(root, rep)
    skill_text = check_frontmatter(root, rep)
    check_references(root, skill_text, args.max_ref_lines, rep)
    check_links_and_paths(root, rep)
    check_json(root, rep)
    check_scripts(root, rep, run_exec=not args.no_exec)
    if not args.no_exec:
        check_query_templates(root, rep)
        check_sbatch(root, rep)
    check_evals(root, rep)
    check_triggers(root, rep)
    check_privacy(root, deny_rules, rep)
    left = sorted(bytecode_files(root) - bytecode_before)
    if left:
        rep.fail("files", "this validation run left bytecode: %s" % ", ".join(left[:5]))

    n_fail, n_warn, n_pass = rep.count("FAIL"), rep.count("WARN"), rep.count("PASS")
    if args.json:
        print(json.dumps({"package": os.path.basename(root), "passed": n_pass, "warnings": n_warn, "failed": n_fail,
                          "valid": n_fail == 0, "results": rep.results}, indent=2))
    else:
        print("openfold3 static validation: package '%s'" % os.path.basename(root))
        for r in rep.results:
            print("%-4s  %-11s %s" % (r["status"], r["check"], r["message"]))
        print("\nSummary: %d passed, %d warning(s), %d failed -> %s" % (
            n_pass, n_warn, n_fail, "VALID" if n_fail == 0 else "INVALID"))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
