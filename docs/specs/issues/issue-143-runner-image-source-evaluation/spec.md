# Issue #143 — Promote runner-images to source-backed GitHub-hosted runner image evaluation

- Issue: `#143`
- Spec mode: `behavior spec`
- Expected implementation PR linkage: `Closes #143`

## Why this slice exists

Already delivered on `main`:
- PR #145 added the checked-in runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #157 and PR #158 split the Android host-toolchain backlog into the bounded follow-up issues `#154`, `#155`, and `#156`.
- The current runner-host watch already owns the live summary and managed issue flow through:
  - `.github/runner-host-watch.json`
  - `tests/test-support/scripts/runner_host_review_report.py`
  - `.github/workflows/cve-watch.yml`
  - `tests/test-support/scripts/cve_watch_issue_sync.py`
- A fresh analyst dry-run on current `main` still reports:
  - `verdict=no review-needed`
  - `reason=baseline-match`
  - `advisory_count=0`
  - `runner-images` still marked `manual-review-required`

That means the repo already owns the drift / missing-evidence runner-host lane honestly, but the `runner-images` source group is still only a placeholder for future source-backed evaluation.

## Scope of this slice

Promote the existing `runner-images` group from `manual-review-required` to one bounded source-backed evaluation slice for the currently watched GitHub-hosted runner image facts on:
- Android smoke runner facts under `ubuntu-latest`
- iOS smoke runner facts under `macos-15`

This slice must:
1. change only the `runner-images` source group behavior
2. keep the existing `security: runner-host review needed` managed issue path
3. keep the watched fact inventory in `.github/runner-host-watch.json` unchanged
4. preserve the current drift / missing-evidence behavior for the rest of the runner-host watch
5. keep the remaining source groups explicit future work:
   - `android-java` → `#154`
   - `android-gradle` → `#155`
   - `android-emulator-runtime` → `#156`
   - `ios-xcode-simulator` → `#144`

## Required implementation artifacts

### 1. Promote only the checked-in `runner-images` source rule

Update:
- `.github/runner-host-advisory-sources.json`

Contract requirements:
- promote only the `runner-images` entry away from `manual-review-required`
- keep these existing fields unchanged for `runner-images` unless the promoted rule must add minimal new fields:
  - `key=runner-images`
  - `platforms=["android", "ios"]`
  - `follow_up_issue=143`
  - the current watched fact paths from `.github/runner-host-watch.json`
- leave the four non-`runner-images` groups on current `main` as `manual-review-required`
- do not widen the watched inventory beyond the current runner-image / OS facts already owned by `runner-images`
- do not repurpose `#143` into a generic runner-host source-rule framework

The promoted rule must stay fail-closed:
- if the authoritative runner-image source data cannot be fetched, parsed, or matched to the current watched facts, the evaluator must surface an explicit review-needed outcome instead of silently returning clean

### 2. Add one bounded runner-images evaluator to the runner-host report

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- add exactly one runner-images-specific promoted rule path for the `runner-images` group
- keep the existing drift / missing-evidence platform summary logic authoritative for watched-fact drift
- evaluate the currently watched runner-image facts only:
  - Android: `runner.label`, `runner.image_name`, `runner.image_version`, `runner.os_version`
  - iOS: `runner.label`, `runner.image_name`, `runner.image_version`, `runner.os_version`, `runner.os_build`
- include machine-readable source-backed outcome details for `runner-images` in the emitted summary JSON and markdown
- keep the existing top-level fields and managed issue title intact so `cve_watch_issue_sync.py` can keep reusing the same issue lane
- do not generalize this slice into shared promotion logic for the Android or iOS host-toolchain groups that still belong to later issues

Required outcome model for `runner-images`:
- clean source-backed match → may still yield overall `no review-needed`
- actionable runner-image finding → must reuse the existing `security: runner-host review needed` lane
- source retrieval / parsing / matching failure → must fail closed into explicit review-needed reporting, not a silent clean pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/source-rules/`
- add a new runner-image-source fixture directory under `tests/test-support/fixtures/runner-host-watch/runner-image-source/`

Required coverage:
- a deterministic clean `runner-images` source-backed case
- an Android actionable runner-image case
- an iOS actionable runner-image case
- a malformed or unavailable runner-image source case that proves the evaluator fails closed
- unchanged manual-review-only behavior for `android-java`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator`
- a checked-in manifest test that proves only `runner-images` was promoted and the other four groups stayed manual-review-only

### 4. Reconcile report wording and canonical docs

Update:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`

Update these docs so they say:
- the runner-host lane is no longer uniformly drift-only once `#143` lands
- `runner-images` is the only source-backed promoted group after this slice
- the remaining runner-host groups stay explicit future work under `#154`, `#155`, `#156`, and `#144`
- the managed findings issue title remains `security: runner-host review needed`

