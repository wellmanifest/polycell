# Ticket 019: Bound stdio requests and retire failed hosts

- **ID**: ticket-019
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-stdio-deadlines-20261114.

Bound stdio request I/O and lock waits, matching the existing ten-second HTTP
and gRPC budget. Retire a host after timeout, EOF or malformed JSON so its
remaining output cannot answer another request. Recover only on a later explicit
call; never replay a request whose execution status is unknown. Make cached host
creation atomic and release owned processes/pipes/workers on shutdown. Preserve
valid long-lived stdio calls and process failure persistence. Keep hosts,
protobuf, cell contracts and business implementations unchanged.

## Acceptance criteria

- [x] AC-01: Silent hosts, partial replies and blocked writes produce bounded structured failures; dead/malformed hosts are retired without automatic replay.
- [x] AC-02: Later calls recover without stale replies, queued deadlines preserve in-flight calls, concurrent first callers share one host, and process timeouts persist failure and stop downstream execution.
- [x] AC-03: Full regressions, conformance, real three-language parity, TestQL, DB/MCP and governance pass before independently protected publication.

## Validation

`make check test`: conformance PASS and 146 tests PASS, including nine new tests.
The first seven regressions on the old code produced eight failed checks and
one exception; watchdog cleanup prevented hung tests from leaking fixture hosts.

Real subprocesses cover silent/partial responses, blocked writes, EOF, malformed
JSON, recovery without replay, shared host creation for six concurrent callers,
queued deadlines and persistent worker reuse. A file handshake makes the queued
test independent of host response speed. A separate interpreter confirms normal
shutdown reaps its cached child. A real HTTP process request times out with 422,
persists one failed invocation and matching failed process receipt in SQLite,
and creates no successful result or downstream invocation.

The existing TS/Python/Rust demo passes 45 parity calls, TestQL 5/5, checkout,
guards, persistence, invalid input, logs and MCP on its isolated Compose stack.
Governance PASS. The request deadline is ten seconds; process/worker cleanup is
separately bounded. UI, generic hosts and cell interfaces are unchanged.
Raw evidence stays in the private cache and the final external artifact report.

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
