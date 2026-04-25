# Issue #165 — Evaluate source-backed advisory automation for iOS simulator runtime-catalog facts

- Issue: `#165`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #165`
- Upstream slice already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
- Repo-owned prerequisite already merged on `main` as analyst contract:
  - `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`
- Related follow-up issues that must remain separate from this slice:
  - `#143` (`runner-images`)
  - `#154` (`android-java`)
  - `#155` (`android-gradle`)
  - `#156` (`android-emulator-runtime`)
  - `#164` (`ios-xcode`)
  - `#172` (`ios simulator device-availability facts`)

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #166 merged the analyst contract for `#144`, which froze the later iOS source-backed work into separate follow-up issues instead of one umbrella iOS slice.
- A fresh live invocation at analyst handoff (`2026-04-22` UTC) against current `main` still reports:
  - `verdict=no review-needed`
  - `reason=baseline-match`
  - `advisory_count=0`
  - source-rule groups `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator`
  - `runner-images` and `android-gradle` are already source-backed on current `main`, while `android-java`, `android-emulator-runtime`, and the combined iOS placeholder remain `manual-review-required`
- The checked-in iOS baseline on current `main` watches these simulator facts:
  - `simulator.runtime_identifier=com.apple.CoreSimulator.SimRuntime.iOS-26-2`
  - `simulator.runtime_name=iOS 26.2`
  - `simulator.device_name=iPhone 16`
- Fresh source inspection during analyst shaping confirmed Apple currently publishes simulator runtime metadata at `https://devimages-cdn.apple.com/downloads/xcode/simulators/index2.dvtdownloadableindex`, and that catalog contains an iOS 26.2 simulator runtime entry (`name=iOS 26.2 beta Simulator Runtime`, `simulatorVersion.version=26.2`).
- That same source inspection did **not** expose one stable machine-readable selector for the watched simulator device name. Raw catalog inspection surfaced separate device-support packages rather than one trustworthy runtime-catalog field for `simulator.device_name`.

That means the original issue wording was still too broad for one honest implementation seam. The immediate repo-owned next slice is runtime-catalog evaluation for `simulator.runtime_identifier` and `simulator.runtime_name`. The selected simulator device remains watched on current `main`, but any future source-backed device-availability logic now belongs to the separate follow-up issue `#172` rather than being smuggled into this runtime-catalog slice.

## Current-main prerequisite

This slice is only honest after current `main` exposes the split iOS source-rule contract from the earlier `#144` work.

Required precondition before implementation starts:
- `.github/runner-host-advisory-sources.json` already exposes `ios-xcode` with `follow_up_issue: 164`
- `.github/runner-host-advisory-sources.json` already exposes `ios-simulator-runtime` with `follow_up_issue: 165`
- `tests/test-support/scripts/runner_host_review_report.py` already renders those split group keys in the source-rule summary

If current `main` still exposes only the combined `ios-xcode-simulator` group when Dev begins this issue, hand the slice back instead of re-implementing the earlier split inside `#165`.

## Scope of this slice

Add source-backed iOS simulator runtime-catalog evaluation to the existing runner-host watch.

This slice must:
1. promote only `ios-simulator-runtime` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate only the watched iOS simulator runtime identity/version facts `simulator.runtime_identifier` and `simulator.runtime_name` against Apple’s simulator runtime catalog
3. keep `simulator.device_name` inside the existing watched inventory as a drift-only supporting fact rather than inventing a second device-availability source-backed evaluator in this issue
4. surface actionable simulator-runtime findings through the existing managed issue `security: runner-host review needed`
5. preserve the current drift / missing-evidence behavior for the watched runner-host facts and keep every non-runtime group on its existing separate follow-up issue

## Required implementation artifacts

### 1. iOS simulator runtime source-rule contract

Update:
- `.github/runner-host-advisory-sources.json`

Contract:
- require current `main` to already expose `ios-simulator-runtime` as a split group owned by `#165`; if it does not, hand the slice back
- keep the `ios-simulator-runtime` group key, `follow_up_issue: 165`, surface name, and watched fact paths unchanged once that split exists
- change only the `ios-simulator-runtime` rule kind from `manual-review-required` to a stable active kind: `apple-simulator-runtime-catalog`
- add only the rule-specific source metadata needed to resolve iOS simulator runtime entries from Apple’s simulator catalog
- preserve `ios-xcode` as a separate issue under `#164`
- preserve `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` as their existing separate groups/follow-up issues
- do **not** widen `.github/runner-host-watch.json`
- keep `simulator.device_name` in the watched inventory, but treat it as drift-only/supporting context for this slice rather than a source-backed mismatch dimension
- do **not** reassign `simulator.device_name` to another current issue inside this implementation; its future source-backed/device-availability shaping now belongs to `#172`

