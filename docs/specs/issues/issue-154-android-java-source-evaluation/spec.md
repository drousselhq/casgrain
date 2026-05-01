# Issue #154 — Evaluate source-backed advisory automation for Android Java host version facts

- Issue: `#154`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #154`
- Upstream slices already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
  - `#142` (`Split Android runner-host advisory source rules into bounded follow-up slices`)
- Related follow-up issues that must remain separate from this slice:
  - `#155` (`android-gradle`)
  - `#156` (`android-emulator-runtime`)
  - `#164` / `#165` (`later iOS ownership for the current combined ios-xcode-simulator placeholder on main`)
  - `#164` (`later ios-xcode source-backed follow-up once the iOS split lands`)
  - `#165` (`later ios-simulator-runtime source-backed follow-up once the iOS split lands`)

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #158 split the Android runner-host backlog into bounded `android-java`, `android-gradle`, and `android-emulator-runtime` groups.
- PR #174 already promoted `runner-images` to the active `runner-image-release-metadata` rule on current `main`.
- A fresh live invocation (`2026-04-23` UTC) against current `main` reports:
  - `verdict=manual-review-required`
  - `reason=runner-images-source-drift`
  - issue title `security: runner-host review needed`
  - source-rule groups `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, `ios-xcode-simulator`
  - `runner-images` now evaluates as `runner-image-release-metadata`, `android-java` now evaluates as `java-release-support`, `android-gradle` now evaluates as `gradle-release-catalog`, `android-emulator-runtime` now evaluates as `android-system-image-catalog`, and the current combined `ios-xcode-simulator` placeholder stays manual-only while later iOS ownership lives in `#164` / `#165`
- `docs/specs/issues/issue-144-ios-runner-host-source-split/{spec,tasks}.md` already describe a later iOS split into `#164` and `#165`, and current `main` now keeps the combined `ios-xcode-simulator` placeholder while treating `#164` / `#165` as the truthful later owners rather than reviving closed issue `#144`.
- `tests/test-support/scripts/runner_host_review_report.py` now carries the active Android Java source-backed rule on this branch; before this slice it only had the placeholder/manual entry, and the watched Java facts still stay bounded to `java.configured_major` plus `java.resolved_version`.
- `.github/runner-host-watch.json` watches only these Android Java facts on current `main`:
  - `java.configured_major`
  - `java.resolved_version`
- `host-environment.json` still emits `java.distribution`, but that fact is not part of the checked-in watched inventory.

That means the honest remaining gap is now narrow: add trustworthy source-backed evaluation for the already-watched Android Java facts without widening the runner-host inventory, without reopening the delivered `runner-images` or `android-emulator-runtime` slices or widening the unchanged iOS placeholder on current `main`, and without inventing a parallel report flow.

## Scope of this slice

Add source-backed Android Java evaluation to the existing runner-host watch.

This slice must:
1. promote only `android-java` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate only the watched Android Java facts (`java.configured_major` and `java.resolved_version`) using authoritative machine-readable Java release/support metadata
3. surface actionable Java findings through the existing report `security: runner-host review needed`
4. preserve the current drift / missing-evidence behavior, keep the delivered `runner-images` rule intact, and leave the remaining non-Java follow-up groups otherwise unchanged

## Required implementation artifacts

### 1. Android Java source-rule contract

Update:
- `.github/runner-host-advisory-sources.json`

Contract:
- keep the `android-java` group key, `follow_up_issue: 154`, surface name, and watched fact paths unchanged
- change only the `android-java` rule kind from `manual-review-required` to a stable active kind: `java-release-support`
- add the rule-specific source metadata needed to evaluate the watched Java facts and to render the human-facing source description in report output
- preserve `runner-images` as the delivered `runner-image-release-metadata` group
- preserve `android-gradle` as the delivered `gradle-release-catalog` group mapped to `#155`, treat `android-emulator-runtime` as an already-delivered source-backed slice under `#156`, and leave the current combined `ios-xcode-simulator` placeholder manual-only while later iOS ownership stays with `#164` / `#165`
- do **not** add `java.distribution` or any other new Android watched fact to `.github/runner-host-watch.json`

