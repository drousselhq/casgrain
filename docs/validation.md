# Validation Policy

This document is the canonical place for Casgrain validation rules and quality gates.

It pairs with `docs/development/test-pyramid-and-runtime-contracts.md`, which explains what kinds of tests should exist, what stronger expectations apply to critical logic, and how to interpret coverage beyond the baseline CI floor.

## Default merge gate

Before merging work, run the required checks below unless the PR is explicitly scoped as a narrowly exempted docs-only or governance-only change and the reviewer accepts the exception.

Repository reality today:
- `main` is protected with required `validate`, `coverage`, `gitleaks`, `cargo-audit`, `cargo-deny-policy`, `analyze (actions)`, `analyze (rust)`, `ios-smoke`, and `android-smoke` status checks
- both mobile smoke workflows always report a PR status on candidate heads, but self-skip unless the change touches their owned platform or shared runtime surfaces; this keeps the required mobile contexts present without paying the full simulator/emulator cost on unrelated work
- both mobile smoke workflows also run on qualifying pushes to `main` plus a nightly schedule so `cve-watch` can consume fresh `main` host evidence after runner-host changes land
- CodeQL participates in the required merge gate through `analyze (actions)` and `analyze (rust)` while also remaining the always-on static-analysis baseline for workflow logic and Rust code
- the `coverage` job still enforces the same 75% workspace line-coverage floor, publishes a GitHub step summary plus uploaded `coverage-summary.json`, `coverage-report.json`, and `lcov.info` artifacts, and on pull requests it also checks that overall line coverage does not regress below the latest successful `main` coverage artifact when that baseline is available
- PR authors and mergers must still avoid bypassing the merge gate just because an admin path exists

Required checks:
- `cargo fmt --all --check`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`
- `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- `cargo audit`
- `gitleaks dir .`
- `cargo deny check licenses sources`

## Inspecting coverage locally

Use the same low-churn flow as CI when you need more than a pass/fail answer:

```bash
mkdir -p target/llvm-cov
cargo llvm-cov \
  --workspace \
  --all-features \
  --fail-under-lines 75 \
  --summary-only \
  --json \
  --output-path target/llvm-cov/coverage-summary.json
cargo llvm-cov report --lcov --output-path target/llvm-cov/lcov.info
python3 tests/test-support/scripts/coverage_report.py \
  --input target/llvm-cov/coverage-summary.json \
  --repo-root . \
  --threshold 75 \
  --summary-out target/llvm-cov/coverage-report.json \
  --markdown-out target/llvm-cov/coverage-report.md
```

Artifacts produced by this flow:
- `target/llvm-cov/coverage-summary.json` — raw cargo-llvm-cov summary data
- `target/llvm-cov/coverage-report.json` — distilled totals plus scope/file rollups for future ratchet tooling
- `target/llvm-cov/coverage-report.md` — human-readable summary suitable for PR notes or local review
- `target/llvm-cov/lcov.info` — LCOV export for downstream tooling

On pull requests, CI also compares `coverage-report.json` against the latest successful `main` coverage artifact with `tests/test-support/scripts/coverage_regression_check.py`. That check is intentionally narrow: it blocks only overall line-coverage regression when the `main` baseline artifact is available, while the stronger changed-code and critical-logic expectations still rely on reviewer judgment.

Coverage interpretation:
- that floor is the baseline merge gate, not the full testing policy for new work
- contributors should also follow the documented review policy to target **85%+ coverage on new or materially changed code** and **90%+ on critical core logic** where the metric is meaningful
- until touched/new-code coverage tooling lands, authors and reviewers must still apply the stronger 85%+/90%+ expectations through targeted tests, honest PR notes, and no-unexplained-regression discipline beyond the automated overall-line non-regression check

First shared mobile vertical-slice note:
- the current product-true execution proof is intentionally narrow: one shared tap-counter scenario compiled from `tests/test-support/fixtures/ios-smoke/features/tap_counter.feature` and `tests/test-support/fixtures/android-smoke/features/tap_counter.feature`, then executed through `casgrain run-ios-smoke` and `casgrain run-android-smoke`
- changes that touch this slice must preserve both halves of the user-facing contract: deterministic compile output shape and the CLI execution/reporting path across both mobile smoke entrypoints
- the older handwritten XCTest remains harness plumbing and debugging support under `tests/test-support/scripts/ios_smoke.sh`; it is not sufficient evidence by itself for the user-facing slice

## Validation style

- Prefer cheap evidence before expensive exploration.
- Add targeted regression tests for behavior changes.
- Keep validation focused on the changed area first, then widen only if needed.
- Treat structured traces, logs, and artifacts as first-class evidence.
- Prefer deterministic tests and fixtures over timing-sensitive or environment-sensitive checks.

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
  - critical core logic whose review bar should exceed the workspace-wide baseline

## Mobile smoke workflow policy

- Casgrain's current product-true mobile merge gate is both `ios-smoke` and `android-smoke`.
- Both mobile smoke workflows are required PR checks on `main`.
- Both workflows always report a PR status, but each only runs the expensive simulator/emulator path when the PR touches its owned platform or shared execution surfaces; qualifying pushes to `main` also run the device path so fresh host evidence exists after runner-host changes merge.
- There is no separate Android-only reliability-window, reliability-qualification tracker, future-run streak requirement, or GitHub issue-management layer for Android smoke; if the required check exposes a concrete defect, file that defect directly.
- The Android workflow must still validate and archive an explicit artifact contract: `trace.json` plus stable sibling artifacts on success, or `failure.json` plus referenced diagnostics for runner-managed failure paths, with `failure_class`/`evidence-summary.json` capturing the machine-readable outcome. Empty, malformed, or failed `uiautomator` dump capture should stay inside that runner-managed contract as `ui-dump-failure`, preserving `ui-last.xml` (empty when the dump yielded no bytes) plus any truthful foreground diagnostics when available. If the workflow cannot produce either bundle, it should fail explicitly as an `artifact-contract-breach`.
- Changes limited to docs, governance, labels, or other non-runtime surfaces should not pay the full mobile smoke cost.
- Shared execution surfaces (`casgrain`, `compiler`, `runner`, `domain`, `application`, root Cargo manifests) should trigger both mobile smoke workflows because they can regress either platform.

## Reporting standard

When reporting completion, include:
- what was changed
- which validation commands ran
- whether any follow-up work was opened in GitHub Issues
- any known risks or exceptions
- whether coverage expectations above the baseline CI floor were satisfied directly, deferred explicitly, or not meaningful for the diff
