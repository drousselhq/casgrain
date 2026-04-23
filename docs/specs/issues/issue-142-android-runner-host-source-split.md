# Issue #142 — Split Android runner-host advisory source rules into bounded follow-up slices

- Issue: `#142`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #142`
- Later follow-up implementation slices after this contract lands:
  - `#154` — Android Java host version facts
  - `#155` — Android Gradle host version facts
  - `#156` — Android emulator-runtime host facts

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- Current `main` still owns the drift / missing-evidence runner-host review path and a live invocation during analyst shaping returned:
  - `verdict=no review-needed`
  - `reason=baseline-match`
  - `advisory_count=0`
  - source-rule groups: `runner-images`, `android-java-gradle`, `ios-xcode-simulator`
- The Android source-backed backlog is therefore still represented as one combined manual-review-only group:
  - key: `android-java-gradle`
  - follow-up issue: `#142`

That remaining Android group is still too broad for one honest implementation PR because it mixes multiple future authoritative-source families:
1. watched Android Java version facts
2. watched Android Gradle version facts
3. watched Android emulator-runtime facts

Without another repo-owned contract split, any later implementation would either widen one PR across unrelated source families or leave the checked-in source-rule manifest and docs claiming that one issue still owns all Android source-backed promotion work.

## Scope of this slice

Narrow `#142` to the immediate repo-owned contract split only.

This slice must:
1. replace the single Android `android-java-gradle` source-rule group with three bounded Android groups
2. bind each new Android group to exactly one later follow-up issue
3. keep the current drift / missing-evidence alert semantics and managed issue title unchanged
4. keep the report/docs truthful that all Android groups still remain `manual-review-required` on current `main`
5. stay testable from checked-in manifests, report output, and deterministic fixtures

This slice is **not** the later source-backed advisory implementation itself. It is the contract change that makes the later Android source integrations bounded and auditable.

## Required implementation artifacts

### 1. Split the checked-in Android source-rule inventory

Update:
- `.github/runner-host-advisory-sources.json`

The implementation PR must replace the current combined Android group with exactly these bounded Android groups:

1. `android-java`
   - platforms: `android`
   - watched fact paths:
     - `java.configured_major`
     - `java.resolved_version`
   - follow-up issue: `#154`
   - current rule kind: `manual-review-required`
   - candidate source description: authoritative Java release/support metadata for the configured and resolved runtime version facts

2. `android-gradle`
   - platforms: `android`
   - watched fact paths:
     - `gradle.configured_version`
     - `gradle.resolved_version`
   - follow-up issue: `#155`
   - current rule kind: `manual-review-required`
   - candidate source description: authoritative Gradle release/support metadata for the configured and resolved version facts

3. `android-emulator-runtime`
   - platforms: `android`
   - watched fact paths:
     - `emulator.api_level`
     - `emulator.device_name`
     - `emulator.os_version`
   - follow-up issue: `#156`
   - current rule kind: `manual-review-required`
   - candidate source description: authoritative Android emulator / system-image / runtime metadata for the watched emulator facts

Contract requirements:
- `runner-images` must remain mapped to `#143`
- `ios-xcode-simulator` must remain mapped to `#144`
- every watched fact path in `.github/runner-host-watch.json` must still be owned by exactly one source-rule group after the split
- the manifest must fail closed if any Android watched fact path is dropped, duplicated, or assigned to the wrong follow-up issue

Explicit current-main boundary:
- `host-environment.json` currently emits `java.distribution`, but `.github/runner-host-watch.json` does **not** watch that fact on current `main`
- this slice must **not** silently widen the watched inventory just to keep the old umbrella wording alive
- if the repo later wants source-backed promotion for `java.distribution`, that must be shaped as a separate future contract change rather than smuggled into this slice

### 2. Runner-host report integration

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract for this slice:
- accept the new Android group keys and follow-up issue mappings
- emit the split Android groups in the machine-readable summary
- render markdown that names the three Android manual-review groups separately instead of one combined Android umbrella group
- keep the current top-level `verdict`, `reason`, `alert`, `advisory_count`, and managed-issue behavior authoritative for this slice
- fail closed if the manifest omits one of the expected new Android groups, points a group at the wrong follow-up issue, or leaves any watched Android fact uncovered

