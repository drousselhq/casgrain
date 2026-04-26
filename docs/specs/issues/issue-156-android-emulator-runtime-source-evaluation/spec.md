# Issue #156 — Evaluate source-backed advisory automation for Android emulator-runtime host facts

- Issue: `#156`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #156`
- Upstream slices already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
  - `#142` (`Split Android runner-host advisory source rules into bounded follow-up slices`)
  - `#143` (`runner-images` source-backed promotion)
- Related follow-up issues that must remain separate from this slice:
  - `#154` (`android-java`)
  - `#155` (`android-gradle`)
  - `#164` (`ios-xcode`)
  - `#165` (`ios-simulator-runtime`)

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #158 split the Android runner-host backlog into bounded `android-java`, `android-gradle`, and `android-emulator-runtime` groups.
- PR #174 already promoted `runner-images` to the active `runner-image-release-metadata` rule on current `main`.
- A fresh live invocation at the pre-`#155` analyst-repair checkpoint against then-current `main` reported:
  - `verdict=manual-review-required`
  - `reason=runner-images-source-drift`
  - `advisory_count=2`
  - source-rule groups `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, `ios-xcode-simulator`
  - `runner-images` evaluated as `runner-image-release-metadata`, while `android-java`, `android-gradle`, `android-emulator-runtime`, and the current combined `ios-xcode-simulator` placeholder still rendered as `manual-review-required`
- GitHub issue `#144` is already closed, while the later iOS source-backed work now lives in open follow-up issues `#164` and `#165`; their issue-scoped specs are already merged on `main` via PRs `#171` and `#173`.
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
- `tests/test-support/scripts/runner_host_review_report.py` on current `main` currently accepts only `manual-review-required` and `runner-image-release-metadata` source-rule kinds, so the repo cannot yet express or evaluate an active Android emulator-runtime source-backed rule.
- Fresh source inspection during analyst shaping confirmed:
  - `https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-5.xml` exposes `system-images;android-34;google_apis;x86_64` with `api-level=34`, tag `google_apis`, and `abi=x86_64`
  - `https://dl.google.com/android/repository/repository2-1.xml` exposes `platforms;android-34`
  - `https://source.android.com/docs/setup/reference/build-numbers` maps `Android14` to `API level 34` / version `14`
- Android's AVD documentation states that an emulator device is the combination of a hardware profile and a system image. Current `host-environment.json` records supporting lookup inputs (`target`, `arch`, `profile`) alongside the watched facts, but `.github/runner-host-watch.json` does not currently watch those supporting inputs and the emitted `sdk_gphone64_x86_64` string is an AVD product identity rather than a standalone upstream release channel.

That means the honest remaining gap is now narrow: add trustworthy source-backed evaluation for the Android emulator-runtime group by validating the selected system-image/runtime identity against authoritative Android platform metadata, while keeping the existing drift guard for the emitted `device_name` string, preserving the already-delivered `runner-images` slice, and without widening the checked-in watched inventory or smuggling the separate iOS ownership cleanup already split across `#164` / `#165` into this Android slice.

## Scope of this slice

Add source-backed Android emulator-runtime evaluation to the existing runner-host watch.

