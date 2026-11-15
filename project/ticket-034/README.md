# Ticket 034: Bind assembled package bytes to immutable Git commits

- **ID**: ticket-034
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continuing repairs, merging
and testing the Forge/SubLLM/Polycell harness. Writer: agent:codex, session
codex-assembly-git-20261115.

Freeze verified package files before assembly and bind any recorded Git commit
to those exact bytes and the flat package layout. A clean status alone is not
proof: index flags can hide coherent replacements, and a source may be committed
again while an application is being copied. Reject mismatched committed content
before publishing; keep the recorded manifest digest and copied source bound to
the same private snapshot. Preserve record_git=False, non-Git packages, existing
lock/manifest formats, SHA-1/SHA-256 Git repositories and atomic output cleanup.
No cell, host, transport, dependency or governance changes.

## Acceptance criteria

- [x] AC-01: Hidden/uncommitted or incomplete Git package contents cannot be recorded as a matching committed package, even when git status is clean.
- [x] AC-02: Concurrent source edits/commits during copy cannot change frozen application bytes or their recorded Git/manifest identity; supported clean and non-Git modes remain valid.
- [x] AC-03: Regression, real Python/TS/Rust qualification and Git bundles, assembly, parity, TestQL, DB/MCP and governance pass before protected independent publication.

## Validation

Six initial regression methods expose five failures on old source, including
hidden coherent edits and a new commit incorrectly relabeling copied code.
The final nine methods also cover SHA-256 Git, missing/extra committed files,
committed symlink modes, newline normalization and output/source overlap.
Assembly compares the flat committed tree with raw snapshot object IDs using
Git's own object format, without clean filters. It never relies on status alone
and refuses output inside a source package. Explicit record_git=False still
accepts verified working files and records no commit.

`make check test` passes 221 tests. Three complete-file replacement fixtures
(Python/TS/Rust) pass real Docker qualification, Git commit/bundle/clone and
assembly with generated artifacts and conformance. Each source repository is
edited and committed while its source file is copied: the resulting app and
lock retain the earlier frozen bytes/commit. A subsequent assembly captures
the newer commits consistently. Three coherent edits hidden by index flags
are rejected without publishing output; explicit uncommitted assembly passes.
The audit makes zero native inference calls and changes no generator behavior.

The application passes 45 parity calls, TestQL 5/5, checkout, persistence, logs
and MCP. Governance passes without errors or warnings. Existing package/lock
formats remain unchanged. These checks establish content consistency, not
Git-signature authenticity. Protected publication requires independent review
of the exact tested head; runtime evidence stays in the private cache.

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
