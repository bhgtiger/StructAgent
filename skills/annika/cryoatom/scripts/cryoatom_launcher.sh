#!/bin/bash
# ==========================================================================
# Portable CryoAtom2 launcher.
#
# Install it anywhere on PATH and call it `cryoatom`:
#     install -m 0755 cryoatom_launcher.sh ~/bin/cryoatom
#
#     cryoatom --version                                       # no weights needed
#     cryoatom build -h                                        # no weights needed
#     cryoatom build -v map.mrc -o out_fresh                   # no-sequence mode
#     cryoatom build -v map.mrc -ps prot.fasta -o out_fresh     # sequence mode
#     cryoatom build -v map.mrc -ps p.fa -rs r.fa -ds d.fa -o out_fresh
#
# A `build` needs a GPU with >= 14 GiB VRAM. Do not run inference on a login node.
#
# CONFIGURATION — resolved in this order:
#   1. environment variables (below)
#   2. $CRYOATOM_SKILL_CONFIG
#   3. ${XDG_CONFIG_HOME:-$HOME/.config}/cryoatom-skill/site-config.json
#
#   CRYOATOM_SKILL_CONFIG   path to the site config
#   CRYOATOM_ROUTE          container | native
#   CRYOATOM_RUNTIME        apptainer | singularity | docker | podman
#   CRYOATOM_SIF            container image: a FILE for apptainer/singularity,
#                           a store REFERENCE (name:tag) for docker/podman
#   CRYOATOM_CACHE          external weight cache root
#   CRYOATOM_BIN            native route: path to the cryoatom entry point
#   CRYOATOM_BINDS          extra binds, space-separated (e.g. "/data /scratch");
#                           an entry may also be "/src:/dst[:opts]"
#   CRYOATOM_MODULE_LOAD    module route: the command that puts cryoatom on PATH
#   CRYOATOM_NO_MOUNT_HOSTFS=1  start the container with --no-mount hostfs
#   CRYOATOM_VERIFY_WEIGHTS=1   full SHA-256 re-hash before running (~5.5 GiB read)
#   CRYOATOM_FORCE_NV=1 / CRYOATOM_NO_NV=1   override GPU-flag autodetection
#   CRYOATOM_DEBUG=1        print the resolved command before executing it
#
# WHY THE BINDS. build.py resolves checkpoints relative to the installed package
# directory and upstream provides no env-var override, so <cache>/checkpoint is
# bind-mounted over the in-image checkpoint directory. ESM-2 and RNA-FM are
# found through TORCH_HOME, so <cache>/torch is bound at /torchhome. Both
# language models load UNCONDITIONALLY, including in the no-sequence path.
# ==========================================================================
set -uo pipefail

DEFAULT_IN_IMAGE_BIN="/opt/conda/envs/CryoAtom2/bin/cryoatom"
DEFAULT_IN_IMAGE_CKPT="/opt/conda/envs/CryoAtom2/lib/python3.9/site-packages/CryoAtom2/checkpoint"

die() { echo "cryoatom: $*" >&2; exit 1; }

# --- resolve the site config -------------------------------------------------
CONFIG="${CRYOATOM_SKILL_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/cryoatom-skill/site-config.json}"
CFG_ROUTE="" CFG_RUNTIME="" CFG_IMAGE="" CFG_CACHE="" CFG_BIN=""
CFG_IN_BIN="" CFG_IN_CKPT="" CFG_NOHOSTFS="" CFG_MODULE_LOAD=""
CFG_BINDS=()

if [ -r "$CONFIG" ] && command -v python3 >/dev/null 2>&1; then
    _dump=$(python3 - "$CONFIG" <<'PY' 2>/dev/null
import json, shlex, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
inst = cfg.get("install") or {}
w = cfg.get("weights") or {}
def emit(key, val):
    print("%s=%s" % (key, shlex.quote("" if val is None else str(val))))
emit("CFG_ROUTE", inst.get("route"))
emit("CFG_RUNTIME", inst.get("container_runtime"))
emit("CFG_IMAGE", inst.get("image_path"))
emit("CFG_CACHE", w.get("cache_root"))
prefix = inst.get("conda_env_prefix")
emit("CFG_BIN", (prefix.rstrip("/") + "/bin/cryoatom") if prefix else None)
emit("CFG_IN_BIN", inst.get("in_image_binary"))
emit("CFG_IN_CKPT", inst.get("in_image_checkpoint_dir"))
emit("CFG_NOHOSTFS", "1" if inst.get("no_mount_hostfs") else "")
emit("CFG_MODULE_LOAD", inst.get("module_load"))
binds = inst.get("extra_binds") or []
if isinstance(binds, str):          # a scalar in the config must not be iterated per character
    binds = [binds]
print("CFG_BINDS=(%s)" % " ".join(shlex.quote(str(b)) for b in binds))
PY
)
    [ -n "$_dump" ] && eval "$_dump"
