# 07 — Codex portability & pipeline integration

## Using this skill under Codex

The skill is **optimized for Claude** but built to be **Codex-compatible**:

- **Frontmatter** is the universal `name` + `description` only — the two fields
  both Claude and Codex read for triggering. No Claude-specific frontmatter keys
  that a Codex loader would choke on.
- **Scripts are portable:** `modelangelo_env_probe.py` is stdlib-only Python 3;
  `install_modelangelo.sh` / `verify_modelangelo.sh` are POSIX-ish bash that
  resolve paths relative to the script and auto-locate `conda.sh`. They don't
  assume a Claude or Codex harness.
- **`agents/openai.yaml`** carries Codex UI metadata (`display_name`,
  `short_description`, `default_prompt` mentioning `$modelangelo`). Codex reads
  it; Claude ignores it.
- **No absolute paths** to a specific skills root are baked into the references;
  routing is by relative `references/NN_*.md`.

To install for Codex: copy the folder into `~/.codex/skills/` (or
`$CODEX_HOME/skills`), **excluding any private local config** — e.g. `rsync -a
--exclude 'configs/*.local.md' modelangelo ~/.codex/skills/`. `site_config.local.md`
records a specific machine and must not travel with the skill (regenerate it per
target with the probe). The Codex `skill-creator` lives at
`~/.codex/skills/.system/skill-creator`; its `quick_validate.py` can validate the
copy. The Claude copy lives at `~/.claude/skills/modelangelo` (auto-discovered)
and is the canonical one to edit; mirror changes into the Codex copy if you keep
both (as the user does for `topaz`).

Differences to keep in mind if running under Codex:
- Codex skill guidance discourages extra docs (README/CHANGELOG) inside a skill —
  this skill has none; `lessons.md` is an internal running log, not user docs.
- The skill-creator **eval loop** (with-skill vs baseline subagents, eval-viewer)
  is a Claude/Anthropic workflow; under Codex, validate structurally with
  `quick_validate.py` and forward-test manually.

## RELION 5 integration (important, non-obvious)

RELION 5 runs ModelAngelo from a **GUI job**, but it does **not** call the
`model_angelo` PATH binary — it **imports `model_angelo` as a Python module**
from the Python environment RELION was compiled against. Consequences:

- A standalone `model_angelo` on PATH (route 1) is **not sufficient** for RELION
  integration. RELION must be built/configured so that `import model_angelo`
  works inside *its* Python env.
- Build RELION with `-DPYTHON_EXE_PATH=<path/to/python>` pointing at the env that
  has ModelAngelo (RELION's docs recommend a Miniforge / `relion-5.0` conda env),
  and set the weights location via `-DTORCH_HOME_PATH=<dir>` (or `TORCH_HOME` in
  the environment). Missing this yields `ModuleNotFoundError: No module named
  'model_angelo'` (and similarly for `relion_classranker`).
- In the RELION GUI ModelBuilding job: I/O tab takes a B-factor-sharpened map +
  a protein FASTA and a "Which GPUs to use" field (e.g. `0,1,2,3`); a **Hmmer**
  tab toggles "Perform HMMer search?" with a "Library with sequences" FASTA and
  an "Alphabet" (amino). Reported tutorial runtimes: ~18 min (with sequence),
  ~12 min (no-seq + HMMer) on four GTX 1080s — *dataset-specific*, not a
  benchmark.

So for "install ModelAngelo for use *inside RELION 5*", the target env is
RELION's Python env, not a standalone `model_angelo` env; set `TORCH_HOME` for
that env and verify `python -c "import model_angelo"` succeeds there.

## CCP-EM / course environments

The CCP-EM Doppio tutorial drives ModelAngelo entirely through its GUI with
install/PATH/queue/weights all pre-staged by the course environment — there are
no raw install commands to copy. Useful as a public **fixture** (EMD-18645, 2.2 Å;
UniProt Q8CZ28; proteome UP000038237) for a future build test, not as an install
recipe.

## Downstream handoff (always)

Installing ModelAngelo enables *building*; it does not finish a structure. After
a build (a separate, out-of-scope step), route outputs to refinement
(Servalcat/Phenix real-space) and validation (MolProbity geometry, Q-score/
EMRinger, manual inspection of low-confidence regions, termini, flexible loops,
ligands/glycans/cofactors which ModelAngelo does not build). The per-residue
confidence/B-factor column guides inspection but is **not** validation
(`references/00`).
