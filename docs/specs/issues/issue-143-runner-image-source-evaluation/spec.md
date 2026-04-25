# Issue #143 — Promote runner-images to source-backed GitHub-hosted runner image evaluation

- Issue: `#143`
- Spec mode: `behavior spec`
- Expected implementation PR linkage: `Closes #143`

## Why this slice exists

Already delivered on `main`:
- PR #145 added the checked-in runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- Historical note: PR #157 and PR #158 split the Android host-toolchain backlog into the bounded follow-up issues `#154`, `#155`, and `#156`; current `main` now has `#155` delivered while `#154` and `#156` remain follow-ups.
- The current runner-host watch already owns the live summary and managed issue flow through:
  - `.github/runner-host-watch.json`
  - `tests/test-support/scripts/runner_host_review_report.py`
  - `.github/workflows/cve-watch.yml`
  - `tests/test-support/scripts/cve_watch_issue_sync.py`
- At issue #143 shaping time, a fresh analyst dry-run reported:
  - `verdict=no review-needed`
  - `reason=baseline-match`
  - `advisory_count=0`
  - `runner-images` marked `manual-review-required`

That meant the repo already owned the drift / missing-evidence runner-host lane honestly, but the `runner-images` source group was only a placeholder before PR #143 promoted it to source-backed evaluation.

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
   - `android-emulator-runtime` → `#156`
   - `ios-xcode-simulator` → `#144`

## Required implementation artifacts

### 1. Promote only the checked-in `runner-images` source rule

Update:
- `.github/runner-host-advisory-sources.json`

Contract requirements:
- promote only the `runner-images` entry from `manual-review-required` to the exact literal `rule_kind=runner-image-release-metadata`
- keep these existing fields unchanged for `runner-images` unless this spec names the additional field explicitly:
  - `key=runner-images`
  - `surface=GitHub-hosted runner images and OS facts`
  - `platforms=["android", "ios"]`
  - `follow_up_issue=143`
  - `managed_issue_behavior` continues to reuse `security: runner-host review needed`
  - the current watched fact paths from `.github/runner-host-watch.json`
- keep `candidate_source` explicit as `GitHub-hosted runner image release metadata`; do not broaden this slice into generic package/CVE scraping or a new source family
- add an exact `source_streams` object on `runner-images` with only these platform selectors and source-compared facts:
  - `android` → `runner_label=ubuntu-latest`, `image_name=ubuntu-24.04`, `compared_facts=[runner.image_version, runner.os_version]`
  - `ios` → `runner_label=macos-15`, `image_name=macos-15-arm64`, `compared_facts=[runner.image_version, runner.os_version, runner.os_build]`
- `runner.label` and `runner.image_name` remain part of the checked-in watched inventory and the emitted context, but this slice treats them as source-stream selectors / drift-only facts rather than as source-backed changed-fact assertions
- leave the four non-`runner-images` groups on current `main` as `manual-review-required`
- do not widen the watched inventory beyond the current runner-image / OS facts already owned by `runner-images`
- do not repurpose `#143` into a generic runner-host source-rule framework

The promoted rule must stay fail-closed:
- the evaluator must normalize the authoritative source into per-platform records with exact source-backed fields:
  - Android: `image_version`, `os_version`
  - iOS: `image_version`, `os_version`, `os_build`
- if the authoritative runner-image source data cannot be fetched, parsed, normalized into those exact fields, or matched to the selected `source_streams` contract for the current watched runner facts, the evaluator must surface an explicit review-needed outcome instead of silently returning clean

### 2. Add one bounded runner-images evaluator to the runner-host report

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- add exactly one runner-images-specific promoted rule path for `rule_kind=runner-image-release-metadata`
- keep the existing drift / missing-evidence platform summary logic authoritative for the full watched-fact inventory in `.github/runner-host-watch.json`
- treat `runner.label` and `runner.image_name` as stream-selection / drift-context inputs for this slice, not as new source-backed changed-fact comparisons
- evaluate source-backed runner-images facts only through the exact normalized per-platform field sets named above:
  - Android: `runner.image_version`, `runner.os_version`
  - iOS: `runner.image_version`, `runner.os_version`, `runner.os_build`
- include machine-readable runner-images outcome details for `runner-images` in the emitted summary JSON and markdown without inventing a second top-level report family
- keep the existing top-level fields and managed issue title intact so `cve_watch_issue_sync.py` can keep reusing the same issue lane
- do not generalize this slice into shared promotion logic for the Android or iOS host-toolchain groups that still belong to later issues

Required emitted summary contract:
- top-level `verdict` values remain exactly `no review-needed` or `manual-review-required`
- top-level `reason` continues to use `baseline-match`, `baseline-drift`, and `missing-evidence` for the existing drift/evidence paths; add only these exact runner-images-specific reasons when the promoted rule drives the verdict:
  - `runner-images-source-drift`
  - `runner-images-source-error`
