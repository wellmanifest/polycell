# Ticket 026: Prevent MCP replay after gateway response loss

- **ID**: ticket-026
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-mcp-replay-20261114.

Prevent MCP from replaying a tool locally after an HTTP attempt fails or returns
an invalid response. A lost response can follow successful remote execution;
report an uncertain outcome without retrying. Preserve intentional standalone
execution through an explicit `--local` mode selected before dispatch. Keep
normal cell/process routing, HTTP business errors and subsequent messages working.
Limit implementation to the MCP adapter and its tests; no host, cell, contract
or generated artifact changes.

## Acceptance criteria

- [x] AC-01: HTTP transport/response failures never dispatch a local call or retry remotely, and report that execution may have completed.
- [x] AC-02: Explicit local mode executes cells/processes once without HTTP; valid HTTP results, business errors and later messages remain supported.
- [x] AC-03: A real lost-response regression, unit suite, parity, TestQL, DB/MCP and governance pass before independent protected publication.

## Validation

The initial four regressions exposed 14 errors on old source, including local
replay after completed HTTP calls and uncaught incomplete responses. All 175 unit
tests pass, including 12 MCP tests and a subprocess test proving `--local`
uses its own SQLite database without HTTP.

A private relay forwards real calls through the running TS/Python/Rust stack,
then drops, truncates or replaces the completed gateway response with null or
invalid JSON. Twenty MCP tool calls produce exactly 28 remote invocations and
four process runs, with zero local replay. Every failed call is followed by a
successful tools/list response. Positive HTTP and explicit local batches each
execute five tools / seven invocations; local mode makes zero HTTP attempts and
uses a separate SQLite database. Runtime MCP source digest is recorded.

Existing demo: parity 45 calls, TestQL 5/5, checkout across all three transports,
guards, persistence, logs and MCP pass. Conformance and governance pass. Exact
reports and source hashes stay in the private cache and external artifact
report. Trusted review must still bind the final committed head.

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
