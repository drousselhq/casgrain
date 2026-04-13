# Rust-First Domain Model and Project Scaffolding Recommendation

## Why this shape

This proposal keeps the deterministic execution path entirely inside a Rust core, matches the existing Clean Architecture document, and gives Gherkin a stable compilation target that is explicit enough for CI replay and agent-assisted repair.

## 1. Canonical executable plan IR

Use a compiled JSON-serializable plan as the execution substrate.

Suggested root model:

```rust
pub struct ExecutablePlan {
    pub plan_id: PlanId,
    pub name: String,
    pub version: PlanFormatVersion,
    pub source: PlanSource,
    pub target: TargetProfile,
    pub capabilities_required: CapabilitySet,
    pub defaults: ExecutionDefaults,
    pub steps: Vec<PlanStep>,
    pub metadata: BTreeMap<String, String>,
}
```

Core plan step:

```rust
pub struct PlanStep {
    pub step_id: StepId,
    pub intent: StepIntent,
    pub action: ActionKind,
    pub preconditions: Vec<Guard>,
    pub postconditions: Vec<Postcondition>,
    pub timeout: TimeoutBudget,
    pub retry: RetryPolicy,
    pub on_failure: FailurePolicy,
    pub artifacts: ArtifactPolicy,
}
```

Recommended IR rules:
- every step gets a stable `step_id`
- selectors are fully explicit after compilation
- waits/assertions are first-class, not hidden inside actions
- compilation expands prose into explicit guards, action inputs, and postconditions
- serialization format should be `serde` JSON first, with room for a binary format later

Recommended intent enum:
- `Setup`
- `Navigate`
- `Interact`
- `Observe`
- `Assert`
- `Cleanup`

## 2. Selector taxonomy

Use a selector model that separates semantic intent from adapter resolution details.

```rust
pub enum Selector {
    ResourceId(String),
    AccessibilityId(String),
    Text(TextSelector),
    Role(RoleSelector),
    Label(LabelSelector),
    Value(ValueSelector),
    Placeholder(String),
    Hint(String),
    Trait(UiTrait),
    Path(UiPath),
    Coordinate(CoordinateSelector),
    Platform(PlatformSelector),
    Chain(Vec<SelectorPart>),
    AnyOf(Vec<Selector>),
}
```

Resolution precedence recommendation:
1. Stable platform-native identifiers: `ResourceId`, `AccessibilityId`
2. Structural/semantic selectors: `Role`, `Label`, `Value`, `Trait`
3. Textual selectors: `Text`, `Placeholder`, `Hint`
4. Structural path selectors: `Path`, `Chain`
5. Last-resort selectors: `Coordinate`, platform-specific raw selectors

Selector guidance:
- compiler should emit diagnostics when it must fall back to fragile selectors
- `AnyOf` should be allowed only when ordering is explicit and deterministic
- `PlatformSelector` should isolate iOS/Android escape hatches without polluting the shared model
- selectors should compile into a normalized `ResolvedSelectorPlan` that adapters can execute deterministically

## 3. Actions, assertions, and waits

### Action kinds

```rust
pub enum ActionKind {
    LaunchApp { app: AppRef, args: Vec<String> },
    TerminateApp { app: AppRef },
    ActivateApp { app: AppRef },
    OpenDeepLink { url: String },
    Tap { target: Selector },
    DoubleTap { target: Selector },
    LongPress { target: Selector, duration_ms: u64 },
    TypeText { target: Selector, text: SecretString, mode: TextEntryMode },
    ClearText { target: Selector },
    ReplaceText { target: Selector, text: SecretString },
    SendKeys { target: Selector, keys: Vec<KeyInput> },
    Scroll { target: Option<Selector>, direction: ScrollDirection, amount: ScrollAmount },
    Swipe { target: Option<Selector>, direction: SwipeDirection },
    SelectOption { target: Selector, option: Selector },
    SetToggle { target: Selector, value: bool },
    Back,
    Home,
    TakeScreenshot { name: Option<String> },
    CaptureViewTree { name: Option<String> },
    CaptureLogs { scope: LogScope },
    Noop,
}
```

### Assertion kinds

```rust
pub enum AssertionKind {
    Exists { target: Selector },
    NotExists { target: Selector },
    Visible { target: Selector },
    Hidden { target: Selector },
    Enabled { target: Selector },
    Disabled { target: Selector },
    Focused { target: Selector },
    TextEquals { target: Selector, value: StringMatch },
    TextContains { target: Selector, value: StringMatch },
    ValueEquals { target: Selector, value: StringMatch },
    Count { target: Selector, op: ComparisonOp, expected: u32 },
    AppInForeground { app: AppRef },
    UrlMatches { pattern: String },
}
```

### Wait kinds

```rust
pub enum WaitKind {
    ForAssertion { assertion: AssertionKind },
    ForIdle { duration_ms: u64 },
    ForAnimationToSettle,
    ForAppForeground { app: AppRef },
    ForElementGone { target: Selector },
    ForTimeout { duration_ms: u64 },
}
```

Recommended execution semantics:
- `ActionKind` changes state
- `AssertionKind` evaluates current state once
- `WaitKind` polls deterministically until success or timeout
- retries belong to step policy, not adapter heuristics
- every poll attempt should be traceable when debugging is enabled

## 4. Trace and artifact model

Treat trace as a domain object, not log text.

```rust
pub struct ExecutionTrace {
    pub run_id: RunId,
    pub plan_id: PlanId,
    pub device: DeviceDescriptor,
    pub started_at: Timestamp,
    pub finished_at: Option<Timestamp>,
    pub status: RunStatus,
    pub steps: Vec<StepTrace>,
    pub artifacts: Vec<ArtifactRef>,
    pub diagnostics: Vec<RunDiagnostic>,
}
```

