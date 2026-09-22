# Trigger tests — openfold3 skill

Queries the `description` should (or should not) cause this skill to load. Used for description optimization
(skill-creator `run_loop.py`) and as a quick sanity list. Mix of phrasings, casual or misspelled prompts, and
near-miss negatives. `tests/validate_static.py` checks that both lists below exist and are not empty.

## should-trigger (true)

- "how do I run openfold3 on a protein + ATP complex"
- "write a run_openfold predict command for my query json, no msa server"
- "what's the difference between run.sh pred --mode exact --det 1 and --mode fast in the openfold3 kit"
- "OpenBind-0 checkpoint: the kit prints WARNING: WEIGHTS unknown, is my download bad?"
- "setup_openfold keeps prompting for a cache dir inside my batch job"
- "my of3 kit job exited 3 with NOT ACTIVE, what does that mean"
- "cofold an RNA aptamer with its small-molecule ligand using OpenFold 3"
- "can openfold3 use my precomputed a3m files instead of the colabfold server"
- "openfold3_ob0 big mode with --n_gpu 4 on one node for a 6000-token complex"
- "which sample is the best one in the openfold3 output folder, is sample_1 the top model?"
- "run align-msa-server on the login node and then predict offline on the GPU node"
- "is the openfold3 optimization kit supported on an RTX 4090?"
- "build the uplifting-biomolecular-modeling openfold3 kit as an apptainer image for our cluster"
- "openfodl3 predict crashed with OOM on an a100 40gb, what now" (misspelled)
- "run OpenFold on this protein-ligand query JSON" (bare "OpenFold" with a cofolding cue)
- "update the openfold3 skill for the new openfold-3 release"

## should-not-trigger (false) — near misses

- "run colabfold_batch on my fasta with AlphaFold2-multimer" (ColabFold skill)
- "predict this monomer with AlphaFold2 and relax it with Amber" (AlphaFold2)
- "boltz predict with affinity for my ligand YAML" (Boltz skill)
- "run the Boltz-2 optimization kit, boltz2-kit pred --mode fast" (same kit repository, but Boltz)
- "run DeepMind's AlphaFold 3 run_alphafold.py on my input JSON" (AlphaFold3 itself; its JSON differs)
- "predict my complex with Chai-1 or Protenix" (other cofolding tools)
- "fold this sequence with ESMFold" (other predictor)
- "just fold this sequence for me" (generic "fold", no tool named: ask which tool; do not assume OpenFold3)
- "set up 5-fold cross-validation for my classifier" (not protein folding)
- "dock this ligand with AutoDock Vina and estimate the binding energy" (docking tool)
- "build a model into my cryo-EM map" (model building, not structure prediction)
- "my PyTorch Lightning training loop runs out of GPU memory" (generic OOM)

## Ambiguity policy — "OpenFold" without "3"

Decision: the description lists `openfold` as a trigger, so a bare "OpenFold" loads this skill. The skill then
disambiguates instead of guessing (SKILL.md intro, one sentence):

- **No version cue, or any OpenFold3 cue** (ligands, ions, RNA/DNA cofolding, query JSON, `run_openfold`,
  `setup_openfold`, OpenBind-0, `of3-ob-…pt`, the kit, `run.sh`): treat it as OpenFold3 v0.5.0, say so in one line
  ("assuming OpenFold3; tell me if you mean the older OpenFold"), then follow the normal probe-first flow.
- **AlphaFold2-era OpenFold cues** (`aqlaboratory/openfold` without `-3`, `run_pretrained_openfold.py`,
  `finetuning_*.pt` or `initial_training.pt` weights, AlphaFold2 `params_model_*` weights, OpenProteinSet training,
  "OpenFold v1"): state that this skill covers OpenFold3 only, write no command for the older tool, point to that
  project's own documentation, and offer OpenFold3 or the AlphaFold2/ColabFold skill as alternatives
  (eval 17 in `evals/evals.json`).
- **Truly ambiguous and the answer would differ** (e.g. "OpenFold weights for my monomer"): ask one short question.

Example prompts under this policy (not counted in the lists above):

- "run openfold on my protein-DNA complex" → loads; treated as OpenFold3.
- "OpenFold run_pretrained_openfold.py with finetuning_ptm_2.pt on a monomer" → may load (keyword); must route out,
  no command.
- "train OpenFold on OpenProteinSet" → may load (keyword); training is out of scope for both tools here; route out.
- "which OpenFold weights should I download?" → loads; ask whether OpenFold3 (OpenBind-0) or the older OpenFold is meant.
