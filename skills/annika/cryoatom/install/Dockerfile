# ============================================================================
# Dockerfile — CryoAtom2 2.1.1, the Docker/Podman equivalent of cryoatom.def.
#
#   docker build -f install/Dockerfile -t cryoatom:2.1.1 install/
#   podman build -f install/Dockerfile -t cryoatom:2.1.1 install/
#
# Same contract as the Apptainer recipe: the upstream commit AND tree hash are
# verified during the build, `getp` is compiled from the pinned sources, and
# NO model weights are baked in — the checkpoint directory is left empty as a
# bind-mount point, and ESM-2 / RNA-FM are found through TORCH_HOME=/torchhome.
#
# Record the resulting image REFERENCE (cryoatom:2.1.1), not a file path, as
# `install.image_path` in the site config; docker/podman resolve names from the
# image store, not the filesystem.
#
# Run it through scripts/cryoatom_launcher.sh, or by hand:
#   docker run --rm --gpus all -u "$(id -u):$(id -g)" \
#     -v "$PWD":"$PWD" -w "$PWD" \
#     -v <CACHE>/checkpoint:/opt/conda/envs/CryoAtom2/lib/python3.9/site-packages/CryoAtom2/checkpoint:ro \
#     -v <CACHE>/torch:/torchhome:ro -e TORCH_HOME=/torchhome \
#     cryoatom:2.1.1 /opt/conda/envs/CryoAtom2/bin/cryoatom build ...
#
# --gpus all needs the NVIDIA Container Toolkit (or CDI for rootless podman)
# installed and configured on the host. Without it the container has no GPU.
#
# Base image pinned by digest, exactly as in cryoatom.def. Do not replace it
# with a floating tag.
# ============================================================================
FROM continuumio/miniconda3@sha256:1808b31ef43e9c521cde5884ba4df9ec26d8d503a314cea787590f8550358a63

LABEL tool="CryoAtom2" \
      version="2.1.1" \
      source.repo="https://github.com/YangLab-SDU/CryoAtom" \
      source.commit="856e250df7b784b854b892f1b619d32d51188cef" \
      source.tree="0058c0c68857b66962f9ad421756513e74de7518" \
      source.kind="untagged 2.1.1 master snapshot (NOT a tagged release)" \
      source.license="MIT" \
      image.class="content-addressed installed snapshot; NOT a byte-identical rebuild recipe" \
      weights.policy="external cache, bind-mounted at run time"

ENV PYTHONNOUSERSITE=1 \
    MPLBACKEND=Agg \
    TORCH_HOME=/torchhome \
    PATH=/opt/conda/envs/CryoAtom2/bin:$PATH

SHELL ["/bin/bash", "-c"]

RUN set -eu; \
    SRC=/opt/src; \
    COMMIT=856e250df7b784b854b892f1b619d32d51188cef; \
    EXPECT_TREE=0058c0c68857b66962f9ad421756513e74de7518; \
    echo "=== [1/6] base tooling ==="; \
    conda install -y -n base -c conda-forge git make 'gxx_linux-64=13.*' 'gcc_linux-64=13.*'; \
    conda clean -afy; \
    echo "=== [2/6] fetch pinned source ==="; \
    mkdir -p "$SRC"; \
    git clone https://github.com/YangLab-SDU/CryoAtom "$SRC/CryoAtom"; \
    git -C "$SRC/CryoAtom" checkout --detach "$COMMIT"; \
    test "$(git -C "$SRC/CryoAtom" rev-parse HEAD)" = "$COMMIT" || { echo "FATAL: wrong commit" >&2; exit 1; }; \
    test "$(git -C "$SRC/CryoAtom" rev-parse HEAD^{tree})" = "$EXPECT_TREE" || { echo "FATAL: wrong tree" >&2; exit 1; }; \
    mkdir -p /opt/cryoatom; \
    git -C "$SRC/CryoAtom" log -1 --format='%H%n%ci%n%s' > /opt/cryoatom/source_commit.txt; \
    git -C "$SRC/CryoAtom" rev-parse HEAD^{tree} > /opt/cryoatom/source_tree.txt; \
    cp "$SRC/CryoAtom/LICENSE" /opt/cryoatom/LICENSE; \
    cp "$SRC/CryoAtom/linux.yml" /opt/cryoatom/linux.yml; \
    echo "=== [3/6] conda environment from the pinned linux.yml ==="; \
    conda env create -f "$SRC/CryoAtom/linux.yml"; \
    conda clean -afy; \
    echo "=== [4/6] compile getp from the pinned sources ==="; \
    export CXX="$(ls /opt/conda/bin/*-linux-gnu-g++ | head -1)"; \
    make -C "$SRC/CryoAtom/CryoAtom2/src/getp" clean || true; \
    make -C "$SRC/CryoAtom/CryoAtom2/src/getp" CXX="$CXX"; \
    test -x "$SRC/CryoAtom/CryoAtom2/src/getp/getp" || { echo "FATAL: getp did not build" >&2; exit 1; }; \
    echo "=== [5/6] install the package ==="; \
    ENV_PREFIX=/opt/conda/envs/CryoAtom2; \
    "$ENV_PREFIX/bin/pip" install --no-deps --no-build-isolation "$SRC/CryoAtom"; \
    SITE="$ENV_PREFIX/lib/python3.9/site-packages"; \
    cp -a "$SRC/CryoAtom/CryoAtom2/." "$SITE/CryoAtom2/"; \
    if [ -f "$SITE/CryoAtom2/utils/getp" ]; then mv "$SITE/CryoAtom2/utils/getp" "$SITE/CryoAtom2/utils/getp.upstream-prebuilt"; fi; \
    install -m 0755 "$SRC/CryoAtom/CryoAtom2/src/getp/getp" "$SITE/CryoAtom2/utils/getp"; \
    mkdir -p "$SITE/CryoAtom2/checkpoint" /torchhome; \
    if find "$SITE/CryoAtom2/checkpoint" -name '*.pth' | grep -q .; then \
        echo "FATAL: model weights were baked into the image; that is forbidden" >&2; exit 1; fi; \
    echo "=== [6/6] locks and self-check ==="; \
    conda list -n CryoAtom2 --explicit > /opt/cryoatom/conda-explicit.txt; \
    "$ENV_PREFIX/bin/pip" freeze > /opt/cryoatom/pip-freeze.txt; \
    V="$("$ENV_PREFIX/bin/python" -c 'import CryoAtom2; print(CryoAtom2.__version__)')"; \
    test "$V" = "2.1.1" || { echo "FATAL: version mismatch: $V" >&2; exit 1; }; \
    test -z "$(ls -A "$SITE/CryoAtom2/checkpoint")" || { echo "FATAL: checkpoint dir not empty" >&2; exit 1; }; \
    ldd "$SITE/CryoAtom2/utils/getp" | grep -q 'not found' && { echo "FATAL: getp has unresolved libraries" >&2; exit 1; }; \
    "$ENV_PREFIX/bin/python" -c 'import torch, esm, fm, mrcfile, pyhmmer, Bio, numpy, scipy; assert torch.__version__.startswith("2.1.0"), torch.__version__'; \
    "$ENV_PREFIX/bin/cryoatom" --version; \
    rm -rf "$SRC"; \
    chmod -R a+rX /opt/cryoatom

ENTRYPOINT ["/opt/conda/envs/CryoAtom2/bin/cryoatom"]
