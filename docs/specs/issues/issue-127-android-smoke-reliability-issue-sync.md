# Issue #127 — Android smoke reliability-window issue sync

- Issue: `#127`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Closes #127`
- The later live-evidence outcome is advisory only; the repo does not use a separate qualification-tracker issue.

## Why this slice exists

Already delivered on `main`:
- issue #122 landed the repo-owned Android smoke reliability-window reporter at `tests/test-support/scripts/android_smoke_reliability_window.py`
- a fresh live invocation at analyst handoff (`2026-04-19T06:36Z`) still reports `verdict=not_qualified`
- current live counts from that invocation:
  - `successful_run_count=16`
  - `pull_request_success_count=16`
  - `schedule_main_success_count=0`
  - `reasons=["schedule_main_runs_below_threshold"]`
- current blocker context remains run `24611423606` with `failure_class=artifact-contract-breach`

At shaping time, the repo could already evaluate Android smoke reliability honestly, but it still had **no repo-owned issue sync** that turned the report into durable GitHub state.

The original issue mixed:
1. the immediate tooling gap — sync the existing report into GitHub issue state
2. the later wall-clock outcome — wait for enough scheduled `main` runs to accumulate and then record the first qualified window

This issue was narrowed to **only** the first concern. The later live-evidence outcome remains advisory only and does not use a separate tracker issue.

## Scope of this slice

Build a repo-owned sync path around the existing Android smoke reliability report.

This slice must:
1. consume the existing summary JSON plus markdown emitted by `android_smoke_reliability_window.py`
2. synchronize the existing report output into durable GitHub state
3. avoid spurious blocker issues when the report is still only short on scheduled `main` runs
4. open or update a bounded blocker issue when the synced report later surfaces a concrete new blocker beyond simple schedule shortfall
5. stay testable offline from saved fixtures plus one honest dry-run against the live repo state

This slice is **not** the later qualification judgment itself. The automation added here should make that later judgment durable and boring, but there is no separate qualification tracker issue.

## Required implementation artifacts

### 1. Issue-sync helper

Add a new script at:

- `tests/test-support/scripts/android_smoke_issue_sync.py`

The script should follow the same narrow-sync style as:
- `tests/test-support/scripts/cve_watch_issue_sync.py`

Implementation contract:
- accept the repo, summary JSON path, and markdown file path as explicit inputs
- use a thin `gh`-based mutation layer rather than a second GitHub client stack
- support a `--dry-run` mode that prints the planned action without mutating GitHub
- use explicit HTML comment markers so the automation can recognize tracker/blocker bodies it owns on later runs
- keep plan selection pure enough to unit-test without live GitHub access

Required report behavior:
- if the report is `not_qualified` **only** because `schedule_main_runs_below_threshold`, keep the reporter output advisory and do not open a separate tracker issue
- if the report is `qualified`, record the qualifying run IDs/event counts in the report output and stop surfacing the advisory shortfall state
- if the report is `not_qualified` and the report identifies a concrete blocker beyond plain schedule shortfall, update the report output with that blocker summary and link the blocker issue created/reused below

### 2. Managed blocker issue behavior

The sync helper must also support a bounded blocker path.

Required blocker rules:
- when the synced report later surfaces a concrete new blocker beyond simple schedule shortfall, create or reopen **one** bounded blocker issue for that blocker class instead of silently leaving GitHub issue state ambiguous
- the blocker issue must:
  - be labeled `enhancement` and `devops`
  - include the blocker run ID, run URL, report verdict/reasons, and machine-readable `failure_class` when present
  - include a marker that lets later sync runs update the same blocker issue instead of churning duplicates
- the shaping-time known state (`schedule_main_runs_below_threshold` with historical blocker run `24611423606`) must **not** open a blocker issue by itself; it should stay advisory-only unless a previously managed blocker issue needs to close because the report no longer justifies keeping it open

A simple deterministic title shape is acceptable, for example:
- `android-smoke: unblock reliability window after <failure_class>`

### 3. Deterministic fixtures

Add checked-in sync fixtures under:

- `tests/test-support/fixtures/android-smoke/reliability-issue-sync/`

Required fixture cases:
- `schedule-shortfall.*` modeling the shaping-time honest live state:
  - `verdict=not_qualified`
  - `reasons=["schedule_main_runs_below_threshold"]`
  - run `24611423606`
  - `failure_class=artifact-contract-breach`
  - expected plan: tracker-free advisory no-op when no managed blocker issue exists, or close the matching managed blocker issue if one is still open
- `qualified.*` modeling a future valid window:
  - `verdict=qualified`
  - at least 10 successful runs
  - at least 3 `schedule` runs on `main`
  - at least 3 `pull_request` runs
  - expected plan: remain tracker-free and close any matching managed blocker issue that is still open
