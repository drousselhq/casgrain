# Automation Agent Operations

## Goal

Casgrain is intentionally agent-native for repository maintenance, but agent autonomy should stay explicit and bounded.

This document defines the repo-operations responsibilities that can be delegated to automation without changing Casgrain's product behavior.

## Scope

These roles apply to repository maintenance work such as:
- issue triage
- bug reproduction and evidence gathering
- CI failure diagnosis
- flaky-test ownership
- backlog hygiene and docs reconciliation

They do not redefine Casgrain's runtime architecture or put LLMs in the deterministic execution path.

## Shared operating rules

All automation agents operating in this repository should:
- treat GitHub Issues as the backlog source of truth
- inspect open issues, PRs, recent activity, and branch state before starting work
- work one bounded slice at a time
- prefer cheap evidence before expensive exploration
- keep diffs small and focused
- open PRs rather than pushing directly to `main`
- stop when a proposed change would alter product behavior, developer experience, or architecture in a meaningful way
- record discovered follow-up work in GitHub Issues instead of leaving it implicit in chat logs or PR comments

## Human and agent boundaries

Humans remain responsible for:
- product-direction decisions
- architectural tradeoffs
- meaningful developer-experience changes
- approving high-risk changes
- repository settings changes that cannot be expressed safely in-repo

Agents may act autonomously on:
- maintenance-oriented docs reconciliation
- issue clarification and triage comments
- validation and CI hardening that does not change expected product behavior
- small regression tests for already-decided behavior
- bug reproduction and evidence capture
- PR preparation for bounded low-risk slices

Agents must escalate instead of proceeding when:
- requirements are ambiguous
- multiple reasonable next steps would change project direction
- the safest next move depends on human prioritization
- a change crosses a product, DX, or architecture boundary
- the evidence is too weak to justify a code or policy change

## Role definitions

### 1. Backlog hygiene agent

Purpose:
- keep issues, plans, and docs aligned
- prevent stale maintenance work from quietly drifting

Typical triggers:
- scheduled maintenance runs
- newly opened issues
- merged PRs that leave follow-up work behind
- docs that reference already-completed or missing backlog items

Expected outputs:
- issue triage comments
- labels, assignments, or closures when evidence is clear
- small docs reconciliations opened as PRs
- follow-up issues for newly discovered maintenance gaps

Must not:
- invent roadmap work that is not grounded in existing issues or repo evidence
- close active work that still has unresolved product decisions

#### Backlog hygiene protocol

Before choosing work, the backlog hygiene agent should gather cheap evidence in this order:
1. inspect local branch state and the active repo operating docs (`AGENTS.md`, `docs/plans/current-plan.md`, and `docs/validation.md`)
2. inspect open GitHub Issues, open PRs, recent merged PRs, and recent `main` history
3. inspect the candidate issue body, comments, labels, and nearby files before editing anything

The non-interference screen is mandatory. Do not start a coding slice when:
- an open PR already covers the issue or same file area
- a branch name, recent comment, or fresh commit shows someone is actively working the same change
- the change would overlap very recent product-path work and is not purely reconciliatory
- the safest next step depends on a human product or DX decision

After inspection, choose exactly one outcome for the run:
1. **Coding slice** when the issue is clearly bounded, maintenance-oriented, and safe to complete in one PR
2. **Triage-only update** when the right next step is clarification, labeling, assignment, or a comment with findings and a concrete proposal
3. **No-op** when interference risk, insufficient evidence, or settings-side blockers make even a small in-repo change unsafe

When a coding slice is safe, keep it narrow:
- change only the files needed for the selected issue
- prefer docs reconciliation, validation hardening, or small regression coverage over broader refactors
- convert any newly discovered adjacent work into follow-up GitHub Issues instead of expanding the PR

When triaging issues, the backlog hygiene agent may:
- add or remove labels when the classification is evidence-backed
- close issues only when the work is already landed, duplicated, or explicitly not planned
- leave a comment summarizing what was checked, why the chosen action is safe, and what should happen next

Every maintenance-loop completion report should include:
- which issue was selected and why it was safe
- whether the result was a coding slice, triage-only update, or no-op
- what evidence or repo state was inspected
- what validation ran, if any
- any PR or follow-up issue links
- any explicit blocker that prevented further safe progress

Escalate instead of proceeding when:
- the issue would change product behavior or developer experience in a meaningful way
- multiple reasonable issue choices exist but require human prioritization
- the repo needs settings-side enforcement rather than an in-repo change
- the evidence is too weak to justify labels, closure, or code edits

### 2. Reproduction agent

Purpose:
- turn bug reports or suspicious failures into deterministic evidence

Typical triggers:
- issues with incomplete reproduction detail
- CI failures that are not obviously infrastructure-only
- reports of runtime regressions, trace gaps, or fixture inconsistencies

Expected outputs:
- minimal reproduction steps
- captured commands, traces, logs, screenshots, or artifacts
- issue comments clarifying whether the problem is deterministic, flaky, or environment-specific
- narrowly scoped regression tests or fixture updates when the fix is already well understood and low risk

Must not:
- guess at root cause without captured evidence
- broaden a bug report into speculative product redesign

### 3. CI shepherd agent

Purpose:
- keep the validation gate trustworthy and understandable

Typical triggers:
- failed GitHub Actions runs
- missing or drifting validation docs
- workflow/tooling regressions that weaken the merge gate

Expected outputs:
- failure diagnosis with concrete run/job evidence
- small CI or docs hardening PRs
- follow-up issues for settings-side or plan-limited blockers
- issue or PR comments explaining what is blocked in-repo versus out-of-repo

Must not:
- merge around failing or still-running required checks
- weaken validation merely to make CI green

### 4. Flaky-test owner agent

Purpose:
- identify, isolate, and reduce nondeterminism in validation

Typical triggers:
- intermittently failing tests or workflows
- reports that a failure cannot be reproduced consistently
- simulator/emulator instability that blurs product failures and infrastructure failures

Expected outputs:
- evidence describing the flake signature
- issue updates that separate deterministic bugs from nondeterministic infrastructure noise
- hardening PRs that improve selection, waiting, retries, observability, or fixture isolation
- explicit follow-up issues when a flake cannot be safely fixed in one slice

Must not:
- hide real failures behind broad retries
- mute tests without replacing lost signal intentionally and explicitly

## Coordination model

When multiple roles could respond to the same situation, prefer this order:
1. backlog hygiene agent confirms the work is safe and not already in progress
2. reproduction agent gathers evidence if the failure or bug is unclear
3. CI shepherd agent tightens validation or workflow behavior when the failure is in the merge gate
4. flaky-test owner agent handles confirmed nondeterminism separately from deterministic defects

This ordering keeps repo maintenance grounded in evidence rather than jumping directly to fixes.

## Tracked follow-up work

The definitions in this document are governance only. Remaining concrete automation rollout should be tracked as follow-up GitHub Issues rather than assumed to exist implicitly.

- issue #43 — define a deterministic bug reproduction evidence contract
- issue #44 — define CI shepherd and flaky-ownership operating procedures

## Relationship to other repo documents

- `AGENTS.md` defines the high-level operating contract for repo work
- `docs/validation.md` defines the canonical validation gate
- `docs/development/merge-and-validation-policy.md` defines merge classes and merge discipline
- `docs/plans/current-plan.md` remains the live project direction document
