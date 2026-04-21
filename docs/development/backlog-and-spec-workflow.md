# Backlog, spec, and delivery workflow

Casgrain treats GitHub Project v2 and GitHub Issues as the Jira-like product backlog.

## Artifact hierarchy

Use this split consistently:

1. **Project item / GitHub issue body**
   - PRD / backlog artifact
   - source of truth for `what` and `why`
   - owned by PO

2. **Repo implementation artifacts**
   - source of truth for the current slice's delivery contract and ordered execution plan
   - live under `docs/specs/issues/`
   - created by Analyst before Dev / DevOps starts
   - consist of:
     - `spec.md` — the bounded delivery contract
     - `tasks.md` — the ordered execution checklist for the same slice

3. **Pull request**
   - review and merge unit
   - implements or reviews the repo artifacts for that slice

Do **not** treat PRs as the primary planning/specification artifact.

## Repo artifact location

New issue-scoped artifacts live under:

- `docs/specs/issues/issue-<number>-<slug>/spec.md`
- `docs/specs/issues/issue-<number>-<slug>/tasks.md`

The global product behavior reference remains:

- `docs/specs/casgrain-product-spec.md`

That product spec is **not** a dumping ground for every in-flight slice. Keep issue-specific shaping in per-issue artifacts. Promote stable cross-cutting behavior into the product spec deliberately when it becomes canonical product behavior.

Legacy note:
- older single-file issue specs may remain for already-shaped historical slices until they are superseded
- new analyst handoffs should use the directory form above

## Which spec style to use

### Use Gherkin / scenario coverage when the slice changes observable behavior

Examples:
- CLI behavior
- runtime outputs
- machine-readable contract fields
- compiler / runner behavior
- user-visible or agent-visible behavior

### Use a technical change contract when the slice is non-behavioral

Examples:
- refactors
- infrastructure
- workflow automation
- docs-only alignment
- internal module/layout work

A technical change contract in `spec.md` should still be formal. It should define:
- scope
- non-goals
- invariants to preserve
- acceptance checks
- validation evidence expected

## Task-list rules

`tasks.md` is the ordered execution plan for the bounded slice.

Required rules:
- Dev / DevOps executes `tasks.md` in order
- task checkboxes are updated honestly as work lands on the PR branch
- if `tasks.md` conflicts with `spec.md`, `spec.md` wins
- if either artifact is stale, missing a prerequisite, or no longer matches current `main`, hand the issue back for Analyst reshaping instead of improvising a wider slice

## Development-chain entry point

The true repo entry point is the **analyst-created spec-only PR**.

Expected flow:
1. PO creates or curates the PRD in the issue body / Project backlog.
2. PO backlog release hands the issue to Analyst.
3. Analyst creates the issue-scoped `spec.md` and `tasks.md` artifacts and opens a **spec-only PR**.
4. That PR goes through normal review lanes.
5. After the spec-only PR merges, the issue becomes `ready-for-dev`.
6. Dev / DevOps implements against the merged repo artifacts.

## Workflow labels that matter here

Issue-side:
- `needs-analyst` — queued for Analyst shaping
- `spec-in-review` — Analyst has an open spec-only PR for the issue
- `ready-for-dev` — merged repo contract exists; implementation may begin
- `in-dev` — implementation in progress
- `blocked`
- `waiting-on-human`

PR-side:
- `analyst-spec` — this PR is the Analyst-created spec-entry PR
- `waiting-on-human` — explicit hold for required human action; the PR must also carry a comment explaining the action and return path back into automation
- plus the normal delivery labels (`needs-qa`, `qa-passed`, `needs-security`, `needs-po`, `needs-merge`, docs/security labels)

## Responsibilities by lane

### PO
- writes and curates PRDs in issues / Project items
- decides when a backlog item is ready for Analyst

### Analyst
- turns the PRD into the repo-side delivery contract and ordered task list
- chooses the correct spec mode (behavior vs technical)
- opens the spec-only PR

### Dev / DevOps
- reads the PRD for context
- implements against `spec.md`
- follows `tasks.md` in order instead of inventing ad hoc work
- hands the slice back for reshaping when the merged artifacts are stale or contradictory

### QA / Security / Docs / PO approval
- review against both:
  - issue PRD
  - merged repo artifacts (`spec.md` + `tasks.md`)

### Merge
- merges the selected PR
- reconciles the linked issue honestly after merge

## Rule against a single monolithic in-flight spec file

Do **not** collapse all analyst output into one huge `casgrain_spec.md` for day-to-day slice work.

Why:
- it will become an edit hotspot
- unrelated slices will conflict constantly
- review context becomes noisy
- partial backlog progress becomes harder to trace
- the repo loses clear per-issue auditability

Use:
- `docs/specs/casgrain-product-spec.md` for stable product-level behavior
- `docs/specs/issues/issue-.../spec.md` and `tasks.md` for bounded in-flight slice contracts
