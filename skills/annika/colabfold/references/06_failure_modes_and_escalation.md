# Failure modes and escalation

High-risk facts:
- Default MSA modes can use a remote server; model weights may auto-download.
- Public MSA retention/privacy terms were not established in the source bundle.
- overwrite-existing-results help text conflicts with source semantics.
- zip removes artifacts after archiving.
- local database setup is large and resource-intensive.
- current issue tracker has MSA timeouts, GPU/MLIR, and memory-mapping reports; these are signals, not support answers.

Escalate or defer when:
- remote privacy/retention, license, or data-use terms matter;
- user wants execution, installation, upload, file modification, result parsing, or server setup;
- user wants AF3/alternate-model workflows;
- a command depends on uncertain flag semantics;
- confidence is being used to justify a high-stakes biological claim.

v0 can surface the uncertainty but must not manufacture a workaround.