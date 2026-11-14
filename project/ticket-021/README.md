# Ticket 021: Add documentation index for wellmanifest/docs

- **ID**: ticket-021
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user authorized sequential continuation,
standard alignment, verification, and protected Validator publication (`kolejno`).
Writer: `agent:antigravity`, session `antigravity-polycell-docs-index-20261114`.

Add the tracked `docs/README.md` documentation index for `wellmanifest/polycell`
so the subsequent governance change adding `.governance/docs.json` and
`errors/` satisfies `wellmanifest/docs` without triggering `GOV-DOCS-INDEX-MISSING`.
Keep all existing docs, governance manifests, and application runtime code unchanged.

## Acceptance criteria

- [x] AC-01: Tracked `docs/README.md` indexes existing repository documentation with valid relative links and stays within `allowedPaths`.
- [x] AC-02: `./project/governance-check.sh`, `standard/conformance.py`, and regression tests pass in the ticket worktree before publication.

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
