# Product Requirements — Mobile Agent Runtime

## Problem

Existing mobile automation choices usually force an unhappy trade-off:
- high-maintenance frameworks with large operational overhead
- simple declarative tools with limited abstraction ceilings
- SaaS-oriented tooling that pulls important workflows out of local/CI control
- agent-hostile interfaces that are not designed for Claude CLI, Copilot CLI, Codex CLI, Hermes, and similar tools

## Product Thesis

A strong mobile automation platform should support three equally important operating modes:

1. Deterministic CI/CD execution
2. Local developer workflows
3. Agent-native exploration, authoring, and repair

## Users

### Primary
- mobile platform/dev productivity teams
- senior mobile engineers and QA automation engineers
- developers using agentic CLI tools during daily work

### Secondary
- engineering managers/directors who need traceability and maintainability
- CI platform owners

## Goals

### G1. Deterministic runner
The execution engine must be deterministic and explicit enough for CI use.

### G2. Agent-first interfaces
Agents must be able to inspect, control, author, and repair workflows using structured interfaces from day one.

### G3. Living specs
Project behavior and scope must remain documented continuously through maintained specs and architecture docs.

### G4. Traceability
Git history, branches, PRs, comments, and specs should provide a clear audit trail.

## MVP Scope

### Included
- iOS simulator support (initial target)
- Android emulator support (planned in MVP architecture, implementation may follow iOS)
- executable deterministic plan model
- Gherkin/OpenSpec-style requirement inputs compiled into executable plans
- interactive exploration/control interface for agents and developers
- artifact-rich execution traces
- local CLI + CI-friendly machine-readable output

### Excluded initially
- cloud device farm
- paid SaaS features
- real-device support
- broad framework compatibility layers
- flaky record/replay-only workflow

## Product Principles

- deterministic execution before magic
- repair assistance before autonomous hidden mutation
- structured outputs before pretty text
- clean architecture before rapid accumulation of shell glue
- platform truth over fake abstraction
- prefer safe, high-performance implementation languages for core runtime pieces

## Implementation Direction

Initial implementation direction:
- Rust core for deterministic engine/compiler/execution/tracing
- Swift where native iOS adapter code is needed
- Kotlin/Java where native Android adapter code is needed

This direction is motivated by:
- long-term maintainability
- performance of local/CI execution
- safety in complex runtime orchestration
- credibility with mobile engineers who care about systems quality

## Success Criteria

### Technical
- deterministic plan execution without LLM dependency
- stable JSON output for machine consumers
- high domain-layer test coverage
- clear separation of domain/application/infrastructure/presentation layers

### Product
- a developer can explore an app with an agent and generate a deterministic test artifact
- a CI pipeline can run the generated artifact repeatably
- a failing artifact can be diagnosed and repaired with agent assistance

## Open Questions

- iOS-first vs dual-platform MVP sequencing
- canonical executable plan serialization format
- exact selector precedence model
- fixture app strategy for integration testing
- how much automated repair is allowed locally vs in CI
