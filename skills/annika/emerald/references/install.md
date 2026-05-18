# Installing Rosetta for EMERALD

EMERALD ships inside the main Rosetta distribution. Minimum version: **2023.06**
(released 2023-02-05).

## 1. License

Rosetta is **free for non-commercial / academic use** but requires a license.

- Go to https://rosettacommons.org/software/download/
- Accept the academic license (fill out the form)
- You'll receive a download link for weekly releases (source + binary)

Commercial users license via the University of Washington CoMotion office —
see the same page.

## 2. Download

Two options, pick one:

- **Binary release** (recommended for Linux x86_64) — extract, done.
- **Source release** — required on macOS (Apple Silicon), and anywhere you
  want to customize the build.

Either way, after extraction you'll have a `rosetta.*/main/` directory. That's
what `$ROSETTA3` must point at.

```bash
export ROSETTA3=$HOME/rosetta.binary.linux.release-371/main
# or wherever you extracted it
```

Persist it in `~/.zshrc` / `~/.bashrc` so the skill's wrappers find it.

## 3. (Source build only) Compile

```bash
cd $ROSETTA3/source
./scons.py -j8 mode=release bin
```

On macOS with Apple Silicon, prefer the Homebrew clang toolchain; GCC builds
are known to mis-link. Expect 30–60 min on 8 cores.

## 4. Verify

```bash
bash skills/annika/emerald/scripts/check_env.sh
# Or from the repo root: bash scripts/check_env.sh (if installed in your agent's skills/)
```

Must print `[OK]` for ROSETTA3, the rosetta_scripts binary, and the GenFF
params file. If it complains about GenFF missing, your release is too old —
grab a newer weekly release.

## 5. (Optional) AmberTools for AM1-BCC charges

The paper's recipe uses `antechamber` for AM1-BCC partial charges. Install
AmberTools via conda:

```bash
conda install -c conda-forge ambertools
```

Without AmberTools, `scripts/make_params.sh` falls back to Rosetta's
`mol2genparams.py`, which uses GenFF's default charges — acceptable for most
cases but not identical to the published protocol.

## References
- Rosetta build docs: https://docs.rosettacommons.org/docs/latest/build_documentation/Build-Documentation
- Supported platforms: https://docs.rosettacommons.org/docs/latest/build_documentation/Platforms
- EMERALD paper (open access): https://www.nature.com/articles/s41467-023-36732-5
