# Ticket 048: Make Polycell URTLog outcomes trustworthy

- **ID**: ticket-048
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-25

## Goal and scope

Correct the Python host's opt-in URTLog bridge so Heyasa can use genuine cell
failures. Preserve the host response and the existing spans for hosted cells.

SESSION_EXECUTION_AUTHORIZATION: the user asked to continue repairing service
outcome coverage in URTLog and deliver the fixes through independent merge.

## Acceptance criteria

- [x] AC-01. A runtime error in the telemetry sink reports an emission failure.
- [x] AC-02. A hosted cell failure reaches URTLog with a fixed error summary.
- [x] AC-03. Unknown cells retain their gateway response without registering
  caller-supplied addresses in URTLog.

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
| Estimated effort | 54 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
