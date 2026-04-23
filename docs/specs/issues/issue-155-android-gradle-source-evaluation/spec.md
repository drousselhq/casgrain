# Issue #155 — Evaluate source-backed advisory automation for Android Gradle host version facts

- Issue: `#155`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #155`
- Upstream slices already landed on `main`:
  - `#129` (`Runner-host advisory source-rule contract`)
  - `#142` (`Split Android runner-host advisory source rules into bounded follow-up slices`)
- Related follow-up issues that must remain separate from this slice:
  - `#143` (`runner-images`)
  - `#154` (`android-java`)
  - `#156` (`android-emulator-runtime`)
  - `#144` (`ios-xcode-simulator`)

## Why this slice exists

Already delivered on `main`:
- PR #145 added the repo-owned runner-host source-rule contract at `.github/runner-host-advisory-sources.json`.
- PR #158 split the Android runner-host backlog into bounded `android-java`, `android-gradle`, and `android-emulator-runtime` groups.
- A fresh live invocation at analyst repair (`2026-04-23` UTC) against current `main` reports:
  - `verdict=manual-review-required`
  - `reason=runner-images-source-drift`
  - `advisory_count=2`
  - source-rule groups `runner-images`, `android-java`, `android-gradle`, `android-emulator-runtime`, `ios-xcode-simulator`
  - `runner-images` already renders as the delivered source-backed `runner-image-release-metadata` group
  - `android-java`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator` still remain `manual-review-required`
- `tests/test-support/scripts/runner_host_review_report.py` already supports an active promoted rule for `runner-images`, but current `main` still lacks any active Android Gradle source-backed rule.
- `.github/runner-host-watch.json` watches only these Android Gradle facts on current `main`:
  - `gradle.configured_version`
  - `gradle.resolved_version`
- Fresh source inspection during analyst shaping confirmed `https://services.gradle.org/versions/all` exposes machine-readable Gradle release metadata including `version`, `current`, and `broken`, and the current baseline `8.7` appears in that catalog.

That means the honest remaining gap is now narrow: add trustworthy source-backed evaluation for the already-watched Android Gradle facts without widening the runner-host inventory, without touching the Java/emulator/iOS follow-ups, and without inventing a parallel managed-issue flow.

## Scope of this slice

Add source-backed Android Gradle evaluation to the existing runner-host watch.

This slice must:
1. promote only `android-gradle` from a placeholder/manual source-rule entry to an active source-backed evaluation rule
2. evaluate only the watched Android Gradle facts (`gradle.configured_version` and `gradle.resolved_version`) against authoritative machine-readable Gradle release metadata
3. surface actionable Gradle findings through the existing managed issue `security: runner-host review needed`
4. preserve the current drift / missing-evidence behavior for the existing watched facts while keeping `runner-images` on its already-delivered `runner-image-release-metadata` path and the remaining follow-up groups unchanged

## Required implementation artifacts

### 1. Android Gradle source-rule contract

Update:
- `.github/runner-host-advisory-sources.json`

Contract:
- keep the `android-gradle` group key, `follow_up_issue: 155`, surface name, and watched fact paths unchanged
- change only the `android-gradle` rule kind from `manual-review-required` to a stable active kind: `gradle-release-catalog`
- add the rule-specific source metadata needed to validate the official Gradle release catalog and to render the human-facing source description in report output
- preserve `runner-images` as the existing `runner-image-release-metadata` group mapped to `#143`, and preserve `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` as `manual-review-required` groups mapped to their existing follow-up issues
- do **not** add Android Gradle plugin versions, wrapper checksums, dependency-graph surfaces, or any other new watched fact to `.github/runner-host-watch.json`

### 2. Runner-host source evaluation and report plumbing

