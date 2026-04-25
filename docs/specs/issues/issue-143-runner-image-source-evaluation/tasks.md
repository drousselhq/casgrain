# Issue #143 — Implementation tasks

- Linked issue: `#143`
- Source contract: `./spec.md`

## 1. Confirm the bounded runner-images slice still matches current `main`
- [x] 1.1 Verify `.github/runner-host-advisory-sources.json` still maps `runner-images` to `#143` and leaves the other four runner-host groups on their current follow-up issues.
- [x] 1.2 Re-run the current runner-host report on `main` and record whether it still renders the existing `security: runner-host review needed` title plus a `runner-images` group that is still `manual-review-required` before the implementation change.
- [x] 1.3 Stop and hand the slice back if current `main` already promoted `runner-images` or if another PR changed the source-group split this task list depends on.
- Goal: Prove the selected work is still the `runner-images` promotion slice rather than stale backlog text.
- Validation: `python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No production edits yet, no new issue split, no policy rewrite.
- Hand back if: `runner-images` is no longer owned by `#143`, the runner-host issue title changed, or the remaining host-toolchain groups are no longer the four manual-review-only follow-ups named in `spec.md`.

## 2. Add failing deterministic coverage for runner-images source-backed outcomes
- [x] 2.1 Extend `tests/scripts/test_runner_host_review_report.py` with source-backed `runner-images` coverage before changing production code.
- [x] 2.2 Add deterministic fixture payloads under `tests/test-support/fixtures/runner-host-watch/runner-image-source/` for:
  - a clean `runner-images` source-backed match
  - an actionable Android runner-image finding
  - an actionable iOS runner-image finding
  - a source retrieval / parsing / normalization / matching failure that must fail closed
- [x] 2.3 Add or update manifest fixtures so the promoted `runner-images` entry must use the exact literal `rule_kind=runner-image-release-metadata`, the exact `source_streams` selectors, and the exact source-compared fact boundaries from `spec.md`.
- [x] 2.4 Make the tests assert the exact promoted-rule strings before production edits:
  - top-level `reason` values `runner-images-source-drift` and `runner-images-source-error`
  - group-level `status` values `no review-needed` / `manual-review-required`
  - group-level `outcome` values `source-match` / `source-drift` / `source-error`
- [x] 2.5 Verify the new tests fail on the pre-change implementation before editing production code.
- Goal: Lock the expected clean, actionable, and fail-closed `runner-images` behavior in place before any evaluator logic changes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production report logic changes yet, no workflow YAML edits yet.
- Hand back if: The failing tests show the current summary shape or managed issue title cannot support the exact promoted-rule fields from `spec.md` without redesigning the whole runner-host lane.

## 3. Promote only the `runner-images` source rule and implement its evaluator
- [x] 3.1 Update `.github/runner-host-advisory-sources.json` so only `runner-images` is promoted from `manual-review-required` to `runner-image-release-metadata`.
- [x] 3.2 Add the exact `source_streams` contract from `spec.md` and keep `runner.label` plus `runner.image_name` limited to selector / drift-context use in this slice.
- [x] 3.3 Keep source-backed comparisons scoped to the exact normalized fields from `spec.md` only:
  - Android: `runner.image_version`, `runner.os_version`
  - iOS: `runner.image_version`, `runner.os_version`, `runner.os_build`
- [x] 3.4 Update `tests/test-support/scripts/runner_host_review_report.py` so the `runner-images` group emits the exact promoted-rule fields `status`, `outcome`, and `platform_results` while the four non-promoted groups remain manifest-only follow-up entries.
- [x] 3.5 Make source retrieval / parsing / normalization / matching failures fail closed into `reason=runner-images-source-error` rather than a silent clean pass.
- Goal: Land the smallest production change that makes `runner-images` source-backed while leaving the rest of the runner-host watch alone.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No Android Java/Gradle/emulator source work, no iOS Xcode/simulator source work, no generic source-rule framework for every future runner-host group.
- Hand back if: Promoting `runner-images` would require widening `.github/runner-host-watch.json`, adding a second managed issue lane, or inventing promoted-rule fields or reason strings beyond the exact contract frozen in `spec.md`.

## 4. Keep the workflow/reporting contract truthful and reconcile docs
- [x] 4.1 Update the runner-host markdown / summary output so it clearly distinguishes the existing drift / missing-evidence path from the promoted runner-images source-backed `source-match`, `source-drift`, and `source-error` outcomes.
- [x] 4.2 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, `docs/development/security-owasp-baseline.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, `docs/specs/issues/issue-124-runner-host-drift-watch.md`, and `docs/specs/issues/issue-142-android-runner-host-source-split.md` so this historical artifact stays truthful now that `runner-images` and `android-gradle` are source-backed after the later `#155` slice.
- [x] 4.3 In the three older issue-spec docs, remove the stale future-work wording that still presents `#143` as an open follow-up or keeps the whole runner-host lane drift-triggered, and reconcile them so `#143` and the later Android Gradle slice `#155` are documented as already delivered while only `#154`, `#156`, and `#144` remain future work.
- [x] 4.4 Touch `.github/workflows/cve-watch.yml` only if a minimal wording or already-available env/input adjustment is required for the promoted evaluator.
- [x] 4.5 Confirm the implementation still reuses `security: runner-host review needed` rather than inventing another title or sync step.
- Goal: Leave one truthful repo contract on `main` for how runner-images findings are reported and routed after `#143` lands.
- Validation: `python3 - <<'PY'
from pathlib import Path
for rel in [
    'docs/development/cve-watch-operations.md',
    'docs/development/security-automation-plan.md',
    'docs/development/security-owasp-baseline.md',
    'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md',
    'docs/specs/issues/issue-124-runner-host-drift-watch.md',
    'docs/specs/issues/issue-142-android-runner-host-source-split.md',
]:
    text = Path(rel).read_text(encoding='utf-8')
    assert '#143' in text, rel
    assert 'runner-images' in text, rel
print('runner-images docs updated')
PY`
- Non-goals: No repo-wide documentation sweep beyond the runner-host security contract.
- Hand back if: Keeping the docs truthful would require broader policy changes outside the runner-host lane or contradict another already-merged issue-spec on current `main`.

## 5. Run bounded validation and prepare the QA handoff
- [x] 5.1 Run `git diff --check`.
- [x] 5.2 Run Python compile and unit-test coverage for the runner-host report path.
- [x] 5.3 Re-run the live runner-host report and assert that the summary still carries the same managed issue title, all five source groups, the exact promoted runner-images fields, and the remaining `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` follow-up groups still `manual-review-required`.
- [x] 5.4 In the PR handoff comment, state that `#143` promotes only `runner-images`, list the exact validation commands, note that docs still need review because the spec/reporting contract changed, and call out that `#154`, `#156`, and `#144` remain future work while `#155` is now delivered as the Android Gradle source-backed slice.
- [x] 5.5 Add a regression that exercises the live runner-image release-discovery path and proves the report selects the latest stream release instead of the observed runner-image tag.
- Goal: Hand QA a bounded PR with deterministic test evidence and an honest live render smoke, not a speculative framework change.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No manual GitHub issue surgery outside the existing managed runner-host review lane.
- Hand back if: The bounded validation passes locally but the live render smoke cannot preserve the existing `security: runner-host review needed` contract or the PR would no longer honestly `Closes #143`.
