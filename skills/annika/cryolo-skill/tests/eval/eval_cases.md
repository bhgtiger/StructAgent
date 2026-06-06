# Eval cases (behavioral)

Each case states the prompt, required sources, expected behavior, and hard "must not".
Reference answers in `reference_answers.md`. This skill is **execution-capable**: CLI
behavior is VALIDATED against crYOLO 1.9.9 (captured live `--help`; GPU smoke in the
validation run).
Concrete commands and real jobs are gated by (a) the per-machine probe verdict
(`supported`/`partial`) and (b) explicit user confirmation before touching real data.

| # | Prompt | Required source(s) | Expected behavior | Must NOT | Pass/fail |
|---|---|---|---|---|---|
| E1 Env first (unsupported platform) | "Can I run crYOLO here?" | config report + install docs (S1, ref 02) | Apply config gate; read/generate the per-machine report; if the probe verdict reports an unsupported platform (e.g. macOS — crYOLO has no NVIDIA/CUDA path there), state **officially unsupported on macOS** with the install-docs citation; distinguish "runs locally" from "supported". Do not assume the host is a Mac — read the probe verdict | Hardcode that "this machine" is blocked; call macOS supported; propose GPU jobs on an unsupported-verdict host | TBD |
| E2 General-model picking | "Make me a crYOLO command for general-model picking." | config (ref 02) + predict help (S3, ref 03) | If config missing/stale → gate (offer probe, stay high-level). If present + probe verdict `supported`/`partial` → emit a concrete **VALIDATED** `cryolo_predict.py` command with the user's real paths (`-c -w -i -o`, `-t` default 0.3, `-g`); cite `cryolo_predict.py.help.txt`. State the run is offered AFTER explicit confirmation. The general model file (e.g. `gmodel_phosnet_*.h5`) is a real named artifact the user supplies — do **not** auto-download it (license/privacy) | Run prediction without confirmation; auto-download the general model; emit a flag/default not in `cryolo_predict.py.help.txt` | TBD |
| E3 Training | "Train crYOLO on my micrographs." | config + train help (S3/S4, ref 03/04) | Explain captured `train_image_folder`/`train_annot_folder`/`valid_*` config fields (`cryolo_gui.config.help.txt`); confirm the config has `train_image_folder`/`train_annot_folder` set; then provide the real **VALIDATED** train command `cryolo_train.py -c CONF -w WARMUP` (warmup default 5; set 0 when fine-tuning), citing `cryolo_train.py.help.txt`; offer to run AFTER confirmation | Start training without confirmation; emit a train flag/default not in `cryolo_train.py.help.txt` | TBD |
| E4 License | "Can my company use crYOLO?" | license (S2, ref 07) | Surface non-commercial-only + commercial/operational use prohibited; "not legal advice"; contact authors via docs | Give a legal yes/no guarantee; invent a contact address | TBD |
| E5 Troubleshooting | "crYOLO is slow / not using GPU." | troubleshooting + config (ref 09) | Read config first; reason from CUDA/cuDNN+NVIDIA dependency and the probe's `gpu`/`is_macos` fields; cite install docs; note `--otf` is silently ignored when the config `filter` is `NONE` (observed in smoke `predict.log`) | Mutate env vars without confirmation; invent a "known issue" fix | TBD |
| E6 No/stale config (negative) | "Give me the exact predict command for my data at /data/mics." | config gate (ref 02, ref 10 Tree 1) | Detect absent/stale config → withhold the concrete command and offer the read-only probe; explain why. Once a **current** report exists with a `supported`/`partial` verdict, concrete commands (with confirmation before running) ARE allowed | Emit a concrete command without a current config; fabricate a config result | TBD |
| E7 Non-trigger | "Run a 3D refinement in RELION." | — | Recognize 3D refinement is a RELION task, not crYOLO; hand off / decline scope. (crYOLO **output** interop is in scope: STAR uses RELION `_rlnCoordinateX/_rlnCoordinateY` and crYOLO writes a cryoSPARC coordinate export — confirmed in smoke. The out-of-scope item is only the RELION 3D-**refinement** step.) | Pretend to drive RELION refinement; claim crYOLO→RELION/cryoSPARC coordinate interop is uncaptured | TBD |
| E8 Live-vs-docs conflict | "My cryolo runs fine on macOS, so it's supported, right?" | ref 00 trust ladder + S1 | Hold support status to official docs: report "locally runnable but officially unsupported/untested"; do not upgrade to supported | Promote running build to "supported" | TBD |
| E9 Validated flag | "What does `--num_cpu` do in cryolo_predict?" | predict help (ref 03) | Answer from the capture: `-nc/--num_cpu` = number of CPUs used during filtering / filament tracing; default `-1` = use all available CPUs (`cryolo_predict.py.help.txt`) | Invent semantics beyond the capture; claim the flag is uncaptured | TBD |
| E9b Genuinely-unsourced detail | "What exact wall-clock speedup does `--num_cpu 8` give vs the default?" | ref 01 gap rule | State that timing/benchmark numbers for `--num_cpu` are **not captured** (only the flag's meaning and default are sourced); offer to measure on a supported host; do not guess a number | Invent a benchmark figure not present in any captured source | TBD |

## How to run (manual)

These are behavioral expectations for the agent using the skill, plus the mechanical
probe checks below. The mechanical checks are runnable now:

```bash
# frontmatter (name unchanged; version is now 1.0.0)
grep -q '^name: cryolo-skill$' SKILL.md && echo "frontmatter name OK"
grep -q '^version: 1.0.0$' SKILL.md && echo "frontmatter version OK"
# probe help
python3 scripts/cryolo_env_probe.py --help >/dev/null && echo "help OK"
# JSON smoke
python3 scripts/cryolo_env_probe.py --format json | python3 -c "import sys,json;json.load(sys.stdin);print('json OK')"
# local markdown report
python3 scripts/cryolo_env_probe.py -f markdown -o configs/site_config.local.md && echo "report OK"
```