Update:
- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract:
- normalize the new `gradle-release-catalog` rule kind and validate its required source metadata
- fetch or otherwise load authoritative machine-readable Gradle release data during live runs, while keeping deterministic fixture-driven coverage for tests instead of relying on live network calls in unit tests
- evaluate `gradle.configured_version` and `gradle.resolved_version` only
- treat only stable catalog entries as actionable release data for this slice; do not promote nightlies, release-nightlies, snapshots, milestones, or RCs into the steady-state Android smoke contract
- produce explicit Android Gradle source findings when any of the following is true:
  - the configured version is absent from the authoritative stable release catalog
  - the resolved version is absent from the authoritative stable release catalog
  - the authoritative catalog marks the resolved version as `broken`
  - the authoritative Gradle source response is unavailable, malformed, or contradictory for the Gradle slice
- keep the current drift / missing-evidence evaluation for watched facts authoritative and unchanged for both platforms
- preserve the existing meaning of top-level `advisory_count` on current `main`: it is the total number of review-needed baseline drift / missing-evidence facts plus any review-needed source-backed findings already counted by the runner-images evaluator
- make Android Gradle source findings contribute to that same top-level `advisory_count` instead of inventing a new top-level `source_advisory_count` field
- keep Android Gradle source findings explicitly inspectable in the rendered summary / markdown through the source-rule group status, outcome, and platform-result details rather than by forcing QA or later automation to infer them from the top-level count alone
- set top-level `alert` / `verdict` to review-needed when either:
  - drift / missing evidence requires review, or
  - Android Gradle source findings require review
- keep top-level reason precedence truthful:
  - `baseline-match` when there is no drift and no Android Gradle source finding
  - existing drift reasons keep winning when drift or missing evidence exists
  - use a dedicated source-backed reason (for example `source-review-needed`) when drift count is zero but Android Gradle source findings require review
- render markdown that clearly distinguishes Android Gradle source-backed findings from drift / missing-evidence findings and states that `runner-images` remains the already-delivered source-backed exception while `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` stay follow-up groups
- do **not** auto-alert solely because a newer Gradle release exists; until the repo defines a separate upgrade policy, newer upstream releases may be rendered as informational context but must not by themselves open or reopen the runner-host review lane on current `main`
- fail closed on checked-in manifest/schema violations, but degrade authoritative-source retrieval/normalization failures into explicit review-needed Android Gradle findings rather than a silent pass

### 3. Deterministic fixtures and tests

Update:
- `tests/scripts/test_runner_host_review_report.py`
- `tests/test-support/fixtures/runner-host-watch/gradle-source/`

Required coverage:
- supported/current Android Gradle source payload + baseline-match host facts → `alert=false`, `advisory_count=0`, and `android-gradle` is reported as `gradle-release-catalog`
- broken or unrecognized Android Gradle version → `alert=true` with a source-backed review-needed reason and a non-zero top-level `advisory_count` even when the baseline drift count is zero
- authoritative-source payload unavailable or malformed → explicit review-needed Android Gradle source finding instead of silent success
- a newer upstream Gradle release exists while the configured/resolved version is still a recognized non-broken stable release → no automatic alert from the Gradle source path alone
- existing drift and missing-evidence fixtures still preserve their current `advisory_count` behavior while source-backed findings continue to roll into that same top-level count on current `main`
- a checked-in manifest regression proves `.github/runner-host-advisory-sources.json` itself exercises the active `android-gradle` rule while preserving `runner-images` as `runner-image-release-metadata` and the remaining groups as manual-only follow-ups

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
- `docs/specs/issues/issue-154-android-java-source-evaluation/spec.md`
- `docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md`

