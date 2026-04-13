# Merge and Validation Policy

## Goal

Casgrain should move quickly without pretending weakly validated work is safe.

This policy exists to support:
- fast forward progress
- cheap validation before expensive exploration
- self-merge of low-risk work when checks are green
- a higher bar for runtime behavior changes

## Merge classes

### Class A — safe self-merge
Examples:
- docs
- governance/process files
- issue templates
- CI improvements
- low-risk refactors

Expected bar:
- green required checks
- no unresolved review concerns

Default action:
- agent may self-merge when green

### Class B — self-merge after stronger automated validation
Examples:
- compiler lowering changes
- runner semantics
- selector resolution changes
- artifact/trace behavior
- fake-engine behavior used as deterministic validation infrastructure

Expected bar:
- green required checks
- targeted regression tests for the changed behavior
- no unexplained coverage regressions
- validation notes in the PR

Default action:
- agent may self-merge when green and well-validated

### Class C — hold for explicit human awareness
Examples:
- repository/package rename waves
- first real simulator/emulator adapters
- destructive migrations
- major public workflow changes
- significant product-direction pivots

Expected bar:
- green checks plus explicit awareness from Daniel before merge

Default action:
- prepare the PR, but do not silently merge

## Required validation

Current default required checks:
- `cargo fmt --all --check`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- `cargo audit`

## E2E policy

Casgrain should not wait for full real-device infrastructure before making progress.

Validation levels:
1. unit + fake-engine + compiler golden tests
2. fixture-app simulator/emulator smoke tests
3. richer cross-platform end-to-end validation

Until level 2 exists, many PRs can still merge using level 1.
Once level 2 exists, runtime-affecting PRs should increasingly rely on it.

## Cost discipline

Prefer:
- cheap evidence before expensive iteration
- small PRs over large speculative branches
- tests and traces over repeated token-heavy reasoning loops

## GitHub issue discipline

If work uncovers:
- a bug
- a validation gap
- a security concern
- a follow-up requirement

track it in a GitHub issue rather than relying on chat memory alone.
