# Issue #164 — Implementation tasks

- Linked issue: `#164`
- Source contract: `./spec.md`

## 1. Confirm the bounded iOS Xcode slice is actually ready on current `main`
- [ ] 1.1 Re-run the runner-host report and confirm whether current `main` already exposes split `ios-xcode` / `ios-simulator-runtime` groups instead of the old combined `ios-xcode-simulator` group.
- [ ] 1.2 Confirm `ios-xcode` is mapped to `#164` and `ios-simulator-runtime` is mapped to `#165` before making any production edit for this issue.
- [ ] 1.3 Capture the authoritative Apple Xcode support-matrix row for the currently watched Xcode version and bundled simulator SDK so the implementation stays grounded on the real source family for this slice.
- Goal: Prove the repo is on the post-split contract required for the Xcode-only promotion work before changing the checked-in manifest, tests, or report logic.
- Validation:

  ```bash
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
  import json, re, requests
  from html import unescape
  from pathlib import Path

  summary = json.loads(Path('/tmp/runner-host-watch-summary.json').read_text(encoding='utf-8'))
  keys = [group['key'] for group in summary['source_rule_groups']]
  print('source_rule_keys=', keys)

  html = requests.get('https://developer.apple.com/support/xcode/', timeout=20).text
  match = re.search(r'<td>Xcode&nbsp;16\.4</td>.*?<td>(.*?)</td>\s*<td>(.*?)</td>', html, re.S)
  assert match, 'missing Xcode 16.4 support-matrix row'
  sdk_cell = unescape(re.sub(r'<.*?>', ' ', match.group(2)))
  assert 'iOS 18.5' in ' '.join(sdk_cell.split()), sdk_cell
  print('apple xcode support row includes iOS 18.5')
  PY
  ```
- Non-goals: No production edits yet, no simulator-runtime evaluation, no reimplementation of the earlier iOS split inside this issue.
- Hand back if: Current `main` still exposes only `ios-xcode-simulator`, `ios-xcode` is not already owned by `#164`, or Apple’s support matrix no longer provides a trustworthy row for the observed Xcode version.

## 2. Add failing regression coverage for iOS Xcode source-backed evaluation
- [ ] 2.1 Add deterministic Apple Xcode support-matrix fixtures under `tests/test-support/fixtures/runner-host-watch/xcode-source/` for a clean match, a missing-version-row case, a simulator-SDK mismatch case, a newer-upstream-row-but-non-alerting case, and an unavailable/malformed source response.
- [ ] 2.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `ios-xcode` remains `manual-review-required` instead of an active source-backed rule.
- [ ] 2.3 Prove the new assertions keep iOS Xcode source-backed findings on the same top-level `advisory_count` path current `main` already uses for source-backed findings instead of introducing a separate top-level `source_advisory_count` field.
- [ ] 2.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing iOS Xcode source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `ios-xcode` as an active source-backed rule with deterministic coverage for clean, mismatch, newer-row-only, and source-unavailable cases.

## 3. Promote the checked-in `ios-xcode` source rule from placeholder to active contract
- [ ] 3.1 Update `.github/runner-host-advisory-sources.json` so `ios-xcode` uses `rule_kind: apple-xcode-support-matrix`.
- [ ] 3.2 Add only the rule-specific source metadata needed for the Apple Xcode support-matrix evaluator while preserving `follow_up_issue: 164` and the existing watched fact paths.
- [ ] 3.3 Keep `ios-simulator-runtime` as the remaining `manual-review-required` iOS follow-up under `#165`, and keep `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` on their already-delivered source-backed groups.
- [ ] 3.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` and still treats `xcode.app_path` as a watched drift/supporting fact rather than a source-backed comparison field.
- Goal: Make the repo-owned manifest describe one bounded active Xcode source rule without reopening the simulator-runtime or non-iOS follow-up scopes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No simulator-runtime activation, no new managed issue title, no freshness ratchet.
- Hand back if: The Xcode slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the simulator-runtime or non-iOS groups too.

## 4. Implement bounded iOS Xcode source evaluation in `runner_host_review_report.py`
- [ ] 4.1 Normalize and validate the new `apple-xcode-support-matrix` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [ ] 4.2 Load Apple’s Xcode support matrix for live runs while keeping deterministic fixture injection for unit tests.
- [ ] 4.3 Evaluate only `xcode.version` and `xcode.simulator_sdk_version`, and emit explicit review-needed findings when the Xcode row is missing, the simulator SDK version does not match the authoritative row, or the source payload is unavailable/malformed.
- [ ] 4.4 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` on the shared current-main contract: it remains the total actionable finding count across drift/missing evidence and source-backed results, without adding a separate top-level `source_advisory_count` field.
- [ ] 4.5 Keep `xcode.app_path` in the existing drift path only; do not create a second source-only alert dimension for the local install path in this slice.
- [ ] 4.6 Ensure a newer upstream Xcode or SDK row can be rendered as context without becoming a review-needed condition by itself on current `main`.
- Goal: Activate one trustworthy Xcode-only source-backed path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No simulator-runtime/device availability evaluation, no local Xcode probing, no source-backed comparison for `xcode.app_path`.
- Hand back if: The bounded Xcode evaluator would require widening the watched inventory, redefining the managed-issue sync path, or absorbing the simulator-runtime source family instead of staying inside the existing runner-host watch.

