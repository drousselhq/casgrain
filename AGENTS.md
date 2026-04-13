# AGENTS.md

Project operating contract for Casgrain.

## 1. Project identity

Casgrain is an open-source mobile automation runtime for iOS simulators and Android emulators.

Primary goals:
- deterministic CI/CD execution
- strong local developer ergonomics
- first-class agent workflows for exploration, authoring, and repair

## 2. Source of truth

- Repo docs are canonical.
- GitHub Issues are the backlog.
- `docs/plans/current-plan.md` is the active plan.
- Pull Requests are the review and merge unit.

## 3. Standard workflow

For non-trivial work:
1. Shape the request
2. Write or update the spec when behavior changes
3. Update the current plan
4. Execute one bounded slice
5. Validate
6. Review
7. Reconcile project state

## 4. Autonomy rules

Allowed by default:
- inspect repo state, issues, PRs, and CI
- choose the next bounded task from approved work
- implement one bounded slice at a time
- run validation
- update docs/specs when implementation reveals they need clarification
- open GitHub Issues for discovered follow-up work
- open Pull Requests autonomously
- merge only low-risk changes that do not change product behavior or developer experience

Require human review before proceeding:
- product behavior changes
- developer experience changes
- major architecture changes
- destructive migrations
- scope expansion across multiple slices
- ambiguous situations where the right next step is unclear

## 5. Artifact model

Required:
- `AGENTS.md`
- project charter / PRD
- behavior spec (`docs/specs/casgrain-product-spec.md`)
- architecture notes / ADRs
- `docs/plans/current-plan.md`
- `docs/validation.md`

Recommended:
- PR template
- issue templates
- decision log

## 6. Validation policy

`docs/validation.md` is the source of truth for required checks and quality gates.

## 7. Escalation rules

Stop and ask when:
- requirements are unclear
- a change would alter product behavior or developer experience
- an architectural tradeoff needs a decision
- a change would cross a high-risk boundary
- evidence is insufficient to proceed safely

## 8. Change discipline

- Keep diffs small and focused.
- Prefer evidence over speculation.
- Reconcile plan, issues, and docs after each slice.
- Preserve a clean history of decisions in issues, PRs, or ADRs.
- Avoid leaving stale documentation on main.

## 9. Current plan handling

- Keep the current plan file small and actively maintained.
- Archive old plans only when the project becomes complex enough that the live plan is no longer readable.
- Move history into archived plan files only when needed.

## 10. If you are unsure

When trade-offs are unclear, prefer:
- clearer architecture
- more explicit tests
- smaller scope
- better docs
- cheaper validation first
