# ticket-039: Keep MCP stdio Unicode responses UTF-8 safe

- **ID**: ticket-039
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: user requests continuing Forge/Polycell investigation, repairs and protected merging. Outer PLF-27174 records this bounded slice. Writer codex-mcp-unicode-20261115-2016, native lease1/fence1. Source/carrier implementation window 2026-11-15T20:19:01.599098+00:00 to 2026-11-15T20:29:01.599098+00:00, maximum10minutes.

A real child on merged4dfcec9 receives valid UTF-8 JSON with an escaped lone-surrogate id, exits1 with UnicodeEncodeError and loses the next valid request. This is a deterministic response-encoding defect, distinct from original intermittent timing. Escape outer response codepoints so the wire stays UTF-8-safe while decoded ids/results and normal Unicode remain unchanged. Do not reinterpret the accepted JSON input or replay a completed call.

## Acceptance criteria

- [x] AC-01: Real stdio regressions fail before repair and pass after, covering both stdout error modes, lone/normal Unicode ids, gateway payloads and same-process recovery with exact HTTP counts.
- [ ] AC-02: Existing tests, assertions, deadlines and conformance remain valid; native delivery retains all language gates.
- [ ] AC-03: Original generated TypeScript project passes pinned SQLite/PGlite transport, TestQL, persistence and MCP Unicode controls, without function edits or new inference.
- [ ] AC-04: Native author delivery, required final-head CI, independent protected review/merge and owner cleanup complete.

## Scope and evidence

Only gateway/mcp.py, tests/test_mcp.py and this ticket's governed carriers. Preserve the separate active038 writer. Evidence: forge-polycell-20261113/continuation-20261115-2010. Protocol requires UTF-8 JSON-RPC messages: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports . JSON escaping preserves values: https://docs.python.org/3.13/library/json.html . No raw malformed-input recovery, dependency, provider budget, schema, function or release changes.

## Reproduction, qualification and source freeze

Before repair the gateway-payload case and strict-output subcase terminate the child, while surrogateescape emits a non-UTF-8 byte. The preserved focused run reports three failures. After the single outer-encoder change, all15MCP tests and26subtests pass; decoded ids, payloads and normal Unicode remain equal, one completed HTTP call stays one, and later messages succeed in the same process. make check passes with zero errors/warnings. No input interpretation, finite-number guard, assertion, watchdog or replay policy changed.

Source and tracked carriers freeze at2026-11-15T20:24:00.106982+00:00, within the10minute implementation window. Full native Python/Rust gates and actual generated-project TypeScript SQLite/PGlite/Unicode qualification remain required before author delivery; exact-head checks and independent protected review remain required before merge. No function edits or new generated-cell calls.
