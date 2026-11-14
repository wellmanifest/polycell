# Ticket 016: Preserve null and nested arrays in process mappings

- **ID**: ticket-016
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-process-mappings-20261113.

Preserve literal and referenced JSON null values in process input/output maps.
Distinguish an absent object field, which remains omitted, from explicit null.
Resolve references recursively in arrays without changing opaque data reached
through a reference. Reject missing array/root references and record mapping
failures in the process result/receipt before dispatch or output publication.
Keep hosts, transport protobuf, cell contracts and business code unchanged.

## Acceptance criteria

- [x] AC-01: Literal/reference nulls, nested arrays and opaque JSON data retain their intended values; missing optional object fields remain omitted.
- [x] AC-02: Unresolved array/root references fail with process evidence and no unintended dispatch; explicit null is not coerced into omission for non-nullable optional fields.
- [x] AC-03: Regressions, real HTTP/gRPC/stdio process cases, existing parity, TestQL, DB/MCP and governance pass before independent publication.

## Validation

`make check test`: conformance PASS and 123 tests PASS, including 11 new
mapping regressions. Before the repair those regressions exposed eight failures
and one error. Governance PASS with no findings.

A private assembled application runs three JSON echo cells in Python, TypeScript
and Rust using the unchanged hosts. Nine processes across HTTP/gRPC/stdio verify
27 expected success/failure results, exact HTTP status, saved process receipts
and invocation counts. Missing input references dispatch no cells; missing output
references retain all three completed steps and persist failure. Its parity,
three portable tests, TestQL (4/4), persistence and MCP (12 tools, 8 calls) pass.

The existing demo passes parity, TestQL (5/5), DB/MCP integration and six extra
checkout cases. An omitted coupon still succeeds; explicit null fails at quote
with HTTP 422, stops notification, and persists the failure receipt, on all three
protocols. UI code is unchanged. Raw evidence is retained in the private ticket
cache and the final external artifact report; protected review remains required
for the exact committed head.

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
