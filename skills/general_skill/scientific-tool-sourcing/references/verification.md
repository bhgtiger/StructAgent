# Verifying gathered evidence before the hand-off

Gatherers, human or model, produce confident text. The audits in earlier projects found
errors every time: invented aliases, a probe flag that did not exist, stale README
defaults, an error introduced by the project's own distilled notes. Run all of these
checks before writing `HANDOFF.md`. Record the results in `sources/crosscheck/verification.md`.

## 1. Mechanical checks (scripts, ~1 minute)

```bash
SK=<this skill's folder>; P=<project root>
python3 -I $SK/scripts/check_citations.py --root $P --sources sources --sample 15 \
        --report sources/crosscheck/citation_check.txt
python3 -I $SK/scripts/build_manifest.py --root $P --sources sources --max-mb 50
```
- `check_citations.py`: **0 errors required**: every `path:line` resolves and every
  `Verbatim` block matches its lines. Read each warning; fix it or explain it.
- `build_manifest.py` writes `sources/MANIFEST.tsv` (SHA-256 per file, HEAD per clone).
  Exit 1 means a `.pdf` is not a PDF. Re-fetch or record a gap. List files > 50 MB in the
  hand-off; they must not be packaged into a skill.
- For another layout (`artifacts/sources`, `references/`), pass `--sources` and `--prefix`.

## 2. Run logs
- Codex: `logs/codex_<ID>_status.txt` shows `exit=0 failure_events=0`, and `_final.md`
  exists. `run_codex_task.sh` already flags these; never trust exit 0 alone.
- Subagents: each final message has the four required sections. Every path under
  "Files written" exists (`ls` them).
- Gaps reported in final messages appear in `crosscheck/gap_report.md`, not only in chat.

## 3. Eyeball the sample
For each sampled citation printed by `check_citations.py`, open the inventory line that
cites it and judge: does the cited line actually support the claim? A citation can resolve
and still be irrelevant. Take ≥ 15 samples, and add extra ones from P0 areas (CLI options,
defaults, license clauses). Record "n checked / n supported".

## 4. Your own spot-checks of high-risk claims (5–10 claims)
Re-verify these yourself against primary evidence, not against another inventory:
- the pin: `git ls-remote <url> refs/tags/<tag>*` matches the recorded commit;
- 2–3 option defaults that the future skill will rely on, read in the parser source;
- every "this flag/subcommand exists" claim that the docs make and the code does not
  obviously back;
- license / weights terms clause quoted verbatim from the license file or terms page;
- every default network call (data egress), and the flag that disables it;
- any claim that came from a paper, video or issue and is phrased as current tool behavior.

## 5. Independent review (recommended for anything beyond a small tool)
A fresh reviewer that did not gather the material. In Claude Code, use a subagent. From
another orchestrator, use the `invoke-claude-cli` skill (read-only plan mode), or a Codex
run with `-s read-only`. Give it a **compact packet**: the source plan, `crosscheck/gap_report.md`,
`crosscheck/cli_parity.md`, and the HANDOFF draft. Give it read access to `sources/` for
look-ups rather than pasting everything (a deep pass on a big bundle ran out of budget in
cryoAtom). Do not hand it your conclusions. Ask:
1. Which stated facts lack adequate evidence, or rest on a weaker source than the trust ladder allows?
2. Which P0 source classes are missing or thin for the planned v0 skill?
3. Which contradictions between sources are not flagged?
4. What would a skill built from this pack most likely get wrong?
Findings come back as P0/P1/P2 with file references. Fix the P0s, or list them as gaps.

## 6. "Evidence pack ready" criteria
- [ ] Pins recorded (commit SHAs, not tag objects; docs version; fetch dates).
- [ ] Every P0 class in the plan is collected or listed as a gap with a resolution path.
- [ ] `check_citations.py`: 0 errors; warnings explained.
- [ ] `MANIFEST.tsv` written; no fake PDFs; oversized files listed.
- [ ] Sample eyeballed (n / n supported) and high-risk claims spot-checked.
- [ ] `cli_parity.md` (or API parity) and `contradictions.md` exist.
- [ ] `live_verification_checklist.md` exists if no live capture was made.
- [ ] Gathering is reproducible: `tasks/` briefs + `logs/`, or a `logs/fetch_commands.md`
      for inline gathering (Job_001 `scripts/` folders were empty in earlier projects).
