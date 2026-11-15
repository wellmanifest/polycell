# Ticket 027: Preserve stdio host paths containing spaces and quotes

- **ID**: ticket-027
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-stdio-paths-20261115.

Preserve literal interpreter and host executable paths when the default stdio
commands are parsed into argv. Spaces, quotes and Unicode in a package assembly
directory must not split arguments or prevent host startup. Keep explicit
HOST_<LANG>_STDIO command overrides and the existing transport lifecycle intact.
Change only gateway transport defaults and regression tests; hosts, cell logic,
contracts and generated files are outside this implementation scope.

## Acceptance criteria

- [x] AC-01: Default stdio launches preserve literal Python/TS/Rust host paths with spaces and quotes; real Python calls work in relocated assembled applications.
- [x] AC-02: Interpreter paths and explicit command overrides retain their argument boundaries, with no shell evaluation.
- [x] AC-03: Regressions, a three-language package/assembly acceptance, make check/parity, TestQL, DB/MCP and governance pass before independent protected publication.

## Validation

`make check test`: conformance PASS and 178 tests PASS. The three new regressions
run real Python hosts from relocated assemblies, including an interpreter path
with spaces/apostrophes and a custom command with literal arguments. Old source
failed three checks: a space split the host path, and apostrophes caused parsing
errors. The explicit command override remains compatible.

Private acceptance exports four packages, each with one implementation file,
records a Git commit/bundle, clones it and assembles the clones into a directory
containing spaces, apostrophe, double quotes and Polish characters. Current
gateway code is copied by assembly and its SHA-256 is retained. Rust is compiled
for this assembly; all three default stdio hosts start without command overrides.
Gateway parity and `make parity` each pass 45 calls. Portable tests 3/3, TestQL
5/5, persistence across HTTP/gRPC/stdio and MCP (five tools/five calls) pass.

The compiler image supplies dependencies; GNU Make is the hash-recorded installed
OS binary. Private startup readiness allows slow SQLite schema initialization.
Raw failures, the resolved fixture prerequisites, final results, package commits
and source hashes are retained in the private cache and external artifact report.
Governance passes; trusted approval must bind the final committed head.

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
