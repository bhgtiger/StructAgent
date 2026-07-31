# Scope and safety

## Capability boundary

Allow explanation, config inspection, read-only probing, opt-in live `--help` capture, command planning, local result inspection, and approval-gated prediction execution. Keep software installation, model-weight/database download, remote MSA/template submission, scheduler/GPU execution, and destructive output options behind separate explicit confirmation.

A config is evidence, not authorization. A successful fixture validates only the recorded version, launcher, model type, MSA mode, host/profile, and date.

## Privacy

Assume protein sequences, alignments, templates, job names, and result metadata may be confidential. Remote MSA modes and `--templates` can send data off-host. Public service retention and processing terms were not established from the collected official source set. Default to no remote submission; require per-sequence approval even when the config says `per_job_approval`.

For confidential work, prefer an approved local A3M/local-database route or `single_sequence`, and explain that reduced evolutionary information can reduce prediction quality. Local MMseqs2 databases are substantial infrastructure, not a quick offline toggle.

## Destructive and uncertain behavior

- `--zip` archives then deletes most original artifacts. Never add it silently.
- `--overwrite-existing-results` has ambiguous v1.6.2 wording/flow. Keep it out of generated commands until a disposable behavioral test resolves it.
- Use a fresh result directory. If a path exists, stop and ask whether to preserve, version, or replace it.

## Scientific interpretation

Treat pLDDT as local confidence, PAE as relative-placement uncertainty, and pTM/ipTM as model confidence signals. They are not experimental validation. Do not infer binding, stoichiometry, state, affinity, or mechanism without orthogonal evidence and expert review.

## Licenses and citations

ColabFold code is MIT-licensed, while trained weights and dependencies have separate terms. Configuration does not grant rights to install, download, redistribute, or use weights. Record upstream versions, citations, and license decisions for each deployment.