### 2. Runner-host source evaluation and report plumbing

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- normalize the new `apple-simulator-runtime-catalog` rule kind and validate its required source metadata
- fetch or otherwise load Apple’s simulator runtime catalog during live runs while keeping deterministic fixture-driven coverage for tests instead of relying on live network calls in unit tests
- evaluate only these watched simulator facts from the active source-backed path:
  - `simulator.runtime_identifier`
  - `simulator.runtime_name`
- treat the Apple catalog as authoritative for runtime existence/version matching, not as a freshness ratchet for newer upstream runtimes
- produce explicit iOS simulator-runtime source findings when any of the following is true:
  - the observed runtime identifier/name cannot be normalized into one expected iOS runtime version/name pair
  - the normalized observed runtime version has no authoritative iOS runtime row in the Apple catalog
  - the observed runtime name does not match the authoritative runtime row for the normalized version
  - the Apple source response is unavailable, malformed, or contradictory for the simulator-runtime slice
- keep the current drift / missing-evidence evaluation for watched facts authoritative and unchanged for both platforms
- preserve the existing meaning of top-level `advisory_count` on current `main`: it is the total actionable finding count across baseline drift / missing evidence and source-backed review findings already counted by the delivered `runner-images` and `android-gradle` evaluators
- make iOS simulator-runtime source findings contribute to that same top-level `advisory_count` instead of inventing a separate top-level `source_advisory_count`
- set top-level `alert` / `verdict` to review-needed when either:
  - drift / missing evidence requires review, or
  - iOS simulator-runtime source findings require review
- keep top-level reason precedence truthful:
  - `baseline-match` when there is no drift and no simulator-runtime source finding
  - existing drift reasons keep winning when drift or missing evidence exists
  - use only these exact source-backed reasons when the promoted runtime rule drives the verdict:
    - `ios-simulator-runtime-source-drift`
    - `ios-simulator-runtime-source-error`
- render markdown that clearly distinguishes iOS simulator-runtime source-backed findings from drift / missing-evidence findings and states that `ios-xcode`, `#172`, and the non-iOS groups remain separate work
- keep `simulator.device_name` in the existing drift-only path for this slice; do **not** create a second source-only alert solely because the selected device name lacks a stable match in the runtime catalog
- do **not** auto-alert solely because Apple publishes a newer runtime than the observed one while the observed runtime still resolves cleanly in the authoritative catalog
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed simulator-runtime findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/simulator-runtime-source/`

Required coverage:
- matching Apple simulator runtime metadata for the observed `simulator.runtime_identifier=com.apple.CoreSimulator.SimRuntime.iOS-26-2` and `simulator.runtime_name=iOS 26.2` → `alert=false`, `advisory_count=0`, and `ios-simulator-runtime` is reported as `apple-simulator-runtime-catalog`
- no matching Apple runtime row for the observed runtime version → `alert=true` with a dedicated simulator-runtime source-backed review-needed reason and an incremented top-level `advisory_count` even when the watched-fact drift count remains zero
- Apple runtime row present but the observed runtime name does not match the authoritative row → `alert=true` with a dedicated simulator-runtime source-backed review-needed reason and an incremented top-level `advisory_count` even when the watched-fact drift count remains zero
- authoritative-source payload unavailable or malformed → explicit review-needed simulator-runtime source finding instead of silent success, with the same top-level `advisory_count` path used for other source-backed findings on current `main`
- newer runtime rows exist upstream while the observed runtime still resolves cleanly → no automatic alert from the simulator-runtime source path alone
- existing drift and missing-evidence fixtures still preserve their current overall `advisory_count` behavior while source-backed findings remain distinguishable in the rendered output
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` itself exercises the active `ios-simulator-runtime` rule while `simulator.device_name` remains a watched drift-only fact and `ios-xcode` plus the non-iOS groups stay outside this slice

### 4. Canonical docs and live-contract reconciliation

