#!/bin/bash
# ==========================================================================
# CryoAtom2 2.1.1 external weight cache — stage, pin, verify, link, fixture.
#
#   bash stage_cryoatom_weights.sh --cache <DIR> plan       # what would be fetched (no writes)
#   bash stage_cryoatom_weights.sh --cache <DIR> weights    # download + lay out + pin
#   bash stage_cryoatom_weights.sh --cache <DIR> pin        # (re)write weights.pin.json
#   bash stage_cryoatom_weights.sh --cache <DIR> verify     # full sha256 check
#   bash stage_cryoatom_weights.sh --cache <DIR> fixture    # public EMD-33198 / 7XHT test data
#   bash stage_cryoatom_weights.sh --cache <DIR> link --site-packages <DIR>
#                                                          # native installs: symlink into the package
#
# Layout produced (5,443,574,325 bytes of downloads -> six weight files, ~5.1 GiB):
#   <cache>/checkpoint/{RUNet,CryoNet,CryoNet_no_seq}.pth
#   <cache>/torch/hub/checkpoints/{RNA-FM_pretrained.pth,esm2_t33_650M_UR50D.pt,
#                                  esm2_t33_650M_UR50D-contact-regression.pt}
#   <cache>/weights.pin.json          sizes + SHA-256 of all six
#   <cache>/fixture/                  only after `fixture`
#
# WHY EXTERNAL. build.py resolves checkpoints relative to the installed package
# directory and upstream exposes no env-var override, so the container launcher
# bind-mounts <cache>/checkpoint over the in-image checkpoint directory and a
# native install symlinks into it (`link`). ESM-2 and RNA-FM are found through
# TORCH_HOME=<cache>/torch. Both language models load UNCONDITIONALLY, including
# in the no-sequence path, so all six files are required for every run.
#
# TLS. Upstream install.sh uses `wget --no-check-certificate`. That bypass is
# NOT needed and NOT used here. Do not reintroduce it.
#
# Downloads total 5,443,574,325 bytes (~5.1 GiB), plus ~118 MiB for the fixture.
# Run on a login or data-transfer node — network I/O only — never inside a GPU
# allocation.
# ==========================================================================
set -uo pipefail

CACHE=""
SITE_PACKAGES=""
CHECKPOINT_DIR=""
CMD=""

usage() {
    sed -n '2,32p' "$0"
    exit 2
}

need_value() {                   # need_value <flag> <remaining-arg-count>
    if [ "$2" -lt 2 ]; then
        echo "$1 needs a value" >&2
        exit 2
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        --cache)          need_value "$1" $#; CACHE="$2"; shift 2 ;;
        --site-packages)  need_value "$1" $#; SITE_PACKAGES="$2"; shift 2 ;;
        --checkpoint-dir) need_value "$1" $#; CHECKPOINT_DIR="$2"; shift 2 ;;
        -h|--help)        usage ;;
        plan|weights|pin|verify|fixture|link) CMD="$1"; shift ;;
        *) echo "unknown argument: $1" >&2; usage ;;
    esac
done

[ -n "$CMD" ]   || usage
[ -n "$CACHE" ] || { echo "--cache <DIR> is required" >&2; exit 2; }

CKPT="$CACHE/checkpoint"
TORCH="$CACHE/torch/hub/checkpoints"
DL="$CACHE/_dl"
PIN="$CACHE/weights.pin.json"
FIXTURE="$CACHE/fixture"

YANG="https://yanglab.qd.sdu.edu.cn/CryoAtom/download"
ESM="https://dl.fbaipublicfiles.com/fair-esm"

# url  dest-basename  expected-bytes
DOWNLOADS=(
    "$YANG/checkpoints_v2.1.zip|checkpoints_v2.1.zip|1644608666"
    "$YANG/RNA-FM_pretrained.pth|RNA-FM_pretrained.pth|1194424423"
    "$ESM/models/esm2_t33_650M_UR50D.pt|esm2_t33_650M_UR50D.pt|2604537549"
    "$ESM/regression/esm2_t33_650M_UR50D-contact-regression.pt|esm2_t33_650M_UR50D-contact-regression.pt|3687"
)

