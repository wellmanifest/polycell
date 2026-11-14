# Ticket 022: Adopt wellmanifest docs standard and declare errors ownership

- **ID**: ticket-022
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-14
- **Base SHA**: cbff079b789e56f4fe0b380c67bdc7c142aab7fe

## Goal and scope

Record the `wellmanifest/docs` adoption metadata in `.governance/docs.json` (now
that `docs/README.md` is merged on `main`) and add `"errors/**"` to
`coordination.workstreams.governance.ownedPaths` in `.governance/manifest.json`
so the follow-up ticket can allocate and publish the `errors/` conformance runbook
catalog for `wellmanifest/logs`.

## Execution authorization

`SESSION_EXECUTION_AUTHORIZATION`: Continuing sequential autonomous execution
(`kolejno`) requested by the owner across `heyasa` and `wellmanifest/polycell`,
with independent protected publication through `ifuri-validator-agent[bot]`.

## Acceptance criteria

- [x] AC-01: `.governance/docs.json` records `wellmanifest/docs` adoption (`source_revision` `aa92136b4e94f48355c39fb206286aba024c6aa4`, `policy_sha256` `af5fde2d52e1c292e569cd47a4068f0e42181a8f8fb9fc21737a569bee9a206f`) for `wellmanifest/polycell`.
- [x] AC-02: `.governance/manifest.json` declares `"errors/**"` under `coordination.workstreams.governance.ownedPaths`.
- [x] AC-03: `./project/governance-check.sh --actor agent`, `wellman check --standard wellmanifest/docs`, `standard/conformance.py`, and unit tests pass on HEAD.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