Workflow touch is allowed only if narrowly necessary:
- `.github/workflows/cve-watch.yml` may change only for minimal step wording or a minimal input/env adjustment already available in the job
- do not add a new secret, a new managed issue path, or a second runner-host sync step in this slice

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` promotes only `runner-images`; the other four runner-host groups remain `manual-review-required`.
2. `runner_host_review_report.py` can emit source-backed `runner-images` outcome details without breaking the existing top-level summary shape used by `cve_watch_issue_sync.py`.
3. A clean deterministic source-backed `runner-images` fixture can still render `no review-needed`.
4. Actionable deterministic runner-image findings reopen or update the existing `security: runner-host review needed` path rather than inventing a new managed issue title.
5. Source retrieval or parsing failure for the promoted `runner-images` rule fails closed into review-needed reporting instead of a silent clean result.
6. Drift / missing-evidence behavior for the rest of the runner-host watch remains intact on current `main`.
7. The implementation PR for this slice can honestly say `Closes #143` because it finishes the bounded `runner-images` promotion work, while the Android and iOS host-toolchain follow-ups remain open under their existing issue numbers.

## Behavior-spec scenario coverage

```gherkin
Feature: Source-backed runner-images evaluation in the runner-host watch

  Scenario: Clean authoritative runner-image metadata keeps the lane green
    Given the runner-host baseline and observed Android/iOS runner facts match the checked-in watch inventory
    And the authoritative runner-image source resolves those watched runner-images facts cleanly for the promoted runner-images group
    When the runner-host report is rendered
    Then the report verdict is "no review-needed"
    And the source-rule output marks runner-images as source-backed clean
    And the remaining runner-host groups stay explicit future follow-up work

  Scenario: An actionable Android runner-image finding reuses the managed runner-host review lane
    Given the observed Android runner-images facts are present
    And the authoritative runner-image source returns an actionable finding for the promoted runner-images group
    When the runner-host report is rendered
    Then the report verdict is "manual-review-required"
    And the issue title remains "security: runner-host review needed"
    And the actionable finding appears in the runner-images section of the summary and markdown

  Scenario: An actionable iOS runner-image finding reuses the managed runner-host review lane
    Given the observed iOS runner-images facts are present
    And the authoritative runner-image source returns an actionable finding for the promoted runner-images group
    When the runner-host report is rendered
    Then the report verdict is "manual-review-required"
    And the issue title remains "security: runner-host review needed"
    And the actionable finding appears in the runner-images section of the summary and markdown

  Scenario: Runner-image source errors fail closed
    Given the promoted runner-images evaluator cannot fetch, parse, or match the authoritative source data
    When the runner-host report is rendered
    Then the report verdict is "manual-review-required"
    And the output explains that the runner-images source-backed evaluation could not be trusted
    And the report does not silently return a clean result

  Scenario: Non-promoted host-toolchain groups stay manual-review-only
    Given runner-images has been promoted by this slice
    When the runner-host report is rendered
    Then android-java, android-gradle, android-emulator-runtime, and ios-xcode-simulator remain manual-review-only follow-up groups
```

## Explicit non-goals

- **no** Android Java source-backed automation in this slice (`#154`)
- **no** Android Gradle source-backed automation in this slice (`#155`)
- **no** Android emulator-runtime source-backed automation in this slice (`#156`)
- **no** iOS Xcode / simulator source-backed automation in this slice (`#144`)
- **no** widening of `.github/runner-host-watch.json` to add new watched facts such as `runner.os_name`
- **no** generic source-rule engine for every future runner-host source family
- **no** broad package-in-image scraping or unrelated CVE inventory work beyond the current `runner-images` contract
- **no** new managed issue title or parallel issue-sync workflow

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
assert summary['issue_title'] == 'security: runner-host review needed', summary
keys = {group['key'] for group in summary['source_rule_groups']}
assert keys == {
    'runner-images',
    'android-java',
    'android-gradle',
    'android-emulator-runtime',
    'ios-xcode-simulator',
}, summary
non_runner_groups = {
    group['key']: group['rule_kind']
    for group in summary['source_rule_groups']
    if group['key'] != 'runner-images'
}
assert all(kind == 'manual-review-required' for kind in non_runner_groups.values()), non_runner_groups
print('runner-images promotion left the remaining source groups untouched')
PY
```

The live invocation above should be treated as a render smoke and contract check, not as a promise that the external source-backed verdict will stay fixed forever.

## Completion boundary

The implementation PR for this spec should be able to close `#143` because it finishes the bounded `runner-images` source-backed promotion slice.

After that PR merges:
- `#154`, `#155`, and `#156` remain the bounded Android host-toolchain follow-ups
- `#144` remains the bounded iOS Xcode / simulator-runtime follow-up
- the runner-host lane continues to reuse `security: runner-host review needed`
- any later desire for broader runner-image package or CVE inventory work must be shaped as a new bounded issue rather than smuggled into this slice
