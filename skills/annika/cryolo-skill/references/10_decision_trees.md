# 10 · Decision trees

Operational branching for the skill. All trees assume the hard rules in `SKILL.md §5`.
CLI behavior below is **VALIDATED against crYOLO 1.9.9** (captured live `--help`; smoke
evidence from the validation run, crYOLO section).

## Tree 1 — The config gate (run this for every crYOLO request)

```text
User asks something crYOLO-related
        |
        v
Is the request "concrete"?  (a command, a can/can't-run or support claim,
a workflow recommendation, or device/GPU/CUDA advice for THIS machine)
        |
   no --+--> Answer at HIGH LEVEL from references (what crYOLO is, formats,
        |     license, workflow meaning). No machine-specific claims. Done.
        |
   yes
        |
        v
Does configs/site_config.local.md (or a user-provided report) exist?
        |
   no --+--> Offer to run the read-only probe:
        |       python3 scripts/cryolo_env_probe.py -f markdown -o configs/site_config.local.md
        |     If declined / cannot run -> stay at HIGH LEVEL only (no per-machine
        |     can/can't-run claims). You MAY still show generic, validated command
        |     shapes from refs 03/05, labeled "fill in your own paths; run only after
        |     your own machine is confirmed".
        |
   yes
        |
        v
Is it stale?  (older than stale_after_days, or OS/arch/conda/crYOLO/GPU/docs-pin changed)
        |
   yes -+--> Treat as absent: offer to re-run the probe; otherwise HIGH LEVEL only.
        |
   no
        |
        v
Use support_assessment + os/gpu/cryolo fields -> proceed to Tree 2.
```

## Tree 2 — Support / suitability (from the config report)

```text
Read support_assessment.status (computed per ref 02 rules; this is a per-machine
verdict — never hardcode one host's result):

  blocked   -> Explain WHY (cite the probe reason's source). On macOS/Apple Silicon
               the sourced per-platform fact is "crYOLO is officially unsupported on
               macOS; no NVIDIA/CUDA path on Apple Silicon" — present this as the
               probe's platform outcome, not as a statement about any specific machine.
               Offer high-level explanation + the option of a supported Linux+NVIDIA
               machine. Do NOT present a command as runnable on a blocked machine.
               If a cryolo exe is somehow present on an unsupported platform:
               "may be locally runnable but officially unsupported/untested."

  partial   -> Linux/no-NVIDIA or Windows. State the limitation (GPU accel may be
               unavailable / platform untested) with its source. You MAY emit the
               concrete validated commands with the user's real paths; flag that GPU
               steps may fall back to CPU or fail, and confirm before running on real
               data.

  supported -> Linux + NVIDIA (the validated configuration; see VALIDATION_SUMMARY
               crYOLO section). Proceed to Tree 3 and emit concrete, validated commands
               with the user's real paths. You MAY run real jobs AFTER explicit user
               confirmation (ref 07: confirm before touching real data).

  unknown   -> OS not covered by captured docs. Do not assert support. Offer to capture
               sources for that platform.
```

Also check `cryolo.installed`:

```text
installed:false -> Note crYOLO must be installed first (the skill does not perform
                   blind system-level installs; ref 07). Explain that install steps +
                   license (ref 07) apply. Keep per-machine advice high level until a
                   probe confirms an install.
installed:true  -> Workflow commands (Tree 3) apply directly; the CLI is VALIDATED
                   against crYOLO 1.9.9.
```

## Tree 3 — Workflow selection (gate + support passed)

All commands below are VALIDATED against crYOLO 1.9.9. Front-end is
`cryolo_gui.py {config,train,predict,evaluation,boxmanager}`; the standalone scripts
`cryolo_predict.py`, `cryolo_train.py`, `cryolo_evaluation.py`, `janni_denoise.py`,
`cryolo_boxmanager_legacy.py`, `cryolo_boxmanager_tools.py`, `cryolo_evaluation_tomo.py`,
and `napari_boxmanager` all exist (captured help: `cryolo_gui.py.help.txt`,
`_versions.txt`). Substitute the user's real paths; run only after Tree 2 = supported
(or partial, with caveats) AND explicit confirmation.

