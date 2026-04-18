# Automation and `agent-team-orchestrator` integration

Casgrain uses the external `agent-team-orchestrator` repository for Hermes lane prompts, cron topology, workflow-state transitions, and other automation internals.

This repository intentionally keeps only the minimum local contract needed for contributors and automation to work against the product honestly.

## Local source-of-truth split

- GitHub Issues and the Casgrain GitHub Project v2 board are the backlog and prioritization source of truth.
- `docs/specs/casgrain-product-spec.md` is the canonical behavior/spec source of truth.
- `docs/validation.md` is the canonical validation gate.
- `docs/development/merge-and-validation-policy.md` defines local merge discipline.

## Workflow-state labels used in this repo

These labels are still the durable execution-state surface consumed by automation:

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

Use GitHub-native issue relationships (`Blocked by`, parent/sub-issue links) when possible instead of encoding dependencies only in comments.

## What this repo does not define

Casgrain does **not** keep the following automation internals in-repo anymore:

- agent role diagrams
- lane/state-machine diagrams
- cron schedules
- lane prompts
- detailed Hermes workflow implementation notes

Those belong in `agent-team-orchestrator`.
