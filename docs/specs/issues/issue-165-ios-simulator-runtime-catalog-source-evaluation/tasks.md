# Issue #165 — Implementation tasks

- Linked issue: `#165`
- Source contract: `./spec.md`

## 1. Confirm the bounded simulator runtime-catalog slice is actually ready on current `main`
- [ ] 1.1 Re-run the runner-host report and confirm whether current `main` already exposes split `ios-xcode` / `ios-simulator-runtime` groups instead of the old combined `ios-xcode-simulator` group.
- [ ] 1.2 Confirm `ios-simulator-runtime` is mapped to `#165`, `ios-xcode` is mapped to `#164`, and the separate device-availability follow-up `#172` remains the home for any future `simulator.device_name` source-backed work.
- [ ] 1.3 Capture the authoritative Apple simulator runtime row for the currently watched runtime so the implementation stays grounded on the real runtime-catalog source family for this slice.
- Goal: Prove the repo is on the post-split contract required for the runtime-only promotion work before changing the checked-in manifest, tests, or report logic.
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
  import json
  import plistlib
  import urllib.request
  from pathlib import Path

  summary = json.loads(Path('/tmp/runner-host-watch-summary.json').read_text(encoding='utf-8'))
  print('source_rule_keys=', [group['key'] for group in summary['source_rule_groups']])

  data = urllib.request.urlopen(
      'https://devimages-cdn.apple.com/downloads/xcode/simulators/index2.dvtdownloadableindex',
      timeout=30,
  ).read()
  root = plistlib.loads(data)
  matches = [
      item for item in root['downloadables']
      if item.get('name') == 'iOS 26.2 beta Simulator Runtime'
      and item.get('simulatorVersion', {}).get('version') == '26.2'
  ]
  assert matches, 'missing iOS 26.2 runtime row'
  print('apple simulator runtime catalog includes iOS 26.2')
  PY
  ```
- Non-goals: No production edits yet, no device-availability/source work for `simulator.device_name`, no reimplementation of the earlier iOS split inside this issue.
- Hand back if: Current `main` still exposes only `ios-xcode-simulator`, `ios-simulator-runtime` is not already owned by `#165`, or Apple’s runtime catalog no longer provides a trustworthy runtime row for the observed simulator runtime.

## 2. Add failing regression coverage for simulator runtime-catalog evaluation
- [ ] 2.1 Add deterministic Apple simulator runtime fixtures under `tests/test-support/fixtures/runner-host-watch/simulator-runtime-source/` for a clean match, a missing-runtime-row case, a runtime-name mismatch case, a newer-upstream-runtime-but-non-alerting case, and an unavailable/malformed source response.
- [ ] 2.2 Extend `tests/scripts/test_runner_host_review_report.py` so current `main` fails when `ios-simulator-runtime` remains `manual-review-required` instead of an active source-backed rule.
- [ ] 2.3 Prove the new assertions distinguish simulator-runtime source-backed findings from drift counts by keeping `advisory_count` at zero for runtime-only source findings and by leaving `simulator.device_name` in drift-only/supporting status.
- [ ] 2.4 Verify the new or updated tests fail on the pre-change implementation before editing production behavior.
- Goal: Prove the missing simulator-runtime source-backed contract before touching the checked-in manifest or report logic.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No production manifest/report/docs edits yet.
- Hand back if: Current `main` already reports `ios-simulator-runtime` as an active source-backed rule with deterministic coverage for clean, mismatch, newer-row-only, and source-unavailable cases.

## 3. Promote the checked-in `ios-simulator-runtime` source rule from placeholder to active contract
- [ ] 3.1 Update `.github/runner-host-advisory-sources.json` so `ios-simulator-runtime` uses `rule_kind: apple-simulator-runtime-catalog`.
- [ ] 3.2 Add only the rule-specific source metadata needed for the Apple simulator runtime-catalog evaluator while preserving `follow_up_issue: 165` and the existing watched fact paths.
- [ ] 3.3 Keep `ios-xcode`, `android-java`, and `android-emulator-runtime` as their existing separate follow-up groups, while preserving `runner-images` and `android-gradle` as the already-delivered source-backed groups on current `main`.
- [ ] 3.4 Confirm the manifest still does **not** widen `.github/runner-host-watch.json` and still treats `simulator.device_name` as a watched drift/supporting fact rather than a runtime-catalog comparison field.
- Goal: Make the repo-owned manifest describe one bounded active simulator runtime rule without reopening device-availability, Xcode, or non-iOS follow-up scopes.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No device-availability activation, no new managed issue title, no runtime freshness ratchet.
- Hand back if: The runtime slice cannot be represented honestly inside the existing runner-host source-rule manifest without redesigning the device-availability or non-iOS groups too.

