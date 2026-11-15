# Ticket 033: Reject malformed qualification receipts before package publication

- **ID**: ticket-033
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-qualification-receipt-20261115.

Validate the existing qualification worker receipt before binding it to package
digests or admitting publication. Require strict JSON, the existing receipt
schema and identity, literal boolean success, the exact trusted case count,
stdio/no-network metadata and finite nonnegative timings. Missing, malformed or
inconsistent receipts must produce an actionable ValueError so the bounded
regeneration loop retains the failed qualification and cannot publish it.
Preserve the successful worker format, cleanup, immutable package snapshots,
interface hashes and host/cell contracts. No new dependencies or host changes.

## Acceptance criteria

- [x] AC-01: Invalid worker receipts fail qualification consistently, including malformed JSON, wrong identity, false success flags, counts and timings.
- [x] AC-02: Valid receipts retain the frozen package/image bindings, while bounded regeneration preserves failed receipt diagnostics and publishes only a valid qualified candidate.
- [x] AC-03: Regression, real Docker qualification for Python/TS/Rust, Git bundle/assembly, parity, TestQL, DB/MCP and governance pass before protected publication.

## Validation

The initial ten regression methods produced 48 failures and four uncaught
errors on old source. The fixed public qualifier rejects 57 malformed receipt
variants and consistently reports an invalid qualification receipt. Successful
receipts preserve optional metadata, while image and package digests remain
bound locally to the frozen inputs. Nonzero worker status and timeouts still
fail qualification and clean up the container.

`make check test` passes 212 tests. Eight real Docker evaluations exercise
Python, TypeScript and Rust regeneration and an exhaustion control. Explicitly
injected receipt faults reject the first qualified candidate; the next complete
file is accepted only with a valid report. All three one-source-file packages
pass Git commit/bundle/clone and joint assembly/conformance. Two repeated bad
reports exhaust the attempt budget without publication.

Provider replies in this audit are controlled fixtures; there are zero native
inference calls. Worker-report faults are deliberate test injections. Receipt
validation checks consistency, not cryptographic authenticity or arbitrary image
safety. The existing worker format and container policy remain unchanged.

The application passes 45 parity calls over HTTP/gRPC/stdio, TestQL 5/5,
checkout, database persistence, logs and MCP. Governance passes with no errors
or warnings. Publication requires independent review of the exact tested head
and the protected controller; runtime evidence stays in the private cache.

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
| Estimated effort | 59 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
