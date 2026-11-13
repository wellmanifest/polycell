# Ticket 009: Bind process plans to immutable execution definitions

- **ID**: ticket-009
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the polycell harness. Writer: agent:codex, session
polycell-process-plan-20261113.

The compact gateway plan must expose and hash its execution mappings and guards,
and process execution must use the same snapshot. Add a local JSON Schema for
this plan projection, preserving its existing fields, and reject ambiguous step
identities/dependencies before dispatch. No cell or host interfaces change.

## Acceptance criteria

- [x] AC-01: The visible plan binds input/output mappings, dependencies, effects and guards to plan_hash.
- [x] AC-02: Definition mutation cannot change an in-flight execution or an already returned plan.
- [x] AC-03: Duplicate IDs and invalid dependencies fail before any dispatch and duplicate IDs fail conformance.
- [x] AC-04: Regression tests, conformance, parity and integration pass before independent publication.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 64/100 |
| Complexity | L |
| Estimated effort | 68 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->

## Validation

85 tests and conformance pass; the affected process suite also passes after adding legacy-plan schema compatibility coverage. The new regressions failed before the fix (13 failures and 3 errors). Governance, 45 parity calls, TestQL 5/5 and DB/MCP integration pass. Live HTTP/gRPC/stdio checkout plans validate against the local schema, independently recompute to their hashes, and match both returned and database-persisted receipts.
