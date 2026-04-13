# Test Pyramid and Runtime Contract Plan

This document defines the current testing strategy for Casgrain's deterministic core and the next validation layers that should be added as the product grows.

It complements:
- `docs/validation.md` for the canonical merge gate
- `docs/development/merge-and-validation-policy.md` for merge classes
- `docs/specs/casgrain-product-spec.md` for product behavior intent
- issue #1 for the original backlog item
- issue #4 for the future fixture-app integration layer

## Goals

The test strategy should keep Casgrain:
- deterministic by default
- cheap to validate locally and in CI
- explicit about which layer owns which regressions
- ready to grow from fake-engine validation into simulator/emulator-backed validation

## Testing principles

1. Prefer the cheapest test that can prove the behavior.
2. Keep the deterministic execution path covered without depending on live mobile platforms.
3. Add targeted regression tests when compiler lowering, runner semantics, selector resolution, or trace/artifact behavior changes.
4. Treat fixture-app and simulator/emulator coverage as a separate integration layer, not a replacement for fast workspace tests.
5. Keep one clear smoke path from CLI entrypoint to compiled plan to execution trace.

## Current pyramid

### Layer 0 — domain and application contracts

Purpose:
- protect the canonical `ExecutablePlan`, trace, and validation contracts
- catch schema and plan-validation regressions before runner or CLI layers are involved

Current coverage in the repo:
- `crates/mar_domain`: JSON round-trip coverage for `ExecutablePlan`
- `crates/mar_application`: plan validation coverage for duplicate step IDs

Examples today:
- `mar_domain::tests::executable_plan_round_trips_to_json`
- `mar_application::tests::validate_plan_rejects_duplicate_step_ids`

Expected growth in this layer:
- selector normalization and stability rules
- failure/trace serialization invariants
- stricter plan validation for invalid step structure and metadata

### Layer 1 — compiler lowering and determinism tests

Purpose:
- prove that spec input lowers into a stable deterministic plan
- catch accidental changes in intent mapping, actions, waits, and assertions

Current coverage in the repo:
- stable repeated compilation for the same Gherkin input
- lowering checks for launch, tap, type, and visibility assertions

Examples today:
- `mar_compiler::tests::compiles_gherkin_into_stable_plan`
- `mar_compiler::tests::lowers_common_actions_and_assertions`

Expected growth in this layer:
- golden tests from representative specs to expected plan JSON
- diagnostics coverage for unsupported or ambiguous phrases
- version-pinning and compatibility checks for plan output

### Layer 2 — runner and fake-engine runtime contract tests

Purpose:
- validate deterministic execution semantics without a real simulator or emulator
- ensure the runner, selector matching, artifacts, and failure reporting stay predictable

Current coverage in the repo:
- selector success and failure behavior in `DeterministicRunner`
- a small login-like end-to-end flow through the fake engine
- fake-engine fixture behavior for controls, tap side effects, and screenshot artifacts

Examples today:
- `mar_runner::tests::runner_passes_for_matching_selector`
- `mar_runner::tests::runner_fails_for_missing_selector`
- `mar_runner::tests::runner_can_execute_small_login_like_flow`
- `mar_runner::mock::tests::login_fixture_contains_expected_controls`
- `mar_runner::mock::tests::tapping_login_reveals_home_screen`
- `mar_runner::mock::tests::screenshot_action_emits_artifact`

Expected growth in this layer:
- retry and timeout semantics
- failure-policy coverage for abort vs continue behavior
- trace and artifact manifest assertions
- adapter-facing contract tests that confirm platform-specific failures map into domain failure codes

### Layer 3 — CLI smoke tests

Purpose:
- keep at least one user-facing path covered from CLI command parsing into compiler and runner behavior
- ensure failures stay readable for contributors and automation agents

Current coverage in the repo:
- usage and unknown-command handling
- compile failure rendering
- `run-mock` success path from feature file to human-readable output

Examples today:
- `mar_cli::tests::usage_is_returned_for_missing_arguments`
- `mar_cli::tests::usage_is_returned_for_unknown_command`
- `mar_cli::tests::compile_failure_is_rendered_cleanly`
- `mar_cli::tests::run_mock_reports_successful_flow`

Expected growth in this layer:
- machine-readable output snapshots
- trace JSON contract checks
- explicit coverage for future stable CLI subcommands

### Layer 4 — fixture-app simulator/emulator integration tests

Purpose:
- validate that real adapters preserve the deterministic contracts already proven in lower layers
- prove reproducible launch/tap/type/assert/trace flows against controlled fixture apps

Status:
- not implemented yet
- tracked by issue #4

Initial target scope:
- one iOS fixture-app smoke path
- one Android parity path after iOS contracts stabilize
- reproducible simulator/emulator setup in CI or documented pre-merge validation

## Ownership by change type

Use this table when deciding what tests to add for a PR.

| Change area | Minimum expected validation |
| --- | --- |
| Domain model / validation rules | Layer 0 unit tests + workspace gate |
| Compiler lowering / diagnostics | Layer 1 tests + workspace gate |
| Runner semantics / selector resolution / trace behavior | Layer 2 tests + workspace gate |
| CLI behavior | Layer 3 tests + workspace gate |
| Real adapter integration | Lower-layer coverage first, then targeted Layer 4 validation |

The workspace gate remains the same canonical merge bar in `docs/validation.md`:
- `cargo fmt --all --check`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only`
- `cargo audit`
- `gitleaks dir .`
- `cargo deny check licenses sources`

## Immediate next testing investments

1. Add compiler golden tests from representative product-spec slices to expected plan JSON.
2. Expand runner contract coverage for retry, timeout, continue-on-failure, and trace/artifact details.
3. Add CLI checks for `--trace-json` and other machine-readable output contracts.
4. Land the fixture-app and simulator/emulator strategy from issue #4 before building broad adapter integration suites.

## Exit criteria for issue #1

Issue #1 is satisfied when this repo has:
- an explicit in-repo test pyramid
- named validation layers from domain through future integration coverage
- a documented runtime contract testing strategy
- follow-on implementation work clearly delegated to existing backlog items
