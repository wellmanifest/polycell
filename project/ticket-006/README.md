# Ticket 006: Harden MCP dispatch and malformed requests

- **ID**: ticket-006
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging and testing polycell. Harden MCP request handling and dispatch while preserving existing tool behavior. Writer: agent:codex, session polycell-mcp-repair-20261113.

## Acceptance criteria

- [x] AC-01: Invalid requests return JSON-RPC errors without terminating stdio.
- [x] AC-02: Unknown and ambiguous names never dispatch; cell and process routes are explicit.
- [x] AC-03: Unit tests, conformance, parity and integration pass.

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

## Validation

64 tests pass, conformance and governance pass; 45 parity calls, TestQL 5/5 and integration including five MCP tool calls pass.
