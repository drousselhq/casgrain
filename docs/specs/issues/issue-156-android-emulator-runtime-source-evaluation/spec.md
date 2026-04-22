# Issue #156 — Evaluate source-backed advisory automation for Android emulator-runtime host facts

- Issue: `#156`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #156`
- Upstream slices already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
  - `#142` (`Split Android runner-host advisory source rules into bounded follow-up slices`)
- Related follow-up issues that must remain separate from this slice:
  - `#143` (`runner-images`)
  - `#154` (`android-java`)
  - `#155` (`android-gradle`)
  - `#144` (`ios-xcode-simulator`)

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #158 split the Android runner-host backlog into bounded `android-java`, `android-gradle`, and `android-emulator-runtime` groups.
- A fresh live invocation at analyst handoff (`2026-04-22` UTC) against current `main` still reports:
  - `verdict=no review-needed`
  - `reason=baseline-match`
  - `advisory_count=0`
  - source-rule groups `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, `ios-xcode-simulator`
  - every current source-rule group, including `android-emulator-runtime`, remains `manual-review-required`
- The latest successful Android smoke artifact on `main` currently emits this emulator evidence:
  - `api_level=34`
  - `target=google_apis`
  - `arch=x86_64`
  - `profile=pixel_7`
  - `device_name=sdk_gphone64_x86_64`
  - `os_version=14`
- `.github/workflows/android-emulator-smoke.yml` currently pins the same runtime inputs for the Android smoke lane:
  - `api-level: 34`
  - `target: google_apis`
  - `arch: x86_64`
  - `profile: pixel_7`
- `tests/test-support/scripts/runner_host_review_report.py` currently accepts only `manual-review-required` source-rule kinds, so current `main` cannot yet express or evaluate an active Android emulator-runtime source-backed rule.
- Fresh source inspection during analyst shaping confirmed:
  - `https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-5.xml` exposes `system-images;android-34;google_apis;x86_64` with `api-level=34`, tag `google_apis`, and `abi=x86_64`
  - `https://dl.google.com/android/repository/repository2-1.xml` exposes `platforms;android-34`
  - `https://source.android.com/docs/setup/reference/build-numbers` maps `Android14` to `API level 34` / version `14`
- Android's AVD documentation states that an emulator device is the combination of a hardware profile and a system image. Current `host-environment.json` records supporting lookup inputs (`target`, `arch`, `profile`) alongside the watched facts, but `.github/runner-host-watch.json` does not currently watch those supporting inputs and the emitted `sdk_gphone64_x86_64` string is an AVD product identity rather than a standalone upstream release channel.

That means the honest remaining gap is now narrow: add trustworthy source-backed evaluation for the Android emulator-runtime group by validating the selected system-image/runtime identity against authoritative Android platform metadata, while keeping the existing drift guard for the emitted `device_name` string and without widening the checked-in watched inventory.

## Scope of this slice

Add source-backed Android emulator-runtime evaluation to the existing runner-host watch.

This slice must:
1. promote only `android-emulator-runtime` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate the observed Android emulator runtime identity from authoritative platform/system-image metadata using `emulator.api_level` and `emulator.os_version`, with the existing emitted `target` / `arch` fields as supporting lookup inputs
3. surface actionable emulator-runtime findings through the existing managed issue `security: runner-host review needed`
4. preserve the current drift / missing-evidence behavior for the existing watched facts and keep every non-emulator runner-host group `manual-review-required`
5. keep `emulator.device_name` as a drift-guarded supporting fact in this slice rather than inventing a second source-backed alert dimension for the generated AVD product string

## Required implementation artifacts

### 1. Android emulator-runtime source-rule contract

Update:
- `.github/runner-host-advisory-sources.json`

