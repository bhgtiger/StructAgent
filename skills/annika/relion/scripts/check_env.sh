#!/usr/bin/env bash
# check_env.sh - read-only RELION environment probe.
# Reports what should go into site_config.md. Runs no RELION jobs and writes nothing.
# Exit 0 if a usable relion_refine is found, 1 otherwise (with fix guidance).

set -u
FAIL=0
ok()   { echo "[OK]   $*"; }
bad()  { echo "[FAIL] $*"; FAIL=1; }
note() { echo "       $*"; }

echo "=== RELION environment probe (read-only) ==="
echo "host: $(hostname 2>/dev/null)    date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# 1. RELION binaries
RELION_REFINE="$(command -v relion_refine 2>/dev/null || true)"
if [ -z "$RELION_REFINE" ]; then
  # common manual locations (keep placeholders out of shell globs)
  for c in ${RELION_BIN:-/opt/relion/bin}/relion_refine "$HOME"/relion*/build/bin/relion_refine /usr/local/bin/relion_refine; do
    [ -x "$c" ] && RELION_REFINE="$c" && break || true
  done
fi
if [ -z "$RELION_REFINE" ]; then
  bad "relion_refine not found on PATH"
  note "Fix: load your RELION module / source its env, or add its bin dir to PATH."
  note "Then set RELION install path in site_config.md."
else
  ok "relion_refine: $RELION_REFINE"
  BIN_DIR="$(dirname "$RELION_REFINE")"
  note "bin dir: $BIN_DIR"
  VER="$("$RELION_REFINE" --version 2>&1 | head -1)"
  note "version: ${VER:-unknown}"
fi
echo

# 2. Program family coverage (helical / tomo / python wrappers)
echo "--- program families on PATH ---"
for p in relion_refine_mpi relion_preprocess relion_run_motioncorr relion_run_ctffind \
         relion_ctf_refine relion_motion_refine relion_postprocess relion_mask_create \
         relion_particle_subtract relion_class_ranker relion_star_handler relion_image_handler \
         relion_convert_star relion_helix_toolbox relion_tomo_reconstruct_particle \
         relion_python_blush relion_python_dynamight relion_python_modelangelo relion_python_topaz; do
  if command -v "$p" >/dev/null 2>&1; then printf '  %-34s yes\n' "$p"; else printf '  %-34s NO\n' "$p"; fi
done
echo

# 3. Compute environment
echo "--- compute ---"
if command -v mpirun >/dev/null 2>&1; then ok "mpirun: $(command -v mpirun) ($(mpirun --version 2>&1 | head -1))"; else bad "mpirun not found (relion_*_mpi will not run)"; fi
if command -v nvidia-smi >/dev/null 2>&1; then
  ok "nvidia-smi present"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null | sed 's/^/       GPU: /' || \
    nvidia-smi 2>&1 | grep -i 'CUDA Version' | sed 's/^/       /'
else
  note "no nvidia-smi (CPU-only, or GPUs only on worker nodes — check the queue, not the head node)"
fi
command -v python3 >/dev/null 2>&1 && note "python3: $(command -v python3) ($(python3 --version 2>&1))"
echo

# 4. Interop tools
echo "--- interop tools (for file conversion) ---"
for t in csparc2star.py cryodrgn; do
  if command -v "$t" >/dev/null 2>&1; then printf '  %-20s %s\n' "$t" "$(command -v "$t")"; else printf '  %-20s NOT FOUND (set path in site_config.md if you need it)\n' "$t"; fi
done
echo

# 5. Queue hint
echo "--- queue / scheduler ---"
for q in sbatch qsub bsub; do command -v "$q" >/dev/null 2>&1 && note "scheduler: $q ($(command -v "$q"))"; done
echo

if [ "$FAIL" -eq 0 ]; then
  echo "=> Usable RELION install found. Record the values above in site_config.md."
else
  echo "=> Environment incomplete. See [FAIL] lines above before generating commands."
fi
exit $FAIL
