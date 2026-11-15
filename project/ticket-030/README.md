# Ticket 030: Retry rejected generated package contents within proposal budget

- **ID**: ticket-030
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-proposal-retry-20261115.

Treat verification failures of newly written package contents as rejected model
proposals, allowing the existing bounded whole-file feedback loop to continue.
Keep operational provider/filesystem failures and destination collisions fatal.
Introduce a ValueError-compatible package-content validation error at the
verification boundary; let the Forge adapter classify it as ProposalRejected.
Preserve rejected provider artifacts, attempt limits and independent qualification
before publication. Scope is the package writer, Forge adapter and their tests.

## Acceptance criteria

- [x] AC-01: Rejected generated contents, including known I/O and oversized files, consume bounded attempts with diagnostics and whole-file feedback.
- [x] AC-02: Operational write/provider failures and path collisions stop once; rejected candidates never publish or reach qualification.
- [x] AC-03: Unit regressions, controlled three-language regeneration with real qualification, parity, TestQL, DB/MCP and governance pass before independent protected publication.

## Validation

`make check test`: conformance PASS, 193 tests PASS, including six new regression
methods. On old source those methods exposed one failure and five errors. They
cover known I/O across Python/TS/Rust, oversized contents, bounded exhaustion,
operational write errors, collisions and a ValueError-compatible schema rejection.

Controlled full-file provider replies exercise the real proposal adapter: the
first file violates an existing I/O rule, and the second is independently
qualified in the pinned networkless compiler sandbox for each language. Each
successful run has two provider replies, one real qualification, retained first
bundle/diagnostic and whole-file feedback. The accepted one-file packages pass
Git bundle/clone roundtrips and joint assembly with conformance PASS.

Three negative controls publish nothing: two rejected attempts exhaust the
budget, an existing destination is preserved after one reply, and an actual
unprivileged filesystem permission failure stops after one reply. Source hashes,
qualification receipts, Git commits and complete attempt reports are retained.
Provider responses are seeded fixtures; the probe makes zero native inference calls.

Existing demo: parity 45 calls, TestQL 5/5, HTTP/gRPC/stdio persistence, checkout,
guards, logs and MCP PASS. Governance PASS. Evidence remains in the private cache
and external report; exact-head trusted approval is required for publication.

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
