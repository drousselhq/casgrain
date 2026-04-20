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
- PR body records the validation that actually ran and whether any documented exception was used

Default action:
- agent may self-merge when green
- agent must not treat a visible GitHub merge button as proof that the merge gate is satisfied

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

See `docs/validation.md` for the canonical validation gate and reporting expectations.

See also:
- `docs/development/security-automation-plan.md` for the current security baseline and staged follow-up checks.
- the Casgrain GitHub Project v2 board for current prioritization.

## E2E policy

Casgrain should not wait for full real-device infrastructure before making progress.

Validation levels:
1. unit + fake-engine + compiler golden tests
2. fixture-app simulator/emulator smoke tests
3. richer cross-platform end-to-end validation

Until level 2 exists, many PRs can still merge using level 1.
Once level 2 exists, runtime-affecting PRs should increasingly rely on it.

Current rollout policy:
- iOS smoke is now required on PRs because the current product-true slice is iOS-first.
- The required iOS check may self-skip for docs-only / governance-only PRs, but it must always report a status so branch protection remains enforceable.
- Android smoke runs automatically for Android/shared-runtime changes, qualifying pushes to `main`, and on a nightly schedule, but remains advisory until its stability is strong enough for required-check promotion.
- Even while Android smoke is advisory, its workflow artifacts should be treated as a real contract: the run must archive either the success bundle (`trace.json`, plan, screenshot, emulator metadata, UI dumps) or a runner-managed failure bundle with `failure.json`, `evidence-summary.json`, and a stable `failure_class`, plus any diagnostics that truthfully exist for that class. Boot-readiness failures may legitimately have no foreground/UI diagnostics; later foreground, `ui-dump-failure`, selector, and text failures should preserve the referenced diagnostics when available, and `ui-dump-failure` should always preserve `ui-last.xml` (empty when the dump itself yielded no bytes) plus the latest truthful foreground snapshot when available. Missing both bundles should be treated as an explicit `artifact-contract-breach`.
- The repo-owned Android smoke reliability report/sync path keeps qualification state in issue `#132` on current `main`; a `schedule_main_runs_below_threshold` shortfall stays tracker-only and does not itself promote Android to a required gate.
- Shared runtime/compiler/CLI changes should trigger both platform smoke workflows; platform-specific fixture/harness changes should trigger only the affected platform plus the normal Linux gate.
- Docs/governance-only changes can rely on the default Linux validation gate without paying for mobile smoke execution.

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

When releasing work into automation, use the Casgrain GitHub Project v2 board for prioritization and the workflow-state labels documented in `docs/development/automation-agent-operations.md` for durable execution state.
In particular:
- `ready-for-dev` means released into execution
- `devops` routes repo-infrastructure work to the DevOps lane instead of the general Dev Delivery lane
- `blocked` and `waiting-on-human` should be explicit when execution is not currently safe
