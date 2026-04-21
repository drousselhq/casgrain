# Issue #79 — Implementation tasks

- Linked issue: `#79`
- Source contract: `./spec.md`

## 1. Add failing coverage for required-check-safe Android PR behavior
- [x] 1.1 Update `tests/scripts/test_mobile_smoke_workflow_triggers.py` so current `main` fails if `android-emulator-smoke.yml` still relies on `pull_request.paths` instead of always reporting an `android-smoke` context on PRs.
- [x] 1.2 Add or extend fixture/assertion coverage for the Android/shared-runtime path list the workflow should treat as `should_run=true`.
- [x] 1.3 Verify the new assertions fail on the pre-change workflow before editing production YAML.
- Goal: Prove the branch-protection-safe gap before changing workflow behavior.
- Validation: `python3 -m unittest tests/scripts/test_mobile_smoke_workflow_triggers.py`
- Non-goals: No workflow, ruleset, or docs edits yet.
- Hand back if: Current `main` already reports `android-smoke` on every PR and the only remaining work is a live ruleset flip.

## 2. Make `android-smoke` always report safely on pull requests
- [x] 2.1 Update `.github/workflows/android-emulator-smoke.yml` so the workflow runs on every PR and keeps `jobs.smoke.name` exactly `android-smoke`.
- [x] 2.2 Add in-job change detection that uses the existing Android/shared-runtime surface list to decide whether the expensive emulator path is required.
- [x] 2.3 When `should_run=false`, report success with a clear skip message and do not build the APK, boot the emulator, or upload Android smoke artifacts.
- [x] 2.4 When `should_run=true`, preserve the current emulator-backed smoke run, artifact validation, reliability report, and issue-sync behavior.
- Goal: Make the Android lane safe to require in branch protection without paying emulator cost on unrelated PRs.
- Validation: `python3 -m unittest tests/scripts/test_mobile_smoke_workflow_triggers.py && python3 - <<'PY'
from pathlib import Path
import yaml
workflow = yaml.safe_load(Path('.github/workflows/android-emulator-smoke.yml').read_text(encoding='utf-8'))
on_block = workflow.get('on', workflow.get(True))
assert 'pull_request' in on_block
pr = on_block['pull_request']
assert pr in (None, {}) or 'paths' not in pr
assert workflow['jobs']['smoke']['name'] == 'android-smoke'
print('android workflow exposes an unconditional PR trigger and stable android-smoke context')
PY`
- Non-goals: No Android runtime/fixture redesign, no artifact-contract semantics changes, no ruleset relaxation.
- Hand back if: Required-check-safe PR behavior would require splitting the Android smoke lane into a second workflow or otherwise changing the repo’s workflow topology beyond this bounded slice.

## 3. Reconcile the canonical repo contract from advisory to required gate
- [x] 3.1 Update `docs/validation.md` so it states `android-smoke` is a required merge gate and explains the always-reporting/self-skip model.
- [x] 3.2 Update `docs/specs/casgrain-product-spec.md`, `docs/development/test-pyramid-and-runtime-contracts.md`, and `docs/development/merge-and-validation-policy.md` so they no longer describe Android as advisory-only or iOS as the sole required mobile gate.
- [x] 3.3 Update `docs/development/security-owasp-baseline.md` so the protected-branch evidence snapshot matches the promoted live gate once the ruleset change is applied.
- Goal: Leave one truthful repo-owned policy/spec story after Android becomes a required merge gate.
- Validation: `python3 - <<'PY'
from pathlib import Path
needles = {
    'docs/validation.md': ['android-smoke', 'required merge gate'],
    'docs/specs/casgrain-product-spec.md': ['android-smoke'],
    'docs/development/test-pyramid-and-runtime-contracts.md': ['android-smoke'],
    'docs/development/merge-and-validation-policy.md': ['android-smoke'],
    'docs/development/security-owasp-baseline.md': ['android-smoke'],
}
for rel, expected in needles.items():
    text = Path(rel).read_text(encoding='utf-8')
    for needle in expected:
        assert needle in text, (rel, needle)
print('required docs mention android-smoke promotion')
PY`
- Non-goals: No repo-wide wording sweep beyond the named contradictory files.
- Hand back if: Another canonical doc or runbook becomes false only because it encodes a distinct policy decision that this slice cannot honestly change.

## 4. Promote the live `main` ruleset once the workflow head is safe to enforce
- [x] 4.1 Record the current `main-protection-ruleset` required status-check list before editing it.
- [x] 4.2 Add `android-smoke` to the live required-check list without removing any existing contexts or relaxing strict/review/history rules.
- [x] 4.3 Verify the live ruleset state through `gh api` after the update and keep `#79` open until that verification is true on `main`.
- Goal: Make the live GitHub protection state match the promoted repo contract.
- Validation: `RULESET_ID=$(gh api repos/drousselhq/casgrain/rulesets --jq '.[] | select(.name == "main-protection-ruleset") | .id') && gh api repos/drousselhq/casgrain/rulesets/$RULESET_ID --jq '.rules[] | select(.type == "required_status_checks").parameters.required_status_checks[].context' | grep -Fx 'android-smoke'`
- Non-goals: No relaxation of branch protection, no bypass-policy changes, no new required contexts beyond `android-smoke`.
- Hand back if: The authenticated actor cannot modify rulesets or repo governance requires a separate human-owned settings change.

## 5. Run the bounded validation set and hand back with honest closure semantics
- [x] 5.1 Run `git diff --check` and the workflow-trigger regression tests.
- [x] 5.2 Re-read the final Android workflow YAML and confirm the required-check-safe trigger plus stable `android-smoke` job name still hold.
- [x] 5.3 In the PR summary/comment, say the implementation PR is `Part of #79` and state whether the live ruleset update has already been applied or is still the remaining close-out step.
- [x] 5.4 Hand the PR back to QA with the exact validation evidence and any truthful docs lane note.
- Goal: Leave QA and later merge work with one honest picture of what changed and what still remains to close `#79`.
- Validation: `git diff --check && python3 -m unittest tests/scripts/test_mobile_smoke_workflow_triggers.py`
- Non-goals: No silent issue closure before the live ruleset verification is complete.
- Hand back if: The refreshed workflow/docs diff is clean but the live ruleset state still cannot be updated by the current actor.
