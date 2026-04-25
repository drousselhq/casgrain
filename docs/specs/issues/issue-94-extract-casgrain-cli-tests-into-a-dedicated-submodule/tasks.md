# Issue #94 — Implementation tasks

- Linked issue: `#94`
- Source contract: `./spec.md`

## 1. Confirm the remaining `#94` slice is still current on `main`
- [ ] 1.1 Verify `crates/casgrain/src/main.rs` is still a thin entrypoint and `crates/casgrain/src/cli.rs` still contains the inline `#[cfg(test)] mod tests` block.
- [ ] 1.2 Verify `crates/casgrain/src/cli/tests.rs` does not already exist on current `main`.
- [ ] 1.3 Reconfirm that PR #114 and PR #118 already landed, so this issue is only the remaining CLI test-module extraction.
- Goal: Start from the real current-main boundary instead of reviving the older umbrella wording from before the compiler and entrypoint splits landed.
- Validation:

  ```bash
  python3 - <<'PY'
  from pathlib import Path
  main = Path('crates/casgrain/src/main.rs').read_text(encoding='utf-8')
  cli = Path('crates/casgrain/src/cli.rs').read_text(encoding='utf-8')
  assert 'mod cli;' in main, 'main.rs no longer uses the expected cli module entrypoint'
  assert '#[cfg(test)]\nmod tests {' in cli, 'cli.rs no longer contains the inline test module'
  assert not Path('crates/casgrain/src/cli/tests.rs').exists(), 'cli/tests.rs already exists on current main'
  print('current main still matches the remaining issue-94 slice')
  PY
  ```
- Non-goals: No production edits yet and no reopening of compiler work already shipped in PR #118.
- Hand back if: Current `main` already extracted the CLI tests, changed the CLI surface materially, or no longer reflects the remaining slice frozen in `spec.md`.

## 2. Extract the inline CLI tests into `crates/casgrain/src/cli/tests.rs`
- [ ] 2.1 Create `crates/casgrain/src/cli/tests.rs` and move the entire current inline test module there.
- [ ] 2.2 Replace the inline test body in `crates/casgrain/src/cli.rs` with `#[cfg(test)] mod tests;`.
- [ ] 2.3 Keep `cli.rs` limited to the production dispatch/reporting helpers already frozen in `spec.md`.
- Goal: Remove the oversized inline test block from `cli.rs` while leaving the production CLI surface small and recognizable.
- Validation: `cargo test -p casgrain`
- Non-goals: No command/flag changes, no render-text changes, and no extra production-module breakup beyond the test-module extraction.
- Hand back if: The move would require changing public CLI behavior or reopening a broader production-code redesign to compile cleanly.

## 3. Repair only the minimal module-path fallout inside the moved tests
- [ ] 3.1 Fix imports, module paths, and `super::...` references only where the new file location requires it.
- [ ] 3.2 Keep the fake runner, temp-path, and temp-feature helpers inside the test module instead of promoting test-only helpers into runtime code.
- [ ] 3.3 Preserve the existing assertions for usage, compile output, mock runs, iOS smoke runs, Android smoke runs, and failure rendering unless a change is purely mechanical from the file move.
- Goal: Keep the diff behavior-preserving and focused on module boundaries instead of smuggling in cleanup or new abstractions.
- Validation: `cargo test -p casgrain`
- Non-goals: No new test scenarios, no helper API redesign, and no widening into compiler or runner changes.
- Hand back if: The moved tests reveal a real behavior contradiction on current `main` that this refactor-only slice cannot fix honestly.

## 4. Run targeted CLI validation on the extracted module layout
- [ ] 4.1 Re-run `cargo test -p casgrain` on the moved test layout.
- [ ] 4.2 Re-run `cargo clippy -p casgrain --all-targets -- -D warnings`.
- [ ] 4.3 Confirm the extracted test file still owns the current CLI behavior contract instead of silently dropping coverage.
- Goal: Prove the module split preserves the current Casgrain CLI behavior contract before widening to full-repo validation.
- Validation: `cargo test -p casgrain && cargo clippy -p casgrain --all-targets -- -D warnings`
- Non-goals: No repo-wide cleanup unrelated to the CLI module boundary.
- Hand back if: The targeted CLI validation fails for a reason that requires behavior changes rather than a pure module move.

## 5. Run the full non-docs merge gate and hand back with honest closure semantics
- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Run `cargo fmt --all --check`.
- [ ] 5.3 Run `cargo test --workspace`.
- [ ] 5.4 Run `cargo clippy --workspace --all-targets -- -D warnings`.
- [ ] 5.5 Run `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`.
- [ ] 5.6 Run `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`.
- [ ] 5.7 Run `cargo audit`.
- [ ] 5.8 Run `gitleaks dir .`.
- [ ] 5.9 Run `cargo deny check licenses sources`.
- [ ] 5.10 In the PR summary/comment, state that the implementation PR `Closes #94`, note that this is the final remaining slice after PR #114 and PR #118, and call out that CI on the candidate head must still report both shared-surface mobile smoke checks.
- [ ] 5.11 State that no docs gate is needed for the implementation PR if the final diff stays limited to the internal CLI module/test layout.
- Goal: Leave QA with one honest picture of what changed, what validated locally, and why `#94` is complete once the extracted test module lands without narrowing the canonical merge gate from `docs/validation.md`.
- Validation: `git diff --check && cargo fmt --all --check && cargo test --workspace && cargo clippy --workspace --all-targets -- -D warnings && RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps && cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only && cargo audit && gitleaks dir . && cargo deny check licenses sources`
- Non-goals: No docs/policy edits, no new follow-up issue unless the module split exposes genuinely new remaining scope, and no repo-local exception to the canonical validation policy.
- Hand back if: The final diff no longer stays internal-only, the shared-surface validation regresses, or the implementation PR cannot honestly `Closes #94`.
