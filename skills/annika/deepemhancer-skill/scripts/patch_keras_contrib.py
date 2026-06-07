#!/usr/bin/env python3
"""Idempotently patch keras_contrib for TensorFlow 2.x.

DeepEMhancer's bundled model checkpoints reference `keras_contrib`
(InstanceNormalization etc.). On TF 2.x, `keras_contrib.backend.
tensorflow_backend.moments()` calls `tf.nn.moments(..., keep_dims=...)`, but
TF 2.x renamed that keyword to `keepdims`, so loading a checkpoint raises
`TypeError: moments() got an unexpected keyword argument 'keep_dims'`.

This script rewrites that one function to accept BOTH spellings and forward
the modern one. Running it twice is a no-op (it detects the already-patched
signature). It edits ONLY the keras_contrib backend file inside the given
environment's site-packages; it touches nothing else.

Usage:
    python3 patch_keras_contrib.py            # patch the active env
    python3 patch_keras_contrib.py --env-prefix /path/to/conda/env
    python3 patch_keras_contrib.py --check    # report status, change nothing
"""
import argparse
import glob
import os
import sys

PATCHED_SIGNATURE = "def moments(x, axes, shift=None, keep_dims=False, keepdims=None):"
PATCHED_BODY = '''def moments(x, axes, shift=None, keep_dims=False, keepdims=None):
    \'\'\' Wrapper over tensorflow backend call \'\'\'
    # Support both legacy `keep_dims` and modern `keepdims` callers (TF 2.x).
    kd = keepdims if keepdims is not None else keep_dims
    return tf.nn.moments(x, axes, shift=shift, keepdims=kd)
'''


def find_backend_file(env_prefix):
    """Locate keras_contrib/backend/tensorflow_backend.py under env_prefix."""
    patterns = [
        os.path.join(env_prefix, "lib", "python*", "site-packages",
                     "keras_contrib", "backend", "tensorflow_backend.py"),
    ]
    for pat in patterns:
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    return None


def patch_text(text):
    """Return (new_text, changed: bool). Idempotent.

    Matches only from `def moments(...keep_dims=False):` up to and INCLUDING the
    first `return tf.nn.moments(...)` line — never to end-of-file — so an
    unexpected keras_contrib layout can't have its trailing code deleted.
    """
    if PATCHED_SIGNATURE in text:
        return text, False  # already patched
    import re
    pattern = re.compile(
        r"def moments\(x, axes, shift=None, keep_dims=False\):"
        r".*?return tf\.nn\.moments\([^\n]*\)\n",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        raise RuntimeError(
            "Could not find the expected `def moments(x, axes, shift=None, "
            "keep_dims=False):` ending in `return tf.nn.moments(...)`. "
            "keras_contrib may be a different version; inspect the file manually.")
    if len(m.group(0)) > 2000:
        raise RuntimeError(
            "Matched moments() span is unexpectedly large (%d chars); refusing "
            "to patch automatically — inspect the file manually." % len(m.group(0)))
    # Slice-replace (no re.sub backreference surprises) and keep one trailing NL.
    new_text = text[:m.start()] + PATCHED_BODY + text[m.end():]
    return new_text, True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-prefix", default=os.environ.get("CONDA_PREFIX", ""),
                    help="conda env prefix (default: active $CONDA_PREFIX).")
    ap.add_argument("--check", action="store_true",
                    help="report patch status only; make no changes.")
    args = ap.parse_args(argv)

    if not args.env_prefix:
        sys.stderr.write("No env prefix; activate the env or pass --env-prefix.\n")
        return 2
    path = find_backend_file(args.env_prefix)
    if not path:
        sys.stderr.write(
            "keras_contrib backend file not found under %s. Is keras_contrib "
            "installed in this env?\n" % args.env_prefix)
        return 3

    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    if PATCHED_SIGNATURE in text:
        print("Already patched: %s" % path)
        return 0
    if args.check:
        print("NOT patched (would patch): %s" % path)
        return 1

    new_text, changed = patch_text(text)
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_text)
        print("Patched moments() for TF 2.x in: %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
