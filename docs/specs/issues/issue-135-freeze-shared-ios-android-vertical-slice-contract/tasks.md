# Issue #135 — Implementation tasks

- Linked issue: `#135`
- Source contract: `./spec.md`

## 1. Confirm the remaining work is contract reconciliation, not a missing runtime lane
- [ ] 1.1 Verify current `main` still has both tap-counter fixture features, both compiler golden-plan tests, and both smoke CLI contract tests before editing anything.
- [ ] 1.2 Verify the live `main` ruleset still requires both `ios-smoke` and `android-smoke`.
- [ ] 1.3 Verify the canonical docs named in `spec.md` still contain the stale iOS-first / Android-advisory wording that this slice is supposed to remove.
- [ ] 1.4 Verify `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md` still frames `#135` as a later parity/unblock follow-up so the repair scope stays grounded on a real current-main contradiction.
- Goal: Prove this issue now owns the remaining shared-contract freeze/reconciliation slice rather than a missing Android implementation path.
- Validation: `gh api repos/drousselhq/casgrain/rulesets/15179247 --jq '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context' && git grep -n -E 'iOS-first|parallel emulator-backed evidence lane|pending companion gate tracked by `#79`|Android parity matures separately|Bring the Android product-true vertical slice to parity with iOS|later parity work against the now-required Android gate|#135 stays downstream' -- docs/specs/casgrain-product-spec.md docs/validation.md docs/development/merge-and-validation-policy.md docs/development/test-pyramid-and-runtime-contracts.md docs/development/security-owasp-baseline.md docs/prd/product-requirements.md docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md`
- Non-goals: No production edits yet, no new issue split, no new runtime design.
- Hand back if: current `main` no longer has both live smoke gates, or the runtime surface has already changed beyond the bounded tap-counter contract frozen in `spec.md`.

## 2. Add failing compiler-level parity coverage for the shared tap-counter contract
- [ ] 2.1 Extend `crates/compiler/src/tests.rs` with one test that compiles both fixture features and normalizes only the truthful platform-specific differences named in `spec.md`.
- [ ] 2.2 Make that test assert the shared ordered step intents, selector semantics, assertion semantics, and default execution policy for the current tap-counter slice.
- [ ] 2.3 Verify the new test would fail if one fixture drifted in shared user-facing semantics while only target/source/screenshot naming differed.
- Goal: Freeze the compiler-side shared contract so future platform drift becomes a repo-visible regression instead of doc-only mismatch.
- Validation: `cargo test -p compiler`
- Non-goals: No new fixture steps, no broader Gherkin expansion, no new CLI surface.
- Hand back if: the two fixture plans already diverge in real user-facing semantics and the slice would require product-scope decisions instead of a bounded parity guard.

## 3. Add failing CLI trace-contract parity coverage for the two smoke entrypoints
- [ ] 3.1 Extend `crates/casgrain/src/cli.rs` with one test that compares normalized iOS and Android smoke output on the existing fake-runner path.
- [ ] 3.2 Make that test assert the shared passed/failed run semantics, per-step failure structure, and artifact-to-step linkage while allowing truthful platform metadata and additive artifact differences.
- [ ] 3.3 Keep the comparison bounded to the current smoke commands `run-ios-smoke` and `run-android-smoke`; do not invent a new runtime interface in this slice.
- Goal: Freeze the user-facing smoke summary / `--trace-json` contract at the CLI boundary for both platforms.
- Validation: `cargo test -p casgrain`
- Non-goals: No new command names, no emulator/simulator harness rewrite, no broader runtime refactor.
- Hand back if: the existing fake-runner coverage cannot express the shared contract without redesigning the CLI shape itself.

## 4. Reconcile the canonical docs and older issue-spec to the shipped dual-platform slice
- [ ] 4.1 Update `docs/specs/casgrain-product-spec.md` so the first product-true slice is framed as the current shared iOS/Android tap-counter contract, not an iOS-first / Android-advisory split.
- [ ] 4.2 Update `docs/validation.md`, `docs/development/merge-and-validation-policy.md`, and `docs/development/test-pyramid-and-runtime-contracts.md` so they match the live rule that both `ios-smoke` and `android-smoke` are required mobile merge-gate checks on `main`.
- [ ] 4.3 Update `docs/development/security-owasp-baseline.md` so it no longer says `android-smoke` is the pending companion gate tracked by `#79`.
- [ ] 4.4 Update `docs/prd/product-requirements.md` so it no longer leaves the current slice as an unresolved iOS-first vs dual-platform sequencing question.
- [ ] 4.5 Reconcile `docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md` so it stops presenting `#135` as a future parity/unblock follow-up and instead points at the already-live required Android gate plus this docs/test contract-freeze slice.
- [ ] 4.6 Keep archived history docs untouched unless a touched canonical doc explicitly points at them as current truth.
- Goal: Leave one truthful repo-wide description of the shipped bounded vertical slice and the live merge gate around it.
- Validation: `git grep -n -E 'iOS-first|parallel emulator-backed evidence lane|pending companion gate tracked by `#79`|Android parity matures separately|Bring the Android product-true vertical slice to parity with iOS|later parity work against the now-required Android gate|#135 stays downstream' -- docs/specs/casgrain-product-spec.md docs/validation.md docs/development/merge-and-validation-policy.md docs/development/test-pyramid-and-runtime-contracts.md docs/development/security-owasp-baseline.md docs/prd/product-requirements.md docs/specs/issues/issue-79-promote-android-smoke-to-a-required-merge-gate-on-main/spec.md`
- Non-goals: No historical-plan rewrite, no roadmap expansion beyond the current tap-counter slice.
- Hand back if: making the docs truthful would require reopening product-scope questions beyond the already-shipped bounded slice.

## 5. Run bounded validation and prepare the QA handoff
- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Run `cargo test -p compiler`.
- [ ] 5.3 Run `cargo test -p casgrain`.
- [ ] 5.4 Re-check the live ruleset contexts and confirm the updated docs match them exactly.
- [ ] 5.5 In the PR summary, state that the runtime parity already existed on `main`, list the exact validation commands, and keep the PR scoped to contract/tests/docs reconciliation for `#135`.
- Goal: Hand QA a bounded contract-freeze PR with concrete validation evidence and no hidden runtime-scope expansion.
- Validation: `git diff --check && cargo test -p compiler && cargo test -p casgrain && gh api repos/drousselhq/casgrain/rulesets/15179247 --jq '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context'`
- Non-goals: No live ruleset mutation, no separate follow-up tracker, no new platform capability work.
- Hand back if: the branch needs broader runtime changes than the bounded compiler/CLI/docs freeze described in `spec.md`.
