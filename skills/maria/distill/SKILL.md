# Distill Skill

End-of-session reflection. Maria reviews what she did, updates persistent state, and improves her approach.

## Trigger
Manual — user says "distill", "reflect", "summarize session", "ready for /reset", or similar.

## Process

### 1. Update working.md (CRITICAL — do this first)
Write `memory/working.md` with:
```markdown
# Working (current state)

## Current Focus
- (what project/task is active, key file paths)

## Open Loops
- (max 5 unfinished items, drop oldest when overflow)

## Next Actions
- (what the next session should do first)
```
Use `exec` (cat/tee) to write — the Edit tool can't resolve symlinks.
This is what survives /reset. If you skip this, the next session starts blind.

### 2. Update PROFILE.md
Set the active project and loaded context so the next session routes correctly.

### 3. Session Review
- List all papers read this session
- Identify themes, patterns, surprises

### 4. Update Project Knowledge
For each project touched this session:
- Update `connections.md` with new relationships discovered
- Add any new topic clusters
- Flag contradictions or gaps in the literature

### 5. Self-Improvement (optional)
Review and update if needed:
- `skills/reading/SKILL.md` — add domain-specific reading tips learned
- `memory/` — store key insights that span projects

### 6. Generate Summary
Produce a session summary for the user:
```markdown
## Session Summary — {date}

### Papers Read: {count}
{list with one-line TL;DR each}

### Key Insights
- {cross-cutting insights from this session}

### Knowledge Gaps Identified
- {what's missing, what to read next}

### Suggested Next Reads
- {based on gaps and connections found}
```

Also save the summary to the active project folder as `SESSION_SUMMARY.md` for continuity.

## Notes
- This is the ONLY time Maria modifies her own skill files
- Keep self-modifications small and targeted
- If a fundamental approach change is needed, flag it for the user rather than auto-modifying
- Don't over-optimize — the distill step should take 2-3 minutes, not 20
- **working.md is the single most important output** — everything else is optional
