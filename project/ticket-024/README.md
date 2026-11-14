# Ticket 024: Reject incomplete or invalid parity runs

- **ID**: ticket-024
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-parity-preflight-20261114.

Fail parity when there is no executable matrix, any registered cell lacks a
behavior case, or the case catalog/transport selection is invalid. Validate the
complete catalog and its input/output schemas before dispatching any host call.
Keep explicit valid transport subsets and golden-only coverage working, and
preserve strict output comparison. Do not edit conformance diagnostic codes,
hosts, protobuf, contracts or business implementations.

## Acceptance criteria

- [x] AC-01: Empty/incomplete coverage and invalid selectors/catalogs return a failed parity report with actionable errors before any host call.
- [x] AC-02: Valid default/subset matrices and golden-only cases still execute; CLI failures exit nonzero and HTTP reports expose failed readiness.
- [x] AC-03: Regressions, live three-language positive/negative cases, existing parity, TestQL, DB/MCP and governance pass before independent protected publication.

## Validation

`make check test`: conformance PASS, 166 tests PASS, including 12 new preflight
regressions. The initial 11 tests on old source exposed 18 failed checks and
15 exceptions. The existing strict JSON comparison regression now supplies a
complete registry/schema fixture and confirms all three comparisons execute.

A private golden-only TS/Python/Rust application exercises actual CLI and HTTP
entrypoints. Eight invalid runs (empty/missing/schema-invalid coverage and
duplicate/unknown transports) dispatch zero functions; failing CLI reports exit
1. Five valid runs, including a single-protocol selection and recovery after
regeneration, perform 117 real calls. Source golden files are regenerated through
the generator; no production generated artifacts are patched. Three portable
tests, TestQL 4/4 and DB/MCP pass. Audit counts and complete reports are retained.

Existing demo: parity 45 calls, TestQL 5/5, checkout, guards, persistence, logs and
MCP PASS. Governance PASS. UI, conformance diagnostic codes, hosts, protobuf and
cell interfaces are unchanged. Raw evidence stays in the private cache and final
external artifact report; exact-head trusted review remains required.

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
| Estimated effort | 54 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
