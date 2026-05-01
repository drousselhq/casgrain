# Issue #129 — Runner-host advisory source-rule contract

- Issue: `#129`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #129`
- Follow-up source-specific slices after this contract lands:
  - `#143` — delivered GitHub-hosted runner image release-metadata slice
  - `#142` — Android source-rule split contract that narrows the original Android umbrella into `#154`, `#155`, and `#156`
  - `#154` — Android Java host version facts
  - `#155` — Android Gradle host version facts
  - `#156` — Android emulator-runtime host facts
  - `#164` / `#165` — historical iOS Xcode / simulator-runtime follow-up issue numbers for the current combined placeholder

## Why this slice exists

Already delivered on `main`:
- PR #130 added the spec entry for the runner-host drift-watch baseline.
- PR #138 added the shipped drift-triggered runner-host review path:
  - `.github/runner-host-watch.json`
  - `tests/test-support/scripts/runner_host_review_report.py`
  - `host-environment.json` in both mobile smoke artifact contracts
  - the runner-host job inside `.github/workflows/cve-watch.yml`
- A fresh live invocation at analyst handoff (`2026-04-19T21:37:05Z`) against current `main` reports:
  - Android run `24638847602` → `no review-needed`
  - iOS run `24638847580` → `no review-needed`
  - top-level `verdict=no review-needed`
  - `reason=baseline-match`
  - no `security: runner-host review needed` report is currently open from drift or missing evidence

That means the repo already owns the **drift / missing-evidence** slice honestly.

What still remains is narrower than the original umbrella issue wording. The original issue mixed three different future automation concerns that do **not** share one honest implementation seam:
1. GitHub-hosted runner image sources
2. Android Java / Gradle / emulator-runtime sources
3. iOS Xcode / simulator-runtime sources

Current `main` has no checked-in source-rule contract that records, in repo-owned machine-readable form:
- which runner-host surface groups still remain `manual-review-required`
- which watched fact paths belong to each future source-specific slice
- which follow-up ownership shape owns each later promotion
- how those future promotions should continue to map into the existing runner-host report flow

Without that contract, later source-backed work would either hardcode policy in scripts/docs or widen one issue into several unrelated source integrations.

## Scope of this slice

Add a repo-owned source-rule contract around the **existing** runner-host drift watch.

This slice must:
1. keep the current drift / missing-evidence alert semantics unchanged
2. make the current source-evaluation status explicit for each runner-host surface group
3. bind each surface group to explicit follow-up ownership for later source-backed automation, while allowing the still-combined iOS placeholder on current `main` to preserve historical `follow_up_issues: [164, 165]`
4. keep the reporting / docs truthful that this contract initially shipped a drift-triggered live runner-host workflow-summary report path, and that later main may promote bounded source-backed slices like `#143` without widening the remaining groups
5. stay testable from checked-in manifests plus deterministic fixtures

This slice is **not** the later source-backed automation itself. It is the repo-owned contract that makes the later source-specific work bounded and auditable.

## Required implementation artifacts

### 1. Checked-in source-rule inventory

Add a checked-in manifest at:

- `.github/runner-host-advisory-sources.json`

The file is the source of truth for this slice.

It initially shipped three umbrella source groups, but current `main` now carries five explicit groups after the later Android narrowing and delivered promotions:

1. `runner-images`
   - covers the watched runner-image / OS facts that currently come from GitHub-hosted runner evidence for Android and iOS
2. `android-java`
   - covers the Android watched Java host version facts
3. `android-gradle`
   - covers the Android watched Gradle host version facts
4. `android-emulator-runtime`
   - covers the Android watched emulator runtime facts already inventoried in `.github/runner-host-watch.json`
5. `ios-xcode-simulator`
   - covers the watched iOS Xcode / simulator-runtime host facts and remains the still-combined placeholder on current `main`

Each group entry must declare at minimum:
- a stable group key
- the human-facing surface name
- the platform(s) it applies to
- the exact watched fact paths it owns from `.github/runner-host-watch.json`
- the current rule kind
- the current rationale
- the intended report behavior for future actionable findings
- the follow-up ownership for later source-backed automation (`follow_up_issue` for singular ownership or `follow_up_issues` for the still-combined iOS placeholder)
- a short `candidate_source` description naming the future authoritative machine-readable source class to evaluate later

Current-slice rule requirement:
- the honest initial rule kind for every group in this contract slice was `manual-review-required`; current `main` now promotes `runner-images` via `#143`, `android-java` via `#154`, `android-gradle` via `#155`, and `android-emulator-runtime` via `#156`, while the current combined iOS placeholder remains the manual-review follow-up
- the rationale must explain why the repo is not yet claiming trustworthy source-backed evaluation for that group on current `main`
- the manifest now points to:
  - `#143` for `runner-images`
  - `#154` for `android-java`
  - `#155` for `android-gradle`
  - `#156` for `android-emulator-runtime`
  - historical iOS follow-up issue numbers `#164` / `#165` for the current combined `ios-xcode-simulator` placeholder
- historical note: this current five-group shape grew out of the initial combined Android ownership that `#142` later narrowed into the delivered `#154` / `#155` / `#156` slices

Validation rule:
- the manifest must fail closed if any listed watched fact path does not exist in `.github/runner-host-watch.json`
- do not allow free-floating source groups that are not anchored to the current watched runner-host contract

### 2. Runner-host report integration

Update:

- `tests/test-support/scripts/runner_host_review_report.py`

Implementation contract for this slice:
- read and validate `.github/runner-host-advisory-sources.json`
- include a machine-readable summary of source-rule status per group in the emitted JSON summary
- include a concise markdown section that states which groups are still `manual-review-required`, and on current `main` also reflects that `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` are the delivered source-backed promotions
- keep the current top-level drift logic authoritative for alerting in this slice
- do **not** change the existing `alert`, `advisory_count`, `verdict`, or report-opening semantics merely because the new source-rule inventory exists
- if the new manifest is missing, malformed, or references unknown watched fact paths, fail closed rather than silently dropping the source-rule story

