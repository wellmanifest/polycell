# ticket-041: Reject invalid MCP request ids before tool dispatch

- **ID**: ticket-041
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: continuing the user's Forge/Polycell investigation, repairs and protected merging. Outer PLF-27175; writer codex-mcp-request-id-20261115-2140, lease1/fence1. Bounded source/carrier window 2026-11-15T21:41:13.482465+00:00 to 2026-11-15T21:51:13.482465+00:00, maximum10minutes.

At independently merged5eab513 a real MCP child accepts nine invalid ids and performs nine HTTP calls instead of Invalid Request. Reject invalid ids before any side effect. This is distinct from the unresolved intermittent stdio timing. Missing-id notifications remain silent; valid strings and integer-valued JSON numbers retain their decoded ids, including integral float spellings.

## Acceptance criteria

- [x] AC-01: Meaningful direct and real-child regressions fail before repair and pass afterward; zero invalid gateway/local cell/process calls, exact valid calls and continued service.
- [ ] AC-02: Existing tests, assertions, timeouts and conformance stay valid; all-language native author gates pass.
- [ ] AC-03: Original generated TypeScript project passes pinned SQLite/PGlite transports, TestQL, persistence, strict JSON, Unicode and id controls without function edits or new inference.
- [ ] AC-04: Native author delivery, required exact-head checks, independent protected review/merge, owner release and exact cleanup complete.

## Scope and evidence

Only gateway/mcp.py, tests/test_mcp.py and this ticket's governed carriers. Evidence forge-polycell-20261113/continuation-20261115-2132/mcp-request-ids-before.json. MCP2025-06-18 requires string/integer nonnull ids: https://modelcontextprotocol.io/specification/2025-06-18/basic . JSON Schema integer semantics preserve integral float values: https://json-schema.org/understanding-json-schema/reference/numeric . Invalid Request uses the existing null error-correlation policy. No id uniqueness policy, raw byte, dependency, cell, model budget, schema or release changes.

## Qualification and source freeze

The new regressions fail on unmodified5eab513 (11pytest failures/subfailures), and both pass after the id guard. Direct gateway/local cell/process controls cover all nine invalid id shapes. The real child retains seven valid ids, an id-less notification stays silent, exact HTTP calls match only valid requests, and a subsequent tools/list succeeds. Full focused MCP suite passes17tests and62subtests after private RAM scratch/environment preparation; every timeout/assertion is unchanged. An initial existing local-mode test expired at10seconds in the cold disk-backed run (16passed/62subtests); that failure is preserved. Neither this environmental preparation nor the id repair proves the original intermittent timing cause. Conformance and governance pass with zero errors/warnings.

Source/carriers freeze at2026-11-15T21:47:45.124160+00:00 within the accepted10minute window. Full native Python/Rust and original generated TypeScript SQLite/PGlite/id qualification remain required before author delivery, followed by exact-head checks and independent protected review/merge. No function edits or new generated-cell model calls.
