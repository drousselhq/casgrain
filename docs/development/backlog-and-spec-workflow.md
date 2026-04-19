# Backlog, spec, and delivery workflow

Casgrain treats GitHub Project v2 and GitHub Issues as the Jira-like product backlog.

## Artifact hierarchy

Use this split consistently:

1. **Project item / GitHub issue body**
   - PRD / backlog artifact
   - source of truth for `what` and `why`
   - owned by PO

2. **Repo spec artifact**
   - source of truth for the current slice's delivery contract
   - lives under `docs/specs/issues/`
   - created by Analyst before Dev / DevOps starts

3. **Pull request**
   - review and merge unit
   - implements or reviews the repo artifact for that slice

Do **not** treat PRs as the primary planning/specification artifact.

## Repo spec location

Per-slice specs live under:

- `docs/specs/issues/issue-<number>-<slug>.md`

The global product behavior reference remains:

- `docs/specs/casgrain-product-spec.md`

That product spec is **not** a dumping ground for every in-flight slice. Keep issue-specific shaping in per-issue spec files. Promote stable cross-cutting behavior into the product spec deliberately when it becomes canonical product behavior.

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

A technical change contract should still be formal. It should define:
- scope
- non-goals
- invariants to preserve
- acceptance checks
- validation evidence expected

## Development-chain entry point

The true repo entry point is the **analyst-created spec-only PR**.

Expected flow:
1. PO creates or curates the PRD in the issue body / Project backlog.
2. PO backlog release hands the issue to Analyst.
3. Analyst creates the repo spec artifact and opens a **spec-only PR**.
4. That PR goes through normal review lanes.
5. After the spec-only PR merges, the issue becomes `ready-for-dev`.
6. Dev / DevOps implements against the merged repo spec artifact.

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
- turns the PRD into the repo-side delivery contract
- chooses the correct spec mode (behavior vs technical)
- opens the spec-only PR

### Dev / DevOps
- reads the PRD for context
- implements mainly against the merged repo spec artifact
- does not quietly invent the spec

### QA / Security / Docs / PO approval
- review against both:
  - issue PRD
  - repo spec artifact

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
- `docs/specs/issues/issue-...md` for bounded in-flight slice contracts
