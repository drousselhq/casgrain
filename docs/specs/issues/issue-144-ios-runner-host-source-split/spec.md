# Issue #144 — Split iOS runner-host advisory source rules into bounded Xcode and simulator-runtime follow-up slices

- Linked issue: `#144`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #144`
- Later follow-up implementation slices after this contract lands:
  - `#164` — iOS Xcode host facts
  - `#165` — iOS simulator-runtime host facts

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #151 landed the current checked-in split across `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, and one combined iOS `ios-xcode-simulator` group.
- A fresh live render on current `main` during analyst shaping returned:
  - iOS run `24713703011` -> `no review-needed`
  - top-level `verdict=no review-needed`
  - `reason=baseline-match`
  - source-rule groups: `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, `ios-xcode-simulator`
  - no managed `security: runner-host review needed` issue is currently open from drift or missing evidence

That means the repo already owns the **drift / missing-evidence** runner-host slice honestly.

What still remains is narrower than the current issue wording. The combined iOS group still mixes two different future source families that do not share one honest implementation seam:
1. watched iOS Xcode host facts (`xcode.app_path`, `xcode.version`, `xcode.simulator_sdk_version`)
2. watched iOS simulator-runtime host facts (`simulator.runtime_identifier`, `simulator.runtime_name`, `simulator.device_name`)

Without another repo-owned contract split, any later implementation would either widen one PR across unrelated Apple source families or leave the checked-in manifest/docs claiming that one issue still owns all iOS source-backed promotion work.

## Scope of this slice

Narrow `#144` to the immediate repo-owned contract split only.

This slice must:
1. replace the single iOS `ios-xcode-simulator` source-rule group with two bounded iOS groups
2. bind each new iOS group to exactly one later follow-up issue
3. keep the current drift / missing-evidence alert semantics and managed issue title unchanged
4. keep the report/docs truthful that both iOS groups still remain `manual-review-required` on current `main`
5. stay testable from checked-in manifests, report output, and deterministic fixtures

This slice is **not** the later source-backed advisory implementation itself. It is the contract change that makes the later iOS source integrations bounded and auditable.

## Required implementation artifacts

### 1. Split the checked-in iOS source-rule inventory

Update:
- `.github/runner-host-advisory-sources.json`

The implementation PR must replace the current combined iOS group with exactly these bounded iOS groups:

1. `ios-xcode`
   - platforms: `ios`
   - watched fact paths:
     - `xcode.app_path`
     - `xcode.version`
     - `xcode.simulator_sdk_version`
   - follow-up issue: `#164`
   - current rule kind: `manual-review-required`
   - candidate source description: authoritative Apple Xcode release/support metadata for the installed Xcode app and bundled simulator SDK facts

2. `ios-simulator-runtime`
   - platforms: `ios`
   - watched fact paths:
     - `simulator.runtime_identifier`
     - `simulator.runtime_name`
     - `simulator.device_name`
   - follow-up issue: `#165`
   - current rule kind: `manual-review-required`
   - candidate source description: authoritative Apple simulator runtime/device availability metadata for the watched simulator facts

Contract requirements:
- `runner-images` must remain mapped to `#143`
- `android-java`, `android-gradle`, and `android-emulator-runtime` must remain mapped to `#154`, `#155`, and `#156`
- every watched fact path in `.github/runner-host-watch.json` must still be owned by exactly one source-rule group after the split
- the manifest must fail closed if any watched iOS fact path is dropped, duplicated, or assigned to the wrong follow-up issue

Explicit current-main boundary:
- this slice must **not** silently widen the watched runner-host inventory beyond the existing iOS facts on current `main`
- `runner.*` facts stay under `runner-images`; do not move them into the new iOS groups
- if the repo later wants a different ownership model for simulator device-selection/configuration facts, that must be shaped as a separate contract change rather than smuggled into this slice

