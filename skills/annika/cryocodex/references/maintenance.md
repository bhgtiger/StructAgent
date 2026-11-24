# Maintenance — refreshing this skill

No install, download or GPU job is needed (or authorised) to maintain the documentation. The source review is pinned
to **2026-11-24**: tag `v1.0.0` = `a35e73a72f9cbc2b13cf6f8d95cf963cb704ca17` = `main` on that date.

## 1. Detect change (read-only, network)

```bash
git ls-remote https://github.com/YangLab-SDU/CryoCodex.git                 # main and v1.0.0 were a35e73a… on 2026-11-24
gh api repos/YangLab-SDU/CryoCodex/releases --jq '.[] | "\(.tag_name) \(.published_at)"'
gh api 'repos/YangLab-SDU/CryoCodex/issues?state=all' --jq '.[] | "\(.number) \(.state) \(.title)"'   # 0 issues/PRs on 2026-11-24
curl -sI https://yanglab.qd.sdu.edu.cn/CryoCodex/CryoCodex.pth | grep -iE 'content-length|last-modified|etag'
#   470938660 · Thu, 01 Oct 2026 02:13:30 GMT · "1c11f424-65cbdf6493754" on 2026-11-24
curl -s 'https://api.biorxiv.org/details/biorxiv/10.64898/2026.09.30.755675/na/json' \
  | python3 -c 'import json,sys; print([(c["version"], c["date"], c.get("published")) for c in json.load(sys.stdin)["collection"]])'
curl -s https://pypi.org/pypi/scipion-em-cryocodex/json | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])'   # 0.3.2
```

## 2. If upstream code moved (new commit or tag)

1. `git diff a35e73a..<new> -- predict.sh predict.py grid_utils.py data_processor.py crop_check.py requirements.txt README.md`.
2. Re-derive the option table from the argparse block and the launcher; update [03](03_cli_reference.md) §3/§4, the
   allowlist in `tests/validate_static.py` and the refusals in `scripts/build_cryocodex_command.py`.
3. Re-check the facts the scripts encode (`scripts/mrcheader.py` constants and formulas): input name test, 90° gate,
   resampling extent, 48³ window / 2-voxel margin, crop pad, output names, NSTART placement, mask threshold, score clip,
   `--keep_size` canvas, reverse-interpolation extent; and the safety facts (download trigger, `weights_only=False`,
   `-g` overwrite, `cuda:0`, `--crop_check` prompt).
4. Bump the pin in SKILL.md, [01](01_source_map.md), `scripts/mrcheader.py` (`PIN_COMMIT`) and the probe; re-run the
   runbook on a host before calling anything VALIDATED again.

## 3. If the weights changed (size / ETag / Last-Modified differ)

Treat it as a new model: record the new size and sha256, update `WEIGHTS_BYTES` in `scripts/mrcheader.py`, 01 §1, 02 §4
and 07 §2; re-run R7–R13 of the runbook; note in `lessons.md` that results before/after are not comparable.

## 4. If the preprint is revised or published

Update the citation (01 §2), the trust wording in [00](00_scope_and_trust.md) and [08](08_validation_and_benchmarks.md)
("not peer reviewed" → journal reference), re-read Methods for changed preprocessing (resampling kernel C16,
normalisation) and new statements on input maps, limitations or downstream use.

## 5. After a live validation run (first GPU host)

1. Copy the runbook's `live/<host>_<date>/` evidence back to the evidence pack; write `RESULTS.md` (one line per step).
2. In this skill: paste the live help texts into [03 §6](03_cli_reference.md); turn confirmed rows from "derived/source"
   into "verified on <host>, <date>"; correct any expectation that differed (scripts too); add the measured GPU memory,
   host RSS and wall time for EMD-10387 to [05](05_core_workflows.md); record the weights sha256 in 01 §1 and 07 §2.
3. Record the host in `configs/site_config.local.md` (git-ignored) and lessons in `lessons.md` (no host names).
4. Update the SKILL.md status block and description ("SOURCED … NOT yet validated") only for what was actually run.

## 6. Always

- Keep `lessons.md` and `configs/site_config.local.md`; never overwrite them from a template.
- Run `python3 tests/validate_static.py` and, if the skill-creator skill is present,
  `python3 <skill-creator>/scripts/quick_validate.py <this skill's folder>`.
- Ship no evidence-pack files inside the skill; new findings go into the skill and `lessons.md`.