Update:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`
- `docs/specs/issues/issue-124-runner-host-drift-watch.md`
- `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`
- `docs/specs/issues/issue-142-android-runner-host-source-split.md`
- `docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md`
- `docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md`
- `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`
- `docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md`
- `docs/specs/issues/issue-164-ios-xcode-source-evaluation/spec.md`
- `docs/specs/issues/issue-164-ios-xcode-source-evaluation/tasks.md`
- `docs/specs/issues/issue-154-android-java-source-evaluation/spec.md`
- `docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md`
- `docs/specs/issues/issue-155-android-gradle-source-evaluation/spec.md`
- `docs/specs/issues/issue-155-android-gradle-source-evaluation/tasks.md`
- `docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md`
- `docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/tasks.md`

Those updates must explicitly say:
- current `main` now performs source-backed evaluation for `ios-simulator-runtime`
- `ios-xcode` remains separate follow-up work under `#164`
- `simulator.device_name` remains part of the watched drift contract, but any future source-backed device-availability work belongs to `#172` rather than this runtime-catalog slice
- `runner-images` and `android-gradle` remain the already-delivered source-backed groups on current `main`, while `android-java` and `android-emulator-runtime` stay on their own separate follow-up issues until those slices land
- actionable simulator-runtime findings continue to reuse `security: runner-host review needed`
- a newer Apple runtime upstream alone is not yet a review-needed condition on current `main`; this slice is bounded to recognized runtime identity/name validation for the observed runtime, not a general upgrade/freshness policy
- older issue-spec artifacts, including the ordered task lists in `docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md` and `docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md`, must stop claiming that `#144` is still the current or future iOS umbrella owner, must stop preserving closed `#144` as the remaining iOS follow-up after the split prerequisite lands, and must stop claiming that current `main` still has no active iOS source-backed evaluation once this slice lands
- `docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md` must stop preserving the stale post-`#143` wording that `#154`, `#155`, `#156`, and `#144` remain future work; after `#165` lands, that historical task artifact must point the remaining iOS follow-up ownership at the split issues `#164` / `#165` instead of reviving closed umbrella issue `#144`
- `docs/specs/issues/issue-164-ios-xcode-source-evaluation/{spec,tasks}.md` must stop preserving the post-`#164` current-main contract where `ios-simulator-runtime` is still manual-only future work; after `#165` lands, those older artifacts must describe `ios-simulator-runtime` as already source-backed on current `main` and preserve the shared current-main contract where source-backed findings increment the same top-level `advisory_count` while remaining explicit through source-rule group details
- `docs/specs/issues/issue-154-android-java-source-evaluation/{spec,tasks}.md` must stop preserving the pre-split `ios-xcode-simulator -> #144` live-owner story once the split `ios-xcode` / `ios-simulator-runtime` prerequisite is on current `main`, and must keep the post-`#165` shared summary contract truthful by preserving that same shared current-main contract instead of reviving either a drift-only top-level count or a separate top-level `source_advisory_count`
- `docs/specs/issues/issue-155-android-gradle-source-evaluation/{spec,tasks}.md` must stop requiring simulator-runtime source findings to use a separate top-level source-backed finding/count field once this slice lands; after `#165`, those adjacent follow-up artifacts must preserve the shared current-main contract where simulator-runtime source findings increment the same top-level `advisory_count` while remaining explicit through source-rule group details
- `docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/{spec,tasks}.md` must keep that same shared current-main contract for simulator-runtime source findings, and `docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md` must stop saying the later iOS work lives in open spec-entry PRs `#171` and `#173`; after `#165` lands, that adjacent spec must describe the later iOS ownership through open follow-up issues `#164` / `#165` without preserving `#173` as still open

## Acceptance criteria

1. Once the split iOS source-rule contract already exists on current `main`, `.github/runner-host-advisory-sources.json` exposes `ios-simulator-runtime` as `apple-simulator-runtime-catalog` while preserving `follow_up_issue: 165`, and `ios-xcode` remains the separate follow-up under `#164`.
2. A recognized Apple simulator runtime row for the observed runtime still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no simulator-runtime source findings requiring review.
3. A missing runtime row, a runtime-name mismatch, or source-unavailable simulator-runtime evaluation produces an explicit source-backed finding for `ios-simulator-runtime`, increments the same top-level `advisory_count` current `main` already uses for source-backed findings, and turns the overall runner-host summary/managed-issue path into `manual-review-required` even when the watched-fact drift count remains zero.
4. The rendered JSON and markdown distinguish simulator-runtime source-backed findings from drift / missing-evidence findings, keep `simulator.device_name` in the drift-only/supporting contract, and leave `ios-xcode`, `#172`, and the non-iOS groups as separate work.
5. The named canonical docs and adjacent main-branch issue specs/tasks (`#124`, `#129`, `#142`, `issue-143/{spec,tasks}.md`, `issue-144/{spec,tasks}.md`, `issue-164/{spec,tasks}.md`, and `issue-154/155/156/{spec,tasks}.md`) no longer claim that current runner-host automation has no active iOS source-backed evaluation, no longer preserve `#144` as the live or remaining iOS umbrella owner after the split prerequisite lands, no longer preserve `ios-simulator-runtime` as manual-only future work after `#165`, and no longer leave contradictory shared summary/count expectations about whether simulator-runtime source findings increment the same top-level `advisory_count` or use a separate top-level `source_advisory_count` field.
6. The implementation PR for this slice can honestly say `Closes #165` because the iOS simulator runtime-catalog evaluation becomes active on `main` without widening the watched inventory or absorbing Xcode/device-availability work.

