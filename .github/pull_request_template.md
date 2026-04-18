## Summary
- 
- 
- 

## Change type
- [ ] docs
- [ ] ci / automation
- [ ] refactor
- [ ] domain / compiler / runner behavior
- [ ] adapter / integration work
- [ ] governance / process

## Validation
- [ ] `cargo fmt --all --check`
- [ ] `cargo test --workspace`
- [ ] `cargo clippy --workspace --all-targets -- -D warnings`
- [ ] `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`
- [ ] `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- [ ] `cargo audit`
- [ ] `gitleaks dir .`
- [ ] `cargo deny check licenses sources`
- [ ] other validation noted below

## Merge gate acknowledgement
- [ ] I confirmed this PR should not merge until the required checks above are green or an explicitly documented docs/governance exception applies.
- [ ] I recorded any exception, skipped check, or path-scoped extra validation below.
- [ ] I confirmed whether `ios-simulator-smoke` is required for this diff.

## Notes for reviewers
- risk level:
- expected follow-up work:
- current plan item or issue:
- relevant issues:

## Additional validation details
```text
Paste useful command output, screenshots, traces, or notes here.
```
