# Ticket 031: Reap stdio hosts when worker startup fails

- **ID**: ticket-031
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: user requests continuing Forge/Polycell repairs and merging. Outer PLF-27168 retains original timing investigation; this separate native slice repairs a reproduced resource-cleanup defect. Writer codex-worker-start-20261115-1601, native lease1/fence1; source/carrier implementation window 2026-11-15T16:02:13.300172+00:00 to 2026-11-15T16:12:13.300172+00:00, maximum10minutes.

If Thread.start fails after Popen succeeds, the constructor currently leaves an uncached child and both pipes alive. A real-process failure-injection probe on merged0294fbc reproduces one living host and two open pipes; the probe explicitly cleaned its own process group afterward. This does not prove the original intermittent timeout cause. Reuse existing bounded lifecycle cleanup, preserve the original startup exception, and permit a later healthy call without replay.

## Acceptance criteria

- [x] AC-01: Actual-process regression fails before repair, then confirms reaped child, closed pipes, empty cache, preserved exception and successful later request without replay.
- [x] AC-02: Existing transport/application tests and conformance pass with unchanged deadlines/assertions; native delivery retains all language checks.
- [x] AC-03: Original generated TypeScript application passes isolated HTTP/gRPC/stdio, TestQL, persistence and MCP; no new generation calls or generated function edits.
- [ ] AC-04: Native author delivery, required exact-head checks and independent protected review/merge complete.

## Scope

Only gateway/transport.py, tests/test_transport.py and this ticket's governed carriers. Keep existing process-group cleanup, queued timeout/no-replay semantics and all peer030 paths intact. Raw operational receipts: forge-polycell-20261113/continuation-20261115-1555.

## Qualification and source freeze

Both real-subprocess regressions fail on unchanged production source (the child survives); after repair both pass in0.059s. Public API recovery succeeds with exactly one new host and no replay; interrupted startup re-raises the same KeyboardInterrupt instance after cleanup. Existing189tests plus575subtests pass in125.74s. make check and conformance pass. The original TypeScript function passes the pinned networkless, read-only UID65534 runtime in36.203s: six transport calls, two TestQL cases, three portable tests, SQLite/MCP and strict JSON controls. Exported transport bytes equal this checkout. Zero new inference calls or generated function edits.

Hostguard and fixos classified CPU pressure in observe-only mode; no foreign process was terminated. The original intermittent timeout cause remains unproven. Source and tracked carriers freeze at2026-11-15T16:09:09.557789+00:00, within the10minute implementation window. The native Goal delivery still runs every Python, TypeScript runtime and Rust check before author push; only independent trusted validation may merge.

## Approved base integration

PR30 independently merged main373939cddcd1da7d8910f1f6973ca359be453827, approved by trusted App review5911675243 for exact author8d8d8cca8858c1d09a83705a3f32527cf5f0608b. The owned branch integrates that exact base through the repository-declared ticket-index driver, retaining both030/031 entries and every peer change. The original gateway/transport.py and tests/test_transport.py bytes remain unchanged from authorabcb5ea.

Bounded integration stage 2026-11-15T16:30:59.406974+00:00 to2026-11-15T16:40:59.406974+00:00, existing lease2/fence2 with unchanged expiry. Source/carriers freeze at2026-11-15T16:31:36.331964+00:00. Reassemble the original generated cell and run fresh full native delivery for the combined candidate before exact-head independent review; prior results and failures remain retained. No history rewrite, direct main write, version/tag/release change or new generation call.