```text
What does the user want to do?

  "configure"            -> cryolo_gui.py config CONFIG_OUT BOXSIZE  (refs 03/05).
                            Positionals are exactly `config_out_path boxsize`; the
                            integer IS the box size (validated smoke used 160). Box size
                            maps into model.anchors and max_box_per_image defaults 700
                            in the written JSON. Filter choice is VALIDATED (captured
                            help: cryolo_gui.config.help.txt), -f/--filter
                            {NONE,LOWPASS,JANNI}, default LOWPASS:
                              - LOWPASS (default): low-pass denoise, --low_pass_cutoff 0.1.
                              - JANNI: neural-net denoise; REQUIRES --janni_model PATH
                                (default None); --janni_overlap 24, --janni_batches 3.
                                The denoiser is janni_denoise.py {config,train,denoise}.
                              - NONE: no filtering (then --otf is silently ignored at
                                predict; see Tree 5).
                            Smoke example: cryolo_gui.py config config_cryolo.json 160 --filter NONE

  "pick with a model"    -> cryolo_predict.py (or cryolo_gui.py predict) (refs 03/05).
                            Required: -c/--conf, -w/--weights, -i/--input (one or more
                            folders/images), -o/--output. Common optional: -t/--threshold
                            (default 0.3), -g/--gpu (default GPU 0), -d/--distance
                            (default 0), --minsize/--maxsize (default None), -pbs
                            (default 3), --gpu_fraction (default 1.0), --otf, --cleanup,
                            --skip. (cryolo_predict.py.help.txt / cryolo_gui.predict.help.txt)
        has a model .h5? --yes--> emit the concrete predict command; outputs land under
                                  -o in CBOX/ EMAN/ STAR/ (+ CRYOSPARC/ DISTR/), see ref 04.
                                  Validated smoke command:
                                    cryolo_predict.py -c config_cryolo.json \
                                      -w <general_model.h5> -i mics/ -o out/ -g 0 --otf -t 0.2
                         --no---> a general model file (e.g. a named PhosaurusNet general
                                  model such as gmodel_phosnet_201912_N63.h5) is a real,
                                  named artifact but is NOT shipped by this skill;
                                  do NOT auto-download (ref 07 license/privacy). Point to
                                  the official crYOLO model page (ref 05).

  "train / refine"       -> cryolo_train.py (or cryolo_gui.py train) (cryolo_train.py.help.txt).
                            Required: -c/--conf, -w/--warmup (default 5). Optional:
                            -g/--gpu, -nc/--num_cpu (default -1), --gpu_fraction (1.0),
                            -e/--early (default 10), --cleanup, --ignore_directions.
                            Set config train/valid fields per ref 04.
                              - Train from scratch:   cryolo_train.py -c config.json -w 5 -g 0
                              - Fine-tune a general model: set --warmup 0 and --fine_tune
                                (also -lft/--layers_fine_tune, default 2; requires
                                pretrained_weights in the config "Training options"):
                                    cryolo_train.py -c config.json -w 0 --fine_tune -g 0

  "evaluate"             -> cryolo_evaluation.py (or cryolo_gui.py evaluation)
                            (cryolo_evaluation.py.help.txt). Required: -c/--config,
                            -w/--weights. Typical: -r/--runfile (the runfile from the
                            runfiles/ folder created during training) OR -i/--images +
                            -b/--boxfiles for explicit ground truth; -o/--output
                            (default result_evaluation.html), -g/--gpu (default 0):
                              cryolo_evaluation.py -c config.json -w model.h5 \
                                -r runfiles/<runfile>.json -o result_evaluation.html -g 0

  "visualize / curate"   -> cryolo_gui.py boxmanager (cryolo_gui.boxmanager.help.txt):
                            -i/--image_dir, -b/--box_dir, --wildcard (e.g. *_new_*.mrc).
                            napari_boxmanager also exists (_versions.txt). This launches
                            a GUI: emit/launch it only on explicit user request (not in a
                            headless/batch context), e.g.:
                              cryolo_gui.py boxmanager -i mics/ -b out/CBOX/ --wildcard '*.mrc'

  "import to RELION/cryoSPARC" -> see ref 06. crYOLO STAR output already carries RELION
                            columns _rlnCoordinateX / _rlnCoordinateY (confirmed in
                            out/STAR/synth_0001.star) and is directly RELION-importable.
                            crYOLO also natively writes a cryoSPARC-style coordinate
                            export: predict produces a CRYOSPARC/ output folder
                            (predict.log: "Write cryoSPARC coordinates"). Point the user
                            to ref 06 for the import path; do not invent column maps
                            beyond what is captured.
```

## Tree 4 — License / commercial question

```text
"Can I/my company use crYOLO commercially?"
   -> Surface: non-commercial academic/research only; commercial/operational use
      explicitly prohibited under the Complimentary Science Software License (ref 07).
   -> Say: summary, NOT legal advice.
   -> Direct commercial users to contact the authors via official docs (exact contact = GAP).
   -> Never give a yes/no legal guarantee.
```

## Tree 5 — "It won't run / no GPU / slow"

```text
Read the config report first (Tree 1).
  is_macos:true              -> probe verdict = blocked: crYOLO is officially unsupported
                                on macOS; needs a supported Linux+NVIDIA machine, not a
                                tweak (ref 09). State as a per-platform outcome.
  Linux, nvidia_smi:missing  -> no NVIDIA GPU visible; GPU accel unavailable (ref 09).
  Linux, nvidia_smi:present, slow / OOM
                             -> Surface the CUDA/cuDNN dependency and the probed env
                                vars, and tune the now-validated knobs (do NOT mutate
                                env vars without confirmation; ref 09):
                                  - predict: lower -pbs/--prediction_batch_size
                                    (default 3) to cut GPU memory; cap --gpu_fraction
                                    (default 1.0); pick a free -g/--gpu.
                                  - config: --input_size (default 1024) and -f/--filter
                                    (LOWPASS vs JANNI vs NONE) affect speed/throughput.
                                  - Note: --otf is silently ignored when the config
                                    filter is NONE (predict.log: "you specified --otf ...
                                    filtering is not configured ... crYOLO will ignore
                                    --otf"). Set a real filter or drop --otf.
```
