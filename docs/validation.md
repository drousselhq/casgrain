# Validation Policy

This document is the canonical place for Casgrain validation rules and quality gates.

## Default merge gate

Before merging work, run the required checks below unless the PR is explicitly scoped as a narrowly exempted docs-only or governance-only change and the reviewer accepts the exception.

Repository reality today:
- `main` is protected with required `validate`, `coverage`, `gitleaks`, `cargo-audit`, `cargo-deny-policy`, and `ios-smoke` status checks
- `ios-simulator-smoke` now runs on every PR, but self-skips unless the change touches iOS-smoke-impacting files; this keeps the required check present without paying the full simulator cost on unrelated work
- `android-emulator-smoke` runs automatically on PRs only when Android/shared-runtime paths change, and both mobile smoke workflows also run on a nightly schedule to catch environment drift
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
- the current product-true execution proof is intentionally narrow: one fixture-specific iOS scenario compiled from `tests/test-support/fixtures/ios-smoke/features/tap_counter.feature` and executed through `casgrain run-ios-smoke`
- changes that touch this slice must preserve both halves of the user-facing contract: deterministic compile output shape and the CLI execution/reporting path
- the older handwritten XCTest remains harness plumbing and debugging support under `tests/test-support/scripts/ios_smoke.sh`; it is not sufficient evidence by itself for the user-facing slice

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
  - Android emulator interaction
  - security-sensitive code paths
  - the fixture iOS smoke harness or its shared scheme
  - the Android smoke fixture or emulator harness

## Mobile smoke workflow policy

- `ios-simulator-smoke` is a required PR check because the first product-true vertical slice is currently iOS.
- The iOS workflow always reports a status on PRs so branch protection can enforce it safely, but it only runs the expensive simulator path when the PR touches iOS or shared execution surfaces.
- `android-emulator-smoke` is advisory for now: it auto-runs for Android/shared-runtime changes and on the nightly drift-catching schedule, but it is not yet a required branch-protection gate.
- Changes limited to docs, governance, labels, or other non-runtime surfaces should not pay the full mobile smoke cost.
- Shared execution surfaces (`casgrain`, `compiler`, `runner`, `domain`, `application`, root Cargo manifests) should trigger both mobile smoke workflows because they can regress either platform.

## Reporting standard

When reporting completion, include:
- what was changed
- which validation commands ran
- whether any follow-up work was opened in GitHub Issues
- any known risks or exceptions
