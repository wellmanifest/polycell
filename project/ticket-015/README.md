# Ticket 015: Keep parallel cell major versions independently callable

- **ID**: ticket-015
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
polycell-parallel-majors-20261113.

Allow independently callable major versions of the same cell. Preserve v1
aliases and paths; other majors use name.vN runtime aliases while package and
contract identity retain the original name and full URN. Keep generated types,
schemas, examples, golden cases, prompts and package assembly separate. Reject
alias/file/type collisions before generation. Do not modify hosts, the fixed
transport protobuf or existing business cell implementations.

## Acceptance criteria

- [x] AC-01: Parallel majors generate independent artifacts without overwriting v1 implementations or changing their input/output shapes.
- [x] AC-02: Prompts and Git packages select either version by alias or URN and assemble together without losing behavior cases.
- [x] AC-03: All three unchanged language hosts execute both versions through HTTP/gRPC/stdio; regressions, conformance, parity, TestQL, DB/MCP and governance pass before independent publication.

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
| Estimated effort | 67 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->

## Validation

112 tests and conformance pass, including seven new versioning regressions. The
first six failed before implementation. A package export regression exposed a
v1-schema lookup in v2 export; the lookup now uses the selected runtime alias.
Existing collision fixtures compare the same major, preserving filename/type
collision coverage while permitting intentionally different majors.

Six one-file packages (v1/v2 in Python, TS and Rust) round-trip through Git
bundles and assemble into one app. The unchanged hosts pass 18 HTTP/gRPC/stdio
parity calls, 12 alias/wrong-interface checks and a process mixing old Python,
new TS and old Rust on all three protocols. The app passes three portable
tests, DB/MCP integration, TestQL 7/7 and six real-browser scenarios (66 steps).
All six Git clones qualify independently in the evaluator. The shared image
extends the pinned cached compiler image with the current framework sources;
its Dockerfile and image identity are retained in private evidence.

The existing demo passes 45 parity calls, TestQL 5/5 and DB/MCP integration.
Its generated artifacts remain unchanged. No hosts or fixed transport protobuf
were edited, and no existing business implementation was changed.
