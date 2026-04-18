# Test Pyramid, Unit Testing Strategy, and Runtime Contracts

This document defines Casgrain's current testing strategy, unit-testing expectations, and coverage policy for the deterministic core.

It complements:
- `docs/validation.md` for the canonical merge gate
- `docs/development/merge-and-validation-policy.md` for merge classes
- `docs/specs/casgrain-product-spec.md` for product behavior intent
- issue #1 for the original backlog item
- issue #4 for the fixture-app integration strategy that now anchors Layer 4 planning

## Goals

The test strategy should keep Casgrain:
- deterministic by default
- cheap to validate locally and in CI
- explicit about which layer owns which regressions
- honest about what lower-layer tests prove versus what real simulator/emulator checks prove
- easy for contributors and agents to apply without inventing one-off testing rules per PR

## Testing principles

1. Prefer the cheapest test that can prove the behavior.
2. Keep the deterministic execution path covered without depending on live mobile platforms.
3. Add targeted regression tests when compiler lowering, runner semantics, selector resolution, trace/artifact behavior, or CLI output changes.
4. Treat fixture-app and simulator/emulator coverage as a separate integration layer, not a replacement for fast workspace tests.
5. Keep one clear smoke path from CLI entrypoint to compiled plan to execution trace.
6. Prefer deterministic fixtures, stable assertions, and explicit artifacts over timing-sensitive or environment-sensitive tests.
7. Use coverage as a signal for review and ratcheting, not as a reason to write shallow tests that only exercise lines.

## Rust unit testing strategy

### What belongs in unit tests

Use fast crate-local tests as the default proof for pure or mostly pure logic:
- **domain values and validation rules**: serialization, round-trips, invariants, and invalid-shape rejection
- **parsers and lowering logic**: phrase mapping, diagnostics, plan shape, stable lowering output, and unsupported-input behavior
- **planners and selectors**: selection rules, normalization, matching semantics, and stable resolution behavior
- **runner semantics**: step ordering, failure propagation, retry/timeout policy, artifact/trace emission, and deterministic mock behavior
- **adapter-facing translation layers**: mapping platform-specific errors or events into Casgrain domain failures without needing a live device for every case
- **CLI boundaries**: command parsing, human-readable failure rendering, machine-readable output shape, and contract-level smoke behavior

### Layer expectations by area

#### Layer 0 — domain and application contracts

Purpose:
- protect the canonical `ExecutablePlan`, trace, and validation contracts
- catch schema and plan-validation regressions before runner or CLI layers are involved

Current coverage in the repo:
- `crates/domain`: JSON round-trip coverage for `ExecutablePlan`
- `crates/application`: plan validation coverage for duplicate step IDs

Examples today:
- `domain::tests::executable_plan_round_trips_to_json`
- `application::tests::validate_plan_rejects_duplicate_step_ids`

Expected growth in this layer:
- selector normalization and stability rules
- failure/trace serialization invariants
- stricter plan validation for invalid step structure and metadata

#### Layer 1 — compiler lowering and determinism tests

Purpose:
- prove that spec input lowers into a stable deterministic plan
- catch accidental changes in intent mapping, actions, waits, and assertions

Current coverage in the repo:
- stable repeated compilation for the same Gherkin input
- lowering checks for launch, tap, type, and visibility assertions

Examples today:
- `compiler::tests::compiles_gherkin_into_stable_plan`
- `compiler::tests::lowers_common_actions_and_assertions`

Expected growth in this layer:
- golden tests from representative specs to expected plan JSON
- diagnostics coverage for unsupported or ambiguous phrases
- version-pinning and compatibility checks for plan output

#### Layer 2 — runner and fake-engine runtime contract tests

Purpose:
- validate deterministic execution semantics without a real simulator or emulator
- ensure the runner, selector matching, artifacts, and failure reporting stay predictable

Current coverage in the repo:
- selector success and failure behavior in `DeterministicRunner`
- a small login-like end-to-end flow through the fake engine
- fake-engine fixture behavior for controls, tap side effects, and screenshot artifacts