Those updates must explicitly say:
- `runner-images`, `android-gradle`, `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` are now the named current-main contract surface groups; after this slice lands, `runner-images` and `android-gradle` are source-backed while `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` remain `manual-review-required` follow-up groups until their own slices land
- actionable Android Gradle findings continue to reuse `security: runner-host review needed`
- a newer upstream Gradle release alone is not yet a review-needed condition on current `main`; this slice is bounded to recognized/broken/source-unavailable release-catalog evaluation
- `docs/specs/issues/issue-124-runner-host-drift-watch.md` must stop presenting `#155` as a still-open later follow-up on current `main` after this slice lands
- `docs/specs/issues/issue-143-runner-image-source-evaluation/{spec,tasks}.md` must stop saying the remaining future-work set still includes `#155` or that only `runner-images` is source-backed after this slice lands; after this slice lands, only `#154`, `#156`, and `#144` remain future source-backed follow-ups
- `docs/specs/issues/issue-154-android-java-source-evaluation/{spec,tasks}.md` must stop preserving `android-gradle` as an unchanged `manual-review-required` follow-up or validating it as such after this slice lands; those artifacts must instead treat `android-gradle` as an already-delivered source-backed group while keeping the Java slice itself open under `#154`
- the older issue-spec artifacts are historical or adjacent-current backlog contracts and must not keep claiming that current `main` has no Android Gradle source-backed runner-host evaluation after this slice lands

## Acceptance criteria

1. `.github/runner-host-advisory-sources.json` exposes `android-gradle` as `gradle-release-catalog` while preserving its watched fact paths and `follow_up_issue: 155`.
2. A recognized non-broken baseline-match Android Gradle evaluation still produces top-level `verdict=no review-needed`, `reason=baseline-match`, `advisory_count=0`, and no Gradle source findings requiring review.
3. Broken, unrecognized, or source-unavailable Android Gradle evaluation produces an explicit source-backed finding for `android-gradle`, turns the overall runner-host summary/managed-issue path into `manual-review-required`, and increments the same top-level `advisory_count` field current `main` already uses for source-backed findings.
4. The rendered JSON and markdown distinguish Android Gradle source-backed findings from drift / missing-evidence findings through explicit source-rule group details, preserve `runner-images` as the existing source-backed group, leave `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` as `manual-review-required` follow-ups, and do not auto-alert merely because a newer upstream Gradle release exists.
5. The named canonical docs and older main-branch issue specs/tasks (`#124`, `#129`, `#142`, `issue-143/{spec,tasks}.md`, and `issue-154/{spec,tasks}.md`) no longer claim that current runner-host automation is drift-only for every source group, that only `runner-images` is source-backed, or that `#155` remains future work on current `main` after this slice lands.
6. The implementation PR for this slice can honestly say `Closes #155` because the Android Gradle source-backed evaluation becomes active on `main`.

## Explicit non-goals

- **no** new runner-images promotion or contract changes beyond preserving the existing `runner-image-release-metadata` path from `#143`
- **no** source-backed evaluation for `android-java` (`#154`)
- **no** source-backed evaluation for `android-emulator-runtime` (`#156`)
- **no** source-backed evaluation for `ios-xcode-simulator` (`#144`)
- **no** widening of `.github/runner-host-watch.json` to include Android Gradle plugin versions, wrapper checksums, dependency manifests, or any new Gradle fact
- **no** automatic upgrade policy or freshness ratchet solely because a newer Gradle release exists
- **no** new managed issue title or parallel runner-host issue-sync lane
- **no** broad CVE or release-note scraping beyond the chosen Gradle release catalog contract

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
android = next(group for group in summary['source_rule_groups'] if group['key'] == 'android-gradle')
assert android['rule_kind'] == 'gradle-release-catalog', android
assert android['follow_up_issue'] == 155, android
assert 'source_rule_groups' in summary, summary
print('android-gradle source-backed rule is present in the runner-host summary')
PY
```

## Completion boundary

The implementation PR for this spec should be able to close `#155` because it turns the checked-in `android-gradle` placeholder into an active source-backed evaluation on current `main`.

After that PR merges:
- Android Gradle facts are evaluated from authoritative machine-readable release metadata through the existing runner-host watch
- `runner-images` remains on its existing source-backed path, while `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` remain separate manual-review follow-ups
- any future Gradle upgrade-policy, wrapper-integrity, or dependency-surface expansion must land as a new bounded follow-up issue instead of being smuggled into `#155`
