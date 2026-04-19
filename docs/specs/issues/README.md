# Issue-scoped spec artifacts

This directory holds Analyst-authored, per-issue delivery contracts.

Use one file per bounded issue or slice:

- `issue-<number>-<slug>.md`

Examples:
- `issue-101-failure-contract-coverage.md`
- `issue-75-non-cargo-cve-watch.md`

## Choose one of two honest modes

### 1. Behavior spec
Use when the slice changes observable behavior.

Recommended sections:
- Summary
- Scope
- Non-goals
- Acceptance criteria
- Gherkin scenario coverage
- Validation notes

### 2. Technical change contract
Use when the slice is non-behavioral.

Recommended sections:
- Summary
- Scope
- Non-goals
- Invariants to preserve
- Required changes
- Acceptance checks
- Validation notes

## Do not use this directory for
- broad product vision
- backlog-only PRDs
- implementation notes that should live only in a PR description

Those belong elsewhere:
- backlog PRDs -> GitHub issue body / Project item
- stable product behavior -> `docs/specs/casgrain-product-spec.md`
