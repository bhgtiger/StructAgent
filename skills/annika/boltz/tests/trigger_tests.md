# Trigger tests — boltz skill

Queries the `description` should (or should not) cause this skill to load.
Used for description optimization (skill-creator `run_loop.py`) and as a quick
sanity list. Mix of phrasings, casual/typo'd, and near-miss negatives.

## should-trigger (true)

- "how do I run boltz on a protein sequence to get its structure"
- "set up a yaml for boltz with a protein and a ligand and predict the complex"
- "boltz2 gave me affinity_pred_value -1.2, is that a strong binder?"
- "boltz predict crashed with CUDA out of memory on a 2080 ti, what now"
- "can I use --use_msa_server for an unpublished antibody sequence?"
- "should I use boltz-1 or boltz-2 for protein-ligand binding affinity"
- "my colabfold MSA step keeps failing in boltz, how do I use a custom a3m"
- "install boltz on our GPU node and run a quick structure prediction"
- "what do the confidence_score / iptm / ligand_iptm fields in boltz output mean"
- "I have 150 ligands for one target, how do I screen them with boltz affinity"

## should-not-trigger (false) — near misses

- "run alphafold3 on this sequence" (different tool)
- "predict protein structure with ESMFold / Chai-1" (different tool)
- "set up a colabfold notebook for an MSA, nothing to do with boltz" (MSA-only)
- "dock this ligand with AutoDock Vina and estimate binding energy" (docking tool)
- "what's the binding affinity from my ITC experiment" (wet-lab data, not Boltz)
- "convert this cif to pdb with gemmi" (file conversion, not Boltz)
- "build a model into my cryo-EM map" (model building, not Boltz)
- "lightning training loop is OOMing on my own pytorch model" (generic torch OOM)
