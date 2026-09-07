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

### Tutorial and output traps — source checked 2026-09-07

The [v2.1.0 README](https://github.com/YangLab-SDU/CryoAtom/blob/v2.1.0/README.md)
provides 7XHT sequence-guided and 9ENB database-identification examples.
Choose the mode from known polymer classes and sequence coverage, and return
only a NOT-RUN plan. A tutorial download or cloud notebook is not part of this
advisor's execution capability.

In [the pinned output filter](https://github.com/YangLab-SDU/CryoAtom/blob/v2.1.0/CryoAtom2/utils/flood_fill.py),
sequence-guided output masks nucleotide positions when both RNA and DNA
sequences are absent. A protein-only FASTA example must not be treated as a
complete mixed-polymer reconstruction. Plan all applicable sequence inputs,
or the fully sequence-free mode, and require an eventual output polymer check.
This is static source evidence, not a new observed run.

The [pinned build implementation](https://github.com/YangLab-SDU/CryoAtom/blob/v2.1.0/CryoAtom2/build.py)
comments out the `running_time.log` write. Do not promise that file, diagnose
its absence as failure, or treat a log shipped in an example archive as timing
evidence for a later run.

The source creates the chosen output directory with exist_ok behavior, moves/replaces files under it, and deletes intermediates unless the keep flag is used. Never tell a user to reuse a real result directory. This advisor never creates a directory.

## Interpretation

Static source indicates that model confidence is written into the mmCIF B-factor field. It is not an experimental B-factor, proof of accuracy, or a biological conclusion.
