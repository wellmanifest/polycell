# Ticket 047: Publish Polycell cells and POA processes via /v1/poa/registry

- **ID**: ticket-047
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-24

## Goal and scope

Publish Polycell cells (linked to `urn:wm:cell:...` URNs), POA processes, and gateway
query operations via `/v1/poa/registry` (`gateway/poa_registry.py`), HTTP route
`GET /v1/poa/registry` (`gateway/app.py`), and CLI `python -m gateway.cli poa-registry`
(`gateway/cli.py`), compatible with `urtlog.registry.UnifiedRegistry.import_poa_registry`.

## Acceptance criteria

- [ ] AC-01: `gateway/poa_registry.py` exports `polycell.poa-registry/v1` with linked cell URNs, process aliases, and read/write effect metadata without adding mandatory dependencies.
- [ ] AC-02: `GET /v1/poa/registry` and `python -m gateway.cli poa-registry` serve the exact registry payload, and `UnifiedRegistry.import_poa_registry` imports all operations and linked URNs.
- [ ] AC-03: Full `tests/test_*.py` suite, `./project/governance-check.sh`, and `wellman check` pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 56/100 |
| Complexity | M |
| Estimated effort | 57 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
