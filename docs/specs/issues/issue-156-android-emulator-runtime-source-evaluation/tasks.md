# Issue #156 — Implementation tasks

- Linked issue: `#156`
- Source contract: `./spec.md`

## 1. Add failing regression coverage for Android emulator-runtime source-backed evaluation
- [ ] 1.1 Add deterministic Android emulator source payload fixtures under `tests/test-support/fixtures/runner-host-watch/emulator-source/` for a matching API 34 / Android 14 / Google APIs x86_64 runtime, a missing-package case, an API/runtime mismatch case, a newer-upstream-revision-but-non-alerting case, and an unavailable/malformed source response.
- [ ] 1.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `android-emulator-runtime` remains `manual-review-required` instead of an active source-backed rule.
- [ ] 1.3 Prove the new assertions distinguish source-backed findings from drift counts by keeping `advisory_count` at zero for emulator-runtime-only source findings.
- [ ] 1.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing Android emulator-runtime source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `android-emulator-runtime` as an active source-backed rule with deterministic coverage for matching, missing-package, mismatch, newer-revision-only, and source-unavailable cases.

## 2. Promote the checked-in `android-emulator-runtime` source rule from placeholder to active contract
- [ ] 2.1 Update `.github/runner-host-advisory-sources.json` so `android-emulator-runtime` uses `rule_kind: android-system-image-catalog`.
- [ ] 2.2 Add only the rule-specific source metadata needed for the Android platform/system-image evaluator while preserving `follow_up_issue: 156` and the existing watched fact paths.
- [ ] 2.3 Keep `runner-images`, `android-java`, `android-gradle`, and `ios-xcode-simulator` as `manual-review-required` follow-up groups.
- [ ] 2.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` to include `emulator.target`, `emulator.arch`, `emulator.profile`, package revisions, extension levels, or any other new watched fact.
- Goal: Make the repo-owned manifest describe one bounded active emulator-runtime source rule without reopening the other runner-host follow-up scopes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No Java/Gradle/iOS/runner-image source activation, no new managed issue title.
- Hand back if: The emulator-runtime slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the non-emulator groups too.

## 3. Implement bounded Android emulator-runtime source evaluation in `runner_host_review_report.py`
- [ ] 3.1 Normalize and validate the new `android-system-image-catalog` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [ ] 3.2 Load authoritative Android platform/system-image metadata for live runs while keeping deterministic fixture injection for unit tests.
- [ ] 3.3 Evaluate the observed runtime using `emulator.api_level` and `emulator.os_version`, with the emitted `target` / `arch` support fields used only as lookup inputs for the official Google APIs x86_64 system-image package.
- [ ] 3.4 Emit explicit review-needed findings when the observed API level has no matching Google APIs x86_64 system image, the observed Android version does not match the authoritative API mapping, or the source payload is unavailable/malformed.
- [ ] 3.5 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` scoped to changed/missing watched facts, with a separate source-backed finding count/list for emulator-runtime findings.
- [ ] 3.6 Keep `emulator.device_name` in the existing drift path only; do not create a second source-only alert dimension for the generated device string in this slice.
- [ ] 3.7 Ensure a newer upstream Android API/system-image revision can be rendered as context without becoming a review-needed condition by itself on current `main`.
- Goal: Activate one trustworthy emulator-runtime source-backed path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No local-sdk probing, no API freshness ratchet, no device-name policy beyond the bounded contract in `spec.md`.
- Hand back if: The bounded emulator-runtime evaluator would require widening the watched inventory, redefining the managed-issue sync path, or inventing an unsupported authoritative source for `emulator.device_name` instead of staying inside the existing runner-host watch.

## 4. Reconcile the repo-owned docs and earlier issue-spec contract
- [ ] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `android-emulator-runtime` is now source-backed while the other runner-host groups remain `manual-review-required`.
- [ ] 4.2 Reconcile `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md` and `docs/specs/issues/issue-142-android-runner-host-source-split.md` so they no longer read as if current `main` still has no active runner-host source-backed evaluation at all.
- [ ] 4.3 Make the docs explicit that `emulator.device_name` remains a drift-only supporting fact in this slice, and that `target` / `arch` / `profile` are lookup/context inputs rather than newly watched runner-host facts.
- [ ] 4.4 Make the docs explicit that a newer upstream Android API or system-image revision alone is informational for this slice unless the repo later adds a separate upgrade/freshness policy contract.
- [ ] 4.5 Run a targeted search for stale wording that still claims every runner-host group is manual-only on current `main`.
- Goal: Leave one truthful repo-owned contract instead of a live emulator-source-backed story colliding with older drift-only wording.
- Validation:
  ```bash
  python3 - <<'PY'
  from pathlib import Path
  checks = {
      'docs/development/cve-watch-operations.md': ['android-emulator-runtime', 'source-backed'],
      'docs/development/security-automation-plan.md': ['android-emulator-runtime', 'source-backed'],
      'docs/development/security-owasp-baseline.md': ['android-emulator-runtime', 'source-backed'],
      'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['historical', 'android-emulator-runtime'],
      'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['historical', 'android-emulator-runtime'],
  }
  for rel, needles in checks.items():
      text = Path(rel).read_text(encoding='utf-8').lower()
      for needle in needles:
          assert needle in text, (rel, needle)
  print('runner-host docs/specs reflect the android-emulator-runtime source-backed contract')
  PY
  ```
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this emulator-runtime-only slice cannot honestly change.

## 5. Run bounded validation and hand back with honest closure semantics
- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `android-emulator-runtime` now renders as `android-system-image-catalog`.
- [ ] 5.5 In the PR summary/comment, say the implementation PR `Closes #156`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state that the non-emulator runner-host groups remained manual-only.
- Goal: Leave QA with one honest picture of the emulator-runtime-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host managed-issue behavior under test.
- Hand back if: The refreshed head still reports `android-emulator-runtime` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #156`.