- the `runner-images` entry inside `summary['source_rule_groups']` must include these exact new fields:
  - `status` → `no review-needed` or `manual-review-required`
  - `outcome` → `source-match`, `source-drift`, or `source-error`
  - `platform_results` → one entry for `android` and one entry for `ios`
- each `platform_results` entry for `runner-images` must include exactly these machine-readable fields:
  - `platform`
  - `status`
  - `outcome`
  - `observed`
  - `source`
  - `changed_facts`
  - `source_error`
- `observed` and `source` must carry only the exact source-backed facts for that platform from this slice; `changed_facts` must identify only those same compared fact paths
- the four non-`runner-images` groups remain manifest-only `manual-review-required` follow-up entries; this slice must not require them to emit promoted-rule-only fields

Required outcome model for `runner-images`:
- clean source-backed match → `outcome=source-match`, `status=no review-needed`, and overall `verdict` may remain `no review-needed`
- actionable runner-image finding → `outcome=source-drift`, `status=manual-review-required`, `reason=runner-images-source-drift`, and reuse the existing `security: runner-host review needed` lane
- source retrieval / parsing / normalization / matching failure → `outcome=source-error`, `status=manual-review-required`, `reason=runner-images-source-error`, and fail closed rather than silently returning clean

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
- `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`
- `docs/specs/issues/issue-124-runner-host-drift-watch.md`
- `docs/specs/issues/issue-142-android-runner-host-source-split.md`

Update these docs so they say:
- the runner-host lane is no longer uniformly drift-only once `#143` lands
- `runner-images` and the later `android-gradle` slice `#155` are the delivered source-backed promoted groups on current `main`
- the remaining runner-host groups stay explicit future work under `#154`, `#156`, and `#144`
- the managed findings issue title remains `security: runner-host review needed`
- the older issue-spec docs for `#129` and `#124` no longer describe `#143` as remaining future work on current `main`; they must explicitly reconcile that `#143` is the delivered runner-images promotion slice while the other follow-up issues remain open
- `docs/specs/issues/issue-142-android-runner-host-source-split.md` no longer says the shipped runner-host lane stays drift-triggered review until a later Android follow-up lands; it must reconcile that `runner-images` becomes the delivered source-backed exception while `#154` and `#156` remain the Android follow-ups after the later Android Gradle slice `#155` landed

Workflow touch is allowed only if narrowly necessary:
- `.github/workflows/cve-watch.yml` may change only for minimal step wording or a minimal input/env adjustment already available in the job
- do not add a new secret, a new managed issue path, or a second runner-host sync step in this slice

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` promotes only `runner-images`, uses the exact literal `rule_kind=runner-image-release-metadata`, and keeps the other four runner-host groups `manual-review-required`.
2. The promoted `runner-images` manifest entry freezes the exact `source_streams` selectors and compared-fact boundaries for Android and iOS without widening `.github/runner-host-watch.json`.
3. `runner_host_review_report.py` keeps the existing top-level summary shape intact and uses only the exact runner-images-specific reason values `runner-images-source-drift` and `runner-images-source-error` when the promoted rule drives the verdict.
4. The `runner-images` entry inside `summary['source_rule_groups']` emits the exact promoted-rule fields `status`, `outcome`, and `platform_results`, and each platform result emits `platform`, `status`, `outcome`, `observed`, `source`, `changed_facts`, and `source_error`.
5. A clean deterministic source-backed `runner-images` fixture can still render `no review-needed` with `outcome=source-match`.
6. Actionable deterministic runner-image findings reuse the existing `security: runner-host review needed` path with `outcome=source-drift` rather than inventing a new managed issue title.
7. Source retrieval, parsing, normalization, or matching failure for the promoted `runner-images` rule fails closed into `reason=runner-images-source-error` rather than a silent clean result.
8. Drift / missing-evidence behavior for the rest of the runner-host watch remains intact on current `main`.
9. The canonical runner-host docs plus the older issue-spec docs for `#129`, `#124`, and `#142` no longer describe `#143` as remaining future work or claim the shipped runner-host lane stays uniformly drift-triggered after this slice lands; they reconcile `#143` as the delivered runner-images promotion, `#155` as the later delivered Android Gradle slice, and only `#154`, `#156`, and `#144` as the open follow-ups.
10. The implementation PR for this slice can honestly say `Closes #143` because it finishes the bounded `runner-images` promotion work, while the Android and iOS host-toolchain follow-ups remain open under their existing issue numbers.

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
- `#154` and `#156` remain the bounded Android host-toolchain follow-ups after the later Android Gradle slice `#155` shipped
- `#144` remains the bounded iOS Xcode / simulator-runtime follow-up
- the runner-host lane continues to reuse `security: runner-host review needed`
- any later desire for broader runner-image package or CVE inventory work must be shaped as a new bounded issue rather than smuggled into this slice
