# Ticket 012: Bound Chrome readiness and allow isolated CDP ports

- **ID**: ticket-012
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the polycell harness. Writer: agent:codex, session
polycell-chrome-readiness-20261113.

Repair the native Chrome readiness gate after repeated 20-second CDP startup
timeouts in otherwise passing CI runs. Allow an isolated CHROME_PORT, wait up to
60 seconds by default with bounded probes, detect a dead browser process and
show its log on failure. Limit implementation to Makefile; preserve every CI
and contract gate. Validate delayed readiness, timeout, early process exit and
the real browser on an isolated port before independent publication.
Keep Chrome's temporary socket directory in a short project-relative cache path
so long canonical worktree and executor paths fit Unix socket name limits.

## Acceptance criteria

- [x] AC-01: Chrome launch and CDP consumers use the configured CHROME_PORT.
- [x] AC-02: Delayed startup succeeds within a bounded deadline; dead or unready browsers fail with logs.
- [x] AC-03: Conformance, parity, unit/integration tests, TestQL, browser scenarios and governance pass before independent publication.

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

## Validation

95 tests, conformance, 45 HTTP/gRPC/stdio parity calls, TestQL 5/5 and DB/MCP
integration pass. Before the change, the isolated-port probe failed after
21.951 seconds and showed the hardcoded port mismatch. Four controlled probes
pass with the final implementation: 23-second delayed readiness succeeds in
23.703 seconds, a configured readiness timeout fails in 2.297 seconds, an exited
browser fails in 1.134 seconds with its log, and a stalled HTTP response fails in
3.145 seconds. Real Chrome on port 19223 completes five UI scenarios and 72
steps without console/network errors under the project-bound executor. Its
short relative temporary path fixes the reproduced Unix socket path overflow.