This slice must:
1. promote only `android-emulator-runtime` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate the observed Android emulator runtime identity from authoritative platform/system-image metadata using `emulator.api_level` and `emulator.os_version`, with the existing emitted `target` / `arch` fields as supporting lookup inputs
3. surface actionable emulator-runtime findings through the existing managed issue `security: runner-host review needed`
4. preserve the current drift / missing-evidence behavior, keep the delivered `runner-images` rule intact, leave `android-java` and `android-gradle` unchanged, and do not widen this Android slice into the separate iOS follow-up ownership already tracked by `#164` / `#165`
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
- preserve `runner-images` as the delivered `runner-image-release-metadata` group
- preserve `android-java` and `android-gradle` on their already-delivered source-backed paths under `#154` / `#155`
- do not use this slice to reopen closed issue `#144` or to invent a new combined iOS owner in touched docs/specs; any later iOS source-backed work remains tracked by `#164` / `#165`

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
- preserve the current meaning of top-level `advisory_count`: it remains the total actionable finding count across baseline drift / missing evidence and source-backed review findings; do **not** introduce a separate top-level `source_advisory_count`
- when Android emulator-runtime source findings require review and baseline drift count is zero, use a dedicated emulator-runtime source reason (for example `android-emulator-runtime-source-review-needed`) rather than reusing a drift reason
- render JSON and markdown that clearly distinguish Android emulator-runtime source-backed findings from drift / missing-evidence findings, preserve `runner-images` as the delivered source-backed group, and expose the current combined `ios-xcode-simulator` placeholder with plural later ownership under `#164` / `#165` instead of reintroducing closed issue `#144` as the live owner
- keep `emulator.device_name` in the existing baseline-drift story for this slice; do **not** invent a second source-only alert solely because the generated device string differs from an upstream naming convention
- do **not** auto-alert solely because the Android catalog exposes a newer API level, extension level, or system-image revision than the current API 34 / Android 14 Google APIs x86_64 runtime while that selected runtime still resolves cleanly
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed Android emulator-runtime findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/emulator-source/`

Required coverage:
- matching Android platform + system-image source payloads for API 34 / Android 14 / Google APIs x86_64 → `alert=false`, `advisory_count=0`, and `android-emulator-runtime` is reported as `android-system-image-catalog`
- no matching Google APIs x86_64 package for the observed API level → `alert=true` with a dedicated emulator-runtime source-backed review-needed reason and an incremented top-level `advisory_count`, while the underlying watched-fact drift count remains zero
- authoritative Android version/API mapping disagrees with the observed `os_version` / `api_level` pair → `alert=true` with a dedicated emulator-runtime source-backed review-needed reason and an incremented top-level `advisory_count`
- authoritative-source payload unavailable or malformed → explicit review-needed Android emulator-runtime source finding instead of silent success
- a newer official system-image revision or newer Android API exists while the current API 34 / Android 14 runtime is still a recognized match → no automatic alert from the emulator-runtime source path alone
- existing drift and missing-evidence fixtures still preserve their current overall `advisory_count` behavior while the source-backed findings remain distinguishable in the rendered output
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` exercises the active `android-emulator-runtime` rule, keeps `runner-images` and `android-gradle` on their already-delivered source-backed paths, and leaves `android-java` plus the later iOS follow-up groups unchanged

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
- `docs/specs/issues/issue-154-android-java-source-evaluation/spec.md`
- `docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md`
- `docs/specs/issues/issue-155-android-gradle-source-evaluation/spec.md`
- `docs/specs/issues/issue-155-android-gradle-source-evaluation/tasks.md`

