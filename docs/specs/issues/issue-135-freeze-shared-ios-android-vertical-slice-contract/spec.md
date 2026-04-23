# Issue #135 — Freeze the shared iOS/Android product-true vertical-slice contract

- Issue: `#135`
- Spec mode: `technical`
- Expected implementation PR linkage: `Closes #135`

## Why this slice exists

Already delivered on `main`:
- issue `#58` landed the first Android Gherkin -> executable plan -> emulator-backed tap-counter slice.
- `crates/compiler/src/tests.rs` already pins golden plan JSON for both `tests/test-support/fixtures/ios-smoke/features/tap_counter.feature` and `tests/test-support/fixtures/android-smoke/features/tap_counter.feature`.
- `crates/casgrain/src/cli.rs` already covers success summaries, failure summaries, and `--trace-json` contracts for both `run-ios-smoke` and `run-android-smoke`.
- the live `main` ruleset now requires both `ios-smoke` and `android-smoke` status contexts.

The remaining gap is not a missing Android execution path on current `main`; it is that the repo's canonical docs still describe the first product-true slice as iOS-first / Android-advisory even though the shipped fixture slice and live merge gate are now dual-platform.

## Scope of this slice

Freeze the current bounded shared contract for the tap-counter vertical slice and reconcile the repo docs to that reality.

This slice must:
1. keep the supported user-facing vertical slice intentionally tiny
2. treat iOS and Android as the same bounded product-true slice from the user's point of view
3. allow platform-specific target metadata and additive diagnostics/artifacts below that common contract
4. reconcile the canonical docs that still describe Android as advisory or future promotion work
5. add one explicit repo-side parity guard so future changes cannot silently drift the two fixture slices apart while the docs still claim a shared contract

## Non-goals

- no new product capability beyond the existing tap-counter vertical slice
- no new CLI surface such as a unified `run-smoke` command
- no general-purpose Android adapter expansion beyond the existing fixture-backed path
- no change to the live GitHub ruleset or required-check inventory in this slice
- no rewrite of historical archive material like `docs/plans/2026-04-13-full-ios-vertical-slice.md` just to erase the original iOS-first delivery history

## Technical change contract

### Invariants to preserve
- `tests/test-support/fixtures/ios-smoke/features/tap_counter.feature` and `tests/test-support/fixtures/android-smoke/features/tap_counter.feature` remain the bounded user-facing proof for the current slice.
- Platform-specific differences stay limited to truthful target/device details and additive artifact/diagnostic fields.
- The current commands `casgrain run-ios-smoke` and `casgrain run-android-smoke` remain the live fixture entrypoints for this slice.
- The live ruleset continues to require both `ios-smoke` and `android-smoke`; this PR only reconciles repo truth to that already-live state.

### Required changes

#### 1. Add one explicit compiler-level parity guard
Update `crates/compiler/src/tests.rs` so current `main` has a test that normalizes the two tap-counter fixture plans down to the shared user-facing contract and proves they stay aligned.

That normalization must ignore only the truthful platform-specific fields already expected to differ, such as:
- `target.platform`
- `target.device_class`
- source file path / feature metadata
- platform-specific screenshot name (`tap-counter` vs `android-tap-counter`)

The guard must still assert that both fixtures preserve the same bounded user-visible semantics:
- same ordered step intents
- same launch/tap/assert/screenshot step structure
- same selector semantics
- same assertion semantics
- same default timeout / polling / artifact policy

#### 2. Add one explicit CLI trace-contract parity guard
Update `crates/casgrain/src/cli.rs` so current `main` has a test that compares the normalized `--trace-json` / summary contract for the two smoke entrypoints on the existing fake-runner path.

The guard must prove that both platform entrypoints preserve the same bounded user-facing semantics for:
- passed and failed run statuses
- per-step status / attempts / failure-code structure
- artifact linkage back to the failing or screenshot step
- machine-readable trace shape expected by QA / downstream automation

The comparison may normalize truthful platform-specific differences such as device platform/name/version strings, screenshot artifact ids, and additive platform-specific artifact entries.