# Byte size of a file, portably: GNU stat, then BSD/macOS stat, then POSIX wc.
# Echoes nothing and returns 1 when the size cannot be read — never 0, so a
# failed stat is not mistaken for an empty file.
filesize() {
    [ -f "$1" ] || return 1
    # -L: follow symlinks. Without it GNU stat reports the LINK's size, which
    # would reject a cache whose files were symlinked in (see the `link` step).
    stat -Lc%s "$1" 2>/dev/null || stat -Lf%z "$1" 2>/dev/null || \
        wc -c < "$1" 2>/dev/null | tr -cd '0-9' || return 1
}

fetch() {                       # fetch <url> <dest> <bytes>
    local url="$1" dest="$2" want="$3" got
    got=$(filesize "$dest") || got=""
    if [ -n "$got" ] && [ "$got" -eq "$want" ]; then
        echo "  have $(basename "$dest")"
        return 0
    fi
    echo "  get  $(basename "$dest")  ($want bytes)"
    curl -fL --retry 5 --retry-delay 10 -C - --progress-bar -o "$dest" "$url" || return 1
    got=$(filesize "$dest") || got=""
    if [ -z "$got" ]; then
        echo "  FAIL $(basename "$dest"): cannot read the downloaded file's size" >&2
        return 1
    fi
    if [ "$got" -ne "$want" ]; then
        echo "  FAIL $(basename "$dest"): got $got bytes, expected $want" >&2
        return 1
    fi
}

cmd_plan() {
    local total=0 bytes
    echo "== plan (nothing is downloaded or written) =="
    echo "cache root : $CACHE"
    for spec in "${DOWNLOADS[@]}"; do
        IFS='|' read -r url name bytes <<< "$spec"
        printf '  %-46s %14s bytes  %s\n' "$name" "$bytes" "$url"
        total=$((total + bytes))
    done
    echo "  --------------------------------------------------------------"
    local tenths=$(( (total * 10 + 536870912) / 1073741824 ))
    printf '  total download %s bytes (~%d.%d GiB), expands to six weight files\n' \
        "$total" "$((tenths / 10))" "$((tenths % 10))"
    echo "  fixture (separate step): $YANG/7xht.zip  123995068 bytes (~118 MiB)"
    echo
    echo "Needs curl and unzip. Run 'weights' to execute this plan; it requires outbound"
    echo "HTTPS to yanglab.qd.sdu.edu.cn and dl.fbaipublicfiles.com over verified TLS."
}

cmd_weights() {
    # Check the tools first: discovering a missing unzip after 5 GiB of
    # downloads is a pointless way to fail.
    command -v curl  >/dev/null || { echo "  FAIL: curl not found" >&2; return 1; }
    command -v unzip >/dev/null || { echo "  FAIL: unzip not found" >&2; return 1; }
    mkdir -p "$CKPT" "$TORCH" "$DL" || return 1
    echo "== downloading CryoAtom2 weights into $CACHE =="
    for spec in "${DOWNLOADS[@]}"; do
        IFS='|' read -r url name bytes <<< "$spec"
        fetch "$url" "$DL/$name" "$bytes" || return 1
    done

    echo "== laying out the cache =="
    # checkpoints_v2.1.zip unpacks as ./CryoAtom2/checkpoint/*.pth
    ( cd "$DL" && unzip -oq checkpoints_v2.1.zip ) || return 1
    local f src
    for f in RUNet.pth CryoNet.pth CryoNet_no_seq.pth; do
        src=$(find "$DL" -name "$f" -type f | head -1)
        [ -n "$src" ] || { echo "  FAIL: $f not found in checkpoints_v2.1.zip" >&2; return 1; }
        install -m 0640 "$src" "$CKPT/$f" || return 1
        echo "  ok   checkpoint/$f"
    done
    for f in RNA-FM_pretrained.pth esm2_t33_650M_UR50D.pt esm2_t33_650M_UR50D-contact-regression.pt; do
        install -m 0640 "$DL/$f" "$TORCH/$f" || return 1
        echo "  ok   torch/hub/checkpoints/$f"
    done

    cmd_pin || return 1
    echo
    echo "Cache staged. Reclaim the download staging area with:"
    echo "  rm -rf $DL"
}