## 4. Implement bounded simulator runtime-catalog evaluation in `runner_host_review_report.py`
- [ ] 4.1 Normalize and validate the new `apple-simulator-runtime-catalog` rule kind in `tests/test-support/scripts/runner_host_review_report.py`.
- [ ] 4.2 Load Apple’s simulator runtime catalog for live runs while keeping deterministic fixture injection for unit tests.
- [ ] 4.3 Evaluate only `simulator.runtime_identifier` and `simulator.runtime_name`, and emit explicit review-needed findings when the runtime row is missing, the runtime name does not match the authoritative row, or the source payload is unavailable/malformed.
- [ ] 4.4 Preserve the existing drift / missing-evidence behavior and keep top-level `advisory_count` scoped to changed/missing watched facts, with a separate source-backed finding count/list for simulator-runtime findings.
- [ ] 4.5 Keep `simulator.device_name` in the existing drift path only; do not create a second source-only alert dimension for device availability in this slice.
- [ ] 4.6 Ensure a newer upstream runtime row can be rendered as context without becoming a review-needed condition by itself on current `main`.
- Goal: Activate one trustworthy simulator runtime-catalog path without changing the baseline drift contract for the rest of the runner-host watch.
- Validation: `python3 -m unittest tests/scripts/test_runner_host_review_report.py && python3 tests/test-support/scripts/runner_host_review_report.py --repo drousselhq/casgrain --baseline .github/runner-host-watch.json --android-workflow android-emulator-smoke.yml --android-artifact casgrain-android-smoke --ios-workflow ios-simulator-smoke.yml --ios-artifact casgrain-ios-smoke --summary-out /tmp/runner-host-watch-summary.json --markdown-out /tmp/runner-host-watch.md`
- Non-goals: No device-availability/source evaluation, no local simulator probing, no source-backed comparison for `simulator.device_name`.
- Hand back if: The bounded runtime evaluator would require widening the watched inventory, redefining the managed-issue sync path, or absorbing Xcode/device-availability source families instead of staying inside the existing runner-host watch.