#### 3. Reconcile the canonical docs and prior issue-spec artifacts that still describe an iOS-only or advisory Android story
Update these repo-owned docs so they describe the current vertical slice as a shared iOS/Android product-true contract and match the live required-check reality:
- `docs/specs/casgrain-product-spec.md`
- `docs/validation.md`
- `docs/development/merge-and-validation-policy.md`
- `docs/development/test-pyramid-and-runtime-contracts.md`
- `docs/development/security-owasp-baseline.md`
- `docs/prd/product-requirements.md`
- `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md`
- `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/tasks.md`

Required wording outcome:
- the first product-true slice is no longer framed as iOS-first or Android-advisory on current `main`
- both `ios-smoke` and `android-smoke` are described as the live mobile merge-gate proof for the current bounded slice
- the shared contract is explicitly limited to the current tap-counter fixture behavior, not a promise of broad feature parity beyond this slice
- platform-specific evidence remains allowed where the implementation genuinely differs underneath the shared contract
- `docs/validation.md` no longer says `android-smoke` is the remaining required merge-gate promotion / close-out work for `#79`, no longer treats the current execution proof as one fixture-specific iOS scenario, and no longer frames the Android status context as something that becomes safe to require only after another workflow lands
- `docs/development/merge-and-validation-policy.md` no longer says `android-smoke` is the remaining `#79` close-out step or that the live ruleset flip is still a future action for the current shared mobile contract
- `docs/development/test-pyramid-and-runtime-contracts.md` no longer says to keep Layer 4 focused on a narrow product-true iOS slice while Android parity matures separately, and no longer frames the shared mobile merge gate as future convergence work on top of an iOS-first current slice
- `docs/prd/product-requirements.md` no longer leaves "iOS-first vs dual-platform MVP sequencing" as an unresolved current-state question for this shipped slice
- `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md` no longer presents `#135` as a future parity/unblock follow-up; it must describe `#135` as the current docs/test contract-freeze slice on top of the already-promoted Android merge gate, or otherwise remove that stale downstream framing
- `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/tasks.md` no longer preserves rollout-pending task wording as current truth for this area (for example `android-smoke` as a pending companion gate tracked by `#79`, a goal that still says the live ruleset flip is pending, or post-merge ruleset-flip tasks that still leave `#135` downstream) once this slice lands on `main`

### Acceptance checks
- `crates/compiler/src/tests.rs` contains a parity guard that would fail if the two fixture plans drift in shared user-facing semantics while only target/source/screenshot naming changed.
- `crates/casgrain/src/cli.rs` contains a parity guard that would fail if the two smoke entrypoints drift in summary / trace-json failure semantics while only truthful platform metadata differed.
- `docs/specs/casgrain-product-spec.md`, `docs/validation.md`, `docs/development/merge-and-validation-policy.md`, `docs/development/test-pyramid-and-runtime-contracts.md`, `docs/development/security-owasp-baseline.md`, `docs/prd/product-requirements.md`, `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md`, and `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/tasks.md` all match the current dual-platform tap-counter contract on `main`.
- No repo doc updated by this slice still says Android is only an advisory / future promotion lane for the current product-true tap-counter slice, and the older issue-79 spec/tasks no longer frame `#135` as future parity work or Android gate promotion as still pending current-state work.
- The implementation PR can honestly say `Closes #135` because runtime parity already exists on current `main` and this slice freezes + reconciles the remaining repo contract around that shipped reality.

## Validation notes

Minimum validation expected in the implementation PR:

```bash
git diff --check
cargo test -p compiler
cargo test -p casgrain
gh api repos/drousselhq/casgrain/rulesets/15179247 --jq '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context'
git grep -n -E 'iOS-first|parallel emulator-backed evidence lane|remaining required merge gate promotion for `#79`|first product-true execution proof is intentionally narrow: one fixture-specific iOS scenario|matching required check immediately after that workflow lands on `main`|remaining `#79` close-out step|Android parity matures separately|Bring the Android product-true vertical slice to parity with iOS|later parity work against the now-required Android gate|#135 stays downstream|live `android-smoke` ruleset flip is still pending|keep `#79` open until that verification is true on `main`' -- docs/specs/casgrain-product-spec.md docs/validation.md docs/development/merge-and-validation-policy.md docs/development/test-pyramid-and-runtime-contracts.md docs/development/security-owasp-baseline.md docs/prd/product-requirements.md docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/tasks.md
```

The final `git grep` should return no matches in those updated canonical docs.
