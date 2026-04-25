# Issue #80 — Retire stale Android tracker sync path and align the Android smoke contract

- Issue: `#80`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #80`
- Historical downstream dependency at shaping time: `#79` (`Promote android-smoke to a required merge gate on main`)
- Supersedes the legacy one-file issue artifact previously stored at `docs/specs/issues/issue-80-android-smoke-docs-and-policy-reconciliation.md`
- Historical note: this closed issue artifact records the tracker-retirement slice before the later merge-gate reconciliation work tracked in issues `#79` and `#135`. Read current-state merge-gate ownership from the canonical docs plus the issue-79 and issue-135 artifacts, not from this closed issue alone.

## Why this slice exists

Already delivered on `main`:
- PR #104 added the first Android artifact-bundle validator and removed misleading partial-evidence paths.
- PR #117 added stable Android smoke `failure_class` values and tightened the evidence contract.
- PR #123 kept empty/malformed `uiautomator` dumps inside the structured `ui-dump-failure` path.
- PR #134 added the repo-owned Android smoke reliability report plus issue-sync flow.
- PR #152 stopped `android_smoke_issue_sync.py` from reopening retired tracker issue `#132` once that tracker was intentionally closed.
- at the time `#80` was shaped, `docs/validation.md`, `docs/development/merge-and-validation-policy.md`, `docs/development/automation-agent-operations.md`, and the earlier issue specs for `#122` / `#127` described Android smoke as advisory on `main` and did **not** require a separate live qualification tracker issue.

Live baseline at analyst handoff (`2026-04-21` UTC):
- `python3 tests/test-support/scripts/android_smoke_reliability_window.py ...` still reports `verdict=not_qualified`
- current streak counts are `successful_run_count=42`, `schedule_main_success_count=2`, `pull_request_success_count=36`
- the only current reason is `schedule_main_runs_below_threshold`
- the historical blocker context is still run `24611423606` with `failure_class=artifact-contract-breach`
- `.github/workflows/android-emulator-smoke.yml` still passes `--tracker-issue 132`
- a fresh dry-run of `android_smoke_issue_sync.py` on current `main` reports `report_kind=schedule_shortfall_only`, `blocker.action=noop`, and tracker `#132` with `current_state=CLOSED` plus `desired_state=OPEN`

That means the honest remaining gap is no longer a broad docs rewrite. The repo-owned apply path still encodes a retired dedicated-tracker contract even though the canonical docs/spec direction has already moved away from any separate live Android qualification tracker.

## Scope of this slice

Retire the stale Android tracker-sync path so the then-current `main` matched the no-separate-tracker Android advisory contract.

This slice must:
1. remove the hardcoded live tracker dependency from the Android reliability sync path
2. keep the one-bounded-blocker issue path for concrete non-threshold blockers
3. keep threshold-only shortfalls advisory rather than turning them into tracker churn
4. reconcile any remaining repo-owned spec/doc references that still describe tracker issue `#132` as part of the current contract

## Required implementation artifacts

### 1. Android reliability sync helper

Update:
- `tests/test-support/scripts/android_smoke_issue_sync.py`

Implementation contract:
- retire the mandatory dedicated-tracker issue contract for this automation path
- remove the assumption that every non-qualified or qualified report must transition a live tracker issue
- keep the blocker-planning logic for concrete non-threshold blockers (for example `artifact-contract-breach`) so the automation can still create, reopen, update, and close **one** managed blocker issue per blocker class
- when the report is threshold-shortfall-only (`schedule_main_runs_below_threshold` or another pure threshold shortfall), the sync plan must be a no-op on GitHub issue state unless it needs to close a previously managed blocker issue that is no longer active
- when the report is `qualified`, the sync plan must not require any tracker mutation; it should leave GitHub issue state quiet unless it needs to close a previously managed blocker issue that this report no longer justifies
- the dry-run output must stop advertising a tracker transition for the current live state

### 2. Android smoke workflow integration

Update:
- `.github/workflows/android-emulator-smoke.yml`

Workflow contract:
- stop passing a hardcoded tracker issue (`#132`) into the sync path
- keep the current report generation and issue-sync invocation intact apart from the tracker retirement
- preserve the existing event boundary: repo-owned issue mutation happens only on repository-owned events, never on ordinary PR validation runs
- keep the rendered reliability markdown / summary visible to humans in the workflow output

### 3. Deterministic tests and fixtures

