# Issue #164 — Evaluate source-backed advisory automation for iOS Xcode host facts

- Issue: `#164`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #164`
- Upstream slice already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
- Repo-owned prerequisite already merged on `main` as analyst contract:
  - `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`
- Related follow-up issues that must remain separate from this slice:
  - `#143` (`runner-images`)
  - `#154` (`android-java`)
  - `#155` (`android-gradle`)
  - `#156` (`android-emulator-runtime`)
  - `#165` (`ios-simulator-runtime`)

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #166 merged the analyst contract for `#144`, which froze the later iOS source-backed work into two separate follow-up issues: `#164` for Xcode host facts and `#165` for simulator-runtime host facts.
- A fresh live invocation at analyst handoff (`2026-04-22` UTC) against current `main` still reports:
  - `verdict=no review-needed`
  - `reason=baseline-match`
  - `advisory_count=0`
  - source-rule groups `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator`
  - every current source-rule group, including the combined iOS group, remains `manual-review-required`
- The checked-in iOS baseline on current `main` watches these Xcode facts:
  - `xcode.app_path=/Applications/Xcode_16.4.app`
  - `xcode.version=16.4`
  - `xcode.simulator_sdk_version=18.5`
- Fresh source inspection during analyst shaping confirmed Apple currently publishes authoritative Xcode support metadata at `https://developer.apple.com/support/xcode/`, and the Xcode 16.4 row lists `iOS 18.5` in the bundled SDK/support table.
- That same source inspection also confirmed the Apple simulator-runtime catalog lives in a different authoritative source family (`index2.dvtdownloadableindex`), which belongs to `#165`, not this Xcode-only slice.

That leaves one honest bounded next step once the earlier iOS split contract is present on current `main`: activate source-backed evaluation for the Xcode group only, using Apple’s Xcode support matrix for `xcode.version` and `xcode.simulator_sdk_version`, while keeping `xcode.app_path` as a drift-only supporting fact and leaving simulator-runtime evaluation to `#165`.

## Current-main prerequisite

This slice is only honest after current `main` exposes the split iOS source-rule contract from the earlier `#144` work.

Required precondition before implementation starts:
- `.github/runner-host-advisory-sources.json` already exposes `ios-xcode` with `follow_up_issue: 164`
- `.github/runner-host-advisory-sources.json` already exposes `ios-simulator-runtime` with `follow_up_issue: 165`
- `tests/test-support/scripts/runner_host_review_report.py` already renders those split group keys in the source-rule summary

If current `main` still exposes only the combined `ios-xcode-simulator` group when Dev begins this issue, hand the slice back instead of re-implementing the earlier split inside `#164`.

## Scope of this slice

Add source-backed iOS Xcode evaluation to the existing runner-host watch.

This slice must:
1. promote only `ios-xcode` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate only the watched iOS Xcode release/support facts `xcode.version` and `xcode.simulator_sdk_version` against Apple’s published Xcode support matrix
3. keep `xcode.app_path` inside the existing watched inventory as a drift-only supporting fact rather than inventing a second source-backed alert dimension for a local install path
4. surface actionable Xcode findings through the existing managed issue `security: runner-host review needed`
5. preserve the current drift / missing-evidence behavior for the watched runner-host facts and keep every non-Xcode group on its existing separate follow-up issue

## Required implementation artifacts

### 1. iOS Xcode source-rule contract

Update:
- `.github/runner-host-advisory-sources.json`

Contract:
- require current `main` to already expose `ios-xcode` as a split group owned by `#164`; if it does not, hand the slice back
- keep the `ios-xcode` group key, `follow_up_issue: 164`, surface name, and watched fact paths unchanged once that split exists
- change only the `ios-xcode` rule kind from `manual-review-required` to a stable active kind: `apple-xcode-support-matrix`
- add only the rule-specific source metadata needed to evaluate the Apple Xcode support matrix row for the observed Xcode version and bundled simulator SDK version
- preserve `ios-simulator-runtime` as `manual-review-required` and mapped to `#165`
- preserve `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` as their existing separate groups/follow-up issues
- do **not** widen `.github/runner-host-watch.json`
- keep `xcode.app_path` in the watched inventory, but treat it as drift-only/supporting context for this slice rather than as a source-backed mismatch dimension

### 2. Runner-host source evaluation and report plumbing

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- normalize the new `apple-xcode-support-matrix` rule kind and validate its required source metadata
- fetch or otherwise load Apple’s Xcode support matrix during live runs while keeping deterministic fixture-driven coverage for tests instead of relying on live network calls in unit tests
- evaluate only these watched Xcode facts from the active source-backed path:
  - `xcode.version`
  - `xcode.simulator_sdk_version`
- produce explicit iOS Xcode source findings when any of the following is true:
  - the observed `xcode.version` has no authoritative row in the Apple Xcode support matrix
  - the observed `xcode.simulator_sdk_version` is not present in the authoritative support matrix row for the observed Xcode version
  - the Apple source response is unavailable, malformed, or contradictory for the Xcode slice
- keep the current drift / missing-evidence evaluation for watched facts authoritative and unchanged for both platforms
- preserve the existing meaning of top-level `advisory_count`: it remains the count of changed or missing watched facts from the baseline contract
- add a separate source-backed finding count/list (for example `source_advisory_count` plus detailed source findings) instead of overloading the drift counter
- set top-level `alert` / `verdict` to review-needed when either:
  - drift / missing evidence requires review, or
  - iOS Xcode source findings require review
- keep top-level reason precedence truthful:
  - `baseline-match` when there is no drift and no iOS Xcode source finding
  - existing drift reasons keep winning when drift or missing evidence exists
  - use a dedicated source-backed reason (for example `source-review-needed`) when drift count is zero but iOS Xcode source findings require review
