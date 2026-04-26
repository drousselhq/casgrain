# Issue #124 — Runner-image and host-toolchain drift watch

- Issue: `#124`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #124`
- Follow-up contract that landed after this slice: `#129` (`Add source-rule contract for runner-host advisory evaluation`)
- Remaining later source-specific automation is now split across delivered `#143` (runner images), `#154` (Android Java), and `#156` (Android emulator runtime), the remaining Android follow-up `#155`, and later iOS follow-ups `#164` / `#165` after the Android narrowing contract in `#142`

## Why this slice exists

Already delivered on `main`:
- PR #87 added the weekly Rust dependency `cargo audit` watch.
- PR #116 hardened managed findings-issue sync and recurrence handling.
- PR #121 added the Dependabot-backed non-Cargo watch for GitHub Actions and Gradle-managed dependencies.
- PR #125 added the workflow-installed security-tooling watch for `gitleaks`, `cargo-audit`, and `cargo-deny`.

Live baseline at analyst handoff (2026-04-19 UTC, inspected on `main`):
- latest successful Android smoke run on `main`: `24600768008` (`android-emulator-smoke`, `schedule`)
  - runner preamble reported `ubuntu-24.04` image version `20260413.86.1`
  - OS reported `Ubuntu 24.04.4 LTS`
  - setup-java resolved Temurin `17.0.18+8`
  - workflow YAML still pins Gradle `8.7`
  - uploaded `emulator.json` reports device `sdk_gphone64_x86_64` / Android `14`
- latest successful iOS smoke run on `main`: `24600433713` (`ios-simulator-smoke`, `schedule`)
  - runner preamble reported `macos-15-arm64` image version `20260414.0270.1`
  - OS reported `macOS 15.7.4 (24G517)`
  - uploaded `simulator.json` reports runtime `iOS 26.2` on `iPhone 16`
  - uploaded `xcodebuild.log` shows `/Applications/Xcode_16.4.app` with the iPhoneSimulator `18.5` SDK

That means the repo already has enough deterministic evidence to identify the current runner/host surface, but it still lacks all of the following:
1. a checked-in baseline inventory for exactly which runner/host facts are being watched
2. a single machine-readable host-environment summary artifact per mobile workflow
3. a low-noise review loop that opens work only when those facts drift or the evidence contract breaks

So the next honest slice is **not** direct CVE scraping of hosted runners. It is a drift-triggered manual-review watch grounded on explicit repo-managed evidence.

## Scope of this slice

Build a repo-owned runner-host drift watch.

This slice must:
1. define the watched baseline in a checked-in repo file
2. emit explicit machine-readable host-environment summaries from both mobile smoke workflows
3. inspect the latest successful `main` run for each mobile workflow
4. compare the observed host facts against the checked-in baseline
5. render concise markdown plus machine-readable JSON
6. open/update/close exactly one managed review issue via the existing issue-sync helper

This slice is **only** the change-detection + manual-review slice.
Direct source-backed advisory evaluation for selected surfaces does not belong to this slice.
That next repo-owned follow-up landed as issue #129 for the source-rule contract; after the later Android narrowing contract in `#142`, current `main` now includes the delivered `#143` runner-images, `#154` Android Java, and `#156` Android emulator-runtime promotion slices while `#155`, `#164`, and `#165` remain the later source-specific follow-ups.

## Required implementation artifacts

### 1. Checked-in baseline inventory

Add a checked-in baseline inventory at:

- `.github/runner-host-watch.json`

The file must be the source of truth for this slice.

It must define at minimum:
- `issue_title`: `security: runner-host review needed`
- a concise `scope` string for the generated report
- one explicit entry for the Android smoke surface
- one explicit entry for the iOS smoke surface

Each platform entry must declare:
- the workflow file to inspect
- the artifact name to download
- the branch selection rule: newest successful run on `main`
- the exact watched facts that participate in drift detection
- the baseline values seeded from the current `main` evidence

Minimum watched facts:

**Android**
- runner label (`ubuntu-latest`)
- live runner image family (`ubuntu-24.04`)
- live runner image version (`20260413.86.1` at analyst handoff)
- OS version (`24.04.4` at analyst handoff)
- configured Java major (`17`)
- resolved Java version (`17.0.18+8` at analyst handoff)
- configured Gradle version (`8.7`)
- emulator/device facts needed for review (`api 34`, `sdk_gphone64_x86_64`, Android `14`)

**iOS**
- runner label (`macos-15`)
- live runner image family (`macos-15-arm64`)
- live runner image version (`20260414.0270.1` at analyst handoff)
- OS version/build (`15.7.4`, `24G517` at analyst handoff)
- Xcode app path/version (`/Applications/Xcode_16.4.app`, `16.4`)
- simulator SDK version (`18.5`)
- simulator runtime identifier/name (`com.apple.CoreSimulator.SimRuntime.iOS-26-2`, `iOS 26.2`)
- simulator device name (`iPhone 16`)

