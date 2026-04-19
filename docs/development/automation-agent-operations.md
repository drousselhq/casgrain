# Automation and `agent-team-orchestrator` integration

Casgrain uses the external `agent-team-orchestrator` repository for Hermes lane prompts, cron topology, workflow-state transitions, and other automation internals.

This repository intentionally keeps only the minimum local contract needed for contributors and automation to work against the product honestly.

## Local source-of-truth split

- GitHub Issues and the Casgrain GitHub Project v2 board are the backlog and PRD source of truth.
- `docs/specs/casgrain-product-spec.md` is the canonical product-level behavior source of truth.
- `docs/specs/issues/` holds issue-level repo spec artifacts created by Analyst before Dev/DevOps starts.
- `docs/development/backlog-and-spec-workflow.md` defines the backlog -> Analyst spec-only PR -> implementation chain.
- `docs/validation.md` is the canonical validation gate.
- `docs/development/merge-and-validation-policy.md` defines local merge discipline.

## Workflow-state labels used in this repo

These labels are still the durable execution-state surface consumed by automation:

- `needs-analyst`
- `spec-in-review`
- `ready-for-dev`
- `devops`
- `in-dev`
- `needs-qa`
- `qa-failed`
- `qa-passed`
- `needs-security`
- `security-review-needed`
- `security-approved`
- `security-blocked`
- `needs-po`
- `po-approved`
- `needs-merge`
- `blocked`
- `waiting-on-human`
- `docs-needed`
- `docs-approved`
- `docs-blocked`
- `analyst-spec` (PR classification label for analyst-created spec-entry PRs)

### Human-review handoff rule

When automation needs Daniel or another human to act on a PR, it must not rely on a bare GitHub review request.

Minimum required handoff:
- add `waiting-on-human` to the PR so lane selectors stop treating it as actively automatable
- preserve the truthful return-path label when one exists (for example `needs-qa`, `needs-security`, `needs-po`, `needs-merge`, or a docs/security gate label)
- if the PR links an open issue, mark that issue `waiting-on-human` too so the backlog state also shows the hold
- leave a structured PR comment that says:
  - why the human is needed
  - exactly what action is requested
  - how the human sends it back to automation
  - the next owner after release

A PR must never be handed to a human with only a review request and no explicit workflow hold/comment.

Use GitHub-native issue relationships (`Blocked by`, parent/sub-issue links) when possible instead of encoding dependencies only in comments.

## What this repo does not define

Casgrain does **not** keep the following automation internals in-repo anymore:

- agent role diagrams
- lane/state-machine diagrams
- cron schedules
- lane prompts
- detailed Hermes workflow implementation notes

Those belong in `agent-team-orchestrator`.
