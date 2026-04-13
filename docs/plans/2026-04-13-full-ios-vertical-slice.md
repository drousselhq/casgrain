# Full iOS Vertical Slice Implementation Plan

> For Hermes: use subagent-driven-development skill to execute this plan one bounded task at a time.

Goal: prove Casgrain's first product-true vertical slice on iOS: Gherkin in, deterministic executable artifact out, real simulator execution against the fixture app, machine-readable result plus screenshot artifact.

Architecture: keep this slice intentionally narrow and fixture-specific. Reuse the existing compiler, plan, runner, and iOS smoke harness where possible, but make the proof unambiguous by ensuring the primary executable input is generated from Gherkin rather than handwritten XCTest. Prefer one honest path over a flexible abstraction.

Tech stack: Rust workspace crates (`mar_cli`, `mar_compiler`, `mar_runner`, `mar_ios`, `mar_domain`), SwiftUI fixture app under `fixtures/ios-smoke/`, macOS GitHub Actions smoke workflow.

---

## Scope guardrails
- Support exactly one tiny fixture scenario first.
- Support only the step forms needed by that scenario.
- Keep iOS-only for this slice.
- Do not broaden authoring UX or general selector inference yet.
- Keep handwritten XCTest only as harness plumbing or fallback evidence, not as the primary user-facing execution artifact.

## Target proof
A user can point Casgrain at a minimal `.feature` file such as:
- Given the app is launched
- When the user taps tap button
- Then count label text is "Count: 1"
- And a screenshot is captured

Casgrain then:
1. compiles that feature into a deterministic executable plan
2. routes the plan through a real iOS execution path for the smoke fixture
3. runs against the real simulator-backed fixture app
4. emits machine-readable results and screenshot evidence

---

## Task 1: Add the fixture Gherkin source of truth

Objective: create the smallest possible feature file that expresses the existing smoke-app behavior.

Files:
- Create: `fixtures/ios-smoke/features/tap_counter.feature`
- Modify: `fixtures/ios-smoke/README.md`

Steps:
1. Create `fixtures/ios-smoke/features/tap_counter.feature` with one scenario only.
2. Use only step phrases that we are willing to support in the first slice.
3. Update the fixture README so it explains that this feature is now the product-true source for the vertical slice.
4. Validation:
   - `cargo run -p mar_cli -- compile fixtures/ios-smoke/features/tap_counter.feature`

## Task 2: Narrow and pin the first supported Gherkin vocabulary

Objective: make compiler behavior explicit and stable for the fixture scenario.

Files:
- Modify: `crates/mar_compiler/src/lib.rs`
- Test: `crates/mar_compiler/src/lib.rs`

Steps:
1. Add or tighten tests for the exact step phrases used by `tap_counter.feature`.
2. Ensure compilation produces deterministic selectors for the fixture controls:
   - `tap button`
   - `count label`
3. Ensure screenshot capture can be expressed by a supported step phrase.
4. Ensure unsupported nearby phrases fail clearly with structured diagnostics.
5. Validation:
   - `cargo test -p mar_compiler`

## Task 3: Add a real iOS execution path in the CLI

Objective: stop at the smallest user-visible product command that runs the compiled plan against iOS instead of the mock engine.

Files:
- Modify: `crates/mar_cli/src/main.rs`
- Modify: `crates/mar_runner/src/lib.rs` if trace/result shaping needs a small addition
- Modify: `crates/mar_ios/src/lib.rs`
- Test: `crates/mar_cli/src/main.rs`

Steps:
1. Add a bounded CLI command for this slice, for example `run-ios-smoke <feature-file>`.
2. Compile the feature file through the existing compiler path.
3. Execute the compiled plan through an iOS-specific engine path rather than `run-mock`.
4. Return machine-readable output as JSON when requested, or at minimum a deterministic structured summary plus artifact references.
5. Validation:
   - `cargo test -p mar_cli`
   - `cargo test -p mar_runner`
   - `cargo test -p mar_ios`

## Task 4: Bridge the runner to the real fixture harness

Objective: make the compiled plan drive the real fixture app, not just an in-memory adapter.

Files:
- Modify: `crates/mar_ios/src/lib.rs`
- Modify: `scripts/ios_smoke.sh`
- Possibly create: `scripts/ios_smoke_run_plan.py` or `scripts/ios_smoke_run_plan.sh`
- Possibly create: `artifacts/` contract documentation in `fixtures/ios-smoke/README.md`

Steps:
1. Decide the thinnest honest bridge from Rust plan execution to the real simulator-backed fixture.
2. Keep it fixture-specific if that avoids fake generality.
3. Ensure the bridge can perform exactly the required operations for the first slice:
   - launch app
   - tap control
   - read visible text/assert text
   - capture screenshot
4. Make artifact paths deterministic enough to archive in CI.
5. Validation:
   - local Linux validation may be limited to unit tests and script syntax
   - macOS GitHub Actions must prove the real path

## Task 5: Replace the workflow proof from handwritten XCTest to generated-plan execution

Objective: make CI prove the product loop, not only the harness loop.

Files:
- Modify: `.github/workflows/ios-simulator-smoke.yml`
- Modify: `fixtures/ios-smoke/README.md`
- Possibly modify: `docs/validation.md`

Steps:
1. Change the smoke workflow so the canonical path runs Casgrain on `tap_counter.feature`.
2. Preserve upload of logs, structured results, and screenshot artifacts.
3. Keep the old handwritten XCTest path only if needed as temporary debugging support, not as the primary proof.
4. Validation:
   - PR check `ios-simulator-smoke` passes on GitHub-hosted macOS

## Task 6: Add explicit end-to-end regression coverage around the slice

Objective: lock in the exact proof and prevent silent regression back to mock-only behavior.

Files:
- Modify: `crates/mar_cli/src/main.rs` tests
- Modify: relevant docs under `docs/validation.md` and `docs/specs/casgrain-product-spec.md` if wording needs tightening

Steps:
1. Add regression tests for compile output shape for `tap_counter.feature`.
2. Add regression tests for the CLI/user-facing command shape.
3. Document clearly that the first vertical slice is:
   - minimal
   - iOS-only
   - fixture-specific
   - product-true end-to-end
4. Validation:
   - `cargo test --workspace`
   - `cargo fmt --all --check`
   - `cargo clippy --workspace --all-targets -- -D warnings`
   - GitHub Actions PR checks green

---

## Suggested execution order
1. feature file
2. compiler narrowing
3. CLI command
4. real fixture bridge
5. CI workflow switch
6. docs and regression cleanup

## Acceptance checkpoint
Do not call this complete until the primary successful demo is:
1. edit or provide a `.feature` file
2. Casgrain compiles it into a deterministic executable artifact
3. Casgrain runs that artifact against the real iOS simulator fixture app
4. CI captures structured output and screenshot evidence

## Related backlog
- Issue #32: Deliver the first full Gherkin-to-iOS-fixture vertical slice
