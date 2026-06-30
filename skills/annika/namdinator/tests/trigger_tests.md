# Trigger tests — namdinator skill

Natural-language queries used to check that the skill's `description` triggers
when it should and stays quiet when it shouldn't. The hard cases are the
near-misses: flexible-fitting / cryo-EM queries that belong to a *different*
tool, and Namdinator-adjacent phrasings.

## Should trigger (true)

1. "should i use namdinator for my 4.2 Å cryo-EM map? i have a model thats
   roughly docked already"
2. "what does the -x flag do in Namdinator and should I turn it on for cryo-EM"
3. "namdinator dropped my Zn and the heme from the output pdb, how do I keep them"
4. "my Namdinator run died with 'Bad global bond count' — what now"
5. "is it safe to upload an unpublished map to namdinator.au.dk"
6. "I want to MDFF-fit this homology model into a 6 Å EM map automatically,
   without sitting in front of ChimeraX — what's the simplest pipeline"
7. "plan me a namdinator command for model.pdb + emd map at 3.8 angstrom"
8. "namdinator says atoms are moving too fast, run keeps blowing up"
9. "how do I read last_frame_rsr.pdb vs last_frame.pdb and which one do I keep"
10. "a domain in my model is rotated like 70 degrees out of the density, can
    namdinator pull it in"

## Should NOT trigger (false) — near-misses

1. "set up an interactive ISOLDE session so I can pull this loop into density by
   hand" (→ isolde)
2. "run phenix.real_space_refine on my model against the half-map at 3.1 Å"
   (→ phenix; no MDFF/Namdinator)
3. "rigid-body fit this PDB into my map in ChimeraX and save the fitted coords"
   (→ chimerax)
4. "build waters and fit the ligand into the density in Coot" (→ coot)
5. "which is better for my 2.5 Å map overall — real-space refine, ISOLDE, or
   rebuild in Coot?" (strategy across tools → structural-strategy; only mention
   Namdinator if asked)
6. "what NAMD2 config do I need for a free-energy perturbation MD run" (generic
   NAMD/MD, not Namdinator)
7. "convert my mtz to a ccp4 map" (CCP4/Phenix utility, no fitting)
8. "denoise my cryo-EM map with deepEMhancer" (→ deepemhancer-skill)
9. "pick particles with crYOLO on these micrographs" (→ cryolo-skill)
10. "explain MDFF theory / the Trabuco 2008 method" (background concept, not a
    Namdinator task — answer directly unless they ask about Namdinator)

## Edge calls (judgment)

- "automatic flexible fitting of a model into a cryo-EM map" with no tool named →
  *lean trigger*: Namdinator is a strong default answer, but present alternatives
  (ISOLDE/Phenix) honestly.
- "MDFF" alone, interactive context → likely isolde, not this skill.