Update:
- `tests/scripts/test_android_smoke_issue_sync.py`
- `tests/test-support/fixtures/android-smoke/reliability-issue-sync/`

Required regression coverage:
- the current `schedule-shortfall` fixture must prove the new plan is tracker-free and blocker-free
- a `qualified` fixture must prove the new plan is tracker-free and closes any matching managed blocker issue if one exists
- a `blocker` fixture must prove the new plan still creates/reopens/updates exactly one managed blocker issue for the surfaced blocker class
- add at least one regression that starts from a previously managed blocker issue and proves the issue closes when the report later downgrades to threshold-shortfall-only or qualified
- update dry-run assertions so they describe blocker/no-op behavior rather than tracker transitions

### 4. Repo-owned spec/doc reconciliation only where still necessary

Update only the repo-owned files that still contradict the tracker-retirement contract after the code/workflow change.

Minimum required reconciliation:
- the legacy issue-80 artifact must not remain a stale competing contract on `main`
- `docs/specs/issues/issue-127-android-smoke-reliability-issue-sync.md` must be reconciled because it still describes the `schedule-shortfall` and `qualified` paths as tracker-managed state transitions for issue `#132`
- no repo-owned doc/spec on `main` may still tell implementers that Android reliability currently depends on live tracker issue `#132`

Do **not** broaden this into another repo-wide Android docs sweep. The canonical validation / merge-policy docs are already mostly on the correct side of the contract and should change only if the implementation reveals one remaining false claim.

## Acceptance criteria

1. `.github/workflows/android-emulator-smoke.yml` no longer depends on `--tracker-issue 132` or another dedicated live tracker issue for the Android reliability sync path.
2. `android_smoke_issue_sync.py --dry-run` on the current live summary no longer plans any tracker mutation when the only reason is `schedule_main_runs_below_threshold`.
3. The managed blocker path still works for concrete non-threshold blockers and does not create duplicate blocker issues for the same blocker class.
4. A previously managed blocker issue is closed when a later report no longer justifies keeping it open.
5. Repo-owned docs/spec artifacts on `main` no longer depended on a live tracker issue `#132` as part of the then-current Android advisory contract.
6. The implementation PR for this slice can honestly say `Closes #80`; at the time this spec landed, `#79` still tracked the later Android merge-gate promotion, but current `main` has since completed that follow-up.

## Explicit non-goals

- **no** Android merge-gate promotion or branch-protection change here (`#79`)
- **no** threshold or reliability-window math changes
- **no** reopening `#132` or inventing a replacement future-run tracker issue
- **no** broader Android artifact-contract redesign
- **no** repo-wide docs rewrite beyond directly contradictory tracker references

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
git diff --check
python3 -m py_compile \
  tests/test-support/scripts/android_smoke_issue_sync.py \
  tests/scripts/test_android_smoke_issue_sync.py
python3 -m unittest tests/scripts/test_android_smoke_issue_sync.py
python3 tests/test-support/scripts/android_smoke_reliability_window.py \
  --repo drousselhq/casgrain \
  --workflow android-emulator-smoke.yml \
  --artifact-name casgrain-android-smoke \
  --summary-out /tmp/android-smoke-reliability-window.json \
  --markdown-out /tmp/android-smoke-reliability-window.md
python3 tests/test-support/scripts/android_smoke_issue_sync.py \
  --repo drousselhq/casgrain \
  --summary-json /tmp/android-smoke-reliability-window.json \
  --markdown-file /tmp/android-smoke-reliability-window.md \
  --dry-run
python3 - <<'PY'
from pathlib import Path
workflow_text = Path('.github/workflows/android-emulator-smoke.yml').read_text(encoding='utf-8')
assert '--tracker-issue 132' not in workflow_text
print('tracker issue argument removed from workflow')
PY
```

The live dry-run should stay advisory-only for the current shortfall state; it must not propose reopening or updating a tracker issue.

## Completion boundary

The implementation PR for this spec should be able to close `#80` because it removes the last stale tracker/apply-path contradiction on current `main`.

After that PR merges:
- Android smoke may still remain `not_qualified` for live reliability-window reasons, but that state should live in the report output and any bounded blocker issue rather than in a dedicated tracker issue
- at the time this slice landed, `#79` still tracked the later Android merge-gate promotion; current `main` has since completed that follow-up, so this closed spec no longer defines a live downstream owner
- if future work needs richer advisory reporting beyond blocker-only GitHub state, open a new bounded follow-up issue instead of reopening this slice