fi

# --- environment overrides ---------------------------------------------------
ROUTE="${CRYOATOM_ROUTE:-${CFG_ROUTE:-container}}"
RUNTIME="${CRYOATOM_RUNTIME:-${CFG_RUNTIME:-}}"
SIF="${CRYOATOM_SIF:-${CFG_IMAGE:-}}"
CACHE="${CRYOATOM_CACHE:-${CFG_CACHE:-}}"
NATIVE_BIN="${CRYOATOM_BIN:-${CFG_BIN:-}}"
IN_BIN="${CFG_IN_BIN:-$DEFAULT_IN_IMAGE_BIN}"
IN_CKPT="${CFG_IN_CKPT:-$DEFAULT_IN_IMAGE_CKPT}"
NOHOSTFS="${CRYOATOM_NO_MOUNT_HOSTFS:-${CFG_NOHOSTFS:-}}"
MODULE_LOAD="${CRYOATOM_MODULE_LOAD:-${CFG_MODULE_LOAD:-}}"

if [ -n "${CRYOATOM_BINDS:-}" ]; then
    # space-separated only: a colon inside an entry means "/src:/dst[:opts]"
    IFS=' ' read -r -a CFG_BINDS <<< "$CRYOATOM_BINDS"
fi

CKPT="${CACHE:+$CACHE/checkpoint}"
TORCH="${CACHE:+$CACHE/torch}"
PIN="${CACHE:+$CACHE/weights.pin.json}"

# --- does this invocation need the weights? ----------------------------------
# `--help`, `--version` and `build -h` never open a checkpoint, so they must keep
# working on a login node with no cache staged. Scan every argument: a help flag
# anywhere on the line wins over the subcommand.
_saw_build=0 _saw_help=0
for _arg in "$@"; do
    case "$_arg" in
        build)               _saw_build=1 ;;
        -h|--help|--version) _saw_help=1 ;;
    esac
done
NEEDS_WEIGHTS=0
[ "$_saw_build" -eq 1 ] && [ "$_saw_help" -eq 0 ] && NEEDS_WEIGHTS=1

# relative path|expected bytes  (CryoAtom2 2.1.1, commit 856e250)
WEIGHT_TABLE=(
    "checkpoint/RUNet.pth|151641598"
    "checkpoint/CryoNet.pth|847721570"
    "checkpoint/CryoNet_no_seq.pth|771564842"
    "torch/hub/checkpoints/RNA-FM_pretrained.pth|1194424423"
    "torch/hub/checkpoints/esm2_t33_650M_UR50D.pt|2604537549"
    "torch/hub/checkpoints/esm2_t33_650M_UR50D-contact-regression.pt|3687"
)

# Byte size, portably: GNU stat, then BSD/macOS stat, then POSIX wc. Echoes
# nothing and returns 1 when the size cannot be read, so an unreadable file is
# never mistaken for a zero-byte one.
filesize() {
    [ -f "$1" ] || return 1
    # -L: follow symlinks. Without it GNU stat reports the LINK's size, which
    # would reject a cache whose files were symlinked in (see the `link` step).
    stat -Lc%s "$1" 2>/dev/null || stat -Lf%z "$1" 2>/dev/null || \
        wc -c < "$1" 2>/dev/null | tr -cd '0-9' || return 1
}