- render markdown that clearly distinguishes iOS Xcode source-backed findings from drift / missing-evidence findings and states that `ios-simulator-runtime` plus the non-iOS groups still remain separate follow-up work
- keep `xcode.app_path` in the existing drift-only path for this slice; do **not** invent a second source-only alert solely because the local app bundle path differs from a naming convention
- do **not** auto-alert solely because Apple publishes a newer Xcode release or newer SDK row upstream while the observed Xcode version / bundled SDK pair still resolves cleanly in the authoritative matrix
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed iOS Xcode findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/xcode-source/`

Required coverage:
- matching Apple Xcode support metadata for the observed `xcode.version=16.4` and `xcode.simulator_sdk_version=18.5` → `alert=false`, `advisory_count=0`, `source_advisory_count=0`, and `ios-xcode` is reported as `apple-xcode-support-matrix`
- no matching Apple row for the observed Xcode version → `alert=true` with a source-backed review-needed reason while the drift counter remains zero
- Apple row present but the observed simulator SDK version is not listed for that Xcode version → `alert=true` with a source-backed review-needed reason while the drift counter remains zero
- authoritative-source payload unavailable or malformed → explicit review-needed iOS Xcode source finding instead of silent success
- newer Xcode or SDK rows exist upstream while the observed Xcode version / bundled SDK pair still resolves cleanly → no automatic alert from the iOS Xcode source path alone
- existing drift and missing-evidence fixtures still preserve their current `advisory_count` behavior
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` itself exercises the active `ios-xcode` rule while `ios-simulator-runtime` and the non-iOS groups stay manual-only

### 4. Canonical docs and live-contract reconciliation

Update:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`
- `docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md`
- `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`

Those updates must explicitly say:
- current `main` now performs source-backed evaluation for `ios-xcode`
- `ios-simulator-runtime` remains separate follow-up work under `#165`
- `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` remain on their own separate source-backed follow-up issues until those slices land
- actionable iOS Xcode findings continue to reuse `security: runner-host review needed`
- `xcode.app_path` remains part of the drift guard / supporting context for the iOS smoke artifact contract in this slice rather than a source-backed comparison field
- a newer Apple Xcode release or newer SDK row alone is not yet a review-needed condition on current `main`; this slice is bounded to recognized release/support metadata for the observed Xcode version and bundled SDK facts, not a general freshness policy
- older issue-spec artifacts are historical and must not keep claiming that current `main` still has no active iOS source-backed evaluation or that `#164` remains unresolved future work after this slice lands

## Acceptance criteria

1. Once the split iOS source-rule contract already exists on current `main`, `.github/runner-host-advisory-sources.json` exposes `ios-xcode` as `apple-xcode-support-matrix` while preserving `follow_up_issue: 164`, and `ios-simulator-runtime` remains `manual-review-required` under `#165`.
2. A recognized Apple support-matrix row for the observed Xcode version / bundled simulator SDK pair still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no Xcode source findings requiring review.
3. A missing row, a simulator-SDK mismatch, or source-unavailable iOS Xcode evaluation produces an explicit source-backed finding for `ios-xcode` and turns the overall runner-host summary/managed-issue path into `manual-review-required` without pretending the drift counter increased.
4. The rendered JSON and markdown distinguish iOS Xcode source-backed findings from drift / missing-evidence findings, keep `xcode.app_path` in the drift-only/supporting contract, and leave `ios-simulator-runtime` plus the non-iOS groups as separate manual-review follow-ups.
5. The named canonical docs and older main-branch issue specs no longer claim that current runner-host automation has no active iOS source-backed evaluation or that `ios-xcode` remains unresolved future work after `#164` lands.
6. The implementation PR for this slice can honestly say `Closes #164` because the iOS Xcode source-backed evaluation becomes active on `main` without widening the watched inventory or absorbing the simulator-runtime work.

## Explicit non-goals

- **no** source-backed evaluation for `runner-images` (`#143`)
- **no** source-backed evaluation for `android-java` (`#154`)
- **no** source-backed evaluation for `android-gradle` (`#155`)
- **no** source-backed evaluation for `android-emulator-runtime` (`#156`)
- **no** source-backed evaluation for `ios-simulator-runtime` (`#165`)
- **no** widening of `.github/runner-host-watch.json` or addition of new watched Xcode facts
- **no** second source-only alert dimension for `xcode.app_path`
- **no** automatic freshness ratchet solely because Apple later publishes a newer Xcode or SDK row
- **no** new managed issue title or parallel runner-host issue-sync lane
- **no** local Xcode probing beyond the emitted workflow artifact facts already captured by the smoke artifact contract

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
ios_xcode = next(group for group in summary['source_rule_groups'] if group['key'] == 'ios-xcode')
assert ios_xcode['rule_kind'] == 'apple-xcode-support-matrix', ios_xcode
assert ios_xcode['follow_up_issue'] == 164, ios_xcode
assert 'source_advisory_count' in summary, summary
print('ios-xcode source-backed rule is present in the runner-host summary')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#164` because it turns the checked-in `ios-xcode` placeholder into an active source-backed evaluation on current `main` once the earlier split contract already exists.

After that PR merges:
- iOS Xcode facts are evaluated from Apple’s Xcode support matrix through the existing runner-host watch
- `xcode.app_path` remains a drift-only supporting fact
- `#165` remains the bounded follow-up for simulator-runtime source-backed evaluation
- any future work on Xcode freshness ratchets, alternate path policy, or broader Apple advisory semantics must land as a new bounded follow-up issue instead of being smuggled into `#164`
