# Issue #79 — Promote `android-smoke` to a required merge gate on `main`

- Issue: `#79`
- Spec mode: `technical change contract`
- Expected implementation PR linkage: `Part of #79`
- Upstream slice already landed on `main`: `#80` (`Retire stale Android tracker sync path and align the Android smoke contract`)
- Current follow-up on top of the shipped required Android gate: `#135` (`Freeze the shared iOS/Android vertical-slice contract`)

## Why this slice exists

Already delivered on `main`:
- PR #104 added the first Android artifact-bundle validator and removed misleading partial-evidence paths.
- PR #117 added stable Android smoke `failure_class` values and tightened the evidence contract.
- PR #123 kept empty or malformed `uiautomator` dumps inside the structured `ui-dump-failure` path.
- PR #134 added the repo-owned Android reliability report + issue-sync flow.
- PR #160 retired the stale dedicated tracker-sync path so Android reliability state no longer depends on live tracker issue `#132`.

Live baseline at analyst handoff (`2026-04-21` UTC):
- the active branch ruleset named `main-protection-ruleset` still requires `validate`, `coverage`, `gitleaks`, `cargo-audit`, `cargo-deny-policy`, `analyze (actions)`, `analyze (rust)`, and `ios-smoke`, but it does **not** require `android-smoke`
- `.github/workflows/android-emulator-smoke.yml` still uses `pull_request.paths`, so unrelated PRs produce no `android-smoke` status context at all
- `.github/workflows/ios-simulator-smoke.yml` already follows the required-check-safe pattern: it runs on every PR, self-decides whether the expensive simulator path is needed, and still reports `ios-smoke`
- canonical repo docs still describe Android as advisory rather than required, including `docs/validation.md`, `docs/specs/casgrain-product-spec.md`, `docs/development/test-pyramid-and-runtime-contracts.md`, `docs/development/merge-and-validation-policy.md`, and `docs/development/security-owasp-baseline.md`

The honest remaining gap is therefore no longer Android reliability plumbing. The repo already has a real emulator-backed Android lane with stable artifact/report contracts; what remains is promoting that existing lane into a branch-protection-safe required merge gate.

## Scope of this slice

Promote the existing Android smoke lane from advisory evidence to a required merge gate on `main`.

This slice must:
1. make `android-smoke` report on every pull request without paying the emulator cost for unaffected diffs
2. preserve the real emulator-backed Android smoke run for Android/shared-runtime changes and for repo-owned `main` / scheduled events
3. reconcile the canonical docs/spec wording from `Android is advisory` to `Android is a required merge gate`
4. update the live `main-protection-ruleset` required status checks to include `android-smoke` once the always-reporting workflow head is safe to enforce

## Required implementation artifacts

### 1. Android workflow trigger + skip contract

Update:
- `.github/workflows/android-emulator-smoke.yml`
- `tests/scripts/test_mobile_smoke_workflow_triggers.py`

Implementation contract:
- keep `jobs.smoke.name` exactly `android-smoke` so the required-check context stays stable
- stop relying on `pull_request.paths` alone for PR execution; the workflow must run on every PR so the required status context always exists
- add in-job change detection that mirrors the current Android/shared-runtime surface list already expressed in the workflow trigger paths
- when the PR is unaffected, report success with an explicit skip message and do **not** build the fixture APK, boot an emulator, or upload smoke artifacts
- when the PR is affected, preserve the current real emulator-backed smoke path, artifact validation, and machine-readable artifact contract
- keep the existing `push`, `schedule`, `workflow_dispatch`, reliability-report, and issue-sync behavior intact unless the implementation proves a narrower edit is impossible

### 2. Canonical docs / spec / policy reconciliation

Update:
- `docs/validation.md`
- `docs/specs/casgrain-product-spec.md`
- `docs/development/test-pyramid-and-runtime-contracts.md`
- `docs/development/merge-and-validation-policy.md`
- `docs/development/security-owasp-baseline.md`