### 2. Runner-host report integration

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract for this slice:
- accept the new iOS group keys and follow-up issue mappings
- emit the split iOS groups in the machine-readable summary
- render markdown that names the two iOS manual-review groups separately instead of one combined iOS umbrella group
- keep the current top-level `verdict`, `reason`, `alert`, `advisory_count`, and managed-issue behavior authoritative for this slice
- fail closed if the manifest omits one of the expected new iOS groups, points a group at the wrong follow-up issue, or leaves any watched iOS fact uncovered

Required reporting behavior:
- current clean runs must still report `no review-needed` when the baseline matches
- the new source-rule section must make it explicit that Xcode and simulator-runtime promotion are still future follow-up work
- the report must not imply that any iOS source-backed advisory evaluation is already active until `#164` or `#165` lands

### 3. Tests and fixtures

Add or extend deterministic fixtures and tests so the repo validates the new iOS split directly.

Required coverage:
- valid manifest with the two split iOS groups plus the unchanged runner-image and Android groups
- duplicate or missing iOS watched fact ownership fails closed
- wrong follow-up issue number for one split iOS group fails closed
- rendered JSON/markdown includes the new iOS group keys and keeps the same clean top-level drift verdict

The tests should cover the production checked-in manifest, not only a synthetic fixture copy.

### 4. Canonical docs and older issue-spec updates

The implementation PR for this spec must update these docs:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`
- `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`
- `docs/specs/issues/issue-124-runner-host-drift-watch.md`

Those docs updates must explicitly say:
- the shipped runner-host automation still evaluates drift / missing evidence only
- the iOS backlog is no longer one combined `ios-xcode-simulator` umbrella after this slice
- later source-backed iOS promotion is split across `#164` and `#165`
- those later iOS slices must continue to reuse the existing `security: runner-host review needed` lane rather than inventing parallel managed issue titles
- the current runner-image and Android follow-up ownership remains unchanged

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` no longer uses `#144` as the owner of one combined iOS source group; it instead exposes two bounded iOS groups mapped to `#164` and `#165`.
2. Every watched fact path in `.github/runner-host-watch.json` remains covered exactly once after the split.
3. `runner_host_review_report.py` still reports the same honest top-level drift result for current clean `main`, while exposing the split iOS groups in JSON and markdown.
4. The canonical security docs and older issue-spec docs stop describing `#144` as the remaining umbrella iOS follow-up and instead point at `#164` and `#165`.
5. The implementation PR for this slice can honestly say `Closes #144` because it finishes the immediate repo-owned contract split, while the actual Xcode/runtime source-backed integrations remain in follow-up issues.

## Bounded design decisions

### In scope for the implementation PR
- one bounded manifest split in `.github/runner-host-advisory-sources.json`
- one bounded update to `runner_host_review_report.py`
- one focused test/fixture update that proves coverage stays fail-closed
- bounded docs/spec updates in the five named files above

### Explicit non-goals
- **no** live external advisory queries in this slice
- **no** source-backed promotion logic for iOS Xcode (`#164`)
- **no** source-backed promotion logic for iOS simulator runtime (`#165`)
- **no** change to the existing runner-host managed issue title or drift-alert semantics
- **no** widening of `.github/runner-host-watch.json`
- **no** changes to the runner-image (`#143`) or Android (`#154`, `#155`, `#156`) source-backed follow-ups beyond keeping their ownership references honest

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
    'ios-xcode',
    'ios-simulator-runtime',
}, summary
issue_map = {group['key']: group['follow_up_issue'] for group in summary['source_rule_groups']}
assert issue_map['ios-xcode'] == 164, issue_map
assert issue_map['ios-simulator-runtime'] == 165, issue_map
print('runner-host iOS source split summary present')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#144` because it finishes the immediate repo-owned iOS source-rule split.

After that PR merges:
- `#164` remains the bounded follow-up for iOS Xcode host fact source-backed promotion
- `#165` remains the bounded follow-up for iOS simulator-runtime host fact source-backed promotion
- the shipped runner-host lane on `main` still remains drift-triggered review until one of those later iOS follow-up issues lands