Keep the manifest intentionally small.
Do **not** turn it into a catalog of every package installed on the hosted runners.

### 2. Machine-readable host-environment artifacts

Extend both mobile smoke artifact contracts with one explicit host summary file:

- `host-environment.json`

#### Android requirements

Add `host-environment.json` to the `casgrain-android-smoke` artifact bundle.

The Android host summary must include at minimum:
- generation timestamp
- workflow/run identity
- runner label
- runner image name/version
- OS name/version
- Java distribution + resolved version
- configured Java major line
- configured Gradle version and resolved Gradle version when available cheaply
- emulator API/device/runtime facts already relevant to the Android smoke proof

Implementation rule:
- keep the existing `emulator.json` contract for runtime-facing evidence
- use `host-environment.json` for the host/runner/toolchain facts that currently only exist in logs or workflow YAML
- update `tests/test-support/scripts/validate_android_smoke_artifacts.py` so missing/malformed `host-environment.json` fails the artifact contract

#### iOS requirements

Add `host-environment.json` to the `casgrain-ios-smoke` artifact bundle.

The iOS host summary must include at minimum:
- generation timestamp
- workflow/run identity
- runner label
- runner image name/version
- OS name/version/build
- Xcode app path + version
- simulator SDK version
- simulator runtime identifier/name
- simulator device name

Implementation rule:
- keep `simulator.json` and `xcodebuild.log` as existing evidence
- use `host-environment.json` as the single normalized source the later report reads
- update the iOS workflow artifact assertions so missing `host-environment.json` fails the smoke artifact contract honestly

### 3. Reporter script

Add a new reporter script at:

- `tests/test-support/scripts/runner_host_review_report.py`

The script should follow the same style as the repo's existing reporting helpers, especially:
- `tests/test-support/scripts/cve_watch_report.py`
- `tests/test-support/scripts/dependabot_alerts_report.py`
- `tests/test-support/scripts/security_tooling_cve_watch.py`

Implementation contract:
- keep the GitHub collection layer thin and explicit
- keep the drift-evaluation logic pure enough to unit-test without live GitHub access
- prefer the existing repo pattern of `gh api` / `gh run download` over introducing a second API client stack
- inspect the newest successful `main` run per platform/workflow, not PR-branch artifacts
- consume the normalized `host-environment.json` artifact, not raw log scraping
- compare only the watched facts named in `.github/runner-host-watch.json`
- reuse `tests/test-support/scripts/cve_watch_issue_sync.py` instead of inventing a new issue-upsert path

### 4. Weekly cve-watch integration

Extend `.github/workflows/cve-watch.yml` with one dedicated runner-host review job.

That job must:
1. read `.github/runner-host-watch.json`
2. fetch the newest successful `main` run for:
   - `.github/workflows/android-emulator-smoke.yml`
   - `.github/workflows/ios-simulator-smoke.yml`
3. download the configured artifact from each run
4. execute `runner_host_review_report.py`
5. append the rendered markdown to `$GITHUB_STEP_SUMMARY`
6. pass the summary JSON + markdown into `cve_watch_issue_sync.py`

Issue-sync rule:
- `alert=true` means `manual-review-required`
- `advisory_count` is the count of changed or missing watched facts requiring review
- `alert=false` means `no review-needed`

### 5. Fixtures and tests

Add deterministic fixtures under:

- `tests/test-support/fixtures/runner-host-watch/`

Required fixture cases:
- `baseline-match` — current honest `main` shape, no drift
- `android-drift` — at least one Android watched fact changed (for example runner image or resolved Java version)
- `ios-drift` — at least one iOS watched fact changed (for example Xcode or runtime)
- `missing-evidence` — one platform lacks a readable `host-environment.json`

Add focused tests at:

- `tests/scripts/test_runner_host_review_report.py`

The tests should import the script module the same way the repo already tests the other reporting helpers.

### 6. Required repo docs updates

The later implementation PR must explicitly update these canonical repo docs:

- `docs/development/cve-watch-operations.md`
- `docs/development/security-automation-plan.md`
- `docs/development/security-owasp-baseline.md`

Those docs updates must say, in repo-owned language rather than issue-only shorthand:
- which runner/host facts are watched from `.github/runner-host-watch.json`
- which evidence artifacts feed the review (`host-environment.json` for both mobile smoke workflows, with `emulator.json`, `simulator.json`, and `xcodebuild.log` remaining supporting evidence where relevant)
- that the weekly `cve-watch` scope/output now includes this runner-host drift watch as a fourth low-noise review lane, and that drift or missing/unreadable evidence opens/updates the managed `security: runner-host review needed` issue via the existing sync flow
- that any blanket wording claiming `manual-review-required` outcomes never open managed issues, or that `cve-watch` still has only three low-noise slices, is updated or removed so the canonical docs stay internally consistent
- that this slice opens review only when watched facts drift or required evidence is missing/unreadable
- that the result is drift-triggered **manual review**, not direct runner-image / host-toolchain advisory automation in this slice
- that the repo-owned source-rule contract landed in follow-up issue `#129`, and any later source-backed advisory automation now advances via delivered slices `#143` (`runner-images`), `#154` (`android-java`), and `#156` (`android-emulator-runtime`) plus split follow-up issues `#155`, `#164`, and `#165` rather than staying attached to one umbrella tracker

