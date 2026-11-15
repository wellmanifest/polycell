# Ticket 038: Reject overlapping proposal output and audit paths before provider calls

- **ID**: ticket-038
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, tests
and protected merging of the Forge/SubLLM/Polycell harness. Writer agent:codex,
session codex-proposal-paths-20261115.

Reject proposal output/audit paths that overlap each other or the source
package before creating directories or invoking the provider. Resolve parent
aliases and reject occupied destinations, including dangling symlinks. Reuse
the same preflight in bounded regeneration so both entry points preserve the
same isolation rules. Keep valid complete-file proposals, retained audit data,
qualification and source packages unchanged. No cell, host, dependency,
transport, package-format or schema changes.

## Acceptance criteria

- [x] AC-01: Reproduce source-layout corruption and provider calls before path-collision failures; regression tests reject overlap without filesystem mutation or provider invocation.
- [x] AC-02: Aliases and occupied/dangling destinations fail early; disjoint proposals for Python, TS and Rust and bounded feedback regeneration retain their behavior.
- [x] AC-03: Full regression, conformance, parity, TestQL, persistence/MCP and governance pass before independent protected publication.

## Validation before publication

Six new regression methods expose seven failures and two dangling-link errors
on the old implementation. All 21 adapter tests and all 236 full regression
tests pass with the shared destination check. Conformance, 45 transport parity
calls, TestQL 5/5, live PGlite checkout/persistence, logs and MCP pass.

Hash-verified Forge 0.3.0 and SubLLM 1.14.0+forge.1 execute real bounded provider
processes against a loopback HTTP fixture, without contacting a model. Three
complete-file fixtures (Python, TS, Rust) each produce one successful native
journal attempt, pass real network-isolated Docker qualification, round-trip
through a Git bundle/clone, and assemble into a conforming application. Six
overlap scenarios produce zero provider HTTP requests and preserve every source
artifact. The acceptance report pins the tested adapter's source hash.

Python execution uses the admitted checkout-local environment. The executor
rejects the separately installed provider interpreter; the integration instead
installs the exact hash-verified optional wheels into the admitted environment
without changing other distributions or tracked dependencies.

Independent exact-head review, required CI, protected merge, main checks and
owner cleanup are recorded externally after this source/carrier freeze.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 52/100 |
| Complexity | M |
| Estimated effort | 51 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
