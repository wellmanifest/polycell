# Ticket 014: Preserve JSON types and numeric precision in qualification

- **ID**: ticket-014
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-json-comparison-20261113.

Make behavior comparison preserve JSON boolean types and integer precision.
Share one comparator between gateway parity and the trusted package worker;
the latter must use the mounted harness rather than a cached runtime image's
gateway module. Keep the existing strict 1e-9 absolute numeric tolerance, pure
cell contracts, host interfaces and independent oracle boundary unchanged.

## Acceptance criteria

- [x] AC-01: JSON booleans differ from numbers, nested shapes stay exact, and large integers are not rounded during comparison.
- [x] AC-02: Parity and real container qualification reject altered JSON values while accepting valid numeric tolerance.
- [x] AC-03: Regression tests, conformance, parity, TestQL, DB/MCP integration and governance pass before independent publication.

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

## Validation

105 tests and conformance pass, including ten comparison/qualification/parity
tests. Before the fix those tests produced 12 failing subcases and four errors.
Two real Docker qualifications incorrectly accepted changed boolean and large
integer values before the fix; both reject the same unchanged candidate bytes
afterward. An exact implementation, a near-float implementation and its Git
bundle clone qualify against the same frozen three-case oracle. The existing
cached evaluator image is unchanged, proving the mounted harness supplies the
correct comparison. Three assembled applications make 27 real HTTP/gRPC/stdio
calls and detect both changes consistently. Existing three-language parity
passes all 45 calls; TestQL 5/5, DB/MCP integration and governance pass.