Required reporting behavior:
- current clean runs must still report `no review-needed` when the baseline matches
- the new source-rule section must make it explicit that this slice introduced the source-rule inventory contract, while later delivered follow-up slices now add source-backed evaluation on current `main`
- the report must not imply broader source-backed advisory evaluation than current `main` actually ships; today that means `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` are active while only the combined iOS placeholder stays manual-only

### 3. Tests and fixtures

Add or extend deterministic fixtures under a dedicated path such as:

- `tests/test-support/fixtures/runner-host-watch/source-rules/`

Required fixture cases:
- valid manifest covering the historical three-group baseline with only `manual-review-required` rules
- current-main-compatible manifest covering the later five-group shape, including singular `follow_up_issue` ownership for `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime`, plus historical `follow_up_issues: [164, 165]` on the still-combined iOS placeholder
- manifest references an unknown watched fact path
- manifest omits required follow-up ownership
- manifest omits the rationale for a `manual-review-required` rule

Add focused tests in either:
- `tests/scripts/test_runner_host_review_report.py`
- or one small adjacent test module dedicated to the new source-rule manifest

The tests must verify:
- manifest normalization / validation
- failure-closed behavior for bad source-rule input
- rendered JSON/markdown includes the source-rule summary
- the existing drift verdict remains unchanged for the baseline-match fixture/live shape
- the source-rule summary stays truthful about the current five-group contract, including historical `follow_up_issues: [164, 165]` on the still-combined iOS placeholder

### 4. Canonical docs updates

The implementation PR for this spec must update these docs:
- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`

Those docs updates must explicitly say:
- current shipped runner-host automation now evaluates drift / missing evidence plus the delivered source-backed promotions for `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime`
- `.github/runner-host-advisory-sources.json` is the repo-owned contract for later source-backed promotion decisions
- the current source groups on `main` keep `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` delivered while the combined iOS placeholder remains the `manual-review-required` follow-up until its later slices land
- future actionable advisory automation must continue to report through the existing runner-host workflow-summary reporting path rather than inventing parallel report titles
- later source-specific promotion work is split across delivered `#143` / `#154` / `#155` / `#156` plus the still-combined iOS placeholder, which continues to render historical `#164` / `#165` references after the narrowing contract in `#142` lands

## Acceptance criteria

1. Current `main` still reports the same honest runner-host drift verdicts as before this slice; the new work does not silently alter alert semantics.
2. The repo gains a checked-in source-rule inventory that binds each current runner-host surface group to explicit watched fact paths and truthful follow-up ownership, using singular `follow_up_issue` fields for the delivered groups and historical `follow_up_issues: [164, 165]` on the still-combined iOS placeholder.
3. The runner-host report output now makes the current source-rule status visible and testable instead of leaving it implicit in issue prose.
4. The canonical security docs stop treating future source-backed promotion as an unstructured umbrella and instead point at the checked-in source-rule contract plus the delivered `#143` / `#154` / `#155` / `#156` slices, while treating `#164` / `#165` only as historical follow-up issue numbers on the still-combined iOS placeholder.
5. The implementation PR for this slice can honestly say `Closes #129` because it finishes the immediate repo-controlled contract/plumbing work, while the actual source integrations remain in follow-up issues.

## Bounded design decisions

### In scope for the implementation PR
- one new checked-in source-rule manifest
- one bounded update to `runner_host_review_report.py`
- one small fixture/test addition for the source-rule manifest
- bounded docs updates in the three named canonical security docs

### Explicit non-goals
- **no** live external advisory queries in this slice
- **no** new report title or parallel workflow-summary reporting path
- **no** changes to `.github/runner-host-watch.json` watched-fact coverage beyond any tiny schema link needed for validation
- **no** direct advisory implementation for GitHub-hosted runner images (`#143`)
- **no** direct advisory implementation for Android host surfaces in this slice; the later narrowing contract in `#142` splits those source-backed follow-ups into `#154`, `#155`, and `#156`
- **no** direct advisory implementation for iOS Xcode / simulator-runtime surfaces still represented on current `main` only by the combined placeholder and its historical `#164` / `#165` references
- **no** broad scraping of hosted-runner package inventories or release-note text

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
assert summary['verdict'] == 'no review-needed', summary
assert summary['reason'] == 'baseline-match', summary
assert 'source_rules' in summary or 'source_rule_groups' in summary, summary
print('runner-host source-rule summary present')
PY
```

The live invocation above should still report the same clean drift verdict on current `main`, while also exposing the new source-rule state.

## Completion boundary

The implementation PR for this spec should be able to close `#129` because it finishes the immediate repo-owned source-rule contract and reporting/doc plumbing.

After that PR merges:
- `#143` remains the bounded GitHub-hosted runner image source-backed automation already delivered on current `main`
- `#142` initially owned the Android umbrella follow-up, and the later narrowing contract in `#142` then split that Android work into delivered `#154`, `#155`, and `#156`
- `#154` is now the delivered bounded Android Java host version source-backed automation after that narrowing landed
- delivered `#155` now covers the Android Gradle host version source-backed automation after that narrowing lands
- the current combined `ios-xcode-simulator` placeholder on current `main` still renders the historical iOS follow-up issue numbers `#164` / `#165`, even though both issues are already closed
- the shipped runner-host workflow-summary report path on `main` now includes the delivered `runner-images`, `android-java`, `android-gradle`, and `android-emulator-runtime` source-backed exceptions while the remaining combined iOS placeholder stays manual-review-only