Examples today:
- `runner::tests::runner_passes_for_matching_selector`
- `runner::tests::runner_fails_for_missing_selector`
- `runner::tests::runner_can_execute_small_login_like_flow`
- `runner::mock::tests::login_fixture_contains_expected_controls`
- `runner::mock::tests::tapping_login_reveals_home_screen`
- `runner::mock::tests::screenshot_action_emits_artifact`

Expected growth in this layer:
- retry and timeout semantics
- failure-policy coverage for abort vs continue behavior
- trace and artifact manifest assertions
- adapter-facing contract tests that confirm platform-specific failures map into domain failure codes

#### Layer 3 — CLI smoke tests

Purpose:
- keep at least one user-facing path covered from CLI command parsing into compiler and runner behavior
- ensure failures stay readable for contributors and automation agents

Current coverage in the repo:
- usage and unknown-command handling
- compile failure rendering
- `run-mock` success path from feature file to human-readable output

Examples today:
- `casgrain::tests::usage_is_returned_for_missing_arguments`
- `casgrain::tests::usage_is_returned_for_unknown_command`
- `casgrain::tests::compile_failure_is_rendered_cleanly`
- `casgrain::tests::run_mock_reports_successful_flow`

Expected growth in this layer:
- machine-readable output snapshots
- trace JSON contract checks
- explicit coverage for future stable CLI subcommands

#### Layer 4 — fixture-app simulator/emulator integration tests

Purpose:
- validate that real adapters preserve the deterministic contracts already proven in lower layers
- prove reproducible launch/tap/type/assert/trace flows against controlled fixture apps

Status:
- partially implemented
- the first iOS fixture-app smoke path now exists under `tests/test-support/fixtures/ios-smoke/`
- the macOS `ios-simulator-smoke` workflow now runs the generated-plan `casgrain run-ios-smoke` path and archives plan, trace, simulator, log, and xcresult evidence
- the Android emulator smoke path also exists now as a bounded Layer 4 evidence lane, with success traces and runner-managed failure diagnostics archived machine-readably for the canonical Android fixture

Current strategy:
- keep one tiny iOS fixture app as the first honest integration target
- prove launch, one visible tap, one visible assertion, and one screenshot artifact before broadening scope
- keep simulator/emulator coverage as a narrow Layer 4 proof on top of cheaper workspace validation
- keep iOS as the first required merge-gate slice while using Android smoke as a parallel evidence/debugging contract for the Android fixture path

Current target scope:
- one iOS fixture-app smoke path
- one Android fixture-app parity path with explicit artifact-contract validation
- reproducible simulator/emulator setup in CI or documented pre-merge validation

## Stronger expectations for critical core logic

Some paths need more than a single happy-path unit test. Treat the following as critical core logic unless a future design document explicitly says otherwise:
- canonical plan/domain serialization and validation invariants
- compiler lowering from supported Gherkin into `ExecutablePlan`
- selector matching and runner execution semantics
- trace, artifact, and failure-reporting contracts that QA or agents consume
- stable CLI output modes that other tooling depends on

For critical core logic:
- target **90%+ coverage** on the changed area when the work is substantial enough for the metric to be meaningful
- prefer multiple focused tests that cover success, expected failure, and boundary behavior
- favor golden/contract-style assertions when output shape stability matters
- do not rely on a live mobile workflow as the only proof for logic that can be exercised deterministically in Rust tests

## Regression-test expectations for bug fixes

When fixing a bug, add the smallest practical regression test when feasible.

Usually this means:
- a Layer 0 or Layer 1 test for validation/lowering bugs
- a Layer 2 contract test for runner or selector semantics
- a Layer 3 CLI test when the bug was visible through command behavior or output
- a Layer 4 proof only when the bug truly depends on simulator/emulator behavior and cannot be reproduced honestly below that layer

If a regression test is not feasible in the same slice, explain why in the PR and open follow-up work instead of silently skipping coverage.

## Determinism and flake avoidance

Contributors should optimize for tests that are stable under repeated local and CI execution.

