# Ticket 013: Explicit Result and String guidance for Rust generation

- **ID**: ticket-013
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and authorization

SESSION_EXECUTION_AUTHORIZATION: the continued Forge/Polycell generation investigation and protected merge request authorize PLF-22412. A real Rust generation run at63d084c returned a bare output instead of Result, then matched &String against string literals; neither compiled, and a final changed envelope was safely rejected. Clarify these two general language rules without supplying a business implementation.

Native owner polycell-rust-guidance-20261113 was allocated at21:27:52Z with revision1/fence1. Source changes stop21:57:52Z; total owner lifetime ends22:27:52Z, no automatic extension. Preserve standard version owner429 and infrastructure writer012. This ticket owns only tools/polycell/prompt.py outside tracking carriers.

## Acceptance criteria

- [x] AC-01: Standalone Rust instructions explicitly cover Ok/Err and String.as_str while keeping the existing signature, generated type ownership, contract and examples unchanged.
- [x] AC-02: A bounded fresh generation is compiled and independently qualified, with every rejected proposal retained and no operator patching of its function body. Report the actual result, including failure if the model does not converge.
- [ ] AC-03: Existing regressions and required governance/native checks pass before independent exact-head publication. Preserve reproducible accepted package/application artifacts when available.

## Evidence boundary

Historical failures: forge-polycell-20261113/fresh-after-feedback/audits/pricing.quote. New private results and checkpoints: forge-polycell-20261113/rust-guidance/. The prompt is advice, not acceptance authority; the frozen oracle, Docker isolation and three-attempt cap remain unchanged. Do not add literal-string tests that merely repeat the prompt text.

## Measured validation and remaining limit

The existing95 tests pass in34.642s; local governance passes with zero findings. No literal-string tests were added. Contract, examples, oracle and generated types are unchanged.

The fresh run used exactly three real requests in total. The first altered Forge sentinels. The second was rejected by the native quality gate (SUBLLM-RESPONSE-QUALITY-REJECTED), but Forge hid that distinction behind generic ProviderError and stopped. After reading the native diagnostic, the remaining third request was an explicit operator continuation with envelope feedback; it reached Rust compilation but failed with mixed i32/f64 arithmetic and missing variables. No candidate was published and no function body was edited. The third request is not represented as an automatic SDK retry or a budget increase.

These are clearer language instructions, not a claim that the model now converges. The typed quality-diagnostic propagation defect is queued separately at Forge HOME. Required exact-head native CI and independent publication remain pending.

The exact-range prepublication check rejected XS with a30min estimate (XS is limited to10min). Correct the classification to S, retaining the original30min estimate, source/owner deadlines and stricter1file/1component/0interface/0dependency numeric budgets. This corrects a declaration mismatch without expanding implementation. The original failure is retained externally. Rebased onto independently merged infrastructure PR11 before final checks.
