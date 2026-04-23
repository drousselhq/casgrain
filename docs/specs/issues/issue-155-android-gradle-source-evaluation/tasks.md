# Issue #155 — Implementation tasks

- Linked issue: `#155`
- Source contract: `./spec.md`

## 1. Add failing regression coverage for Android Gradle source-backed evaluation
- [ ] 1.1 Add deterministic Gradle source payload fixtures under `tests/test-support/fixtures/runner-host-watch/gradle-source/` for a recognized non-broken release, a broken or unrecognized release, a newer-release-available-but-non-alerting case, and an unavailable/malformed source response.
- [ ] 1.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `android-gradle` remains `manual-review-required` instead of an active source-backed rule.
- [ ] 1.3 Prove the new assertions distinguish source-backed findings from drift counts by keeping `advisory_count` at zero for Gradle-only source findings.
- [ ] 1.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing Android Gradle source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `android-gradle` as an active source-backed rule with deterministic coverage for recognized, broken/unrecognized, newer-release-only, and source-unavailable cases.

## 2. Promote the checked-in `android-gradle` source rule from placeholder to active contract
- [ ] 2.1 Update `.github/runner-host-advisory-sources.json` so `android-gradle` uses `rule_kind: gradle-release-catalog`.
- [ ] 2.2 Add only the rule-specific source metadata needed for the Gradle release-catalog evaluator while preserving `follow_up_issue: 155` and the existing watched fact paths.
- [ ] 2.3 Keep `runner-images`, `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` as `manual-review-required` follow-up groups.
- [ ] 2.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` to include Android Gradle plugin versions, wrapper checksums, dependency manifests, or any other new Gradle fact.
- Goal: Make the repo-owned manifest describe one bounded active Gradle source rule without reopening the other runner-host follow-up scopes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No Java/emulator/iOS/runner-image source activation, no new managed issue title.
- Hand back if: The Gradle slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the non-Gradle groups too.

## 3. Implement bounded Android Gradle source evaluation in `runner_host_review_report.py`
- [ ] 3.1 Normalize and validate the new `gradle-release-catalog` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [ ] 3.2 Load authoritative machine-readable Gradle release data for live runs while keeping deterministic fixture injection for unit tests.
- [ ] 3.3 Evaluate only `gradle.configured_version` and `gradle.resolved_version`, and emit explicit review-needed findings when a watched Gradle version is unrecognized, the resolved version is marked `broken`, or the source payload is unavailable/malformed.
- [ ] 3.4 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` scoped to changed/missing watched facts, with a separate source-backed finding count/list for Gradle findings.
- [ ] 3.5 Ensure a newer upstream Gradle release can be rendered as context without becoming a review-needed condition by itself on current `main`.
- [ ] 3.6 Update the rendered markdown/summary so Android Gradle source findings are explicit and the non-Gradle groups still show as `manual-review-required` follow-ups.
- Goal: Activate one trustworthy Gradle-only source-backed path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No Gradle plugin policy, no wrapper-integrity ratchet, no broad CVE scraping beyond the bounded release-catalog contract in `spec.md`.
- Hand back if: The bounded Gradle evaluator would require changing `host-environment.json` fields, widening the watched inventory, or redesigning the managed-issue sync path instead of staying inside the existing runner-host watch.

## 4. Reconcile the repo-owned docs and earlier issue-spec contract
- [ ] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `android-gradle` is now source-backed while `android-java`, `android-emulator-runtime`, and `ios-xcode-simulator` remain `manual-review-required`.
- [ ] 4.2 Reconcile `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, `docs/specs/issues/issue-142-android-runner-host-source-split.md`, and `docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md` so they no longer read as if current `main` has no Android Gradle source-backed evaluation or as if `#155` is still future work after this slice lands.
- [ ] 4.3 Make the docs explicit that a newer Gradle release alone is informational for this slice unless the repo later adds a separate upgrade-policy contract.
- [ ] 4.4 Remove the stale phrases that currently say `#155` remains future work on current `main`, including the `issue-124` line that lists `#155` among later source-specific follow-ups and the `issue-143` line that says the remaining future-work set still includes `#155`.
- [ ] 4.5 Run a targeted search for stale wording that still claims every runner-host group is manual-only or that `#155` remains future work on current `main`.
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
      'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['historical', 'android-gradle'],
      'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['historical', 'android-gradle'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': ['historical', 'android-gradle'],
  }
  stale_checks = {
      'docs/specs/issues/issue-124-runner-host-drift-watch.md': [
          'remaining later source-specific automation is split across `#143` (runner images), `#154` (android java), `#155` (android gradle), `#156` (android emulator runtime), and `#144` (ios xcode / simulator runtime) after the android narrowing contract in `#142`',
      ],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': [
          'the remaining runner-host groups stay explicit future work under `#154`, `#155`, `#156`, and `#144`',
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
- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `android-gradle` now renders as `gradle-release-catalog`.
- [ ] 5.5 In the PR summary/comment, say the implementation PR `Closes #155`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state that the non-Gradle runner-host groups remained manual-only.
- Goal: Leave QA with one honest picture of the Gradle-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host managed-issue behavior under test.
- Hand back if: The refreshed head still reports `android-gradle` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #155`.