Contract:
- state that both `ios-smoke` and `android-smoke` are required merge gates on `main`
- explain that both mobile smoke workflows always report a PR status context but self-skip the expensive device work when the PR does not touch their owned surface area
- remove stale wording that says Android is advisory, non-required, or only a debugging lane, including the current advisory language in `docs/development/merge-and-validation-policy.md`
- preserve the already-landed truth that Android no longer uses a separate reliability tracker issue; concrete Android defects should still be tracked directly as bounded issues

### 3. Live ruleset promotion

Update live GitHub repo state for the active `main-protection-ruleset`.

Ruleset contract:
- add `android-smoke` to the required status-check list without removing any existing required contexts
- preserve strict up-to-date checks, linear history, required conversation resolution, and the rest of the current protection policy
- apply the ruleset change only once the new workflow head is safe to enforce, so unrelated open PRs do not get stranded behind a missing required check
- verify the live ruleset state through the GitHub API after the change; do not assume the edit stuck

## Acceptance criteria

1. Every PR head reports an `android-smoke` status context.
2. PRs that do **not** touch Android/shared-runtime surfaces report a successful `android-smoke` result without booting an emulator or building/uploading Android smoke artifacts.
3. PRs that **do** touch Android/shared-runtime surfaces still run the real emulator-backed Android smoke lane and preserve the current artifact/report contract.
4. The active `main-protection-ruleset` requires `android-smoke` alongside the existing required contexts.
5. `docs/validation.md`, `docs/specs/casgrain-product-spec.md`, `docs/development/test-pyramid-and-runtime-contracts.md`, `docs/development/merge-and-validation-policy.md`, and `docs/development/security-owasp-baseline.md` no longer describe Android smoke as advisory-only.
6. `#79` is the shipped Android merge-gate promotion slice because the merged workflow changes and the live ruleset update are both already complete.

## Explicit non-goals

- **no** new Android product/runtime behavior changes
- **no** new reliability-window math, tracker logic, or blocker-issue redesign
- **no** broader shared mobile contract-freeze work beyond the separate `#135` follow-up that documents the already-shipped dual-platform slice
- **no** repo-wide docs sweep beyond the named contradictory policy/spec artifacts
- **no** change to the stable `android-smoke` job/context name

## Validation contract for the later implementation PR

Minimum validation expected in the implementation PR:

```bash
git diff --check
python3 -m unittest tests/scripts/test_mobile_smoke_workflow_triggers.py
python3 - <<'PY'
from pathlib import Path
import yaml
workflow = yaml.safe_load(Path('.github/workflows/android-emulator-smoke.yml').read_text(encoding='utf-8'))
on_block = workflow.get('on', workflow.get(True))
assert 'pull_request' in on_block
pr = on_block['pull_request']
assert pr in (None, {}) or 'paths' not in pr
assert workflow['jobs']['smoke']['name'] == 'android-smoke'
print('android workflow exposes an unconditional PR trigger and stable android-smoke context')
PY
```

Post-merge verification that completed `#79`:

```bash
RULESET_ID=$(gh api repos/drousselhq/casgrain/rulesets --jq '.[] | select(.name == "main-protection-ruleset") | .id')
gh api repos/drousselhq/casgrain/rulesets/$RULESET_ID --jq '.rules[] | select(.type == "required_status_checks").parameters.required_status_checks[].context' \
  | grep -Fx 'android-smoke'
```

## Completion boundary

The implementation PRs for this spec were correctly `Part of #79`, not `Closes #79`, because the issue only became honestly complete once the merged workflow was on `main` **and** the live `main-protection-ruleset` had been updated to require `android-smoke`.

Current main state after this slice landed:
- `#79` is the shipped Android merge-gate promotion slice
- `#135` is the current docs/test contract-freeze follow-up on top of the already-required Android gate
- any future Android smoke scope expansion should be opened as a new bounded follow-up issue rather than reopening this promotion slice
