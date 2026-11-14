# Ticket 025: PC-ADOPT-01: exclude worktrees, governance, venv, build and gen in adopt.py inventory (#23)

- **ID**: ticket-025
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: authorized by the user (2026-11-14) to evaluate
and prepare `wellmanifest/polycell` for Heyasa ecosystem autonomy refactoring
(issue #23 / PC-ADOPT-01).

Exclude non-domain directories (`.git`, `.worktrees`, `worktrees`, `.governance`,
`.venv`, `venv`, `build`, `dist`, `gen`, `.run`, `__pycache__`, `*.egg-info`)
from `tools/polycell/adopt.py` (`inventory_map` and `inventory_src`, pruning
skipped directory subtrees during traversal) and cover both modes with unit
regression tests.

## Acceptance criteria

- [x] AC-01: `SKIP` excludes linked worktrees, managed `.governance` projections,
  virtualenvs, build/dist/gen artifacts in both `inventory_map` and `inventory_src`.
- [x] AC-02: `inventory_src` prunes skipped directories during `os.walk` instead
  of traversing `.venv` or `.worktrees` subtrees.
- [x] AC-03: Unit tests in `tests/test_adopt_inventory.py` and existing suite pass.
- [ ] AC-04: `governance-check.sh` and independent Validator review/merge succeed.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 52/100 |
| Complexity | XS |
| Estimated effort | 20 min |
| Planning budget | 30 min |
| Split recommended | no |
<!-- ticket-radar:end -->
