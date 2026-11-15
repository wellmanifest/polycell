# Ticket 032: Reject console and logging I/O in pure cell implementations

- **ID**: ticket-032
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-console-purity-20261115.

Reject known console/logging operations in pure Python, TypeScript and Rust
implementations. Share the detector between conformance PC008 and package
verification, retaining the existing I/O patterns. Distinguish logging code from
comments and literal text; support Python AST, TS template expressions and Rust
raw strings/lifetimes without runtime dependencies. Keep diagnostic codes and
interface hashes intact; no business-cell, host or transport changes.

## Acceptance criteria

- [x] AC-01: Common print/logging/stream calls in all three languages fail both PC008 conformance and package verification.
- [x] AC-02: Literal/comment text, pure formatting and supported language constructs remain accepted; existing I/O rules remain enforced.
- [ ] AC-03: Regression tests, bounded regeneration/real qualification, parity, TestQL, DB/MCP and governance pass before protected independent publication.

## Validation in progress

The initial three end-to-end gate regressions exposed 30 false acceptances on
old source. `make check test` passes 200 tests on the starting base. All seven
purity tests also pass after extending coverage to rehashed incoming packages and
qualification preflight. Fifteen logging variants fail conformance, package
creation, direct verification and qualification admission; literal/comment data
remains valid. Console parsing covers Python imports/AST, TS template expressions
and regex literals, and Rust raw strings, comments, lifetimes and formatting.

Continue with real qualification, integrated upstream checks, application parity
and protected independent publication. Runtime evidence stays in the private cache.

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
| Estimated effort | 61 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
