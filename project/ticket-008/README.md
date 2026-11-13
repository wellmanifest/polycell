# Ticket 008: Regenerate rejected model proposals

- **ID**: ticket-008
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: the repeated user request to continue and merge the Forge/Polycell generation investigation authorizes PLF-22410. A fresh customer.validate response at main7382032 failed the controller file-key check and stopped after one attempt despite a two-attempt budget. This is a model proposal rejection, distinct from a provider failure.

Native allocation assigned session polycell-proposal-feedback-20261113 at revision1/fence1, issued20:05:01Z. Source stage ends20:35:01Z; total owner lifetime ends21:05:01Z. No automatic renewal or copied identity. Preserve the independent standard ticket432 writer and blocked release scope429.

## Acceptance criteria

- [x] AC-01: Preserve the original model bundle and regenerate the entire file after envelope/header rejection, using bounded actionable feedback and the frozen contract/oracle.
- [x] AC-02: Exhaustion publishes no candidate; provider failures stop after one call; existing qualification and publication-integrity guarantees remain tested.
- [ ] AC-03: Focused and full regressions plus required governance/native checks pass; independent Validator approves and merges the frozen exact head.

## Evidence boundary

Raw output and failed fresh generations remain in external ignored evidence forge-polycell-20261113/fresh-languages. Model bodies are never patched manually. Operational checkpoints bind PLF-22410, ticket008, branch, HEAD and current lease. A successful source change does not claim standard release or consumer adoption.

## Validation and publication checkpoint

The regression fails on accepted main7382032: wrong target and conflicting header stop immediately, while exhaustion reports generation failure after one call. The candidate passes10 focused tests and79 full tests. Local governance passes with zero findings. The existing provider failure tests retain one-call fail-stop behavior. Raw responses remain private per-attempt bundle.json; only qualified candidates become public. Native CI and independent Validator approval/merge remain required.

The adapter fixtures also pass with imports of optional Forge/SubLLM packages deliberately refused. Only provider transport and profile generation are replaced; the real adapter, audit persistence, classification and bounded loop execute. A native provider-error answer is separately verified to stop after one call.
