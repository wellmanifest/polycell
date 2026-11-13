# Ticket 007: Regenerate cells from actionable qualification feedback

- **ID**: ticket-007
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing fixes, testing
and merging the Forge/SubLLM and polycell harness. Writer: agent:codex,
session polycell-forge-feedback-20261113.

Preserve actionable host/schema/behavior diagnostics, clarify Python dictionary
and source-file output rules, and add an opt-in loop of at most three complete
proposals against a frozen trusted oracle. Publish a candidate only after
qualification. Provider failures stop and retain the native audit.

## Acceptance criteria

- [x] AC-01: Qualification identifies host failures and behavioral mismatches by case.
- [x] AC-02: Bounded regeneration uses frozen inputs and publishes only the accepted candidate.
- [x] AC-03: Failed proposals remain auditable and never publish an application candidate.
- [x] AC-04: Unit, conformance, parity and real Forge/SubLLM qualification checks pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 56/100 |
| Complexity | M |
| Estimated effort | 57 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->

## Validation

76 unit tests and conformance pass; affected tests pass after the final provider-error handling change. Governance, 45 parity calls, TestQL 5/5 and DB/MCP integration pass. A live qwen3-coder:30b invocation generated an independently qualified Python cell on attempt 2 (9/9 cases). The accepted package was committed, transferred through Git bundle, cloned, qualified again (9/9), and assembled into an application passing 3 portable tests. No model-generated function body was manually patched.

Opt-in usage: `python tools/polycell/forge.py PACKAGE --out NEW_PACKAGE --audit NEW_AUDIT --model MODEL --oracle TRUSTED_PACKAGE --image WORKER_IMAGE --attempts 3`. Existing proposal and archive-replay commands remain available.