- `blocker.*` modeling a future non-qualified state with a concrete new blocker:
  - expected plan: create/reopen/update exactly one bounded blocker issue for that blocker class

The fixture format does **not** need to mirror raw GitHub API payloads. It should instead match the sync helper's normalized plan inputs so tests stay small and deterministic.

### 4. Sync tests

Add focused tests at:

- `tests/scripts/test_android_smoke_issue_sync.py`

The tests should verify:
- pure plan selection for the three required fixture cases
- marker-based issue selection / reuse behavior
- dry-run output for each decision path
- close/update/reopen behavior without requiring live GitHub access

### 5. Workflow integration

Update:

- `.github/workflows/android-emulator-smoke.yml`

Workflow contract for this slice:
- keep the existing smoke execution and artifact upload path intact
- add a follow-on reliability-sync path that runs the existing reporter and then the new issue-sync helper
- run the issue-mutating sync path only on events where repo-owned state should move (`schedule` and `workflow_dispatch` on the repository), never on ordinary PR validation runs
- expose the rendered reliability markdown in the workflow summary so humans can inspect the same output the sync consumed
- pass `GH_TOKEN: ${{ github.token }}` (or equivalent) only to the sync step that actually mutates issues

A separate job inside the same workflow is acceptable if it keeps the sync logic clearly isolated from the expensive emulator execution.

## Required docs / runbook updates

The later implementation PR must update:

- `docs/development/automation-agent-operations.md`

That doc update must explicitly state:
- the Android smoke workflow now has a repo-owned reliability issue-sync path
- the repo does not use a separate live tracker issue for qualification state
- the sync may create or reuse one bounded blocker issue when the report surfaces a concrete new blocker
- this slice does **not** promote Android to a required merge gate and did **not** replace the broader docs/policy work that was still tracked in `#80` at shaping time

Do **not** broaden this slice into a full `docs/validation.md` policy rewrite. At shaping time, that broader validation/gate work still lived under `#80` and `#79`; current `main` has since completed both closed follow-ups.

## Bounded design decisions

### In scope for the implementation PR
- one new issue-sync helper script
- one new sync unit-test module
- one small checked-in sync fixture set
- one bounded update to `.github/workflows/android-emulator-smoke.yml`
- one bounded update to `docs/development/automation-agent-operations.md`

### Explicit non-goals
- **no** reimplementation or threshold changes in `android_smoke_reliability_window.py`
- **no** manual prompt-time browsing as the persistence mechanism
- **no** Android branch-protection / merge-gate promotion here (that later closed under `#79`)
- **no** broad Android evidence/docs parity rewrite here (that later closed under `#80`)
- **no** attempt to backfill pre-failure runs into the current qualifying window
- **no** generic workflow-health issue manager for unrelated jobs

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
python3 -m py_compile \
  tests/test-support/scripts/android_smoke_issue_sync.py \
  tests/scripts/test_android_smoke_issue_sync.py
python3 -m unittest tests/scripts/test_android_smoke_issue_sync.py
python3 - <<'PY'
import pathlib, yaml
path = pathlib.Path('.github/workflows/android-emulator-smoke.yml')
yaml.safe_load(path.read_text())
print(path)
PY
python3 tests/test-support/scripts/android_smoke_reliability_window.py \
  --repo drousselhq/casgrain \
  --workflow android-emulator-smoke.yml \
  --artifact-name casgrain-android-smoke \
  --summary-out /tmp/android-smoke-reliability-window.json \
  --markdown-out /tmp/android-smoke-reliability-window.md
python3 tests/test-support/scripts/android_smoke_issue_sync.py \
  --repo drousselhq/casgrain \
  --summary-json /tmp/android-smoke-reliability-window.json \
  --markdown-file /tmp/android-smoke-reliability-window.md \
  --dry-run
```

On current `main`, the live dry-run still plans a **tracker-free no-op** action (`report_kind=tracking_only`, `blocker.action=noop`), but the report is now not qualified for multiple threshold reasons (`total_runs_below_threshold`, `schedule_main_runs_below_threshold`, and `pull_request_runs_below_threshold`) rather than only the schedule-`main` shortfall captured at shaping time.

## Completion boundary

The implementation PR for this spec should be able to close `#127` because it finishes the immediate repo-controlled sync/tooling slice.

After that PR merges:
- the live evidence outcome remains advisory only; any concrete blocker issue is linked directly from the report output
- at the time this slice landed, issues `#80` and `#79` remained the separate Android readiness follow-ups rather than qualification-tracker work; current `main` has since completed both closed follow-ups
