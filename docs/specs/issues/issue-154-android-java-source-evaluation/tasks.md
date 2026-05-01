# Issue #154 — Implementation tasks

- Linked issue: `#154`
- Source contract: `./spec.md`

## 1. Add failing regression coverage for Android Java source-backed evaluation
- [x] 1.1 Add deterministic Java source payload fixtures under `tests/test-support/fixtures/runner-host-watch/java-source/` for a supported release line, an unsupported/unrecognized release line, and an unavailable/malformed source response.
- [x] 1.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `android-java` remains `manual-review-required` instead of an active source-backed rule.
- [x] 1.3 Prove the new assertions keep Java-only source-backed findings on the same top-level `advisory_count` path current `main` already uses for source-backed results.
- [x] 1.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing Android Java source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `android-java` as an active source-backed rule with deterministic coverage for supported, unsupported, and source-unavailable cases, or if the adjacent `runner-images` / iOS placeholder contract no longer matches `spec.md`.

## 2. Promote the checked-in `android-java` source rule from placeholder to active contract
- [x] 2.1 Update `.github/runner-host-advisory-sources.json` so `android-java` uses `rule_kind: java-release-support`.
- [x] 2.2 Add only the rule-specific source metadata needed for the Java release/support evaluator while preserving `follow_up_issue: 154` and the existing watched fact paths.
- [x] 2.3 Keep `runner-images` on the delivered `runner-image-release-metadata` rule, treat `android-gradle` and `android-emulator-runtime` as already source-backed on current `main`, and leave the current combined `ios-xcode-simulator` placeholder unchanged in this slice while later ownership stays with `#164` / `#165`.
- [x] 2.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` to include `java.distribution` or any other new Java fact.
- Goal: Make the repo-owned manifest describe one bounded active Java source rule without reopening the other runner-host follow-up scopes.
- Validation:

  ```bash
  python3 - <<'PY'
  import json
  from pathlib import Path
  manifest = json.loads(Path('.github/runner-host-advisory-sources.json').read_text(encoding='utf-8'))
  groups = {group['key']: group for group in manifest['groups']}
  assert groups['runner-images']['rule_kind'] == 'runner-image-release-metadata', groups['runner-images']
  assert groups['android-java']['rule_kind'] == 'java-release-support', groups['android-java']
  assert groups['android-gradle']['rule_kind'] == 'gradle-release-catalog', groups['android-gradle']
  assert groups['android-emulator-runtime']['rule_kind'] == 'android-system-image-catalog', groups['android-emulator-runtime']
  assert groups['ios-xcode-simulator']['rule_kind'] == 'manual-review-required', groups['ios-xcode-simulator']
  print('android-java is promoted while runner-images and android-emulator-runtime stay delivered and the remaining follow-up groups stay unchanged at this checkpoint')
  PY
  ```
- Non-goals: No Gradle/emulator/iOS source activation, no runner-images rework, no new report title.
- Hand back if: The Java slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the non-Java groups too.

## 3. Implement bounded Android Java source evaluation in `runner_host_review_report.py`
- [x] 3.1 Normalize and validate the new `java-release-support` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [x] 3.2 Load authoritative machine-readable Java release/support data for live runs while keeping deterministic fixture injection for unit tests.
- [x] 3.3 Evaluate only `java.configured_major` and `java.resolved_version`, and emit explicit review-needed findings when the configured line is unsupported, the resolved version is unrecognized for that line, or the source payload is unavailable/malformed.
- [x] 3.4 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` on the shared current-main contract: it remains the total actionable finding count across drift/missing evidence and source-backed results, without adding a separate top-level field.
- [x] 3.5 When Android host evidence is missing or unreadable, report the active `android-java` source rule as `source-skipped` and do not add a second Java source advisory on top of the baseline missing-evidence count.
- [x] 3.6 Update the rendered markdown/summary so Android Java source findings are explicit while `runner-images` stays source-backed and the remaining follow-up groups stay otherwise unchanged.
- Goal: Activate one trustworthy Java-only source-backed path without changing the baseline drift contract for the rest of the runner-host watch or rewriting the unchanged iOS placeholder ownership on current `main`.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No broad CVE scraping, no Java distribution policy, no patch-freshness ratchet beyond the bounded release/support contract in `spec.md`.
- Hand back if: The bounded Java evaluator would require changing `host-environment.json` fields, widening the watched inventory, or redesigning the report sync path instead of staying inside the existing runner-host watch.

