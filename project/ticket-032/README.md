# Ticket 032: Reject console and logging I/O in pure cell implementations

- **ID**: ticket-032
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
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
- [x] AC-03: Regression tests, bounded regeneration/real qualification, parity, TestQL, DB/MCP and governance pass before protected independent publication.

## Validation

The initial three end-to-end gate regressions exposed 30 false acceptances on
old source. After integrating published PR #31, `make check test` passes 202
tests. All seven purity tests cover rehashed incoming packages and
qualification preflight. Fifteen logging variants fail conformance, package
creation, direct verification and qualification admission; literal/comment data
remains valid. Console parsing covers Python imports/AST, TS template expressions
and regex literals, and Rust raw strings, comments, lifetimes and formatting.

Controlled full-file provider replies exercise the real Forge bounded loop:
each language rejects logging, preserves feedback, then accepts and qualifies
the replacement in Docker without networking. Three one-source-file packages
pass Git commit/bundle/clone and joint assembly/conformance. Exhaustion,
destination collision and a real filesystem permission failure publish nothing.
These checks use seeded replies, with zero native inference calls.

The integrated application passes 45 parity calls, TestQL 5/5, three-language
checkout, database persistence, logs and MCP. Governance passes without errors
or warnings. The detector recognizes known APIs; it is not a formal proof of
purity or a substitute for executable qualification. No cell, host or transport
interfaces change. Runtime evidence stays in the private cache. Publication uses
exact-head independent review and the protected merge controller.

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
