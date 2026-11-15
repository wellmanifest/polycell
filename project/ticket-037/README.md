# Ticket 037: Upgrade Psycopg to avoid PGlite timestamp loader crashes

- **ID**: ticket-037
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, testing
and protected publication of the Forge/Polycell harness. Writer: agent:codex,
session codex-psycopg-compat-20261115. This prerequisite was found during the
separately scoped runtime-copy ticket-036; only the dependency pin changes here.

The pinned Python 3.12/Psycopg 3.3.6 binary runtime repeatedly exits 139 reading
an empty timestamp result from PGlite, including the gateway's invocation list.
Integer-only queries pass. ClientCursor does not fix the failure. The same
bounded reproduction passes after upgrading only Psycopg/binary to 3.3.9 in a
derived image. The server reports no TimeZone startup status; this observation
does not prove the complete upstream native root cause.

## Acceptance criteria

- [x] AC-01: Preserve the bounded old/new driver reproduction, native stacks and integer-only control.
- [x] AC-02: Candidate-pinned environment, regression and live PGlite application gates pass without weakening assertions or changing adapters.
- [ ] AC-03: Exact-head CI, independent trusted review, protected merge and owner cleanup complete.

## Source

The upstream release notes describe subsequent timestamp loader fixes:
https://www.psycopg.org/psycopg3/docs/news.html . The dependency change is
justified by the actual old/new reproduction, not by assuming an identical
upstream bug. No generator calls, cell edits, data migrations or releases.

## Validation before publication

A private environment contains matching psycopg/psycopg-binary 3.3.9 and passes
222 tests plus conformance. A candidate-matching image passes 45 parity calls,
TestQL 5/5 (including the initially empty timestamp query), persisted checkout
over HTTP/gRPC/stdio, logs and MCP. The gateway remains running. No assertions,
timeouts, adapters or schemas changed. Hash-verified Forge/SubLLM wheel metadata
has no incompatible Psycopg constraint; the optional SubLLM range is >=3.2,<4.

Required CI, independent review and terminal cleanup are recorded externally
after the source/carrier freeze; AC-03 remains pending in this author snapshot.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 40/100 |
| Complexity | M |
| Estimated effort | 40 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
