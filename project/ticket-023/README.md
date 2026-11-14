# Ticket 023: Add wellmanifest/logs error catalog and conformance runbooks

- **ID**: ticket-023
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14
- **Base SHA**: cf2012fe8a4e7194b583cfa33a0ff135b199f988

## Goal and scope

Add the `wellmanifest/logs` consumer error catalog [`errors/README.md`](../../errors/README.md)
and per-code conformance runbooks [`errors/PC001.md`](../../errors/PC001.md) through
[`errors/PC009.md`](../../errors/PC009.md) documenting every error and warning code
emitted by `standard/conformance.py`.

## Execution authorization

`SESSION_EXECUTION_AUTHORIZATION`: Continuing sequential autonomous execution
(`kolejno`) requested by the owner for `wellmanifest/polycell` standards compliance
and independent protected publication through `ifuri-validator-agent[bot]`.

## Acceptance criteria

- [x] AC-01: `errors/README.md` indexes every emitted `polycell` conformance code (`PC001`–`PC009`) with severity, summary, and runbook link.
- [x] AC-02: `errors/PC001.md` through `errors/PC009.md` document exact condition, inspection, and remediation matching `standard/conformance.py` and `docs/SPEC.md`.
- [x] AC-03: `./project/governance-check.sh --actor agent`, `wellman check --standard wellmanifest/logs`, `wellman check --standard wellmanifest/docs`, `standard/conformance.py`, and all 154 unit tests pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
