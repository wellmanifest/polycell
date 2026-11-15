# Ticket 035: Reject nonfinite JSON before MCP dispatch

- **ID**: ticket-035
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: user requests continuing Forge/Polycell repairs and merging. Outer PLF-27173 records this bounded source slice. Writer codex-mcp-finite-20261115-1810, native lease1/fence1; source/carrier implementation window 2026-11-15T18:12:04.785259+00:00 to 2026-11-15T18:22:04.785259+00:00, maximum10minutes.

A real subprocess at merged516fe920 accepts NaN as a request id and emits invalid JSON containing NaN, then handles a later valid request. Reject nonfinite constants and decoded exponent overflow before any dispatch. Return existing Parse error -32700 with null id, keep the same stdio process alive, and preserve finite values and quoted strings. No new inference calls or original timing-cause claim.

## Acceptance criteria

- [x] AC-01: Real stdio regression fails before repair and passes afterward; invalid nonfinite input never reaches HTTP, valid quoted strings do, and the same process recovers.
- [ ] AC-02: Existing application tests and conformance pass with unchanged deadlines/assertions; native delivery checks all languages.
- [ ] AC-03: Original generated TypeScript application passes isolated transport, TestQL, persistence and MCP; exported MCP bytes equal candidate with no function edits or inference.
- [ ] AC-04: Native author delivery, exact-head checks, independent App review and protected merge complete.

## Scope

Only gateway/mcp.py, tests/test_mcp.py and this ticket's governed carriers. Preserve foreign034 package work. External operational receipts: forge-polycell-20261113/continuation-20261115-1755. Protocol: https://www.jsonrpc.org/specification#error_object .

## Qualification and source freeze

The new real stdio regression fails against unchanged production source (NaN is echoed as id). After the finite JSON preflight it passes, with all ten invalid messages rejected before HTTP, three quoted strings forwarded exactly once and later tools/list handled by the same process. make check passes with zero errors/warnings. The first focused MCP suite retains one existing local-mode10second timeout and12passes; isolated unchanged local-mode and new finite-input controls both pass in1.96seconds. No watchdog/assertion was changed and the timing cause remains unproven.

Original generated TypeScript cell assembled from its accepted immutable commit, with no inference or function edits; candidate MCP bytes will be verified in the required isolated runtime. Source and tracked carriers freeze at2026-11-15T18:14:56.690065+00:00, within the10minute implementation window. Full native Python, TypeScript runtime and Rust gates, required exact-head checks and independent trusted review remain required before merge. Operational results and all failures remain external.
