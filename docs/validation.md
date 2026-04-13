# Validation Policy

This document is the canonical place for Casgrain validation rules and quality gates.

## Default merge gate

Before merging work, run the required checks below unless the PR is explicitly scoped as a narrowly exempted docs-only or governance-only change and the reviewer accepts the exception.

Required checks:
- `cargo fmt --all --check`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- `cargo audit`
- `gitleaks dir .`
- `cargo deny check licenses sources`

## Validation style

- Prefer cheap evidence before expensive exploration.
- Add targeted regression tests for behavior changes.
- Keep validation focused on the changed area first, then widen only if needed.
- Treat structured traces, logs, and artifacts as first-class evidence.

## When extra validation is needed

- Add targeted validation when work touches:
- compiler lowering
- runner semantics
- selector resolution
- trace / artifact behavior
- adapter or integration boundaries
- iOS simulator interaction
- security-sensitive code paths

## Reporting standard

When reporting completion, include:
- what was changed
- which validation commands ran
- whether any follow-up work was opened in GitHub Issues
- any known risks or exceptions
