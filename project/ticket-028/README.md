# Ticket 028: Clean up stdio descendants after launcher exit

- **ID**: ticket-028
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: the user requests continuing Forge/Polycell repairs and merging. This implements the reproduced cleanup slice of outer PLF-27168 after independently merged PR27 released the transport reservation. Writer session codex-stdio-cleanup-20261115-1420, native allocation fencing1/1. Implementation window 2026-11-15T14:21:59.756740+00:00 to 2026-11-15T14:41:59.756740+00:00, maximum20minutes.

A POSIX launcher can exit while a same-group descendant retains stdin/stdout. Existing cleanup skips the process group when poll reports the launcher exited. The public API returns a timeout and evicts the cache but leaves the descendant, worker and pipes alive. Terminate the owned group independently of launcher liveness; preserve existing non-POSIX behavior, wait/join limits, no-replay semantics and peer027 path quoting. The cause of the earlier intermittent tests remains unproven.

## Acceptance criteria

- [x] AC-01: A real exited-launcher regression fails on original source and passes after the fix; the failed request is not replayed, cached client is retired, worker stops and both pipes close.
- [x] AC-02: All existing transport/path and application unit tests plus conformance pass without increased deadlines or weakened assertions.
- [x] AC-03: The portable generated TypeScript project passes isolated transports, persistence/MCP and governance; original generated logic remains unchanged.
- [ ] AC-04: Native author delivery, exact-head protected checks and independent review/merge complete.

## Scope and risk

Only gateway/transport.py and tests/test_transport.py plus this ticket's governed carriers are owned. No dependencies, generated cell edits, protocol/version/release changes or foreign checkout modifications. Use only the process group created for this client; retain the non-POSIX fallback. Raw probes/logs stay in external receipts.

External evidence: forge-polycell-20261113/stdio-recovery-20261115. The direct and public-API controls already demonstrate the unmodified-source leak; new in-repository regression will preserve that reproducer.

## Focused regression

The new actual-process public API test fails on the accepted base because the worker remains alive after an exited launcher timeout. The same test passes after the single cleanup-condition repair. It checks cache retirement, no new-host retry, stopped worker and closed stdin/stdout, and bounds cleanup even on old source. The request deadline remains0.15s; existing deadlines/assertions are unchanged. Original raw failures remain in external evidence.

## Application qualification

All179 application tests pass in39.304s with owned nonGit tmpfs TMPDIR; every existing timeout/assertion is retained. The first full run had178passes and one existing MCP local subprocess exceeded its unchanged10s watchdog during high host load. That identical case later passes alone in1.177s. Preserve the first failure and control; the cause of that startup discrepancy is unproven and this cleanup repair does not claim to fix MCP startup. Conformance and diff whitespace checks pass. Hostguard/fixos observed resource pressure; no foreign process was terminated.

## Portable runtime and freeze

The original generated TypeScript function is unchanged (SHA256108dcd77c13bd68152e02229cedc687dda44aef7a4873d6f55eef5eb4f68ebba), with zero new inference calls. Its assembled application passes HTTP/gRPC/stdio, two TestQL scenarios, three portable tests, SQLite persistence, MCP and strict finite-JSON controls inside a pinned networkless read-only UID65534 container in36.419s. The exported transport bytes match this checkout. Implementation and tracked carriers freeze at2026-11-15T14:37:19.748528+00:00; only protected publication remains.

## CI budget correction and direct descendant oracle

The first author head ff68eaf passed both native application CI jobs, but required governance rejected the intent: class XS defaults to10minutes, while the initial estimate was20. Correct the estimate to10 without changing XS, allowed paths or any file/component/interface/dependency cap. Preserve that failed head and original planning entry as history; no policy is weakened. The original production change and first regression were finished before the10minute source window; qualification and delivery continued afterward.

A bounded follow-up implementation stage runs from2026-11-15T15:02:17.399893+00:00 to2026-11-15T15:12:17.399893+00:00, maximum10minutes, under the same owner and lease2/fence2 with unchanged expiry. Add a real descendant-lifetime oracle: an inherited child keeps a control connection open until process death, so the test verifies termination directly as well as worker/pipes/cache cleanup. The transport production code stays identical to the already qualified author head. Re-run focused/full native qualification and obtain fresh exact-head CI and independent review.

The direct descendant-death oracle passes: the inherited control connection reaches EOF after cleanup, in addition to stopped-worker/closed-pipe/cache assertions. The complete179-test suite passes again in99.275s without changed request deadlines. The bounded follow-up and carriers freeze at2026-11-15T15:07:21.068331+00:00, before the10minute stage deadline. Production transport bytes remain identical to ff68eaf.
