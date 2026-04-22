# Issue #154 — Implementation tasks

- Linked issue: `#154`
- Source contract: `./spec.md`

## 1. Add failing regression coverage for Android Java source-backed evaluation
- [ ] 1.1 Add deterministic Java source payload fixtures under `tests/test-support/fixtures/runner-host-watch/java-source/` for a supported release line, an unsupported/unrecognized release line, and an unavailable/malformed source response.
- [ ] 1.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `android-java` remains `manual-review-required` instead of an active source-backed rule.
- [ ] 1.3 Prove the new assertions distinguish source-backed findings from drift counts by keeping `advisory_count` at zero for Java-only source findings.
- [ ] 1.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing Android Java source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `android-java` as an active source-backed rule with deterministic coverage for supported, unsupported, and source-unavailable cases.

## 2. Promote the checked-in `android-java` source rule from placeholder to active contract
- [ ] 2.1 Update `.github/runner-host-advisory-sources.json` so `android-java` uses `rule_kind: java-release-support`.
- [ ] 2.2 Add only the rule-specific source metadata needed for the Java release/support evaluator while preserving `follow_up_issue: 154` and the existing watched fact paths.
- [ ] 2.3 Keep `runner-images`, `android-gradle`, `android-emulator-runtime`, and `ios-xcode-simulator` as `manual-review-required` follow-up groups.
- [ ] 2.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` to include `java.distribution` or any other new Java fact.
- Goal: Make the repo-owned manifest describe one bounded active Java source rule without reopening the other runner-host follow-up scopes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No Gradle/emulator/iOS/runner-image source activation, no new managed issue title.
- Hand back if: The Java slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the non-Java groups too.

## 3. Implement bounded Android Java source evaluation in `runner_host_review_report.py`
- [ ] 3.1 Normalize and validate the new `java-release-support` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [ ] 3.2 Load authoritative machine-readable Java release/support data for live runs while keeping deterministic fixture injection for unit tests.
- [ ] 3.3 Evaluate only `java.configured_major` and `java.resolved_version`, and emit explicit review-needed findings when the configured line is unsupported, the resolved version is unrecognized for that line, or the source payload is unavailable/malformed.
- [ ] 3.4 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` scoped to changed/missing watched facts, with a separate source-backed finding count/list for Java findings.
- [ ] 3.5 Update the rendered markdown/summary so Android Java source findings are explicit and the non-Java groups still show as `manual-review-required` follow-ups.
- Goal: Activate one trustworthy Java-only source-backed path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No broad CVE scraping, no Java distribution policy, no patch-freshness ratchet beyond the bounded release/support contract in `spec.md`.
- Hand back if: The bounded Java evaluator would require changing `host-environment.json` fields, widening the watched inventory, or redesigning the managed-issue sync path instead of staying inside the existing runner-host watch.

## 4. Reconcile the repo-owned docs and earlier issue-spec contract
- [ ] 4.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `android-java` is now source-backed while the other runner-host groups remain `manual-review-required`.
- [ ] 4.2 Reconcile `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md` and `docs/specs/issues/issue-142-android-runner-host-source-split.md` so they no longer read as if current `main` still has no active runner-host source-backed evaluation at all.
- [ ] 4.3 Keep `java.distribution` explicitly out of scope in every touched doc/spec artifact unless a later issue adds it to `.github/runner-host-watch.json`.
- [ ] 4.4 Run a targeted search for stale wording that still claims every runner-host group is manual-only on current `main`.
- Goal: Leave one truthful repo-owned contract instead of a live Java-source-backed story colliding with older drift-only wording.
- Validation: `python3 - <<'PY'
from pathlib import Path
checks = {
    'docs/development/cve-watch-operations.md': ['android-java', 'source-backed'],
    'docs/development/security-automation-plan.md': ['android-java', 'source-backed'],
    'docs/development/security-owasp-baseline.md': ['android-java', 'source-backed'],
    'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['historical', 'android-java'],
    'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['historical', 'android-java'],
}
for rel, needles in checks.items():
    text = Path(rel).read_text(encoding='utf-8').lower()
    for needle in needles:
        assert needle in text, (rel, needle)
print('runner-host docs/specs reflect the android-java source-backed contract')
PY`
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this Java-only slice cannot honestly change.

## 5. Run bounded validation and hand back with honest closure semantics
- [ ] 5.1 Run `git diff --check`.
- [ ] 5.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [ ] 5.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `android-java` now renders as `java-release-support`.
- [ ] 5.5 In the PR summary/comment, say the implementation PR `Closes #154`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state whether any non-Java runner-host groups remained manual-only.
- Goal: Leave QA with one honest picture of the Java-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host managed-issue behavior under test.
- Hand back if: The refreshed head still reports `android-java` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #154`.