Contract:
- keep the `android-emulator-runtime` group key, `follow_up_issue: 156`, surface name, and watched fact paths unchanged
- change only the `android-emulator-runtime` rule kind from `manual-review-required` to a stable active kind: `android-system-image-catalog`
- add the rule-specific source metadata needed to evaluate the official Android platform + system-image feeds and to render the human-facing source description in report output
- the rule metadata must include the authoritative source locations for:
  - Android platform catalog metadata
  - Google APIs x86_64 system-image catalog metadata
  - Android version / API-level mapping metadata
- the rule metadata may use the already-emitted `target` / `arch` fields as lookup inputs for source evaluation, but this slice must **not** widen `.github/runner-host-watch.json` to make those support fields newly watched facts
- preserve `runner-images`, `android-java`, `android-gradle`, and `ios-xcode-simulator` as `manual-review-required` groups mapped to their existing follow-up issues

### 2. Runner-host source evaluation and report plumbing

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- normalize the new `android-system-image-catalog` rule kind and validate its required source metadata
- fetch or otherwise load authoritative Android platform/system-image data during live runs, while keeping deterministic fixture-driven coverage for tests instead of relying on live network calls in unit tests
- evaluate the Android emulator-runtime group by checking all of the following:
  - the observed `emulator.api_level` resolves to an official Android platform entry on current `main`
  - the observed `emulator.os_version` is consistent with the authoritative Android version/API mapping for that API level
  - the configured Android smoke runtime (`target=google_apis`, `arch=x86_64`) has a matching official system-image package for the observed API level
- produce explicit Android emulator-runtime source findings when any of the following is true:
  - no matching official Google APIs x86_64 system-image package exists for the observed API level
  - the authoritative Android version/API mapping does not support the observed `emulator.os_version` ↔ `emulator.api_level` pair
  - the authoritative Android source response is unavailable, malformed, or contradictory for the emulator-runtime slice
- keep the current drift / missing-evidence evaluation for watched facts authoritative and unchanged for both platforms
- preserve the existing meaning of top-level `advisory_count`: it remains the count of changed or missing watched facts from the baseline contract
- add a separate source-backed finding count/list (for example `source_advisory_count` plus detailed source findings) instead of overloading the drift counter
- set top-level `alert` / `verdict` to review-needed when either:
  - drift / missing evidence requires review, or
  - Android emulator-runtime source findings require review
- keep top-level reason precedence truthful:
  - `baseline-match` when there is no drift and no Android emulator-runtime source finding
  - existing drift reasons keep winning when drift or missing evidence exists
  - use a dedicated source-backed reason (for example `source-review-needed`) when drift count is zero but Android emulator-runtime source findings require review
- render markdown that clearly distinguishes Android emulator-runtime source-backed findings from drift / missing-evidence findings and states that the non-emulator runner-host groups still remain `manual-review-required` follow-ups
- keep `emulator.device_name` in the existing baseline-drift story for this slice; do **not** invent a second source-only alert solely because the generated device string differs from an upstream naming convention
- do **not** auto-alert solely because the Android catalog exposes a newer API level, extension level, or system-image revision than the current baseline while the selected API 34 / Android 14 Google APIs x86_64 runtime still resolves cleanly
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed Android emulator-runtime findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/emulator-source/`

Required coverage:
- matching Android platform + system-image source payloads for API 34 / Android 14 / Google APIs x86_64 → `alert=false`, `advisory_count=0`, `source_advisory_count=0`, and `android-emulator-runtime` is reported as `android-system-image-catalog`
- no matching Google APIs x86_64 package for the observed API level → `alert=true` with a source-backed review-needed reason while the drift counter remains zero
- authoritative Android version/API mapping disagrees with the observed `os_version` / `api_level` pair → `alert=true` with a source-backed review-needed reason while the drift counter remains zero
- authoritative-source payload unavailable or malformed → explicit review-needed Android emulator-runtime source finding instead of silent success
- a newer official system-image revision or newer Android API exists while the current API 34 / Android 14 runtime is still a recognized match → no automatic alert from the emulator-runtime source path alone
- existing drift and missing-evidence fixtures still preserve their current `advisory_count` behavior
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` itself exercises the active `android-emulator-runtime` rule while the non-emulator groups stay manual-only