## 5. Reconcile the repo-owned docs and earlier issue-spec contract
- [ ] 5.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `ios-xcode` is now source-backed while `ios-simulator-runtime` and `android-java` remain follow-up issues and the other non-iOS groups keep their already-delivered source-backed states.
- [ ] 5.2 Reconcile `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, `docs/specs/issues/issue-142-android-runner-host-source-split.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/{spec,tasks}.md`, `docs/specs/issues/issue-144-ios-runner-host-source-split/{spec,tasks}.md`, `docs/specs/issues/issue-154-android-java-source-evaluation/{spec,tasks}.md`, `docs/specs/issues/issue-155-android-gradle-source-evaluation/{spec,tasks}.md`, and `docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/{spec,tasks}.md` so they no longer preserve the superseded `ios-xcode-simulator` / `#144` umbrella story, no longer say only `runner-images` is source-backed on current `main`, no longer frame `#164` as unresolved future work after this slice lands, no longer require a drift-only top-level `advisory_count` plus a separate top-level `source_advisory_count` for the shared runner-host summary contract, and no longer leave `issue-156/spec.md` claiming the later iOS work still has open spec-entry PRs `#171` and `#173` after `#164` merges.
- [ ] 5.3 Make the docs explicit that `xcode.app_path` remains a drift-only supporting fact in this slice and that a newer upstream Xcode release or SDK row alone is not yet a review-needed condition.
- [ ] 5.4 Run a targeted search for stale wording that still claims `ios-xcode` is manual-only future work on current `main`, still keeps `ios-xcode-simulator` / `#144` as the live post-`#164` iOS placeholder, still says the later iOS work has open spec-entry PRs `#171` and `#173`, or still requires a drift-only `advisory_count` plus a top-level `source_advisory_count` in the adjacent `#154` / `#155` / `#156` issue-spec artifacts.
- Goal: Leave one truthful repo-owned contract instead of a live Xcode-source-backed story colliding with older drift-only or future-work wording.
- Validation:
  ```bash
  python3 - <<'PY'
  from pathlib import Path
  checks = {
      'docs/development/cve-watch-operations.md': ['ios-xcode', 'source-backed'],
      'docs/development/security-automation-plan.md': ['ios-xcode', 'source-backed'],
      'docs/development/security-owasp-baseline.md': ['ios-xcode', 'source-backed'],
      'docs/specs/issues/issue-124-runner-host-drift-watch.md': ['#164', '#165'],
      'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['#164', '#165'],
      'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['#164', '#165'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': ['historical', '#164', '#165'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md': ['#164', '#165'],
      'docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md': ['historical', '#164', '#165'],
      'docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md': ['#164', '#165'],
      'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md': ['#164', '#165', 'ios-xcode'],
      'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md': ['#164', '#165', 'ios-xcode'],
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/spec.md': ['#164', '#165', 'ios-xcode'],
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/tasks.md': ['#164', '#165', 'ios-xcode'],
      'docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md': ['#164', '#165', 'ios-xcode'],
      'docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/tasks.md': ['#164', '#165', 'ios-xcode'],
  }
  for rel, needles in checks.items():
      text = Path(rel).read_text(encoding='utf-8').lower()
      for needle in needles:
          assert needle.lower() in text, (rel, needle)
  for rel in (
      'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md',
      'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md',
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/spec.md',
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/tasks.md',
      'docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md',
      'docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/tasks.md',
  ):
      text = Path(rel).read_text(encoding='utf-8').lower()
      assert 'source_advisory_count' not in text, rel
  issue_156_spec = Path('docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md').read_text(encoding='utf-8').lower()
  assert 'open spec-entry prs `#171` and `#173`' not in issue_156_spec, 'issue-156/spec.md still preserves stale post-#164 PR-open wording'
  print('runner-host docs/specs reflect the ios-xcode source-backed contract')
  PY
  ```
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this Xcode-only slice cannot honestly change.

## 6. Run bounded validation and hand back with honest closure semantics
- [ ] 6.1 Run `git diff --check`.
- [ ] 6.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [ ] 6.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [ ] 6.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `ios-xcode` now renders as `apple-xcode-support-matrix` without adding a top-level `source_advisory_count` field.
- [ ] 6.5 In the PR summary/comment, say the implementation PR `Closes #164`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state that `#165` and `android-java` remained separate follow-up work while `runner-images`, `android-gradle`, and `android-emulator-runtime` stayed on their delivered source-backed paths.
- Goal: Leave QA with one honest picture of the Xcode-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host managed-issue behavior under test.
- Hand back if: The refreshed head still reports `ios-xcode` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #164`.
