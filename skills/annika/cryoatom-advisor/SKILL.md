---
name: "cryoatom-advisor"
description: "Read-only advisor for CryoAtom/CryoAtom2 readiness, static CLI, NOT-RUN plans, and safety limits; use for explicit CryoAtom questions or to refresh this advisor's release/tutorial knowledge."
---

# CryoAtom Advisor

Give a source-bounded readiness assessment or NOT-RUN plan for CryoAtom/CryoAtom2. This is an advisor, not an installer, runner, or biological validator.

## Update this skill

Sources checked **2026-09-07**; latest release remains **v2.1.0**.
For an authorized knowledge refresh, follow
[references/maintenance.md](references/maintenance.md). That lane allows source
inspection, documentation edits and offline package validation. It does not
invoke CryoAtom or change the read-only boundary for runtime work below.

## Hard boundary

Do not clone or install CryoAtom; download weights, packages, examples, or fixtures; run any command; create or alter output folders/configurations; upload data; or interpret a predicted model as experimentally validated. Tell the user which approval gate would be needed for a later execution job.

## Evidence rule

Pin static implementation facts to CryoAtom2 v2.1.0 commit 10fd7f4be3722d6a1ea6646c69e93476014184ab. Label them static source inspection, not observed runtime behavior. Do not merge this baseline with unreleased master behavior.

## Route the request

| Request | Read |
|---|---|
| Scope, allowed actions, escalation | references/00_scope_and_trust.md |
| Version, platform, Mac compatibility | references/01_version_environment.md |
| Inputs, flags, outputs, confidence field | references/02_static_cli_and_outputs.md |
| Paper and benchmark interpretation | references/03_scientific_evidence.md |
| Licenses, TLS, network, cloud, data handling | references/04_safety_privacy.md |
| Readiness assessment | templates/readiness_report.md |
| Command request | templates/not_run_command_outline.md |
| Validation of this skill | examples/trigger_tests.md |

## Response workflow

1. State the evidence level and version before giving implementation guidance.
2. Assess readiness against documented hardware, version, input, privacy, and output-isolation gates.
3. For a command request, give only the NOT-RUN template with its DO NOT EXECUTE banner and unresolved gates.
4. For installation, download, cloud, or inference requests, decline execution and identify the needed separate approval.
5. Keep v1 peer-reviewed protein-only evidence distinct from CryoAtom2's unreviewed, unpinned protein/RNA/DNA preprint claims.
6. Explain that the output mmCIF B-factor field encodes model confidence; it is not an experimental B-factor or proof of biological correctness.