preflight_weights() {
    [ -n "$CACHE" ] || die "no weight cache configured (set CRYOATOM_CACHE or weights.cache_root)"
    local spec rel want got bad=0
    for spec in "${WEIGHT_TABLE[@]}"; do
        IFS='|' read -r rel want <<< "$spec"
        if [ ! -s "$CACHE/$rel" ]; then
            echo "cryoatom: missing weight file: $CACHE/$rel" >&2
            bad=1; continue
        fi
        got=$(filesize "$CACHE/$rel") || got=""
        if [ -z "$got" ]; then
            echo "cryoatom: cannot read the size of $rel" >&2
            bad=1; continue
        fi
        if [ "$got" -ne "$want" ]; then
            echo "cryoatom: wrong size: $rel (got $got, expected $want)" >&2
            bad=1
        fi
    done
    if [ "$bad" -ne 0 ]; then
        echo "cryoatom: stage the cache with" >&2
        echo "  bash stage_cryoatom_weights.sh --cache $CACHE weights" >&2
        exit 1
    fi
    # An explicit verification request must FAIL CLOSED: if the hashes cannot be
    # checked, refuse rather than silently downgrade to the size check.
    if [ "${CRYOATOM_VERIFY_WEIGHTS:-}" = "1" ]; then
        local checker; checker="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/check_cryoatom_weights.py"
        [ -s "$PIN" ] || die "CRYOATOM_VERIFY_WEIGHTS=1 but no pin file at ${PIN:-<unset>}; run 'stage_cryoatom_weights.sh --cache $CACHE pin' first."
        if [ -r "$checker" ] && command -v python3 >/dev/null 2>&1; then
            python3 "$checker" --cache "$CACHE" --pin "$PIN" --mode sha256 \
                || die "weight cache does not match $PIN — refusing to run."
        elif command -v python3 >/dev/null 2>&1; then
            # The launcher may be installed on its own, away from the package.
            python3 - "$CACHE" "$PIN" <<'PYCHK' || die "weight cache does not match $PIN — refusing to run."
import hashlib, json, os, sys
cache, pin = sys.argv[1], sys.argv[2]
bad = []
for rel, meta in sorted(json.load(open(pin)).get("files", {}).items()):
    path = os.path.join(cache, rel)
    if not os.path.isfile(path):
        bad.append("missing: " + rel); continue
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    if meta.get("sha256") and h.hexdigest() != meta["sha256"]:
        bad.append("sha256 mismatch: " + rel)
for b in bad:
    print("  - " + b, file=sys.stderr)
sys.exit(1 if bad else 0)
PYCHK
        else
            die "CRYOATOM_VERIFY_WEIGHTS=1 but no python3 is available to check the hashes."
        fi
    fi
}

[ "$NEEDS_WEIGHTS" -eq 1 ] && preflight_weights

# --- writable scratch for matplotlib / torch hub locks ------------------------
RUNTMP="${TMPDIR:-/tmp}/cryoatom-${USER:-$(id -un)}-$$"
mkdir -p "$RUNTMP" || die "cannot create $RUNTMP"
trap 'rm -rf "$RUNTMP"' EXIT

# --- native route ------------------------------------------------------------
if [ "$ROUTE" = "native" ] || [ "$ROUTE" = "module" ] || [ "$ROUTE" = "preinstalled" ]; then
    # module route: run the site's module load line first, then resolve the
    # entry point it put on PATH. Guard against resolving back to this wrapper.
    if [ -z "$NATIVE_BIN" ] && [ -n "$MODULE_LOAD" ]; then
        eval "$MODULE_LOAD" || die "module load failed: $MODULE_LOAD"
        _cand="$(command -v cryoatom 2>/dev/null || true)"
        _self="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/$(basename "$0")"
        if [ -n "$_cand" ] && [ "$(readlink -f "$_cand" 2>/dev/null || echo "$_cand")" != \
                               "$(readlink -f "$_self" 2>/dev/null || echo "$_self")" ]; then
            NATIVE_BIN="$_cand"
        fi
    fi
    [ -n "$NATIVE_BIN" ] || die "route '$ROUTE' needs CRYOATOM_BIN, install.conda_env_prefix, or an install.module_load that puts a cryoatom other than this wrapper on PATH"
    [ -x "$NATIVE_BIN" ] || die "not executable: $NATIVE_BIN"
    # The verified cache wins over an inherited TORCH_HOME: a stale value would
    # send ESM-2 / RNA-FM to unpinned weights, or trigger a silent download.
    export TORCH_HOME="${TORCH:-${TORCH_HOME:-}}"
    export MPLCONFIGDIR="$RUNTMP" MPLBACKEND=Agg PYTHONNOUSERSITE=1
    [ "${CRYOATOM_DEBUG:-}" = "1" ] && echo "+ $NATIVE_BIN $*" >&2
    "$NATIVE_BIN" "$@"
    exit $?
fi

# --- container route ---------------------------------------------------------
if [ -z "$RUNTIME" ]; then
    for c in apptainer singularity podman docker; do
        command -v "$c" >/dev/null 2>&1 && { RUNTIME="$c"; break; }
    done
