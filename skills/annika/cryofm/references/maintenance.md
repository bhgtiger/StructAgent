# Maintenance — refreshing this skill

No runtime probe is needed to maintain the documentation; nothing here authorises an install, download or GPU job.

## 1. Detect change (read-only, network)

```bash
gh api repos/ByteDance-Seed/cryofm/branches --jq '.[] | "\(.name) \(.commit.sha)"'     # main 64486814…, unstable 6792340d…, gradio-demo bacde8d1…
gh api repos/ByteDance-Seed/cryofm/tags; gh api repos/ByteDance-Seed/cryofm/releases    # both [] on 2026-10-08
gh api 'repos/ByteDance-Seed/cryofm/issues?state=all' --jq '.[] | "\(.number) \(.state) \(.title)"'
curl -s https://huggingface.co/api/models/ByteDance-Seed/cryofm-v2 | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["sha"], d["lastModified"])'
curl -sI https://bytedance-seed.github.io/cryofm/docs/model-guides/cryofm2/quick-start.html | grep -i last-modified   # 23 Jan 2026
curl -s 'https://api.biorxiv.org/details/biorxiv/10.64898/2025.12.29.696802/na/json' | python3 -c 'import json,sys; d=json.load(sys.stdin)["collection"]; print([(c["version"], c["date"], c["published"]) for c in d])'
```

## 2. If `main` moved

1. `git diff 6448681..<new> -- src/cryofm/cli.py src/cryofm/projects/cryofm2/ relion/relion_wrapper.py user-guide/docs/`.
2. Re-derive flags from the argparse blocks; recapture live `--help` on the target; update [03](03_cli_reference.md)
   and the whitelist in `tests/validate_static.py`.
3. Check whether the four documented-command bugs (03 §6), the `--norm-grad` assertion, the origin reset
   (`save_mrc(..., np.array([0,0,0]))`), the 1.5 Å constant, the final-iteration `ValueError` and the `--num_processes`
   drop still hold; move fixed items from "hazards" to "history".
4. Rebuild the site image only with consent (the site's build job after updating the tarball, its sha256 and the lock);
   re-run the smoke test; update `configs/site_config.local.md` (sha256, job ids, numbers), refresh
   `configs/site_config.example.md` from it (sanitized) and SKILL.md's "Update this skill" line.

## 3. If the HF revision moved

Compare per-variant `config.yaml` blob ids and `model.safetensors` LFS sha256 with [01](01_source_map.md). New
weights → refetch (`hf download --revision <new>`, or the site's fetch script), re-verify sha256, re-run the fixture, bump the
pin everywhere. New variants → add rows to 11 §2 and the launcher shorthand.

## 4. If the paper is published or revised

Update the tier wording in [00](00_scope_and_trust.md), [08](08_outputs_and_validation.md), [09](09_evidence_and_benchmarks.md)
("unrefereed preprint" → journal reference), re-read Methods for changed settings, and record whether the public code
gained the paper-only features (`keep_lowres`, adaptive λ, final-iteration skip).

## 5. Always

- Keep `lessons.md` and `configs/site_config.local.md`; never overwrite them from a template.
- Run `python3 tests/validate_static.py` (frontmatter, flag whitelist, script `--help`, fixture header tests) and
  `python3 <skill-creator>/scripts/quick_validate.py <this skill's folder>` (if the skill-creator skill is present).
- Bump the dates in SKILL.md ("Source review", "VALIDATED") only after the corresponding check actually ran.
- The evidence archive ([01 §3](01_source_map.md), not bundled) is a 2026-10-08 snapshot; new findings go into the skill
  and `lessons.md`, not into that archive.
