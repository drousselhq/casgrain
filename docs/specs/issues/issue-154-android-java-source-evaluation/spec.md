# Issue #154 — Evaluate source-backed advisory automation for Android Java host version facts

- Issue: `#154`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #154`
- Upstream slices already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
  - `#142` (`Split Android runner-host advisory source rules into bounded follow-up slices`)
- Related follow-up issues that must remain separate from this slice:
  - `#143` (`runner-images`)
  - `#155` (`android-gradle`)
  - `#156` (`android-emulator-runtime`)
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
  - every current source-rule group, including `android-java`, remains `manual-review-required`
- `tests/test-support/scripts/runner_host_review_report.py` currently accepts only `manual-review-required` source-rule kinds, so current `main` cannot yet express or evaluate an active Android Java source-backed rule.
- `.github/runner-host-watch.json` watches only these Android Java facts on current `main`:
  - `java.configured_major`
  - `java.resolved_version`
- `host-environment.json` still emits `java.distribution`, but that fact is not part of the checked-in watched inventory.

That means the honest remaining gap is now narrow: add trustworthy source-backed evaluation for the already-watched Android Java facts without widening the runner-host inventory, without touching the Gradle/emulator/iOS follow-ups, and without inventing a parallel managed-issue flow.

## Scope of this slice

Add source-backed Android Java evaluation to the existing runner-host watch.

This slice must:
1. promote only `android-java` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate only the watched Android Java facts (`java.configured_major` and `java.resolved_version`) using authoritative machine-readable Java release/support metadata
3. surface actionable Java findings through the existing managed issue `security: runner-host review needed`
4. preserve the current drift / missing-evidence behavior for the existing watched facts and keep every non-Java runner-host group `manual-review-required`

## Required implementation artifacts

### 1. Android Java source-rule contract

Update:
- `.github/runner-host-advisory-sources.json`

Contract:
- keep the `android-java` group key, `follow_up_issue: 154`, surface name, and watched fact paths unchanged
- change only the `android-java` rule kind from `manual-review-required` to a stable active kind: `java-release-support`
- add the rule-specific source metadata needed to evaluate the watched Java facts and to render the human-facing source description in report output
- preserve `runner-images`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator` as `manual-review-required` groups mapped to their existing follow-up issues
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
- preserve the existing meaning of top-level `advisory_count`: it remains the count of changed or missing watched facts from the baseline contract
- add a separate source-backed finding count/list (for example `source_advisory_count` plus detailed source findings) instead of overloading the drift counter
- set top-level `alert` / `verdict` to review-needed when either:
  - drift / missing evidence requires review, or
  - Android Java source findings require review
- keep top-level reason precedence truthful:
  - `baseline-match` when there is no drift and no Android Java source finding
  - existing drift reasons keep winning when drift or missing evidence exists
  - use a dedicated source-backed reason (for example `source-review-needed`) when drift count is zero but Android Java source findings require review
- render markdown that clearly distinguishes Android Java source-backed findings from drift / missing-evidence findings and states that the non-Java runner-host groups still remain `manual-review-required` follow-ups
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed Android Java findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/java-source/`

Required coverage:
- supported/current Android Java source payload + baseline-match host facts → `alert=false`, `advisory_count=0`, `source_advisory_count=0`, and `android-java` is reported as `java-release-support`
- unsupported or unrecognized Android Java version → `alert=true` with a source-backed review-needed reason while the drift counter remains zero
- authoritative-source payload unavailable or malformed → explicit review-needed Android Java source finding instead of silent success
- existing drift and missing-evidence fixtures still preserve their current `advisory_count` behavior
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` itself exercises the active `android-java` rule while the non-Java groups stay manual-only

### 4. Canonical docs and live-contract reconciliation

Update:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`
- `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`
- `docs/specs/issues/issue-142-android-runner-host-source-split.md`

Those updates must explicitly say:
- current `main` now performs source-backed evaluation for `android-java` only
- `runner-images`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator` still remain `manual-review-required` follow-up groups
- actionable Android Java findings continue to reuse `security: runner-host review needed`
- `java.distribution` remains outside the watched runner-host inventory unless a later contract change adds it explicitly
- the older issue-spec artifacts are historical and must not keep claiming that current `main` still has no source-backed runner-host evaluation at all

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` exposes `android-java` as `java-release-support` while preserving its watched fact paths and `follow_up_issue: 154`.
2. A supported/baseline-match Android Java evaluation still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no Java source findings requiring review.
3. Unsupported, unrecognized, or source-unavailable Android Java evaluation produces an explicit source-backed finding for `android-java` and turns the overall runner-host summary/managed-issue path into `manual-review-required` without pretending the drift counter increased.
4. The rendered JSON and markdown distinguish Android Java source-backed findings from drift / missing-evidence findings and leave the non-Java runner-host groups as `manual-review-required` follow-ups.
5. The named canonical docs and older main-branch issue specs no longer claim that current runner-host automation is drift-only for every source group.
6. The implementation PR for this slice can honestly say `Closes #154` because the Android Java source-backed evaluation becomes active on `main`.

## Explicit non-goals

- **no** source-backed evaluation for `runner-images` (`#143`)
- **no** source-backed evaluation for `android-gradle` (`#155`)
- **no** source-backed evaluation for `android-emulator-runtime` (`#156`)
- **no** source-backed evaluation for `ios-xcode-simulator` (`#144`)
- **no** widening of `.github/runner-host-watch.json` to include `java.distribution` or any new Java fact
- **no** new managed issue title or parallel runner-host issue-sync lane
- **no** generic Java patch-freshness ratchet or vendor-distribution policy beyond the bounded release/support contract for `java.configured_major` and `java.resolved_version`
- **no** broad external CVE or release-note scraping outside the chosen authoritative Java release/support metadata

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
android = next(group for group in summary['source_rule_groups'] if group['key'] == 'android-java')
assert android['rule_kind'] == 'java-release-support', android
assert android['follow_up_issue'] == 154, android
assert 'source_advisory_count' in summary, summary
print('android-java source-backed rule is present in the runner-host summary')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#154` because it turns the checked-in `android-java` placeholder into an active source-backed evaluation on current `main`.

After that PR merges:
- Android Java facts are evaluated from authoritative machine-readable release/support data through the existing runner-host watch
- `runner-images`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator` remain separate manual-review follow-ups
- any future work on Java distribution policy, patch-freshness ratchets, or broader Java-source semantics must land as a new bounded follow-up issue instead of being smuggled into `#154`
