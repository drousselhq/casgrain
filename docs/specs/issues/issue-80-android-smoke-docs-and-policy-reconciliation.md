# Issue #80 — Android smoke docs and policy reconciliation

- Issue: `#80`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #80`
- Downstream dependency that stays blocked until this slice lands: `#79` (`Promote android-smoke to a required merge gate once reliability and evidence are ready`)

## Why this slice exists

Already delivered on `main`:
- PR #104 added the first Android artifact-bundle validator and made partial/missing evidence fail closed.
- PR #117 added stable runner-managed `failure_class` values and tightened the Android smoke evidence contract.
- PR #123 kept empty/malformed `uiautomator` dumps inside the structured `ui-dump-failure` path.
- PR #134 added the repo-owned Android smoke reliability report + issue-sync path.

Live baseline at analyst handoff (2026-04-19 UTC):
- `python3 tests/test-support/scripts/android_smoke_reliability_window.py ...` now reports `verdict=not_qualified`
- current streak counts are `total=26`, `schedule on main=1`, `pull_request=25`
- the only current reason is `schedule_main_runs_below_threshold`
- `.github/workflows/android-emulator-smoke.yml` still applies sync with `--tracker-issue 132`

Current canonical docs are no longer internally consistent with that shipped repo state. In particular, `docs/validation.md` and the older issue specs for `#122` / `#127` still describe Android smoke as having **no** separate tracker / future-run qualification story, while the shipped workflow + sync helper now keep a dedicated tracker issue (`#132`) and may later link a concrete blocker issue from that tracker.

That makes the honest remaining work for `#80` narrower than the original umbrella: this issue should now track one bounded docs/policy reconciliation slice, not broad Android/iOS artifact redesign.

## Scope of this slice

Reconcile the canonical Android smoke docs/policy story with the repo behavior already on `main`.

This slice must:
1. keep iOS documented as the only currently required mobile smoke gate
2. keep Android documented as advisory today, but with a real evidence contract and a repo-owned reliability report/sync path
3. describe the current tracker/blocker ownership story honestly enough that reviewers and agents do not have to rediscover it from workflow YAML or prompt history
4. remove stale spec/doc wording that still says the repo has no dedicated Android reliability tracker

## Required implementation artifacts

### 1. Canonical validation / merge-policy docs

Update these files:
- `docs/validation.md`
- `docs/development/merge-and-validation-policy.md`

Required doc contract:
- explicitly state that `ios-smoke` remains the only required mobile smoke gate today
- explicitly state that `android-emulator-smoke` remains advisory **for merge gating**, but its artifact/evidence contract is mandatory when the workflow runs
- explain that Android reliability qualification is currently tracked through the repo-owned reliability report/sync path, not only by ad hoc human browsing
- explain that the current non-qualified shortfall is a live tracker/report concern and does **not** itself promote Android to a required gate; that later promotion still belongs to `#79`

### 2. Automation runbook doc

Update:
- `docs/development/automation-agent-operations.md`

Required runbook contract:
- name the current tracker issue `#132` as the repo-owned live tracker used by the Android reliability sync on current `main`
- state that threshold-only shortfalls (for example the current `schedule_main_runs_below_threshold` state) keep the tracker open/updateable and do **not** create a blocker issue by themselves
- state that when the synced report later surfaces a concrete blocker beyond threshold shortfall, the automation may create or reuse one bounded blocker issue and link it from the tracker
- keep the wording repo-facing and operational; do **not** import lane-internal orchestration details

### 3. Cross-spec reconciliation

Update these older issue-spec artifacts so they stop contradicting the shipped tracker story:
- `docs/specs/issues/issue-122-android-smoke-reliability-window-report.md`
- `docs/specs/issues/issue-127-android-smoke-reliability-issue-sync.md`

Required reconciliation:
- neither file may continue to claim that the repo has no separate Android reliability tracker if the workflow still targets `#132`
- `#122` must remain the reporter/tooling slice
- `#127` must remain the sync/tooling slice
- the later live qualification outcome must point at tracker issue `#132` unless the implementation PR deliberately changes the workflow/script contract in the same diff (that is **not** expected for this slice)

### 4. Optional supporting doc touch-ups only if needed for truthfulness

A small README or fixture-doc clarification is acceptable **only if** the implementation PR finds one more canonical doc that directly contradicts the updated tracker/evidence story.

Do **not** broaden this into a repo-wide wording sweep. Keep the diff bounded to the canonical Android smoke contract/policy docs named above plus directly contradictory spec entries.

## Acceptance criteria

1. The canonical docs no longer claim that Android smoke has no dedicated reliability tracker while the workflow still syncs against issue `#132`.
2. The canonical docs explain the current split honestly:
   - iOS is the required mobile smoke gate
   - Android is still advisory for merge gating
   - Android nevertheless has a real artifact/evidence contract plus repo-owned reliability reporting/sync
3. The docs explain the current tracker/blocker behavior clearly enough that a reviewer can tell why the present `not_qualified` / `schedule_main_runs_below_threshold` state is still a tracker-only condition.
4. The older issue-spec docs (`#122` and `#127`) no longer contradict the runbook/policy docs about who owns the post-sync live qualification state.
5. The implementation PR for this slice can honestly say `Closes #80` because it finishes the remaining canonical docs/policy reconciliation work tracked here.

## Explicit non-goals

- **no** workflow logic changes in `.github/workflows/android-emulator-smoke.yml`
- **no** new behavior in `tests/test-support/scripts/android_smoke_reliability_window.py`
- **no** new behavior in `tests/test-support/scripts/android_smoke_issue_sync.py`
- **no** Android merge-gate promotion or branch-protection change here (`#79`)
- **no** new Android runner hardening / artifact-surface redesign here
- **no** speculative artifact renames unless a named canonical doc would otherwise remain false

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
git diff --check
python3 - <<'PY'
from pathlib import Path
required = [
    Path('docs/validation.md'),
    Path('docs/development/merge-and-validation-policy.md'),
    Path('docs/development/automation-agent-operations.md'),
    Path('docs/specs/issues/issue-122-android-smoke-reliability-window-report.md'),
    Path('docs/specs/issues/issue-127-android-smoke-reliability-issue-sync.md'),
]
for path in required:
    text = path.read_text(encoding='utf-8')
    print(path)
    assert text.strip(), f'{path} is unexpectedly empty'
workflow_text = Path('.github/workflows/android-emulator-smoke.yml').read_text(encoding='utf-8')
assert '--tracker-issue 132' in workflow_text, 'expected current tracker contract missing from workflow'
print('workflow tracker contract present')
PY
```

The validation above is intentionally docs-focused: this slice should update the canonical wording to match the shipped repo behavior already on `main`, not widen into new runtime/workflow behavior.

## Completion boundary

The implementation PR for this spec should be able to close `#80` because it resolves the remaining canonical docs/policy gap.

After that PR merges:
- issue `#79` becomes the remaining follow-up for any later Android merge-gate promotion
- Android may still remain `not_qualified` for live reliability-window reasons, but that should be represented through the existing report/tracker flow rather than by leaving the canonical docs contradictory
- if a future concrete artifact-surface parity problem appears beyond docs truthfulness, open a new bounded follow-up issue instead of reopening this slice
