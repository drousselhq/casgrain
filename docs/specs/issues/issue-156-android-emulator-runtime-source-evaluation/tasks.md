# Issue #156 — Implementation tasks

- Linked issue: `#156`
- Source contract: `./spec.md`

## 1. Add failing regression coverage for Android emulator-runtime source-backed evaluation
- [x] 1.1 Add deterministic Android emulator source payload fixtures under `tests/test-support/fixtures/runner-host-watch/emulator-source/` for a matching API 34 / Android 14 / Google APIs x86_64 runtime, a missing-package case, an API/runtime mismatch case, a newer-upstream-revision-but-non-alerting case, and an unavailable/malformed source response.
- [x] 1.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `android-emulator-runtime` remains `manual-review-required` instead of an active source-backed rule.
- [x] 1.3 Prove the new assertions use the shared runner-host summary contract: emulator-runtime-only source findings increment the top-level `advisory_count` and use a dedicated source-backed reason when no baseline drift exists, without requiring a separate top-level `source_advisory_count`.
- [x] 1.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing Android emulator-runtime source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `android-emulator-runtime` as an active source-backed rule with deterministic coverage for matching, missing-package, mismatch, newer-revision-only, and source-unavailable cases.

## 2. Promote the checked-in `android-emulator-runtime` source rule from placeholder to active contract
- [x] 2.1 Update `.github/runner-host-advisory-sources.json` so `android-emulator-runtime` uses `rule_kind: android-system-image-catalog`.
- [x] 2.2 Add only the rule-specific source metadata needed for the Android platform/system-image evaluator while preserving `follow_up_issue: 156` and the existing watched fact paths.
- [x] 2.3 Keep `runner-images` on the delivered `runner-image-release-metadata` rule, keep `android-java` and `android-gradle` on their already-delivered source-backed paths under `#154` / `#155`, and do not widen this Android slice into the separate iOS follow-up ownership already tracked by `#164` / `#165`.
- [x] 2.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` to include `emulator.target`, `emulator.arch`, `emulator.profile`, package revisions, extension levels, or any other new watched fact.
- Goal: Make the repo-owned manifest describe one bounded active emulator-runtime source rule without reopening the delivered `runner-images` slice or the other runner-host follow-up scopes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No Java/Gradle/iOS source activation, no runner-images rework, no new managed issue title.
- Hand back if: The emulator-runtime slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the non-emulator groups or silently overriding the separate iOS follow-up ownership already tracked by `#164` / `#165`.

## 3. Implement bounded Android emulator-runtime source evaluation in `runner_host_review_report.py`
- [x] 3.1 Normalize and validate the new `android-system-image-catalog` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [x] 3.2 Load authoritative Android platform/system-image metadata for live runs while keeping deterministic fixture injection for unit tests.
- [x] 3.3 Evaluate the observed runtime using `emulator.api_level` and `emulator.os_version`, with the emitted `target` / `arch` support fields used only as lookup inputs for the official Google APIs x86_64 system-image package.
- [x] 3.4 Emit explicit review-needed findings when the observed API level has no matching Google APIs x86_64 system image, the observed Android version does not match the authoritative API mapping, or the source payload is unavailable/malformed.
- [x] 3.5 Preserve the existing drift / missing-evidence behavior, keep top-level `advisory_count` as the combined actionable count across baseline and source-backed findings, and do **not** add a separate top-level `source_advisory_count`.
- [x] 3.6 Keep `emulator.device_name` in the existing drift path only; do not create a second source-only alert dimension for the generated device string in this slice.
- [x] 3.7 Ensure a newer upstream Android API/system-image revision can be rendered as context without becoming a review-needed condition by itself on current `main`.
- Goal: Activate one trustworthy emulator-runtime source-backed path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No local-SDK probing, no API freshness ratchet, no device-name policy beyond the bounded contract in `spec.md`.
- Hand back if: The bounded emulator-runtime evaluator would require widening the watched inventory, redefining the managed-issue sync path, or inventing an unsupported authoritative source for `emulator.device_name` instead of staying inside the existing runner-host watch.

