# Ticket 020: Reject non-finite JSON before dispatch

- **ID**: ticket-020
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-finite-json-20261114.

Reject non-finite JSON numbers, including nested values and numeric overflow,
before cell/process dispatch and persistence. Apply the rule to arbitrary `json`
fields and to unused process inputs. Reject malformed numeric HTTP bodies with
400 while preserving finite numbers, null, booleans, arrays, Unicode and quoted
strings such as "NaN". Keep hosts, protobuf, cell contracts and business logic
unchanged; malformed non-JSON inputs are not invocation records.

## Acceptance criteria

- [x] AC-01: Schema validation and direct invocation reject nested non-finite/non-serializable values before dispatch or DB access; ordinary JSON values retain their behavior.
- [x] AC-02: HTTP rejects NaN, infinities and overflowing numbers before routing; process preflight rejects non-finite unused inputs without executing or persisting a run.
- [x] AC-03: Full regressions, live three-language JSON cases, existing parity, TestQL, DB/MCP and governance pass before independent protected publication.

## Validation

`make check test`: conformance PASS, 154 tests PASS (eight new tests). On the
old source those eight tests exposed 45 failed checks. They cover generic JSON
schemas, direct calls, process preflight, unsupported/circular Python values,
strict HTTP number decoding and ordinary JSON values including quoted tokens.

A private assembled application runs JSON echo cells in Python, TypeScript and
Rust using unchanged hosts. Its 120 successful API cell/process calls preserve
ten representative values across HTTP/gRPC/stdio. Ninety invalid requests across
cell, invoke, process and NL routes return 400; invocation/process table counts
are identical before and after. App parity (90 calls), three portable tests,
TestQL 4/4, persistence and MCP (four tools, 13 calls) pass. Source hashes and
full replies/counts are retained in the runtime report.

Existing demo: parity 45 calls, TestQL 5/5, checkout, guards, persistence, logs and
MCP PASS. Governance PASS. UI and cell interfaces are unchanged. Raw evidence
stays in the private cache and final external artifact report; exact-head trusted
review remains the publication boundary.

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