## 4. Reconcile the repo-owned docs and earlier issue-spec contract
- [x] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `runner-images`, `android-gradle`, and `android-emulator-runtime` are already source-backed on current `main`, `android-java` becomes source-backed in this slice, Android Java `source-review-needed` / `source-error` findings reuse `security: runner-host review needed`, and the current combined `ios-xcode-simulator` placeholder still remains `manual-review-required` on current `main` while any `#164` / `#165` references are historical only.
- [x] 4.2 Reconcile `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, `docs/specs/issues/issue-142-android-runner-host-source-split.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md`, `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`, and `docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md` so they no longer read as if current `main` still has only one delivered source-backed runner-host slice or still presents `#154` as a later follow-up after this slice lands, while preserving the unchanged `ios-xcode-simulator` placeholder on current `main` and treating `#164` / `#165` only as historical follow-up issue numbers.
- [x] 4.3 Keep `java.distribution` explicitly out of scope in every touched doc/spec artifact unless a later issue adds it to `.github/runner-host-watch.json`.
- [x] 4.4 Run a targeted search for stale wording that still claims every runner-host group except `runner-images` is manual-only on current `main`, still says `#154` remains future work in `docs/specs/issues/issue-124-runner-host-drift-watch.md` or `docs/specs/issues/issue-142-android-runner-host-source-split.md`, still says the shipped runner-host automation evaluates only drift / missing evidence in `docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md`, still freezes the `#154` validation snippet to `advisory_count == 0` instead of the shared runner-host summary contract when unrelated drift remains, or still tells implementers in `docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md` to expect split iOS summary keys instead of the live combined `ios-xcode-simulator` placeholder plus later ownership `#164` / `#165` on current `main`.
- Goal: Leave one truthful repo-owned contract instead of a live Java-source-backed story colliding with older drift-only wording or a fictional iOS split that current `main` has not landed yet.
- Validation:

  ```bash
  python3 - <<'PY'
  from pathlib import Path
  checks = {
    'docs/development/cve-watch-operations.md': ['android-java', 'security: runner-host review needed'],
    'docs/development/security-automation-plan.md': ['android-java', 'security: runner-host review needed'],
    'docs/development/security-owasp-baseline.md': ['android-java', '#164', '#165'],
    'docs/specs/issues/issue-124-runner-host-drift-watch.md': ['android-java', '#164', '#165'],
    'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['android-java', '#164', '#165'],
    'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['#154', '#155', '#156', '#164', '#165'],
    'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': ['historical', 'android-java'],
    'docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md': ['runner-images', 'android-java'],
    'docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md': ['runner-images', 'android-java'],
    'docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md': ['historical', 'ios-xcode-simulator', '#164', '#165'],
    'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md': ['unrelated drift or missing-evidence alerts', 'shared runner-host summary contract'],
  }
  for rel, needles in checks.items():
      text = Path(rel).read_text(encoding='utf-8').lower()
      for needle in needles:
          assert needle in text, (rel, needle)
  print('runner-host docs/specs reflect the android-java source-backed contract')
  PY
  ```
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this Java-only slice cannot honestly change, or if the live iOS placeholder ownership changes again on current `main`.

## 5. Run bounded validation and hand back with honest closure semantics
- [x] 5.1 Run `git diff --check`.
- [x] 5.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [x] 5.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [x] 5.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `android-java` now renders as `java-release-support` while `runner-images` remains `runner-image-release-metadata`, even if unrelated drift elsewhere still keeps the top-level summary advisory count non-zero.
- [x] 5.5 In the PR summary/comment, say the implementation PR `Closes #154`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state that the current combined `ios-xcode-simulator` placeholder still remains on current `main` while any `#164` / `#165` references are historical only.
- Goal: Leave QA with one honest picture of the Java-only source-backed change, its validation evidence, and its closure boundary without reopening the delivered runner-images or the unchanged iOS placeholder slice.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host report behavior under test.
- Hand back if: The refreshed head still reports `android-java` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #154`.
