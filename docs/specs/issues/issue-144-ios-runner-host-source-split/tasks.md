# Issue #144 task list

- Linked issue: `#144`
- Source contract: `./spec.md`

## Working rules

- Execute tasks in order.
- Keep the diff bounded to the repo-owned iOS source-rule split described in `spec.md`.
- Update checkboxes honestly on the implementation branch as work lands.
- If this task list conflicts with `spec.md` or current `main`, hand the slice back for reshaping instead of improvising.

## 1. Confirm the current split is still needed

- [ ] 1.1 Run the current runner-host report on `main` and capture that `ios-xcode-simulator` is still the only iOS source-rule group mapped to `#144`.
- [ ] 1.2 Confirm follow-up issues `#164` and `#165` are still the intended later implementation slices for Xcode and simulator-runtime source-backed work.

Goal: Prove the repo still needs the contract split described in `spec.md` before changing manifests, tests, or docs.

Validation:
- `python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- `gh issue view 164 --repo drousselhq/casgrain`
- `gh issue view 165 --repo drousselhq/casgrain`

Non-goals:
- No manifest edits yet.
- No source-backed Apple advisory implementation yet.

Hand back if:
- Current `main` already uses split iOS source-rule groups.
- `#164` or `#165` no longer represents the later iOS Xcode/simulator-runtime work.

## 2. Split the checked-in iOS source-rule inventory

- [ ] 2.1 Update `.github/runner-host-advisory-sources.json` to replace `ios-xcode-simulator` with `ios-xcode` and `ios-simulator-runtime`.
- [ ] 2.2 Keep `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` unchanged while ensuring every watched iOS fact remains owned exactly once.

Goal: Make the checked-in source-rule manifest declare two bounded iOS promotion backlogs instead of one umbrella group.

Validation:
- `python3 -m unittest tests/scripts/test_runner_host_review_report.py`

Non-goals:
- No live Apple-source queries.
- No changes to `.github/runner-host-watch.json`.
- No change to the managed issue title.

Hand back if:
- The watched iOS fact inventory on current `main` no longer matches `spec.md`.
- One watched iOS fact cannot be assigned honestly to exactly one of the two new groups.

## 3. Update runner-host report logic and fail-closed coverage

- [ ] 3.1 Update `tests/test-support/scripts/runner_host_review_report.py` so the expected group keys, follow-up issue mapping, and markdown/JSON rendering use `ios-xcode` and `ios-simulator-runtime`.
- [ ] 3.2 Extend `tests/scripts/test_runner_host_review_report.py` and any fixture cases under `tests/test-support/fixtures/runner-host-watch/source-rules/` to cover missing or duplicate iOS ownership and wrong follow-up issue numbers.
- [ ] 3.3 Keep the checked-in `.github/runner-host-advisory-sources.json` manifest covered directly, not only synthetic fixture copies.

Goal: Make the report and tests fail closed around the new split iOS contract.

Validation:
- `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`
- `python3 -m unittest tests/scripts/test_runner_host_review_report.py`

Non-goals:
- No change to the top-level drift verdict/reason semantics.
- No new runner-host managed issue behavior.

Hand back if:
- The only way to make the slice pass is to weaken fail-closed ownership checks.
- The implementation would need to invent new alert semantics not frozen in `spec.md`.

## 4. Reconcile canonical docs and older issue-spec references

- [ ] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they stop treating `#144` as the remaining umbrella iOS promotion issue and instead name `#164` and `#165`.
- [ ] 4.2 Update `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md` and `docs/specs/issues/issue-124-runner-host-drift-watch.md` so older repo-owned specs do not preserve the superseded `ios-xcode-simulator` umbrella story after this slice lands.

Goal: Keep canonical docs and older issue-spec artifacts aligned with the new iOS split.

Validation:
- `git grep -n 'ios-xcode-simulator\|#144' docs/development docs/specs/issues`

Non-goals:
- No unrelated docs cleanup outside the five named files.
- No rewrite of the underlying security policy beyond the split ownership story.

Hand back if:
- Another canonical doc or older live issue-spec still owns the old `#144` umbrella contract and this slice would otherwise leave contradictory repo guidance.

## 5. Run scoped validation and prepare the implementation PR handoff

- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.3 Run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.4 Render `tests/test-support/scripts/runner_host_review_report.py` against current `main` and assert the summary still reports `verdict=no review-needed`, `reason=baseline-match`, and source-rule keys `ios-xcode` / `ios-simulator-runtime` mapped to `#164` / `#165`.
- [ ] 5.5 Prepare the implementation PR summary with exact validation evidence and honest closure semantics: `Closes #144` for the split contract, while `#164` and `#165` stay open for the later source-backed implementations.

Goal: Prove the split lands without changing current drift behavior and hand QA a bounded, verifiable slice.

Validation:
- `git diff --check`
- `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`
- `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- `python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- `python3 - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('/tmp/runner-host-watch-summary.json').read_text(encoding='utf-8'))
assert summary['verdict'] == 'no review-needed', summary
assert summary['reason'] == 'baseline-match', summary
issue_map = {group['key']: group['follow_up_issue'] for group in summary['source_rule_groups']}
assert issue_map['ios-xcode'] == 164, issue_map
assert issue_map['ios-simulator-runtime'] == 165, issue_map
print('runner-host iOS source split summary present')
PY`

Non-goals:
- No extra CI/workflow changes.
- No live Apple-source integration.
- No closure of `#164` or `#165`.

Hand back if:
- Current `main` no longer produces a clean runner-host baseline render.
- The split changes the top-level drift verdict or reason without an explicit `spec.md` update.
