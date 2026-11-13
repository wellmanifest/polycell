# Ticket 010: Return compose.yml ownership to the infrastructure workstream

- **ID**: ticket-010
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-13

## Goal and scope

Follow-up to ticket-001. The first adoption listed `compose.yml` under the
`governance` workstream only so that the bootstrap ticket could carry the
`GOV-DOCKER-002` digest pins. `infrastructure` already owns `compose*.yml`;
remove the duplicate governance ownership. `VERSION` stays with governance
because it is a governance-required file. Requested by the owner on
2026-11-13 ("continue, carry out the tasks in order").

## Acceptance criteria

- [ ] AC-01: `compose.yml` is owned only by `infrastructure` in `.governance/manifest.json`.
- [ ] AC-02: `./project/governance-check.sh --actor agent` passes on the ticket head.

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
| Estimated effort | 47 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
