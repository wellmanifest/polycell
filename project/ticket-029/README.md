# Ticket 029: Reject invalid host envelopes during package qualification

- **ID**: ticket-029
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-qualification-envelope-20261115.

Qualification must reject malformed host envelopes before comparing outputs.
Reuse the existing gateway wire validator for strict success flags, qualified
URN/language, required fields, consistent error metadata and finite duration/JSON.
Mount that trusted gateway code alongside the trusted evaluator, so a cached
compiler image cannot supply an older permissive validator. Preserve actionable
host/contract/schema/behavior diagnostics and valid three-language qualification.
Do not modify gateway transport (owned by peer028), hosts, cell logic, contracts,
generated artifacts, dependency manifests or sandbox limits.

## Acceptance criteria

- [x] AC-01: Malformed success flags, identities, missing/inconsistent metadata and nonfinite values fail qualification before output comparison.
- [x] AC-02: Qualification uses the same trusted wire validator as the gateway, including with a cached image; valid replies and existing diagnostics remain supported.
- [x] AC-03: Regressions, real bounded three-language qualification with wire fault injection, parity, TestQL, DB/MCP and governance pass before independent protected publication.

## Validation

`make check test`: conformance PASS, 186 tests PASS, including eight new envelope
regressions. Old source produced 33 failed checks. Existing comparison/diagnostic
fixtures now supply complete envelopes, preserving their original schema,
behavior and host-error assertions rather than failing earlier on metadata.

Real bounded qualification uses cached compiler image ticket-015. Four packages,
each with one implementation, are exported, committed, bundled, cloned and
qualified through the public API, then assembled with conformance PASS. A
separate wrong implementation is rejected for behavior mismatch.

Private networkless probes run the complete trusted evaluator and actual Python,
TS and Rust hosts. Fourteen metadata faults per language leave correct outputs
unchanged: all 42 are accepted by the saved old evaluator and rejected by the
new evaluator. Each probe confirms the validator is loaded from the read-only
`/harness/gateway/transport.py` mount, and records source hashes, image ID,
positive qualification receipts and case-level diagnostics.

Existing demo: parity 45 calls, TestQL 5/5, checkout through HTTP/gRPC/stdio,
guards, persistence, logs and MCP PASS. Governance PASS. Raw evidence remains in
the private cache and external report; exact-head trusted approval is required.

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
| Estimated effort | 68 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