fi
[ -n "$RUNTIME" ] || die "no container runtime found (apptainer/singularity/podman/docker)"
command -v "$RUNTIME" >/dev/null 2>&1 || die "container runtime not on PATH: $RUNTIME"
[ -n "$SIF" ] || die "no container image configured (set CRYOATOM_SIF or install.image_path)"
# apptainer/singularity take a FILE; docker/podman take a store REFERENCE
# (name:tag or name@sha256:...), which is not a path and must not be stat'ed.
case "$RUNTIME" in
    apptainer|singularity)
        [ -e "$SIF" ] || die "image file not found: $SIF" ;;
esac

# GPU flag only when NVIDIA devices are actually present: on a CPU/login node an
# unconditional --nv makes the runtime complain about missing NVIDIA libraries,
# which would break light checks like `cryoatom build -h`.
WANT_GPU=0
if [ "${CRYOATOM_NO_NV:-}" != "1" ]; then
    if [ "${CRYOATOM_FORCE_NV:-}" = "1" ] || [ -e /dev/nvidiactl ] || [ -e /dev/nvidia0 ]; then
        WANT_GPU=1
    fi
fi

case "$RUNTIME" in
  apptainer|singularity)
    ARGS=(exec)
    [ "$WANT_GPU" -eq 1 ] && ARGS+=(--nv)
    # Some sites overlay the host filesystem into the container, which shadows
    # the image's /opt and hides the entry point. --no-mount hostfs fixes that,
    # at the cost of auto-binding only $HOME and $PWD — hence extra_binds.
    [ -n "$NOHOSTFS" ] && ARGS+=(--no-mount hostfs)
    for b in "${CFG_BINDS[@]+"${CFG_BINDS[@]}"}"; do
        [ -n "$b" ] && ARGS+=(-B "$b")
    done
    ARGS+=(-B "$RUNTMP":/rwcache)
    [ -n "$CKPT" ]  && [ -d "$CKPT" ]  && ARGS+=(-B "$CKPT":"$IN_CKPT")
    [ -n "$TORCH" ] && [ -d "$TORCH" ] && ARGS+=(-B "$TORCH":/torchhome)
    ARGS+=(--env TORCH_HOME=/torchhome --env MPLCONFIGDIR=/rwcache
           --env MPLBACKEND=Agg --env PYTHONNOUSERSITE=1)
    [ "${CRYOATOM_DEBUG:-}" = "1" ] && echo "+ $RUNTIME ${ARGS[*]} $SIF $IN_BIN $*" >&2
    # Not exec: the EXIT trap that removes $RUNTMP must still run.
    "$RUNTIME" "${ARGS[@]}" "$SIF" "$IN_BIN" "$@"
    exit $?
    ;;
  docker|podman)
    ARGS=(run --rm)
    if [ "$RUNTIME" = "podman" ]; then
        # Rootless podman already maps the caller into the container; adding
        # -u would break writes to bind-mounted host directories. keep-id makes
        # the in-container uid match the host uid.
        if [ "$(id -u)" -ne 0 ]; then
            ARGS+=(--userns=keep-id)
        fi
    else
        ARGS+=(-u "$(id -u):$(id -g)")
    fi
    [ "$WANT_GPU" -eq 1 ] && ARGS+=(--gpus all)
    ARGS+=(-v "$PWD":"$PWD" -w "$PWD" -v "$RUNTMP":/rwcache)
    for b in "${CFG_BINDS[@]+"${CFG_BINDS[@]}"}"; do
        # accept both "/path" and "/src:/dst[:opts]"
        case "$b" in "") continue ;; *:*) ARGS+=(-v "$b") ;; *) ARGS+=(-v "$b":"$b") ;; esac
    done
    [ -n "$CKPT" ]  && [ -d "$CKPT" ]  && ARGS+=(-v "$CKPT":"$IN_CKPT":ro)
    [ -n "$TORCH" ] && [ -d "$TORCH" ] && ARGS+=(-v "$TORCH":/torchhome:ro)
    ARGS+=(-e TORCH_HOME=/torchhome -e MPLCONFIGDIR=/rwcache
           -e MPLBACKEND=Agg -e PYTHONNOUSERSITE=1)
    [ "${CRYOATOM_DEBUG:-}" = "1" ] && echo "+ $RUNTIME ${ARGS[*]} $SIF $IN_BIN $*" >&2
    # Every input and output path must sit inside one of the -v mounts above.
    "$RUNTIME" "${ARGS[@]}" "$SIF" "$IN_BIN" "$@"
    exit $?
    ;;
  *)
    die "unsupported container runtime: $RUNTIME"
    ;;
esac
