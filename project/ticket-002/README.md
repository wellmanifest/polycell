# Ticket 002: Reject invalid process guards before dispatch

- **ID**: ticket-002
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested "napraiwaj,scalaj,testuj"
for the Forge/SubLLM and polycell harness. This bounded application fix rejects
malformed process guards before dispatch and evaluates valid guards with JSON
types, distinguishing a missing field from explicit null. The implementation
writer is `agent:codex`, session `polycell-process-guards-20261113`.

The shared parser serves the planner and the conformance checker. No cell,
contract, transport, generated artifact or dependency changes are required.
Publication uses the independent Validator and an exact-head pull request.

## Acceptance criteria

- [x] AC-01: Invalid guards, including a malformed later step, fail before any cell invocation.
- [x] AC-02: False guards stop downstream dispatch; booleans differ from numbers and missing fields differ from null.
- [x] AC-03: `make check` reports invalid guard syntax as PC006; existing valid process contracts pass.
- [x] AC-04: Regression tests, `make check`, `make parity`, TestQL and integration pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 60/100 |
| Complexity | L |
| Estimated effort | 65 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->

## Validation

57 unit tests pass (36 assertions failed before the fix); polycell conformance and governance pass. Rebuilt Docker services pass 45 parity calls, TestQL 5/5, checkout across all three transports, failure guards, persistence and MCP.
