# Static CLI and outputs

Source: static inspection of CryoAtom2 v2.1.0 commit 10fd7f4be3722d6a1ea6646c69e93476014184ab. Confirm every item on a disposable supported fixture before using it operationally.

## Entry point

The registered command is cryoatom with a build subcommand.

## Static flags

- Required map: --map-path, -v, or --v.
- Optional sequences: --protein-sequence-path (-ps/--ps), --rna-sequence-path (-rs/--rs), --dna-sequence-path (-ds/--ds).
- Output: --output-dir (-o/--o); source default is output.
- Device: --device (-d/--d); source code's CPU fallback is not evidence of supported CPU-only performance.
- Optional extras: --mask-path (-m/--m), --protein-fasta-path (-pf/--pf), --na-fasta-path (-nf/--nf), --refine-backbone-path (-r/--r), --keep-intermediate-results (-k/--k), and --config-path (-c/--c).

Do not invent aliases such as --protein-fasta or --hmm-db. Do not recommend source defaults as universal parameters.

## Output risk

The source creates the chosen output directory with exist_ok behavior, moves/replaces files under it, and deletes intermediates unless the keep flag is used. Never tell a user to reuse a real result directory. This advisor never creates a directory.

## Interpretation

Static source indicates that model confidence is written into the mmCIF B-factor field. It is not an experimental B-factor, proof of accuracy, or a biological conclusion.