# Ticket 005: Enforce portable generated field types and numeric bounds

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested investigation of Forge and
Polycell project generation, followed by "kontynuuj,scalaj". This implements
PLF-22405 and requests independent publication. Writer: agent:codex; session:
polycell-generation-repair-20261113. The scope includes generated projections
of the repaired schema/type emitters, accepted through the managed scope helper.

Reject names that cannot be emitted as portable Python/Rust identifiers before
writing artifacts. Optional fields may be omitted; explicit null remains invalid
for non-JSON fields, matching the existing gateway contract. Generated Python
and TypeScript types must reflect that rule. Enforce declared int32/int64 ranges
and reject non-finite numeric inputs at the gateway.

## Acceptance criteria

- [x] AC-01: Invalid generated names fail before overwriting artifacts.
- [x] AC-02: Optional Python/TypeScript fields agree with schema null semantics.
- [x] AC-03: Nested numeric bounds and non-finite values are checked; valid boundaries pass.
- [ ] AC-04: Regressions, generation and governance pass; the independent Validator merges the exact reviewed head.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Validation

The five added regression methods fail before the fix (16 failing subcases).
After the change all 64 tests pass, including isolated application generation.
Generated typed proto compiles. Polycell conformance and managed governance
pass with no findings. A separate worker image is being built for package
qualification; its exact result and independent publication remain external
receipts and are not implied by these local checks.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 60/100 |
| Complexity | L |
| Estimated effort | 64 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
