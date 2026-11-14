# Ticket 017: Reject malformed and mismatched host response envelopes

- **ID**: ticket-017
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-host-envelopes-20261114.

Reject malformed host envelopes consistently at the shared transport boundary.
Require a JSON object, strict boolean status, expected URN/language, required
response fields and finite JSON-compatible values. Keep valid host success and
failure responses working. Convert violations into the normal structured
transport failure before process execution or persistence can treat them as
success. Do not edit hosts, protobuf, cell contracts or business implementations.

## Acceptance criteria

- [x] AC-01: Invalid envelope shapes, status/metadata values and response identity fail closed across HTTP/gRPC/stdio; valid responses remain accepted.
- [x] AC-02: Gateway/process/API regressions and live malformed-host cases demonstrate structured failure, no downstream execution and failed persistence.
- [x] AC-03: Full regressions, conformance, real three-language parity, TestQL, DB/MCP and governance pass before independently protected publication.

## Validation

`make check test`: conformance PASS, 137 tests PASS (14 new tests). The first
11 regressions on the old source produced 148 failed checks and 24 exceptions.

Three committed wire tests use actual HTTP, gRPC and stdio hosts behind the
gateway API and a temporary SQLite database. Their 78 API/process calls cover
66 malformed-response rejections, six valid business failures and six successes.
They check HTTP status, requested identity, failed invocation/process persistence,
exact receipts, stopped downstream execution, and absence of successful result
rows after failure. gRPC covers malformed values representable by its typed
envelope; HTTP and stdio additionally cover invalid status and object shapes.

Existing three-language demo: parity 45 calls PASS; TestQL 5/5 PASS;
checkout, guard stop, persistence, invalid inputs, logs and MCP PASS on the
isolated Compose project. Governance PASS. UI and cell interfaces are unchanged.
Raw logs are retained in the private cache; final publication evidence belongs
in the external artifact report and trusted exact-head delivery receipt.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 52/100 |
| Complexity | M |
| Estimated effort | 51 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