Those updates must explicitly say:
- current `main` already performs source-backed evaluation for `runner-images`, and after this slice it also performs source-backed evaluation for `android-emulator-runtime`
- `android-java` and `android-gradle` are already source-backed on current `main`
- current `main` still renders one combined `ios-xcode-simulator` placeholder as `manual-review-required`, but touched docs/specs must not preserve closed issue `#144` as the live later-owner because the iOS source-backed follow-up work is already split across `#164` / `#165`
- actionable Android emulator-runtime findings continue to reuse `security: runner-host review needed`
- a newer Android API level, extension level, or system-image revision alone is not yet a review-needed condition on current `main`; this slice is bounded to recognized package/runtime identity, not general freshness policy
- `emulator.device_name` remains part of the drift guard for the Android smoke artifact contract, while authoritative source evaluation in this slice is grounded on the platform/system-image runtime identity
- `target`, `arch`, and `profile` remain supporting lookup/context fields emitted by `host-environment.json`, but this slice does not promote them into newly watched runner-host facts
- `docs/specs/issues/issue-124-runner-host-drift-watch.md` must stop saying that only `#143` is delivered while `#154`, `#155`, `#156`, and closed issue `#144` all remain later source-specific follow-ups; after `#156` lands it must describe `runner-images` and `android-emulator-runtime` as the delivered source-backed slices while keeping `android-java`, `android-gradle`, and the later iOS follow-up ownership truthful under `#164` / `#165`
- `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md` and `docs/specs/issues/issue-142-android-runner-host-source-split.md` must stop describing current `main` as uniformly drift-only or as having no active source-backed runner-host evaluation after `#156` lands
- `docs/specs/issues/issue-143-runner-image-source-evaluation/{spec,tasks}.md` must stop saying only `runner-images` is source-backed or presenting `#156` as untouched future work once this slice lands
- `docs/specs/issues/issue-144-ios-runner-host-source-split/{spec,tasks}.md` must stop using closed issue `#144` as if it were still the live owner of the later iOS source-backed work; after `#156` lands they must keep `runner-images` and `android-emulator-runtime` as the delivered source-backed exceptions while pointing the later iOS follow-up ownership at `#164` / `#165`
- `docs/specs/issues/issue-154-android-java-source-evaluation/{spec,tasks}.md` must stop requiring drift-only `advisory_count` plus a top-level `source_advisory_count`, and must stop saying `android-emulator-runtime` remains `manual-review-required` after `#156` lands
- `docs/specs/issues/issue-155-android-gradle-source-evaluation/{spec,tasks}.md` must stop preserving `android-emulator-runtime` as a later unchanged `manual-review-required` follow-up or leaving `#156` as untouched future work after this slice lands; after `#156` lands they must treat `android-emulator-runtime` as an already-delivered source-backed group while keeping only the bounded `android-gradle` slice under `#155` and the later iOS ownership truthful under `#164` / `#165`

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` exposes `android-emulator-runtime` as `android-system-image-catalog` while preserving its watched fact paths and `follow_up_issue: 156`, and keeps `runner-images` on `runner-image-release-metadata`.
2. A recognized Android 14 / API 34 Google APIs x86_64 runtime still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no emulator-runtime source findings requiring review.
3. Missing package metadata, an API/runtime mismatch, or source-unavailable Android emulator-runtime evaluation produces an explicit source-backed finding for `android-emulator-runtime`, increments the overall `advisory_count`, and turns the overall runner-host summary/managed-issue path into `manual-review-required` even when no watched-fact drift exists.
4. The rendered JSON and markdown distinguish Android emulator-runtime source-backed findings from drift / missing-evidence findings, preserve `runner-images`, `android-gradle`, and `android-emulator-runtime` as delivered source-backed groups, keep `android-java` as the remaining Android follow-up, and expose the current `ios-xcode-simulator` placeholder with plural later ownership under `#164` / `#165` rather than reintroducing closed issue `#144` as the live owner.
5. The named canonical docs and historical issue-spec/task artifacts no longer claim that current runner-host automation is drift-only or that only `runner-images` is source-backed on current `main`, no longer preserve stale `android-emulator-runtime` manual-only / unchanged-ownership wording in the adjacent `#154` / `#155` issue-spec artifacts, and no longer require a top-level `source_advisory_count` for the shared runner-host summary contract.
6. The implementation PR for this slice can honestly say `Closes #156` because the Android emulator-runtime source-backed evaluation becomes active on `main`.

## Explicit non-goals

- **no** further behavior or ownership changes to the delivered `runner-images` slice (`#143`)
- **no** source-backed evaluation for `android-java` (`#154`)
- **no** changes to the already-delivered `android-gradle` source-backed evaluation (`#155`)
- **no** source-backed evaluation or iOS ownership/split implementation work; later iOS follow-up work remains with `#164` and `#165`
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
groups = {group['key']: group for group in summary['source_rule_groups']}
assert groups['android-emulator-runtime']['rule_kind'] == 'android-system-image-catalog', groups['android-emulator-runtime']
assert groups['android-emulator-runtime']['follow_up_issue'] == 156, groups['android-emulator-runtime']
assert groups['runner-images']['rule_kind'] == 'runner-image-release-metadata', groups['runner-images']
assert groups['ios-xcode-simulator']['follow_up_issues'] == [164, 165], groups['ios-xcode-simulator']
assert 'follow_up_issue' not in groups['ios-xcode-simulator'], groups['ios-xcode-simulator']
assert summary['source_rule_managed_issue_title'] == 'security: runner-host review needed', summary
print('android-emulator-runtime source-backed rule is present while runner-images stays delivered')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#156` because it turns the checked-in `android-emulator-runtime` placeholder into an active source-backed evaluation on current `main`.

After that PR merges:
- Android emulator-runtime identity is evaluated from authoritative Android platform/system-image metadata through the existing runner-host watch
- `runner-images` remains the delivered source-backed group on current `main`
- `android-java` and `android-gradle` are already delivered as source-backed groups, and later iOS source-backed work remains under `#164` / `#165` even though current `main` still renders one combined iOS placeholder today
- any future work on device-name policy, profile-level policy, API freshness ratchets, or broader Android runtime semantics must land as a new bounded follow-up issue instead of being smuggled into `#156`
