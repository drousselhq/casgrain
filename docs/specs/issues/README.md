# Issue-scoped implementation artifacts

This directory holds Analyst-authored, per-issue implementation artifacts.

Use one directory per bounded issue or slice:

- `issue-<number>-<slug>/`
  - `spec.md`
  - `tasks.md`

Examples:
- `issue-101-failure-contract-coverage/spec.md`
- `issue-101-failure-contract-coverage/tasks.md`
- `issue-75-non-cargo-cve-watch/spec.md`
- `issue-75-non-cargo-cve-watch/tasks.md`

## Artifact roles

### `spec.md`
`spec.md` is the bounded delivery contract for the slice.

Choose one of two honest modes:

#### 1. Behavior spec
Use when the slice changes observable behavior.

Recommended sections:
- Summary
- Scope
- Non-goals
- Acceptance criteria
- Gherkin scenario coverage
- Validation notes

#### 2. Technical change contract
Use when the slice is non-behavioral.

Recommended sections:
- Summary
- Scope
- Non-goals
- Invariants to preserve
- Required changes
- Acceptance checks
- Validation notes

### `tasks.md`
`tasks.md` is the ordered execution checklist for the same bounded slice.

It should:
- stay aligned with `spec.md`
- list tasks in the order Dev / DevOps should execute them
- be specific enough that progress can be shown honestly via checkboxes
- avoid hidden scope or umbrella follow-ups that should be separate issues

If `tasks.md` conflicts with `spec.md`, `spec.md` wins and the slice should be reshaped instead of improvised.

## Legacy note

Older single-file issue specs may remain in this directory for already-shaped historical slices.
New analyst handoffs should use the per-issue directory form above.

## Do not use this directory for
- broad product vision
- backlog-only PRDs
- implementation notes that should live only in a PR description

Those belong elsewhere:
- backlog PRDs -> GitHub issue body / Project item
- stable product behavior -> `docs/specs/casgrain-product-spec.md`
