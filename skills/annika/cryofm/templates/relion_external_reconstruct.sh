#!/bin/bash
# ==========================================================================
# RELION Refine3D with CryoFM2 as the external reconstructor -- TEMPLATE, NOT RUN ANYWHERE IN THIS PROJECT.
# Static reading of relion_wrapper.py (commit 6448681) and RELION 4.0.1-5.1.1 sources; see references/07.
#
# Requirements: RELION >= 4.0.1 (writes rlnPixelSize/rlnParticleDiameter), MPI auto-refine with split halves
# (3 or more MPI ranks; half1 and half2 ranks should share a node), GPU(s) visible to both RELION and CryoFM2,
# the cryofm2-pretrain weights, a solvent mask on the reference grid (cubic), RELION's default `--o .../run` naming
# (the wrapper derives run_it(N-1)_data.star for the inpaint mask from it).
#
# Known static hazards (07 §3): the FINAL joined iteration calls the wrapper without half1/half2 in the STAR name
# and the public wrapper raises ValueError there -> the refinement aborts after convergence; the previous
# iteration's half maps are the result. --num_processes in the string is ignored (all visible GPUs are used).
# --threshold-res is inert. Do not add --blush (CryoFM2 is then never called). Do not use --sequential_halves_recons.
# ==========================================================================
set -u

# ---- CHANGE-ME -----------------------------------------------------------
EXP_DIR=/abs/relion/project
OUTPUT_DIR=Refine3D_cryofm2/job001
REF_MAP=/abs/reference_lowpass40A.mrc
MASK_MAP=/abs/solvent_mask.mrc              # same box/pixel as the reference, cubic
PARTICLES=Select/jobNNN/particles.star
# --------------------------------------------------------------------------

# Site environment: whatever puts the CryoFM2 python (or a site launcher such as `cfm-relion`) on PATH, e.g.
# "source /abs/path/activate.sh", "module load …" or "conda activate cryofm". No `set -e` around it.
SITE_ENV_CMD=""                              # CHANGE-ME, e.g. "source /abs/path/activate.sh"
[ -n "$SITE_ENV_CMD" ] && eval "$SITE_ENV_CMD"
export CRYOFM_MODEL_DIR=/abs/cryofm-v2/cryofm2-pretrain   # CHANGE-ME; a shorthand such as `pretrain` only where a site launcher resolves it
export CRYOFM_HALF1_PORT=29500 CRYOFM_HALF2_PORT=29501     # distinct per concurrent job on one host
export NCCL_DEBUG=ERROR
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}      # the wrapper uses every visible GPU (per-GPU memory ~21 GB at batch 4 + bf16)

# All uncond_sampling flags are accepted; RELION appends the STAR as the LAST argument, so the string must end
# with a flag that takes no value (or a complete flag=value pair).
# CHANGE-ME: on the validated site `cfm-relion` is the launcher's alias for `python /opt/cryofm/relion/relion_wrapper.py`
# inside its container; elsewhere put "/abs/env/bin/python /abs/cryofm/relion/relion_wrapper.py" here.
CRYOFM_WRAPPER="/abs/path/cfm-relion"
export RELION_EXTERNAL_RECONSTRUCT_EXECUTABLE="${CRYOFM_WRAPPER} --mask-path ${MASK_MAP} --bbox --op denoise inpaint --fmask-threshold 10 --batch-size 4 --bf16 --norm-grad --use-lamb-w --spectral-mixing"
# The upstream docs add --skip-spectral-trailing and --threshold-res 10; the former disables the FSC(1/7) low-pass
# (RELION warns its Blush analogue "may inflate resolution estimates"), the latter is inert.

cd "${EXP_DIR}" || exit 2
mkdir -p "${OUTPUT_DIR}"
mpirun -n 3 relion_refine_mpi \
  --o "${OUTPUT_DIR}/run" \
  --auto_refine --split_random_halves \
  --i "${PARTICLES}" \
  --ref "${REF_MAP}" --ini_high 40 \
  --solvent_mask "${MASK_MAP}" \
  --dont_combine_weights_via_disc --pool 30 --pad 2 \
  --ctf --particle_diameter CHANGE-ME --flatten_solvent --zero_mask \
  --oversampling 1 --healpix_order 2 --auto_local_healpix_order 4 --offset_range 5 --offset_step 2 \
  --sym C1 --low_resol_join_halves 40 --norm --scale \
  --gpu "" --j 4 \
  --external_reconstruct |& tee "${OUTPUT_DIR}/console_log.txt"
# expect per iteration: " + Making system call for external reconstruction: ... run_itNNN_half1_class001_external_reconstruct.star"
# and the wrapper's "[relion_wrapper.py] Half1 detected: Using port 29500" / "Half2 detected: Using port 29501" lines in run.out.
