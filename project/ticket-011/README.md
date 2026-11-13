# Ticket 011: Keep Forge provider environment in project cache

- **ID**: ticket-011
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the polycell harness. Writer: agent:codex, session
polycell-forge-cache-20261113.

Install the pinned Forge/SubLLM provider in the ignored project cache so local
governance does not classify dependency versions as application versions. Keep
the documented .run/forge-provider path as a compatibility symlink. Preserve
existing directories and refuse foreign links; migration requires a separate
local audit of active users and destination contents. No managed rules change.

## Acceptance criteria

- [x] AC-01: Provider dependencies install under .subactor/cache/forge-provider with a compatible .run alias.
- [x] AC-02: Digest failures, unsafe paths and installation failures do not overwrite existing data or publish an incomplete alias.
- [x] AC-03: Regression tests, conformance, parity and governance pass before independent publication.

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

95 tests and conformance pass, including seven installer regressions that failed
before the fix. All 45 parity calls pass against the existing three-language
Docker stack. A fresh installation of the digest-pinned wheels loads Forge
0.3.0 and SubLLM 1.14.0+forge.1 through both paths; governance passes with that
environment present. The primary checkout's old environment was moved without
deletion (1589 entries and the directory inode preserved); its compatibility
path loads the provider and local governance now passes with no rule changes.
