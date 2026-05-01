# Issue #155 — Implementation tasks

- Linked issue: `#155`
- Source contract: `./spec.md`

## 1. Add failing regression coverage for Android Gradle source-backed evaluation
- [x] 1.1 Add deterministic Gradle source payload fixtures under `tests/test-support/fixtures/runner-host-watch/gradle-source/` for a recognized non-broken release, a broken or unrecognized release, a newer-release-available-but-non-alerting case, and an unavailable/malformed source response.
- [x] 1.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `android-gradle` remains `manual-review-required` instead of an active source-backed rule.
- [x] 1.3 Prove the new assertions distinguish Android Gradle source-backed findings from baseline drift / missing-evidence findings without inventing a new top-level `source_advisory_count` field.
- [x] 1.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing Android Gradle source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `android-gradle` as an active source-backed rule with deterministic coverage for recognized, broken/unrecognized, newer-release-only, and source-unavailable cases.

## 2. Promote the checked-in `android-gradle` source rule from placeholder to active contract
- [x] 2.1 Update `.github/runner-host-advisory-sources.json` so `android-gradle` uses `rule_kind: gradle-release-catalog`.
- [x] 2.2 Add only the rule-specific source metadata needed for the Gradle release-catalog evaluator while preserving `follow_up_issue: 155` and the existing watched fact paths.
- [x] 2.3 Keep `runner-images` on its existing `runner-image-release-metadata` contract, keep `android-java` on its existing separate source-backed path, keep the current combined `ios-xcode-simulator` placeholder as the remaining `manual-review-required` follow-up group, and treat `android-emulator-runtime` as already source-backed on current `main` while any `#164` / `#165` references remain historical only.
- [x] 2.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` to include Android Gradle plugin versions, wrapper checksums, dependency manifests, or any other new Gradle fact.
- Goal: Make the repo-owned manifest describe one bounded active Gradle source rule without reopening the other runner-host follow-up scopes.
- Validation:

```bash
python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('.github/runner-host-advisory-sources.json').read_text(encoding='utf-8'))
groups = {group['key']: group for group in manifest['groups']}
assert groups['runner-images']['rule_kind'] == 'runner-image-release-metadata', groups['runner-images']
assert groups['android-gradle']['rule_kind'] == 'gradle-release-catalog', groups['android-gradle']
assert groups['android-java']['rule_kind'] == 'java-release-support', groups['android-java']
assert groups['android-emulator-runtime']['rule_kind'] == 'android-system-image-catalog', groups['android-emulator-runtime']
assert groups['ios-xcode-simulator']['rule_kind'] == 'manual-review-required', groups['ios-xcode-simulator']
print('android-gradle is promoted while the remaining iOS follow-up group stays unchanged at this checkpoint')
PY
```
- Non-goals: No Java/emulator/iOS/runner-image source activation, no new report title.
- Hand back if: The Gradle slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the already-delivered `runner-images` / `android-java` / `android-emulator-runtime` contracts or the remaining manual-only iOS follow-up group.

## 3. Implement bounded Android Gradle source evaluation in `runner_host_review_report.py`
- [x] 3.1 Normalize and validate the new `gradle-release-catalog` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [x] 3.2 Load authoritative machine-readable Gradle release data for live runs while keeping deterministic fixture injection for unit tests.
- [x] 3.3 Evaluate only `gradle.configured_version` and `gradle.resolved_version`, and emit explicit review-needed findings when a watched Gradle version is unrecognized, the resolved version is marked `broken`, or the source payload is unavailable/malformed.
- [x] 3.4 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` consistent with current `main` by counting review-needed source-backed findings there too, while still making Android Gradle source findings explicit in the source-rule group details.
- [x] 3.5 Ensure a newer upstream Gradle release can be rendered as context without becoming a review-needed condition by itself on current `main`.
- [x] 3.6 Update the rendered markdown/summary so Android Gradle source findings are explicit, `runner-images` still renders as an already-delivered source-backed group, `android-emulator-runtime` stays delivered as source-backed, and the remaining follow-up groups stay truthful.
- Goal: Activate one trustworthy Gradle-only source-backed path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No Gradle plugin policy, no wrapper-integrity ratchet, no broad CVE scraping beyond the bounded release-catalog contract in `spec.md`.
- Hand back if: The bounded Gradle evaluator would require changing `host-environment.json` fields, widening the watched inventory, or redesigning the report sync path instead of staying inside the existing runner-host watch.

