# Clean Architecture for Mobile Agent Runtime

## Goal

Create a mobile automation platform that supports deterministic CI execution, local developer tooling, and agent-native workflows without collapsing those concerns into one fragile layer.

## Architectural Rule

Dependencies point inward only.

- Presentation -> Application -> Domain
- Infrastructure -> Application -> Domain
- Domain depends on nothing outside itself

## Layers

### 1. Domain Layer

Pure business logic and platform-agnostic models.

Owns:
- selector model
- action/step model
- assertions and wait conditions
- scenario plan model
- execution trace model
- runtime capabilities contracts
- compiler contracts
- error taxonomy

Must not depend on:
- Apple or Android toolchains
- simulator/emulator CLIs
- LLM SDKs
- CLI parsing libraries
- filesystem/network/UI frameworks

### 2. Application Layer

Use-case orchestration.

Owns:
- compile requirement spec -> executable plan
- run executable plan against abstract device engine
- collect artifacts and trace output
- repair workflow coordination
- interactive exploration session orchestration
- backlog/task orchestration for agent workflows

Application services may depend on domain interfaces but not on platform-specific implementations.

### 3. Infrastructure Layer

Concrete adapters.

Owns:
- iOS simulator adapter
- Android emulator/device adapter
- accessibility tree extraction
- screenshot/log capture
- filesystem artifact storage
- Git integration
- external tool invocation
- machine-oriented CLI JSON output adapters

### 4. Presentation Layer

Multiple interfaces over the same application use cases.

Initial planned interfaces:
- human CLI
- machine/agent CLI with JSON-first output
- CI entrypoint
- future IDE or daemon/session adapters if needed

## Core Bounded Contexts

### A. Runtime Engine

Concern: deterministic interaction with mobile runtime targets.

Key abstractions:
- DeviceEngine
- DeviceSession
- RuntimeCapabilitySet
- ScreenSnapshot
- InteractionResult

### B. Specification & Compilation

Concern: convert human-facing requirements into deterministic executable plans.

Key abstractions:
- RequirementSpec
- ScenarioPlan
- Step
- Selector
- Assertion
- WaitCondition
- CompilationDiagnostic

### C. Execution & Tracing

Concern: deterministic execution, retries, timing, artifacts, and failure reporting.

Key abstractions:
- ExecutionRun
- StepResult
- TraceEvent
- ArtifactRef
- FailureReport

### D. Agent Workflow Support

Concern: exploration, authoring, diagnosis, and repair — without making LLM inference part of deterministic execution.

Key abstractions:
- ExplorationSession
- RepairProposal
- AuthoringRequest
- ScenarioDraft
- BacklogItem

## Critical Design Decision

The LLM is never part of the deterministic execution path.

Allowed LLM roles:
- authoring
- exploration assistance
- repair suggestions
- summarization
- conversion from higher-level intent into draft specs

Forbidden LLM roles in CI-critical path:
- deciding runtime actions during deterministic replay
- resolving assertions during deterministic replay
- interpreting whether a test passed or failed in place of explicit rules

## Language Strategy

### Core runtime
Preferred language: Rust.

Rationale:
- memory safety without GC pauses in the core engine
- strong type system for selectors, plans, traces, and compiler outputs
- strong suitability for deterministic CLI/runtime tooling
- maintainable boundaries for domain/application logic
- good long-term fit for a performance-sensitive, tool-heavy platform

### Platform-native adapters
Use thin native adapters where platform integration benefits from native ecosystems.

- iOS adapter direction: Swift
- Android adapter direction: Kotlin (or Java where necessary)

Principle:
- keep platform-specific code thin
- keep business rules and deterministic orchestration out of platform adapters
- keep the largest amount of logic possible in the Rust core

## Cross-Platform Strategy

Shared abstractions are allowed only where they are semantically honest.

Likely shared concepts:
- launch app
- tap selector
- type text
- screenshot
- wait/assert visible state
- deep links
- logs

Likely platform-specific extensions:
- system dialogs
- simulator/emulator lifecycle peculiarities
- accessibility hierarchy nuances
- permission handling details

## Testing Strategy

### Domain tests
Target: near-100% coverage.

### Adapter contract tests
Target: verify platform adapters normalize behavior into domain/application contracts.

### Compilation golden tests
Target: spec input deterministically compiles into expected plan output.

### Integration tests
Target: simulator/emulator-backed validation using fixture apps.

## UI and design-system governance

Current interface priorities are:
- human CLI
- machine/agent CLI with structured output
- CI entrypoints

If we later introduce non-CLI/CI product UI surfaces, a design system must be established before UI implementation proceeds.

That design system should define at minimum:
- design tokens
- component primitives
- layout and navigation principles
- information density and artifact presentation patterns
- brand language suitable for developer tooling

This prevents presentation work from becoming an unstructured parallel architecture.

## Non-goals for early phases

- device farm orchestration
- cloud SaaS dashboard
- natural-language-only test execution in CI
- complete Appium compatibility
- real-device support before simulator/emulator foundation is solid