cmd_pin() {
    echo "== writing $PIN =="
    python3 - "$CACHE" "$PIN" <<'PY'
import hashlib, json, os, sys
cache, out = sys.argv[1], sys.argv[2]
rels = [
    "checkpoint/RUNet.pth",
    "checkpoint/CryoNet.pth",
    "checkpoint/CryoNet_no_seq.pth",
    "torch/hub/checkpoints/RNA-FM_pretrained.pth",
    "torch/hub/checkpoints/esm2_t33_650M_UR50D.pt",
    "torch/hub/checkpoints/esm2_t33_650M_UR50D-contact-regression.pt",
]
files = {}
for rel in rels:
    p = os.path.join(cache, rel)
    if not os.path.isfile(p):
        sys.exit("  FAIL: %s is missing; run `weights` first" % rel)
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    files[rel] = {"bytes": os.path.getsize(p), "sha256": h.hexdigest()}
    print("  %s  %d  %s..." % (rel, files[rel]["bytes"], files[rel]["sha256"][:16]))
with open(out, "w") as fh:
    json.dump({"tool": "CryoAtom2", "version": "2.1.1",
               "source_commit": "856e250df7b784b854b892f1b619d32d51188cef",
               "files": files}, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
}

cmd_verify() {
    local here; here="$(cd "$(dirname "$0")" && pwd)"
    python3 "$here/check_cryoatom_weights.py" --cache "$CACHE" --mode sha256
}

cmd_fixture() {
    # Public example from the upstream README: EMD-33198 / PDB 7XHT, with
    # protein + RNA + DNA FASTA. Public data only — safe as a smoke test.
    mkdir -p "$FIXTURE" "$DL" || return 1
    command -v unzip >/dev/null || { echo "  FAIL: unzip not found" >&2; return 1; }
    fetch "$YANG/7xht.zip" "$DL/7xht.zip" 123995068 || return 1
    ( cd "$FIXTURE" && unzip -oq "$DL/7xht.zip" ) || return 1
    echo "== fixture =="
    find "$FIXTURE" -type f | sort
}

cmd_link() {
    # Native (non-container) installs: build.py reads checkpoints from
    # <site-packages>/CryoAtom2/checkpoint and offers no override, so symlink
    # the cached files in rather than copying 1.8 GiB twice.
    local target="$CHECKPOINT_DIR"
    if [ -z "$target" ]; then
        [ -n "$SITE_PACKAGES" ] || {
            echo "link needs --site-packages <DIR> or --checkpoint-dir <DIR>" >&2; return 2; }
        target="$SITE_PACKAGES/CryoAtom2/checkpoint"
    fi
    mkdir -p "$target" || return 1
    local f
    for f in RUNet.pth CryoNet.pth CryoNet_no_seq.pth; do
        [ -s "$CKPT/$f" ] || { echo "  FAIL: $CKPT/$f missing; run 'weights' first" >&2; return 1; }
        ln -sfn "$CKPT/$f" "$target/$f" || return 1
        echo "  link $target/$f -> $CKPT/$f"
    done
    echo
    echo "Also export TORCH_HOME so ESM-2 and RNA-FM resolve:"
    echo "  export TORCH_HOME=$CACHE/torch"
}

case "$CMD" in
    plan)    cmd_plan ;;
    weights) cmd_weights ;;
    pin)     cmd_pin ;;
    verify)  cmd_verify ;;
    fixture) cmd_fixture ;;
    link)    cmd_link ;;
    *)       usage ;;
esac