### 2. Runner-host source evaluation and report plumbing

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- normalize the new `java-release-support` rule kind and validate its required source metadata
- fetch or otherwise load authoritative machine-readable Java release/support data during live runs, while keeping deterministic fixture-driven coverage for tests instead of relying on live network calls in unit tests
- evaluate `java.configured_major` and `java.resolved_version` only
- produce explicit Android Java source findings when any of the following is true:
  - the configured major is outside the authoritative supported release set
  - the resolved version cannot be matched to authoritative metadata for that configured major
  - the authoritative Java source response is unavailable, malformed, or contradictory for the Java slice
- keep the current drift / missing-evidence evaluation for watched facts authoritative and unchanged for both platforms
- preserve the existing meaning of top-level `advisory_count` on current `main`: it is the total number of review-needed baseline drift / missing-evidence facts plus any review-needed source-backed findings already counted by delivered source-backed groups
- make Android Java source findings contribute to that same top-level `advisory_count` instead of inventing a separate top-level field
- set top-level `alert` / `verdict` to review-needed when either:
  - drift / missing evidence requires review, or
  - Android Java source findings require review
- keep top-level reason precedence truthful:
  - `baseline-match` when there is no drift and no Android Java source finding
  - existing drift reasons keep winning when drift or missing evidence exists
  - use a dedicated source-backed reason (for example `source-review-needed`) when drift count is zero but Android Java source findings require review
- render markdown that clearly distinguishes Android Java source-backed findings from drift / missing-evidence findings and states that `runner-images`, `android-gradle`, and `android-emulator-runtime` are already delivered source-backed groups while the current combined iOS placeholder remains follow-up work
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed Android Java findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/java-source/`

Required coverage:
- supported/current Android Java source payload + baseline-match host facts → `alert=false`, `advisory_count=0`, and `android-java` is reported as `java-release-support`
- unsupported or unrecognized Android Java version → `alert=true` with a source-backed review-needed reason and a non-zero top-level `advisory_count` even when the underlying watched-fact drift count remains zero
- authoritative-source payload unavailable or malformed → explicit review-needed Android Java source finding instead of silent success
- existing drift and missing-evidence fixtures still preserve their current overall `advisory_count` behavior on current `main`
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` itself exercises the active `android-java` rule while `runner-images`, `android-gradle`, and `android-emulator-runtime` stay delivered and the remaining follow-up groups stay unchanged

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