## 4. Reconcile the repo-owned docs and earlier issue-spec contract
- [x] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `runner-images`, `android-java`, and `android-emulator-runtime` are already source-backed, `android-gradle` becomes source-backed in this slice, and the current combined `ios-xcode-simulator` placeholder remains `manual-review-required` while any `#164` / `#165` references remain historical only.
- [x] 4.2 Reconcile `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, `docs/specs/issues/issue-142-android-runner-host-source-split.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md`, `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`, `docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md`, `docs/specs/issues/issue-154-android-java-source-evaluation/spec.md`, and `docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md` so they no longer read as if current `main` has no Android Gradle source-backed evaluation, as if only `runner-images` is source-backed or as if `android-emulator-runtime` were still an untouched future/manual-only slice, as if `#155` is still future work after this slice lands, or as if Android source-backed slices still require a drift-only `advisory_count` plus a separate `source_advisory_count`.
- [x] 4.3 Make the docs explicit that a newer Gradle release alone is informational for this slice unless the repo later adds a separate upgrade-policy contract.
- [x] 4.4 Remove the stale phrases that currently say `#155` remains future work on current `main`, including the `issue-124` line that lists `#155` among later source-specific follow-ups, the `issue-143` spec/task wording that still limits current-main source-backed status to `runner-images`, the `issue-144` spec/task wording that still frames `runner-images` as the only delivered source-backed exception or validates only that live-summary state, and the `issue-154` spec/task wording that still says `android-gradle` remains an unchanged `manual-review-required` follow-up after this slice lands or that Android source-backed findings must be split into drift-only `advisory_count` plus a separate `source_advisory_count`.
- [x] 4.5 Run a targeted search for stale wording that still claims only `runner-images` is source-backed, that every runner-host group except `runner-images` is manual-only on current `main`, that `#155` remains future work on current `main`, or that Android source-backed findings must be rendered as drift-only `advisory_count` plus a separate `source_advisory_count`.
- Goal: Leave one truthful repo-owned contract instead of a live Gradle-source-backed story colliding with older drift-only wording.
- Validation:
```bash
python3 - <<'PY'
from pathlib import Path

positive_checks = {
'docs/development/cve-watch-operations.md': ['android-gradle', 'source-backed'],
'docs/development/security-automation-plan.md': ['android-gradle', 'source-backed'],
'docs/development/security-owasp-baseline.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-124-runner-host-drift-watch.md': ['historical', 'android-gradle'],
'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': ['historical', 'android-gradle'],
'docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md': ['android-gradle', 'source-backed'],
'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md': ['android-gradle', 'source-backed'],
}
stale_checks = {
'docs/specs/issues/issue-124-runner-host-drift-watch.md': [
'remaining later source-specific automation is split across `#143` (runner images), `#154` (android java), `#155` (android gradle), `#156` (android emulator runtime), and `#144` (ios xcode / simulator runtime) after the android narrowing contract in `#142`',
],
'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': [
'the remaining runner-host groups stay explicit future work under `#154`, `#155`, `#156`, and `#144`',
'`#154`, `#155`, and `#156` remain the bounded android host-toolchain follow-ups',
],
'docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md': [
'so they state that only `runner-images` is source-backed after this slice',
],
'docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md': [
'the shipped runner-host lane on `main` now includes the delivered `runner-images` source-backed exception from `#143`, while the ios groups in this spec remain manual-review-only until their own follow-up slices land',
'`android-java` and `android-gradle` remain open follow-ups under `#154` / `#155`, while `android-emulator-runtime` is already delivered as a source-backed slice under `#156`',
],
'docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md': [
'render `tests/test-support/scripts/runner_host_review_report.py` against current `main` and assert the summary still reports `verdict=no review-needed`, `reason=baseline-match`, and source-rule keys `ios-xcode` / `ios-simulator-runtime` mapped to `#164` / `#165`.',
],
'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md': [
'`android-emulator-runtime` is already source-backed on current `main` while `android-gradle` remains the active manual-review follow-up group',
'preserve the existing meaning of top-level `advisory_count`: it remains the count of changed or missing watched facts from the baseline contract',
'add a separate source-backed finding count/list (for example `source_advisory_count` plus detailed source findings) instead of overloading the drift counter',
'supported/current android java source payload + baseline-match host facts → `alert=false`, `advisory_count=0`, `source_advisory_count=0`, and `android-java` is reported as `java-release-support`',
'unsupported or unrecognized android java version → `alert=true` with a source-backed review-needed reason while the drift counter remains zero',
'after `#154` lands it must describe `runner-images`, `android-emulator-runtime`, and `android-java` as the already-delivered source-backed exceptions while keeping the current combined iOS placeholder truthful under later ownership `#164` / `#165`',
'**no** source-backed evaluation for `android-emulator-runtime` (`#156`)',
"assert 'source_advisory_count' in summary, summary",
],
'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md': [
'keep `android-gradle` as the remaining manual-review follow-up while `android-emulator-runtime` stays already-delivered as source-backed',
"assert groups[key]['rule_kind'] == 'manual-review-required'",
'prove the new assertions distinguish source-backed findings from drift counts by keeping `advisory_count` at zero for java-only source findings',
'preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` scoped to changed/missing watched facts, with a separate source-backed finding count/list for java findings.',
],
}

for rel, needles in positive_checks.items():
    text = Path(rel).read_text(encoding='utf-8').lower()
    for needle in needles:
        assert needle in text, (rel, needle)

for rel, stale_needles in stale_checks.items():
    text = Path(rel).read_text(encoding='utf-8').lower()
    for needle in stale_needles:
        assert needle not in text, (rel, needle)

print('runner-host docs/specs reflect the android-gradle source-backed contract')
PY
```
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this Gradle-only slice cannot honestly change.

## 5. Run bounded validation and hand back with honest closure semantics
- [x] 5.1 Run `git diff --check`.
- [x] 5.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [x] 5.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [x] 5.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `android-gradle` now renders as `gradle-release-catalog`.
- [x] 5.5 In the PR summary/comment, say the implementation PR `Closes #155`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state that `runner-images`, `android-java`, and `android-emulator-runtime` stayed source-backed while only the current combined iOS placeholder remained the follow-up group.
- Goal: Leave QA with one honest picture of the Gradle-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host report behavior under test.
- Hand back if: The refreshed head still reports `android-gradle` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #155`.
