# Ticket 018: Adopt published governance standard 0.20.149

- **ID**: ticket-018
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing the Forge and
Polycell generation investigation, completing the fixes and merging them.
This continues PLF-22407. Writer: agent:codex, session
codex-polycell-standard149-20261114-0840.

Upgrade the complete managed governance package from published 0.20.147 to
published 0.20.149 through Goal. The annotated v0.20.149 tag and final canonical
GitHub Release bind source c3aa6c0c35d6408cdb4b6bd10086baef7e77f3a6.
The native allocation plan defines the exact twenty-file upgrade and full
delivery contract. Preserve target-owned configuration and application code.
Implementation is bounded to thirty minutes; publication uses the independent
protected controller after validation of the committed head.

## Acceptance criteria

- [x] AC-01: Adopt the complete published package, verify its pin and managed hashes, and qualify ignored provider-version scanning and application regressions before independent protected publication.

## Validation

`make check test`: conformance PASS and 137 tests PASS in 131.914 seconds.
Native Goal adoption check reports the complete package up to date at the
published source revision. Target-owned manifest settings are preserved.

The managed governance gate passes with zero findings while an ignored
`.run/` provider fixture declares version 999.0.0 beside product version 0.1.0.
Before commit the gate receives the complete actual dirty-path set; publication
also requires its ordinary check against the exact committed base and head.
The owned fixture is removed after the check. No product, test or generated
application source changes belong to this ticket.

Source release provenance, real workspace snapshots and raw results are
retained in the external PLF-22407 adoption-149 evidence directory.
Independent review and merge remain required for the committed head.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 68/100 |
| Complexity | L |
| Estimated effort | 112 min |
| Planning budget | 120 min |
| Split recommended | no |

Diagnostics: RADAR-ACCEPTANCE-MISSING.
<!-- ticket-radar:end -->