Those updates must explicitly say:
- current `main` already performs source-backed evaluation for `runner-images`, and after this slice it performs source-backed evaluation for `android-java` too
- `android-gradle` is already source-backed on current `main` while `android-emulator-runtime` is already source-backed on current `main`
- the current combined `ios-xcode-simulator` placeholder group stays `manual-review-required` on current `main`, while later live iOS ownership already sits with `#164` / `#165`; this slice does not widen that placeholder
- actionable Android Java findings continue to reuse `security: runner-host review needed`
- `java.distribution` remains outside the watched runner-host inventory unless a later contract change adds it explicitly
- the older issue-spec artifacts are historical and must not keep claiming that current `main` still has no source-backed runner-host evaluation at all
- `docs/specs/issues/issue-124-runner-host-drift-watch.md` must stop saying that current `main` still has delivered only `#143` while `#154`, `#155`, `#156`, and `#144` all remain later follow-ups; after this slice lands it must treat `#154` as delivered while keeping the unchanged combined iOS placeholder truthful
- `docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md` and `docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md` must be reconciled as historical artifacts so they no longer claim that only `runner-images` is source-backed after `#154` lands
- `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md` must stop saying that the shipped runner-host automation still evaluates only drift / missing evidence; after `#154` lands it must describe `runner-images`, `android-gradle`, `android-emulator-runtime`, and `android-java` as the already-delivered source-backed exceptions while keeping the current combined iOS placeholder truthful under later ownership `#164` / `#165`
- `docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md` must stop telling implementers to expect split current-main iOS keys; until a later iOS split ships, that historical task artifact must preserve the live combined `ios-xcode-simulator` placeholder while pointing later ownership at `#164` / `#165`

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` exposes `android-java` as `java-release-support` while preserving its watched fact paths and `follow_up_issue: 154`.
2. A supported/baseline-match Android Java evaluation still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no Java source findings requiring review.
3. Unsupported, unrecognized, or source-unavailable Android Java evaluation produces an explicit source-backed finding for `android-java`, increments the same top-level `advisory_count` current `main` already uses for source-backed findings, and turns the overall runner-host summary/report path into `manual-review-required`.
4. Missing Android host evidence preserves the existing top-level `reason=missing-evidence` / watched-fact advisory path and leaves `android-java` present as `rule_kind=java-release-support` with `outcome=source-skipped` instead of adding a second Java-only top-level advisory.
5. The rendered JSON and markdown distinguish Android Java source-backed findings from drift / missing-evidence findings, preserve `runner-images`, `android-gradle`, and `android-emulator-runtime` as delivered source-backed groups, and leave only the current combined iOS placeholder as the unchanged follow-up entry.
6. The named canonical docs and older main-branch issue specs/tasks, including `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/{spec,tasks}.md`, and `docs/specs/issues/issue-144-ios-runner-host-source-split/{spec,tasks}.md`, no longer claim that only drift / missing-evidence checks or only `runner-images` are source-backed on current `main`, no longer preserve stale `android-emulator-runtime` manual-only wording, no longer present `#154` as a later follow-up once this slice lands, and still keep the unchanged combined `ios-xcode-simulator` placeholder truthful on current `main` under later ownership `#164` / `#165`.
7. The implementation PR for this slice can honestly say `Closes #154` because the Android Java source-backed evaluation becomes active on `main`.

## Explicit non-goals

- **no** further behavior or ownership changes to the delivered `runner-images` slice (`#143`)
- **no** further behavior or ownership changes to the delivered `android-gradle` slice (`#155`)
- **no** further behavior or ownership changes to the delivered `android-emulator-runtime` slice (`#156`)
- **no** iOS source-rule split rework or source-backed evaluation; the current combined `ios-xcode-simulator` placeholder stays unchanged in this slice while later ownership remains `#164` / `#165`
- **no** widening of `.github/runner-host-watch.json` to include `java.distribution` or any new Java fact
- **no** new report title or parallel runner-host GitHub issue lane
- **no** generic Java patch-freshness ratchet or vendor-distribution policy beyond the bounded release/support contract for `java.configured_major` and `java.resolved_version`
- **no** broad external CVE or release-note scraping outside the chosen authoritative Java release/support metadata

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

Because the live runner-host summary can still surface unrelated drift or missing-evidence alerts on current `main`, the slice-specific check should prove that `android-java` is active on the shared runner-host summary contract rather than forcing a globally clean `advisory_count == 0` render.

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
android = next(group for group in summary['source_rule_groups'] if group['key'] == 'android-java')
assert android['rule_kind'] == 'java-release-support', android
assert android['follow_up_issue'] == 154, android
assert android['status'] in {'no review-needed', 'manual-review-required'}, android
assert android['outcome'] in {'source-match', 'source-skipped', 'source-review-needed', 'source-error'}, android
assert 'source_advisory_count' not in summary, summary
print('android-java source-backed rule is active on the shared runner-host summary contract')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#154` because it turns the checked-in `android-java` placeholder into an active source-backed evaluation on current `main`.

After that PR merges:
- Android Java facts are evaluated from authoritative machine-readable release/support data through the existing runner-host watch
- `runner-images` remains a delivered source-backed group on current `main`
- `android-gradle` is already delivered as a source-backed group, while `android-emulator-runtime` is also already delivered as a source-backed group
- the current combined `ios-xcode-simulator` placeholder remains manual-only and later iOS ownership stays with `#164` / `#165`
- any future work on Java distribution policy, patch-freshness ratchets, or broader Java-source semantics must land as a new bounded follow-up issue instead of being smuggled into `#154`
