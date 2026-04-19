# Validation Policy

This document is the canonical place for Casgrain validation rules and quality gates.

## Default merge gate

Before merging work, run the required checks below unless the PR is explicitly scoped as a narrowly exempted docs-only or governance-only change and the reviewer accepts the exception.

Repository reality today:
- `main` is protected with required `validate`, `coverage`, `gitleaks`, `cargo-audit`, and `cargo-deny-policy` status checks
- expensive simulator/emulator smoke workflows are manual-only so unsolicited public PRs do not automatically burn minutes
- smoke runs are advisory evidence, not a separate qualification gate; do not delay unrelated work on a future-run streak
- if a smoke run exposes a concrete defect, file that defect directly instead of inventing a tracker issue for qualification timing
- CodeQL runs on PRs and `main` pushes as an always-on static-analysis baseline for Actions workflow logic and Rust code; keep it advisory until the workflow proves stable on this repo
- PR authors and mergers must still avoid bypassing the merge gate just because an admin path exists

Required checks:
- `cargo fmt --all --check`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- `cargo audit`
- `gitleaks dir .`
- `cargo deny check licenses sources`

First iOS vertical-slice note:
- the current product-true execution proof is intentionally narrow: one fixture-specific iOS scenario compiled from `fixtures/ios-smoke/features/tap_counter.feature` and executed through `mar run-ios-smoke`
- changes that touch this slice must preserve both halves of the user-facing contract: deterministic compile output shape and the CLI execution/reporting path
- the older handwritten XCTest remains harness plumbing and debugging support under `scripts/ios_smoke.sh`; it is not sufficient evidence by itself for the user-facing slice

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
  - the fixture iOS smoke harness or its shared scheme

## Reporting standard

When reporting completion, include:
- what was changed
- which validation commands ran
- whether any follow-up work was opened in GitHub Issues
- any known risks or exceptions