Required reporting behavior:
- current clean runs must still report `no review-needed` when the baseline matches
- the new source-rule section must make it explicit that Android Java, Gradle, and emulator-runtime promotion are still future follow-up work
- the report must not imply that any Android source-backed advisory evaluation is already active until `#154`, `#155`, or `#156` lands

### 3. Tests and fixtures

Add or extend deterministic fixtures and tests so the repo validates the new Android split directly.

Required coverage:
- valid manifest with the three split Android groups plus the unchanged runner-images / iOS groups
- duplicate or missing Android watched fact ownership fails closed
- wrong follow-up issue number for one split Android group fails closed
- rendered JSON/markdown includes the new Android group keys and keeps the same clean top-level drift verdict

The tests should cover the production checked-in manifest, not only a synthetic fixture copy.

### 4. Canonical docs updates

The implementation PR for this spec must update these docs:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`

Those docs updates must explicitly say:
- the shipped runner-host automation still evaluates drift / missing evidence only
- the Android backlog is no longer one combined `android-java-gradle` umbrella after this slice
- historical note: later source-backed Android promotion was split across `#154`, `#155`, and `#156`; current `main` now has `#155` delivered while `#154` and `#156` remain follow-ups
- those later Android slices must continue to reuse the existing `security: runner-host review needed` lane rather than inventing parallel managed issue titles
- `java.distribution` is not part of the current watched runner-host inventory unless and until a later contract change adds it explicitly

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` no longer uses `#142` as the owner of one combined Android source group; it instead exposes three bounded Android groups mapped to `#154`, `#155`, and `#156`.
2. Every watched fact path in `.github/runner-host-watch.json` remains covered exactly once after the split.
3. `runner_host_review_report.py` still reports the same honest top-level drift result for current clean `main`, while exposing the split Android groups in JSON and markdown.
4. The canonical security docs stop describing the Android source-backed backlog as one umbrella owned by `#142` and instead point at the three bounded follow-up issues.
5. The implementation PR for this slice can honestly say `Closes #142` because it finishes the immediate repo-owned contract split, while the actual Java / Gradle / emulator source-backed integrations remain in follow-up issues.

## Bounded design decisions

### In scope for the implementation PR
- one bounded manifest split in `.github/runner-host-advisory-sources.json`
- one bounded update to `runner_host_review_report.py`
- one focused test/fixture update that proves coverage stays fail-closed
- bounded docs updates in the three named canonical security docs

### Explicit non-goals
- **no** live external advisory queries in this slice
- **no** source-backed promotion logic for Android Java (`#154`)
- **no** source-backed promotion logic for Android Gradle (`#155`)
- **no** source-backed promotion logic for Android emulator runtime (`#156`)
- **no** change to the existing runner-host managed issue title or drift-alert semantics
- **no** widening of `.github/runner-host-watch.json` to add new watched Android facts such as `java.distribution`
- **no** changes to the delivered runner-image slice (`#143`) or the iOS (`#144`) source-backed follow-up beyond re-pointing the Android contract story honestly

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
assert summary['verdict'] == 'no review-needed', summary
assert summary['reason'] == 'baseline-match', summary
keys = {group['key'] for group in summary['source_rule_groups']}
assert keys == {
    'runner-images',
    'android-java',
    'android-gradle',
    'android-emulator-runtime',
    'ios-xcode-simulator',
}, summary
issue_map = {group['key']: group['follow_up_issue'] for group in summary['source_rule_groups']}
assert issue_map['android-java'] == 154, issue_map
assert issue_map['android-gradle'] == 155, issue_map
assert issue_map['android-emulator-runtime'] == 156, issue_map
print('runner-host Android source split summary present')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#142` because it finishes the immediate repo-owned Android source-rule split.

After that PR merges:
- `#154` remains the bounded follow-up for Android Java host version source-backed promotion
- `#155` is the delivered Android Gradle host version source-backed promotion on current `main`
- `#156` remains the bounded follow-up for Android emulator-runtime source-backed promotion
- the shipped runner-host lane on `main` now includes the delivered `runner-images` source-backed exception from `#143` and the delivered `android-gradle` source-backed slice from `#155`, while `#154` and `#156` remain the Android follow-ups that are still manual-review-only on current `main`