## 5. Reconcile the repo-owned docs and earlier issue-spec contract
- [ ] 5.1 Update `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` so they state that `ios-simulator-runtime` is now source-backed while `ios-xcode`, `#172`, and the non-iOS groups remain on their own follow-up issues.
- [ ] 5.2 Reconcile `docs/specs/issues/issue-124-runner-host-drift-watch.md`, `docs/specs/issues/issue-129-runner-host-advisory-source-rules.md`, `docs/specs/issues/issue-142-android-runner-host-source-split.md`, `docs/specs/issues/issue-143-runner-image-source-evaluation/{spec,tasks}.md`, `docs/specs/issues/issue-144-ios-runner-host-source-split/{spec,tasks}.md`, and the other named adjacent issue-spec artifacts so they no longer read as if current `main` still has no active iOS source-backed evaluation, still leaves `#144` as the live umbrella owner, or still preserves closed `#144` as the remaining iOS follow-up after this slice lands.
- [ ] 5.3 Reconcile `docs/specs/issues/issue-164-ios-xcode-source-evaluation/{spec,tasks}.md` so they stop preserving the post-`#164` current-main contract where `ios-simulator-runtime` is still manual-only future work and all source-backed review findings still flow only through the shared top-level `advisory_count`; after `#165` lands, those older artifacts must treat `ios-simulator-runtime` as already source-backed on current `main` and preserve the separate simulator-runtime source finding/count surface instead of forbidding `source_advisory_count`.
- [ ] 5.4 Reconcile `docs/specs/issues/issue-154-android-java-source-evaluation/{spec,tasks}.md` so they stop preserving the pre-split `ios-xcode-simulator -> #144` live-owner story once the split prerequisite is on current `main`, and so they keep the post-`#165` shared summary contract truthful by preserving a separate simulator-runtime source finding/count surface instead of collapsing those findings into a drift-only top-level count.
- [ ] 5.5 Reconcile `docs/specs/issues/issue-155-android-gradle-source-evaluation/{spec,tasks}.md` so they stop requiring all source-backed review findings to live only in the shared top-level `advisory_count` with no separate source-backed finding/count field once this slice lands.
- [ ] 5.6 Reconcile `docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/{spec,tasks}.md` so they stop requiring that shared top-level-count-only contract, and rewrite `issue-156/spec.md` so it no longer says the later iOS work has open spec-entry PRs `#171` and `#173` after this slice lands.
- [ ] 5.7 Make the docs explicit that `simulator.device_name` remains a drift-only supporting fact in this slice and that any future device-availability source automation belongs to `#172`.
- [ ] 5.8 Run a targeted search for stale wording that still claims `ios-simulator-runtime` is manual-only future work, that `#144` still owns the live iOS umbrella contract after the split prerequisite, that `issue-143/tasks.md` still says `#154`, `#155`, `#156`, and `#144` remain future work instead of the split `#164` / `#165` ownership, that `issue-164/{spec,tasks}.md` still preserves the post-`#164` top-level-`advisory_count`-only contract or keeps `ios-simulator-runtime` manual-only, that adjacent `#154` / `#155` / `#156` specs/tasks still encode conflicting shared summary/count expectations about `source_advisory_count`, or that `issue-156/spec.md` still preserves `#173` as an open spec-entry PR.
- Goal: Leave one truthful repo-owned contract instead of a live simulator-runtime source-backed story colliding with older drift-only or umbrella-work wording.
- Validation:
  ```bash
  python3 - <<'PY'
  from pathlib import Path
  checks = {
      'docs/development/cve-watch-operations.md': ['ios-simulator-runtime', 'source-backed'],
      'docs/development/security-automation-plan.md': ['ios-simulator-runtime', 'source-backed'],
      'docs/development/security-owasp-baseline.md': ['ios-simulator-runtime', 'source-backed'],
      'docs/specs/issues/issue-124-runner-host-drift-watch.md': ['#172', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-129-runner-host-advisory-source-rules.md': ['#172', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-142-android-runner-host-source-split.md': ['#172', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/spec.md': ['#172', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md': ['#164', '#165', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-144-ios-runner-host-source-split/spec.md': ['#172', '#165'],
      'docs/specs/issues/issue-144-ios-runner-host-source-split/tasks.md': ['#165', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-164-ios-xcode-source-evaluation/spec.md': ['#165', 'ios-simulator-runtime', 'source_advisory_count'],
      'docs/specs/issues/issue-164-ios-xcode-source-evaluation/tasks.md': ['#165', 'ios-simulator-runtime', 'source_advisory_count'],
      'docs/specs/issues/issue-154-android-java-source-evaluation/spec.md': ['#165', 'source_advisory_count'],
      'docs/specs/issues/issue-154-android-java-source-evaluation/tasks.md': ['#165', 'source_advisory_count'],
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/spec.md': ['source_advisory_count', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-155-android-gradle-source-evaluation/tasks.md': ['source_advisory_count', 'ios-simulator-runtime'],
      'docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md': ['source_advisory_count', '#165', '#164'],
      'docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/tasks.md': ['source_advisory_count', '#165'],
  }
  for rel, needles in checks.items():
      text = Path(rel).read_text(encoding='utf-8').lower()
      for needle in needles:
          assert needle.lower() in text, (rel, needle)
  issue_164_spec = Path('docs/specs/issues/issue-164-ios-xcode-source-evaluation/spec.md').read_text(encoding='utf-8')
  issue_164_tasks = Path('docs/specs/issues/issue-164-ios-xcode-source-evaluation/tasks.md').read_text(encoding='utf-8')
  issue_143_tasks = Path('docs/specs/issues/issue-143-runner-image-source-evaluation/tasks.md').read_text(encoding='utf-8')
  assert '`#154`, `#155`, `#156`, and `#144` remain future work' not in issue_143_tasks, issue_143_tasks
  assert '`#154`, `#155`, `#156`, and `#144` remain the open follow-ups' not in issue_143_tasks, issue_143_tasks
  assert "assert 'source_advisory_count' not in summary" not in issue_164_spec, issue_164_spec
  assert 'remains separate follow-up work under `#165`' not in issue_164_spec, issue_164_spec
  assert 'preserve `ios-simulator-runtime` as `manual-review-required` and mapped to `#165`' not in issue_164_spec, issue_164_spec
  assert 'without adding a separate top-level `source_advisory_count` field' not in issue_164_tasks, issue_164_tasks
  issue_156_spec = Path('docs/specs/issues/issue-156-android-emulator-runtime-source-evaluation/spec.md').read_text(encoding='utf-8')
  assert '#173' not in issue_156_spec, 'issue-156 spec must not preserve PR #173 as still open after #165 lands'
  assert 'open spec-entry prs `#171` and `#173`' not in issue_156_spec.lower(), issue_156_spec
  print('runner-host docs/specs reflect the ios-simulator-runtime source-backed contract')
  PY
  ```
- Non-goals: No repo-wide security-doc rewrite beyond the named contradictory files.
- Hand back if: Another canonical contract file becomes false only because it encodes a separate policy decision that this runtime-only slice cannot honestly change.

## 6. Run bounded validation and hand back with honest closure semantics
- [ ] 6.1 Run `git diff --check`.
- [ ] 6.2 Re-run `python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py`.
- [ ] 6.3 Re-run `python3 -m unittest tests/scripts/test_runner_host_review_report.py`.
- [ ] 6.4 Rebuild `/tmp/runner-host-watch-summary.json` and `/tmp/runner-host-watch.md` from the live runner-host command and confirm `ios-simulator-runtime` now renders as `apple-simulator-runtime-catalog`.
- [ ] 6.5 In the PR summary/comment, say the implementation PR `Closes #165`, explicitly note that `docs-needed` still applies because canonical security docs changed, and state that `#164` and `#172` remained separate follow-up work.
- Goal: Leave QA with one honest picture of the simulator-runtime-only source-backed change, its validation evidence, and its closure boundary.
- Validation: `git diff --check && python3 -m py_compile tests/test-support/scripts/runner_host_review_report.py tests/scripts/test_runner_host_review_report.py && python3 -m unittest tests/scripts/test_runner_host_review_report.py`
- Non-goals: No manual GitHub issue mutation beyond the existing runner-host managed-issue behavior under test.
- Hand back if: The refreshed head still reports `ios-simulator-runtime` as manual-only, or the final diff no longer lets the implementation PR honestly `Closes #165`.
