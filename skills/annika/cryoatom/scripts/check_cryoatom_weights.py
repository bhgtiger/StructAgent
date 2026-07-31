#!/usr/bin/env python3
"""Verify the external CryoAtom2 weight cache.

The install keeps model weights outside the image/environment on purpose (one
image plus an external cache), so the six weight files are the part of the
install that can silently rot. This checks them.

  --mode size    presence + exact byte size          (default; cheap)
  --mode sha256  presence + size + SHA-256           (~5.5 GiB read)

With --pin <weights.pin.json> the pinned sizes and hashes are what a file is
checked against. WITHOUT a pin there is nothing to compare a hash to: the
built-in byte sizes are still checked, `--mode sha256` only computes and prints
the hashes, and the report says so rather than claiming a verified cache.

Exit 0 if every file matches, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# Relative path -> expected byte size at CryoAtom2 2.1.1 (commit 856e250).
EXPECTED = [
    ("checkpoint/RUNet.pth", 151641598),
    ("checkpoint/CryoNet.pth", 847721570),
    ("checkpoint/CryoNet_no_seq.pth", 771564842),
    ("torch/hub/checkpoints/RNA-FM_pretrained.pth", 1194424423),
    ("torch/hub/checkpoints/esm2_t33_650M_UR50D.pt", 2604537549),
    ("torch/hub/checkpoints/esm2_t33_650M_UR50D-contact-regression.pt", 3687),
]


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def expectations(pin_path):
    """Return {relpath: {'bytes': int, 'sha256': str|None}} from pin or defaults."""
    if pin_path:
        with open(pin_path) as fh:
            pinned = json.load(fh).get("files", {})
        if not pinned:
            raise ValueError("pin file %s has no 'files' section" % pin_path)
        return {rel: {"bytes": meta.get("bytes"), "sha256": meta.get("sha256")}
                for rel, meta in pinned.items()}
    return {rel: {"bytes": size, "sha256": None} for rel, size in EXPECTED}


def check(cache, want, mode):
    problems, report = [], {}
    for rel in sorted(want):
        path = os.path.join(cache, rel)
        entry = {"expected_bytes": want[rel]["bytes"], "bytes": None,
                 "sha256": None, "status": "ok"}
        if not os.path.isfile(path):
            entry["status"] = "missing"
            problems.append("missing: %s" % rel)
        else:
            entry["bytes"] = os.path.getsize(path)
            if want[rel]["bytes"] is not None and entry["bytes"] != want[rel]["bytes"]:
                entry["status"] = "size-mismatch"
                problems.append("size mismatch: %s (got %d, expected %d)"
                                % (rel, entry["bytes"], want[rel]["bytes"]))
            elif mode == "sha256":
                entry["sha256"] = sha256_of(path)
                if want[rel]["sha256"] and entry["sha256"] != want[rel]["sha256"]:
                    entry["status"] = "sha256-mismatch"
                    problems.append("sha256 mismatch: %s (got %s, pinned %s)"
                                    % (rel, entry["sha256"], want[rel]["sha256"]))
        report[rel] = entry
    return problems, report


def self_test():
    failures = []
    if len(EXPECTED) != 6:
        failures.append("expected six weight files")
    if len({rel for rel, _ in EXPECTED}) != 6:
        failures.append("weight paths must be unique")
    want = expectations(None)
    problems, report = check("/nonexistent-cryoatom-cache", want, "size")
    if len(problems) != 6 or any(e["status"] != "missing" for e in report.values()):
        failures.append("empty cache must report six missing files")
    if any(v["sha256"] is not None for v in expectations(None).values()):
        failures.append("the built-in table must carry no hashes to compare against")
    print(json.dumps({"self_test": "ok" if not failures else "failed",
                      "failures": failures}, indent=2))
    return 0 if not failures else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", help="weight cache root")
    ap.add_argument("--pin", help="weights.pin.json (default: <cache>/weights.pin.json if present)")
    ap.add_argument("--mode", choices=("size", "sha256"), default="size")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.cache:
        ap.error("--cache is required")

    pin = args.pin
    if pin is None:
        candidate = os.path.join(args.cache, "weights.pin.json")
        pin = candidate if os.path.isfile(candidate) else None

    try:
        want = expectations(pin)
    except (OSError, ValueError) as exc:
        print("cannot read pin file: %s" % exc, file=sys.stderr)
        return 1

    problems, report = check(args.cache, want, args.mode)

    if args.json:
        print(json.dumps({"cache": args.cache, "pin": pin, "mode": args.mode,
                          "ok": not problems, "problems": problems,
                          "files": report}, indent=2, sort_keys=True))
    elif problems:
        print("cryoatom weight cache FAILED (%s check):" % args.mode, file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        if not pin:
            print("  (no pin file; sizes checked against the built-in table for 2.1.1)",
                  file=sys.stderr)
    elif pin:
        print("cryoatom weight cache OK (%d files, %s check against %s)"
              % (len(report), args.mode, pin))
    elif args.mode == "sha256":
        print("cryoatom weight cache: %d files match the built-in byte sizes." % len(report))
        print("NOT VERIFIED: no pin file, so these SHA-256 values were computed, "
              "not checked against anything.")
        for rel in sorted(report):
            if report[rel]["sha256"]:
                print("  %s  %s" % (report[rel]["sha256"], rel))
        print("Create a pin with: stage_cryoatom_weights.sh --cache %s pin" % args.cache)
    else:
        print("cryoatom weight cache OK (%d files, size check against the built-in "
              "table for 2.1.1; no pin file, so content is unverified)" % len(report))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
