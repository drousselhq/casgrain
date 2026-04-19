# Issue #122 — Android smoke reliability-window report

- Issue: `#122`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #122`
- Follow-up after this slice lands: `#127` (`Record Android smoke qualifying window after report tooling lands`)

## Why this slice exists

Already delivered on `main`:
- PR #105 added the first Android boot-readiness hardening slice.
- PR #117 added stable Android runner `failure_class` values and tightened the evidence contract.
- PR #123 kept empty/malformed `uiautomator` dumps inside the structured `ui-dump-failure` path and closed #78.

Live baseline at analyst handoff (2026-04-19 UTC):
- last non-success `android-emulator-smoke` run: `24611423606`
- that run's uploaded `evidence-summary.json` reports `failure_class=artifact-contract-breach`
- current consecutive success streak since that run: `15` successful `pull_request` runs
- current scheduled-`main` count inside that streak: `0`

That means the original post-hardening reliability question is **not yet answerable from a qualified window**, but it is now narrow enough to turn into one bounded DevOps slice: add deterministic report tooling so the repo can answer the question honestly from run history and uploaded artifacts instead of from manual browsing.

## Scope of this slice

Build a repo-owned Android smoke reliability-window reporter.

This slice must:
1. inspect live `android-emulator-smoke` run history for `drousselhq/casgrain`
2. inspect the uploaded `casgrain-android-smoke` `evidence-summary.json` for the evaluated runs
3. decide whether the latest post-failure streak qualifies
4. emit both machine-readable JSON and concise markdown output
5. stay fully testable offline from saved fixtures

This slice is **only** the reporter/tooling slice. The later operational judgment after enough new scheduled runs accrue belongs to follow-up issue #127.

## Required implementation artifacts

### 1. Reporter script

Add a new script at:

- `tests/test-support/scripts/android_smoke_reliability_window.py`

The script should follow the same style as the existing repo reporting helpers such as:
- `tests/test-support/scripts/coverage_regression_check.py`
- `tests/test-support/scripts/cve_watch_report.py`
- `tests/test-support/scripts/dependabot_alerts_report.py`

Implementation contract:
- keep the GitHub collection layer thin and explicit
- keep the evaluation logic pure enough to unit-test without live GitHub access
- prefer the existing repo pattern of `gh run list` + `gh run download` over introducing a second API client stack
- consume the already-uploaded `casgrain-android-smoke` artifact rather than re-inferring status from logs

### 2. Deterministic fixtures

Add checked-in synthetic fixtures under:

- `tests/test-support/fixtures/android-smoke/reliability-window/`

Required fixture cases:
- `not-qualified.json` (or equivalent fixture set) modeling the current honest shape:
  - last non-success run `24611423606`
  - blocker `failure_class=artifact-contract-breach`
  - 15 consecutive successful `pull_request` runs
  - 0 qualifying scheduled `main` runs
- `qualified.json` (or equivalent fixture set) modeling a valid future window with:
  - at least 10 consecutive successful runs
  - at least 3 `schedule` runs on `main`
  - at least 3 `pull_request` runs
  - no `artifact-contract-breach` in the evaluated window

The fixture format does **not** need to mimic raw GitHub REST payloads exactly. It should instead match the reporter's normalized internal shape so tests stay small and deterministic.

### 3. Script tests

Add focused tests at:

- `tests/scripts/test_android_smoke_reliability_window.py`

The tests should import the script module the same way the repo already tests other reporting utilities.

## Reporter input/output contract

### Live collection inputs

The reporter must be able to evaluate the live repo state for:
- repo: `drousselhq/casgrain`
- workflow: `android-emulator-smoke.yml`
- artifact name: `casgrain-android-smoke`

A thin live mode may call `gh` directly, but the evaluation logic should operate on a normalized in-memory representation that can also be loaded from fixtures.

### Required evaluation rules

The reporter must:
1. look at the newest runs first
2. identify the newest consecutive successful streak since the first older non-success run
3. count only runs from that leading streak toward qualification
4. require all of the following for `qualified`:
   - `successful_run_count >= 10`
   - `schedule_main_success_count >= 3`
   - `pull_request_success_count >= 3`
5. treat the first older non-success run as the current blocker context when the window is not yet qualified
6. read that blocker's uploaded `evidence-summary.json` when available and surface its `failure_class`
7. if the blocker artifact or summary is missing/unreadable, surface that honestly as a missing-summary / `artifact-contract-breach`-style blocker instead of inventing a class
8. never backfill older pre-failure successes into the current qualifying window

### Required JSON summary shape

The exact field names may vary slightly, but the JSON output must contain at least:
- repo/workflow identity
- generation timestamp
- qualification thresholds
- top-level verdict: `qualified` or `not_qualified`
- current streak counts broken down by total / `schedule` on `main` / `pull_request`
- ordered run IDs (and preferably URLs) for the evaluated streak
- the last non-success run ID/URL/event/conclusion when present
- the blocker `failure_class` when present
- a short machine-readable reason when the bar is not yet met

### Required markdown output

The markdown output should be concise and operational.

It must include:
- one-line verdict first
- streak counts (`total`, `schedule on main`, `pull_request`)
- the threshold being enforced
- the evaluated streak run IDs
- when not qualified, the blocker run ID and blocker `failure_class`
- no speculative narrative beyond the evidence

## Bounded design decisions

### In scope for the implementation PR
- one new reporter script
- one new unit-test module
- one small checked-in fixture set for the reporter
- any tiny supporting helper refactor needed inside the reporter itself

### Explicit non-goals
- **no** branch-protection or merge-gate promotion work here
- **no** broad docs/validation policy rewrite here (tracked by #80)
- **no** new Android runner hardening here unless the reporter cannot read the already-shipped artifact contract at all
- **no** widening into generic workflow analytics for unrelated CI jobs
- **no** dependence on prompt-time human inspection of Actions history

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
python3 -m py_compile \
  tests/test-support/scripts/android_smoke_reliability_window.py \
  tests/scripts/test_android_smoke_reliability_window.py
python3 -m unittest tests/scripts/test_android_smoke_reliability_window.py
python3 tests/test-support/scripts/android_smoke_reliability_window.py \
  --repo drousselhq/casgrain \
  --workflow android-emulator-smoke.yml \
  --artifact-name casgrain-android-smoke \
  --summary-out /tmp/android-smoke-reliability-window.json \
  --markdown-out /tmp/android-smoke-reliability-window.md
```

The live invocation above should currently produce a **not qualified** result until enough new scheduled `main` runs accumulate.

## Completion boundary

The implementation PR for this spec should be able to close `#122` because it finishes the immediate tooling slice.

After that PR merges:
- issue #127 becomes the place where automation or maintainers record the first actual qualified window (or open the next blocker issue)
- issues #80 and #79 stay blocked on that later evidence, not merely on the existence of the reporter
