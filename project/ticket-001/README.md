# Ticket 001: Adopt new-project governance

- **ID**: ticket-001
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-13

## Goal and scope

Requested by the repository owner on 2026-11-13 after finding that
`fix/composable-app-tests` reached `main` by a direct fast-forward push with no
ticket, worktree, pull request or independent validation.

Install the pinned `wellmanifest/new-project` 0.20.147 package
(`511eb0ab1c0f9f8697c44f5748ba93b25da5e0d9`) through its native bootstrap
route, add the required baseline files, and keep the previous repository
agent rules as `project/polycell-agent-rules.md`. Application code, cells,
contracts and the existing `Test polycell` workflow are out of scope.

## Acceptance criteria

- [ ] AC-01: `./project/governance-check.sh --actor agent` passes on the ticket head.
- [ ] AC-02: `project/new-ticket.sh` allocates under `.worktrees/ticket-NNN--slug` and `/.worktrees/` is root-ignored.
- [ ] AC-03: The previous polycell agent rules remain reachable from `AGENTS.md`-adjacent docs (`project/polycell-agent-rules.md`, linked from `README.md`).
- [ ] AC-04: Publication happens through a pull request approved by the independent Validator, not a direct push.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 48/100 |
| Complexity | M |
| Estimated effort | 44 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