```rust
pub struct StepTrace {
    pub step_id: StepId,
    pub status: StepStatus,
    pub started_at: Timestamp,
    pub finished_at: Option<Timestamp>,
    pub attempts: Vec<StepAttemptTrace>,
    pub observation_summary: Option<ObservationSummary>,
    pub failure: Option<FailureReport>,
    pub artifacts: Vec<ArtifactRef>,
}
```

Recommended artifact types:
- screenshot
- accessibility tree snapshot
- page/source snapshot
- device logs
- video segment later, not required for first cut
- compiled plan JSON
- failure diff / selector resolution report

`ArtifactRef` should include:
- `artifact_id`
- `artifact_type`
- `mime_type`
- `storage_uri` or relative path
- `step_id` optional
- `sha256`
- `created_at`
- `retention`

Failure report should explicitly capture:
- failure code
- message
- unresolved selector or failed assertion payload
- adapter error details normalized into domain codes
- attached artifact ids
- repair hints suitable for agent workflows

## 5. Initial Rust crate layout

Recommended workspace:

- `Cargo.toml`
- `crates/mar_domain`
- `crates/mar_application`
- `crates/mar_compiler`
- `crates/mar_runner`
- `crates/mar_infra_fs`
- `crates/mar_infra_iossim`
- `crates/mar_infra_android`
- `crates/mar_cli`
- `fixtures/`
- `tests/golden/`
- `tests/integration/`

Suggested module layout:

### `crates/mar_domain/src/lib.rs`
- `plan/`
  - `executable_plan.rs`
  - `step.rs`
  - `policy.rs`
- `selector/`
  - `selector.rs`
  - `text.rs`
  - `path.rs`
  - `platform.rs`
- `action/`
  - `action_kind.rs`
  - `input.rs`
- `assertion/`
  - `assertion_kind.rs`
  - `matchers.rs`
- `wait/`
  - `wait_kind.rs`
- `trace/`
  - `execution_trace.rs`
  - `failure_report.rs`
  - `artifact.rs`
- `engine/`
  - `device_engine.rs`
  - `device_session.rs`
  - `capabilities.rs`
  - `snapshot.rs`
- `diagnostics/`
  - `compiler_diagnostic.rs`
  - `runtime_error.rs`
- `ids.rs`
- `time.rs`

### `crates/mar_application/src/lib.rs`
- `compile_plan.rs`
- `run_plan.rs`
- `collect_artifacts.rs`
- `repair_context.rs`
- `exploration_session.rs`

### `crates/mar_compiler/src/lib.rs`
- `gherkin/`
  - `parser.rs`
  - `ast.rs`
- `lowering/`
  - `scenario_to_plan.rs`
  - `selector_lowering.rs`
  - `wait_inference.rs`
- `validation/`
  - `determinism_rules.rs`
- `serialize.rs`

### `crates/mar_runner/src/lib.rs`
- `executor.rs`
- `step_executor.rs`
- `polling.rs`
- `trace_builder.rs`
- `artifact_policy.rs`

### `crates/mar_infra_fs/src/lib.rs`
- `artifact_store.rs`
- `json_reporter.rs`

### `crates/mar_infra_iossim/src/lib.rs`
- `simulator_session.rs`
- `xcui_selector_resolver.rs`
- `capture.rs`

### `crates/mar_infra_android/src/lib.rs`
- `emulator_session.rs`
- `uiautomator_selector_resolver.rs`
- `capture.rs`

### `crates/mar_cli/src/main.rs`
- `commands/compile.rs`
- `commands/run.rs`
- `commands/explore.rs`
- `output/json.rs`
- `output/human.rs`

## 6. Immediate implementation sequence

1. create Cargo workspace and `mar_domain`
2. implement stable IDs, plan IR, selector taxonomy, action/assert/wait enums
3. implement `ExecutionTrace`, `FailureReport`, and `ArtifactRef`
4. define `DeviceEngine` and `DeviceSession` traits in domain
5. add `mar_compiler` with Gherkin parser stubs and deterministic lowerer to plan JSON
6. add `mar_runner` with a fake engine for deterministic domain/application tests
7. add filesystem artifact store and JSON output adapter
8. only then start iOS simulator adapter work

## 7. Test priorities

Priority 0:
- domain unit tests for selector normalization, step policy semantics, trace/failure serialization
- plan JSON round-trip tests with version pinning
- determinism tests proving identical input -> identical compiled plan

Priority 1:
- compiler golden tests from `docs/specs/` to expected plan JSON
- validation tests for fragile selector warnings and forbidden ambiguous constructs
- runner tests using fake device engine for success/failure/timeout/retry behavior

Priority 2:
- artifact store tests for path layout, hash generation, and manifest integrity
- CLI snapshot tests for machine-readable output schemas
- adapter contract tests that map platform-specific errors into domain `FailureCode`

Priority 3:
- iOS simulator integration tests against a fixture app covering login, deep link, and failure diagnostics
- Android parity tests after the iOS contract stabilizes

## 8. Recommendation summary

The best next concrete move is to establish a Rust workspace with `mar_domain` first and make `ExecutablePlan` the canonical contract between Gherkin compilation, deterministic execution, trace capture, and agent-facing repair flows. Keep selectors explicit and ranked by stability, model waits/assertions separately from actions, and make traces/artifacts fully structured so agents can reason over failures without entering the execution path.
