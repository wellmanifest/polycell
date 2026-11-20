# Ticket 046: Optional uritime-urtlog span telemetry for Python Polycell host invocations

- **ID**: ticket-046
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — user requested pilot rollout of `uritime-urtlog` into `wellmanifest/polycell` to capture `URT × URI × URN_IN × URN_OUT` telemetry across Polycell cell invocations.

## Goal and scope

Add an opt-in, zero-mandatory-dependency `hosts/python/urtlog_bridge.py` bridge invoked by `hosts/python/host.py` inside `invoke(urn, data, trace_id)` when `URTLOG_STATE_DIR` is explicitly set and `uritime-urtlog` is installed. When unset or uninstalled, `host.py` runs identically with zero overhead or side effects.

## Acceptance criteria

- [x] AC-01: Scope stays strictly within `application` workstream (`hosts/python/urtlog_bridge.py`, `hosts/python/host.py`, `tests/test_python_host_urtlog.py`).
- [x] AC-02: When `URTLOG_STATE_DIR` is unset, `maybe_emit_polycell_invoke` is a no-op with zero filesystem or import side effects.
- [x] AC-03: When `uritime-urtlog` is absent, `hosts/python/host.py` `invoke()` completes normally without raising telemetry errors.
- [x] AC-04: When `URTLOG_STATE_DIR` is set and `uritime-urtlog` is installed, invoking a cell records a canonical `LOG` event (`URT × URI × URN_IN × URN_OUT`) and registers the cell URN in `UnifiedRegistry`.
- [x] AC-05: Unit tests and `./project/governance-check.sh` pass.

## Tracking boundary

This directory contains the minimal reviewed intent.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 36/100 |
| Complexity | M |
| Estimated effort | 37 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