## Observable report scenarios

```gherkin
Feature: iOS simulator runtime-catalog evaluation in the runner-host watch

  Scenario: A recognized Apple runtime keeps the lane green
    Given the runner-host baseline and observed iOS runtime facts match current main
    And the Apple simulator runtime catalog contains the observed runtime version and name
    When the runner-host report is rendered
    Then the report verdict is "no review-needed"
    And the source-rule output marks ios-simulator-runtime as source-backed clean
    And simulator.device_name remains supporting drift context rather than a source-backed mismatch

  Scenario: A missing or mismatched runtime requires review
    Given the observed iOS runtime facts are present
    And the Apple simulator runtime catalog cannot match the observed runtime version or name
    When the runner-host report is rendered
    Then the report verdict is "manual-review-required"
    And the issue title remains "security: runner-host review needed"
    And the actionable finding appears in the ios-simulator-runtime section of the summary and markdown

  Scenario: Runtime source errors fail closed
    Given the promoted ios-simulator-runtime evaluator cannot fetch, parse, or trust the Apple runtime catalog
    When the runner-host report is rendered
    Then the report verdict is "manual-review-required"
    And the output explains that the simulator-runtime source-backed evaluation could not be trusted
    And the report does not silently return a clean result
```

## Explicit non-goals

- **no** source-backed evaluation for `runner-images` (`#143`)
- **no** source-backed evaluation for `android-java` (`#154`)
- **no** source-backed evaluation for `android-gradle` (`#155`)
- **no** source-backed evaluation for `android-emulator-runtime` (`#156`)
- **no** source-backed evaluation for `ios-xcode` (`#164`)
- **no** source-backed evaluation for `simulator.device_name`; that future device-availability work belongs to `#172`
- **no** widening of `.github/runner-host-watch.json` or addition of new watched iOS facts
- **no** automatic freshness ratchet solely because Apple later publishes a newer runtime row
- **no** new managed issue title or parallel runner-host issue-sync lane
- **no** local simulator probing beyond the emitted workflow artifact facts already captured by the smoke artifact contract

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
git diff --check
python3 -m py_compile \
  tests/test-support/scripts/runner_host_review_report.py \
  tests/scripts/test_runner_host_review_report.py
python3 -m unittest tests/scripts/test_runner_host_review_report.py
python3 tests/test-support/scripts/runner_host_review_report.py \
  --repo drousselhq/casgrain \
  --baseline .github/runner-host-watch.json \
  --android-workflow android-emulator-smoke.yml \
  --android-artifact casgrain-android-smoke \
  --ios-workflow ios-simulator-smoke.yml \
  --ios-artifact casgrain-ios-smoke \
  --summary-out /tmp/runner-host-watch-summary.json \
  --markdown-out /tmp/runner-host-watch.md
python3 - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('/tmp/runner-host-watch-summary.json').read_text(encoding='utf-8'))
ios_runtime = next(group for group in summary['source_rule_groups'] if group['key'] == 'ios-simulator-runtime')
assert ios_runtime['rule_kind'] == 'apple-simulator-runtime-catalog', ios_runtime
assert ios_runtime['follow_up_issue'] == 165, ios_runtime
assert 'source_advisory_count' not in summary, summary
print('ios-simulator-runtime source-backed rule is present in the runner-host summary')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#165` because it turns the checked-in `ios-simulator-runtime` placeholder into an active source-backed evaluation on current `main` once the earlier split contract already exists.

After that PR merges:
- iOS simulator runtime identity/version facts are evaluated from Apple’s simulator runtime catalog through the existing runner-host watch
- `simulator.device_name` remains a drift-only supporting fact
- `#164` remains the bounded follow-up for iOS Xcode source-backed evaluation
- `#172` remains the bounded follow-up for any future simulator device-availability source-backed work
- any future work on runtime freshness ratchets, alternate device-selection policy, or broader Apple simulator/source semantics must land as a new bounded follow-up issue instead of being smuggled into `#165`
