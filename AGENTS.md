# AGENTS.md

Project operating contract for Casgrain.

## 1. Project identity

Casgrain is an open-source mobile automation runtime for iOS simulators and Android emulators.

Primary goals:
- deterministic CI/CD execution
- strong local developer ergonomics
- first-class agent workflows for exploration, authoring, and repair

## 2. Source of truth

- Repo docs are canonical for shipped behavior and contributor expectations.
- `docs/specs/casgrain-product-spec.md` is the canonical product behavior spec.
- GitHub Issues and the Casgrain GitHub Project v2 board are the backlog and prioritization source of truth.
- Pull Requests are the review and merge unit.

## 3. Standard workflow

For non-trivial work:
1. Shape the request
2. Write or update the spec when behavior changes
3. Execute one bounded slice
4. Validate
5. Review
6. Reconcile issues, Project state, and docs

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
- Reconcile issues, Project state, and docs after each slice.
- Preserve a clean history of decisions in issues, PRs, or ADRs.
- Avoid leaving stale documentation on main.

## 9. Automation integration

- Casgrain may be operated by the external `agent-team-orchestrator` repository.
- This repository keeps only the minimum local integration contract needed for contributors and automation.
- Agent prompts, cron topology, lane responsibilities, and workflow internals belong in `agent-team-orchestrator`, not here.

## 10. If you are unsure

When trade-offs are unclear, prefer:
- clearer architecture
- more explicit tests
- smaller scope
- better docs
- cheaper validation first
