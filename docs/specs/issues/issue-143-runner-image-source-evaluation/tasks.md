# Issue #143 — Implementation tasks

- Linked issue: `#143`
- Source contract: `./spec.md`

## 1. Confirm the bounded runner-images slice still matches current `main`
- [ ] 1.1 Verify `.github/runner-host-advisory-sources.json` still maps `runner-images` to `#143` and leaves the other four runner-host groups on their current follow-up issues.
- [ ] 1.2 Re-run the current runner-host report on `main` and record whether it still renders the existing `security: runner-host review needed` title plus a `runner-images` group that is still `manual-review-required` before the implementation change.
- [ ] 1.3 Stop and hand the slice back if current `main` already promoted `runner-images` or if another PR changed the source-group split this task list depends on.
- Goal: Prove the selected work is still the `runner-images` promotion slice rather than stale backlog text.
- Validation: `python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No production edits yet, no new issue split, no policy rewrite.
- Hand back if: `runner-images` is no longer owned by `#143`, the runner-host issue title changed, or the remaining host-toolchain groups are no longer the four manual-review-only follow-ups named in `spec.md`.

## 2. Add failing deterministic coverage for runner-images source-backed outcomes
- [ ] 2.1 Extend `tests/scripts/test_runner_host_review_report.py` with source-backed `runner-images` coverage before changing production code.
- [ ] 2.2 Add deterministic fixture payloads under `tests/test-support/fixtures/runner-host-watch/runner-image-source/` for:
  - a clean `runner-images` source-backed match
  - an actionable Android runner-image finding
  - an actionable iOS runner-image finding
  - a source retrieval / parsing / matching failure that must fail closed
- [ ] 2.3 Update `tests/test-support/fixtures/runner-host-watch/source-rules/` so the checked-in manifest expectations prove only `runner-images` was promoted and the other four groups stayed `manual-review-required`.
- [ ] 2.4 Verify the new tests fail on the pre-change implementation before editing production code.
- Goal: Lock the expected clean, actionable, and fail-closed `runner-images` behavior in place before any evaluator logic changes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production report logic changes yet, no workflow YAML edits yet.
- Hand back if: The failing tests show the current summary shape or managed issue title cannot support a `runner-images` promotion without redesigning the whole runner-host lane.

## 3. Promote only the `runner-images` source rule and implement its evaluator
- [ ] 3.1 Update `.github/runner-host-advisory-sources.json` so only `runner-images` is promoted away from `manual-review-required`.
- [ ] 3.2 Keep `runner-images` scoped to the existing watched facts only:
  - Android: `runner.label`, `runner.image_name`, `runner.image_version`, `runner.os_version`
  - iOS: `runner.label`, `runner.image_name`, `runner.image_version`, `runner.os_version`, `runner.os_build`
- [ ] 3.3 Update `tests/test-support/scripts/runner_host_review_report.py` with exactly one `runner-images`-specific source-backed evaluation path.
- [ ] 3.4 Keep the existing drift / missing-evidence platform summary logic authoritative for watched-fact drift and keep the existing managed issue title intact.
- [ ] 3.5 Make source retrieval / parsing / matching failures fail closed into explicit review-needed output rather than a silent clean pass.
- Goal: Land the smallest production change that makes `runner-images` source-backed while leaving the rest of the runner-host watch alone.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No Android Java/Gradle/emulator source work, no iOS Xcode/simulator source work, no generic source-rule framework for every future runner-host group.
- Hand back if: Promoting `runner-images` would require widening `.github/runner-host-watch.json`, adding a second managed issue lane, or inventing cross-group source logic that `spec.md` explicitly excludes.

## 4. Keep the workflow/reporting contract truthful and reconcile docs
- [ ] 4.1 Update the runner-host markdown / summary output so it clearly distinguishes promoted `runner-images` behavior from the still-manual-review-only follow-up groups.
- [ ] 4.2 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that only `runner-images` is source-backed after this slice.
- [ ] 4.3 Touch `.github/workflows/cve-watch.yml` only if a minimal wording or already-available env/input adjustment is required for the promoted evaluator.
- [ ] 4.4 Confirm the implementation still reuses `security: runner-host review needed` rather than inventing another title or sync step.
- Goal: Leave one truthful repo contract on `main` for how runner-images findings are reported and routed after `#143` lands.
- Validation: `python3 - <<'PY'
from pathlib import Path
for rel in [
    'docs/development/cve-watch-operations.md',
    'docs/development/security-automation-plan.md',
    'docs/development/security-owasp-baseline.md',
]:
    text = Path(rel).read_text(encoding='utf-8')
    assert '#143' in text, rel
    assert 'runner-images' in text, rel
print('runner-images docs updated')
PY`
- Non-goals: No repo-wide documentation sweep beyond the runner-host security contract.
- Hand back if: Keeping the docs truthful would require broader policy changes outside the runner-host lane or contradict another already-merged issue-spec on current `main`.

## 5. Run bounded validation and prepare the QA handoff
- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Run Python compile and unit-test coverage for the runner-host report path.
- [ ] 5.3 Re-run the live runner-host report to confirm the summary still carries the same managed issue title and all five source groups, with the four non-`runner-images` groups still `manual-review-required`.
- [ ] 5.4 In the PR handoff comment, state that `#143` promotes only `runner-images`, list the exact validation commands, and call out that `#154`, `#155`, `#156`, and `#144` remain future work.
- Goal: Hand QA a bounded PR with deterministic test evidence and an honest live render smoke, not a speculative framework change.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No manual GitHub issue surgery outside the existing managed runner-host review lane.
- Hand back if: The bounded validation passes locally but the live render smoke cannot preserve the existing `security: runner-host review needed` contract or the PR would no longer honestly `Closes #143`.