### 4. Canonical docs and live-contract reconciliation

Update:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`
- `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`
- `docs/specs/issues/issue-142-android-runner-host-source-split.md`

Those updates must explicitly say:
- current `main` now performs source-backed evaluation for `android-emulator-runtime` only
- `runner-images`, `android-java`, `android-gradle`, and `ios-xcode-simulator` still remain `manual-review-required` follow-up groups until their own slices land
- actionable Android emulator-runtime findings continue to reuse `security: runner-host review needed`
- a newer Android API level, extension level, or system-image revision alone is not yet a review-needed condition on current `main`; this slice is bounded to recognized package/runtime identity, not general freshness policy
- `emulator.device_name` remains part of the drift guard for the Android smoke artifact contract, while authoritative source evaluation in this slice is grounded on the platform/system-image runtime identity
- `target`, `arch`, and `profile` remain supporting lookup/context fields emitted by `host-environment.json`, but this slice does not promote them into newly watched runner-host facts
- older issue-spec artifacts are historical and must not keep claiming that current `main` has no source-backed runner-host evaluation at all after this slice lands

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` exposes `android-emulator-runtime` as `android-system-image-catalog` while preserving its watched fact paths and `follow_up_issue: 156`.
2. A recognized Android 14 / API 34 Google APIs x86_64 runtime still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no emulator-runtime source findings requiring review.
3. Missing package metadata, an API/runtime mismatch, or source-unavailable Android emulator-runtime evaluation produces an explicit source-backed finding for `android-emulator-runtime` and turns the overall runner-host summary/managed-issue path into `manual-review-required` without pretending the drift counter increased.
4. The rendered JSON and markdown distinguish Android emulator-runtime source-backed findings from drift / missing-evidence findings, leave the non-emulator runner-host groups as `manual-review-required` follow-ups, and do not auto-alert merely because a newer Android API/system-image revision exists.
5. The named canonical docs and older main-branch issue specs no longer claim that current runner-host automation is drift-only for every source group.
6. The implementation PR for this slice can honestly say `Closes #156` because the Android emulator-runtime source-backed evaluation becomes active on `main`.

## Explicit non-goals

- **no** source-backed evaluation for `runner-images` (`#143`)
- **no** source-backed evaluation for `android-java` (`#154`)
- **no** source-backed evaluation for `android-gradle` (`#155`)
- **no** source-backed evaluation for `ios-xcode-simulator` (`#144`)
- **no** widening of `.github/runner-host-watch.json` to add `emulator.target`, `emulator.arch`, `emulator.profile`, extension levels, package revisions, or any other new watched fact
- **no** separate source-only alert policy for the generated `emulator.device_name` string in this slice
- **no** automatic freshness ratchet solely because a newer Android API, extension level, or system-image revision exists upstream
- **no** new managed issue title or parallel runner-host issue-sync lane
- **no** direct probing of locally installed SDK state; the evaluator should use authoritative public source metadata plus the emitted workflow artifact facts

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
android = next(group for group in summary['source_rule_groups'] if group['key'] == 'android-emulator-runtime')
assert android['rule_kind'] == 'android-system-image-catalog', android
assert android['follow_up_issue'] == 156, android
assert 'source_advisory_count' in summary, summary
print('android-emulator-runtime source-backed rule is present in the runner-host summary')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#156` because it turns the checked-in `android-emulator-runtime` placeholder into an active source-backed evaluation on current `main`.

After that PR merges:
- Android emulator-runtime identity is evaluated from authoritative Android platform/system-image metadata through the existing runner-host watch
- `runner-images`, `android-java`, `android-gradle`, and `ios-xcode-simulator` remain separate manual-review follow-ups
- any future work on device-name policy, profile-level policy, API freshness ratchets, or broader Android runtime semantics must land as a new bounded follow-up issue instead of being smuggled into `#156`
