# Ticket 036: Reject assembly output overlapping copied runtime directories

- **ID**: ticket-036
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-runtime-copy-20261115.

Reject an assembly destination inside a runtime directory being copied, before
the copier can traverse its own staging tree. Compare resolved paths so output
aliases and nested source aliases cannot bypass the guard. Cover both regular
runtime copying and optional warm dependency/protobuf copying without changing
their existing exclusion rules. Preserve normal .run/external outputs, source
data, atomic cleanup, package/lock formats and non-overlapping symlink behavior.
No cell, host, transport, dependency or governance changes.

## Acceptance criteria

- [x] AC-01: Overlapping runtime/output paths, aliases and warm copies fail with a bounded ValueError before recursive staging traversal; sources and existing destinations remain intact.
- [x] AC-02: Normal .run/external assembly, unrelated aliases and complete warm dependencies retain existing behavior, including package Git/manifest bindings.
- [ ] AC-03: Regression, real Python/TS/Rust qualification and Git bundles, parity, TestQL, DB/MCP and governance pass before protected independent publication.

## Validation in progress

Eight initial test methods expose twelve bounded self-copy failures on old
source. All 47 focused package tests now pass, including path aliases, warm
protobuf copying, nested warm dependencies, .run output and existing Git gates.
The published MCP integration passes all 230 regression tests and governance.
Real Docker qualification and Git bundle round trips pass for Python, TypeScript
and Rust, with no new generator calls. All 45 parity calls pass. Live PGlite
scenarios exposed a native timestamp-loader crash in the existing Psycopg pin;
separately scoped ticket-037 supplies the prerequisite dependency repair.
Continue application scenarios on that independently published dependency before
protected publication of this guard.

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
