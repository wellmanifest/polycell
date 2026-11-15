# Ticket 040: Bind replay to acceptance context and preserve input directories

- **ID**: ticket-040
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continuing the user's requested repairs,
testing and protected merging of Forge/SubLLM/Polycell. Writer agent:codex,
session codex-replay-integrity-20261115.

Bind replay to the exact package prompt and acceptance cases originally sent
to the provider, using a stable package snapshot. Keep output outside source
packages and the existing audit, and publish complete output atomically. Retain
native request correlation, the Forge baseline, explicit replay metadata and
the requirement for independent qualification. No model calls, cell edits,
dependencies, schemas, transport or package-format changes.

## Acceptance criteria

- [x] AC-01: Reject changed acceptance context and overlapping/occupied output before publication; retain source and audit artifacts on success or failure.
- [x] AC-02: Exact archived context replays for Python/TS/Rust; concurrent input changes cannot relabel copied artifacts, failed writes leave no published partial package, and no inference or usage row is added.
- [x] AC-03: Regression, real pinned Forge/SubLLM replay, Docker qualification/Git/assembly, conformance, parity, TestQL, persistence/MCP and governance pass before protected independent publication.

## Validation before publication

Nine new regression methods expose ten failures and one dangling-output error
on the old implementation. All nine pass after repair, as do all 245 regression
tests, conformance, 45 parity calls, TestQL 5/5, PGlite persistence, logs and MCP.
After integrating published MCP Unicode repair PR #39, all 247 regression tests
and the application gates pass again. Fresh assembly retains the qualified
package commits and includes the exact accepted MCP bytes; replay source stays
identical to the native archive/Docker acceptance evidence.

The actual replay function from accepted revision 7cc43da is also executed in
an isolated historical probe against preserved native fixture archives. For
each of Python, TS and Rust it accepts changed cases and invalidates a source
directory with nested output. The candidate rejects those six cases plus three
audit aliases. Correct native replay retains the exact archived implementation
and logical journal/archive contents, passes real network-isolated Docker
qualification, Git bundle/clone and application assembly. The report pins the
tested adapter source hash and the hash-verified Forge/SubLLM wheels. No new
inference is performed; the source archives contain local HTTP fixture replies.

Exact request-prefix binding intentionally rejects older archives lacking the
explicit acceptance-cases block, or edited request contexts. Stored archives
remain intact; replay still requires independent qualification before use.

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
