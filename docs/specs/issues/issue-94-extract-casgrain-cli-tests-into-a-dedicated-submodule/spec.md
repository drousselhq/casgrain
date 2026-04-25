# Issue #94 — Extract Casgrain CLI tests into a dedicated submodule

- Issue: `#94`
- Spec mode: `technical change contract`
- Intended implementation lane: `dev`
- Expected implementation PR linkage: `Closes #94`
- Upstream slices already landed on `main`:
  - PR #114 (`refactor: split the Casgrain CLI entrypoint`)
  - PR #118 (`refactor: split compiler lib into focused modules`)

## Why this slice exists

Already delivered on current `main`:
- `crates/casgrain/src/main.rs` is already a thin binary entrypoint that only collects args, prints CLI output, and exits.
- The compiler half of the old `#94` umbrella already landed in PR #118.
- The first CLI split already landed in PR #114, which moved the runtime entrypoint logic out of `main.rs` and into `crates/casgrain/src/cli.rs`.

Current-main evidence for the remaining CLI work:
- `crates/casgrain/src/cli.rs` is 1,261 lines.
- The inline `#[cfg(test)] mod tests` block begins at line 176.
- That test module accounts for 1,086 lines, leaving only 175 production lines above it.

That leaves one honest bounded next step for `#94`: move the in-file CLI tests into `crates/casgrain/src/cli/tests.rs`, keep `cli.rs` as the production dispatch/reporting surface, and close the issue once that behavior-preserving split lands.

## Scope of this slice

This slice must:
1. extract the entire current inline `#[cfg(test)] mod tests` module from `crates/casgrain/src/cli.rs` into `crates/casgrain/src/cli/tests.rs`
2. keep `crates/casgrain/src/cli.rs` as the production module that owns `run`, usage/render helpers, compile/read helpers, and run-summary/status rendering
3. preserve current command wiring and behavior for `compile`, `run-mock`, `run-ios-smoke`, and `run-android-smoke`
4. preserve the current fake-runner, temp-file, and failure-fixture test helpers with the moved tests instead of widening runtime code
5. keep the implementation diff internal-only and behavior-preserving so the implementation PR does not need user-facing docs or spec changes

## Required implementation artifacts

### 1. CLI module boundary

Update:
- `crates/casgrain/src/cli.rs`
- `crates/casgrain/src/cli/tests.rs` (new)

Contract:
- `cli.rs` must continue to expose `pub(crate) fn run(args: Vec<String>) -> Result<String, String>`.
- Replace the inline test body with `#[cfg(test)] mod tests;`.
- Keep production-only helpers in `cli.rs`: command dispatch, usage/read/compile helpers, trace rendering, diagnostic rendering, and status markers.
- Do **not** change command names, argument shapes, usage text, exit behavior, or rendered success/failure text solely to justify the file move.
- Do **not** split the remaining ~175-line production CLI surface further in this issue.

### 2. Preserved CLI behavior coverage

Contract:
- Move the existing CLI tests and their local test-only helpers into `crates/casgrain/src/cli/tests.rs`.
- Preserve the current assertions around usage output, compile JSON shape, mock summary/trace output, iOS smoke summary/trace/error output, and Android smoke summary/trace/error output.
- Keep the fake iOS/Android runner scripts and temp helper functions reachable from the new tests module without promoting them into runtime code.
- If the move requires mechanical import/path repairs, keep them minimal and behavior-preserving.

### 3. Validation and handoff boundary

Contract:
- Run targeted local validation that proves the extracted test module still owns the existing CLI behavior contract:
  - `cargo test -p casgrain`
  - `cargo clippy -p casgrain --all-targets -- -D warnings`
- Run the full non-docs merge gate from `docs/validation.md` before handoff because this still touches the shared `casgrain` execution surface:
  - `git diff --check`
  - `cargo fmt --all --check`
  - `cargo test --workspace`
  - `cargo clippy --workspace --all-targets -- -D warnings`
  - `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`
  - `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
  - `cargo audit`
  - `gitleaks dir .`
  - `cargo deny check licenses sources`
- CI on the implementation PR must still report both mobile smoke checks on the candidate head; do **not** invent new local mobile-smoke commands inside this issue.
- Docs assessment for the implementation PR: no docs gate is needed if the diff remains limited to CLI module/test layout and preserves current behavior.

## Acceptance criteria

1. `crates/casgrain/src/cli.rs` no longer embeds the large inline `#[cfg(test)] mod tests` block, and `crates/casgrain/src/cli/tests.rs` becomes the home of the extracted CLI tests.
2. The extracted tests still preserve the existing CLI behavior contracts for usage text, compile output, mock runs, iOS smoke runs, Android smoke runs, and their trace/failure rendering paths.
3. The implementation PR passes the targeted `casgrain` checks (`cargo test -p casgrain`, `cargo clippy -p casgrain --all-targets -- -D warnings`) and the full non-docs merge gate from `docs/validation.md` for shared-surface work.
4. The implementation PR can honestly say `Closes #94` because PR #114 and PR #118 already landed the earlier slices, and this test-module extraction removes the final oversized CLI surface named by the issue without widening into new CLI behavior.

## Explicit non-goals

- no new CLI commands, flags, or output formats
- no compiler changes
- no runner/harness behavior changes
- no additional production CLI module redesign beyond the test-module extraction in this slice
- no docs/policy/workflow changes for the implementation PR
- no speculative abstraction added just because the file move makes it possible

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
git diff --check
cargo fmt --all --check
cargo test -p casgrain
cargo clippy -p casgrain --all-targets -- -D warnings
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only
cargo audit
gitleaks dir .
cargo deny check licenses sources
```

## Completion boundary

The implementation PR for this spec should close `#94` once the inline CLI test module is extracted, the existing CLI behavior coverage stays green, and `cli.rs` remains the production dispatch/reporting surface only.

Any future desire to split the remaining production CLI code further belongs in a new issue only if current `main` grows a new honest seam; it is not part of this slice.
