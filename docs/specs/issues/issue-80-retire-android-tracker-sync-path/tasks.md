# Issue #80 — Implementation tasks

## 1. Add failing regression coverage for the retired tracker contract
- [x] 1.1 Update the existing issue-sync fixtures/tests so the current `schedule-shortfall` case asserts the stale tracker transition is wrong on current `main`.
- [x] 1.2 Add at least one regression that starts from an already-managed blocker issue and proves the old tracker-centric plan would leave stale issue state behind.
- [x] 1.3 Verify the new/updated tests fail on the pre-change implementation before changing production behavior.
- Goal: Prove the tracker-retirement gap with deterministic tests before editing the workflow or sync helper.
- Validation: `python3 -m unittest tests/scripts/test_android_smoke_issue_sync.py`
- Non-goals: No production workflow/script edits yet.
- Hand back if: Current `main` already produces tracker-free dry-run output for the `schedule-shortfall` fixture and no stale blocker lifecycle gap remains.

## 2. Retire the dedicated tracker path from the sync helper
- [x] 2.1 Remove the required live-tracker assumption from `android_smoke_issue_sync.py` and its dry-run output.
- [x] 2.2 Keep one managed-blocker path for concrete non-threshold blockers, including create/reopen/update behavior per blocker class.
- [x] 2.3 Close a previously managed blocker issue when a later report no longer justifies keeping it open.
- Goal: Make the GitHub-state layer match the repo’s current advisory-with-bounded-blocker contract.
- Validation: `python3 -m unittest tests/scripts/test_android_smoke_issue_sync.py`
- Non-goals: No threshold math changes, no new tracker issue, no branch-protection work.
- Hand back if: Removing the tracker contract would require redesigning the reliability reporter itself rather than the sync layer.

## 3. Remove the hardcoded tracker input from workflow integration
- [x] 3.1 Update `.github/workflows/android-emulator-smoke.yml` so the sync step no longer passes `--tracker-issue 132`.
- [x] 3.2 Keep the same event boundary for issue mutation and preserve the current human-readable report output.
- [x] 3.3 Confirm the workflow text no longer depends on any dedicated live tracker issue for Android reliability state.
- Goal: Stop current `main` from carrying a stale tracker contract in workflow configuration.
- Validation: `python3 - <<'PY'
from pathlib import Path
workflow_text = Path('.github/workflows/android-emulator-smoke.yml').read_text(encoding='utf-8')
assert '--tracker-issue 132' not in workflow_text
print('tracker issue argument removed from workflow')
PY`
- Non-goals: No broader workflow refactor, no change to when PRs vs repository-owned events run the smoke lane.
- Hand back if: Another workflow or script outside this slice still hardcodes tracker issue `#132` and would need a broader multi-lane redesign.

## 4. Reconcile only the remaining repo-owned contract artifacts
- [x] 4.1 Update any repo-owned docs/spec files that still describe tracker issue `#132` as part of the live Android contract after the code/workflow change.
- [x] 4.2 Reconcile `docs/specs/issues/issue-127-android-smoke-reliability-issue-sync.md` so its `schedule-shortfall` / `qualified` expectations no longer preserve tracker-managed issue `#132` behavior.
- [x] 4.3 Make the legacy issue-80 artifact a pointer or otherwise non-contradictory if it remains in the tree.
- [x] 4.4 Run a targeted search for stale tracker wording before handoff.
- Goal: Leave one truthful contract on `main` instead of a tracker-era and post-tracker-era story living side by side.
- Validation: `python3 - <<'PY'
from pathlib import Path
root = Path('.')
needle = '#132'
for path in sorted(root.glob('docs/**/*.md')):
    text = path.read_text(encoding='utf-8')
    if needle in text and 'issue-80-retire-android-tracker-sync-path' not in str(path):
        print(path)
PY`
- Non-goals: No repo-wide wording sweep beyond directly contradictory tracker references.
- Hand back if: Canonical docs outside the Android smoke contract would need a broader policy rewrite to stay truthful.

## 5. Run bounded live-state validation and hand back to QA
- [x] 5.1 Run `git diff --check`.
- [x] 5.2 Re-run the local issue-sync unit tests.
- [x] 5.3 Rebuild the live Android reliability summary and confirm the dry-run stays advisory-only for the current `schedule_main_runs_below_threshold` state.
- [x] 5.4 In the PR handoff comment, state that `#80` is now the tracker-retirement cleanup slice and whether any doc files remained in scope.
- Goal: Prove the refreshed head matches current live repo state before QA reviews it.
- Validation: `git diff --check && python3 -m unittest tests/scripts/test_android_smoke_issue_sync.py && python3 tests/test-support/scripts/android_smoke_reliability_window.py --repo drousselhq/casgrain --workflow android-emulator-smoke.yml --artifact-name casgrain-android-smoke --summary-out /tmp/android-smoke-reliability-window.json --markdown-out /tmp/android-smoke-reliability-window.md && python3 tests/test-support/scripts/android_smoke_issue_sync.py --repo drousselhq/casgrain --summary-json /tmp/android-smoke-reliability-window.json --markdown-file /tmp/android-smoke-reliability-window.md --dry-run`
- Non-goals: No manual GitHub issue editing beyond the bounded automation behavior under test.
- Hand back if: The live dry-run still wants tracker mutation after the local code changes, or the refreshed contract would no longer honestly `Closes #80`.
