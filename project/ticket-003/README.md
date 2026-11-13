# Ticket 003: Keep assembled application agent rules portable

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-13

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested "napraiwaj,scalaj,testuj"
for the polycell application harness. After governance adoption, assembly must
copy the preserved portable polycell rules into the application's AGENTS.md,
instead of repository governance instructions requiring files that assembly
does not install. Older runtimes without the preserved file retain their
existing root AGENTS.md behavior. Writer: `agent:codex`, session
`polycell-portable-agent-rules-20261113`.

## Acceptance criteria

- [x] AC-01: Assembled applications receive the portable polycell rules.
- [x] AC-02: Assembly still supports runtimes with only a root AGENTS.md.
- [x] AC-03: Package regressions, `make check` and `make parity` pass.

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

The portability regression fails before the fix. Package and application tests, conformance, governance and parity pass. Transport checks use the same unchanged cell contracts and implementations in the shared Docker test stack.