Prefer:
- pure functions and deterministic fixtures over timing-sensitive orchestration
- explicit expected traces, artifacts, and diagnostics over broad "did not crash" assertions
- stable fake/mock engines for lower layers before reaching for simulator/emulator coverage
- table-driven cases or targeted golden data when many small variants share one contract
- narrow fixture inputs that make the failure obvious

Avoid unless genuinely required:
- sleeping/polling to make tests pass
- assertions that depend on wall-clock timing, random ordering, or host-specific environment state
- large opaque fixtures when a smaller purpose-built sample would prove the same contract

## Fakes, mocks, fixtures, helpers, and builders

Use support code to make tests clearer, not to hide behavior.

Guidelines:
- keep crate-specific helpers close to the crate tests when they only serve one crate
- use `tests/test-support/fixtures/` for shared fixture apps, features, and cross-cutting test assets that represent intentional repo-owned test inputs
- use `tests/test-support/scripts/` for harness plumbing that drives those fixtures in integration/smoke workflows
- prefer small helper functions or builders when they remove repetitive setup without obscuring the behavior under test
- prefer fakes for deterministic contract tests where the fake models the important behavior explicitly
- avoid mocks that merely restate implementation details or make tests pass without asserting user-visible contracts
- when a helper becomes complex enough to hide the real behavior, simplify the helper or move assertions closer to the test body

## Coverage policy

Coverage is part of review discipline, but it is not the only quality signal.

Current repo reality:
- CI currently enforces a **75% workspace line-coverage floor** with `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- the workspace-wide floor is a baseline merge gate, not a statement that 75% is the desired long-term target for all important logic
- touched-code or new-code coverage is not yet enforced automatically in CI; until tooling lands, reviewers and authors must apply the policy below manually and honestly

Policy expectations:
- target **85%+ coverage** on new or materially changed code
- target **90%+ coverage** on critical core logic
- do **not** require 100% coverage as a blanket rule
- do **not** allow overall coverage regression without explicit justification in the PR
- prefer a ratchet strategy over a one-time backfill campaign that creates high churn or shallow tests

How to interpret the policy:
- use coverage to ask whether the changed logic has meaningful proof, not whether every branch was exercised mechanically
- docs-only, governance-only, or label-only changes do not need artificial coverage work
- a small low-risk change may satisfy the spirit of the policy with targeted tests plus no overall coverage regression, even if the repo lacks touched-line automation today
- when a PR intentionally leaves some changed logic under-covered, call that out explicitly and open a follow-up issue if the gap matters

## Ownership by change type

Use this table when deciding what tests to add for a PR.

| Change area | Minimum expected validation |
| --- | --- |
| Domain model / validation rules | Layer 0 unit tests + workspace gate |
| Compiler lowering / diagnostics | Layer 1 tests + workspace gate |
| Planner / selector logic | Layer 1 or 2 deterministic tests + workspace gate |
| Runner semantics / selector resolution / trace behavior | Layer 2 tests + workspace gate |
| CLI behavior | Layer 3 tests + workspace gate |
| Real adapter integration | Lower-layer coverage first, then targeted Layer 4 validation |
| Docs / governance only | Link, consistency, and policy review; run the full Rust gate unless the PR is explicitly scoped as docs-only or governance-only and the reviewer accepts the exception |

The workspace gate remains the same canonical merge bar in `docs/validation.md`:
- `cargo fmt --all --check`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`
- `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- `cargo audit`
- `gitleaks dir .`
- `cargo deny check licenses sources`

## Immediate next testing investments

1. Add low-churn coverage reporting/tooling so touched-code policy can be reviewed with less guesswork.
2. Add compiler golden tests from representative product-spec slices to expected plan JSON.
3. Expand runner and CLI contract coverage for retry, timeout, failure semantics, machine-readable output, and trace/artifact details.
4. Keep Layer 4 focused on the narrow product-true iOS slice while Android parity matures separately.

## Exit criteria for issue #1

Issue #1 is satisfied when this repo has:
- an explicit in-repo test pyramid
- named validation layers from domain through future integration coverage
- a documented runtime contract testing strategy
- a documented unit-testing and coverage policy contributors can apply consistently
- follow-on implementation work clearly delegated to existing backlog items