The spec should leave no room for a later implementation PR to claim completion while keeping those canonical docs ambiguous or stale.

## Reporter input/output contract

### Live inputs

The reporter must be able to evaluate the live repo state for:
- repo: `drousselhq/casgrain`
- Android workflow: `android-emulator-smoke.yml`
- Android artifact: `casgrain-android-smoke`
- iOS workflow: `ios-simulator-smoke.yml`
- iOS artifact: `casgrain-ios-smoke`
- baseline file: `.github/runner-host-watch.json`

### Required evaluation rules

The reporter must:
1. choose the newest successful run on `main` for each configured workflow
2. fail closed into `manual-review-required` when a required run, artifact, or host summary is missing/unreadable
3. compare only the watched facts declared in the baseline inventory
4. treat any mismatch between baseline and observed value as a review-triggering change
5. treat a missing observed fact the same as drift: review-required, not silent success
6. keep Android and iOS results separate inside the output even when the top-level verdict is shared
7. avoid historical trend logic beyond selecting the newest successful `main` run per workflow

### Required JSON summary shape

The exact field names may vary slightly, but the summary JSON must contain at least:
- generation timestamp
- repo identity
- `issue_title`
- `alert` boolean
- `advisory_count` integer = count of changed/missing watched facts
- top-level verdict: `no review-needed` or `manual-review-required`
- the evaluated Android run ID/URL
- the evaluated iOS run ID/URL
- per-platform observed facts
- per-platform changed facts / missing evidence entries
- a short machine-readable reason when review is required

### Required markdown output

The markdown must be concise and operational.

It must include:
- the managed report marker `<!-- cve-watch-report -->`
- one-line verdict first
- one short section for Android
- one short section for iOS
- the evaluated run IDs/URLs
- the watched facts that changed or the explicit missing-evidence reason
- a statement that this slice is drift-triggered manual review, not direct advisory evaluation

## Bounded design decisions

### In scope for the implementation PR
- one checked-in baseline inventory
- one host-summary artifact addition for Android smoke
- one host-summary artifact addition for iOS smoke
- one new reporter script
- one new unit-test module plus a small fixture set
- one `cve-watch` job integration
- explicit docs updates to `docs/development/cve-watch-operations.md`, `docs/development/security-automation-plan.md`, and `docs/development/security-owasp-baseline.md` as specified above

### Explicit non-goals
- **no** scraping of every package preinstalled on hosted runners
- **no** direct CVE lookups against GitHub runner-image release notes in this slice
- **no** widening beyond the Android and iOS smoke workflows
- **no** product/runtime behavior changes in Casgrain itself
- **no** dependence on PR-branch artifacts for the review decision
- **no** second parallel issue-management workflow outside `cve_watch_issue_sync.py`

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
python3 -m py_compile \
  tests/test-support/scripts/runner_host_review_report.py \
  tests/scripts/test_runner_host_review_report.py
python3 -m unittest tests/scripts/test_runner_host_review_report.py
python3 - <<'PY'
import yaml
from pathlib import Path
for path in [
    Path('.github/workflows/android-emulator-smoke.yml'),
    Path('.github/workflows/ios-simulator-smoke.yml'),
    Path('.github/workflows/cve-watch.yml'),
]:
    yaml.safe_load(path.read_text(encoding='utf-8'))
    print(f'YAML_OK {path}')
PY
python3 tests/test-support/scripts/runner_host_review_report.py \
  --repo drousselhq/casgrain \
  --baseline .github/runner-host-watch.json \
  --android-workflow android-emulator-smoke.yml \
  --android-artifact casgrain-android-smoke \
  --ios-workflow ios-simulator-smoke.yml \
  --ios-artifact casgrain-ios-smoke \
  --summary-out /tmp/runner-host-watch-summary.json \
  --markdown-out /tmp/runner-host-watch-report.md
```

The live invocation above must succeed and render either:
- `no review-needed` when the latest successful `main` artifacts still match the checked-in baseline, or
- `manual-review-required` when drift or missing evidence is real.

## Completion boundary

The implementation PR for this spec should be able to close `#124` because it completes the immediate low-noise runner-host review slice.

After that PR merges:
- the weekly watch will keep manual review explicit only when the hosted environment drifts
- issue #129 captured the repo-owned source-rule contract on top of this baseline
- later source-specific automation now advances through delivered slices `#143` / `#154` / `#156`, the remaining Android follow-up `#155`, and split iOS follow-ups `#164` / `#165` rather than returning to one umbrella issue