## 4. Reconcile the repo-owned docs and earlier issue-spec contract
- [x] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `runner-images`, `android-java`, and `android-gradle` are already delivered source-backed groups, `android-emulator-runtime` is newly source-backed in this slice, and current docs do not preserve closed issue `#144` as the live owner of the later iOS work already split across `#164` / `#165`.
- [x] 4.2 Reconcile `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, and `docs/specs/issues/issue-142-android-runner-host-source-split.md` so they no longer read as if current `main` is uniformly drift-only, or as if only `#143` is delivered while `#156` still remains untouched future work after this slice lands.
- [x] 4.3 Reconcile `docs/specs/issues/issue-143-runner-image-source-evaluation/{spec,tasks}.md` so they no longer say only `runner-images` is source-backed or leave `#156` as untouched future work once this slice lands.
- [x] 4.4 Reconcile `docs/specs/issues/issue-144-ios-runner-host-source-split/{spec,tasks}.md`, `docs/specs/issues/issue-154-android-java-source-evaluation/{spec,tasks}.md`, and `docs/specs/issues/issue-155-android-gradle-source-evaluation/{spec,tasks}.md` so they remove stale `android-emulator-runtime` manual-only / unchanged-ownership wording, stop treating closed issue `#144` as the live iOS owner after `#156` lands, and stop presenting the post-`#155` current-main source-backed set as only `runner-images` + `android-gradle` once `android-emulator-runtime` is delivered by this slice.
- [x] 4.5 Make the docs explicit that `emulator.device_name` remains a drift-only supporting fact, that `target` / `arch` / `profile` are lookup/context inputs rather than newly watched runner-host facts, and run a targeted search for stale wording that still contradicts this contract.
- Goal: Leave one truthful repo-owned contract instead of a live emulator-source-backed story colliding with older drift-only or runner-images-only wording.
- Validation:
  ```bash
  python3 - <<'PY'
  from pathlib import Path

  required = {
      'docs/development/cve-watch-operations.md': ['android-emulator-runtime', 'source-backed'],
      'docs/development/security-automation-plan.md': ['android-emulator-runtime', 'source-backed'],
      'docs/development/security-owasp-baseline.md': ['android-emulator-runtime', 'source-backed'],
      'docs/specs/issues/issue-124-runner-host-drift-watch.md': ['android-emulator-runtime', 'source-backed'],
      'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['android-emulator-runtime', 'source-backed'],
      'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['android-emulator-runtime', 'source-backed'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/spec.md': ['android-emulator-runtime'],
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/tasks.md': ['android-emulator-runtime'],
  }
  for rel, needles in required.items():
      text = Path(rel).read_text(encoding='utf-8').lower()
      for needle in needles:
          assert needle in text, (rel, needle)
  for rel in [
      'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md',
      'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md',
  ]:
      text = Path(rel).read_text(encoding='utf-8')
      assert 'source_advisory_count' not in text, rel
  print('runner-host docs/specs reflect the android-emulator-runtime source-backed contract')
  PY
  ```
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this emulator-runtime-only slice cannot honestly change.

## 5. Run bounded validation and hand back with honest closure semantics
- [x] 5.1 Run `git diff --check`.
- [x] 5.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [x] 5.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [x] 5.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `android-emulator-runtime` now renders as `android-system-image-catalog`, `runner-images` still renders as `runner-image-release-metadata`, and the current `ios-xcode-simulator` placeholder exposes `follow_up_issues=[164,165]` instead of reviving closed issue `#144`, even if the current live summary still reports review-needed for unrelated runner-image findings.
- [x] 5.5 In the PR summary/comment, say the implementation PR `Closes #156`, explicitly note that `docs-needed` still applies because canonical docs/specs changed, and state that `runner-images`, `android-java`, and `android-gradle` remain delivered while later iOS work stays with `#164` / `#165`.
- Goal: Leave QA with one honest picture of the emulator-runtime-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host managed-issue behavior under test.
- Hand back if: The refreshed head still reports `android-emulator-runtime` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #156`.
